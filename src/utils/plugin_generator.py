"""plugin_generator

新插件生成流程。约定：
- 模板插件：plugins/plugin_template/（真实格式，可复制修改）
- 插件元数据：plugins/<name>/plugin.yaml（单源真理）
- 模块配置：config/<sim>/modules_config.yaml
"""

from __future__ import annotations

import ast
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class NewModuleSpec:
    name: str
    inherits_from: Optional[str]
    notes: str


def project_root_from(config_dir: str) -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(config_dir)))


def plugin_dir(project_root: str, name: str) -> str:
    return os.path.join(project_root, "plugins", name)


def plugin_manifest_path(project_root: str, name: str) -> str:
    return os.path.join(plugin_dir(project_root, name), "plugin.yaml")


def plugin_exists(project_root: str, name: str) -> bool:
    return os.path.exists(plugin_manifest_path(project_root, name))


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
    parts = [p for p in re.split(r"[^a-zA-Z0-9]+", name.strip()) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Plugin"


# =============================================================================
# 解析 new_modules
# =============================================================================

def parse_new_modules(modules_config_yaml_full: str) -> List[NewModuleSpec]:
    try:
        cfg = yaml.safe_load(modules_config_yaml_full) or {}
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
        base = item.get("inherits_from")
        base = base.strip() if isinstance(base, str) and base.strip() else None
        notes = str(item.get("notes") or "").strip()
        specs.append(NewModuleSpec(name=name.strip(), inherits_from=base, notes=notes))
    return specs


# =============================================================================
# 骨架生成
# =============================================================================

def _prepare_copied_plugin(
    *, new_dir: str, new_name: str, old_module: str, old_class: str, old_name: str, description: str = ""
) -> Dict[str, Any]:
    """复制目录后，统一替换类名/模块名/插件名，写入 manifest。"""
    manifest = read_yaml_file(os.path.join(new_dir, "plugin.yaml"))
    manifest["name"] = new_name
    manifest["enabled"] = True
    if description:
        manifest["description"] = description

    new_module = f"{new_name}_plugin"
    new_class = f"Generated{_camel_case(new_name)}Plugin"
    manifest["module"] = new_module
    manifest["plugin_class"] = new_class

    old_py = os.path.join(new_dir, f"{old_module}.py")
    if not os.path.exists(old_py):
        # 兼容模板插件：模板主文件可能命名为 {old_name}.py 而非 {old_module}_plugin.py
        fallback_py = os.path.join(new_dir, f"{old_name}.py")
        if os.path.exists(fallback_py):
            old_py = fallback_py

    new_py = os.path.join(new_dir, f"{new_module}.py")
    if os.path.exists(old_py) and old_py != new_py:
        os.rename(old_py, new_py)

    for fname in (new_py, os.path.join(new_dir, "__init__.py")):
        if not os.path.exists(fname):
            continue
        with open(fname, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace(old_class, new_class)
        content = content.replace(old_module, new_module)
        content = content.replace(old_name, new_name)
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)

    write_yaml_file(os.path.join(new_dir, "plugin.yaml"), manifest)
    return manifest


def create_minimal_plugin_from_template(
    *, project_root: str, new_name: str, description: str = ""
) -> Dict[str, Any]:
    """复制 plugin_template 创建新插件骨架。"""
    template_dir = os.path.join(project_root, "plugins", "plugin_template")
    new_dir = plugin_dir(project_root, new_name)
    if not os.path.isdir(template_dir):
        raise FileNotFoundError(f"模板插件不存在: {template_dir}")
    if os.path.exists(new_dir):
        return read_yaml_file(plugin_manifest_path(project_root, new_name))

    shutil.copytree(
        template_dir, new_dir,
        ignore=lambda _, names: {n for n in names if n == "__pycache__" or n.endswith(".pyc")}
    )
    return _prepare_copied_plugin(
        new_dir=new_dir, new_name=new_name,
        old_module="plugin_template", old_class="PluginTemplate", old_name="plugin_template",
        description=description,
    )


def copy_plugin_as_new(
    *, project_root: str, new_name: str, base_name: str, description: str = ""
) -> Dict[str, Any]:
    """复制已有插件创建新插件。"""
    base_dir = plugin_dir(project_root, base_name)
    new_dir = plugin_dir(project_root, new_name)
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"base 插件目录不存在: {base_dir}")
    if os.path.exists(new_dir):
        manifest = read_yaml_file(plugin_manifest_path(project_root, new_name))
        if description:
            manifest["description"] = description
            write_yaml_file(os.path.join(new_dir, "plugin.yaml"), manifest)
        return manifest

    shutil.copytree(
        base_dir, new_dir,
        ignore=lambda _, names: {n for n in names if n == "__pycache__" or n.endswith(".pyc")}
    )
    return _prepare_copied_plugin(
        new_dir=new_dir, new_name=new_name,
        old_module=f"{base_name}_plugin", old_class=f"{_camel_case(base_name)}Plugin", old_name=base_name,
        description=description,
    )


