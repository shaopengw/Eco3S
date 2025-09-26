import asyncio
import json
import sys
import random
import pandas as pd
import os
import yaml
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from colorama import Back
import pickle
import networkx as nx
from src.agents import government
from src.agents.resident_agent_generator import (generate_canal_agents)
from src.agents.government import (
    OrdinaryGovernmentAgent,
    HighRankingGovernmentAgent,
    InformationOfficer
)
from src.agents.resident_agent_generator import generate_new_residents
from src.environment.social_network import SocialNetwork
from src.environment.towns import Towns
from src.environment.transport_economy import TransportEconomy
from src.agents.model_manager import ModelManager
from src.environment.map import Map
from src.environment.time import Time
from src.environment.job_market import JobMarket
from src.environment.population import Population
from src.environment.social_network import SocialNetwork
from src.environment.climate import ClimateSystem
from src.agents.government import Government, government_SharedInformationPool
from src.agents.resident import Resident, ResidentGroup, ResidentSharedInformationPool

from camel.configs import ChatGPTConfig
from camel.memories import ScoreBasedContextCreator, MemoryRecord
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelType
from camel.utils import OpenAITokenCounter
from src.agents.model_manager import ModelManager
from src.agents.memory_manager import MemoryManager
from src.agents.base_agent import BaseAgent

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
            government_decision = await self.collect_group_decision(government_config)
            
            if government_decision:
                self.execute_government_decision(government_decision)
            
            # 居民行为阶段
            await self.handle_resident_actions()

            # 4. 年终：更新和记录数据
            self.update_annual_results()
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
                    speech_tasks.append(self.social_network.spread_speech_in_network(
                        resident.resident_id, speech, relation_type
                    ))
                    await self.process_resident_action(resident, select, reason)
                elif isinstance(result, tuple) and len(result) == 2:
                    select, reason = result
                    await self.process_resident_action(resident, select, reason)
                
            
            # 并发执行所有发言传播任务
            if speech_tasks:
                await asyncio.gather(*speech_tasks)

    async def process_resident_action(self, resident, select, reason):
        """处理单个居民的行为结果"""
        if select == 1:  # 加入城邦
            if resident.job == "农民":
                resident.job_market.assign_specific_job_withoutcheck(resident, "城市居民")
            
        elif select == 2:  # 迁徙
            # 尝试迁移
            job = resident.job
            success = await resident.migrate_to_new_town(self.map)

            if success:
                # 更新社交网络
                resident.job_market.assign_specific_job_withoutcheck(resident, job) # 迁移后重新分配身份
                self.social_network.update_network_edges()
            else:
                print(f"居民 {resident.resident_id} 迁移失败")
        
        elif select == 3:  # 自给自足
            if resident.job == "城市居民":
                resident.job_market.assign_specific_job_withoutcheck(resident, "农民")

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

    def save_results(self, filename=None):
        """保存模拟结果"""
        from src.utils.simulation_context import SimulationContext
        
        # 使用 SimulationContext 获取数据目录
        data_dir = SimulationContext.get_data_dir()
        
        # 确保数据目录存在
        SimulationContext.ensure_directories()

        if filename is None:
            # 如果没有指定文件名，使用默认的命名规则
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(data_dir, f"running_data_{timestamp}.csv")
        
        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False)
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

    def save_cache(self, file_path):
        """保存模拟状态到缓存文件"""
        from src.utils.simulation_context import SimulationContext
        
        # 使用 SimulationContext 获取数据目录
        data_dir = SimulationContext.get_data_dir()
        
        # 确保数据目录存在
        SimulationContext.ensure_data_dir_exists()

        if file_path is None:
            # 如果没有指定文件路径，使用默认的命名规则
            population = self.population.get_population()
            total_years = self.time.total_years
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(data_dir, f"simulation_cache_p{population}_y{total_years}_{timestamp}.pkl")
        try:
            with open(file_path, 'wb') as f:
                # 只保存关键状态数据
                government_state = {
                    'budget': self.government.budget,
                    'tax_rate': self.government.tax_rate
                }
                
                residents_state = [
                    {
                        'resident_id': resident.resident_id,
                        'shared_pool': {
                            'economic_status': resident.shared_pool.shared_info.get('economic_status', {}),
                            'social_network': resident.shared_pool.shared_info.get('social_network', {}),
                            'environment_awareness': resident.shared_pool.shared_info.get('environment_awareness', {})
                        },
                        'location': resident.location,
                        'town': resident.town,
                        'employed': resident.employed,
                        'job': resident.job,
                        'income': resident.income,
                        'satisfaction': resident.satisfaction,
                        'health_index': resident.health_index,
                        'lifespan': resident.lifespan,
                        'personality': resident.personality,
                        'system_message': resident.system_message,
                        'memory': {
                            'chat_history': [{
                                'role': record.memory_record.role_at_backend,
                                'content': record.memory_record.message.content
                            } for record in resident.memory.personal_memory.chat_history.retrieve()],
                            'longterm_memory': resident.memory.personal_memory.longterm_memory
                        } if resident.memory else None,
                    } for resident in self.residents.values()
                ]
                
                towns_state = {
                    town_name: {
                        'info': {
                            'name': town_name,
                            'location': town_data['info']['location'],
                            'type': town_data['info']['type']
                        },
                        'residents': {
                            resident_id: {
                                'resident_id': resident.resident_id,
                                'town': resident.town
                            } for resident_id, resident in town_data['residents'].items()
                        },
                        'job_market': {
                            'town_type': town_data['job_market'].town_type,
                            'jobs_info': {
                                job_type: {
                                    'total': info['total'],
                                    'employed': {
                                        resident_id: salary 
                                        for resident_id, salary in info['employed'].items()
                                    },
                                    'base_salary': info['base_salary']
                                } for job_type, info in town_data['job_market'].jobs_info.items()
                            }
                        } if town_data['job_market'] else None
                    } for town_name, town_data in self.towns.towns.items()
                }
                
                government_officials_state = [
                    {
                        'agent_id': official.agent_id,
                        'group_type': 'government',
                        'function': getattr(official, 'function', None),
                        'faction': getattr(official, 'faction', None),
                        'personality': getattr(official, 'personality', None) if hasattr(official, 'personality') else None,
                        'system_message': official.system_message,
                        # 添加记忆系统状态
                        'memory': {
                            'chat_history': [{
                                'role': record.memory_record.role_at_backend,
                                'content': record.memory_record.message.content
                            } for record in official.memory.personal_memory.chat_history.retrieve()],
                            'longterm_memory': official.memory.personal_memory.longterm_memory
                        } if official.memory else None
                    } for official in self.government_officials.values()
                ]

                state = {
                    'map': self.map,
                    'time': self.time,
                    'population': self.population.get_population(),
                    'government': government_state,
                    'transport_economy': self.transport_economy,
                    'residents': residents_state,
                    'towns': towns_state,
                    'government_officials': government_officials_state,
                    'social_network': self.social_network.to_dict(),
                    'climate': self.climate,
                    'basic_living_cost': self.basic_living_cost,
                    'average_satisfaction': self.average_satisfaction,
                    'gdp': self.gdp,
                    'results': self.results,
                    'start_time': self.start_time,
                    'end_time': self.end_time
                }
                pickle.dump(state, f)
                print(f"缓存文件保存成功")
        except Exception as e:
            raise Exception(f"保存缓存失败: {e}")

    @classmethod
    def load_cache(cls, file_path, simulator_years, config):
        """从缓存文件加载模拟状态"""
        try:
            with open(file_path, 'rb') as f:
                state = pickle.load(f)
            
            # 创建新的模拟器实例
            simulator = cls.__new__(cls)
            
            # 重建基础组件
            simulator.map = state.get('map')
            simulator.time = state.get('time')
            if simulator.time:
                simulator.time.update_total_years(simulator_years)
            simulator.population = state.get('population')
            simulator.transport_economy = state.get('transport_economy')
            simulator.climate = state.get('climate')
            simulator.config = config
            
            # 重建居民
            simulator.residents = {}
            residents_data = state.get('residents')
            if residents_data and isinstance(residents_data, list):
                for res_state in residents_data:
                    resident = Resident(
                        resident_id=res_state.get('resident_id'),
                        job_market=None,  # 临时设为None，后续更新
                        shared_pool=ResidentSharedInformationPool(),
                        map=simulator.map,
                        resident_prompt_path=simulator.config["data"]["resident_prompt_path"],
                    )
                    # 初始化model_manager和model_backend
                    resident.model_manager = ModelManager()
                    model_config = resident.model_manager.get_random_model_config()
                    resident.model_type = ModelType(model_config["model_type"])
                    resident.model_config = ChatGPTConfig(**model_config["model_config"])
                    resident.model_backend = ModelFactory.create(
                        model_platform=model_config["model_platform"],
                        model_type=resident.model_type,
                        model_config_dict=resident.model_config.as_dict(),
                    )
                    resident.token_counter = OpenAITokenCounter(resident.model_type)
                    resident.context_creator = ScoreBasedContextCreator(resident.token_counter, 4096)
                    # 恢复居民状态
                    resident.shared_pool.shared_info = res_state.get('shared_pool', {})
                    resident.location = res_state.get('location')
                    resident.town = res_state.get('town')
                    resident.employed = res_state.get('employed')
                    resident.job = res_state.get('job')
                    resident.income = res_state.get('income')
                    resident.satisfaction = res_state.get('satisfaction')
                    resident.health_index = res_state.get('health_index')
                    resident.lifespan = res_state.get('lifespan')
                    resident.personality = res_state.get('personality')
                    resident.system_message = res_state.get('system_message')
                    simulator.residents[resident.resident_id] = resident
                    # 恢复记忆系统
                    memory_state = res_state.get('memory')
                    if memory_state:
                        resident.memory = MemoryManager(
                            agent_id=resident.resident_id,
                            model_type=resident.model_type,
                            group_type='resident',
                            window_size=5
                        )
                        resident.memory.set_agent(resident)
                        # 恢复聊天历史
                        for msg in memory_state.get('chat_history', []):
                            record = MemoryRecord(
                                message=BaseMessage.make_assistant_message(
                                    role_name='resident',
                                    content=msg['content']
                                ) if msg['role'] == 'assistant' else BaseMessage.make_user_message(
                                    role_name='resident',
                                    content=msg['content']
                                ),
                                role_at_backend=msg['role']
                            )
                            resident.memory.personal_memory.write_record(record)
                            # 恢复长期记忆
                            resident.memory.personal_memory.longterm_memory = memory_state.get('longterm_memory', [])
                        simulator.residents[resident.resident_id] = resident
            # 重建城镇
            simulator.towns = Towns(simulator.map, simulator.population.get_population(), simulator.config["data"]["jobs_config_path"])
            towns_state = state.get('towns')
            if towns_state and isinstance(towns_state, dict):
                for town_name, town_data in towns_state.items():
                    simulator.towns.towns[town_name] = {
                        'info': town_data.get('info', {}),
                        'residents': {},
                        'job_market': None,  # 临时设为None，后续更新
                        'resident_group': ResidentGroup(town_name)  # 初始化ResidentGroup
                    }

                    # 恢复就业市场
                    if town_data.get('job_market'):
                        job_market = JobMarket(town_data['job_market'].get('town_type'), initial_jobs_count=0, config_path=simulator.config["data"]["jobs_config_path"])
                        for job_type, info in town_data['job_market'].get('jobs_info', {}).items():
                            job_market.jobs_info[job_type] = {
                                'total': info.get('total'),
                                'employed': info.get('employed', {}),
                                'base_salary': info.get('base_salary')
                            }
                        simulator.towns.towns[town_name]['job_market'] = job_market
                    else:
                        simulator.towns.towns[town_name]['job_market'] = JobMarket(town_data.get('info', {}).get('type', '非沿河'), initial_jobs_count=simulator.population.get_population()*10, config_path=simulator.config["data"]["jobs_config_path"])
                    
                    # 恢复居民关联
                    for resident_id, resident_data in town_data.get('residents', {}).items():
                        if resident_id in simulator.residents:
                            simulator.towns.towns[town_name]['residents'][resident_id] = simulator.residents[resident_id]
                            simulator.residents[resident_id].town = town_name
                            simulator.residents[resident_id].job_market = simulator.towns.towns[town_name]['job_market']
                            simulator.towns.towns[town_name]['resident_group'].add_resident(simulator.residents[resident_id])
                            if resident_id in town_data.get('job_market', {}).get('jobs_info', {}).get('employed', {}):
                                simulator.residents[resident_id].employed = True
                                simulator.residents[resident_id].job = town_data['job_market']['jobs_info']['employed'][resident_id]

            # 恢复社交网络
            if state.get('social_network'):
                simulator.social_network = SocialNetwork.from_dict(
                    state.get('social_network', {}), 
                    simulator.residents
                )
            else:
                simulator.social_network = SocialNetwork()
                simulator.social_network.initialize_network(simulator.residents, simulator.towns)
                
            # 为每个城镇的居民群组设置社交网络
            for town_name, town_data in simulator.towns.towns.items():
                resident_group = town_data.get('resident_group')
                if resident_group:
                    resident_group.set_social_network(simulator.social_network)

            # 恢复政府数据
            government_data = state.get('government')
            if government_data:
                simulator.government = Government(
                    map=simulator.map,
                    towns=simulator.towns,
                    military_strength=0,
                    initial_budget=government_data.get('budget'),
                    time=simulator.time,
                    transport_economy=simulator.transport_economy,
                    government_prompt_path=simulator.config["data"]["government_prompt_path"],
                )
                simulator.government.tax_rate = government_data.get('tax_rate')

            # 恢复政府官员
            simulator.government_officials = {}
            officials_data = state.get('government_officials')
            if officials_data and isinstance(officials_data, list):
                shared_pool = government_SharedInformationPool()
                for off_state in officials_data:
                    if off_state.get('personality'):
                        if off_state.get('function'):
                            official = OrdinaryGovernmentAgent(
                                agent_id=off_state.get('agent_id'),
                                government=simulator.government,
                                shared_pool=shared_pool
                            )
                            official.function = off_state.get('function')
                            official.faction = off_state.get('faction')
                        else:
                            official = HighRankingGovernmentAgent(
                                agent_id=off_state.get('agent_id'),
                                government=simulator.government,
                                shared_pool=shared_pool
                            )
                    else:
                        official = InformationOfficer(
                            agent_id=off_state.get('agent_id'),
                            government=simulator.government,
                            shared_pool=shared_pool
                        )
                    official.personality = off_state.get('personality')
                    official.system_message = off_state.get('system_message')
                    simulator.government_officials[official.agent_id] = official
                    # 恢复记忆系统
                    memory_state = off_state.get('memory')
                    if memory_state:
                        official.memory = MemoryManager(
                            agent_id=official.agent_id,
                            model_type=official.model_type,
                            group_type='government',
                            window_size=5
                        )
                        official.memory.set_agent(official)
                        # 恢复聊天历史
                        for msg in memory_state.get('chat_history', []):
                            record = MemoryRecord(
                                message=BaseMessage.make_assistant_message(
                                    role_name='government',
                                    content=msg['content']
                                ) if msg['role'] == 'assistant' else BaseMessage.make_user_message(
                                    role_name='government',
                                    content=msg['content']
                                ),
                                role_at_backend=msg['role']
                            )
                            official.memory.personal_memory.write_record(record)
                        # 恢复长期记忆
                        official.memory.personal_memory.longterm_memory = memory_state.get('longterm_memory', [])
                    simulator.government_officials[official.agent_id] = official
            # 恢复其他基本属性
            simulator.basic_living_cost = state.get('basic_living_cost')
            simulator.average_satisfaction = state.get('average_satisfaction')
            simulator.gdp = state.get('gdp')
            simulator.results = state.get('results')
            simulator.start_time = state.get('start_time')
            simulator.end_time = state.get('end_time')


            
            return simulator
        except Exception as e:
            raise Exception(f"加载缓存失败: {e}")
