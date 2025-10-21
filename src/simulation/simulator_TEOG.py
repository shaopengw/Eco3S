import asyncio
import json
import sys
import random
import pandas as pd
import os
import yaml
import logging
from datetime import datetime
from colorama import Back
from src.agents.government import (
    OrdinaryGovernmentAgent,
    HighRankingGovernmentAgent,
    InformationOfficer
)
from src.agents.resident_agent_generator import generate_new_residents
from src.utils.simulation_context import SimulationContext

if "sphinx" not in sys.modules:
    resident_log = logging.getLogger(name="resident.agent")
    resident_log.setLevel("DEBUG")
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_handler = logging.FileHandler(f"./log/resident.agent-{str(now)}.log")
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
    resident_log.addHandler(file_handler)

class TEOGSimulator:
    def __init__(self, map, time, government, government_officials, population, social_network, residents, towns, transport_economy, climate, config):
        """初始化模拟器类"""
        self.map = map
        self.time = time
        self.government = government
        self.government_officials = government_officials
        self.population = population
        self.social_network = social_network
        self.residents = residents
        self.towns = towns
        self.transport_economy = transport_economy #水利系统
        self.climate = climate
        self.basic_living_cost = 8  # 每年基本生活所需值（单位：两）
        self.average_satisfaction = None  # 平均满意度（0-100）
        self.gdp = 0  # 国内生产总值（单位：两）
        self.initialize_salaries()
        self.config = config
        
        self.results = {
            "years": [],
            "population": [],
            "government_budget": [],
            "average_satisfaction": [],
            "tax_rate": [],
            "river_navigability": [],
            "gdp": [],
            "urban_scale":[],
        }
        
        # 保存初始数据
        self.gdp = self.calculate_gdp()  # 确保先计算初始GDP
        self.average_satisfaction = self.calculate_average_satisfaction()  # 计算初始满意度
        
        # 创建结果文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}.csv")
        
        self.save_initial_results()
        self.start_time = None  # 用于记录模拟开始时间
        self.end_time = None    # 用于记录模拟结束时间

    def save_initial_results(self):
        """保存结果数据"""
        self.results["years"].append("初始")
        self.results["population"].append(self.population.get_population())
        self.results["government_budget"].append(self.government.get_budget())
        self.results["average_satisfaction"].append(self.average_satisfaction)
        self.results["tax_rate"].append(self.government.get_tax_rate())
        self.results["river_navigability"].append(self.map.get_navigability())
        self.results["gdp"].append(self.gdp)
        self.results["urban_scale"].append(self.get_urban_scale())

    async def run(self):
        """运行模拟"""
        while not self.time.is_end():
            # 打印当前时间步信息
            print(Back.GREEN + f"年份:{self.time.get_current_time()}" + Back.RESET)
            # 更新属性变量
            # 更新运河状态和居民收入
            climate_impact_factor = self.climate.get_current_impact(self.time.get_current_year(),self.time.get_start_time())
            print(f"天气影响因子：{climate_impact_factor}")

            self.map.decay_river_condition_naturally(climate_impact_factor)
            river_navigability = self.map.get_navigability() 
            await self.update_resident_income(climate_impact_factor, river_navigability)

            # 政府
            self.gdp = self.calculate_gdp() # 更新GDP
            self.tax_income = self.gdp * self.government.get_tax_rate() # 计算税收收入
            self.government.budget = round(self.government.budget + self.tax_income, 2) 
            
            # 居民
            self.average_satisfaction = self.calculate_average_satisfaction() # 更新平均满意度
            self.population.update_birth_rate(self.average_satisfaction) # 更新出生率
            print(f"GDP：{self.gdp}，税收收入：{self.tax_income}，政府预算：{self.government.budget}，政府规模：{self.get_urban_scale()}")
            
            # 居民出生（每年）
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
            
            # 政府决策阶段
            government_decision = None
            
            # 收集政府决策
            government_config = {
                'agents': self.government_officials,
                'ordinary_type': OrdinaryGovernmentAgent,
                'leader_type': HighRankingGovernmentAgent,
            }
            # government_decision = await self.collect_group_decision(government_config)
            
            if government_decision:
                self.execute_government_decision(government_decision)
            
            # 居民行为阶段
            await self.handle_resident_actions()

            # 4. 年终：更新和记录数据
            self.update_annual_results()
            # 在每个时间步结束时保存结果
            self.save_results(self.result_file, append=True)
            # 记录年度记忆
            if government_decision:
                changes_summary = self.summarize_time_step_results()
                # 存储到政府记忆中
                if government_decision:
                    await self.store_decision_memory(
                        'government', 
                        government_decision,
                        changes_summary
                    )
            
            print(f"城市居民：{self.get_urban_scale()}，农民：{self.population.get_population() - self.get_urban_scale()}")
            self.time.step()

    async def initialize_salaries(self):
        """
        初始化沿河城市和非沿河城市的基本工资。
        """
        for town_name, town_data in self.towns.towns.items():
            job_market = town_data.get('job_market')
            if job_market:
                original_salary_city = job_market.jobs_info["城市居民"]["base_salary"]
                if job_market.town_type == "非沿河":
                    new_salary = original_salary_city * 0.7
                    self.salary_non_canal = new_salary
                    job_market.jobs_info["城市居民"]["base_salary"] = new_salary
                    job_market.jobs_info["农民"]["base_salary"] = new_salary

                print(f"居民工资初始化：{town_name} "
                    f"新工资 {new_salary:.2f} "
                    f"(非沿河城市: {job_market.town_type == '非沿河'})")

    async def collect_group_decision(self, config, max_rounds=2):
        """
        收集政府群体决策
        :param config: 群体配置
        :param max_rounds: 最大讨论轮数
        :return: 决策结果
        """
        print("开始收集政府决策")

        # 获取群体决策配置
        try:
            with open('config_TEOG/simulation_config.yaml', 'r', encoding='utf-8') as f:
                sim_config = yaml.safe_load(f)
                group_decision_config = sim_config['simulation'].get('group_decision', {})
                group_decision_enabled = group_decision_config.get('enabled', True)
                configured_max_rounds = group_decision_config.get('max_rounds', 2)
        except Exception as e:
            print(f"读取群体决策配置失败，使用默认值：{e}")
            group_decision_enabled = True
            configured_max_rounds = max_rounds

        # 计算决策参数
        government_salary = self.calculate_total_salaries()
        group_param = government_salary

        # 获取领导者
        leaders = [member for member in config['agents'].values()
                  if isinstance(member, config['leader_type'])]
        if not leaders:
            return None

        # 如果不启用群体决策，直接由领导者决策
        if not group_decision_enabled:
            leader = leaders[0]
            decision = await leader.make_decision(
                summary="直接决策模式，无群体讨论。",
                towns_stats=group_param
            )
            return decision

        # 启用群体决策模式
        ordinary_members = [
            member for member in config['agents'].values()
            if isinstance(member, config['ordinary_type'])
            and not isinstance(member, InformationOfficer)
        ]

        if not ordinary_members:
            return None

        shared_pool = list(config['agents'].values())[0].shared_pool
        await shared_pool.clear_discussions()

        # 第一轮：所有成员异步发表初始意见
        first_round_tasks = [
            member.generate_opinion(group_param)
            for member in random.sample(ordinary_members, len(ordinary_members))
        ]
        await asyncio.gather(*first_round_tasks)

        # 后续轮次：基于之前的讨论内容发表见解
        for round_num in range(2, configured_max_rounds + 1):
            print(f"第{round_num}轮决策")
            round_tasks = [
                member.generate_and_share_opinion(group_param)
                for member in random.sample(ordinary_members, len(ordinary_members))
            ]
            await asyncio.gather(*round_tasks)

        # 获取信息整理员
        info_officers = [
            member for member in config['agents'].values()
            if isinstance(member, InformationOfficer)
        ]

        # 处理讨论结果
        if info_officers and leaders and shared_pool.is_ended():
            discussion_summary = await info_officers[0].summarize_discussions()
            if discussion_summary:
                decision = await leaders[0].make_decision(discussion_summary, group_param)
                return decision

        return None

    def execute_government_decision(self, decision):
        """执行政府决策"""
        def parse_decision(decision_text, max_retries=3):
            """解析决策内容，支持重试"""
            import json
            import re
            
            def extract_json_from_text(text):
                """从文本中提取JSON内容"""
                json_pattern = r'\{[^{}]*\}'
                matches = re.findall(json_pattern, text)
                for match in matches:
                    try:
                        return json.loads(match)
                    except json.JSONDecodeError:
                        continue
                return None

            # 删除前缀和后缀
            decision_text = decision_text.strip().removeprefix('```json').removesuffix('```')
            for attempt in range(max_retries):
                try:
                    # 尝试直接解析JSON
                    return json.loads(decision_text)
                except json.JSONDecodeError:
                    # 尝试从文本中提取JSON
                    extracted = extract_json_from_text(decision_text)
                    if extracted:
                        return extracted

                    if attempt < max_retries - 1:
                        print(f"决策内容格式错误，第{attempt + 1}次重试...")
                        continue
                    else:
                        print("达到最大重试次数，决策执行失败")
                        return None

        try:
            # 解析决策内容
            decision_data = parse_decision(decision)
            if not decision_data:
                return False

            # 执行所有决策动作
            success = True
            
            # 获取决策键并随机打乱顺序
            import random
            decision_keys = list(decision_data.keys())
            random.shuffle(decision_keys)

            # 按随机顺序处理政府决策
            for key in decision_keys:
                if key == "maintenance_investment":
                    self.government.maintain_canal(
                        maintenance_investment=decision_data["maintenance_investment"]
                    )

                elif key == "tax_adjustment":
                    self.government.adjust_tax_rate(decision_data["tax_adjustment"])

            return success

        except Exception as e:
            print(f"执行决策时出错：{e}")
            return False

    async def handle_resident_actions(self):
        """处理居民行为"""
        tasks = []
        speech_tasks = []
        resident_decisions = []
        
        for resident_id, resident in list(self.residents.items()):
            # 更新居民寿命（每年）
            if resident.update_resident_status(self.basic_living_cost):
                del self.residents[resident_id]
                self.population.death()
                continue
            
            # 收集居民行为决策
            tax_rate = self.government.get_tax_rate()
            climate_impact_factor = self.climate.get_current_impact(self.time.get_current_year(), self.time.get_start_time())
            task = resident.decide_action_by_llm(tax_rate, self.basic_living_cost, climate_impact_factor)
            tasks.append(task)
            resident_decisions.append(resident)  # 保存对应的居民对象

        # 并发执行所有居民的行为并收集结果
        if tasks:
            results = await asyncio.gather(*tasks)
            # 处理返回的结果
            for resident, result in zip(resident_decisions, results):
                if isinstance(result, tuple) and len(result) == 4:
                    # 处理带有发言的决策结果
                    select, reason, speech, relation_type = result
                    # 收集发言传播任务
                    speech_tasks.append(asyncio.create_task(
                        self.social_network.spread_speech_in_network(
                            resident.resident_id, speech, relation_type
                        )
                    ))
                    try:
                        await resident.execute_decision(select, reason=reason)
                    except Exception as e:
                        print(f"执行居民 {resident.resident_id} 动作失败: {e}")

                elif isinstance(result, tuple) and len(result) == 2:
                    select, reason = result
                    try:
                        await resident.execute_decision(select, reason=reason)
                    except Exception as e:
                        print(f"执行居民 {resident.resident_id} 动作失败: {e}")
                
            
            # 并发执行所有发言传播任务
            if speech_tasks:
                await asyncio.gather(*speech_tasks)

    def update_annual_results(self):
        """更新年度结果"""
        # 每3-5年更新一次社交网络
        current_year = self.time.get_current_year()
        if current_year % random.randint(3, 5) == 0:
            self.social_network.update_network_edges()  # 更新社交网络边

        self.results["years"].append(self.time.get_current_time())
        self.results["population"].append(self.population.get_population())
        self.results["government_budget"].append(self.government.get_budget())
        self.results["average_satisfaction"].append(self.average_satisfaction)
        self.results["tax_rate"].append(self.government.get_tax_rate())
        self.results["river_navigability"].append(self.map.get_navigability())
        self.results["gdp"].append(self.gdp)
        self.results["urban_scale"].append(self.get_urban_scale())

    def calculate_average_satisfaction(self):
        """计算平均满意度"""
        if not self.residents:
            return 0
        return sum(resident.satisfaction for resident in self.residents.values()) / len(self.residents)

    def save_results(self, filename=None, append=False):
        """
        保存模拟结果到CSV文件
        :param filename: 文件名
        :param append: 是否追加模式，用于增量更新
        """
        
        # 使用 SimulationContext 获取数据目录
        data_dir = SimulationContext.get_data_dir()
        
        # 确保数据目录存在
        SimulationContext.ensure_directories()
    
        if filename is None:
            # 如果没有指定文件名，使用默认的命名规则
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(data_dir, f"running_data_{timestamp}.csv")
        
        if append:
            # 创建一个字典，包含每个指标的最新数据点
            last_row_data = {key: [value[-1]] for key, value in self.results.items() if value}
            df = pd.DataFrame(last_row_data)
        else:
            df = pd.DataFrame(self.results)
        
        if append and os.path.exists(filename):
            # 追加模式，不写入表头
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            # 新文件或覆盖模式
            df.to_csv(filename, index=False)
        
        if not append:
            print(f"模拟结果已保存至 {filename}")
    
    def calculate_gdp(self):
        """
        计算GDP
        :return: GDP值（浮点数）
        """
        if not self.residents:
            return 0.0
        # 计算所有居民的收入总和
        total_income = sum(resident.income for resident in self.residents.values() if resident.job != "农民")
        gdp = total_income
        return gdp
    
    async def update_resident_income(self, climate_impact, river_navigability=0):
        """
        更新所有居民的收入，包括居民和就业市场中的相应职业。
        :param climate_impact: 气候影响因子
        :param river_navigability: 运河通航能力因子 (仅对城市居民有影响)
        """
        print(f"收入更新：综合影响因子: (运河影响{river_navigability},天气影响{climate_impact}) ")
        
        # 初始化工资记录
        income_records = {
            '沿河农民': None,
            '非沿河农民': None,
            '沿河城市居民': None,
            '非沿河城市居民': None
        }

        for resident in self.residents.values():
            town_name = resident.town
            town_data = self.towns.towns.get(town_name)

            if not (town_data and 'job_market' in town_data):
                print(f"警告：无法找到居民 {resident.resident_id} 所在城镇 {town_name} 的就业市场信息。")
                continue

            job_market = town_data['job_market']
            job_type = resident.job

            if job_type not in job_market.jobs_info:
                print(f"警告：城镇 {town_name} 的就业市场中没有 '{job_type}' 职业信息。")
                continue

            base_salary = job_market.jobs_info[job_type]["base_salary"]
            original_income = resident.income

            # 确定城镇类型
            town_type = town_data.get('town_type', '非沿河')
            is_river = town_type == "沿河"
            
            if job_type == "农民":
                new_income = round(base_salary * (1 - climate_impact), 2)
                resident.income = max(0, new_income)
                
                # 记录农民工资
                key = '沿河农民' if is_river else '非沿河农民'
                if income_records[key] is None:
                    income_records[key] = resident.income
                    
            elif job_type == "城市居民":
                new_income = round(base_salary * river_navigability, 2)
                resident.income = max(0, new_income)
                
                # 记录城市居民工资
                key = '沿河城市居民' if is_river else '非沿河城市居民'
                if income_records[key] is None:
                    income_records[key] = resident.income
            else:
                print(f"警告：居民 {resident.resident_id} 的职业 '{job_type}' 未在就业市场中找到相应信息。")
        
        # 输出工资信息
        print("\n===== 工资统计 =====")
        for category, income in income_records.items():
            if income is not None:
                print(f"{category}: {income}")

    def summarize_time_step_results(self):
        """总结当前时间步的各项指标变化"""
        current_idx = len(self.results["years"]) - 1
        if current_idx <= 0:
            return {}
        
        # 计算各项指标的变化率
        changes = {
            "城市规模变化率": self.calculate_change_rate("urban_scale", current_idx),
            "GDP变化率": self.calculate_change_rate("gdp", current_idx),
            "政府预算变化率": self.calculate_change_rate("government_budget", current_idx),
            "平均满意度变化": self.calculate_change_rate("average_satisfaction", current_idx),
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
        """
        存储决策记忆
        :param group_type: 群体类型
        :param decision: 决策内容
        :param changes_summary: 变化率总结
        """
        # 将决策内容和结果格式化为字符串
        if group_type == 'government':
            memory_content = (
                f"时间: {self.time.get_current_year()}\n"
                f"决策内容: {decision}\n"
                f"执行结果:\n"
                f"- GDP变化率: {'+' if changes_summary.get('GDP变化率', 0) > 0 else ''}{changes_summary.get('GDP变化率', 0):.2%}\n"
                f"- 政府预算变化率: {'+' if changes_summary.get('政府预算变化率', 0) > 0 else ''}{changes_summary.get('政府预算变化率', 0):.2%}\n"
                f"- 平均满意度变化: {'+' if changes_summary.get('平均满意度变化', 0) > 0 else ''}{changes_summary.get('平均满意度变化', 0):.2%}\n"
                f"- 失业率变化: {'+' if changes_summary.get('失业率变化', 0) > 0 else ''}{changes_summary.get('失业率变化', 0):.2%}\n"
            )
            
            # 存储到所有政府官员的记忆中
            for official in self.government_officials.values():
                if not isinstance(official, InformationOfficer):
                    await official.memory.write_record(
                        role_name=official.__class__.__name__,
                        content=memory_content,
                        is_user=False,
                        round_num=self.time.get_current_time(),
                        store_in_shared=True
                    )

    async def integrate_new_residents(self, new_residents):
        """将新居民整合到系统中"""
        if not new_residents:
            return

        # 更新全局居民列表
        self.residents.update(new_residents)
        print(f"{len(new_residents)} 名新居民已出生")

        # 添加到城镇
        self.towns.initialize_resident_groups(new_residents)
        print("新居民已加入各自城镇")

        # 添加到社交网络
        if new_residents:
            self.social_network.add_new_residents(new_residents)
            print(f"{len(new_residents)} 名新居民已加入社交网络")
            # self.social_network.visualize()

    def calculate_total_salaries(self):
        """
        计算总收入
        :return: 总收入
        """
        total_salary = 0
        
        for town_name, town_data in self.towns.towns.items():
            if town_data.get('job_market'):
                total_salary += town_data['job_market'].get_other_total_salary()
        
        return total_salary

    def get_urban_scale(self):
        """
        获取城市规模        
        :return: 城市规模
        """
        urban_scale = 0
        total_population = self.population.get_population()
        
        for town_name, town_data in self.towns.towns.items():
            if town_data.get('job_market'):
                urban_scale += len(town_data['job_market'].jobs_info["城市居民"]["employed"])
        
        # 确保城市规模不超过总人口
        return min(urban_scale, total_population)
