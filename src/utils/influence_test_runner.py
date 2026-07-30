"""src.utils.influence_test_runner

隔离测试项目 influences.yaml 的工具。
不启动完整模拟，不调用 LLM，只把影响函数跑一轮并输出每个指标的变化量，
用于快速定位哪条影响函数导致数值爆炸、指标恒定或被静默跳过。

两层能力：
1. ``InfluenceTestRunner`` —— 旧接口，给定 MockState 跑一轮，输出数值变化（保持向后兼容）。
2. ``InfluencePreflight`` —— 新增的“通用预检”：从项目 config 自动推导虚拟数据，
   做静态静默跳过检查 + 动态执行（异常 / 数值爆炸 / 全局恒定）检测，
   并能把诊断结果格式化成 CodeFixer 可消费的评估报告。
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# 让 src.* 可导入：本文件在 src/utils/，仓库根目录是上两级
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.influences import InfluenceManager, InfluenceRegistry


class MockState:
    """支持嵌套字典转顶层属性的模拟器替身。

    用法：
        state = MockState(
            state={
                "mortgage_market": {"gse_purchase_share": 0.1, ...},
                "macro_state": {"house_price_index": 100.0, ...},
                "homeownership_rate": 64.0,
            },
            attr_map={
                "gse_purchase_share": ("mortgage_market", "gse_purchase_share"),
                "house_price_index": ("macro_state", "house_price_index"),
                # ...
            }
        )
    """

    def __init__(
        self,
        state: Dict[str, Any],
        attr_map: Optional[Dict[str, Tuple[str, ...]]] = None,
    ):
        object.__setattr__(self, "_state", dict(state))
        object.__setattr__(self, "_attr_map", dict(attr_map or {}))

    def __getattr__(self, name: str) -> Any:
        if name in self._attr_map:
            path = self._attr_map[name]
            cur = self._state
            for key in path:
                if isinstance(cur, dict):
                    cur = cur[key]
                else:
                    cur = getattr(cur, key)
            return cur
        if name in self._state:
            return self._state[name]
        raise AttributeError(f"MockState 没有属性: {name}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        if name in self._attr_map:
            path = self._attr_map[name]
            cur = self._state
            for key in path[:-1]:
                cur = cur[key]
            cur[path[-1]] = value
            return
        self._state[name] = value

    def to_dict(self) -> Dict[str, Any]:
        return self._state


class _TimeStub:
    """influences 常读取 time.current_time / time.start_time，给个最小桩。"""

    def __init__(self, current_time: float = 1, start_time: float = 1):
        self.current_time = current_time
        self.start_time = start_time


class InfluenceTestRunner:
    """加载项目 influences.yaml，在 mock 对象上执行一轮影响函数并输出变化。"""

    DEFAULT_ANOMALY_RATIO = 2.0
    DEFAULT_ANOMALY_ABS = 1_000_000.0

    def __init__(self, influences_config: Dict[str, Any]):
        self.registry = InfluenceRegistry()
        self.registry.load_from_config(influences_config)
        self.manager = InfluenceManager(influence_registry=self.registry)
        self.manager.set_execution_order(self.registry.execution_order)

    @classmethod
    def from_project(cls, project_name: str, projects_root: str = "projects") -> "InfluenceTestRunner":
        config_path = os.path.join(projects_root, project_name, "config", "influences.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return cls(config)

    def run(
        self,
        mock: MockState,
        extra_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行一轮影响函数，返回每个被修改属性的前后值、变化量和变化率。"""
        simulator_state = dict(mock.to_dict())
        if extra_state:
            simulator_state.update(extra_state)

        # 记录所有可能被修改的顶层属性的初始值
        tracked_attrs = set(self.registry.list_targets())
        before: Dict[str, Any] = {}
        for attr in tracked_attrs:
            if hasattr(mock, attr):
                before[attr] = getattr(mock, attr)

        self.manager.apply_all_influences(simulator_state, target_root=mock)

        after: Dict[str, Any] = {}
        changes: List[Dict[str, Any]] = []
        for attr in sorted(tracked_attrs):
            if not hasattr(mock, attr):
                continue
            old = before.get(attr)
            new = getattr(mock, attr)
            after[attr] = new
            delta, ratio = self._compute_delta(old, new)
            changes.append({
                "attr": attr,
                "before": old,
                "after": new,
                "delta": delta,
                "delta_ratio": ratio,
                "anomaly": self._is_anomaly(delta, ratio),
            })

        return {
            "execution_order": self.registry.execution_order,
            "changes": changes,
            "anomalies": [c for c in changes if c["anomaly"]],
        }

    @staticmethod
    def _compute_delta(old: Any, new: Any) -> Tuple[Optional[float], Optional[float]]:
        if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
            return None, None
        delta = new - old
        if old == 0:
            if new == 0:
                return 0.0, 0.0
            ratio = math.inf if new > 0 else -math.inf
        else:
            ratio = delta / old
        return delta, ratio

    def _is_anomaly(self, delta: Optional[float], ratio: Optional[float]) -> bool:
        if delta is None or ratio is None:
            return False
        if abs(delta) > self.DEFAULT_ANOMALY_ABS:
            return True
        if abs(ratio) > self.DEFAULT_ANOMALY_RATIO:
            return True
        return False


