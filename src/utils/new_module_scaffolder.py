"""new_module_scaffolder
“从 modules_config.yaml 的 new_modules 生成新插件 + 自动接线”的重复工程逻辑。

约定：
- 插件目录：plugins/<plugin_name>/
- 插件元数据：plugins/<plugin_name>/plugin.yaml
- 全局启用开关：config/plugins.yaml（bootstrap 只读取 enabled/init_params）
- 运行时绑定：config/<sim>/modules_config.yaml 的 selected_modules
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


@dataclass(frozen=True)
class NewModuleSpec:
    name: str
    inherits_from: Optional[str]
    notes: str


def project_root_from(config_dir: str) -> str:
    # config_dir = <repo>/config/<sim_name>
    return os.path.dirname(os.path.dirname(os.path.abspath(config_dir)))


def plugins_root(project_root: str) -> str:
    return os.path.join(project_root, "plugins")


def plugin_dir(project_root: str, plugin_name: str) -> str:
    return os.path.join(plugins_root(project_root), plugin_name)


def plugin_manifest_path(project_root: str, plugin_name: str) -> str:
    return os.path.join(plugin_dir(project_root, plugin_name), "plugin.yaml")


def plugin_exists(project_root: str, plugin_name: str) -> bool:
    return os.path.exists(plugin_manifest_path(project_root, plugin_name))


def read_yaml_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_yaml_file(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml.dump(data, allow_unicode=True, sort_keys=False).strip() + "\n")


def _camel_case(name: str) -> str:
    parts = [p for p in re.split(r"[^a-zA-Z0-9]+", (name or "").strip()) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Plugin"


def parse_new_modules(modules_config_yaml_full: str) -> List[NewModuleSpec]:
    try:
        cfg = yaml.safe_load(modules_config_yaml_full) if modules_config_yaml_full else {}
    except Exception:
        cfg = {}

    if not isinstance(cfg, dict):
        return []

    raw = cfg.get("new_modules")
    if not isinstance(raw, list):
        return []

    specs: List[NewModuleSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        inherits_from = item.get("inherits_from")
        base = inherits_from.strip() if isinstance(inherits_from, str) and inherits_from.strip() else None
        notes = item.get("notes")
        if isinstance(notes, str):
            notes_str = notes
        elif notes is None:
            notes_str = ""
        else:
            try:
                notes_str = json.dumps(notes, ensure_ascii=False)
            except Exception:
                notes_str = str(notes)

        specs.append(NewModuleSpec(name=name.strip(), inherits_from=base, notes=notes_str))

    return specs


def copy_plugin_as_new(
    *,
    project_root: str,
    new_name: str,
    base_name: str,
    notes: str = "",
) -> Dict[str, Any]:
    """复制 inherits_from 插件目录，创建“继承插件”。

    最小策略：
    - copytree 整个插件目录
    - 只改新目录下 plugin.yaml 的 name/description/enabled
    - 不改 module/plugin_class、不改任何 .py 代码
    """

    base_dir = plugin_dir(project_root, base_name)
    new_dir = plugin_dir(project_root, new_name)

    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"base 插件目录不存在: {base_dir}")

    if os.path.exists(new_dir):
        return read_yaml_file(os.path.join(new_dir, "plugin.yaml"))

    def _ignore(_: str, names: List[str]) -> set[str]:
        ignored: set[str] = set()
        for n in names:
            if n == "__pycache__" or n.endswith(".pyc"):
                ignored.add(n)
        return ignored

    shutil.copytree(base_dir, new_dir, ignore=_ignore)

    base_manifest = read_yaml_file(os.path.join(base_dir, "plugin.yaml"))
    if not base_manifest:
        raise ValueError(f"读取 base 插件 manifest 失败: {base_name}")

    new_manifest = dict(base_manifest)
    new_manifest["name"] = new_name
    new_manifest["enabled"] = True

    base_desc = str(base_manifest.get("description") or "").strip()
    new_desc = base_desc
    if notes and notes.strip():
        new_desc = (new_desc + f" | notes: {notes.strip()}").strip() if new_desc else f"notes: {notes.strip()}"
    new_manifest["description"] = new_desc

    write_yaml_file(os.path.join(new_dir, "plugin.yaml"), new_manifest)
    return new_manifest


def create_minimal_plugin_from_template(
    *,
    project_root: str,
    new_name: str,
    notes: str = "",
    version: str = "0.1.0",
    author: str = "AgentWorld",
) -> Dict[str, Any]:
    """用 tools/templates/plugin_basic 生成最小插件骨架。"""

    new_dir = plugin_dir(project_root, new_name)
    os.makedirs(new_dir, exist_ok=True)

    module_stem = f"{new_name}_plugin"
    plugin_class = f"Generated{_camel_case(new_name)}Plugin"

    description = f"(auto) generated plugin {new_name}"
    if notes and notes.strip():
        description = f"{description} | notes: {notes.strip()}"

    tpl_root = os.path.join(project_root, "tools", "templates", "plugin_basic")
    yaml_tpl = os.path.join(tpl_root, "plugin.yaml.tpl")
    init_tpl = os.path.join(tpl_root, "__init__.py.tpl")
    py_tpl = os.path.join(tpl_root, "plugin.py.tpl")

    for p in (yaml_tpl, init_tpl, py_tpl):
        if not os.path.exists(p):
            raise FileNotFoundError(f"模板文件不存在: {p}")

    ctx = {
        "name": new_name,
        "version": version,
        "description": description.replace("\n", " ").strip(),
        "author": author,
        "module": module_stem,
        "plugin_class": plugin_class,
    }

    with open(yaml_tpl, "r", encoding="utf-8") as f:
        manifest_text = f.read().format(**ctx)
    with open(os.path.join(new_dir, "plugin.yaml"), "w", encoding="utf-8") as f:
        f.write(manifest_text)

    with open(init_tpl, "r", encoding="utf-8") as f:
        init_text = f.read().format(**ctx)
    with open(os.path.join(new_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(init_text)

    with open(py_tpl, "r", encoding="utf-8") as f:
        py_text = f.read().format(**ctx)
    with open(os.path.join(new_dir, f"{module_stem}.py"), "w", encoding="utf-8") as f:
        f.write(py_text + "\n")

    return read_yaml_file(os.path.join(new_dir, "plugin.yaml"))


def enable_plugin_in_global_plugins_yaml(*, project_root: str, plugin_name: str, manifest: Dict[str, Any]) -> None:
    """把插件加入 config/plugins.yaml 并启用。

    bootstrap 实际只读取 plugins[].name/enabled/init_params。
    """

    cfg_path = os.path.join(project_root, "config", "plugins.yaml")
    cfg = read_yaml_file(cfg_path)

    plugins = cfg.get("plugins")
    if not isinstance(plugins, list):
        plugins = []
        cfg["plugins"] = plugins

    for item in plugins:
        if isinstance(item, dict) and item.get("name") == plugin_name:
            item["enabled"] = True
            init_params = manifest.get("init_params")
            if isinstance(init_params, dict) and init_params:
                item.setdefault("init_params", {})
                if isinstance(item["init_params"], dict):
                    for k, v in init_params.items():
                        item["init_params"].setdefault(k, v)
            write_yaml_file(cfg_path, cfg)
            return

    entry: Dict[str, Any] = {"name": plugin_name, "enabled": True}
    init_params = manifest.get("init_params")
    if isinstance(init_params, dict) and init_params:
        entry["init_params"] = dict(init_params)
    plugins.append(entry)
    write_yaml_file(cfg_path, cfg)


def patch_modules_config_binding(
    *,
    modules_config_path: str,
    new_plugin_name: str,
    inherits_from: Optional[str],
) -> None:
    cfg = read_yaml_file(modules_config_path)
    selected = cfg.get("selected_modules")
    if not isinstance(selected, dict):
        selected = {}
        cfg["selected_modules"] = selected

    base = (inherits_from or "").strip() if inherits_from else ""
    if base:
        selected[base] = new_plugin_name
    else:
        selected.setdefault(new_plugin_name, new_plugin_name)

    write_yaml_file(modules_config_path, cfg)


def plugin_module_py_path(project_root: str, plugin_name: str, manifest: Dict[str, Any]) -> str:
    module_stem = str(manifest.get("module") or f"{plugin_name}_plugin").strip()
    return os.path.join(plugin_dir(project_root, plugin_name), f"{module_stem}.py")
