from .simulator_imports import *
from .base_simulator import BaseSimulator

class YourSimulator(BaseSimulator):
    # BaseSimulator 已提供的通用方法（可直接调用，无需在子类重复实现）：
    #   run() / _print_time_step() — 主循环及时间步打印钩子
    #   collect_results()        — 基础结果收集（years/population/unemployment_rate/gdp）
    #   save_results(filename)   — csv.DictWriter 追加保存
    #   integrate_new_residents(new_residents) — 接入居民并同步到 towns/social_network
    #     ⚠️ 若覆写本方法，必须调用 super().integrate_new_residents()。
    #   _get_population_count()  — 兼容多种 population 插件的人口计数
    #   _calculate_gdp_growth_rate() — 基于 results["gdp"] 计算增长率
    #   _refresh_influence_observables(ctx) — 刷新 influences 覆盖的指标
    #   _sum_resident_attr(attr, default)   — 对所有居民的某属性求和
    #   _avg_resident_attr(attr, default)   — 对所有居民的某属性求平均
    #   _stat_residents(attr, stat, role, default) — 按角色统计居民属性（sum/avg/min/max/count）
    #   _aggregate_over_towns(extractor)    — 遍历 towns，按 extractor 提取数据聚合
    #   _query_job_market(query_fn)         — 遍历所有城镇 job_market 查询
    #   _count_employed_by_job(job_type)    — 按职业统计就业人数
    #   _sum_salary_by_job(job_type)        — 按职业统计总收入
    #   _get_town_stats(extractor)          — 按城镇提取统计信息
    #   _orchestrate_group_decision(...)    — 群体决策框架（政府/叛军/委员会）
    #   extract_json_from_text(text)        — 从文本提取 JSON
    #   parse_decision(text, max_retries)   — 解析决策文本
    #   calculate_change_rate(metric, idx)  — 计算指标环比变化率
    #   display_total_simulation_time()     — 显示总模拟时间
    # 如需扩展 collect_results，请先调用 super().collect_results()，再 append 自定义字段。

    def __init__(self, plugin_registry: Any, residents: Dict[int, IResident], config: Dict, influence_manager=None, group_agents=None, **_unused):
        # 必须显式接收并透传 group_agents，否则 government/rebels 等插件群体成员会被 **_unused 吞掉。
        # 详见 docs/ai_group_agent_integration_guide.md。
        super().__init__(plugin_registry, residents, config, influence_manager, group_agents=group_agents)

        # 可按设计文档扩展额外模块
        # self.government = require_module(self.plugin_registry, "government")
        # self.job_market = require_module(self.plugin_registry, "job_market")

        self.results = self.init_results()

        # 缓存 agent_profile，供增量生成新居民时使用
        data_cfg = config.get("data") or {}
        self._agent_profile_path = data_cfg.get("agent_profile_path")
        self._config_dir = os.path.dirname(self._agent_profile_path) if self._agent_profile_path else None
        self._agent_profile = None
        if self._agent_profile_path and os.path.exists(self._agent_profile_path):
            try:
                with open(self._agent_profile_path, "r", encoding="utf-8") as f:
                    self._agent_profile = yaml.safe_load(f) or {}
            except Exception as e:
                self.logger.warning(f"加载 agent_profile 失败: {e}")

        # 示例：如需在初始化时计算某些业务指标，可在此赋值
        # self.average_satisfaction = self._avg_resident_attr("satisfaction", 0.0)
        # self.consumer_avg_income = self._stat_residents("income", stat="avg", role="consumer")

    def init_results(self):
        """初始化结果结构。

        此方法必须返回一个字典，其中包含所有可能出现在最终 CSV 文件中的列名作为键，
        以及空列表作为对应的值。即使某些列在模拟过程中可能不会在每个时间步都有数据，
        也必须在此处声明，以确保 CSV 文件的头部完整且数据长度一致。

        示例：
        如果您的模拟器会收集 GDP、人口、以及按角色（如消费者、企业）分组的平均满意度，
        那么所有这些字段都应该在此处声明。
        """
        return {
            "years": [],
            "population": [],
            # 示例：如果您的模拟器需要以下指标，请取消注释并自行在 collect_results() 中收集
            # "gdp": [],
            # "unemployment_rate": [],
            # "average_satisfaction": [],
            # "custom_metric": [],
            # "government_policy_strength": [],
        }

    async def update_state(self):
        """更新每轮的基础统计值。

        当前模板不接入额外影响函数，只保留最基础的状态刷新。
        后续如果要加气候、经济或政策系统，可以从这里继续扩展。
        """
        self.gdp = self.calculate_gdp()

        # 示例：如需每轮更新自定义业务指标，可使用通用统计方法
        # self.average_satisfaction = self._avg_resident_attr("satisfaction", 0.0)
        # self.total_consumption = self._stat_residents("consumption_expenditure", stat="sum")
        # self.enterprise_avg_output = self._stat_residents("output_manufacturing", stat="avg", role="enterprise")

        if self.influence_manager is None:
            return

        simulator_state = {
            "time": self.time,
            "map": self.map,
            "population": self.population,
            "social_network": self.social_network,
            "towns": self.towns,
            "residents": self.residents,
            "gdp": self.gdp,
            "basic_living_cost": self.basic_living_cost,
            "gdp_growth_rate": self._calculate_gdp_growth_rate(),
        }

        # 注入外生变量（若配置了 exogenous_data_path）：按预编排序列逐步驱动下游因果链，
        # 影响函数通过 context.exogenous.<key> 读取。未配置时不做任何修改。
        current_step = self.time.get_elapsed_time_steps() if hasattr(self.time, "get_elapsed_time_steps") else 0
        self._inject_exogenous_variables(simulator_state, current_step)

        if hasattr(self.influence_manager, "apply_all_influences"):
            # target_root=self 必传：influences.yaml 中以 simulator 标量属性为 target
            # 的影响函数（如 gdp、house_price_index）需要写回到 simulator 实例上，
            # 漏传会导致影响结果无法写回，指标恒定不变。
            global_context = self.influence_manager.apply_all_influences(
                simulator_state, target_root=self
            )
        elif hasattr(self.influence_manager, "build_global_context"):
            global_context = self.influence_manager.build_global_context(simulator_state)
        else:
            global_context = simulator_state

        self._refresh_influence_observables(global_context)

    def _get_influence_observables(self):
        """返回 influences 执行后需要重新刷新的指标名集合。
        新增指标时只需在此添加条目，无需修改 update_state 主体逻辑。

        示例：
            return {
                "gdp": self.calculate_gdp,
                # "average_satisfaction": lambda: self._avg_resident_attr("satisfaction", 0.0),
                # "consumer_avg_income": lambda: self._stat_residents("income", stat="avg", role="consumer"),
            }
        """
        return {
            "gdp": self.calculate_gdp,
        }

    # 示例：如需扩展结果收集，可覆写 collect_results()
    # def collect_results(self):
    #     super().collect_results()
    #     self.results.setdefault("gdp", []).append(self.calculate_gdp())
    #     self.results.setdefault("unemployment_rate", []).append(self.calculate_total_unemployment_rate())
    #     self.results.setdefault("average_satisfaction", []).append(self._avg_resident_attr("satisfaction", 0.0))
    #     self.results.setdefault("consumer_avg_income", []).append(
    #         self._stat_residents("income", stat="avg", role="consumer")
    #     )

    async def execute_actions(self):
        """执行居民层面的行为逻辑。

        当前模板只做两件事：
        1. 按出生率生成新居民；
        2. 让所有居民执行 LLM 决策，并处理返回的求职/发言结果。
        """
        sim_cfg = self.config.get("simulation") or {}
        data_cfg = self.config.get("data") or {}

        # 按出生率扩充人口。
        birth_rate = sim_cfg.get("birth_rate", getattr(self.population, "birth_rate", 0))
        current_population = self._get_population_count()
        new_count = max(0, int(birth_rate * current_population))

        if new_count > 0:
            # 复用现有生成器，避免在模板里重复实现居民构造逻辑。
            new_residents = await generate_new_agents(
                count=new_count,
                map=self.map,
                existing_agents=self.residents,
                agent_profile=self._agent_profile,
                config_dir=self._config_dir,
            )

            # 先通知 population 模块更新计数，再将新居民接入系统，
            # 避免 _get_population_count() 在同轮内重复计数。
            birth_fn = getattr(self.population, "birth", None)
            if callable(birth_fn):
                birth_fn(new_count)

            self.integrate_new_residents(new_residents)
            self.logger.info(f"新加入{new_count}名居民")

        # 居民决策并发执行。
        # 前提：integrate_new_residents 已将 model_backend 注入各居民（否则全返回 None）。
        tasks = []
        residents_list = list(self.residents.values())
        for resident in residents_list:
            tasks.append(
                resident.decide_action_by_llm(
                    basic_living_cost=self.basic_living_cost,
                )
            )

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        speech_tasks = []
        town_job_requests = defaultdict(list)

        # 统一处理居民返回结果，避免把业务逻辑散落到模板外。
        # - dict 且包含 town：视为求职请求
        # - 4 元组：视为带发言的决策
        # - 2 元组：视为普通决策
        for resident, result in zip(residents_list, results):
            if isinstance(result, Exception):
                self.logger.warning(f"居民 {resident.resident_id} 决策失败: {result}")
                continue

            if isinstance(result, dict) and "town" in result:
                town_job_requests[result["town"]].append(result)
                continue

            if isinstance(result, tuple) and len(result) == 4:
                select, _, speech, relation_type = result
                await resident.execute_decision(select)
                speech_tasks.append(
                    asyncio.create_task(
                        self.social_network.spread_speech_in_network(
                            resident.resident_id,
                            speech,
                            relation_type,
                        )
                    )
                )
                continue

            if isinstance(result, tuple) and len(result) == 2:
                select, _ = result
                await resident.execute_decision(select)

        if speech_tasks:
            await asyncio.gather(*speech_tasks)

        # 如果城镇模块提供求职处理接口，就把本轮请求交给它。
        if town_job_requests and hasattr(self.towns, "process_town_job_requests"):
            self.towns.process_town_job_requests(town_job_requests)

    def calculate_gdp(self):
        """最小版 GDP 统计：直接汇总所有居民收入。"""
        return self._sum_resident_attr("income", 0)

    def _extract_employed_for_unemployment(self, town_data):
        """嵌套提取器：从城镇数据中提取已就业人数（供失业率计算使用）。"""
        job_market = town_data.get("job_market")
        if job_market is None:
            return None
        jobs_info = getattr(job_market, "jobs_info", None)
        if not isinstance(jobs_info, dict):
            return None
        return sum(
            len(info.get("employed") or [])
            for info in jobs_info.values()
            if isinstance(info, dict)
        )

    def _extract_labor_for_unemployment(self, town_data):
        """嵌套提取器：从城镇数据中提取劳动力人口（供失业率计算使用）。"""
        residents = town_data.get("residents")
        return len(residents) if isinstance(residents, list) else None

    def calculate_total_unemployment_rate(self):
        """按城镇就业市场统计失业率。失业率 = 失业人口 / 劳动力人口 * 100。"""
        employed_list = self._aggregate_over_towns(self._extract_employed_for_unemployment)
        labor_list = self._aggregate_over_towns(self._extract_labor_for_unemployment)

        total_employed = sum(employed_list)
        total_labor_force = sum(labor_list)

        if total_labor_force <= 0:
            return 0.0

        return max(0.0, min(100.0, (1.0 - total_employed / total_labor_force) * 100))