def plugin_module_py_path(project_root: str, plugin_name: str, manifest: Dict[str, Any]) -> str:
    module = str(manifest.get("module") or f"{plugin_name}_plugin").strip()
    return os.path.join(plugin_dir(project_root, plugin_name), f"{module}.py")


# =============================================================================
# 验证
# =============================================================================

def validate_manifest(manifest: Dict[str, Any], plugin_name: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(manifest, dict):
        errors.append("manifest 不是字典")
        return errors
    for key in ("name", "version", "description", "author", "plugin_class", "module"):
        if not str(manifest.get(key) or "").strip():
            errors.append(f"必填字段缺失: {key}")
    if str(manifest.get("name") or "").strip() != plugin_name:
        errors.append(f"manifest name 不一致")
    desc = str(manifest.get("description") or "").strip()
    if len(desc) < 10:
        errors.append("description 过短，必须准确详细")
    if desc.startswith("(auto) generated plugin"):
        errors.append("description 为占位文本，需替换为业务描述")
    deps = manifest.get("dependencies")
    if deps is not None and not isinstance(deps, list):
        errors.append("dependencies 必须是列表")
    return errors


def _extract_abstract_method_names(interface_path: str) -> List[str]:
    """从接口文件 AST 中提取被 @abstractmethod 标记的方法名。"""
    if not os.path.exists(interface_path):
        return []
    try:
        with open(interface_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return []

    methods: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            name = ""
            if isinstance(decorator, ast.Name):
                name = decorator.id
            elif isinstance(decorator, ast.Attribute):
                name = decorator.attr
            if name == "abstractmethod":
                methods.append(node.name)
                break
    return methods


def _extract_class_method_names(tree: ast.AST, class_name: str) -> List[str]:
    """从插件代码 AST 中提取指定类中定义的方法名（不含继承）。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
    return []


def validate_plugin_code(project_root: str, plugin_name: str, manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    module = str(manifest.get("module") or f"{plugin_name}_plugin").strip()
    py_path = os.path.join(plugin_dir(project_root, plugin_name), f"{module}.py")
    if not os.path.exists(py_path):
        errors.append(f"插件代码文件不存在: {py_path}")
        return errors
    try:
        with open(py_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except SyntaxError as e:
        errors.append(f"语法错误 ({module}.py:{e.lineno}): {e.msg}")
        return errors
    expected = str(manifest.get("plugin_class") or "").strip()
    if expected:
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if expected not in classes:
            errors.append(f"未找到声明的类 {expected}")
            return errors

        # ------------------------------------------------------------------
        # 接口完整性校验：若存在 i<plugin_name>.py，则要求实现其所有抽象方法
        # ------------------------------------------------------------------
        interface_path = os.path.join(project_root, "src", "interfaces", f"i{plugin_name}.py")
        interface_methods = _extract_abstract_method_names(interface_path)
        if interface_methods:
            plugin_methods = _extract_class_method_names(tree, expected)
            plugin_method_set = set(plugin_methods)
            missing = [m for m in interface_methods if m not in plugin_method_set]
            if missing:
                errors.append(
                    f"接口契约校验失败: 插件类 {expected} 未实现 "
                    f"{os.path.basename(interface_path)} 要求的抽象方法: {missing}"
                )
    return errors


def validate_dependencies(project_root: str, manifest: Dict[str, Any], pending: set[str]) -> List[str]:
    errors: List[str] = []
    deps = manifest.get("dependencies")
    if not isinstance(deps, list):
        return errors
    for dep in deps:
        if not isinstance(dep, str) or not dep.strip():
            continue
        dep = dep.strip()
        if dep in pending:
            continue
        if not plugin_exists(project_root, dep):
            errors.append(f"依赖插件不存在: '{dep}'")
    return errors


# =============================================================================
# 注册
# =============================================================================

def enable_plugin_in_global_plugins_yaml(
    *, project_root: str, plugin_name: str, manifest: Dict[str, Any]
) -> None:
    """已废弃：插件元数据单源化后，新插件只需写入 plugins/<name>/plugin.yaml 即可被系统发现。
    保留空函数以兼容旧调用方。"""
    pass


def patch_modules_config_binding(
    *, modules_config_path: str, new_plugin_name: str, inherits_from: Optional[str]
) -> None:
    cfg = read_yaml_file(modules_config_path)
    selected = cfg.get("selected_modules")
    if not isinstance(selected, list):
        selected = []
    names = [n.strip() for n in selected if isinstance(n, str) and n.strip()]
    base = (inherits_from or "").strip()
    if base and base in names:
        names = [new_plugin_name if n == base else n for n in names]
    elif new_plugin_name not in names:
        names.append(new_plugin_name)
    cfg["selected_modules"] = names
    write_yaml_file(modules_config_path, cfg)


