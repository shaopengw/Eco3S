import asyncio
import json
import random
from datetime import datetime, timedelta
from colorama import Back
from src.agents.resident_agent_generator import (generate_canal_agents)
from src.agents.government import (
    OrdinaryGovernmentAgent, 
    HighRankingGovernmentAgent,
    InformationOfficer
)
from src.agents.rebels import OrdinaryRebel, RebelLeader
from src.generator.resident_generate import generate_resident_data, save_resident_data
from src.environment.social_network import SocialNetwork
from src.agents.resident import ResidentGroup
from src.environment.towns import Towns

class Simulator:
    def __init__(self, map, time, job_market, government, government_officials, rebellion, rebels_agents, population, social_network, residents,towns):
        """
        初始化模拟器类
        :param map: 地图对象
        :param time: 时间对象
        :param job_market: 就业市场对象
        :param government: 政府对象
        :param government_officials: 政府官员列表
        :param rebellion: 叛军对象
        :param rebels_agents: 叛军列表
        :param population: 人口对象
        :param social_network: 社会网络对象
        :param residents: 居民列表
        """
        self.map = map
        self.time = time
        self.job_market = job_market
        self.government = government
        self.government_officials = government_officials
        self.rebellion = rebellion
        self.rebels_agents = rebels_agents
        self.population = population
        self.social_network = social_network
        self.residents = residents
        # self.resident_groups = {}  # 新增：按城镇分组的居民组
        self.towns = towns
        self.results = {
            "years": [],
            "rebellions": [],
            "unemployment_rate": [],
            "population": [],
            "government_budget": [],
            "rebellion_strength": [],
        }
        self.start_time = None  # 用于记录模拟开始时间
        self.end_time = None    # 用于记录模拟结束时间

    async def run(self):
        """
        运行模拟
        """
        self.start_time = datetime.now()  # 记录模拟开始时间
        while not self.time.is_end():
            # 打印当前时间步信息
            print(Back.GREEN + f"年份:{self.time.get_current_time()}" + Back.RESET)

            # 居民出生（次/年）
            if self.time.get_current_quarter() == 1:
                new_count = int(self.population.birth_rate * self.population.get_population())
                new_residents = await self.generate_new_residents(new_count)
                await self.integrate_new_residents(new_residents)
                self.population.birth(new_count)
            
            # 基于LLM的决策--测试时建议暂时注释
            await self.process_group_decision('government') # 政府行为
            await self.process_group_decision('rebellion') # 叛军行为

            rebellions = 0

            # 居民行为
            tasks = []
            for resident_name in list(self.residents.keys()):
                resident = self.residents[resident_name]
                # tasks.append(resident.decide_action_by_llm())  # 基于LLM的决策--测试时建议暂时注释
                
                # 更新居民寿命（次/年）
                if self.time.get_current_quarter() == 1:
                    if resident.update_lifespan() == 0:
                        del self.residents[resident_name]  # 从居民列表中删除逝世的居民
                        self.population.death()
                        continue  # 如果居民已死亡，跳过添加任务
            
            # 并发执行所有居民的行为
            if tasks:  # 只在有任务时执行
                await asyncio.gather(*tasks)

            # 记录数据
            self.results["years"].append(self.time.get_current_time())
            self.results["rebellions"].append(rebellions)
            self.results["unemployment_rate"].append(self.job_market.get_unemployment_rate(len(self.residents)))
            self.results["population"].append(self.population.get_population())
            self.results["government_budget"].append(self.government.get_budget())
            self.results["rebellion_strength"].append(self.rebellion.get_strength())

            # 打印当前状态
            print(f"年份: {self.time.get_current_time()}, 叛乱次数: {rebellions}, 人口数量: {self.population.get_population()}")
            
            # 推进时间
            self.time.step()

        self.end_time = datetime.now()  # 记录模拟结束时间
        self.display_total_simulation_time()
        # self.social_network.visualize()

    def display_total_simulation_time(self):
        """
        显示总模拟时间
        """
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")

    async def process_group_decision(self, group_type, activate_prob=0.8, max_rounds=3):
        """
        通用决策流程：
        1. 第一轮：所有成员异步发表初始意见
        2. 后续轮次：基于之前的讨论内容发表见解
        3. 信息整理员整理讨论内容
        4. 领导者做出决策
        """
        # 根据群体类型获取相应的配置
        config = {
            'government': {
                'agents': self.government_officials,
                'ordinary_type': OrdinaryGovernmentAgent,
                'leader_type': HighRankingGovernmentAgent,
                'execute_func': self.execute_government_decision
            },
            'rebellion': {
                'agents': self.rebels_agents,
                'ordinary_type': OrdinaryRebel,
                'leader_type': RebelLeader,
                'execute_func': self.execute_rebellion_decision
            }
        }[group_type]

        # 获取所有普通成员
        ordinary_members = [
            member for member in config['agents'].values()
            if isinstance(member, config['ordinary_type']) and not isinstance(member, InformationOfficer)
        ]

        if ordinary_members and random.random() < activate_prob:
            shared_pool = list(config['agents'].values())[0].shared_pool
            
            # 第一轮：所有成员异步发表初始意见
            first_round_tasks = [
                member.generate_and_share_opinion()
                for member in random.sample(ordinary_members, len(ordinary_members))
            ]
            await asyncio.gather(*first_round_tasks)

            # 后续轮次：基于之前的讨论内容发表见解
            for round_num in range(2, max_rounds + 1):
                if shared_pool.is_ended():
                    break
                    
                # 随机打乱发言顺序
                round_tasks = [
                    member.generate_and_share_opinion()
                    for member in random.sample(ordinary_members, len(ordinary_members))
                ]
                await asyncio.gather(*round_tasks)

            # 获取信息整理员和领导者
            info_officers = [
                member for member in config['agents'].values()
                if isinstance(member, InformationOfficer)
            ]
            leaders = [
                member for member in config['agents'].values()
                if isinstance(member, config['leader_type'])
            ]

            # 处理讨论结果
            if info_officers and leaders and shared_pool.is_ended():
                summary = await info_officers[0].summarize_discussions()
                if summary:
                    decision = await leaders[0].make_decision(summary, self.time.get_current_time())
                    if decision:
                        config['execute_func'](decision)

    def execute_government_decision(self, decision):
        """执行政府决策"""
        return self.execute_decision(decision, 'government')

    def execute_rebellion_decision(self, decision):
        """执行叛军决策"""
        return self.execute_decision(decision, 'rebellion')

    def execute_decision(self, decision, group_type):
        """
        通用决策执行函数
        :param decision: 决策内容
        :param group_type: 群体类型，'government' 或 'rebellion'
        :return: 是否执行成功
        """
        # 定义决策配置
        config = {
            'government': {
                'actions': {
                    "增加就业": lambda p: self.government.provide_jobs(budget_allocation=p),
                    "维护运河": lambda p: self.government.maintain_canals(budget_allocation=p),
                    "提供公共服务": lambda p: self.government.provide_public_services(budget_allocation=p),
                    "军需拨款": lambda p: self.government.support_military(budget_allocation=p)
                }
            },
            'rebellion': {
                'actions': {
                    "袭击政府设施": lambda p: self.rebellion.attack_government_facility(strength_investment=p),
                    "招募新成员": lambda p: self.rebellion.recruit_new_members(resource_investment=p),
                    "争取民众支持": lambda p: self.rebellion.gain_public_support(resource_investment=p),
                    "撤退": lambda _: self.rebellion.retreat()
                }
            }
        }

        def extract_json_from_text(text):
            """从文本中提取JSON内容"""
            import re
            json_pattern = r'\{[^{}]*\}'
            matches = re.findall(json_pattern, text)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            return None

        def parse_decision(decision_text, max_retries=3):
            """解析决策内容，支持重试"""
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
                        # 这里可以添加重新调用LLM的逻辑
                        continue
                    else:
                        print("达到最大重试次数，决策执行失败")
                        return None

        try:
            # 解析决策内容
            decision_data = parse_decision(decision)
            if not decision_data:
                return False

            action = decision_data.get("action")
            param = decision_data.get("params")

            # 执行决策
            if action in config[group_type]['actions']:
                config[group_type]['actions'][action](param)
                return True
            else:
                print(f"未知的决策动作：{action}")
                return False

        except Exception as e:
            print(f"执行决策时出错：{e}")
            return False

    def save_results(self, filename="data/simulation_results.csv"):
        """
        保存模拟结果到CSV文件
        :param filename: 文件名
        """
        import pandas as pd
        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False)
        print(f"模拟结果已保存至 {filename}")

    def initialize_resident_social_network(self):
        """
        初始化居民的社交网络访问
        """
        # 为每个居民设置社交网络引用
        for resident in self.residents.values():
            resident.social_network = self.social_network

    async def generate_new_residents(self, count):
        """生成新居民并初始化"""
        # 生成居民数据
        resident_data = generate_resident_data(count)
        new_resident_info_path = 'experiment_dataset/resident_data/new_resident_data.json'
        save_resident_data(resident_data, new_resident_info_path)
        
        # 生成居民实例
        new_residents = await generate_canal_agents(
            resident_info_path=new_resident_info_path,
            map=self.map,
            job_market=self.job_market,
        )
        
        # 分配新ID
        offset = max(self.residents.keys()) + 1 if self.residents else 1
        new_residents_with_new_ids = {}
        for i, (_, resident) in enumerate(new_residents.items()):
            new_id = offset + i
            resident.resident_id = new_id  # 直接修改 ID
            new_residents_with_new_ids[new_id] = resident
        return new_residents_with_new_ids

    async def integrate_new_residents(self, new_residents):
        """将新居民整合到系统中"""
        # 更新全局居民列表
        self.residents.update(new_residents)
        print(f"{len(new_residents)} 名新居民已出生")
        
        # 添加到城镇
        for resident in new_residents.values():
            if resident.town:
                self.towns.add_resident(resident, resident.town)
        print("新居民已加入各自城镇")
        
        # 添加到社交网络
        if new_residents:
            self.social_network.add_new_residents(new_residents)
            print(f"{len(new_residents)} 名新居民已加入社交网络")
            self.social_network.visualize()