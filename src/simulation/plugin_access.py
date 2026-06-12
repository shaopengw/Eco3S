"""src.simulation.plugin_access

放置 Simulator 初始化时的固定工具函数。

目标：
- Simulator/TEOGSimulator 等统一通过 module_name 获取插件实例
- 失败时给出一致的错误信息
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def require_module(plugin_registry: Any, module_name: str):
    """从插件注册中心按模块名获取插件实例；不存在则抛错。"""
    if plugin_registry is None:
        raise ValueError(f"插件注册中心为空，无法获取模块 '{module_name}'")

    plugin = plugin_registry.get_plugin(module_name)
    if plugin is None:
        raise ValueError(f"模块 '{module_name}' 未通过插件加载")

    return plugin


def build_simulator_state_from_registry(
    plugin_registry: Any,
    extra_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """根据 plugin_registry 中已绑定的模块自动构建 simulator_state。

    遍历 modules_config.yaml 的 selected_modules，将每个模块实例注入字典。
    不存在的模块会被静默跳过，避免因为配置与注册表不一致而崩溃。

    Args:
        plugin_registry: 插件注册表（PluginRegistry 实例）。
        extra_state: 需要额外补充到 simulator_state 的字段（如 residents、gdp 等）。

    Returns:
        构建好的 simulator_state 字典。
    """
    simulator_state: Dict[str, Any] = {}
    if plugin_registry is None:
        return simulator_state

    loaded_plugins: Dict[str, Any] = {}
    getter = getattr(plugin_registry, "get_all_loaded", None)
    if callable(getter):
        try:
            loaded_plugins = getter()
        except Exception:
            pass

    for name in loaded_plugins:
        try:
            plugin = require_module(plugin_registry, name)
            simulator_state[name] = plugin
        except Exception:
            pass

    if extra_state:
        simulator_state.update(extra_state)

    return simulator_state
