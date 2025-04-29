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
from src.agents.rebels import OrdinaryRebel, RebelLeader, InformationOfficer as RebelsInformationOfficer
from src.generator.resident_generate import generate_resident_data, save_resident_data
from src.environment.social_network import SocialNetwork
from src.agents.resident import ResidentGroup
from src.environment.towns import Towns

class Simulator:
    def __init__(self, map, time, job_market, government, government_officials, rebellion, rebels_agents, population, social_network, residents, towns):
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
        # self.resident_groups = {}  # 按城镇分组的居民组
        self.towns = towns
        self.basic_living_cost = 10  # 每年基本生活所需值（单位：两）
        self.results = {
            "years": [],
            "rebellions": [],
            "unemployment_rate": [],
            "population": [],
            "government_budget": [],
            "rebellion_strength": [],
            "average_satisfaction": [],
            "tax_rate": [],
            "basic_living_cost": [],
            "gdp": [],
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

            # 计算GDP和税收
            current_gdp = self.calculate_gdp()
            print(f"当前GDP: {current_gdp}")
            tax_income = current_gdp * self.government.get_tax_rate()
            print(f"税收收入: {tax_income}")
            self.government.budget += tax_income  # 增加政府预算
            print(f"政府预算: {self.government.budget}")


            # 居民出生（次/年）
            if self.time.get_current_quarter() == 1:
                new_count = int(self.population.birth_rate * self.population.get_population())
                new_residents = await self.generate_new_residents(new_count)
                await self.integrate_new_residents(new_residents)
                self.population.birth(new_count)

            # 初始化叛乱计数器
            rebellions = 0

            # 收集政府和叛军的决策
            government_decision = None
            rebellion_decision = None
            # 收集政府决策
            government_config = {
                'agents': self.government_officials,
                'ordinary_type': OrdinaryGovernmentAgent,
                'leader_type': HighRankingGovernmentAgent,
            }
            government_decision = await self.collect_group_decision('government', government_config)
            # 收集叛军决策
            rebellion_config = {
                'agents': self.rebels_agents,
                'ordinary_type': OrdinaryRebel,
                'leader_type': RebelLeader,
            }
            rebellion_decision = await self.collect_group_decision('rebellion', rebellion_config)
            
            # 统一执行决策
            if government_decision:
                self.execute_government_decision(government_decision)
            if rebellion_decision:
                self.execute_rebellion_decision(rebellion_decision)

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

            # 更新平均满意度
            self.average_satisfaction = self.calculate_average_satisfaction()
            # 更新出生率
            self.population.update_birth_rate(self.average_satisfaction)

            # 记录数据
            self.results["years"].append(self.time.get_current_time())
            self.results["rebellions"].append(rebellions)
            self.results["unemployment_rate"].append(self.job_market.get_unemployment_rate(len(self.residents)))
            self.results["population"].append(self.population.get_population())
            self.results["government_budget"].append(self.government.get_budget())
            self.results["rebellion_strength"].append(self.rebellion.get_strength())
            self.results["average_satisfaction"].append(self.calculate_average_satisfaction())
            self.results["tax_rate"].append(self.government.get_tax_rate())
            self.results["basic_living_cost"].append(self.basic_living_cost)
            self.results["gdp"].append(self.calculate_gdp())

            # 打印当前状态
            print(f"年份: {self.time.get_current_time()}, "
                  f"叛乱次数: {rebellions}, "
                  f"人口数量: {self.population.get_population()}, "
                  f"平均满意度: {self.results['average_satisfaction'][-1]:.2f}, "
                  f"税率: {self.results['tax_rate'][-1]*100:.1f}%, "
                  f"基本生活所需值: {self.basic_living_cost}, "
                  f"GDP: {self.results['gdp'][-1]:.2f}")

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

    async def collect_group_decision(self, group_type, config, max_rounds=3):
        """
        收集群体决策
        :param group_type: 群体类型
        :param config: 群体配置
        :param max_rounds: 最大讨论轮数
        :return: 决策结果
        """
        print(f"开始收集 {group_type} 的决策")
        
        # 获取所有普通成员
        ordinary_members = [
            member for member in config['agents'].values()
            if isinstance(member, config['ordinary_type']) and not isinstance(member, InformationOfficer) and not isinstance(member, RebelsInformationOfficer)  
        ]

        if not ordinary_members:
            return None

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

            round_tasks = [
                member.generate_and_share_opinion()
                for member in random.sample(ordinary_members, len(ordinary_members))
            ]
            await asyncio.gather(*round_tasks)

        # 获取信息整理员和领导者
        info_officers = [
            member for member in config['agents'].values()
            if isinstance(member, InformationOfficer) or isinstance(member, RebelsInformationOfficer)
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
                return decision

        return None

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
                    "increase_employment": lambda p: self.government.provide_jobs(budget_allocation=p),
                    "maintain_canal": lambda p: self.government.maintain_canal(budget_allocation=p),
                    "military_support": lambda p: self.government.support_military(budget_allocation=p),
                    "tax_adjustment": lambda p: self.government.adjust_tax_rate(p),
                }
            },
            'rebellion': {
                'actions': {
                    "stage_rebellion": lambda p: self.handle_rebellion(strength_investment=p),
                    "recruit_members": lambda p: self.rebellion.recruit_new_members(resource_investment=p),
                    "maintain_status": lambda p: self.rebellion.maintain_status() if p == 1 else None,
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

            # 执行所有决策动作
            success = True
            for action, param in decision_data.items():
                if action in config[group_type]['actions']:
                    try:
                        config[group_type]['actions'][action](param)
                    except Exception as e:
                        print(f"执行决策 {action} 时出错：{e}")
                        success = False
                else:
                    print(f"未知的决策动作：{action}")
                    success = False

            return success

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

    def calculate_average_satisfaction(self):
        """
        计算所有居民的平均满意度
        :return: 平均满意度（浮点数）
        """
        if not self.residents:
            return 0.0
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())
        return total_satisfaction / len(self.residents)

    def get_basic_living_cost(self):
        """
        获取当前基本生活所需值
        :return: 基本生活所需值（浮点数）
        """
        return self.basic_living_cost

    def adjust_basic_living_cost(self, adjustment):
        """
        调整基本生活所需值
        :param adjustment: 调整值（浮点数，正数表示增加，负数表示减少）
        :return: 调整后的基本生活所需值
        """
        self.basic_living_cost = max(500, self.basic_living_cost + adjustment)  # 确保基本生活所需值不低于500
        print(f"基本生活所需值调整为: {self.basic_living_cost}")
        return self.basic_living_cost


    def calculate_gdp(self):
        """
        计算GDP：所有居民工资总和减去基本生活所需值总和
        :return: GDP值（浮点数）
        """
        # TODO: GDP按照收入法计算：增加值＝劳动者报酬＋生产税净额＋固定资产折旧＋营业盈余 ，不必减去基本生活所需值
        if not self.residents:
            return 0.0
        # 计算所有居民的工资总和
        total_income = sum(resident.income for resident in self.residents.values())
        # total_basic_cost = self.basic_living_cost * len(self.residents)
        # gdp = total_income - total_basic_cost
        gdp = total_income
        return gdp


    def handle_rebellion(self, strength_investment):
        """
        处理叛军袭击事件
        :param strength_investment: 叛军投入的力量
        :return: 是否执行成功
        """
        # 叛军发动袭击
        if self.rebellion.strength < strength_investment:
            print("叛军力量不足以发动叛乱。")
            return False
            
        # 政府进行镇压
        if self.government.suppress_rebellion(strength_investment):
            # 镇压成功，叛军损失大量军事力量和资源
            strength_loss = strength_investment * 0.8  # 损失80%的投入力量
            resource_loss = strength_investment * 0.5  # 损失50%对应的资源
            
            self.rebellion.strength = max(0, self.rebellion.strength - strength_loss)
            self.rebellion.resources = max(0, self.rebellion.resources - resource_loss)
            
            print(f"叛军被镇压，损失军事力量 {strength_loss:.1f}，损失资源 {resource_loss:.1f}")
            return True
        else:
            # 镇压失败，叛军损失少量军事力量，获得大量资源
            strength_loss = strength_investment * 0.2  # 损失20%的投入力量
            resource_gain = strength_investment * 1.5  # 获得150%对应的资源
            
            self.rebellion.strength = max(0, self.rebellion.strength - strength_loss)
            self.rebellion.resources += resource_gain
            
            print(f"叛军袭击成功，损失军事力量 {strength_loss:.1f}，获得资源 {resource_gain:.1f}")
            return True
