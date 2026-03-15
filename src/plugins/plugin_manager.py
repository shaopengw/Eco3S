"""
插件管理器 (PluginManager)

负责插件的加载、初始化、管理和卸载，提供插件系统的统一入口。
"""

from typing import Dict, List, Type, Optional, Any
import logging
from .base_plugin import BasePlugin
from .plugin_context import PluginContext, EventBus, PluginRegistry


class PluginManager:
    """
    插件管理器
    
    提供插件的完整生命周期管理：
    1. 创建插件上下文
    2. 加载和初始化插件
    3. 插件依赖解析
    4. 卸载插件
    
    Example:
        ```python
        from src.utils.log_manager import LogManager
        
        # 创建管理器
        manager = PluginManager(
            config={'simulation': {'population': 1000}},
            logger=LogManager.get_logger('plugin_system')
        )
        
        # 加载插件
        plugin = MyPlugin()
        manager.load_plugin('my_plugin', plugin)
        
        # 获取插件
        loaded_plugin = manager.get_plugin('my_plugin')
        
        # 卸载插件
        manager.unload_plugin('my_plugin')
        
        # 卸载所有插件
        manager.unload_all()
        ```
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化插件管理器
        
        Args:
            config: 插件配置字典
            logger: 日志记录器
        """
        self._event_bus = EventBus()
        self._registry = PluginRegistry()
        
        self._context = PluginContext(
            config=config or {},
            logger=logger,
            event_bus=self._event_bus,
            registry=self._registry
        )
        
        self._load_order: List[str] = []  # 记录加载顺序
    
    def load_plugin(self, name: str, plugin: BasePlugin) -> None:
        """
        加载插件
        
        Args:
            name: 插件名称
            plugin: 插件实例
            
        Raises:
            ValueError: 如果插件名称已存在
            RuntimeError: 如果插件加载失败
            
        Note:
            - 会自动调用 plugin.init() 和 plugin.on_load()
            - 会检查插件依赖并验证
        """
        # 检查插件是否已加载
        if self._registry.has(name):
            raise ValueError(f"Plugin '{name}' is already loaded")
        
        try:
            # 1. 初始化插件（传递上下文）
            self._log_info(f"Initializing plugin: {name}")
            plugin.init(self._context)
            
            # 2. 获取元数据
            metadata = plugin.get_metadata()
            self._log_info(f"Plugin metadata: {metadata}")
            
            # 3. 检查依赖
            dependencies = metadata.get('dependencies', [])
            self._check_dependencies(name, dependencies)
            
            # 4. 注册插件
            self._registry.register(name, plugin)
            
            # 5. 调用加载钩子
            self._log_info(f"Loading plugin: {name}")
            plugin.on_load()
            plugin._mark_loaded()
            
            # 6. 记录加载顺序
            self._load_order.append(name)
            
            # 7. 发布插件加载事件
            self._event_bus.publish('plugin_loaded', {
                'name': name,
                'metadata': metadata
            })
            
            self._log_info(f"Plugin '{name}' loaded successfully")
            
        except Exception as e:
            self._log_error(f"Failed to load plugin '{name}': {e}")
            # 清理可能的部分注册
            self._registry.unregister(name)
            raise RuntimeError(f"Plugin '{name}' load failed: {e}") from e
    
    def unload_plugin(self, name: str) -> None:
        """
        卸载插件
        
        Args:
            name: 插件名称
            
        Raises:
            ValueError: 如果插件不存在
            RuntimeError: 如果插件卸载失败
        """
        plugin = self._registry.get(name)
        if not plugin:
            raise ValueError(f"Plugin '{name}' is not loaded")
        
        try:
            # 1. 调用卸载钩子
            self._log_info(f"Unloading plugin: {name}")
            plugin.on_unload()
            plugin._mark_unloaded()
            
            # 2. 从注册表移除
            self._registry.unregister(name)
            
            # 3. 从加载顺序中移除
            if name in self._load_order:
                self._load_order.remove(name)
            
            # 4. 发布插件卸载事件
            self._event_bus.publish('plugin_unloaded', {'name': name})
            
            self._log_info(f"Plugin '{name}' unloaded successfully")
            
        except Exception as e:
            self._log_error(f"Failed to unload plugin '{name}': {e}")
            raise RuntimeError(f"Plugin '{name}' unload failed: {e}") from e
    
    def unload_all(self) -> None:
        """
        卸载所有插件（按加载顺序的逆序）
        
        Note:
            - 按照加载顺序的逆序卸载，确保依赖关系正确
            - 即使某个插件卸载失败，也会尝试卸载其他插件
        """
        self._log_info("Unloading all plugins...")
        
        # 逆序卸载
        for name in reversed(self._load_order.copy()):
            try:
                self.unload_plugin(name)
            except Exception as e:
                self._log_error(f"Error unloading plugin '{name}': {e}")
        
        self._load_order.clear()
        self._log_info("All plugins unloaded")
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """
        获取已加载的插件
        
        Args:
            name: 插件名称
            
        Returns:
            插件实例，如果不存在返回 None
        """
        return self._registry.get(name)
    
    def has_plugin(self, name: str) -> bool:
        """
        检查插件是否已加载
        
        Args:
            name: 插件名称
            
        Returns:
            如果插件已加载返回 True，否则返回 False
        """
        return self._registry.has(name)
    
    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """
        获取所有已加载的插件
        
        Returns:
            插件名称到插件实例的映射
        """
        return self._registry.get_all()
    
    def get_load_order(self) -> List[str]:
        """
        获取插件加载顺序
        
        Returns:
            插件名称列表（按加载顺序）
        """
        return self._load_order.copy()
    
    @property
    def context(self) -> PluginContext:
        """
        获取插件上下文
        
        Returns:
            PluginContext: 插件上下文对象
        """
        return self._context
    
    @property
    def event_bus(self) -> EventBus:
        """
        获取事件总线
        
        Returns:
            EventBus: 事件总线对象
        """
        return self._event_bus
    
    def _check_dependencies(self, plugin_name: str, dependencies: List[str]) -> None:
        """
        检查插件依赖是否满足
        
        Args:
            plugin_name: 插件名称
            dependencies: 依赖的插件名称列表
            
        Raises:
            ValueError: 如果依赖不满足
        """
        for dep in dependencies:
            if not self._registry.has(dep):
                raise ValueError(
                    f"Plugin '{plugin_name}' depends on '{dep}', "
                    f"but '{dep}' is not loaded"
                )
    
    def _log_info(self, message: str) -> None:
        """记录 INFO 日志"""
        if self._context.logger:
            self._context.logger.info(message)
    
    def _log_error(self, message: str) -> None:
        """记录 ERROR 日志"""
        if self._context.logger:
            self._context.logger.error(message)


