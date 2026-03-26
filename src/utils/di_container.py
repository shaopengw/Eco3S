"""src.utils.di_container

依赖注入容器 (Dependency Injection Container)

- 只负责“构造期注入 + 生命周期管理（单例/瞬态/工厂/实例）”。
- 模块选择/插件发现与加载由插件系统负责，不再由 DI 从 YAML 注册模块实现。
"""

import inspect
from typing import Type, TypeVar, Dict, Any, Optional, Callable, Set, get_type_hints, get_origin, get_args
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
        map_instance = container.get(IMap)
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
    
    def get(self, interface: Type[T]) -> T:
        """获取接口的实例。

        - 支持单例与瞬态
        - 支持工厂函数/实例注册
        - 自动解析构造函数依赖（基于类型注解）

        Raises:
            ValueError: 接口未注册或存在循环依赖
        """
        # 检查是否已有单例实例
        if interface in self._singletons:
            return self._singletons[interface]
        
        def _type_name(t: Any) -> str:
            return getattr(t, '__name__', str(t))

        # 检查循环依赖
        if interface in self._resolving_stack:
            stack_names = [_type_name(t) for t in self._resolving_stack]
            raise ValueError(
                f"检测到循环依赖: {' -> '.join(stack_names)} -> {_type_name(interface)}"
            )
        
        # 检查工厂函数
        if interface in self._factories:
            instance = self._factories[interface]()
            # 工厂函数创建的实例始终作为单例缓存
            self._singletons[interface] = instance
            return instance
        
        # 检查接口是否已注册
        if interface not in self._bindings:
            raise ValueError(f"接口 {_type_name(interface)} 未注册")
        
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

    def create(self, implementation: Type[T], **explicit_kwargs: Any) -> T:
        """创建任意实现类实例，并自动注入缺失依赖。

        与 `get()` 的区别：
        - `get()` 需要先注册 interface->implementation
        - `create()` 直接对指定实现类构造实例

        `explicit_kwargs` 会覆盖自动注入的同名参数。
        """
        init_signature = inspect.signature(implementation.__init__)

        # 尝试解析 forward references / __future__.annotations 产生的字符串注解
        # 若解析失败则回退为原始 annotation。
        try:
            resolved_hints: Dict[str, Any] = get_type_hints(implementation.__init__)
        except Exception:
            resolved_hints = {}

        def _normalize_hint(hint: Any) -> Any:
            """将 Optional/Annotated 等 typing hint 规约为可 resolve 的具体类型。"""
            if hint is None:
                return None
            origin = get_origin(hint)
            if origin is None:
                return hint
            # Optional[T] 等价于 Union[T, NoneType]
            if origin is getattr(__import__('typing'), 'Union'):
                args = [a for a in get_args(hint) if a is not type(None)]  # noqa: E721
                return args[0] if args else hint
            # Annotated[T, ...] -> T
            if str(origin) == 'typing.Annotated':
                args = get_args(hint)
                return args[0] if args else hint
            return hint

        kwargs: Dict[str, Any] = {}
        for param_name, param in init_signature.parameters.items():
            if param_name == 'self':
                continue

            # 调用方显式提供的参数优先
            if param_name in explicit_kwargs:
                kwargs[param_name] = explicit_kwargs[param_name]
                continue

            # 基于类型注解自动注入
            raw_hint = resolved_hints.get(param_name, param.annotation)
            if raw_hint != inspect.Parameter.empty:
                param_type = _normalize_hint(raw_hint)
                # 字符串注解 / Any 等无法可靠注入的类型，直接跳过（若有默认值则使用默认值）
                if isinstance(param_type, str) or param_type is Any:
                    if param.default != inspect.Parameter.empty:
                        continue
                    raise ValueError(
                        f"参数 '{param_name}' 在类 {implementation.__name__} 中类型注解无法解析且无默认值"
                    )
                try:
                    kwargs[param_name] = self.get(param_type)
                    continue
                except ValueError:
                    if param.default != inspect.Parameter.empty:
                        continue
                    raise ValueError(
                        f"无法解析参数 '{param_name}' (类型: {getattr(param_type, '__name__', str(param_type))}) "
                        f"在类 {implementation.__name__} 的构造函数中"
                    )

            # 没有类型注解
            if param.default != inspect.Parameter.empty:
                continue
            raise ValueError(
                f"参数 '{param_name}' 在类 {implementation.__name__} 中缺少类型注解且无默认值"
            )

        # 允许额外的显式参数（实现类构造函数如果不接收会自然抛错）
        for k, v in explicit_kwargs.items():
            if k not in kwargs:
                kwargs[k] = v

        return implementation(**kwargs)
    
    def _create_instance(self, implementation: Type[T]) -> T:
        """
        创建实例并自动注入依赖
        
        Args:
            implementation: 实现类
            
        Returns:
            创建的实例
        """
        # 统一走 create()，以支持 forward refs / __future__.annotations
        return self.create(implementation)
    
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

