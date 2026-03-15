"""
依赖注入容器 (Dependency Injection Container)

提供接口与实现类的注册、自动依赖解析和实例管理功能。
"""

import inspect
from typing import Type, TypeVar, Dict, Any, Optional, Callable, Set
from enum import Enum


class Lifecycle(Enum):
    """生命周期类型"""
    SINGLETON = "singleton"  # 单例模式：整个容器生命周期内只创建一次
    TRANSIENT = "transient"  # 瞬态模式：每次请求都创建新实例


T = TypeVar('T')


class DIContainer:
    """
    依赖注入容器
    
    功能：
    1. 注册接口与实现类的映射
    2. 根据接口获取实例（支持单例和瞬态）
    3. 自动解析构造函数参数（基于类型注解）
    4. 支持工厂函数注册
    5. 支持实例直接注册
    6. 循环依赖检测
    
    使用示例：
        container = DIContainer()
        
        # 注册接口到实现类的映射
        container.register(IMap, Map, lifecycle=Lifecycle.SINGLETON)
        container.register(ITime, Time)
        
        # 注册工厂函数
        container.register_factory(IConfig, lambda: load_config("config.yaml"))
        
        # 注册实例
        container.register_instance(ILogger, logger_instance)
        
        # 解析实例（会自动注入依赖）
        map_instance = container.resolve(IMap)
    """
    
    def __init__(self):
        """初始化依赖注入容器"""
        # 接口到实现类的映射: {interface: (implementation_class, lifecycle)}
        self._bindings: Dict[Type, tuple] = {}
        
        # 单例实例缓存: {interface: instance}
        self._singletons: Dict[Type, Any] = {}
        
        # 工厂函数映射: {interface: factory_function}
        self._factories: Dict[Type, Callable] = {}
        
        # 正在解析的类型栈，用于检测循环依赖
        self._resolving_stack: Set[Type] = set()
    
    def register(
        self,
        interface: Type[T],
        implementation: Type[T],
        lifecycle: Lifecycle = Lifecycle.SINGLETON
    ) -> 'DIContainer':
        """
        注册接口与实现类的映射
        
        Args:
            interface: 接口类型（抽象基类或Protocol）
            implementation: 实现类
            lifecycle: 生命周期（单例或瞬态）
            
        Returns:
            self: 支持链式调用
        """
        if interface in self._factories:
            raise ValueError(f"接口 {interface.__name__} 已通过工厂函数注册")
        
        self._bindings[interface] = (implementation, lifecycle)
        return self
    
    def register_factory(
        self,
        interface: Type[T],
        factory: Callable[[], T],
        override: bool = False
    ) -> 'DIContainer':
        """
        注册工厂函数
        
        Args:
            interface: 接口类型
            factory: 工厂函数，无参数，返回实例
            override: 是否允许覆盖已注册的接口（默认False）
            
        Returns:
            self: 支持链式调用
        """
        if interface in self._bindings and not override:
            raise ValueError(f"接口 {interface.__name__} 已注册实现类")
        
        # 如果覆盖，需要先清理已有注册和缓存
        if override and interface in self._bindings:
            del self._bindings[interface]
        if override and interface in self._singletons:
            del self._singletons[interface]
        
        self._factories[interface] = factory
        return self
    
    def register_instance(
        self,
        interface: Type[T],
        instance: T
    ) -> 'DIContainer':
        """
        直接注册实例（作为单例）
        
        Args:
            interface: 接口类型
            instance: 已创建的实例
            
        Returns:
            self: 支持链式调用
        """
        self._singletons[interface] = instance
        self._bindings[interface] = (type(instance), Lifecycle.SINGLETON)
        return self
    
    def resolve(self, interface: Type[T]) -> T:
        """
        解析并获取接口的实例
        
        Args:
            interface: 接口类型
            
        Returns:
            实例对象
            
        Raises:
            ValueError: 接口未注册或存在循环依赖
        """
        # 检查是否已有单例实例
        if interface in self._singletons:
            return self._singletons[interface]
        
        # 检查循环依赖
        if interface in self._resolving_stack:
            stack_names = [t.__name__ for t in self._resolving_stack]
            raise ValueError(
                f"检测到循环依赖: {' -> '.join(stack_names)} -> {interface.__name__}"
            )
        
        # 检查工厂函数
        if interface in self._factories:
            instance = self._factories[interface]()
            # 工厂函数创建的实例始终作为单例缓存
            self._singletons[interface] = instance
            return instance
        
        # 检查接口是否已注册
        if interface not in self._bindings:
            raise ValueError(f"接口 {interface.__name__} 未注册")
        
        implementation, lifecycle = self._bindings[interface]
        
        # 标记正在解析
        self._resolving_stack.add(interface)
        
        try:
            # 创建实例（自动解析依赖）
            instance = self._create_instance(implementation)
            
            # 如果是单例，缓存实例
            if lifecycle == Lifecycle.SINGLETON:
                self._singletons[interface] = instance
            
            return instance
        finally:
            # 解析完成，从栈中移除
            self._resolving_stack.discard(interface)
    
    def _create_instance(self, implementation: Type[T]) -> T:
        """
        创建实例并自动注入依赖
        
        Args:
            implementation: 实现类
            
        Returns:
            创建的实例
        """
        # 获取构造函数签名
        init_signature = inspect.signature(implementation.__init__)
        
        # 解析构造函数参数
        kwargs = {}
        for param_name, param in init_signature.parameters.items():
            # 跳过 self 参数
            if param_name == 'self':
                continue
            
            # 获取参数类型注解
            if param.annotation != inspect.Parameter.empty:
                param_type = param.annotation
                
                # 尝试解析依赖
                try:
                    kwargs[param_name] = self.resolve(param_type)
                except ValueError:
                    # 如果依赖无法解析，检查是否有默认值
                    if param.default == inspect.Parameter.empty:
                        # 无默认值且无法解析，抛出异常
                        raise ValueError(
                            f"无法解析参数 '{param_name}' (类型: {param_type.__name__}) "
                            f"在类 {implementation.__name__} 的构造函数中"
                        )
                    # 有默认值，跳过此参数
            else:
                # 没有类型注解
                if param.default == inspect.Parameter.empty:
                    raise ValueError(
                        f"参数 '{param_name}' 在类 {implementation.__name__} 中缺少类型注解且无默认值"
                    )
        
        # 创建实例
        return implementation(**kwargs)
    
    def is_registered(self, interface: Type) -> bool:
        """
        检查接口是否已注册
        
        Args:
            interface: 接口类型
            
        Returns:
            是否已注册
        """
        return (interface in self._bindings or 
                interface in self._factories or 
                interface in self._singletons)
    
    def clear(self):
        """清除所有注册和缓存的实例"""
        self._bindings.clear()
        self._singletons.clear()
        self._factories.clear()
        self._resolving_stack.clear()
    
    def reset_singletons(self):
        """重置所有单例实例（保留注册映射）"""
        self._singletons.clear()
        self._resolving_stack.clear()
    
    def get_binding_info(self, interface: Type) -> Optional[Dict[str, Any]]:
        """
        获取接口的绑定信息
        
        Args:
            interface: 接口类型
            
        Returns:
            绑定信息字典，如果未注册则返回 None
        """
        if interface in self._bindings:
            implementation, lifecycle = self._bindings[interface]
            return {
                'interface': interface.__name__,
                'implementation': implementation.__name__,
                'lifecycle': lifecycle.value,
                'has_instance': interface in self._singletons
            }
        elif interface in self._factories:
            return {
                'interface': interface.__name__,
                'type': 'factory',
                'has_instance': interface in self._singletons
            }
        return None
    
    def get_all_bindings(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有注册的绑定信息
        
        Returns:
            绑定信息字典
        """
        result = {}
        
        # 类绑定
        for interface in self._bindings:
            info = self.get_binding_info(interface)
            if info:
                result[interface.__name__] = info
        
        # 工厂绑定
        for interface in self._factories:
            if interface not in result:
                info = self.get_binding_info(interface)
                if info:
                    result[interface.__name__] = info
        
        return result


# 全局容器实例（可选）
_global_container: Optional[DIContainer] = None


def get_global_container() -> DIContainer:
    """
    获取全局 DI 容器实例（单例模式）
    
    Returns:
        全局 DIContainer 实例
    """
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def reset_global_container():
    """重置全局容器"""
    global _global_container
    _global_container = None


# ========================================
# 配置文件加载功能
# ========================================

def load_module_from_path(module_path: str) -> Type:
    """
    从字符串路径动态导入类
    
    Args:
        module_path: 完整的模块路径，如 "src.environment.map.Map"
        
    Returns:
        导入的类
        
    Raises:
        ImportError: 模块导入失败
        AttributeError: 类不存在
        
    Example:
        Map = load_module_from_path("src.environment.map.Map")
    """
    try:
        # 分离模块路径和类名
        # 例如: "src.environment.map.Map" -> "src.environment.map" 和 "Map"
        parts = module_path.rsplit('.', 1)
        if len(parts) != 2:
            raise ValueError(f"无效的模块路径格式: {module_path}")
        
        module_name, class_name = parts
        
        # 动态导入模块
        import importlib
        module = importlib.import_module(module_name)
        
        # 获取类
        cls = getattr(module, class_name)
        return cls
    except ImportError as e:
        raise ImportError(f"无法导入模块 {module_name}: {e}")
    except AttributeError as e:
        raise AttributeError(f"模块 {module_name} 中不存在类 {class_name}: {e}")


def load_implementations_from_config(
    config: Dict[str, Any],
    lifecycle: Lifecycle = Lifecycle.SINGLETON
) -> Dict[Type, Type]:
    """
    从配置字典加载模块实现映射
    
    Args:
        config: 配置字典，包含 module_implementations 部分
        lifecycle: 默认生命周期
        
    Returns:
        {接口类: 实现类} 的映射字典
        
    Example:
        config = {
            'module_implementations': {
                'IMap': 'src.environment.map.Map',
                'ITime': 'src.environment.time.Time',
            }
        }
        implementations = load_implementations_from_config(config)
    """
    if 'module_implementations' not in config:
        return {}
    
    implementations = {}
    module_implementations = config['module_implementations']
    
    # 首先导入所有接口
    try:
        from src import interfaces
        import importlib
        importlib.reload(interfaces)
    except ImportError:
        raise ImportError("无法导入 src.interfaces 模块，请确保接口模块存在")
    
    for interface_name, implementation_path in module_implementations.items():
        try:
            # 从 interfaces 模块获取接口类
            interface = getattr(interfaces, interface_name)
            
            # 动态导入实现类
            implementation = load_module_from_path(implementation_path)
            
            implementations[interface] = implementation
        except AttributeError:
            print(f"警告: 接口 {interface_name} 在 src.interfaces 中不存在，跳过")
        except (ImportError, ValueError) as e:
            print(f"警告: 无法加载实现类 {implementation_path}: {e}")
    
    return implementations


def load_implementations_from_yaml(
    yaml_path: str,
    lifecycle: Lifecycle = Lifecycle.SINGLETON
) -> Dict[Type, Type]:
    """
    从 YAML 配置文件加载模块实现映射
    
    Args:
        yaml_path: YAML 配置文件路径
        lifecycle: 默认生命周期
        
    Returns:
        {接口类: 实现类} 的映射字典
        
    Example:
        implementations = load_implementations_from_yaml("config/template/modules_config.yaml")
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("需要安装 PyYAML: pip install pyyaml")
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件不存在: {yaml_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析错误: {e}")
    
    return load_implementations_from_config(config, lifecycle)


def register_from_config(
    container: DIContainer,
    config: Dict[str, Any],
    lifecycle: Lifecycle = Lifecycle.SINGLETON
) -> DIContainer:
    """
    从配置字典注册模块到容器
    
    Args:
        container: DIContainer 实例
        config: 配置字典
        lifecycle: 默认生命周期
        
    Returns:
        container: 支持链式调用
        
    Example:
        container = DIContainer()
        register_from_config(container, config)
    """
    implementations = load_implementations_from_config(config, lifecycle)
    
    for interface, implementation in implementations.items():
        container.register(interface, implementation, lifecycle)
    
    return container


def register_from_yaml(
    container: DIContainer,
    yaml_path: str,
    lifecycle: Lifecycle = Lifecycle.SINGLETON
) -> DIContainer:
    """
    从 YAML 配置文件注册模块到容器
    
    Args:
        container: DIContainer 实例
        yaml_path: YAML 配置文件路径
        lifecycle: 默认生命周期
        
    Returns:
        container: 支持链式调用
        
    Example:
        container = DIContainer()
        register_from_yaml(container, "config/template/modules_config.yaml")
        
        # 然后可以解析依赖
        map_instance = container.resolve(IMap)
    """
    implementations = load_implementations_from_yaml(yaml_path, lifecycle)
    
    for interface, implementation in implementations.items():
        container.register(interface, implementation, lifecycle)
    
    print(f"从配置文件 {yaml_path} 注册了 {len(implementations)} 个模块")
    
    return container


def create_container_from_yaml(
    yaml_path: str,
    lifecycle: Lifecycle = Lifecycle.SINGLETON
) -> DIContainer:
    """
    从 YAML 配置文件创建并配置容器（便捷方法）
    
    Args:
        yaml_path: YAML 配置文件路径
        lifecycle: 默认生命周期
        
    Returns:
        配置好的 DIContainer 实例
        
    Example:
        container = create_container_from_yaml("config/template/modules_config.yaml")
        map_instance = container.resolve(IMap)
    """
    container = DIContainer()
    register_from_yaml(container, yaml_path, lifecycle)
    return container

