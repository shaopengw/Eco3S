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
import os
import re
import warnings
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from src.environment.data_processing_log import DataProcessingLog


# =============================================================================
# RealWorldCatalog — 加载预处理后的真实数据文件
# =============================================================================

class RealWorldCatalog:
    """真实数据目录加载器。"""

    def __init__(self, catalog_dir: str):
        self.catalog_dir = catalog_dir
        self._data: Dict[str, pd.DataFrame] = {}  # {source_name: dataframe}
        self._country_groups: Dict[str, Dict[str, str]] = {}  # {country_code: {income_group, region}}
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

        # 尝试加载国家分组信息（可选，用于 reference_group 中位数填补）
        group_path = os.path.join(self.catalog_dir, "country_income_groups.csv")
        if os.path.exists(group_path):
            try:
                group_df = pd.read_csv(group_path)
                for _, row in group_df.iterrows():
                    code = str(row.get("country_code", "")).strip().upper()
                    if code:
                        self._country_groups[code] = {
                            "income_group": str(row.get("income_group", "")).strip().lower(),
                            "region": str(row.get("region", "")).strip().lower(),
                        }
            except Exception as e:
                warnings.warn(f"加载国家分组信息失败: {e}")

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

    def query_group_median(
        self,
        indicator_code: str,
        reference_group: str,
        year_start: int = 2000,
        year_end: int = 2024,
    ) -> Optional[pd.Series]:
        """按 reference_group 取同组国家该指标的中位数序列。

        当前若目录下无 country_income_groups.csv，则回退为全样本国家中位数。
        reference_group 格式示例："income_group:high_income"、"region:East Asia"。
        """
        if not self._loaded or not reference_group:
            return None

        # 解析分组字段与值
        group_field, group_value = "", ""
        if ":" in reference_group:
            parts = reference_group.split(":", 1)
            group_field = parts[0].strip().lower()
            group_value = parts[1].strip().lower()

        # 若存在分组文件，过滤对应国家；否则使用所有国家
        if group_field and group_value and self._country_groups:
            country_codes = [
                code for code, info in self._country_groups.items()
                if info.get(group_field, "").lower() == group_value
            ]
            if not country_codes:
                # 没有匹配国家时回退到全样本中位数
                country_codes = None
        else:
            country_codes = None

        # 先查出目标国家集合的原始数据（不过度聚合），再按年份算中位数
        for key, df in self._data.items():
            if "indicator_code" in df.columns:
                subset = df[df["indicator_code"] == indicator_code].copy()
                if subset.empty:
                    continue

                if country_codes:
                    subset = subset[subset["country_code"].isin(country_codes)]
                    if subset.empty:
                        continue

                subset = subset[(subset["year"] >= year_start) & (subset["year"] <= year_end)]
                if subset.empty:
                    continue
                result = subset.groupby("year")["value"].median()
                result = result.sort_index()
                return result

            elif "hs2" in df.columns:
                # WTO 格式暂不细分收入组，按全样本中位数处理
                parts = indicator_code.split("_")
                if len(parts) < 3 or parts[0] != "WTO":
                    continue
                hs2 = parts[1]
                trade_flow = "_".join(parts[2:]).lower()

                subset = df[(df["hs2"] == hs2) & (df["trade_flow"] == trade_flow)].copy()
                if subset.empty:
                    continue

                subset = subset[(subset["year"] >= year_start) & (subset["year"] <= year_end)]
                if subset.empty:
                    continue
                result = subset.groupby("year")["value"].median()
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
        frequency: str = "annual",
        target_frequency: str = "annual",
        fill_forward_years: int = 5,
        reference_group: str = "",
        volatility: str = "",
        aggregation: str = "mean",
    ):
        self.node_slug = node_slug
        self.indicator_codes = indicator_codes
        self.match_type = match_type
        self.reasoning = reasoning
        self.frequency = frequency
        self.target_frequency = target_frequency
        self.fill_forward_years = fill_forward_years
        self.reference_group = reference_group
        self.volatility = volatility
        self.aggregation = aggregation

    @property
    def has_match(self) -> bool:
        return self.match_type != "no_match" and len(self.indicator_codes) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator_codes": self.indicator_codes,
            "match_type": self.match_type,
            "reasoning": self.reasoning,
            "frequency": self.frequency,
            "target_frequency": self.target_frequency,
            "fill_forward_years": self.fill_forward_years,
            "reference_group": self.reference_group,
            "volatility": self.volatility,
            "aggregation": self.aggregation,
        }

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
                frequency=cached.get("frequency", "annual"),
                target_frequency=cached.get("target_frequency", "annual"),
                fill_forward_years=cached.get("fill_forward_years", 5),
                reference_group=cached.get("reference_group", ""),
                volatility=cached.get("volatility", ""),
                aggregation=cached.get("aggregation", "mean"),
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
            "frequency": parsed.frequency,
            "target_frequency": parsed.target_frequency,
            "fill_forward_years": parsed.fill_forward_years,
            "reference_group": parsed.reference_group,
            "volatility": parsed.volatility,
            "aggregation": parsed.aggregation,
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
{{"indicator_codes": ["code1", "code2"], "match_type": "use_indicator|context_indicators|no_match", "reasoning": "简短说明", "frequency": "annual", "fill_forward_years": 5, "reference_group": "", "volatility": "", "aggregation": "mean"}}

