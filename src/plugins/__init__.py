"""
插件系统模块

提供插件基础设施，包括插件基类、上下文管理、插件接口定义、插件管理器和插件注册表。
"""

from .base_plugin import BasePlugin
from .plugin_context import PluginContext, EventBus
from .plugin_context import PluginRegistry as SimplePluginRegistry  # 简单版本
from .plugin_registry import PluginRegistry, PluginMetadata  # 增强版本
from .plugin_manager import PluginManager, PluginLoader
from .plugin_interfaces import (
    IMapPlugin,
    ITimePlugin,
    IPopulationPlugin,
    ITownsPlugin,
    ISocialNetworkPlugin,
    ITransportEconomyPlugin,
    IClimatePlugin,
    IJobMarketPlugin,
    IGovernmentPlugin,
    IRebellionPlugin,
    PLUGIN_INTERFACE_MAP,
)

__all__ = [
    # 基础类
    'BasePlugin',
    'PluginContext',
    'EventBus',
    
    # 注册表（两个版本）
    'SimplePluginRegistry',  # 简单版本（用于 PluginContext）
    'PluginRegistry',        # 增强版本（主要使用）
    'PluginMetadata',
    
    # 管理器
    'PluginManager',
    'PluginLoader',
    
    # 插件接口
    'IMapPlugin',
    'ITimePlugin',
    'IPopulationPlugin',
    'ITownsPlugin',
    'ISocialNetworkPlugin',
    'ITransportEconomyPlugin',
    'IClimatePlugin',
    'IJobMarketPlugin',
    'IGovernmentPlugin',
    'IRebellionPlugin',
    'PLUGIN_INTERFACE_MAP',
]
