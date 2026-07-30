"""跨配置事实契约预检。

不引入新的业务 schema；从已经生成的 agent_profile/jobs/towns/simulation 配置
自动提取事实词表，检查后续文件是否仍引用同一名称和真实路径。
"""

from __future__ import annotations

import json
import os
import ast
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


_OCCUPATION_HINTS = ("职业", "工作", "occupation", "profession", "job")
_TOWN_HINTS = ("城镇", "城市", "所在地", "town", "city", "location")
_UNEMPLOYED_MARKERS = ("失业", "unemployed", "unemployment", "无业")


class ProjectContractPreflight:
    def __init__(self, config_dir: str, project_root: Optional[str] = None):
        self.config_dir = Path(config_dir)
        self.project_root = Path(project_root) if project_root else self.config_dir.parents[2]

    @staticmethod
    def _load(path: Path) -> Any:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            if path.suffix.lower() == ".json":
                return json.load(f)
            return yaml.safe_load(f)

    @staticmethod
    def _contains_hint(name: Any, hints: Iterable[str]) -> bool:
        text = str(name or "").lower()
        return any(h.lower() in text for h in hints)

    @staticmethod
    def _is_unemployed_choice(value: Any) -> bool:
        text = str(value or "").lower()
        return any(marker in text for marker in _UNEMPLOYED_MARKERS)

    @staticmethod
    def _roles(profile: Any) -> List[dict]:
        if isinstance(profile, dict) and isinstance(profile.get("agents"), list):
            return [x for x in profile["agents"] if isinstance(x, dict)]
        if isinstance(profile, list):
            return [x for x in profile if isinstance(x, dict)]
        return []

    @staticmethod
    def _town_names(towns: Any) -> set[str]:
        names: set[str] = set()
        if not isinstance(towns, dict):
            return names
        for canal in towns.get("canals", []) or []:
            if not isinstance(canal, dict):
                continue
            for town in canal.get("towns", []) or []:
                if isinstance(town, dict) and town.get("name"):
                    names.add(str(town["name"]))
        for town in towns.get("other_towns", []) or []:
            if isinstance(town, dict) and town.get("name"):
                names.add(str(town["name"]))
        return names

    @staticmethod
    def _issue(kind: str, file: str, detail: str, **fields: Any) -> Dict[str, Any]:
        return {"kind": kind, "file": file, "detail": detail, **fields}

    def _simulator_resident_keys(self) -> set[str]:
        """提取 simulator 聚合居民属性时实际消费的 runtime keys。"""
        path = self.config_dir.parent / "simulator.py"
        if not path.exists():
            return set()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        keys = set()
        aggregators = {"_sum_resident_attr", "_avg_resident_attr"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in aggregators or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
        return keys

    def run(self) -> Dict[str, Any]:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        try:
            profile = self._load(self.config_dir / "agent_profile.yaml") or {}
            jobs = self._load(self.config_dir / "jobs_config.yaml") or {}
            towns = self._load(self.config_dir / "towns_data.json") or {}
            simulation = self._load(self.config_dir / "simulation_config.yaml") or {}
        except Exception as exc:
            return {
                "ok": False,
                "errors": [self._issue("config_load_error", "config", str(exc))],
                "warnings": [],
            }

        jobs_info = jobs.get("jobs_info", {}) if isinstance(jobs, dict) else {}
        ratios = jobs.get("professions_ratio", {}) if isinstance(jobs, dict) else {}
        job_names = {str(x) for x in jobs_info} if isinstance(jobs_info, dict) else set()
        ratio_names = {str(x) for x in ratios} if isinstance(ratios, dict) else set()
        for name in sorted(ratio_names - job_names):
            errors.append(self._issue(
                "ratio_job_missing",
                "jobs_config.yaml",
                f"professions_ratio 引用职业 {name!r}，但 jobs_info 未定义",
                value=name,
            ))
        for name in sorted(job_names - ratio_names):
            warnings.append(self._issue(
                "job_without_initial_ratio",
                "jobs_config.yaml",
                f"职业 {name!r} 没有初始比例；允许为零，但应确认这是有意设计",
                value=name,
            ))

        town_names = self._town_names(towns)
        resident_runtime_keys: set[str] = set()
        for role in self._roles(profile):
            entity_type = str(role.get("entity_type") or role.get("name") or "").lower()
            runtime_keys: set[str] = set()
            for attr in role.get("attributes", []) or []:
                if not isinstance(attr, dict):
                    continue
                attr_name = attr.get("name")
                runtime_key = attr.get("runtime_key")
                if not isinstance(runtime_key, str) or not runtime_key.isidentifier():
                    errors.append(self._issue(
                        "missing_runtime_key",
                        "agent_profile.yaml",
                        f"角色 {role.get('name')!r} 的属性 {attr_name!r} 缺少合法 runtime_key，显示名与运行时状态可能分裂",
                        attribute=str(attr_name),
                    ))
                elif runtime_key in runtime_keys:
                    errors.append(self._issue(
                        "duplicate_runtime_key",
                        "agent_profile.yaml",
                        f"角色 {role.get('name')!r} 重复定义 runtime_key={runtime_key!r}",
                        value=runtime_key,
                    ))
                else:
                    runtime_keys.add(runtime_key)
                    if entity_type == "resident":
                        resident_runtime_keys.add(runtime_key)
                if not isinstance(attr.get("choices"), list):
                    continue
                choices = {str(x) for x in attr["choices"]}
                if entity_type == "resident" and self._contains_hint(attr_name, _OCCUPATION_HINTS) and job_names:
                    unknown = {
                        x for x in choices
                        if x not in job_names and not self._is_unemployed_choice(x)
                    }
                    for value in sorted(unknown):
                        errors.append(self._issue(
                            "unknown_occupation_choice",
                            "agent_profile.yaml",
                            f"居民属性 {attr_name!r} 使用职业 {value!r}，不在 jobs_info 事实词表中",
                            attribute=str(attr_name),
                            value=value,
                            canonical_values=sorted(job_names),
                        ))
                if entity_type == "resident" and self._contains_hint(attr_name, _TOWN_HINTS) and town_names:
                    for value in sorted(choices - town_names):
                        errors.append(self._issue(
                            "unknown_town_choice",
                            "agent_profile.yaml",
                            f"居民属性 {attr_name!r} 使用城镇 {value!r}，不在 towns_data.json 中",
                            attribute=str(attr_name),
                            value=value,
                            canonical_values=sorted(town_names),
                        ))

            for constraint in role.get("constraints", []) or []:
                if isinstance(constraint, dict) and constraint.get("action") and not constraint.get("adjustments"):
                    errors.append(self._issue(
                        "unsupported_constraint_action",
                        "agent_profile.yaml",
                        f"角色 {role.get('name')!r} 使用 action 字符串约束，但画像引擎要求结构化 adjustments",
                    ))

        for key in sorted(self._simulator_resident_keys() - resident_runtime_keys):
            errors.append(self._issue(
                "resident_runtime_key_missing",
                "agent_profile.yaml",
                f"simulator.py 聚合居民 runtime_key={key!r}，但 resident 画像未声明该代码键",
                value=key,
            ))

        data_cfg = simulation.get("data", {}) if isinstance(simulation, dict) else {}
        if isinstance(data_cfg, dict):
            for key, value in data_cfg.items():
                if not key.endswith("_path") or not isinstance(value, str) or not value.strip():
                    continue
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = self.project_root / candidate
                if not candidate.exists():
                    errors.append(self._issue(
                        "missing_config_path",
                        "simulation_config.yaml",
                        f"data.{key} 指向不存在的路径: {value}",
                        key=key,
                        value=value,
                    ))

        return {"ok": not errors, "errors": errors, "warnings": warnings}

    @staticmethod
    def to_evaluation_report(result: Dict[str, Any]) -> str:
        suspicious = [
            {
                "file": issue.get("file", "config"),
                "param_or_method": issue.get("kind", "contract"),
                "hint": issue.get("detail", "跨配置事实词表不一致"),
            }
            for issue in result.get("errors", [])
        ]
        diagnosis = {
            "primary_issue_category": "cross-config semantic inconsistency",
            "suspicious_locations": suspicious,
            "recommended_investigation": [
                "docs/code_fixer_skills/skill_cross_config_contract.md"
            ],
        }
        return "\n".join([
            "# 跨配置事实契约预检报告",
            "",
            "NEED_ADJUSTMENT",
            "",
            "```json",
            json.dumps(diagnosis, ensure_ascii=False, indent=2),
            "```",
        ])