class PluginLoader:
    """
    插件加载器（工具类）
    
    提供从不同来源加载插件的便捷方法。
    
    Example:
        ```python
        # 从类加载
        loader = PluginLoader(manager)
        loader.load_from_class('my_plugin', MyPluginClass, width=100, height=100)
        
        # 从模块路径加载
        loader.load_from_module('custom_map', 'plugins.custom_map.CustomMap', 
                                width=100, height=100)
        ```
    """
    
    def __init__(self, manager: PluginManager):
        """
        初始化插件加载器
        
        Args:
            manager: 插件管理器实例
        """
        self._manager = manager
    
    def load_from_class(
        self,
        name: str,
        plugin_class: Type[BasePlugin],
        **init_kwargs
    ) -> None:
        """
        从插件类加载插件
        
        Args:
            name: 插件名称
            plugin_class: 插件类
            **init_kwargs: 传递给插件构造函数的参数
        """
        plugin = plugin_class(**init_kwargs)
        self._manager.load_plugin(name, plugin)
    
    def load_from_module(
        self,
        name: str,
        module_path: str,
        **init_kwargs
    ) -> None:
        """
        从模块路径加载插件
        
        Args:
            name: 插件名称
            module_path: 完整的模块路径（如 "plugins.custom_map.CustomMap"）
            **init_kwargs: 传递给插件构造函数的参数
        """
        # 动态导入
        parts = module_path.rsplit('.', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid module path: {module_path}")
        
        module_name, class_name = parts
        
        import importlib
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
        
        self.load_from_class(name, plugin_class, **init_kwargs)
