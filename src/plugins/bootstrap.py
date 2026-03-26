"""
放置“固定运行”的插件系统启动逻辑。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

import yaml

from src.plugins import BasePlugin, PluginContext, PluginRegistry
from src.plugins.plugin_context import EventBus
from src.utils.di_container import DIContainer
from src.utils.di_helpers import register_loaded_plugins
from src.utils.logger import LogManager


def initialize_plugin_system(
    config: dict,
    modules_config_path: str | None = None,
    container: Optional[DIContainer] = None,
    logger: Optional[logging.Logger] = None,
) -> PluginRegistry:
    """初始化插件系统并加载配置的插件。

    约定：
    - modules_config.yaml 仅支持 selected_modules: {module_name: plugin_name}
    - 插件实例创建优先使用 DIContainer.create（支持构造期注入）
    - 插件加载后会把“实现了标准接口”的插件实例注册回 DIContainer，
      以便后续插件可通过类型注入拿到依赖（IMap/ITowns/...）
    """

    if logger is None:
        logger = LogManager.get_logger("plugin_system", console_output=True)

    registry = PluginRegistry(logger=logger)

    # 约定：插件只存在于仓库根目录下的 plugins/ 目录。
    count = registry.discover(["plugins/"])
    logger.info(f"发现了 {count} 个插件")

    loaded_plugins: Dict[str, BasePlugin] = {}
    event_bus = EventBus()

    if container is not None:
        try:
            container.register_instance(EventBus, event_bus)
        except Exception:
            pass

    def _load_enabled_plugins_from_config() -> tuple[Set[str], Dict[str, Dict[str, Any]]]:
        """从 config/plugins.yaml 读取启用插件列表。

        约定：这里只读取 plugins[].name / enabled / init_params，
        插件类/元数据以 plugins/*/plugin.yaml 为准。
        """

        enabled: Set[str] = set()
        init_overrides: Dict[str, Dict[str, Any]] = {}

        cfg_path = os.path.join("config", "plugins.yaml")
        if not os.path.exists(cfg_path):
            return enabled, init_overrides

        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                plugin_system_config = yaml.safe_load(f) or {}
        except Exception:
            return enabled, init_overrides

        plugins_cfg = plugin_system_config.get("plugins")
        if not isinstance(plugins_cfg, list):
            return enabled, init_overrides

        for item in plugins_cfg:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            if item.get("enabled", True) is False:
                continue

            enabled.add(name)
            init_params = item.get("init_params")
            if isinstance(init_params, dict) and init_params:
                init_overrides[name] = dict(init_params)

        return enabled, init_overrides

    enabled_names, init_overrides = _load_enabled_plugins_from_config()

    def _load_one(plugin_name: str) -> None:
        if not plugin_name:
            return
        if plugin_name in loaded_plugins:
            return

        # 若配置提供 enabled 列表，则只加载启用的插件。
        if enabled_names and plugin_name not in enabled_names:
            return

        context = PluginContext(config=config, logger=logger, event_bus=event_bus, registry=registry)
        plugin_instance = registry.load_plugin(
            plugin_name,
            context,
            container=container,
            **(init_overrides.get(plugin_name, {}) or {}),
        )
        loaded_plugins[plugin_name] = plugin_instance

        if container is not None:
            try:
                register_loaded_plugins(container, {plugin_name: plugin_instance})
            except Exception:
                pass

    def _load_with_dependencies(plugin_name: str, seen: Set[str]) -> None:
        if plugin_name in seen:
            return
        seen.add(plugin_name)
        md = registry.get_plugin_metadata(plugin_name)
        deps: List[str] = []
        if md and md.metadata:
            deps = md.metadata.get("dependencies", []) or []
        for dep in deps:
            if enabled_names and dep not in enabled_names:
                raise RuntimeError(f"插件 {plugin_name} 依赖 {dep}，但该依赖在 config/plugins.yaml 中未启用")
            _load_with_dependencies(dep, seen)
        _load_one(plugin_name)

    def _extract_selected_plugins(modules_config: Dict[str, Any]) -> List[str]:
        selected = (modules_config or {}).get("selected_modules")
        if not isinstance(selected, dict):
            return []

        plugins: List[str] = []
        seen: Set[str] = set()
        for _, plugin_name in selected.items():
            if not isinstance(plugin_name, str) or not plugin_name.strip():
                continue
            plugin_name = plugin_name.strip()
            if plugin_name in seen:
                continue
            if registry.has_plugin(plugin_name):
                if enabled_names and plugin_name not in enabled_names:
                    continue
                plugins.append(plugin_name)
                seen.add(plugin_name)
        return plugins

    modules_config: Dict[str, Any] = {}
    if modules_config_path and os.path.exists(modules_config_path):
        try:
            with open(modules_config_path, "r", encoding="utf-8") as f:
                modules_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"读取 modules_config.yaml 失败，将回退到 config/plugins.yaml: {e}")

    selected_modules = (modules_config or {}).get("selected_modules")
    if isinstance(selected_modules, dict):
        registry.bind_modules(selected_modules)

    selected_plugins = _extract_selected_plugins(modules_config)
    if selected_plugins:
        logger.info(f"开始加载 {len(selected_plugins)} 个选择的插件（来自 selected_modules）...")
        seen: Set[str] = set()
        for name in selected_plugins:
            try:
                _load_with_dependencies(name, seen)
                logger.info(f"✓ 已加载插件: {name}")
            except Exception as e:
                logger.error(f"✗ 加载插件 {name} 失败: {e}")
                import traceback

                traceback.print_exc()
        logger.info(f"插件加载完成: {len(loaded_plugins)}/{len(selected_plugins)} 成功")
        return registry

    # 未选择模块时：加载 config/plugins.yaml 里启用的插件（按 name）。
    plugin_names = sorted(enabled_names)
    logger.info(f"开始加载 {len(plugin_names)} 个启用插件（来自 config/plugins.yaml）...")

    seen: Set[str] = set()
    for name in plugin_names:
        try:
            _load_with_dependencies(name, seen)
        except Exception as e:
            logger.error(f"✗ 加载插件 {name} 失败: {e}")
            import traceback

            traceback.print_exc()

    logger.info(f"插件加载完成: {len(loaded_plugins)}/{len(plugin_names)} 成功")
    return registry
