from .simulator_imports import *

class CustomerSatisfactionSimSimulator:
    
    def __init__(self, container: DIContainer, government_officials: List[IOrdinaryGovernmentAgent], residents: Dict[int, IResident], config: Dict, loaded_plugins: Dict = None):

    
            self.logger = LogManager.get_logger('simulator', console_output=True)

    
            # 从插件或容器中获取模块实例
            self.map = self._resolve_instance('default_map', IMap, container, loaded_plugins)

    
            self.time = self._resolve_instance('default_time', ITime, container, loaded_plugins)

    
            self.population = self._resolve_instance('default_population', IPopulation, container, loaded_plugins)

    
            self.social_network = self._resolve_instance('default_social_network', ISocialNetwork, container, loaded_plugins)

    
            self.towns = self._resolve_instance('default_towns', ITowns, container, loaded_plugins)

    
            self.government = container.resolve(IGovernment)

    
            # 接受作为参数传入的对象
            self.government_officials = government_officials

    
            self.residents = residents

    
            self.config = config

    
            self.basic_living_cost = 8

    
            self.gdp = 0

    
            self.tax_income = 0

    
            self.average_satisfaction = None

    
            self.customer_loyalty = 0

    
            self.purchase_decisions = 0

    
            self.rebels_agents = {}

    
            # 依据配置决定是否记录经济类指标（如未配置则不记录）
            data_collection_cfg = (self.config or {}).get('data_collection', {}) if isinstance(self.config, dict) else {}
            metrics_list = set(data_collection_cfg.get('metrics', []) or [])
            self._track_gdp = 'gdp' in metrics_list
            self._track_unemployment = 'unemployment_rate' in metrics_list

            self.results = self.init_results()

    
            self.start_time = None

    
            self.end_time = None

    
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    
            pid = os.getpid()

    
            data_dir = SimulationContext.get_data_dir()

    
            SimulationContext.ensure_directories()

    
            self.result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")

    @staticmethod
    def _resolve_instance(plugin_name: str, interface_type, container: DIContainer, loaded_plugins: Dict = None):
        """从插件或容器中获取实例"""
        if loaded_plugins and plugin_name in loaded_plugins:
            return loaded_plugins[plugin_name]
        return container.resolve(interface_type)

    def init_results(self):
            # 仅在启用时包含经济类指标
            result = {
                "years": [],
                "population": [],
                "average_satisfaction": [],
                "customer_loyalty": [],
                "purchase_decisions": [],
            }
            if getattr(self, '_track_unemployment', False):
                result["unemployment_rate"] = []
            if getattr(self, '_track_gdp', False):
                result["gdp"] = []
            return result

    async def run(self):
        """主运行流程：初始化→主循环→结束"""
        self.start_time = datetime.now()
        
        # 主循环
        while not self.time.is_end():
            # 1. 打印时间步信息
            self.print_time_step()
            
            # 2. 更新系统状态（经济、气候、人口等）
            await self.update_state()
            
            # 3. 执行智能体行为（政府、叛军、居民等）
            await self.execute_actions()
            
            # 4. 收集本轮结果
            self.collect_results()
            
            # 5. 保存结果（增量追加模式）
            self.save_results(self.result_file, append=True)
            
            # 6. 推进时间
            self.time.step()
        
        self.end_time = datetime.now()
        self.display_total_simulation_time()
        
        # 可选：绘制网络分析图
        # self.social_network.plot_degree_distribution()
        # self.social_network.visualize()

    def print_time_step(self):


            print(Back.GREEN + f"年份:{self.time.current_time}" + Back.RESET)


            self.logger.info(f"年份:{self.time.current_time}")

    async def update_state(self):

            # 更新所有居民的收入（基于工作和表现）
            self.update_residents_income()

            # 仅在启用时计算 GDP
            self.gdp = self.calculate_gdp() if self._track_gdp else 0


            if self.government and self._track_gdp:


                self.tax_income = self.gdp * self.government.get_tax_rate()


                self.government.budget = round(self.government.budget + self.tax_income, 2)


                self.government.military_strength = self.calculate_total_government_military()


            self.average_satisfaction = self.calculate_average_satisfaction()


            self.customer_loyalty = self.calculate_customer_loyalty()


            self.population.update_birth_rate(self.average_satisfaction)


            if self.government and self._track_gdp:


                self.logger.info(f"GDP：{self.gdp}，税收收入：{self.tax_income}，政府预算：{self.government.budget}")

    async def execute_actions(self):


            self.purchase_decisions = 0


            new_count = int(self.population.birth_rate * self.population.get_population())


            new_residents = await generate_new_residents(


                count=new_count,


                map=self.map,


                residents=self.residents,


                social_network=self.social_network,


                resident_prompt_path=self.config["data"]["resident_prompt_path"],


                resident_actions_path=self.config["data"]["resident_actions_path"],


            )


            await self.integrate_new_residents(new_residents)


            self.population.birth(new_count)


            self.logger.info(f"新加入{new_count}名居民")


            government_decision = None


            if self.government and self.government_officials:


                government_config = {


                    'agents': self.government_officials,


                    'ordinary_type': OrdinaryGovernmentAgent,


                    'leader_type': HighRankingGovernmentAgent,


                }


                government_decision = await self.collect_group_decision('government', government_config)


            if government_decision:


                self.execute_government_decision(government_decision)


            tasks = []


            speech_tasks = []


            town_job_requests = defaultdict(list)


            for resident_name in list(self.residents.keys()):


                resident = self.residents[resident_name]


                # 先检查居民是否死亡，死亡则删除并跳过
                if resident.update_resident_status(self.basic_living_cost):
                    del self.residents[resident_name]
                    self.population.death()
                    continue


                tax_rate = self.government.get_tax_rate() if self.government else 0


                task = resident.decide_action_by_llm(tax_rate=tax_rate, basic_living_cost=self.basic_living_cost)
                tasks.append(task)


            if tasks:


                results = await asyncio.gather(*tasks)


                residents_list = list(self.residents.values())


                for i, result in enumerate(results):


                    if i >= len(residents_list):


                        break


                    resident = residents_list[i]


                    if isinstance(result, dict) and "town" in result:


                        town_job_requests[result["town"]].append(result)


                    elif isinstance(result, tuple) and len(result) == 4:


                        select, reason, speech, relation_type = result


                        # 处理居民的具体决策动作（购买统计已移至handle_resident_action）


                        self.handle_resident_action(resident, select, reason)


                        await resident.execute_decision(select, map=self.map)


                        if speech and speech.strip():


                            speech_tasks.append(asyncio.create_task(


                                self.social_network.spread_information(


                                    resident_id=resident.resident_id,


                                    message=speech,


                                    relation_type=relation_type,


                                    current_depth=0,


                                    max_depth=2


                                )


                            ))


                    elif isinstance(result, tuple) and len(result) == 2:


                        select, reason = result


                        # 处理居民的具体决策动作（购买统计已移至handle_resident_action）


                        self.handle_resident_action(resident, select, reason)


                        await resident.execute_decision(select, map=self.map)


                if speech_tasks:


                    await asyncio.gather(*speech_tasks)


            if town_job_requests:


                self.logger.info(f"开始处理 {len(town_job_requests)} 个城镇的求职请求")


                hiring_results = self.towns.process_town_job_requests(town_job_requests)


            else:


                self.logger.info("本轮无求职请求")


            current_year = self.time.current_time


            if current_year % random.randint(3, 5) == 0:


                self.social_network.update_network_edges()

    def collect_results(self):


            total_unemployment_rate = self.calculate_total_unemployment_rate() if self._track_unemployment else None


            if self.government:


                self.government.military_strength = self.calculate_total_government_military()


            self.customer_loyalty = self.calculate_customer_loyalty()


            purchase_decisions_count = getattr(self, 'purchase_decisions', 0)


            self.results["years"].append(self.time.current_time)


            if self._track_unemployment:
                self.results["unemployment_rate"].append(total_unemployment_rate)


            self.results["population"].append(self.population.get_population())


            self.results["average_satisfaction"].append(self.average_satisfaction)


            self.results["customer_loyalty"].append(self.customer_loyalty)


            self.results["purchase_decisions"].append(purchase_decisions_count)


            if self._track_gdp:
                self.results["gdp"].append(self.gdp)


            # 组合可用指标进行日志输出
            log_parts = [
                f"年份: {self.time.current_time}",
                f"人口数量: {self.population.get_population()}",
                f"平均满意度: {self.results['average_satisfaction'][-1]:.2f}",
                f"顾客忠诚度: {self.results['customer_loyalty'][-1]:.2f}%",
                f"购买决策数: {self.results['purchase_decisions'][-1]}",
            ]
            if self._track_unemployment:
                log_parts.insert(2, f"失业率: {self.results['unemployment_rate'][-1]:.2f}%")
            if self._track_gdp:
                log_parts.append(f"GDP: {self.results['gdp'][-1]:.2f}")
            self.logger.info(", ".join(log_parts))


            self.purchase_decisions = 0

    def save_results(self, filename=None, append=False):
        """保存结果到CSV文件"""
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突
            filename = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
        
        if append:
            last_row_data = {key: [value[-1]] for key, value in self.results.items() if value}
            df = pd.DataFrame(last_row_data)
        else:
            df = pd.DataFrame(self.results)
        
        if append and os.path.exists(filename):
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            df.to_csv(filename, index=False)
        
        if not append:
            self.logger.info(f"模拟结果已完整保存至 {filename}")

    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            self.logger.info(f"总模拟时间: {total_time}")
    
    # ==================== 群体决策方法 ====================
    
    async def collect_group_decision(self, group_type, config, max_rounds=2):

    
            """收集群体决策（政府或叛军）"""

    
            self.logger.info(f"开始收集 {group_type} 的决策")


    
            try:

    
                with open(f'config/{SimulationContext.get_simulation_type()}/simulation_config.yaml', 'r', encoding='utf-8') as f:

    
                    sim_config = yaml.safe_load(f)

    
                    group_decision_config = sim_config['simulation'].get('group_decision', {})

    
                    group_config = group_decision_config.get(group_type, {})

    
                    group_decision_enabled = group_config.get('enabled', True)

    
                    configured_max_rounds = group_config.get('max_rounds', 2)

    
            except Exception as e:

    
                self.logger.warning(f"读取群体决策配置失败，使用默认值：{e}")

    
                group_decision_enabled = True

    
                configured_max_rounds = max_rounds


    
            _, government_salary = self.calculate_total_salaries()

    
            group_param = government_salary


    
            leaders = [member for member in config['agents'].values()

    
                      if isinstance(member, config['leader_type'])]

    
            if not leaders:

    
                return None


    
            if not group_decision_enabled:

    
                leader = leaders[0]

    
                decision = await leader.make_decision(

    
                    summary="直接决策模式，无群体讨论。",

    
                    salary=group_param

    
                )

    
                return decision


    
            ordinary_members = [

    
                member for member in config['agents'].values()

    
                if isinstance(member, config['ordinary_type'])

    
                and not isinstance(member, InformationOfficer)

    
                and not isinstance(member, RebelsInformationOfficer)

    
            ]


    
            if not ordinary_members:

    
                return None


    
            shared_pool = list(config['agents'].values())[0].shared_pool

    
            await shared_pool.clear_discussions()


    
            first_round_tasks = [

    
                member.generate_opinion(salary=group_param)

    
                for member in random.sample(ordinary_members, len(ordinary_members))

    
            ]

    
            await asyncio.gather(*first_round_tasks)


    
            for round_num in range(2, configured_max_rounds + 1):

    
                self.logger.info(f"第{round_num}轮决策")

    
                round_tasks = [

    
                    member.generate_and_share_opinion(salary=group_param)

    
                    for member in random.sample(ordinary_members, len(ordinary_members))

    
                ]

    
                await asyncio.gather(*round_tasks)


    
            info_officers = [

    
                member for member in config['agents'].values()

    
                if isinstance(member, InformationOfficer)

    
                or isinstance(member, RebelsInformationOfficer)

    
            ]


    
            if info_officers and leaders:

    
                discussion_summary = await info_officers[0].summarize_discussions()

    
                if discussion_summary:

    
                    decision = await leaders[0].make_decision(discussion_summary, group_param)

    
                    return decision


    
            return None
    
    def execute_government_decision(self, decision):

    
            return self.execute_decision(decision, 'government')
    
    def extract_json_from_text(self, text):
        """从文本中提取JSON内容"""
        json_pattern = r'\{[^{}]*\}'
        matches = re.findall(json_pattern, text)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        return None
    
    def parse_decision(self, decision_text, max_retries=3):
        """解析决策内容，支持重试"""
        decision_text = decision_text.strip().removeprefix('```json').removesuffix('```')
        for attempt in range(max_retries):
            try:
                return json.loads(decision_text)
            except json.JSONDecodeError:
                extracted = self.extract_json_from_text(decision_text)
                if extracted:
                    return extracted
        return None
    
    def execute_decision(self, decision, group_type):

    
            _, salary = self.calculate_total_salaries()


    
            try:

    
                decision_data = self.parse_decision(decision)

    
                if not decision_data:

    
                    return False


    
                success = True


    
                if group_type == "government":

    
                    decision_keys = list(decision_data.keys())

    
                    random.shuffle(decision_keys)


    
                    for key in decision_keys:

    
                        if key == "tax_adjustment" and decision_data[key] is not None:

    
                            tax_change = decision_data[key]

    
                            if self.government:

    
                                new_rate = self.government.tax_rate + tax_change

    
                                self.government.adjust_tax_rate(new_rate)

    
                                self.logger.info(f"税率调整: {tax_change:+.2f}%, 新税率: {self.government.tax_rate:.2%}")


    
                        elif key == "service_quality_investment" and decision_data[key] is not None:

    
                            investment = decision_data[key]

    
                            if self.government and self.government.budget >= investment:

    
                                self.government.budget -= investment

    
                                # 服务质量投资提升居民满意度

    
                                satisfaction_boost = investment / 1000  # 简化计算，调整比例以适应0-100范围

    
                                for resident in self.residents.values():

    
                                    resident.satisfaction = min(100, resident.satisfaction + satisfaction_boost)

    
                                self.logger.info(f"服务质量投资: {investment}, 预算剩余: {self.government.budget:.2f}, 满意度提升: {satisfaction_boost:.2f}")

    
                            elif self.government:

    
                                self.logger.warning(f"预算不足，无法进行服务质量投资")

    
                                success = False


    
                return success


    
            except Exception as e:

    
                self.logger.error(f"执行决策时出错：{e}")

    
                return False
    
    def calculate_gdp(self):
        """计算GDP（所有非叛军居民的收入总和）"""
        if not self.residents:
            return 0.0
        total_income = sum(resident.income for resident in self.residents.values() if resident.job != "叛军")
        return total_income
    
    def calculate_average_satisfaction(self):
        """计算所有居民的平均满意度"""
        if not self.residents:
            self.logger.warning("没有居民，平均满意度为 0.0")
            return 0.0
        
        # 额外稳健性：在统计口径上将满意度限制在[0,100]
        bounded = (max(0, min(100, resident.satisfaction)) for resident in self.residents.values())
        total_satisfaction = sum(bounded)
        average_satisfaction = total_satisfaction / self.population.population
        self.logger.info(f"平均满意度: {average_satisfaction:.2f}")
        return average_satisfaction
    
    def calculate_total_unemployment_rate(self):
        """计算所有城镇的平均失业率"""
        total_employed = 0
        total_residents = 0
        
        for town_name, town_data in self.towns.towns.items():
            job_market = town_data['job_market']
            if job_market:
                town_employed = sum(len(info["employed"]) for job, info in job_market.jobs_info.items() if job != "叛军")
                total_employed += town_employed
                total_residents += len(town_data['residents'])
        
        if total_residents == 0:
            return 0.0
        self.logger.info(f"总体就业率: {total_employed} / {total_residents} = {total_employed / total_residents:.2f}")
        unemployment_rate = (1.0 - (total_employed / total_residents)) * 100
        return unemployment_rate
    
    def calculate_total_government_military(self):
        """计算政府军总数"""
        total_military = 0
        for town_name, town_data in self.towns.towns.items():
            job_market = town_data['job_market']
            if job_market:
                total_military += len(job_market.jobs_info.get("官员及士兵", {}).get("employed", []))
        return total_military
    
    def calculate_total_salaries(self):

    
            total_salary = 0


    
            for town_name, town_data in self.towns.towns.items():

    
                if town_data.get('job_market'):

    
                    for job, info in town_data['job_market'].jobs_info.items():

    
                        salary = info.get("salary", 0) * len(info.get("employed", []))

    
                        total_salary += salary


    
            return 0, total_salary
    
    def get_job_total_count(self):
        """获取除了叛军外的所有职业的岗位总数"""
        total_count = 0
        for town_name, town_data in self.towns.towns.items():
            job_market = town_data['job_market']
            if job_market:
                for job, info in job_market.jobs_info.items():
                    if job != "叛军":
                        total_count += info.get("quota", 0)
        return total_count
    
    def get_basic_living_cost(self):
        """获取当前基本生活所需值"""
        return self.basic_living_cost
    
    def adjust_basic_living_cost(self, adjustment):
        """调整基本生活所需值"""
        self.basic_living_cost = max(500, self.basic_living_cost + adjustment)
        self.logger.info(f"基本生活所需值调整为: {self.basic_living_cost}")
        return self.basic_living_cost
    
    async def integrate_new_residents(self, new_residents):
        """整合新居民到系统"""
        if not new_residents:
            return
        
        self.residents.update(new_residents)
        self.logger.info(f"{len(new_residents)} 名新居民已出生")
        
        self.towns.initialize_resident_groups(new_residents)
        self.logger.info("新居民已加入各自城镇")
        
        if new_residents:
            self.social_network.add_new_residents(new_residents)
            self.logger.info(f"{len(new_residents)} 名新居民已加入社交网络")
    
    def summarize_time_step_results(self):
        """总结当前时间步的各项指标变化"""
        current_idx = len(self.results["years"]) - 1
        if current_idx <= 0:
            return {}
        
        changes = {
            "人口变化率": self.calculate_change_rate("population", current_idx),
            "平均满意度变化": self.calculate_change_rate("average_satisfaction", current_idx),
            "顾客忠诚度变化": self.calculate_change_rate("customer_loyalty", current_idx),
            "购买决策数": self.results["purchase_decisions"][current_idx],
        }
        if self._track_gdp and "gdp" in self.results:
            changes["GDP变化率"] = self.calculate_change_rate("gdp", current_idx)
        if self._track_unemployment and "unemployment_rate" in self.results:
            changes["失业率变化"] = self.calculate_change_rate("unemployment_rate", current_idx)
        return changes
    
    def calculate_change_rate(self, metric, current_idx):
        """计算指定指标的变化率"""
        current = self.results[metric][current_idx]
        previous = self.results[metric][current_idx-1]
        if previous == 0:
            return 0 if current == 0 else 1
        return (current - previous) / previous
    
    async def store_decision_memory(self, group_type, decision, changes_summary):
        """存储决策记忆到智能体"""
        if group_type == 'government':
            memory_content = (
                f"时间: {self.time.current_time}"
                f"决策内容: {decision}"
                f"执行结果:"
                f"- GDP变化率: {'+' if changes_summary.get('GDP变化率', 0) > 0 else ''}{changes_summary.get('GDP变化率', 0):.2%}"
                f"- 平均满意度变化: {'+' if changes_summary.get('平均满意度变化', 0) > 0 else ''}{changes_summary.get('平均满意度变化', 0):.2%}"
                f"- 顾客忠诚度变化: {'+' if changes_summary.get('顾客忠诚度变化', 0) > 0 else ''}{changes_summary.get('顾客忠诚度变化', 0):.2%}"
                f"- 失业率变化: {'+' if changes_summary.get('失业率变化', 0) > 0 else ''}{changes_summary.get('失业率变化', 0):.2%}"
                f"- 购买决策数: {changes_summary.get('购买决策数', 0)}"
            )
            for official in self.government_officials.values():
                await official.store_memory(memory_content)
        
        # 注意：本模拟不涉及叛军，移除相关代码

    def handle_resident_action(self, resident, select, reason):


            """处理居民的具体决策动作，更新居民状态"""


            try:


                # 转换select为字符串以确保类型一致


                select = str(select)


                self.logger.info(f"处理居民 {resident.resident_id} 的决策动作：选择={select}，原因={reason[:50] if reason else 'N/A'}...")


                if select == "1":  # 购买决策


                    # 购买行为：需同时满足收入条件和满意度条件


                    if resident.income > self.basic_living_cost:


                        # 满意度影响购买意愿：满意度<40不购买，40-60低概率购买，>60正常购买


                        if resident.satisfaction < 40:


                            # 满意度太低，拒绝购买


                            resident.satisfaction = max(0, resident.satisfaction - 3)


                            self.logger.info(f"居民 {resident.resident_id} 满意度过低({resident.satisfaction:.1f})拒绝购买，满意度下降 3")


                        elif resident.satisfaction < 60:
                            # 满意度一般，30%概率购买
                            if random.random() < 0.3:
                                purchase_amount = min(resident.income * 0.1, 500)  # 低满意度时少量购买
                                satisfaction_boost = random.uniform(2, 5)
                                resident.satisfaction = min(100, resident.satisfaction + satisfaction_boost)
                                self.purchase_decisions += 1  # 成功购买，计数
                                self.logger.info(f"居民 {resident.resident_id} 犹豫后购买，花费 {purchase_amount:.2f}，满意度提升 {satisfaction_boost:.2f}")


                            else:
                                resident.satisfaction = max(0, resident.satisfaction - 2)
                                self.logger.info(f"居民 {resident.resident_id} 满意度一般({resident.satisfaction:.1f})放弃购买，满意度下降 2")


                        else:
                            # 满意度高，正常购买
                            purchase_amount = min(resident.income * 0.2, 1000)  # 花费20%收入或最多1000
                            satisfaction_boost = random.uniform(3, 10)
                            resident.satisfaction = min(100, resident.satisfaction + satisfaction_boost)
                            self.purchase_decisions += 1  # 成功购买，计数
                            self.logger.info(f"居民 {resident.resident_id} 购买商品，花费 {purchase_amount:.2f}，满意度提升 {satisfaction_boost:.2f}")


                    else:
                        # 收入不足，满意度下降
                        resident.satisfaction = max(0, resident.satisfaction - 5)
                        self.logger.info(f"居民 {resident.resident_id} 收入不足无法购买，满意度下降 5")


                elif select == "2":  # 提供反馈


                    # 提供反馈：根据满意度调整，积极反馈提升满意度，消极反馈降低满意度


                    if resident.satisfaction >= 60:


                        # 高满意度给予积极反馈，进一步提升


                        satisfaction_change = random.uniform(2, 5)


                        resident.satisfaction = min(100, resident.satisfaction + satisfaction_change)


                        self.logger.info(f"居民 {resident.resident_id} 提供积极反馈，满意度提升 {satisfaction_change:.2f}")


                    else:


                        # 低满意度给予消极反馈，但表达后会稍微缓解


                        satisfaction_change = random.uniform(1, 3)


                        resident.satisfaction = min(100, resident.satisfaction + satisfaction_change)


                        self.logger.info(f"居民 {resident.resident_id} 提供消极反馈，表达后满意度稍微提升 {satisfaction_change:.2f}")


                elif select == "3":  # 保持观望


                    # 观望：满意度缓慢自然变化


                    if resident.income >= self.basic_living_cost * 1.5:


                        # 收入较高，满意度缓慢提升


                        satisfaction_change = random.uniform(1, 3)


                        resident.satisfaction = min(100, resident.satisfaction + satisfaction_change)


                        self.logger.info(f"居民 {resident.resident_id} 保持观望，收入良好，满意度缓慢提升 {satisfaction_change:.2f}")


                    elif resident.income < self.basic_living_cost:


                        # 收入不足，满意度下降


                        satisfaction_change = random.uniform(2, 5)


                        resident.satisfaction = max(0, resident.satisfaction - satisfaction_change)


                        self.logger.info(f"居民 {resident.resident_id} 保持观望，但收入不足，满意度下降 {satisfaction_change:.2f}")


                    else:


                        # 收入中等，满意度基本稳定，微小波动


                        satisfaction_change = random.uniform(-1, 1)


                        resident.satisfaction = max(0, min(100, resident.satisfaction + satisfaction_change))


            except Exception as e:


                self.logger.error(f"处理居民 {resident.resident_id} 的决策时出错：{e}")

    def update_residents_income(self):
        """更新所有居民的收入，基于工作和满意度"""
        for resident in self.residents.values():
            if resident.employed and resident.job and resident.job != "叛军":
                # 有工作的居民，收入会根据满意度有小幅波动
                base_income = resident.income if resident.income > 0 else 1000
                
                # 根据满意度调整收入（满意度高的居民工作表现更好）
                if resident.satisfaction >= 80:
                    income_multiplier = random.uniform(1.05, 1.15)  # 5-15%提升
                elif resident.satisfaction >= 60:
                    income_multiplier = random.uniform(1.0, 1.05)  # 0-5%提升
                elif resident.satisfaction >= 40:
                    income_multiplier = random.uniform(0.95, 1.0)  # 0-5%下降
                else:
                    income_multiplier = random.uniform(0.85, 0.95)  # 5-15%下降
                
                # 添加随机波动
                random_factor = random.uniform(0.95, 1.05)
                new_income = base_income * income_multiplier * random_factor
                
                # 确保收入不会低于基本生活成本的50%
                resident.income = max(self.basic_living_cost * 0.5, new_income)
            else:
                # 失业居民收入为0或极低
                resident.income = 0


    def calculate_customer_loyalty(self):


            """计算顾客忠诚度"""


            if not self.residents:


                return 0.0


            # 忠诚度基于满意度：满意度>=70为忠诚客户


            loyal_customers = sum(


                1 for resident in self.residents.values()


                if resident.satisfaction >= 70


            )


            loyalty_rate = loyal_customers / len(self.residents) if self.residents else 0.0


            return loyalty_rate * 100  # 返回百分比


    async def spread_speech_in_network(self, resident_id, speech, relation_type):
            """在社交网络中传播言论"""
            if not speech or speech.strip() == "":
                return

            await self.social_network.spread_information(
                resident_id=resident_id,
                message=speech,
                relation_type=relation_type,
                current_depth=0,
                max_depth=2
            )
