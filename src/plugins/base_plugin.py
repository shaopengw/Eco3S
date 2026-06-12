"""
插件基类 (BasePlugin)

定义插件的基本生命周期和元数据接口。所有插件都必须继承此类。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple


class BasePlugin(ABC):
    """
    插件抽象基类
    
    所有插件必须继承此类并实现其抽象方法。提供插件生命周期管理和元数据接口。
    
    生命周期：
        1. __init__() - 插件实例化
        2. init(context) - 插件初始化（接收上下文）
        3. on_load() - 插件加载时的钩子
        4. [使用阶段]
        5. on_unload() - 插件卸载时的钩子
    """
    
    def __init__(self):
        """
        插件构造函数

        Note:
            - 子类可以重写此方法进行基本初始化
            - 不应在此处进行需要上下文的初始化（使用 init() 方法）
        """
        self._context: Optional['PluginContext'] = None
        self._loaded: bool = False
        self._event_subscriptions: List[Tuple[str, Any]] = []
        """记录本插件订阅的所有事件，用于 on_unload 时自动清理"""
    
    def init(self, context: 'PluginContext') -> None:
        """
        初始化插件（接收插件上下文）

        Args:
            context: PluginContext - 插件上下文对象，包含配置、日志等

        Note:
            - 此方法在插件加载前调用
            - 用于设置插件运行所需的资源和配置
            - 子类应覆写此方法以保存上下文引用并读取配置

        Example:
            ```python
            def init(self, context: PluginContext) -> None:
                super().init(context)
                self.config = context.config.get('my_plugin', {})
            ```
        """
        self._context = context

    def on_load(self) -> None:
        """
        插件加载时的钩子函数

        Note:
            - 在 init() 之后、插件正式使用之前调用
            - 用于执行插件加载时的初始化逻辑（如注册事件监听器、建立连接等）
            - 此时可以访问 self._context
            - 加载失败应抛出异常
            - 默认实现仅标记加载状态；需要特殊逻辑的插件请覆写

        Example:
            ```python
            def on_load(self) -> None:
                super().on_load()
                self._context.event_bus.subscribe('simulation_start', self._handle_start)
            ```
        """
        self._mark_loaded()

    def on_unload(self) -> None:
        """
        插件卸载时的钩子函数

        Note:
            - 在插件被卸载前调用
            - 用于清理资源（如取消注册事件、关闭连接等）
            - 卸载失败应抛出异常
            - 默认实现会自动清理通过 subscribe_event() 注册的事件订阅

        Example:
            ```python
            def on_unload(self) -> None:
                self._context.event_bus.unsubscribe('simulation_start', self._handle_start)
                super().on_unload()
            ```
        """
        self.clear_event_subscriptions()
        self._mark_unloaded()

    def subscribe_event(self, event_name: str, callback) -> None:
        """
        订阅事件（自动记录，卸载时自动清理）

        Args:
            event_name: 事件名称
            callback: 回调函数

        Example:
            ```python
            self.subscribe_event(PluginEvent.TIME_ADVANCED, self._on_time_advanced)
            ```

        Note:
            请从 `src.plugins` 导入 `PluginEvent`：
            `from src.plugins import PluginEvent`
        """
        if self._context and self._context.event_bus:
            self._context.event_bus.subscribe(event_name, callback)
            self._event_subscriptions.append((event_name, callback))

    def unsubscribe_event(self, event_name: str, callback) -> None:
        """
        取消订阅事件（同时从自动清理列表中移除）

        Args:
            event_name: 事件名称
            callback: 回调函数
        """
        if self._context and self._context.event_bus:
            self._context.event_bus.unsubscribe(event_name, callback)
        try:
            self._event_subscriptions.remove((event_name, callback))
        except ValueError:
            pass

    def publish_event(self, event_name: str, data: Any = None) -> None:
        """
        发布事件

        Args:
            event_name: 事件名称
            data: 事件数据（可选）
        """
        if self._context and self._context.event_bus:
            self._context.event_bus.publish(event_name, data)

    def clear_event_subscriptions(self) -> None:
        """取消本插件注册的所有事件订阅（通常由 on_unload 自动调用）"""
        if self._context and self._context.event_bus:
            for event_name, callback in list(self._event_subscriptions):
                try:
                    self._context.event_bus.unsubscribe(event_name, callback)
                except Exception:
                    pass
        self._event_subscriptions.clear()

    def get_metadata(self) -> Dict[str, Any]:
        """
        获取插件元数据

        Returns:
            Dict[str, Any]: 插件元数据字典。默认实现返回类名作为名称；
                若插件已在注册表中，建议从注册表元数据读取，或覆写此方法。

        Example:
            ```python
            def get_metadata(self) -> Dict[str, Any]:
                return {
                    "name": "CustomMap",
                    "version": "1.0.0",
                    "description": "Custom map implementation with advanced features",
                    "author": "AgentWorld Team",
                    "dependencies": []
                }
            ```
        """
        return {
            "name": self.__class__.__name__,
            "version": "unknown",
            "description": f"Auto-registered plugin {self.__class__.__name__}",
            "author": "unknown",
            "dependencies": [],
        }
    
    @property
    def context(self) -> Optional['PluginContext']:
        """
        获取插件上下文
        
        Returns:
            Optional[PluginContext]: 插件上下文对象，如果未初始化则返回 None
        """
        return self._context
    
    @property
    def is_loaded(self) -> bool:
        """
        检查插件是否已加载
        
        Returns:
            bool: 如果插件已加载返回 True，否则返回 False
        """
        return self._loaded
    
    def _mark_loaded(self) -> None:
        """标记插件为已加载（内部使用）"""
        self._loaded = True
    
    def _mark_unloaded(self) -> None:
        """标记插件为未加载（内部使用）"""
        self._loaded = False
