"""src.simulation.plugin_access

放置 Simulator 初始化时的固定工具函数。

目标：
- Simulator/TEOGSimulator 等统一通过 module_name 获取插件实例
- 失败时给出一致的错误信息
"""

from __future__ import annotations

from typing import Any


def require_module(plugin_registry: Any, module_name: str):
    """从插件注册中心按模块名获取插件实例；不存在则抛错。"""
    if plugin_registry is None:
        raise ValueError(f"插件注册中心为空，无法获取模块 '{module_name}'")

    plugin = plugin_registry.get_plugin(module_name)
    if plugin is None:
        raise ValueError(f"模块 '{module_name}' 未通过插件加载")

    return plugin
