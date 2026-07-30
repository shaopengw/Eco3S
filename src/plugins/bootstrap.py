"""
放置“固定运行”的插件系统启动逻辑。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
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
    - modules_config.yaml 仅支持 selected_modules: [plugin_name, ...]
    - 插件实例创建优先使用 DIContainer.create（支持构造期注入）
    - 插件加载后会把“实现了标准接口”的插件实例注册回 DIContainer，
      以便后续插件可通过类型注入拿到依赖（IMap/ITowns/...）
    """

    if logger is None:
        logger = LogManager.get_logger("plugin_system", console_output=True)

    registry = PluginRegistry(logger=logger)

    # 先读取 modules_config，若存在 selected_modules 则定向发现（含依赖递归），避免扫描无关插件
    modules_config: Dict[str, Any] = {}
    if modules_config_path and os.path.exists(modules_config_path):
        try:
            with open(modules_config_path, "r", encoding="utf-8") as f:
                modules_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"读取 modules_config.yaml 失败，将回退到全量扫描: {e}")

    selected_modules = (modules_config or {}).get("selected_modules")
    if isinstance(selected_modules, list) and selected_modules:
        # 轻量扫描：收集 name -> directory 映射（只读 YAML，不注册）
        name_to_dir: Dict[str, Path] = {}
        plugin_roots = [Path("plugins"), Path("plugins/generated")]
        for plugins_path in plugin_roots:
            if not plugins_path.exists():
                continue
            for subdir in plugins_path.iterdir():
                if not subdir.is_dir() or subdir.name.startswith("_"):
                    continue
                yaml_file = subdir / "plugin.yaml"
                if yaml_file.exists():
                    try:
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            cfg = yaml.safe_load(f)
                        pname = cfg.get("name") if isinstance(cfg, dict) else None
                        if pname:
                            name_to_dir[pname] = subdir
                    except Exception:
                        pass

        # 定向发现 selected_modules + 递归依赖
        discovered: Set[str] = set()

        def _discover_with_deps(name: str) -> None:
            if name in discovered:
                return
            discovered.add(name)
            plugin_dir = name_to_dir.get(name)
            if plugin_dir and not registry.has_plugin(name):
                yaml_file = plugin_dir / "plugin.yaml"
                registry._discover_from_plugin_yaml(yaml_file, plugin_dir)
            md = registry.get_plugin_metadata(name)
            if md and md.metadata:
                for dep in md.metadata.get("dependencies", []) or []:
                    _discover_with_deps(dep)

        for name in selected_modules:
            if isinstance(name, str) and name.strip():
                _discover_with_deps(name.strip())

        logger.info(f"定向发现 {len(registry.get_all())} 个插件（含依赖）")
    else:
        # 约定：插件存在于 plugins/ 与 plugins/generated/ 目录。
        count = registry.discover(["plugins/", "plugins/generated/"])
        logger.info(f"发现了 {count} 个插件")

    loaded_plugins: Dict[str, BasePlugin] = {}
    event_bus = EventBus(logger=logger)

    if container is not None:
        try:
            container.register_instance(EventBus, event_bus)
        except Exception:
            pass

    def _load_one(plugin_name: str) -> None:
        if not plugin_name:
            return
        if plugin_name in loaded_plugins:
            return

        context = PluginContext(config=config, logger=logger, event_bus=event_bus, registry=registry)
        plugin_instance = registry.load_plugin(
            plugin_name,
            context,
            container=container,
        )
        loaded_plugins[plugin_name] = plugin_instance

        if container is not None:
            try:
                register_loaded_plugins(container, {plugin_name: plugin_instance})
            except Exception:
                pass

    dep_graph = registry.get_dependency_graph()

    def _load_with_dependencies(plugin_name: str, seen: Set[str]) -> None:
        if plugin_name in seen:
            return
        seen.add(plugin_name)
        for dep in dep_graph.get(plugin_name, []):
            _load_with_dependencies(dep, seen)
        _load_one(plugin_name)

    def _extract_selected_plugins(modules_config: Dict[str, Any]) -> List[str]:
        selected = (modules_config or {}).get("selected_modules")
        if not isinstance(selected, list):
            return []

        plugins: List[str] = []
        seen: Set[str] = set()

        for plugin_name in selected:
            if not isinstance(plugin_name, str) or not plugin_name.strip():
                continue
            plugin_name = plugin_name.strip()
            if plugin_name in seen:
                continue
            # selected_modules 是硬契约。即使发现/导入失败也保留名称，
            # 让加载阶段显式报错，而不是静默把模块从运行集合中删除。
            plugins.append(plugin_name)
            seen.add(plugin_name)
        return plugins

    selected_plugins = _extract_selected_plugins(modules_config)
    if selected_plugins:
        logger.info(f"开始加载 {len(selected_plugins)} 个选择的插件（来自 selected_modules）...")
        seen: Set[str] = set()
        load_errors: List[str] = []
        for name in selected_plugins:
            try:
                _load_with_dependencies(name, seen)
                logger.info(f"✓ 已加载插件: {name}")
            except Exception as e:
                logger.error(f"✗ 加载插件 {name} 失败: {e}")
                load_errors.append(f"{name}: {e}")
                import traceback

                traceback.print_exc()
        logger.info(f"插件加载完成: {len(loaded_plugins)}/{len(selected_plugins)} 成功")
        if load_errors:
            raise RuntimeError("selected plugins failed to load: " + "; ".join(load_errors))
        return registry

    # 未提供 modules_config.yaml 时：回退加载所有已发现的插件。
    plugin_names = sorted(registry.get_all().keys())
    logger.info(f"未指定 selected_modules，回退加载全部 {len(plugin_names)} 个已发现插件...")

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
