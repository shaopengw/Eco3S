"""
插件系统模块

提供插件基础设施，包括插件基类、上下文管理、插件接口定义、插件管理器和插件注册表。
"""

from .base_plugin import BasePlugin
from .plugin_context import PluginContext, EventBus
from .plugin_registry import PluginRegistry, PluginMetadata
from .events import PluginEvent

__all__ = [
    # 基础类
    'BasePlugin',
    'PluginContext',
    'EventBus',

    # 事件
    'PluginEvent',

    # 注册表
    'PluginRegistry',
    'PluginMetadata',
]