字段说明：
- frequency: 源数据频率，可选 annual/quarterly/monthly，默认 annual。
- fill_forward_years: 后向外推时取数据起始后前 N 年计算平均增长率，默认 5。
- reference_group: 用于同组中位数填补的分组，如 "income_group:high_income"，不需要则留空。
- volatility: 指标波动类型，高波动填 "high"，否则留空。
- aggregation: 高频转低频时的聚合方式，"mean" 或 "last"，默认 "mean"。
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

        frequency = str(data.get("frequency", "annual") or "annual").lower()
        if frequency not in ("annual", "quarterly", "monthly"):
            frequency = "annual"

        fill_forward_years = data.get("fill_forward_years", 5)
        try:
            fill_forward_years = max(1, int(fill_forward_years))
        except (TypeError, ValueError):
            fill_forward_years = 5

        reference_group = str(data.get("reference_group", "") or "")
        volatility = str(data.get("volatility", "") or "").lower()
        if volatility not in ("high", ""):
            volatility = ""

        aggregation = str(data.get("aggregation", "mean") or "mean").lower()
        if aggregation not in ("mean", "last"):
            aggregation = "mean"

        return ExogenousMapping(
            "",
            codes,
            match_type,
            reasoning,
            frequency=frequency,
            fill_forward_years=fill_forward_years,
            reference_group=reference_group,
            volatility=volatility,
            aggregation=aggregation,
        )


# =============================================================================
# ExogenousSeriesBuilder — 将真实数据转为外生时间序列
# =============================================================================

