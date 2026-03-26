"""
插件上下文 (PluginContext)

为插件提供运行时上下文，包括配置、日志、事件总线和注册表等。
"""

from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass, field
from .base_plugin import BasePlugin


@dataclass
class PluginContext:
    """
    插件上下文类
    
    提供插件运行所需的所有上下文信息：
    - config: 配置信息
    - logger: 日志记录器
    - event_bus: 事件总线（用于插件间通信）
    - registry: 插件注册表（用于查询其他插件）
    - metadata: 额外的元数据
    
    Example:
        ```python
        from src.utils.log_manager import LogManager
        
        # 创建上下文
        context = PluginContext(
            config={'simulation': {'population': 1000}},
            logger=LogManager.get_logger('plugin_system'),
            event_bus=EventBus(),
            registry=PluginRegistry()
        )
        
        # 在插件中使用
        plugin = MyPlugin()
        plugin.init(context)
        ```
    """
    
    config: Dict[str, Any] = field(default_factory=dict)
    """插件配置字典，通常从配置文件加载"""
    
    logger: Optional[logging.Logger] = None
    """日志记录器，用于插件日志输出"""
    
    event_bus: Optional['EventBus'] = None
    """事件总线，用于插件间事件驱动通信"""
    
    registry: Optional['PluginRegistry'] = None
    """插件注册表，用于查询和访问其他已加载的插件"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """额外的元数据，可用于存储自定义信息"""
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的嵌套键）
        
        Args:
            key: 配置键，支持点号分隔访问嵌套值（如 "simulation.population"）
            default: 默认值，如果键不存在则返回
            
        Returns:
            配置值或默认值
            
        Example:
            ```python
            population = context.get_config('simulation.population', 1000)
            ```
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config(self, key: str, value: Any) -> None:
        """
        设置配置值（支持点号分隔的嵌套键）
        
        Args:
            key: 配置键，支持点号分隔设置嵌套值
            value: 配置值
            
        Example:
            ```python
            context.set_config('simulation.population', 2000)
            ```
        """
        keys = key.split('.')
        config = self.config
        
        # 导航到目标位置
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    def log_info(self, message: str) -> None:
        """便捷方法：记录 INFO 级别日志"""
        if self.logger:
            self.logger.info(message)
    
    def log_warning(self, message: str) -> None:
        """便捷方法：记录 WARNING 级别日志"""
        if self.logger:
            self.logger.warning(message)
    
    def log_error(self, message: str) -> None:
        """便捷方法：记录 ERROR 级别日志"""
        if self.logger:
            self.logger.error(message)
    
    def log_debug(self, message: str) -> None:
        """便捷方法：记录 DEBUG 级别日志"""
        if self.logger:
            self.logger.debug(message)


class EventBus:
    """
    简单的事件总线实现
    
    用于插件间的事件驱动通信。
    
    Example:
        ```python
        bus = EventBus()
        
        # 订阅事件
        def on_start(data):
            print(f"Simulation started with {data['population']} residents")
        
        bus.subscribe('simulation_start', on_start)
        
        # 发布事件
        bus.publish('simulation_start', {'population': 1000})
        
        # 取消订阅
        bus.unsubscribe('simulation_start', on_start)
        ```
    """
    
    def __init__(self):
        """初始化事件总线"""
        self._subscribers: Dict[str, list] = {}
    
    def subscribe(self, event_name: str, callback) -> None:
        """
        订阅事件
        
        Args:
            event_name: 事件名称
            callback: 回调函数，接收事件数据作为参数
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)
    
    def unsubscribe(self, event_name: str, callback) -> None:
        """
        取消订阅事件
        
        Args:
            event_name: 事件名称
            callback: 要移除的回调函数
        """
        if event_name in self._subscribers:
            if callback in self._subscribers[event_name]:
                self._subscribers[event_name].remove(callback)
    
    def publish(self, event_name: str, data: Any = None) -> None:
        """
        发布事件
        
        Args:
            event_name: 事件名称
            data: 事件数据（可选）
        """
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    callback(data)
                except Exception as e:
                    # 捕获回调异常，避免影响其他订阅者
                    print(f"Error in event handler for '{event_name}': {e}")
    
    def clear(self, event_name: Optional[str] = None) -> None:
        """
        清除订阅
        
        Args:
            event_name: 要清除的事件名称，如果为 None 则清除所有
        """
        if event_name:
            self._subscribers.pop(event_name, None)
        else:
            self._subscribers.clear()


class PluginRegistry:
    """
    插件注册表
    
    用于管理和查询已加载的插件。
    
    Example:
        ```python
        registry = PluginRegistry()
        
        # 注册插件
        plugin = MyPlugin()
        registry.register('my_plugin', plugin)
        
        # 查询插件
        plugin = registry.get('my_plugin')
        
        # 检查插件是否存在
        if registry.has('my_plugin'):
            print("Plugin exists")
        
        # 获取所有插件
        all_plugins = registry.get_all()
        ```
    """
    
    def __init__(self):
        """初始化插件注册表"""
        self._plugins: Dict[str, 'BasePlugin'] = {}
    
    def register(self, name: str, plugin: 'BasePlugin') -> None:
        """
        注册插件
        
        Args:
            name: 插件名称
            plugin: 插件实例
        """
        self._plugins[name] = plugin
    
    def unregister(self, name: str) -> None:
        """
        注销插件
        
        Args:
            name: 插件名称
        """
        self._plugins.pop(name, None)
    
    def get(self, name: str) -> Optional['BasePlugin']:
        """
        获取插件
        
        Args:
            name: 插件名称
            
        Returns:
            插件实例，如果不存在返回 None
        """
        return self._plugins.get(name)
    
    def has(self, name: str) -> bool:
        """
        检查插件是否存在
        
        Args:
            name: 插件名称
            
        Returns:
            如果插件存在返回 True，否则返回 False
        """
        return name in self._plugins
    
    def get_all(self) -> Dict[str, 'BasePlugin']:
        """
        获取所有插件
        
        Returns:
            插件名称到插件实例的映射
        """
        return self._plugins.copy()
    
    def clear(self) -> None:
        """清空注册表"""
        self._plugins.clear()
