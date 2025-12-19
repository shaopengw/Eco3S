from .simulator_imports import *

class ClimateMigrationSimSimulator:
    
    def __init__(self, **kwargs):

    
        self.map = kwargs.get('map')

    
        self.time = kwargs.get('time')

    
        self.population = kwargs.get('population')

    
        self.social_network = kwargs.get('social_network')

    
        self.residents = kwargs.get('residents')

    
        self.towns = kwargs.get('towns')

    
        self.config = kwargs.get('config')


    
        self.government = kwargs.get('government')

    
        self.government_officials = kwargs.get('government_officials')

    
        self.climate = kwargs.get('climate')


    
        self.basic_living_cost = 8

    
        self.gdp = 0

    
        self.tax_income = 0


    
        self.average_satisfaction = None


    
        self.results = self.init_results()

        # 初始化日志记录器
        self.logger = LogManager.get_logger('simulator_climate_migration', console_output=False)
    
        self.start_time = None

    
        self.end_time = None


    
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突

    
        data_dir = SimulationContext.get_data_dir()

    
        SimulationContext.ensure_directories()

    
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")

    def init_results(self):


        return {


            "years": [],


            "unemployment_rate": [],


            "migration_rate": [],


            "population": [],


            "government_budget": [],


            "average_satisfaction": [],


            "tax_rate": [],


            "gdp": [],


            "temperature": [],


            "extreme_events": [],


        }

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


            if self.climate:


                current_year = self.time.current_time


                start_year = self.time.start_time


                climate_impact = self.climate.get_current_impact(current_year, start_year)


                print(f"气候影响因子：{climate_impact}")

    async def update_state(self):


            self.gdp = self.calculate_gdp()


            if self.government:


                self.tax_income = self.gdp * self.government.get_tax_rate()


                self.government.budget = round(self.government.budget + self.tax_income, 2)


                self.government.military_strength = self.calculate_total_government_military()


            self.average_satisfaction = self.calculate_average_satisfaction()


            self.population.update_birth_rate(self.average_satisfaction)


            if self.government:


                print(f"GDP:{self.gdp},税收收入:{self.tax_income},政府预算:{self.government.budget}")


            if self.climate:


                current_year = self.time.current_time


                climate_impact_factor = self.climate.get_current_impact(current_year, self.time.start_time)


                for town_name in self.towns.towns:


                    self.adjust_town_satisfaction_by_climate(town_name, climate_impact_factor)


                self.map.decay_river_condition_naturally(climate_impact_factor)

    async def execute_actions(self):


            self.migration_count = 0


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


            town_job_requests = defaultdict(list)


            for resident_name in list(self.residents.keys()):


                resident = self.residents[resident_name]


                tax_rate = self.government.get_tax_rate() if self.government else 0


                climate_impact = 0


                if self.climate:


                    current_year = self.time.current_time


                    climate_impact = self.climate.get_current_impact(current_year, self.time.start_time)


                task = resident.decide_action_by_llm(tax_rate=tax_rate, basic_living_cost=self.basic_living_cost, climate_impact=climate_impact)


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


                    elif isinstance(result, tuple) and len(result) == 2:


                        select, reason = result


                        await resident.execute_decision(select, map=self.map)


                        if select == "2":


                            self.migration_count += 1


            if town_job_requests:


                self.towns.process_job_requests(town_job_requests)


            self.update_resident_status(self.basic_living_cost)


            current_year = self.time.current_time


            if current_year % random.randint(3, 5) == 0:


                self.social_network.update_network_edges()

    def collect_results(self):


            total_unemployment_rate = self.calculate_total_unemployment_rate()


            migration_rate = getattr(self, 'migration_count', 0) / self.population.get_population() * 100 if self.population.get_population() > 0 else 0


            if self.government:


                self.government.military_strength = self.calculate_total_government_military()


            current_year = self.time.current_time


            temperature = 0


            extreme_events = 0


            if self.climate:


                start_year = self.time.start_time


                climate_impact = self.climate.get_current_impact(current_year, start_year)


                temperature = climate_impact * 100


                extreme_events = 1 if abs(climate_impact) > self.climate.climate_impact_threshold else 0


            self.results["years"].append(self.time.current_time)


            self.results["unemployment_rate"].append(total_unemployment_rate)


            self.results["migration_rate"].append(migration_rate)


            self.results["population"].append(self.population.get_population())


            self.results["government_budget"].append(self.government.get_budget() if self.government else 0)


            self.results["average_satisfaction"].append(self.average_satisfaction)


            self.results["tax_rate"].append(self.government.get_tax_rate() if self.government else 0)


            self.results["gdp"].append(self.gdp)


            self.results["temperature"].append(temperature)


            self.results["extreme_events"].append(extreme_events)


            print(f"年份: {self.time.current_time}, "


                  f"人口数量: {self.population.get_population()}, "


                  f"失业率: {self.results['unemployment_rate'][-1]:.2f}%, "


                  f"迁移率: {self.results['migration_rate'][-1]:.2f}%, "


                  f"平均满意度: {self.results['average_satisfaction'][-1]:.2f}, "


                  f"税率: {self.results['tax_rate'][-1]:.2f}, "


                  f"GDP: {self.results['gdp'][-1]:.2f}, "


                  f"温度: {self.results['temperature'][-1]:.2f}°C, "


                  f"极端事件数: {self.results['extreme_events'][-1]}"


            )


            self.migration_count = 0

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
            print(f"模拟结果已保存至 {filename}")

    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")
    
    # ==================== 群体决策方法 ====================
    
    async def collect_group_decision(self, group_type, config, max_rounds=2):


    
                """收集群体决策（政府）"""


    
                print(f"开始收集 {group_type} 的决策")


    
                # 读取配置


    
                try:


    
                    with open(f'config/{SimulationContext.get_simulation_type()}/simulation_config.yaml', 'r', encoding='utf-8') as f:


    
                        sim_config = yaml.safe_load(f)


    
                        group_decision_config = sim_config['simulation'].get('group_decision', {})


    
                        group_config = group_decision_config.get(group_type, {})


    
                        group_decision_enabled = group_config.get('enabled', True)


    
                        configured_max_rounds = group_config.get('max_rounds', 2)


    
                except Exception as e:


    
                    print(f"读取群体决策配置失败，使用默认值：{e}")


    
                    group_decision_enabled = True


    
                    configured_max_rounds = max_rounds


    
                # 计算决策参数


    
                _, government_salary = self.calculate_total_salaries()


    
                group_param = government_salary


    
                # 获取领导者


    
                leaders = [member for member in config['agents'].values()


    
                          if isinstance(member, config['leader_type'])]


    
                if not leaders:


    
                    return None


    
                # 直接决策模式（不启用群体决策）


    
                if not group_decision_enabled:


    
                    leader = leaders[0]


    
                    decision = await leader.make_decision(


    
                        summary="直接决策模式，无群体讨论。",


    
                        salary=group_param


    
                    )


    
                    return decision


    
                # 群体决策模式


    
                ordinary_members = [


    
                    member for member in config['agents'].values()


    
                    if isinstance(member, config['ordinary_type'])


    
                    and not isinstance(member, InformationOfficer)


    
                ]


    
                if not ordinary_members:


    
                    return None


    
                shared_pool = list(config['agents'].values())[0].shared_pool


    
                await shared_pool.clear_discussions()


    
                # 确保平均满意度已计算

    
                if self.average_satisfaction is None:

    
                    self.average_satisfaction = self.calculate_average_satisfaction()


    
                # 第一轮：所有成员异步发表初始意见


    
                first_round_tasks = [


    
                    member.generate_opinion(salary=group_param)


    
                    for member in random.sample(ordinary_members, len(ordinary_members))


    
                ]


    
                await asyncio.gather(*first_round_tasks)


    
                # 后续轮次：基于之前的讨论内容发表见解


    
                for round_num in range(2, configured_max_rounds + 1):


    
                    print(f"第{round_num}轮决策")


    
                    round_tasks = [


    
                        member.generate_and_share_opinion(salary=group_param)


    
                        for member in random.sample(ordinary_members, len(ordinary_members))


    
                    ]


    
                    await asyncio.gather(*round_tasks)


    
                # 获取信息整理员


    
                info_officers = [


    
                    member for member in config['agents'].values()


    
                    if isinstance(member, InformationOfficer)


    
                ]


    
                # 处理讨论结果


    
                if info_officers and leaders:


    
                    discussion_summary = await info_officers[0].summarize_discussions()


    
                    if discussion_summary:


    
                        decision = await leaders[0].make_decision(discussion_summary, group_param)


    
                        return decision


    
                return None
    
    def execute_government_decision(self, decision):

    
            """执行政府决策"""

    
            _, salary = self.calculate_total_salaries()


    
            try:

    
                decision_data = self.parse_decision(decision)

    
                if not decision_data:

    
                    return False


    
                success = True

    
                decision_keys = list(decision_data.keys())

    
                random.shuffle(decision_keys)


    
                for key in decision_keys:

    
                    if key == "tax_adjustment" and decision_data[key] is not None:

    
                        new_tax_rate = decision_data[key]

    
                        self.government.adjust_tax_rate(new_tax_rate)

    
                        print(f"政府调整税率至: {new_tax_rate}")


    
                    elif key == "economic_support" and decision_data[key] is not None:

    
                        support_amount = decision_data[key]

    
                        if self.government.budget >= support_amount:

    
                            self.government.budget -= support_amount

    
                            for town_name in self.towns.towns:

    
                                self.towns.towns[town_name]['economic_support'] = self.towns.towns[town_name].get('economic_support', 0) + support_amount / len(self.towns.towns)

    
                            print(f"政府提供经济支持: {support_amount}")


    
                    elif key == "climate_relief" and decision_data[key] is not None:

    
                        relief_amount = decision_data[key]

    
                        if self.government.budget >= relief_amount:

    
                            self.government.budget -= relief_amount

    
                            for town_name in self.towns.towns:

    
                                self.adjust_town_satisfaction_by_policy(town_name, relief_amount / len(self.towns.towns) / 100)

    
                            print(f"政府提供气候救济: {relief_amount}")


    
                    elif key == "river_maintenance" and decision_data[key] is not None:

    
                        maintenance_amount = decision_data[key]

    
                        success = self.government.maintain_canal(maintenance_amount)

    
                        if success:

    
                            print(f"政府投入运河维护: {maintenance_amount}")


    
                return success


    
            except Exception as e:

    
                print(f"执行决策时出错:{e}")

    
                return False
    
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
    
    def calculate_gdp(self):

    
        if not self.residents:

    
            return 0.0

    
        total_income = sum(resident.income for resident in self.residents.values())

    
        return total_income
    
    def calculate_average_satisfaction(self):
        """计算所有居民的平均满意度"""
        if not self.residents:
            print("没有居民，平均满意度为 0.0")
            return 0.0
        
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())
        average_satisfaction = total_satisfaction / self.population.population
        print(f"平均满意度: {average_satisfaction:.2f}")
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
        print(f"总体就业率: {total_employed} / {total_residents} = {total_employed / total_residents:.2f}")
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

    
            """获取所有职业的岗位总数"""

    
            total_count = 0

    
            for town_name, town_data in self.towns.towns.items():

    
                job_market = town_data['job_market']

    
                if job_market:

    
                    for job, info in job_market.jobs_info.items():

    
                        total_count += info.get("quota", 0)

    
            return total_count
    
    def get_basic_living_cost(self):
        """获取当前基本生活所需值"""
        return self.basic_living_cost
    
    def adjust_basic_living_cost(self, adjustment):
        """调整基本生活所需值"""
        self.basic_living_cost = max(500, self.basic_living_cost + adjustment)
        print(f"基本生活所需值调整为: {self.basic_living_cost}")
        return self.basic_living_cost
    
    async def integrate_new_residents(self, new_residents):
        """整合新居民到系统"""
        if not new_residents:
            return
        
        self.residents.update(new_residents)
        print(f"{len(new_residents)} 名新居民已出生")
        
        self.towns.initialize_resident_groups(new_residents)
        print("新居民已加入各自城镇")
        
        if new_residents:
            self.social_network.add_new_residents(new_residents)
            print(f"{len(new_residents)} 名新居民已加入社交网络")
    
    def summarize_time_step_results(self):

    
        current_idx = len(self.results["years"]) - 1

    
        if current_idx <= 0:

    
            return {}


    
        changes = {

    
            "人口变化率": self.calculate_change_rate("population", current_idx),

    
            "GDP变化率": self.calculate_change_rate("gdp", current_idx),

    
            "政府预算变化率": self.calculate_change_rate("government_budget", current_idx),

    
            "平均满意度变化": self.calculate_change_rate("average_satisfaction", current_idx),

    
            "失业率变化": self.calculate_change_rate("unemployment_rate", current_idx),

    
            "温度变化": self.calculate_change_rate("temperature", current_idx),

    
            "迁移率": self.results["migration_rate"][current_idx],

    
        }

    
        return changes
    
    def calculate_change_rate(self, metric, current_idx):
        """计算指定指标的变化率"""
        current = self.results[metric][current_idx]
        previous = self.results[metric][current_idx-1]
        if previous == 0:
            return 0 if current == 0 else 1
        return (current - previous) / previous
    
    async def store_decision_memory(self, group_type, decision, changes_summary):

    
        if group_type == 'government':

    
            memory_content = (

    
                f"时间: {self.time.current_time}"

    
                f"决策内容: {decision}"

    
                f"执行结果:"

    
                f"- GDP变化率: {'+' if changes_summary.get('GDP变化率', 0) > 0 else ''}{changes_summary.get('GDP变化率', 0):.2%}"

    
                f"- 政府预算变化率: {'+' if changes_summary.get('政府预算变化率', 0) > 0 else ''}{changes_summary.get('政府预算变化率', 0):.2%}"

    
                f"- 平均满意度变化: {'+' if changes_summary.get('平均满意度变化', 0) > 0 else ''}{changes_summary.get('平均满意度变化', 0):.2%}"

    
                f"- 失业率变化: {'+' if changes_summary.get('失业率变化', 0) > 0 else ''}{changes_summary.get('失业率变化', 0):.2%}"

    
                f"- 温度变化: {'+' if changes_summary.get('温度变化', 0) > 0 else ''}{changes_summary.get('温度变化', 0):.2%}"

    
                f"- 迁移率: {changes_summary.get('迁移率', 0):.2%}"

    
            )

    
            for official in self.government_officials.values():

    
                await official.store_memory(memory_content)


    def update_resident_status(self, basic_living_cost):


            """更新居民状态，返回居民是否死亡"""


            for resident in list(self.residents.values()):


                is_dead = resident.update_resident_status(basic_living_cost)


                if is_dead:


                    resident_name = resident.resident_id


                    # 从居民字典中移除


                    if resident_name in self.residents:


                        del self.residents[resident_name]


                    # 从社交网络中移除


                    if self.social_network:


                        self.social_network.remove_node(resident_name)


                    # 从城镇中移除（使用Towns API方法）


                    town_name = resident.location


                    job_type = resident.job if hasattr(resident, 'job') else None


                    self.towns.remove_resident(resident_name, town_name, job_type)


                    print(f"居民 {resident_name} 已死亡")


    def adjust_town_satisfaction_by_climate(self, town_name, climate_impact_factor):


            """根据气候影响调整城镇居民满意度"""


            if town_name not in self.towns.towns:


                return


            town_data = self.towns.towns[town_name]


            satisfaction_adjustment = -abs(climate_impact_factor) * 5


            resident_list = town_data.get('residents', [])


            if isinstance(resident_list, dict):


                resident_list = resident_list.values()


            for resident in resident_list:


                if hasattr(resident, 'satisfaction'):


                    resident.satisfaction = max(0, min(100, resident.satisfaction + satisfaction_adjustment))


    def adjust_town_satisfaction_by_policy(self, town_name, satisfaction_increase):


            """根据政策调整城镇居民满意度"""


            if town_name not in self.towns.towns:


                return


            town_data = self.towns.towns[town_name]


            resident_list = town_data.get('residents', [])


            if isinstance(resident_list, dict):


                resident_list = resident_list.values()


            for resident in resident_list:


                if hasattr(resident, 'satisfaction'):


                    resident.satisfaction = max(0, min(100, resident.satisfaction + satisfaction_increase))
