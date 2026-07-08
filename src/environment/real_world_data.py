"""真实世界数据集成模块。

把 WDI / WTO 等预处理后的数据加载、LLM 动态映射、外生序列生成
整合到一个模块，供阶段 3.45 使用。

主要类：
  - RealWorldCatalog: 加载 data_catalog 目录下的 CSV/CSV.GZ 文件，提供 query/list 接口
  - ExogenousMapping: 单个节点的映射结果
  - ExogenousMapper: 用 LLM 把 (module, param) 映射到真实指标
  - ExogenousSeriesBuilder: 把查到的指标数据转成外生时间序列
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import warnings
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml


# =============================================================================
# RealWorldCatalog — 加载预处理后的真实数据文件
# =============================================================================

class RealWorldCatalog:
    """真实数据目录加载器。"""

    def __init__(self, catalog_dir: str):
        self.catalog_dir = catalog_dir
        self._data: Dict[str, pd.DataFrame] = {}  # {source_name: dataframe}
        self._loaded = False

    def load(self) -> bool:
        """加载目录下所有 CSV / CSV.GZ 文件到内存。返回是否加载成功。"""
        if not os.path.isdir(self.catalog_dir):
            return False

        patterns = ["*.csv", "*.csv.gz"]
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(self.catalog_dir, p)))
        if not files:
            return False

        for path in files:
            fname = os.path.basename(path)
            try:
                key = fname.replace(".csv.gz", "").replace(".csv", "")
                self._data[key] = pd.read_csv(path)
            except Exception as e:
                warnings.warn(f"加载 {fname} 失败: {e}")

        self._loaded = bool(self._data)
        return self._loaded

    def is_loaded(self) -> bool:
        return self._loaded

    def query(
        self,
        indicator_code: str,
        country_codes: Optional[List[str]] = None,
        year_start: int = 2000,
        year_end: int = 2024,
    ) -> Optional[pd.Series]:
        """查询指定指标的时间序列。

        Args:
            indicator_code: 指标代码（如 "NY_GDP_MKTP_KD_ZG"）
            country_codes: 国别代码列表（如 ["USA", "CHN"]），None 表示取所有国家平均
            year_start: 起始年份
            year_end: 结束年份

        Returns:
            pd.Series, index=year, value=指标值；查不到返回 None
        """
        if not self._loaded:
            return None

        for key, df in self._data.items():
            if "indicator_code" in df.columns:
                # WDI 格式：country_code, year, indicator_code, value
                subset = df[df["indicator_code"] == indicator_code].copy()
                if subset.empty:
                    continue

                if country_codes:
                    subset = subset[subset["country_code"].isin(country_codes)]
                    if subset.empty:
                        continue

                subset = subset[(subset["year"] >= year_start) & (subset["year"] <= year_end)]
                result = subset.groupby("year")["value"].mean()
                result = result.sort_index()
                return result

            elif "hs2" in df.columns:
                # WTO 格式：reporter_code, year, hs2, trade_flow, value
                # WTO 的 indicator_code 形如 "WTO_72_EXPORT"
                parts = indicator_code.split("_")
                if len(parts) < 3 or parts[0] != "WTO":
                    continue
                hs2 = parts[1]
                trade_flow = "_".join(parts[2:]).lower()

                subset = df[(df["hs2"] == hs2) & (df["trade_flow"] == trade_flow)].copy()
                if subset.empty:
                    continue

                if country_codes:
                    subset = subset[subset["reporter_code"].isin(country_codes)]
                    if subset.empty:
                        continue

                subset = subset[(subset["year"] >= year_start) & (subset["year"] <= year_end)]
                result = subset.groupby("year")["value"].mean()
                result = result.sort_index()
                return result

        return None

    def list_indicators(self) -> List[Dict[str, str]]:
        """列出所有可用指标（供 LLM 映射使用）。"""
        if not self._loaded:
            return []

        indicators = []
        for key, df in self._data.items():
            if "indicator_code" in df.columns:
                info = df[["indicator_code", "indicator_name"]].drop_duplicates()
                for _, row in info.iterrows():
                    indicators.append({
                        "code": row["indicator_code"],
                        "name": row["indicator_name"],
                    })
            elif "hs2" in df.columns:
                for hs2 in sorted(df["hs2"].unique()):
                    for flow in sorted(df["trade_flow"].unique()):
                        indicators.append({
                            "code": f"WTO_{hs2}_{flow.upper()}",
                            "name": f"HS{hs2} {flow} value",
                        })
        return indicators


# =============================================================================
# ExogenousMapper — LLM 动态映射 (module, param) -> 真实指标
# =============================================================================

class ExogenousMapping:
    """映射结果。"""

    def __init__(
        self,
        node_slug: str,
        indicator_codes: List[str],
        match_type: str,  # "use_indicator" | "context_indicators" | "no_match"
        reasoning: str = "",
    ):
        self.node_slug = node_slug
        self.indicator_codes = indicator_codes
        self.match_type = match_type
        self.reasoning = reasoning

    @property
    def has_match(self) -> bool:
        return self.match_type != "no_match" and len(self.indicator_codes) > 0

    def __repr__(self):
        return (
            f"ExogenousMapping(slug={self.node_slug}, "
            f"match={self.match_type}, codes={self.indicator_codes})"
        )


class ExogenousMapper:
    """外生变量映射器。"""

    def __init__(self, registry_path: str, cache_path: Optional[str] = None):
        self.registry_path = registry_path
        self.cache_path = cache_path or os.path.join(
            os.path.dirname(registry_path), "llm_mapping_cache.json"
        )
        self._llm_callback: Optional[Callable[[str], Awaitable[str]]] = None
        self._registry: List[Dict[str, str]] = []
        self._cache: Dict[str, dict] = {}
        self._load_registry()
        self._load_cache()

    def set_llm_callback(self, callback: Callable[[str], Awaitable[str]]):
        """设置 LLM 调用回调（由 project_master 注入）。"""
        self._llm_callback = callback

    def _load_registry(self):
        """加载 indicator_registry.yaml。"""
        if not os.path.exists(self.registry_path):
            warnings.warn(f"indicator_registry.yaml 不存在: {self.registry_path}")
            return
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._registry = data.get("indicators", []) if isinstance(data, dict) else []
        print(f"[Mapper] 加载了 {len(self._registry)} 个指标注册信息")

    def _load_cache(self):
        """加载 LLM 映射缓存。"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                print(f"[Mapper] 加载了 {len(self._cache)} 条缓存映射")
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save_cache(self):
        """持久化缓存。"""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except IOError as e:
            warnings.warn(f"保存 LLM 映射缓存失败: {e}")

    def _cache_key(self, module: str, param: str) -> str:
        return f"{module}__{param}"

    async def map_node(
        self,
        node: Dict[str, str],
        description_md: str = "",
    ) -> ExogenousMapping:
        """将单个外生节点映射到真实数据指标。"""
        module = node.get("module", "")
        param = node.get("param", "")
        slug = node.get("slug", "")
        key = self._cache_key(module, param)

        if key in self._cache:
            cached = self._cache[key]
            return ExogenousMapping(
                node_slug=slug,
                indicator_codes=cached.get("indicator_codes", []),
                match_type=cached.get("match_type", "no_match"),
                reasoning=cached.get("reasoning", "（缓存命中）"),
            )

        if not self._registry or self._llm_callback is None:
            return ExogenousMapping(slug, [], "no_match", "无注册表或无 LLM 回调")

        prompt = self._build_prompt(module, param, description_md)

        try:
            raw = await self._llm_callback(prompt)
            parsed = self._parse_llm_response(raw)
        except Exception as e:
            print(f"[Mapper] LLM 映射失败 ({module}.{param}): {e}")
            parsed = ExogenousMapping(slug, [], "no_match", f"LLM 调用失败: {e}")

        self._cache[key] = {
            "indicator_codes": parsed.indicator_codes,
            "match_type": parsed.match_type,
            "reasoning": parsed.reasoning,
        }
        self._save_cache()

        return parsed

    def _build_prompt(self, module: str, param: str, description_md: str) -> str:
        """构造 LLM 映射 prompt。"""
        desc_summary = (description_md or "")[:1500]
        registry_text = "\n".join(
            f"  - {ind['code']}: {ind.get('name', '')} — {ind.get('description', '')}"
            for ind in self._registry
        )

        prompt = f"""你是一个仿真变量映射专家。请判断仿真中的参数名是否与真实世界数据指标匹配。

【仿真参数】
- 所属模块: {module}
- 参数名: {param}

【仿真设计文档摘要】
{desc_summary}

【可用真实数据指标】
{registry_text}

请判断：
1. 如果参数名直接对应某个真实数据指标（如 "GDP growth" → "NY_GDP_MKTP_KD_ZG"），
   返回 match_type="use_indicator"，indicator_codes 中只放那个指标。
2. 如果参数名没有直接对应指标，但有几个指标能提供相关背景参考（如 "social unrest index"
   与通胀率、失业率、GDP增长率相关），返回 match_type="context_indicators"，
   indicator_codes 中放 1~5 个相关指标。
3. 如果没有任何指标与这个参数相关，返回 match_type="no_match"，indicator_codes 为空。

输出格式（纯 JSON，不要其他解释）：
{{"indicator_codes": ["code1", "code2"], "match_type": "use_indicator|context_indicators|no_match", "reasoning": "简短说明"}}
"""
        return prompt

    def _parse_llm_response(self, raw: str) -> ExogenousMapping:
        """解析 LLM 返回的 JSON。"""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text
            text = text.rsplit("```", 1)[0] if "```" in text else text
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return ExogenousMapping("", [], "no_match", "JSON 解析失败")
            else:
                return ExogenousMapping("", [], "no_match", "JSON 解析失败")

        codes = data.get("indicator_codes", [])
        match_type = data.get("match_type", "no_match")
        reasoning = data.get("reasoning", "")

        if match_type not in ("use_indicator", "context_indicators", "no_match"):
            match_type = "no_match"

        return ExogenousMapping("", codes, match_type, reasoning)


