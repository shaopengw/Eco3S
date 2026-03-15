"""
插件基类 (BasePlugin)

定义插件的基本生命周期和元数据接口。所有插件都必须继承此类。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


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
    
    @abstractmethod
    def init(self, context: 'PluginContext') -> None:
        """
        初始化插件（接收插件上下文）
        
        Args:
            context: PluginContext - 插件上下文对象，包含配置、日志等
            
        Note:
            - 此方法在插件加载前调用
            - 用于设置插件运行所需的资源和配置
            - 必须调用 `self._context = context` 保存上下文引用
            
        Example:
            ```python
            def init(self, context: PluginContext) -> None:
                self._context = context
                self.logger = context.logger
                self.config = context.config.get('my_plugin', {})
            ```
        """
        pass
    
    @abstractmethod
    def on_load(self) -> None:
        """
        插件加载时的钩子函数
        
        Note:
            - 在 init() 之后、插件正式使用之前调用
            - 用于执行插件加载时的初始化逻辑（如注册事件监听器、建立连接等）
            - 此时可以访问 self._context
            - 加载失败应抛出异常
            
        Example:
            ```python
            def on_load(self) -> None:
                self._context.logger.info(f"Loading plugin: {self.get_metadata()['name']}")
                self._context.event_bus.subscribe('simulation_start', self._handle_start)
                self._loaded = True
            ```
        """
        pass
    
    @abstractmethod
    def on_unload(self) -> None:
        """
        插件卸载时的钩子函数
        
        Note:
            - 在插件被卸载前调用
            - 用于清理资源（如取消注册事件、关闭连接等）
            - 卸载失败应抛出异常
            
        Example:
            ```python
            def on_unload(self) -> None:
                self._context.logger.info(f"Unloading plugin: {self.get_metadata()['name']}")
                self._context.event_bus.unsubscribe('simulation_start', self._handle_start)
                self._loaded = False
            ```
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取插件元数据
        
        Returns:
            Dict[str, Any]: 插件元数据字典，必须包含以下键：
                - name: str - 插件名称
                - version: str - 插件版本（建议使用语义化版本）
                - description: str - 插件描述
                - author: str - 插件作者
                - dependencies: List[str] - 依赖的其他插件名称（可选）
                
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
        pass
    
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