# ======================================================================
# 通用预检：从项目配置自动推导虚拟数据，做静态 + 动态健康检查
# ======================================================================

# 解析 inputs.path / fallback_paths 时，剥离这些已知前缀，取最后一段作为属性名
_PATH_PREFIXES = ("context.", "target.", "module.", "source.", "result.")

# 数值爆炸阈值
_ANOMALY_RATIO = 2.0
_ANOMALY_ABS = 1_000_000.0

# 自动播种时，读不到 config 初值就回退该默认值
_FALLBACK_VALUE = 1.0


def normalize_influence_contracts(config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Normalize deterministic target ownership contracts in an influence config.

    Non-placeholder influences write to ``params.target_attr``.  Keep both the
    influence's ``target`` and its precise ``execution_order`` entry aligned
    with that owner.  Ambiguous legacy schedule entries are intentionally left
    untouched for the preflight/CodeFixer path.
    """
    changes: List[Dict[str, str]] = []
    target_by_name: Dict[str, str] = {}

    for influence in config.get("influences", []) or []:
        if not isinstance(influence, dict):
            continue
        params = influence.get("params") or {}
        if not isinstance(params, dict) or params.get("placeholder") is True:
            continue
        name = str(influence.get("name") or "").strip()
        target_attr = params.get("target_attr")
        if not name or not isinstance(target_attr, str) or not target_attr.strip():
            continue
        normalized_target = target_attr.strip()
        target_by_name[name] = normalized_target
        old_target = str(influence.get("target") or "")
        if old_target != normalized_target:
            influence["target"] = normalized_target
            changes.append({
                "location": f"influences[{name}].target",
                "old": old_target,
                "new": normalized_target,
            })

    for index, step in enumerate(config.get("execution_order", []) or []):
        if not isinstance(step, dict):
            continue
        name = str(step.get("influence") or step.get("name") or "").strip()
        normalized_target = target_by_name.get(name)
        if not normalized_target:
            continue
        old_target = str(step.get("target") or "")
        if old_target != normalized_target:
            step["target"] = normalized_target
            changes.append({
                "location": f"execution_order[{index}].target",
                "old": old_target,
                "new": normalized_target,
            })
    return changes


def normalize_influence_contract_file(path: str) -> List[Dict[str, str]]:
    """Atomically normalize deterministic contracts in ``influences.yaml``."""
    with open(path, "r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    if not isinstance(config, dict):
        return []
    changes = normalize_influence_contracts(config)
    if not changes:
        return []

    backup_path = path + ".preflight.backup"
    if not os.path.exists(backup_path):
        shutil.copy2(path, backup_path)
    target_dir = os.path.dirname(os.path.abspath(path))
    fd, temp_path = tempfile.mkstemp(prefix=".influences-", suffix=".yaml", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            yaml.safe_dump(config, stream, allow_unicode=True, sort_keys=False)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return changes


class InfluencePreflight:
    """通用 influence 预检器。

    给定项目的 ``config/influences.yaml`` / ``config/modules_config.yaml`` / ``simulator.py``，
    自动构造虚拟初始状态，跑一轮影响函数，输出结构化诊断：
      - silent_skip：execution_order / source 引用的模块既不是 __simulator__，
        也不是已加载插件模块，且在 simulator.py 里找不到 —— 必然被静默跳过。
      - apply_error：影响函数 apply() 抛异常（输入路径写错、target_attr 拼错等）。
      - anomalies：数值爆炸（变化率/绝对值超阈值）。
      - global_constant：跑完一轮后没有任何指标发生变化 —— 整体空操作。

    ``placeholder: true`` 的影响函数按约定只是占位，预检直接跳过、不计入问题。
    """

    def __init__(
        self,
        influences_config: Dict[str, Any],
        modules_config: Optional[Dict[str, Any]] = None,
        simulator_source: str = "",
        config_initial_values: Optional[Dict[str, Any]] = None,
    ):
        self.influences_config = influences_config or {}
        self.modules_config = modules_config or {}
        self.simulator_source = simulator_source or ""
        self.config_initial_values = config_initial_values or {}

        self.registry = InfluenceRegistry()
        self.registry.load_from_config(self.influences_config)
        self.manager = InfluenceManager(influence_registry=self.registry)
        self.manager.set_execution_order(self.registry.execution_order)
        self.manager.enable_trace(True)

        self.simulator_declared_attrs = self._extract_simulator_attrs(self.simulator_source)
        self.simulator_numeric_defaults = self._extract_simulator_numeric_defaults(self.simulator_source)

    # ---------- 构造 ----------
    @classmethod
    def from_project_dir(cls, config_dir: str, simulator_path: str) -> "InfluencePreflight":
        """从项目目录加载所有需要的文件。

        Args:
            config_dir: projects/<name>/config 目录
            simulator_path: projects/<name>/simulator.py 路径
        """
        influences_config = cls._load_yaml(os.path.join(config_dir, "influences.yaml")) or {}
        modules_config = cls._load_yaml(os.path.join(config_dir, "modules_config.yaml")) or {}

        simulator_source = ""
        if simulator_path and os.path.exists(simulator_path):
            with open(simulator_path, "r", encoding="utf-8") as f:
                simulator_source = f.read()

        # 从常见配置文件里收集“名字 -> 数值初值”，供虚拟数据优先采用真实初值
        initial_values: Dict[str, Any] = {}
        for fname in (
            "simulation_config.yaml",
            "modules_config.yaml",
            "jobs_config.yaml",
            "agent_profile.yaml",
        ):
            data = cls._load_yaml(os.path.join(config_dir, fname))
            cls._collect_numeric_leaves(data, initial_values)
        towns = cls._load_json(os.path.join(config_dir, "towns_data.json"))
        cls._collect_numeric_leaves(towns, initial_values)

        return cls(
            influences_config=influences_config,
            modules_config=modules_config,
            simulator_source=simulator_source,
            config_initial_values=initial_values,
        )

    @staticmethod
    def _load_yaml(path: str) -> Optional[Any]:
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    @staticmethod
    def _load_json(path: str) -> Optional[Any]:
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def _collect_numeric_leaves(data: Any, out: Dict[str, Any]) -> None:
        """递归收集 dict 中所有 数值叶子的 key -> value（首个出现优先）。"""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)) and k not in out:
                    out[str(k)] = v
                else:
                    InfluencePreflight._collect_numeric_leaves(v, out)
        elif isinstance(data, list):
            for item in data:
                InfluencePreflight._collect_numeric_leaves(item, out)

    # ---------- 引用解析 ----------
    @staticmethod
    def _leaf(path: str) -> Optional[str]:
        """从 'context.macro.house_price_index' 这种路径取最后一段属性名。"""
        if not isinstance(path, str) or not path:
            return None
        p = path
        for prefix in _PATH_PREFIXES:
            if p.startswith(prefix):
                p = p[len(prefix):]
                break
        # 取最后一段
        leaf = p.split(".")[-1].strip()
        return leaf or None

    def _collect_referenced_attrs(self) -> set:
        """收集 influences.yaml 中所有被读/写的属性名，用于播种虚拟数据。"""
        attrs: set = set()
        for inf in self.influences_config.get("influences", []) or []:
            if not isinstance(inf, dict):
                continue
            target = inf.get("target")
            if isinstance(target, str):
                attrs.add(target)
            params = inf.get("params") or {}
            for key in ("target_attr", "variable"):
                leaf = self._leaf(params.get(key)) if isinstance(params.get(key), str) else None
                if leaf:
                    attrs.add(leaf)
            # inputs 既可能在 params.inputs，也可能在 source.inputs
            for inputs in (params.get("inputs"), (inf.get("source") or {}).get("inputs") if isinstance(inf.get("source"), dict) else None):
                if not isinstance(inputs, dict):
                    continue
                for spec in inputs.values():
                    if isinstance(spec, str):
                        leaf = self._leaf(spec)
                        if leaf:
                            attrs.add(leaf)
                    elif isinstance(spec, dict):
                        for pth in [spec.get("path")] + list(spec.get("fallback_paths") or []):
                            leaf = self._leaf(pth) if isinstance(pth, str) else None
                            if leaf:
                                attrs.add(leaf)
        # execution_order 的 target 也算被写属性
        for step in (self.registry.execution_order or []):
            _module_name, target_name, _influence_name = self._execution_step_parts(step)
            if isinstance(target_name, str):
                attrs.add(target_name)
        return attrs

    def _referenced_modules(self) -> set:
        """收集 execution_order 与 source 中引用的模块名。"""
        modules: set = set()
        for step in (self.registry.execution_order or []):
            module_name, _target, _influence_name = self._execution_step_parts(step)
            if isinstance(module_name, str):
                modules.add(module_name)
        for inf in self.influences_config.get("influences", []) or []:
            if not isinstance(inf, dict):
                continue
            src = inf.get("source")
            if isinstance(src, str):
                modules.add(src)
            elif isinstance(src, dict) and isinstance(src.get("module"), str):
                modules.add(src["module"])
        return modules

    @staticmethod
    def _execution_step_parts(step: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if isinstance(step, (list, tuple)) and len(step) >= 2:
            name = step[2] if len(step) >= 3 else None
            return str(step[0]), str(step[1]), str(name) if name else None
        return None, None, None

    @staticmethod
    def _extract_simulator_attrs(source: str) -> set:
        if not source:
            return set()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return set()
        attrs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
                attrs.add(node.attr)
        return attrs

    @staticmethod
    def _extract_simulator_numeric_defaults(source: str) -> Dict[str, float]:
        if not source:
            return {}
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}
        values: Dict[str, float] = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value_node = node.value
            if not isinstance(value_node, ast.Constant) or isinstance(value_node.value, bool):
                continue
            if not isinstance(value_node.value, (int, float)):
                continue
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    values.setdefault(target.attr, float(value_node.value))
        return values

    def _semantic_contract_errors(self) -> List[Dict[str, Any]]:
        """检查不会抛异常、但必然造成错写/重复/死输出的 influence 契约错误。"""
        errors: List[Dict[str, Any]] = []
        configs = [x for x in self.influences_config.get("influences", []) or [] if isinstance(x, dict)]
        by_target: Dict[str, List[dict]] = {}
        by_name: Dict[str, List[dict]] = {}
        for inf in configs:
            params = inf.get("params") or {}
            if isinstance(params, dict) and params.get("placeholder") is True:
                continue
            target = str(inf.get("target") or "")
            name = str(inf.get("name") or "")
            by_target.setdefault(target, []).append(inf)
            by_name.setdefault(name, []).append(inf)

            target_attr = params.get("target_attr")
            if target_attr and str(target_attr) != target:
                errors.append({
                    "kind": "target_attr_mismatch",
                    "name": name,
                    "target": target,
                    "detail": f"target={target!r} 但 target_attr={target_attr!r}，写入与调度不是同一状态",
                })
            if target and target not in self.simulator_declared_attrs:
                errors.append({
                    "kind": "dead_output",
                    "name": name,
                    "target": target,
                    "detail": f"simulator.py 未声明/读取 self.{target}，该输出缺少稳定状态所有者或消费者",
                })

            if self.simulator_numeric_defaults.get(target) == 0 and inf.get("type") == "expr":
                params = inf.get("params") or {}
                source = inf.get("source") or {}
                inputs = source.get("inputs", {}) if isinstance(source, dict) else {}
                target_vars = set()
                for var_name, spec in inputs.items() if isinstance(inputs, dict) else []:
                    spec_obj = {"path": spec} if isinstance(spec, str) else spec
                    if not isinstance(spec_obj, dict):
                        continue
                    paths = [spec_obj.get("path"), *(spec_obj.get("fallback_paths") or [])]
                    if any(path in (f"target.{target}", f"context.{target}") for path in paths):
                        target_vars.add(str(var_name))
                expr = params.get("expr")
                if target_vars and isinstance(expr, str) and self._expr_stays_zero(expr, target_vars):
                    errors.append({
                        "kind": "zero_absorbing_formula",
                        "name": name,
                        "target": target,
                        "detail": f"self.{target} 初值为0，公式在其他驱动非零时仍无法离开0",
                    })

        scheduled: Dict[str, int] = {}
        for step in self.registry.execution_order or []:
            module, target, name = self._execution_step_parts(step)
            if name:
                scheduled[name] = scheduled.get(name, 0) + 1
            elif target and len(by_target.get(target, [])) > 1:
                errors.append({
                    "kind": "ambiguous_legacy_schedule",
                    "target": target,
                    "detail": f"旧式 execution_order 未指定 influence，但 target={target!r} 有 {len(by_target[target])} 条影响，会重复执行",
                })
            if not name and module not in (None, "__simulator__") and target in self.simulator_declared_attrs:
                errors.append({
                    "kind": "source_target_conflation",
                    "target": target,
                    "module": module,
                    "detail": f"module={module!r} 会被当成执行对象，但 {target!r} 的状态所有者是 simulator",
                })

        for name, matching in by_name.items():
            if not name:
                continue
            count = scheduled.get(name, 0)
            if count == 0 and any(len(step) >= 3 for step in self.registry.execution_order or []):
                errors.append({
                    "kind": "unscheduled_influence",
                    "name": name,
                    "detail": "该 influence 未进入精确 execution_order",
                })
            elif count > 1:
                errors.append({
                    "kind": "duplicate_schedule",
                    "name": name,
                    "detail": f"该 influence 被调度 {count} 次",
                })
            if len(matching) > 1:
                errors.append({
                    "kind": "duplicate_name",
                    "name": name,
                    "detail": "influence name 必须全局唯一，才能精确调度",
                })
        return errors

    @staticmethod
    def _expr_stays_zero(expr: str, target_vars: set[str]) -> bool:
        """用保守探针判断目标当前值为0时，表达式是否仍被吸附在0。"""
        try:
            tree = ast.parse(expr, mode="eval")
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            safe_functions = {"max": max, "min": min, "abs": abs, "round": round}
            namespace = {
                name: (safe_functions[name] if name in safe_functions else (0.0 if name in target_vars else 1.0))
                for name in names
            }
            value = eval(compile(tree, "<zero-probe>", "eval"), {"__builtins__": {}}, namespace)
            return isinstance(value, (int, float)) and abs(float(value)) < 1e-12
        except Exception:
            return False

    def _allowed_modules(self) -> set:
        """simulator_state 中真实可能存在的模块键集合。

        = {__simulator__} ∪ modules_config 的 selected_modules/new_modules（插件名）
          ∪ simulator.py 源码里以独立单词出现的名字（覆盖 extra_state={...} 注入的键）。
        """
        allowed = {"__simulator__"}
        for key in ("selected_modules", "new_modules"):
            val = self.modules_config.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        allowed.add(item)
                    elif isinstance(item, dict) and isinstance(item.get("name"), str):
                        allowed.add(item["name"])
        return allowed

    def _module_in_simulator_source(self, module_name: str) -> bool:
        if not self.simulator_source or not module_name:
            return False
        return re.search(r"\b" + re.escape(module_name) + r"\b", self.simulator_source) is not None

    # ---------- 主流程 ----------
    def run(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": True,
            # --- 硬门信号（高置信，触发即判不通过）---
            "silent_skip": [],       # 模块名不在 simulator_state，整条影响函数被静默跳过
            "broken_influence": [],  # apply 抛 NameError 等“影响函数本身写坏了”的异常
            "non_finite": [],        # 跑一轮后出现 NaN / inf（真实数值崩溃）
            "load_error": None,      # influences.yaml 无法加载/整体异常
            "semantic_errors": [],   # 不抛异常但会错写、重复执行或产生死输出
            # --- 仅告警（合成数据下噪声较大，不参与判定）---
            "warnings": [],
            "changes": [],
            "execution_order": list(self.registry.execution_order or []),
        }

        if not self.influences_config.get("influences"):
            # 没有任何影响函数，无需检查，视为通过
            result["warnings"].append("influences.yaml 不含 influences，跳过预检")
            return result

        # --- 1. 静态：静默跳过检查（无需运行，最可靠）---
        result["semantic_errors"].extend(self._semantic_contract_errors())
        allowed = self._allowed_modules()
        for module_name in sorted(self._referenced_modules()):
            if module_name in allowed:
                continue
            if self._module_in_simulator_source(module_name):
                continue
            result["silent_skip"].append({
                "module": module_name,
                "note": (
                    f"module '{module_name}' 既不是 __simulator__，也不在 modules_config 的 "
                    f"selected_modules/new_modules，且 simulator.py 中找不到该键 —— "
                    f"InfluenceManager 会静默跳过整条影响函数。"
                ),
            })

        # --- 2. 动态：构造虚拟数据跑一轮 ---
        referenced_attrs = self._collect_referenced_attrs()
        seed_state: Dict[str, Any] = {}
        for attr in referenced_attrs:
            seed_state[attr] = self._seed_value(attr)

        mock = MockState(seed_state)

        # simulator_state：属性标量 + 模块键（指向 mock，使影响函数能落到全局 registry）+ time 桩
        simulator_state: Dict[str, Any] = dict(seed_state)
        for module_name in self._referenced_modules():
            if module_name != "__simulator__":
                simulator_state[module_name] = mock
        simulator_state.setdefault("time", _TimeStub())

        before = {a: getattr(mock, a) for a in referenced_attrs if hasattr(mock, a)}

        # 预检时开启影响函数严格模式：ExprInfluence/CodeInfluence 内部出错会抛出，便于捕获
        for inf in self.registry.get_all_influences():
            if hasattr(inf, "set_raise_on_error"):
                inf.set_raise_on_error(True)

        try:
            self.manager.apply_all_influences(simulator_state, target_root=mock)
        except Exception as e:  # 整体崩溃也算预检不通过
            result["ok"] = False
            result["load_error"] = f"apply_all_influences 整体异常: {e}"
            return result

        # 变化统计 + 非有限值（NaN/inf）检测
        any_change = False
        for attr in sorted(referenced_attrs):
            if not hasattr(mock, attr):
                continue
            old = before.get(attr)
            new = getattr(mock, attr)
            delta, ratio = InfluenceTestRunner._compute_delta(old, new)
            if delta not in (None, 0.0):
                any_change = True
            if isinstance(new, float) and (math.isnan(new) or math.isinf(new)):
                result["non_finite"].append({"attr": attr, "value": str(new)})
            elif ratio is not None and (abs(ratio) > 1000.0 or (delta is not None and abs(delta) > _ANOMALY_ABS)):
                # 合成数据单轮巨变多为播种伪影，仅作告警，不硬门
                result["warnings"].append(
                    f"指标 {attr} 单轮变化较大: {old} -> {new} (ratio={ratio:.4g})，请人工确认是否真爆炸"
                )
            result["changes"].append({
                "attr": attr, "before": old, "after": new,
                "delta": delta, "delta_ratio": ratio,
            })

        # 从执行轨迹提取异常：区分“影响函数写坏了(硬门)”与“合成数据伪影(告警)”
        for ev in self.manager.last_run_trace:
            if ev.get("event") == "apply_error":
                err = str(ev.get("error") or "")
                entry = {"name": ev.get("name"), "target": ev.get("target"), "error": err}
                if self._is_broken_influence_error(err):
                    result["broken_influence"].append(entry)
                else:
                    # 多为把 residents/price_history 等集合 mock 成标量导致的 AttributeError
                    result["warnings"].append(
                        f"影响函数 {entry['name']} -> {entry['target']} 在合成数据上报错（疑似集合类型伪影）: {err}"
                    )
            elif ev.get("event") == "module_missing":
                mod = ev.get("module")
                if mod and not any(s["module"] == mod for s in result["silent_skip"]):
                    result["silent_skip"].append({
                        "module": mod,
                        "note": f"运行期确认 module '{mod}' 缺失，影响函数被静默跳过。",
                    })

        applied_counts: Dict[str, int] = {}
        for ev in self.manager.last_run_trace:
            if ev.get("event") == "applied" and ev.get("name"):
                name = str(ev["name"])
                applied_counts[name] = applied_counts.get(name, 0) + 1
        for name, count in applied_counts.items():
            if count > 1:
                result["semantic_errors"].append({
                    "kind": "applied_multiple_times",
                    "name": name,
                    "detail": f"动态预检确认该 influence 单轮执行了 {count} 次",
                })

        for change in result["changes"]:
            old, new = change.get("before"), change.get("after")
            if isinstance(old, (int, float)) and isinstance(new, (int, float)) and abs(old) >= 10:
                if abs(new) <= 1.0 and abs(new - old) / max(abs(old), 1.0) >= 0.8:
                    result["semantic_errors"].append({
                        "kind": "scale_collapse",
                        "target": change.get("attr"),
                        "detail": f"单轮从 {old} 压缩到 {new}，疑似混用 0-100 与 0-1 尺度",
                    })

        # 全局恒定：跑完一轮没有任何指标变化 —— 仅告警（合成数据下集合型影响普遍不改标量）
        if not any_change and not result["broken_influence"] and not result["silent_skip"]:
            result["warnings"].append("跑完一轮所有标量指标无变化，疑似整体空操作，请确认 execution_order/target_attr")

        result["ok"] = not (
            result["silent_skip"]
            or result["broken_influence"]
            or result["non_finite"]
            or result["load_error"]
            or result["semantic_errors"]
        )
        return result

    def _seed_value(self, attr: str) -> float:
        """优先用 config 初值，读不到回退 1.0；非数值也回退。"""
        val = self.config_initial_values.get(attr)
        if val is None:
            val = self.simulator_numeric_defaults.get(attr)
        if isinstance(val, bool):
            return _FALLBACK_VALUE
        if isinstance(val, (int, float)):
            return float(val)
        return _FALLBACK_VALUE

    # 合成数据把集合 mock 成标量会产生这些“伪影”错误，不算影响函数本身的错
    _ARTIFACT_ERROR_HINTS = (
        "has no attribute 'append'", "has no attribute 'items'",
        "has no attribute 'keys'", "has no attribute 'values'",
        "has no attribute 'get'", "has no attribute 'add'",
        "object is not iterable", "object is not subscriptable",
    )

    @classmethod
    def _is_broken_influence_error(cls, err: str) -> bool:
        """判断 apply 异常是否为“影响函数本身写坏了”（应硬门），而非合成数据伪影。"""
        if not err:
            return False
        low = err.lower()
        # NameError：expr/code 引用了未声明的变量 —— 真 bug
        if "is not defined" in low:
            return True
        # 集合类型伪影：放行
        for hint in cls._ARTIFACT_ERROR_HINTS:
            if hint in err:
                return False
        # 其余未知异常保守地视为真问题
        return True

    # ---------- 输出 ----------
    @staticmethod
    def to_evaluation_report(result: Dict[str, Any]) -> str:
        """把诊断结果格式化成 CodeFixer.run_optimization_session 可消费的评估报告。

        必须包含 NEED_ADJUSTMENT 和一个 ```json``` 块（含 primary_issue_category /
        suspicious_locations / recommended_investigation）。
        """
        # 选定主问题类别 + 推荐排查的技能文档（按优先级）
        if result.get("semantic_errors"):
            category = "influences.yaml semantic contract violation"
            skill = "docs/code_fixer_skills/skill_influences_silent_skip.md"
        elif result.get("silent_skip"):
            category = "influences.yaml functions silently skipped"
            skill = "docs/code_fixer_skills/skill_influences_silent_skip.md"
        elif result.get("broken_influence"):
            category = "AttributeError/KeyError in influence apply"
            skill = "docs/code_fixer_skills/skill_attribute_key_error.md"
        elif result.get("non_finite"):
            category = "numerical explosion in influences"
            skill = "docs/code_fixer_skills/skill_numerical_explosion.md"
        elif result.get("load_error"):
            category = "influences.yaml load failure"
            skill = "docs/code_fixer_skills/skill_influences_silent_skip.md"
        else:
            category = "influence preflight failed"
            skill = "docs/code_fixer_diagnostic_router.md"

        suspicious: List[Dict[str, str]] = []
        for e in result.get("semantic_errors", []):
            suspicious.append({
                "file": "influences.yaml",
                "param_or_method": f"{e.get('kind')}:{e.get('name') or e.get('target') or ''}",
                "hint": e.get("detail", "influence 语义契约不一致"),
            })
        for s in result.get("silent_skip", []):
            suspicious.append({
                "file": "influences.yaml",
                "param_or_method": f"execution_order/source module={s.get('module')}",
                "hint": s.get("note", "module 不在 simulator_state，改为 __simulator__ 或真实模块键"),
            })
        for e in result.get("broken_influence", []):
            suspicious.append({
                "file": "influences.yaml",
                "param_or_method": f"influence={e.get('name')} target={e.get('target')}",
                "hint": f"apply 抛异常: {e.get('error')}；检查 inputs 路径与 target_attr 是否存在",
            })
        for a in result.get("non_finite", []):
            suspicious.append({
                "file": "influences.yaml",
                "param_or_method": f"target={a.get('attr')}",
                "hint": (
                    f"出现非有限值 {a.get('value')}（NaN/inf）；"
                    f"检查 mode/系数、除零，必要时加 min/max 边界"
                ),
            })

        diagnosis = {
            "primary_issue_category": category,
            "suspicious_locations": suspicious,
            "recommended_investigation": [skill],
        }

        intro_messages = {
            "influences.yaml semantic contract violation": (
                "预检确认 influence 虽可执行，但存在错写对象、重复调度、死输出或数值尺度混用。"
            ),
            "influences.yaml functions silently skipped": (
                "虚拟数据预检确认：influences.yaml 中引用的模块名与 simulator_state 实际键不匹配，"
                "这些影响函数将在运行时被 InfluenceManager 静默跳过（详见 src/influences/influence_manager.py:149-151）。"
            ),
            "AttributeError/KeyError in influence apply": (
                "虚拟数据预检确认：影响函数在执行时抛出异常，通常是 expr/code 引用了未定义变量或 target_attr 不存在。"
            ),
            "numerical explosion in influences": (
                "虚拟数据预检确认：影响函数产生 NaN / inf 非有限值，通常是除零、系数过大或缺少边界。"
            ),
            "influences.yaml load failure": (
                "虚拟数据预检确认：influences.yaml 加载或执行整体失败。"
            ),
        }
        intro = intro_messages.get(
            category,
            "虚拟数据预检发现 influence 机制存在异常，详情见下方结构化诊断。"
        )

        lines = [
            "# Influence 预检诊断报告",
            "",
            "NEED_ADJUSTMENT",
            "",
            intro,
            "",
            "```json",
            json.dumps(diagnosis, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 人类可读摘要",
        ]
        for s in result.get("silent_skip", []):
            lines.append(f"- [静默跳过] {s.get('note')}")
        for e in result.get("semantic_errors", []):
            lines.append(f"- [语义契约] {e.get('kind')}: {e.get('detail')}")
        for e in result.get("broken_influence", []):
            lines.append(f"- [执行异常] {e.get('name')} -> {e.get('target')}: {e.get('error')}")
        for a in result.get("non_finite", []):
            lines.append(f"- [非有限值] {a.get('attr')} = {a.get('value')}")
        if result.get("load_error"):
            lines.append(f"- [加载失败] {result.get('load_error')}")
        for w in result.get("warnings", []):
            lines.append(f"- [告警] {w}")
        return "\n".join(lines)


def preflight_project(config_dir: str, simulator_path: str) -> Dict[str, Any]:
    """便捷入口：对一个项目目录跑通用 influence 预检，返回结构化结果。"""
    pf = InfluencePreflight.from_project_dir(config_dir, simulator_path)
    return pf.run()


def _federal_housing_initial_state() -> Tuple[Dict[str, Any], Dict[str, Tuple[str, ...]]]:
    """federal_housing_policy_impact 的默认初始状态与属性映射。"""
    state = {
        "mortgage_market": {
            "gse_purchase_share": 0.1,
            "mortgage_rate": 8.0,
            "origination_volume": 100.0,
            "refinance_volume": 20.0,
            "debt_stock": 5000.0,
            "repayment_rate": 0.15,
        },
        "macro_state": {
            "residential_investment": 200.0,
            "house_price_index": 100.0,
            "unemployment_rate": 5.0,
            "personal_income": 80000.0,
        },
        "homeownership_rate": 64.0,
        "base_origination_volume": 100.0,
        "resident_count": 20,
        "residents_total_income": 1000.0,
    }
    attr_map = {
        "gse_purchase_share": ("mortgage_market", "gse_purchase_share"),
        "mortgage_rate": ("mortgage_market", "mortgage_rate"),
        "origination_volume": ("mortgage_market", "origination_volume"),
        "refinance_volume": ("mortgage_market", "refinance_volume"),
        "debt_stock": ("mortgage_market", "debt_stock"),
        "residential_investment": ("macro_state", "residential_investment"),
        "house_price_index": ("macro_state", "house_price_index"),
        "unemployment_rate": ("macro_state", "unemployment_rate"),
        "personal_income": ("macro_state", "personal_income"),
    }
    return state, attr_map


def main() -> None:
    parser = argparse.ArgumentParser(description="隔离测试项目 influences.yaml")
    parser.add_argument("--project", default="federal_housing_policy_impact", help="项目名称")
    parser.add_argument("--projects-root", default="projects", help="projects 目录")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="使用通用预检（自动推导虚拟数据 + 静默跳过/异常/爆炸检测）",
    )
    args = parser.parse_args()

    if args.preflight:
        config_dir = os.path.join(args.projects_root, args.project, "config")
        simulator_path = os.path.join(args.projects_root, args.project, "simulator.py")
        result = preflight_project(config_dir, simulator_path)
        print(f"执行顺序: {result['execution_order']}")
        print(f"\n预检结果: {'通过' if result['ok'] else '不通过'}")
        for s in result["silent_skip"]:
            print(f"  [静默跳过] module={s['module']}: {s['note']}")
        for e in result["semantic_errors"]:
            print(f"  [语义契约] {e.get('kind')}: {e.get('detail')}")
        for e in result["broken_influence"]:
            print(f"  [执行异常] {e['name']} -> {e['target']}: {e['error']}")
        for a in result["non_finite"]:
            print(f"  [非有限值] {a['attr']} = {a['value']}")
        if result.get("load_error"):
            print(f"  [加载失败] {result['load_error']}")
        for w in result["warnings"]:
            print(f"  [告警] {w}")
        sys.exit(0 if result["ok"] else 1)

    runner = InfluenceTestRunner.from_project(args.project, args.projects_root)

    if args.project == "federal_housing_policy_impact":
        state, attr_map = _federal_housing_initial_state()
    else:
        raise NotImplementedError(
            f"暂不支持项目 {args.project} 的旧式测试，请改用 --preflight 通用预检"
        )

    mock = MockState(state, attr_map)
    result = runner.run(mock, extra_state={"current_time": 1970, "time": _TimeStub(1970, 1970)})

    print(f"执行顺序: {result['execution_order']}")
    print("\n指标变化:")
    for c in result["changes"]:
        delta_str = f"{c['delta']:.4g}" if c["delta"] is not None else "N/A"
        ratio_str = f"{c['delta_ratio']:.4g}" if c["delta_ratio"] is not None else "N/A"
        line = (
            f"  {c['attr']}: {c['before']} -> {c['after']}"
            f"  delta={delta_str} ratio={ratio_str}"
        )
        if c["anomaly"]:
            line += "  [ANOMALY]"
        print(line)

    if result["anomalies"]:
        print(f"\n发现 {len(result['anomalies'])} 个异常影响:")
        for c in result["anomalies"]:
            ratio_str = f"{c['delta_ratio']:.4g}" if c["delta_ratio"] is not None else "N/A"
            print(f"  - {c['attr']}: ratio={ratio_str}")
        sys.exit(1)
    else:
        print("\n未发现异常影响。")


if __name__ == "__main__":
    main()