# =============================================================================
# ExogenousSeriesBuilder — 将真实数据转为外生时间序列
# =============================================================================

class ExogenousSeriesBuilder:
    """外生序列构建器。"""

    def __init__(self, catalog: RealWorldCatalog):
        self.catalog = catalog

    def build_series(
        self,
        indicator_code: str,
        total_steps: int,
        country_codes: Optional[List[str]] = None,
        year_start: int = 2000,
        year_end: int = 2024,
        direction: str = "",
        normalize: bool = True,
    ) -> List[float]:
        """路径 A：提取单个真实指标序列，归一化后返回。"""
        series = self.catalog.query(indicator_code, country_codes, year_start, year_end)
        if series is None or len(series) < 2:
            return []

        values = series.values.astype(float)
        values = values[~np.isnan(values)]
        if len(values) < 2:
            return []

        if normalize:
            v_min, v_max = values.min(), values.max()
            if v_max > v_min:
                values = (values - v_min) / (v_max - v_min)
            else:
                values = np.full_like(values, 0.5)

        if direction == "decrease":
            if self._is_trending_up(values):
                values = 1.0 - values
        elif direction == "increase":
            if self._is_trending_down(values):
                values = 1.0 - values

        result = self._resample(values, total_steps)
        return [round(float(v), 6) for v in result]

    def build_context(
        self,
        indicator_codes: List[str],
        country_codes: Optional[List[str]] = None,
        year_start: int = 2000,
        year_end: int = 2024,
    ) -> Dict[str, List[float]]:
        """路径 B：提取多个指标的原始真实数据序列（供 LLM prompt 参考）。"""
        context = {}
        for code in indicator_codes:
            series = self.catalog.query(code, country_codes, year_start, year_end)
            if series is not None and len(series) > 0:
                context[code] = [round(float(v), 4) for v in series.values if not np.isnan(v)]
        return context

    @staticmethod
    def _is_trending_up(values: np.ndarray) -> bool:
        if len(values) < 2:
            return False
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        return slope > 0

    @staticmethod
    def _is_trending_down(values: np.ndarray) -> bool:
        if len(values) < 2:
            return False
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        return slope < 0

    @staticmethod
    def _resample(values: np.ndarray, target_len: int) -> np.ndarray:
        if len(values) == target_len:
            return values
        if len(values) < target_len:
            x_old = np.linspace(0, 1, len(values))
            x_new = np.linspace(0, 1, target_len)
            return np.interp(x_new, x_old, values)
        else:
            return values[:target_len]


# =============================================================================
# 兼容别名（旧 import 仍可工作）
# =============================================================================

# 如果未来需要把旧 import 重定向，可在此添加：
# from .real_world_data import RealWorldCatalog as RealWorldCatalog
# 但 project_master 和测试文件会一并改成从新位置 import。
