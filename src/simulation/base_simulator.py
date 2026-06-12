import asyncio
import csv
import json
import os
import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml
from colorama import Back
from src.utils.simulation_context import SimulationContext
from src.utils.logger import LogManager
from .plugin_access import require_module


class BaseSimulator:
    """多智能体模拟器抽象基类。

    固化通用骨架逻辑（主循环、结果保存、人口统计、居民接入等），
    子类只需覆写业务相关方法（update_state、execute_actions、calculate_xxx）。
    """

    def __init__(self, plugin_registry: Any, residents: Dict[int, Any], config: Dict, influence_manager=None, **_unused):
        self.logger = LogManager.get_logger("simulator", console_output=True)
        self.plugin_registry = plugin_registry
        self.residents = residents or {}
        self.config = config or {}
        self.basic_living_cost = (self.config.get("simulation") or {}).get("basic_living_cost", 8)
        self.results: Dict[str, List] = {}
        self.start_time = None
        self.end_time = None
        self.influence_manager = influence_manager
        self._last_saved_count = 0
        self._csv_fieldnames: Optional[List[str]] = None

        # 通用核心模块（所有决策型模拟器均依赖）
        self.map = require_module(self.plugin_registry, "map")
        self.time = require_module(self.plugin_registry, "time")
        self.population = require_module(self.plugin_registry, "population")
        self.social_network = require_module(self.plugin_registry, "social_network")
        self.towns = require_module(self.plugin_registry, "towns")

        # 核心模块加载完成后，立即将初始居民接入城镇与社交网络。
        # 这对 lightweight 居民尤为重要：ResidentGroup 会为其补齐 model_backend、
        # memory、token_counter 等共享资源，否则后续决策会因 model_backend 为 None 被跳过。
        self.integrate_new_residents(self.residents, is_initial=True)

    # ------------------------------------------------------------------
    # 通用计算方法（子类可直接复用，也可覆写）
    # ------------------------------------------------------------------
    def _sum_resident_attr(self, attr: str, default=0) -> float:
        """对所有居民的指定属性求和。"""
        if not self.residents:
            return 0.0
        return sum(getattr(r, attr, default) for r in self.residents.values())

    def _avg_resident_attr(self, attr: str, default=0.0) -> float:
        """对所有居民的指定属性求平均。"""
        if not self.residents:
            return default
        total = sum(getattr(r, attr, default) for r in self.residents.values())
        return total / len(self.residents)

    def _filter_residents(self, role: Optional[str] = None):
        """按角色筛选居民。role=None 时返回所有居民。"""
        if not self.residents:
            return []
        if role is None:
            return list(self.residents.values())
        return [
            r for r in self.residents.values()
            if getattr(r, 'profile', {}).get('role', 'consumer') == role
        ]

    def _stat_residents(
        self,
        attr: str,
        stat: str = "avg",
        role: Optional[str] = None,
        default: Any = 0.0,
    ) -> Any:
        """对指定角色居民的某属性进行统计。

        Args:
            attr: 居民属性名（支持通过 __getattr__ 代理到 profile）。
            stat: 统计方式 — "sum"(求和)、"avg"(平均)、"min"(最小)、"max"(最大)、"count"(计数)。
            role: 角色筛选，None 表示所有居民。
            default: 属性缺失时的默认值。

        Returns:
            统计结果（sum/avg/min/max 返回 float，count 返回 int）。
        """
        group = self._filter_residents(role)
        if not group:
            return 0 if stat == "count" else default

        if stat == "count":
            return len(group)

        values = [getattr(r, attr, default) for r in group]
        if not values:
            return default

        if stat == "sum":
            return sum(values)
        if stat == "avg":
            return sum(values) / len(values)
        if stat == "min":
            return min(values)
        if stat == "max":
            return max(values)

        raise ValueError(f"不支持的统计方式: {stat}，支持 sum/avg/min/max/count")

    def _get_population_count(self) -> int:
        """兼容不同 population 插件实现的取值方式。"""
        getter = getattr(self.population, "get_population", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                pass
        pop_val = getattr(self.population, "population", None)
        if isinstance(pop_val, int):
            return pop_val
        return len(self.residents)

    def _calculate_gdp_growth_rate(self) -> float:
        """基于已收集的 gdp 序列计算增长率。"""
        if len(self.results.get("gdp", [])) < 2:
            return 0.0
        current = self.results["gdp"][-1]
        previous = self.results["gdp"][-2]
        if previous == 0:
            return 0.0 if current == 0 else 1.0
        return (current - previous) / previous

    def _aggregate_over_towns(self, extractor):
        """遍历所有城镇，按 extractor 提取数据并收集到列表中。

        Args:
            extractor: 接收 town_data(dict)，返回提取值或 None（None 被忽略）。

        Returns:
            list: 所有非 None 提取值的列表。
        """
        towns_dict = getattr(self.towns, "towns", None)
        if not isinstance(towns_dict, dict):
            return []
        results = []
        for town_data in towns_dict.values():
            if not isinstance(town_data, dict):
                continue
            val = extractor(town_data)
            if val is not None:
                results.append(val)
        return results

    def _query_job_market(self, query_fn) -> list:
        """遍历所有城镇的 job_market，执行 query_fn 并收集非 None 结果。

        Args:
            query_fn: 接收 (town_name, town_data, job_market)，返回提取值或 None。

        Returns:
            list: 所有非 None 结果的列表。
        """
        towns_dict = getattr(self.towns, "towns", None)
        if not isinstance(towns_dict, dict):
            return []
        results = []
        for town_name, town_data in towns_dict.items():
            if not isinstance(town_data, dict):
                continue
            job_market = town_data.get("job_market")
            if job_market is None:
                continue
            val = query_fn(town_name, town_data, job_market)
            if val is not None:
                results.append(val)
        return results

    def _count_employed_by_job(self, job_type: str) -> int:
        """统计所有城镇中指定职业的就业人数。"""
        def _extract(town_name, town_data, job_market):
            info = getattr(job_market, "jobs_info", {}).get(job_type, {})
            return len(info.get("employed", [])) if isinstance(info, dict) else 0
        return sum(self._query_job_market(_extract))

    def _sum_salary_by_job(self, job_type: str = None) -> float:
        """统计所有城镇中指定职业的总收入。job_type=None 时统计所有职业。"""
        def _extract(town_name, town_data, job_market):
            total = 0.0
            jobs_info = getattr(job_market, "jobs_info", {})
            if not isinstance(jobs_info, dict):
                return None
            for job, info in jobs_info.items():
                if job_type is not None and job != job_type:
                    continue
                if isinstance(info, dict):
                    total += info.get("salary", 0) * len(info.get("employed", []))
            return total
        return sum(self._query_job_market(_extract))

    def _get_town_stats(self, extractor) -> list:
        """遍历所有城镇，按 extractor(town_name, town_data) 提取统计信息。

        Args:
            extractor: 接收 (town_name, town_data)，返回提取值或 None（None 被忽略）。

        Returns:
            list: 所有非 None 提取值的列表。
        """
        towns_dict = getattr(self.towns, "towns", None)
        if not isinstance(towns_dict, dict):
            return []
        results = []
        for town_name, town_data in towns_dict.items():
            if not isinstance(town_data, dict):
                continue
            val = extractor(town_name, town_data)
            if val is not None:
                results.append(val)
        return results

    # ------------------------------------------------------------------
    # 居民接入（通用）
    # ------------------------------------------------------------------
    def integrate_new_residents(
        self, new_residents: Dict[int, Any], *, is_initial: bool = False
    ) -> None:
        """把新居民接入系统，并同步到城镇和社交网络。

        Args:
            new_residents: 待接入的居民字典。
            is_initial: 是否为初始居民（区别于模拟过程中出生的新居民），
                        仅影响日志文案。
        """
        if not new_residents:
            return
        self.residents.update(new_residents)
        label = "初始居民" if is_initial else "新居民"
        self.logger.info(f"{len(new_residents)} 名{label}已接入")
        if self.towns and hasattr(self.towns, "initialize_resident_groups"):
            try:
                self.towns.initialize_resident_groups(new_residents)
                self.logger.info(f"{label}已加入各自城镇")
            except Exception as e:
                self.logger.error(f"{label}加入城镇失败: {e}")
        if self.social_network and hasattr(self.social_network, "add_new_residents"):
            try:
                self.social_network.add_new_residents(new_residents)
                self.logger.info(f"{len(new_residents)} 名{label}已加入社交网络")
            except Exception as e:
                self.logger.error(f"{label}加入社交网络失败: {e}")

    # ------------------------------------------------------------------
    # 群体决策框架（通用）
    # ------------------------------------------------------------------
    async def _orchestrate_group_decision(
        self,
        agents: Dict[str, Any],
        ordinary_type: type,
        leader_type: type,
        info_officer_types: tuple,
        group_param: Any,
        max_rounds: int = 2,
        group_type: str = "group",
        use_towns_stats: bool = False,
    ) -> Optional[str]:
        """通用群体决策收集框架。

        流程：
        1. 读取配置判断是否启用群体决策及最大轮数
        2. 从 agents 中分离 leader / ordinary / info_officer
        3. 多轮异步发表意见
        4. 信息整理官总结讨论
        5. leader 作出最终决策

        Args:
            agents: 群体成员字典
            ordinary_type: 普通成员类型
            leader_type: 领导类型
            info_officer_types: 信息整理官类型元组
            group_param: 群体决策参数（政府用 salary，叛军用 towns_stats）
            max_rounds: 默认最大讨论轮数
            group_type: 群体标识（用于日志和配置读取）
            use_towns_stats: leader 决策是否使用 towns_stats 参数（叛军为 True）

        Returns:
            leader 的决策文本，或 None（未成功）
        """
        self.logger.info(f"开始收集 {group_type} 的决策")

        # 读取配置
        try:
            sim_type = SimulationContext.get_simulation_type()
            config_path = f"config/{sim_type}/simulation_config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                sim_config = yaml.safe_load(f)
            group_decision_config = sim_config.get("simulation", {}).get("group_decision", {})
            group_config = group_decision_config.get(group_type, {})
            group_decision_enabled = group_config.get("enabled", True)
            configured_max_rounds = group_config.get("max_rounds", max_rounds)
        except Exception as e:
            self.logger.warning(f"读取群体决策配置失败，使用默认值：{e}")
            group_decision_enabled = True
            configured_max_rounds = max_rounds

        # 找到 leader
        leaders = [m for m in agents.values() if isinstance(m, leader_type)]
        if not leaders:
            return None

        # 直接决策模式（不启用群体讨论）
        if not group_decision_enabled:
            leader = leaders[0]
            if use_towns_stats:
                return await leader.make_decision(summary="直接决策模式，无群体讨论。", towns_stats=group_param)
            return await leader.make_decision(summary="直接决策模式，无群体讨论。", salary=group_param)

        # 分离普通成员和信息整理官
        ordinary_members = [
            m for m in agents.values()
            if isinstance(m, ordinary_type) and not isinstance(m, info_officer_types)
        ]
        info_officers = [m for m in agents.values() if isinstance(m, info_officer_types)]

        if not ordinary_members:
            return None

        # 获取共享信息池并清空
        shared_pool = next(iter(agents.values())).shared_pool
        if hasattr(shared_pool, "clear_discussions"):
            await shared_pool.clear_discussions()

        # 第一轮：所有成员异步发表初始意见
        if use_towns_stats:
            first_round_tasks = [
                member.generate_opinion(towns_stats=group_param)
                for member in random.sample(ordinary_members, len(ordinary_members))
            ]
        else:
            first_round_tasks = [
                member.generate_opinion(salary=group_param)
                for member in random.sample(ordinary_members, len(ordinary_members))
            ]
        await asyncio.gather(*first_round_tasks)

        # 后续轮次
        for round_num in range(2, configured_max_rounds + 1):
            self.logger.info(f"第{round_num}轮决策")
            round_tasks = [
                member.generate_and_share_opinion(salary=group_param)
                for member in random.sample(ordinary_members, len(ordinary_members))
            ]
            await asyncio.gather(*round_tasks)

        # 信息整理官总结，leader 决策
        if info_officers and hasattr(info_officers[0], "summarize_discussions"):
            discussion_summary = await info_officers[0].summarize_discussions()
            if discussion_summary:
                if use_towns_stats:
                    return await leaders[0].make_decision(discussion_summary, group_param)
                return await leaders[0].make_decision(discussion_summary, group_param)

        return None

    # ------------------------------------------------------------------
    # 影响系统刷新（通用逻辑，子类通过 _get_influence_observables 声明指标）
    # ------------------------------------------------------------------
    def _refresh_influence_observables(self, global_context: Dict) -> None:
        """统一刷新所有受 influences 影响的派生指标。
        优先级：context 直接覆盖 > 保持当前值。
        注意：基础指标已在 update_state 中计算，此处仅处理 influences 覆盖。
        """
        observables = self._get_influence_observables()
        for attr_name in observables.keys():
            if attr_name in global_context:
                new_value = global_context[attr_name]
                setattr(self, attr_name, new_value)

    def _get_influence_observables(self):
        """子类覆写以声明需要刷新的指标名集合。

        返回字典，键为属性名，值为对应的计算方法（仅供文档/覆写参考，
        基类 _refresh_influence_observables 中不再主动调用）。
        """
        return {}

    # ------------------------------------------------------------------
    # 决策解析工具（通用）
    # ------------------------------------------------------------------
    @staticmethod
    def extract_json_from_text(text: str) -> Optional[dict]:
        """从文本中提取 JSON 内容，支持嵌套大括号匹配。"""
        json_pattern = r"\{[^{}]*\}"
        matches = re.findall(json_pattern, text)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def parse_decision(decision_text: str, max_retries: int = 3) -> Optional[dict]:
        """解析决策内容（支持 markdown JSON 代码块），失败时重试。"""
        cleaned = decision_text.strip().removeprefix("```json").removesuffix("```")
        for _ in range(max_retries):
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                extracted = BaseSimulator.extract_json_from_text(cleaned)
                if extracted:
                    return extracted
        return None

    # ------------------------------------------------------------------
    # 主循环（完全固化，子类禁止覆写）
    # ------------------------------------------------------------------
    def _print_time_step(self) -> None:
        """打印当前时间步信息。子类可覆写以添加额外输出（如气候信息）。"""
        print(Back.GREEN + f"年份:{self.time.current_time}" + Back.RESET)
        self.logger.info(f"年份:{self.time.current_time}")

    async def run(self) -> None:
        """主运行流程：初始化 -> 循环 -> 收尾。"""
        self.start_time = datetime.now()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")

        while not self.time.is_end():
            self._print_time_step()
            await self.update_state()
            await self.execute_actions()
            self.collect_results()
            self.save_results(result_file)
            self.time.step()

        self.end_time = datetime.now()
        if self.start_time and self.end_time:
            self.logger.info(f"总模拟时间: {self.end_time - self.start_time}")

    # ------------------------------------------------------------------
    # 结果收集（基础字段，子类通过 super().collect_results() 扩展）
    # ------------------------------------------------------------------
    def collect_results(self) -> None:
        """收集本轮基础结果数据。

        此方法会直接修改 `self.results` 字典，不返回任何值。
        基类仅收集最通用的字段（years / population），避免把特定业务指标硬编码到所有模拟器中。
        子类覆写时，应先调用 `super().collect_results()`，再按需追加自定义字段。

        示例：
            def collect_results(self):
                super().collect_results()
                self.results.setdefault("gdp", []).append(self.calculate_gdp())
                self.results.setdefault("unemployment_rate", []).append(self.calculate_total_unemployment_rate())
        """
        self.results.setdefault("years", []).append(getattr(self.time, "current_time", None))
        self.results.setdefault("population", []).append(self._get_population_count())

    # ------------------------------------------------------------------
    # 结果保存
    # ------------------------------------------------------------------
    def save_results(self, filename=None) -> None:
        """保存结果。首次调用写入表头，后续默认追加新行。"""
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()
            filename = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")

        current_count = len(self.results.get("years", []))
        if current_count <= self._last_saved_count:
            return

        # 如果是第一次保存，或者 _csv_fieldnames 尚未初始化，则确定列名
        if self._csv_fieldnames is None:
            self._csv_fieldnames = sorted(list(self.results.keys()))

        new_rows = []
        for i in range(self._last_saved_count, current_count):
            row = {}
            for k in self._csv_fieldnames: # 使用固定的列名
                # 如果某个键在当前时间步没有数据，则填充 None
                row[k] = self.results[k][i] if i < len(self.results.get(k, [])) else None
            new_rows.append(row)

        file_exists = os.path.exists(filename)
        with open(filename, 'a' if file_exists else 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self._csv_fieldnames) # 使用固定的列名
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_rows)

        self._last_saved_count = current_count
        self.logger.info(f"模拟结果已保存至 {filename}")

    # ------------------------------------------------------------------
    # 子类必须覆写的方法
    # ------------------------------------------------------------------
    def init_results(self) -> Dict[str, List]:
        """初始化结果结构。子类必须实现。"""
        raise NotImplementedError

    async def update_state(self) -> None:
        """更新每轮状态。子类必须实现。"""
        raise NotImplementedError

    async def execute_actions(self) -> None:
        """执行居民行为。子类必须实现。"""
        raise NotImplementedError

    def calculate_gdp(self) -> float:
        """计算 GDP。子类必须实现。"""
        raise NotImplementedError

    def calculate_total_unemployment_rate(self) -> float:
        """计算失业率。子类可按需覆写，默认返回 0.0。"""
        return 0.0

    # ------------------------------------------------------------------
    # 通用分析工具
    # ------------------------------------------------------------------
    def calculate_change_rate(self, metric: str, current_idx: int) -> float:
        """计算指定指标在 current_idx 处的环比变化率。"""
        series = self.results.get(metric, [])
        if current_idx <= 0 or current_idx >= len(series):
            return 0.0
        current = series[current_idx]
        previous = series[current_idx - 1]
        if previous == 0:
            return 0.0 if current == 0 else 1.0
        return (current - previous) / previous

    def display_total_simulation_time(self) -> None:
        """显示总模拟时间。"""
        if self.start_time and self.end_time:
            self.logger.info(f"总模拟时间: {self.end_time - self.start_time}")