class ExogenousSeriesBuilder:
    """外生序列构建器。"""

    def __init__(self, catalog: RealWorldCatalog):
        self.catalog = catalog

    @staticmethod
    def _series_str(series: pd.Series, max_items: int = 30) -> str:
        """把序列格式化为 "year: value" 的字符串，便于日志查看。"""
        items = []
        for y, v in series.dropna().items():
            fy = float(y)
            vy = round(float(v), 6)
            if fy.is_integer():
                items.append((int(fy), vy))
            else:
                items.append((round(fy, 3), vy))
        if len(items) > max_items:
            head = items[:10]
            tail = items[-10:]
            return "{" + ", ".join(f"{y}: {v}" for y, v in head) + " ... " + ", ".join(f"{y}: {v}" for y, v in tail) + "}"
        return "{" + ", ".join(f"{y}: {v}" for y, v in items) + "}"

    def build_series(
        self,
        indicator_code: str,
        total_steps: int,
        country_codes: Optional[List[str]] = None,
        year_start: int = 2000,
        year_end: int = 2024,
        direction: str = "",
        normalize: bool = True,
        mapping: Optional[ExogenousMapping] = None,
        log_path: str = "",
    ) -> Tuple[List[float], List[bool]]:
        """路径 A：提取单个真实指标序列，经清洗、外推、预测、频率转换后返回。"""
        # 默认 mapping，保持旧调用兼容
        if mapping is None:
            mapping = ExogenousMapping(
                node_slug="",
                indicator_codes=[indicator_code],
                match_type="use_indicator",
            )

        log = DataProcessingLog(log_path) if log_path else DataProcessingLog("")

        print(f"\n========== [ExogenousSeriesBuilder] 开始处理指标: {indicator_code} ==========")
        print(f"配置参数: year_start={year_start}, year_end={year_end}, total_steps={total_steps}")
        if mapping:
            print(
                f"映射配置: frequency={mapping.frequency}, target_frequency={mapping.target_frequency}, "
                f"fill_forward_years={mapping.fill_forward_years}, reference_group={mapping.reference_group!r}, "
                f"volatility={mapping.volatility!r}, aggregation={mapping.aggregation}"
            )

        # 1) 查询原始序列
        series = self.catalog.query(
            indicator_code, country_codes, year_start, year_end
        )
        if series is None or len(series) < 2:
            print(f"[ExogenousSeriesBuilder] 查询结果为空或不足 2 个点，无法构建序列")
            return [], []

        print(f"原始查询结果（{len(series)} 年）: {self._series_str(series)}")

        # 按完整年份索引对齐，便于识别真实缺失年份
        full_years = pd.Series(
            index=range(int(series.index.min()), int(series.index.max()) + 1),
            dtype=float,
        )
        full_years.loc[series.index] = series.values.astype(float)

        # 2) 缺失值处理
        print(f"\n-- 步骤 1: 缺失值处理 --")
        full_years, remaining_gaps = self._impute_missing(
            full_years,
            log,
            indicator=indicator_code,
            reference_group=mapping.reference_group,
            catalog=self.catalog,
        )
        if remaining_gaps:
            print(f"仍有未填补缺口年份: {remaining_gaps}")

        # 3) 后向外推
        backward_extrapolated_years: List[int] = []
        if year_start < int(full_years.index.min()):
            print(f"\n-- 步骤 2: 后向外推 --")
            full_years, backward_extrapolated_years = self._backward_extrapolate(
                full_years,
                target_start=year_start,
                fill_forward_years=mapping.fill_forward_years,
                log=log,
                indicator=indicator_code,
            )

        # 4) 未来预测
        is_forecasted = pd.Series(False, index=full_years.index)
        if backward_extrapolated_years:
            is_forecasted.loc[backward_extrapolated_years] = True
        if year_end > int(full_years.index.max()):
            print(f"\n-- 步骤 3: 未来预测 --")
            full_years, forecast_index = self._forecast(
                full_years,
                target_end=year_end,
                log=log,
                indicator=indicator_code,
            )
            is_forecasted = pd.Series(False, index=full_years.index)
            is_forecasted.loc[backward_extrapolated_years] = True
            is_forecasted.loc[forecast_index] = True

        # 确保目标年份范围完整
        target_years = pd.Series(
            index=range(year_start, year_end + 1),
            dtype=float,
        )
        target_years.loc[full_years.index] = full_years.values
        is_forecasted = is_forecasted.reindex(target_years.index, fill_value=False)

        print(f"\n目标年份序列（{len(target_years)} 年）: {self._series_str(target_years)}")
        print(f"预测标记: {dict(zip(target_years.index, is_forecasted.values))}")

        # 5) 频率转换
        if mapping.frequency != mapping.target_frequency:
            print(f"\n-- 步骤 4: 频率转换 --")
            target_years = self._convert_frequency(
                target_years,
                source_freq=mapping.frequency,
                target_freq=mapping.target_frequency,
                volatility=mapping.volatility,
                aggregation=mapping.aggregation,
                log=log,
                indicator=indicator_code,
            )
            # 低频->高频后需要重新生成 forecast 标记：简单按原标记重复/聚合
            is_forecasted = self._expand_forecast_flags(
                is_forecasted,
                source_freq=mapping.frequency,
                target_freq=mapping.target_frequency,
            )

        values = target_years.values.astype(float)
        forecast_flags = is_forecasted.values.tolist()

        # 长度对齐
        result = self._resample(values, total_steps)
        # forecast_flags 也要同步对齐到 total_steps
        flags = self._resample_flags(forecast_flags, total_steps)

        print(f"\n最终输出序列（{len(result)} 步）: {[round(float(v), 6) for v in result]}")
        print(f"最终 forecast 标记（{len(flags)} 步）: {flags}")
        print(f"========== [ExogenousSeriesBuilder] 指标 {indicator_code} 处理结束 ==========\n")

        return [round(float(v), 6) for v in result], flags

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

    # -------------------------------------------------------------------------
    # 缺失值处理
    # -------------------------------------------------------------------------
    @staticmethod
    def _impute_missing(
        series: pd.Series,
        log: DataProcessingLog,
        indicator: str,
        reference_group: str = "",
        catalog: Optional[RealWorldCatalog] = None,
    ) -> Tuple[pd.Series, List[int]]:
        """三级缺失处理：线性插补 -> 同组中位数 -> 记录剩余缺口。"""
        missing_years = [int(y) for y in series[series.isna()].index.tolist()]
        print(f"  输入序列: {ExogenousSeriesBuilder._series_str(series)}")
        print(f"  缺失年份: {missing_years}（共 {len(missing_years)} 个）")

        if series.isna().sum() == 0:
            print(f"  结果: 无缺失值，跳过")
            return series, []

        # 首选：连续缺失 <=3 年线性插补
        imputed = series.interpolate(method="linear", limit=3, limit_direction="both")
        filled_linear = int(series.isna().sum() - imputed.isna().sum())
        if filled_linear > 0:
            print(f"  线性插补: 填补了 {filled_linear} 个缺失值")
            filled_detail = {
                int(y): round(float(v), 6)
                for y, v in imputed.items()
                if y in missing_years and not np.isnan(v)
            }
            print(f"  填补后值: {filled_detail}")
            log.record(
                operation="missing_value_impute",
                indicator=indicator,
                period=f"{int(series.index.min())}-{int(series.index.max())}",
                method="linear_interpolation",
                details={"filled_count": filled_linear, "filled_values": filled_detail},
            )
        remaining = imputed.isna()

        # 次选：连续缺失 >3 年用同组中位数
        if remaining.any() and reference_group and catalog is not None:
            print(f"  尝试同组中位数填补: reference_group={reference_group}")
            group_series = catalog.query_group_median(
                indicator, reference_group,
                year_start=int(series.index.min()),
                year_end=int(series.index.max()),
            )
            if group_series is not None and len(group_series) > 0:
                print(f"  同组中位数序列: {ExogenousSeriesBuilder._series_str(group_series)}")
                for year in imputed[remaining].index:
                    if year in group_series.index and not np.isnan(group_series.loc[year]):
                        imputed.loc[year] = group_series.loc[year]
                still_missing = imputed.isna()
                filled_count = int(remaining.sum() - still_missing.sum())
                if filled_count > 0:
                    log.record(
                        operation="missing_value_impute",
                        indicator=indicator,
                        period=f"{int(series.index.min())}-{int(series.index.max())}",
                        method="group_median",
                        details={"reference_group": reference_group, "filled_count": filled_count},
                    )
                remaining = still_missing
            else:
                print(f"  未找到同组中位数数据")

        # 记录仍未填补的缺口位置（交给上层 LLM 处理）
        remaining_gaps = [int(y) for y in imputed[remaining].index.tolist()]
        if remaining_gaps:
            print(f"  仍存在的缺口年份: {remaining_gaps}")
            log.record(
                operation="missing_value_impute",
                indicator=indicator,
                period=remaining_gaps,
                method="llm_pending",
                details={"remaining_count": len(remaining_gaps)},
            )

        print(f"  缺失值处理后序列: {ExogenousSeriesBuilder._series_str(imputed)}")
        return imputed, remaining_gaps

    # -------------------------------------------------------------------------
    # 异常值修正
    # -------------------------------------------------------------------------
    @staticmethod
    def _correct_outliers(
        series: pd.Series,
        log: DataProcessingLog,
        indicator: str,
    ) -> pd.Series:
        """对异常值用滚动中位数替换。优先使用 MAD 作为稳健标准差估计，MAD 为 0 时回退到 3σ。"""
        if series.isna().sum() == len(series) or len(series) < 3:
            return series

        clean = series.copy()
        print(f"  输入序列: {ExogenousSeriesBuilder._series_str(clean)}")
        median = clean.median()
        mad = np.median(np.abs(clean - median))

        if mad > 0 and not np.isnan(mad):
            modified_z = 0.6745 * (clean - median) / mad
            mask = np.abs(modified_z) > 3.0
            details = {"median": float(median), "mad": float(mad), "method": "mad"}
            print(f"  使用 MAD 检测: median={median:.6f}, mad={mad:.6f}")
            print(f"  各点 modified_z: {dict(zip(clean.index, [round(float(z), 3) for z in modified_z]))}")
        else:
            # MAD 为 0（超过一半值相同），回退到经典 3σ
            mean = clean.mean()
            std = clean.std()
            print(f"  MAD=0，回退到 3σ: mean={mean:.6f}, std={std:.6f}")
            if std == 0 or np.isnan(std):
                print(f"  标准差为 0，无需异常值处理")
                return clean
            mask = (clean - mean).abs() > 3 * std
            details = {"mean": float(mean), "std": float(std), "method": "std_fallback"}

        if mask.any():
            outlier_years = [int(y) for y in clean[mask].index.tolist()]
            outlier_values = [round(float(clean.loc[y]), 6) for y in outlier_years]
            rolling_median = clean.rolling(window=3, min_periods=1, center=True).median()
            replaced_values = [round(float(rolling_median.loc[y]), 6) for y in outlier_years]
            print(f"  检测到异常值年份: {outlier_years}, 原值: {outlier_values}, 替换为滚动中位数: {replaced_values}")
            clean[mask] = rolling_median[mask]
            log.record(
                operation="outlier_3sigma_replace",
                indicator=indicator,
                period=outlier_years,
                method="rolling_median",
                details={
                    **details,
                    "replaced_count": int(mask.sum()),
                    "outlier_years": outlier_years,
                    "original_values": outlier_values,
                    "replaced_values": replaced_values,
                },
            )
        else:
            print(f"  未检测到异常值")
        print(f"  异常值处理后序列: {ExogenousSeriesBuilder._series_str(clean)}")
        return clean

    # -------------------------------------------------------------------------
    # 后向外推
    # -------------------------------------------------------------------------
    @staticmethod
    def _backward_extrapolate(
        series: pd.Series,
        target_start: int,
        fill_forward_years: int,
        log: DataProcessingLog,
        indicator: str,
    ) -> Tuple[pd.Series, List[int]]:
        """取数据起始后前 fill_forward_years 年平均增长率，反向递推缺失年份。"""
        observed = series.dropna()
        print(f"  输入序列: {ExogenousSeriesBuilder._series_str(observed)}")
        if len(observed) < 2:
            print(f"  历史数据不足 2 点，无法后向外推")
            return series, []

        first_year = int(observed.index.min())
        first_values = observed.iloc[:fill_forward_years]
        if len(first_values) < 2:
            first_values = observed

        # 计算逐年增长率的算术平均；若存在非正值则保守设为 0
        if len(first_values) >= 2 and (first_values > 0).all():
            growth_rates = first_values.pct_change().dropna()
            g = float(growth_rates.mean()) if len(growth_rates) > 0 else 0.0
        else:
            g = 0.0
        if np.isnan(g):
            g = 0.0

        print(f"  用于计算增长率的早年数据: {ExogenousSeriesBuilder._series_str(first_values)}")
        print(f"  计算得到平均增长率 g={g:.6f}, fill_forward_years={fill_forward_years}")

        # 构建完整年份索引
        full_index = range(target_start, int(observed.index.max()) + 1)
        extended = pd.Series(index=full_index, dtype=float)
        extended.loc[observed.index] = observed.values

        # 从第一个已知年份向前递推
        for year in range(first_year - 1, target_start - 1, -1):
            next_val = extended.loc[year + 1]
            if not np.isnan(next_val):
                extended.loc[year] = next_val / (1.0 + g) if g != -1.0 else next_val

        # 记录外推动作
        extrapolated_years = [y for y in range(target_start, first_year)]
        if extrapolated_years:
            extrapolated_values = {y: round(float(extended.loc[y]), 6) for y in extrapolated_years}
            print(f"  后向外推年份: {extrapolated_years}")
            print(f"  后向外推值: {extrapolated_values}")
            log.record(
                operation="backward_extrapolate",
                indicator=indicator,
                period=extrapolated_years,
                method="人工外推",
                details={"growth_rate": float(g), "fill_forward_years": fill_forward_years, "extrapolated_values": extrapolated_values},
            )
        print(f"  后向外推后序列: {ExogenousSeriesBuilder._series_str(extended)}")
        return extended, extrapolated_years

    # -------------------------------------------------------------------------
    # 未来预测
    # -------------------------------------------------------------------------
    @staticmethod
    def _forecast(
        series: pd.Series,
        target_end: int,
        log: DataProcessingLog,
        indicator: str,
    ) -> Tuple[pd.Series, List[int]]:
        """基于历史序列外推到目标未来年份。

        两种策略：
        - 序列平稳上下波动 → 取历史均值（递归平均）
        - 有明显趋势       → 线性外推
        """
        observed = series.dropna()
        print(f"  输入序列: {ExogenousSeriesBuilder._series_str(observed)}")
        if len(observed) < 2:
            last_year = int(observed.index.max()) if len(observed) > 0 else int(series.index.min())
            last_val = observed.iloc[-1] if len(observed) > 0 else 0.0
            forecast_index = list(range(last_year + 1, target_end + 1))
            forecasted = pd.Series([last_val] * len(forecast_index), index=forecast_index)
            extended = pd.concat([observed, forecasted]).sort_index()
            print(f"  历史数据不足 2 点，末值填充: last_val={last_val}, 预测年份={forecast_index}")
            if forecast_index:
                log.record(operation="forecast", indicator=indicator, period=forecast_index,
                           method="last_value_flat", details={"last_value": float(last_val)})
            return extended, forecast_index

        history_values = observed.values.astype(float)
        last_year = int(observed.index.astype(int).max())
        forecast_index = list(range(last_year + 1, target_end + 1))
        n_forecast = len(forecast_index)
        if n_forecast <= 0:
            return observed, []

        # 线性拟合，判断趋势
        x = np.arange(len(history_values))
        slope, intercept = np.polyfit(x, history_values, 1)
        avg_val = float(np.mean(history_values))

        # 趋势总变化量 < 数据均值 × 1% → 视为平稳
        if abs(slope) * len(history_values) < abs(avg_val) * 0.01:
            forecast_values = np.full(n_forecast, avg_val)
            method = "recursive_average"
            print(f"  平稳波动（|斜率×长度|={abs(slope)*len(history_values):.4f} < |均值|×1%），取递归平均={avg_val:.6f}")
        else:
            forecast_values = slope * (np.arange(len(history_values), len(history_values) + n_forecast)) + intercept
            method = "linear_extrapolation"
            print(f"  有明显趋势，线性外推: slope={slope:.6f}")

        forecast_series = pd.Series(forecast_values, index=forecast_index)
        extended = pd.concat([observed, forecast_series]).sort_index()
        forecast_detail = {int(y): round(float(v), 6) for y, v in zip(forecast_index, forecast_values)}
        print(f"  预测方法: {method}, 值: {forecast_detail}")
        log.record(operation="forecast", indicator=indicator, period=forecast_index,
                   method=method, details={"forecast_values": forecast_detail})
        return extended, forecast_index

    # -------------------------------------------------------------------------
    # 频率转换
    # -------------------------------------------------------------------------
    @staticmethod
    def _convert_frequency(
        series: pd.Series,
        source_freq: str,
        target_freq: str,
        volatility: str,
        aggregation: str,
        log: DataProcessingLog,
        indicator: str,
    ) -> pd.Series:
        """在 annual/quarterly/monthly 之间转换序列长度。"""
        if source_freq == target_freq:
            return series

        values = series.values.astype(float)
        if len(values) < 2:
            return series

        ratios = {"annual": 1, "quarterly": 4, "monthly": 12}
        source_ratio = ratios.get(source_freq, 1)
        target_ratio = ratios.get(target_freq, 1)
        print(f"  源频率={source_freq}(ratio={source_ratio}), 目标频率={target_freq}(ratio={target_ratio}), aggregation={aggregation}, volatility={volatility!r}")
        print(f"  输入序列: {ExogenousSeriesBuilder._series_str(series)}")

        if target_ratio > source_ratio:
            # 低频 -> 高频：Cubic Spline
            try:
                from scipy.interpolate import CubicSpline

                x_old = np.arange(len(values))
                n_new = len(values) * (target_ratio // source_ratio)
                x_new = np.linspace(0, len(values) - 1, n_new)
                cs = CubicSpline(x_old, values)
                new_values = cs(x_new).astype(float)

                if volatility == "high":
                    noise_std = float(np.std(values)) * 0.1
                    if noise_std > 0:
                        noise = np.random.normal(0, noise_std, size=len(new_values))
                        new_values = new_values + noise
                        print(f"  高波动模式: 添加噪声 std={noise_std:.6f}")

                new_index = np.linspace(series.index.min(), series.index.max() + 1 - 1e-9, n_new)
                result = pd.Series(new_values, index=new_index)
                print(f"  Cubic Spline: {len(values)} 点 -> {n_new} 点")
                print(f"  转换后序列: {ExogenousSeriesBuilder._series_str(result)}")
                log.record(
                    operation="frequency_convert",
                    indicator=indicator,
                    period=f"{source_freq}->{target_freq}",
                    method="cubic_spline",
                    details={"source_len": len(values), "target_len": n_new, "volatility": volatility},
                )
                return result
            except Exception as exc:
                # 失败回退到线性插值
                n_new = len(values) * (target_ratio // source_ratio)
                result = pd.Series(
                    np.interp(
                        np.linspace(0, 1, n_new),
                        np.linspace(0, 1, len(values)),
                        values,
                    ),
                    index=np.linspace(series.index.min(), series.index.max() + 1 - 1e-9, n_new),
                )
                print(f"  Cubic Spline 失败，回退线性插值: {exc}")
                log.record(
                    operation="frequency_convert",
                    indicator=indicator,
                    period=f"{source_freq}->{target_freq}",
                    method="linear_fallback",
                    details={"reason": str(exc)},
                )
                return result
        else:
            # 高频 -> 低频：聚合
            group_size = source_ratio // target_ratio
            n_groups = len(values) // group_size
            trimmed = values[: n_groups * group_size]
            reshaped = trimmed.reshape(n_groups, group_size)
            if aggregation == "last":
                new_values = reshaped[:, -1]
            else:
                new_values = reshaped.mean(axis=1)

            new_index = series.index.min() + np.arange(n_groups)
            result = pd.Series(new_values, index=new_index)
            print(f"  高频聚合: {len(values)} 点 -> {n_groups} 点, 方法=aggregate_{aggregation}")
            print(f"  转换后序列: {ExogenousSeriesBuilder._series_str(result)}")
            log.record(
                operation="frequency_convert",
                indicator=indicator,
                period=f"{source_freq}->{target_freq}",
                method=f"aggregate_{aggregation}",
                details={"source_len": len(values), "target_len": n_groups},
            )
            return result

    @staticmethod
    def _expand_forecast_flags(
        flags: pd.Series,
        source_freq: str,
        target_freq: str,
    ) -> pd.Series:
        """forecast 标记随频率转换同步展开或聚合。"""
        if source_freq == target_freq:
            return flags

        ratios = {"annual": 1, "quarterly": 4, "monthly": 12}
        source_ratio = ratios.get(source_freq, 1)
        target_ratio = ratios.get(target_freq, 1)

        if target_ratio > source_ratio:
            repeats = target_ratio // source_ratio
            return pd.Series(
                np.repeat(flags.values.astype(bool), repeats),
                index=np.linspace(flags.index.min(), flags.index.max() + 1 - 1e-9, len(flags) * repeats),
            )
        else:
            group_size = source_ratio // target_ratio
            n_groups = len(flags) // group_size
            new_values = np.array([
                flags.iloc[i * group_size: (i + 1) * group_size].any()
                for i in range(n_groups)
            ])
            return pd.Series(
                new_values,
                index=flags.index.min() + np.arange(n_groups),
            )

    @staticmethod
    def _resample_flags(flags: List[bool], target_len: int) -> List[bool]:
        """把 forecast 标记列表对齐到 target_len，保留任意 True 标记。"""
        if len(flags) == target_len:
            return flags
        if len(flags) < target_len:
            # 扩展：每个原标记复制若干次
            repeats = target_len // len(flags)
            remainder = target_len % len(flags)
            result = []
            for i, flag in enumerate(flags):
                result.extend([flag] * (repeats + (1 if i < remainder else 0)))
            return result[:target_len]
        else:
            # 压缩：按块取 OR，只要块内有 True 就标 True
            result = []
            for i in range(target_len):
                start = i * len(flags) // target_len
                end = (i + 1) * len(flags) // target_len
                result.append(any(flags[start:end]))
            return result

    @staticmethod
    def _apply_normalization_and_direction(
        values: np.ndarray,
        direction: str,
        normalize: bool,
    ) -> np.ndarray:
        """应用归一化与方向反转。"""
        values = values.astype(float)

        if normalize:
            v_min, v_max = np.nanmin(values), np.nanmax(values)
            if v_max > v_min:
                values = (values - v_min) / (v_max - v_min)
            else:
                values = np.full_like(values, 0.5)

        if direction == "decrease":
            if ExogenousSeriesBuilder._is_trending_up(values):
                values = 1.0 - values
        elif direction == "increase":
            if ExogenousSeriesBuilder._is_trending_down(values):
                values = 1.0 - values

        return values

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
