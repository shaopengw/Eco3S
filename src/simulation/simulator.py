import asyncio
import json
import random
import pandas as pd
import os
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
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
from src.environment.transport_economy import TransportEconomy

class Simulator:
    def __init__(self, map, time, government, government_officials, rebellion, rebels_agents, population, social_network, residents, towns, transport_economy, climate):
        """
        初始化模拟器类
        :param map: 地图对象
        :param time: 时间对象
        :param government: 政府对象
        :param government_officials: 政府官员列表
        :param rebellion: 叛军对象
        :param rebels_agents: 叛军列表
        :param population: 人口对象
        :param social_network: 社会网络对象
        :param residents: 居民列表
        :param towns: 城镇对象
        :param transport_economy: 运输经济对象
        :param climate: 天气对象
        """
        self.map = map
        self.time = time
        self.government = government
        self.government_officials = government_officials
        self.rebellion = rebellion
        self.rebels_agents = rebels_agents
        self.population = population
        self.social_network = social_network
        self.residents = residents
        self.towns = towns
        self.transport_economy = transport_economy
        self.climate = climate
        self.basic_living_cost = 8  # 每年基本生活所需值（单位：两）
        self.average_satisfaction = None  # 平均满意度（0-1）
        self.gdp = 0  # 国内生产总值（单位：两）
        self.propaganda_prob = 0.1  # 叛军宣传概率（0-1）
        self.propaganda_speech = ""
        self.rebellion_records = 0
        self.results = {
            "years": [],
            "rebellions": [],
            "unemployment_rate": [],
            "population": [],
            "government_budget": [],
            "rebellion_strength": [],
            "rebellion_resources": [],
            "average_satisfaction": [],
            "tax_rate": [],
            "river_navigability": [],
            "gdp": [],
        }
        self.rebellion_history = []  # 存储叛乱历史记录
        
        # 保存初始数据
        self.gdp = self.calculate_gdp()  # 确保先计算初始GDP
        self.average_satisfaction = self.calculate_average_satisfaction()  # 计算初始满意度
        
        self.results["years"].append("初始")
        self.results["rebellions"].append(self.rebellion_records)
        self.results["unemployment_rate"].append(0)  # 初始失业率
        self.results["population"].append(self.population.get_population())
        self.results["government_budget"].append(self.government.get_budget())
        self.results["rebellion_strength"].append(self.rebellion.get_strength())
        self.results["rebellion_resources"].append(self.rebellion.get_resources())
        self.results["average_satisfaction"].append(self.average_satisfaction)
        self.results["tax_rate"].append(self.government.get_tax_rate())
        self.results["river_navigability"].append(self.map.get_navigability())
        self.results["gdp"].append(self.gdp)
        
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
            current_year = self.time.get_current_year()
            start_year = self.time.get_start_time()
            print(f"天气影响因子：{self.climate.get_current_impact(current_year,start_year)}")
            # 更新属性变量
            # 政府
            self.gdp = self.calculate_gdp() # 更新GDP
            self.tax_income = self.gdp * self.government.get_tax_rate() # 计算税收收入
            self.government.budget = round(self.government.budget + self.tax_income, 2) 
            # 叛军
            self.rebellion_income = self.rebellion.get_strength() * 6 # 假设叛军收入为6两/人
            self.rebellion.resources = round(self.rebellion.resources + self.rebellion_income, 2)
            self.rebellion.strength = self.calculate_total_rebels()

            self.average_satisfaction = self.calculate_average_satisfaction() # 更新平均满意度
            self.population.update_birth_rate(self.average_satisfaction) # 更新出生率
            self.rebellion_records = 0
            print(f"GDP：{self.gdp}，税收收入：{self.tax_income}，政府预算：{self.government.budget}")
            print(f"河运价格：{self.transport_economy.river_price}，维护成本：{self.transport_economy.calculate_maintenance_cost(self.map.get_navigability())}")

            # 居民出生（次/年）
            if self.time.get_current_quarter() == 1:
                new_count = int(self.population.birth_rate * self.population.get_population())
                new_residents = await self.generate_new_residents(new_count)
                await self.integrate_new_residents(new_residents)
                self.population.birth(new_count)

            # 收集政府和叛军的决策（每年第一季度）
            if self.time.get_current_quarter() == 1:
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
                # rebellion_decision = '{"propaganda_budget": 0,"stage_rebellion": 1,"target_town": "杭州"}'
                # rebellion_summary = '一致决定发动叛乱'
                # 统一执行决策
                if government_decision:
                    self.execute_government_decision(government_decision)
                if rebellion_decision:
                    self.execute_rebellion_decision(rebellion_decision)

            # 居民行为
            tasks = []
            # 清空上一轮的求职信息
            town_job_requests = defaultdict(list)
            
            for resident_name in list(self.residents.keys()):
                resident = self.residents[resident_name]
                tax_rate = self.government.get_tax_rate()
                # 基于LLM的决策--测试时建议暂时注释
                if resident.job == "叛军":
                    tasks.append(resident.generate_provocative_opinion(self.propaganda_prob, self.propaganda_speech))
                else:
                    tasks.append(resident.decide_action_by_llm(tax_rate, self.basic_living_cost))

                # 更新居民寿命（次/年）
                if self.time.get_current_quarter() == 1:
                    if resident.update_resident_status(self.basic_living_cost):
                        del self.residents[resident_name]
                        self.population.death()
                        continue

            # 并发执行所有居民的行为并收集结果
            if tasks:  # 只在有任务时执行
                results = await asyncio.gather(*tasks)
                
                # 处理返回的结果
                for result in results:
                    if isinstance(result, dict) and "town" in result:
                        # 处理求职请求
                        town_job_requests[result["town"]].append(result)
                    elif isinstance(result, tuple) and len(result) == 4:
                        # 处理带有发言的决策结果
                        select, reason, speech, relation_type = result
                        for resident_id, resident in self.residents.items():
                            if resident.resident_id == select:  # 使用select作为ID匹配
                                # 处理发言传播
                                await self.social_network.spread_speech_in_network(resident_id, speech, relation_type)
                                break
                    elif isinstance(result, tuple) and len(result) == 2:
                        # 叛军发言，传播到社会网络
                        speech, relation_type = result
                        for resident_id, resident in self.residents.items():
                            if resident.resident_id == resident_name:  # 使用resident_name作为ID匹配
                                # 处理发言传播
                                await self.social_network.spread_speech_in_network(resident_id, speech, relation_type)
                                break
            
            # 处理所有城镇的求职信息
            if town_job_requests:
                hiring_results = self.towns.process_town_job_requests(town_job_requests)
                for town_name, hired_residents in hiring_results.items():
                    print(f"城镇 {town_name} 目前录用了 {len(hired_residents)} 名居民")
            
            # 打印每个城镇的求职信息统计--测试用
            for town, requests in town_job_requests.items():
                print(f"\n城镇 {town} 的求职信息:")
                job_counts = {}
                for req in requests:
                    job = req["desired_job"]
                    job_counts[job] = job_counts.get(job, 0) + 1
                for job, count in job_counts.items():
                    print(f"- {job}: {count}人求职")
            
            # 打印城镇详细状态---测试用
            # print("\n各城镇详细状态：")
            # self.towns.print_towns_status()
            # self.towns.print_towns()
                
            # for resident_name in list(self.residents.keys()):  #测试用-展示居民情况
            #     resident = self.residents[resident_name]
            #     resident.print_resident_status()
            # self.get_rebels_statistics()

            # 社交网络类————测试
            # for resident_name in list(self.residents.keys()):
            #     resident = self.residents[resident_name]
            #     social_network = resident.get_social_network()
            #     social_network.calculate_speech_probability(resident.resident_id, self.population.get_population())

            # 在每年第一季度进行结算更新
            if self.time.get_current_quarter() == 1:

                # 更新运河价格与状态
                self.transport_economy.calculate_river_price(self.map.get_navigability())
                climate_impact_factor = self.climate.get_current_impact(self.time.get_current_year(),self.time.get_start_time())
                self.map.decay_river_condition_naturally(climate_impact_factor)

                # 更新就业市场
                old_navigability = self.results["river_navigability"][len(self.results["years"])-1]
                current_navigability = self.map.get_navigability()
                change_rate = (current_navigability - old_navigability) / old_navigability if old_navigability != 0 else 0
                self.towns.adjust_job_market(change_rate, self.residents)

                # 每3-5年更新一次社交网络
                current_year = self.time.get_current_year()
                if current_year % random.randint(3, 5) == 0:
                    self.social_network.update_network_edges()  # 更新社交网络边
                
                self.propaganda_prob = 0

            total_unemployment_rate = self.calculate_total_unemployment_rate()
            # 记录数据
            self.results["years"].append(self.time.get_current_time())
            self.results["rebellions"].append(self.rebellion_records)
            self.results["unemployment_rate"].append(total_unemployment_rate)
            self.results["population"].append(self.population.get_population())
            self.results["government_budget"].append(self.government.get_budget())
            self.results["rebellion_strength"].append(self.rebellion.get_strength())
            self.results["rebellion_resources"].append(self.rebellion.get_resources())
            self.results["average_satisfaction"].append(self.average_satisfaction)
            self.results["tax_rate"].append(self.government.get_tax_rate())
            self.results["river_navigability"].append(self.map.get_navigability())
            self.results["gdp"].append(self.gdp)

            # 打印当前状态
            print(f"年份: {self.time.get_current_time()}, "
                  f"叛乱次数: {self.rebellion_records}, "
                  f"人口数量: {self.population.get_population()}, "
                  f"失业率: {self.results['unemployment_rate'][-1]:.2f}%, "
                  f"平均满意度: {self.results['average_satisfaction'][-1]:.2f}, "
                  f"税率: {self.government.get_tax_rate():.2f}, "
                  f"GDP: {self.results['gdp'][-1]:.2f}, "
                  f"叛军强度: {self.results['rebellion_strength'][-1]}, "
                  f"运河通航能力: {self.map.get_navigability():.2f}"
            )
            # 在时间步结束前，总结本次决策结果
            if self.time.get_current_quarter() == 1:
                if government_decision or rebellion_decision:
                    changes_summary = self.summarize_time_step_results()
                    # 存储到政府和叛军的记忆中
                    if government_decision:
                        await self.store_decision_memory(
                            'government', 
                            government_decision,
                            changes_summary
                        )
                    if rebellion_decision:
                        await self.store_decision_memory(
                            'rebellion', 
                            rebellion_decision,
                            changes_summary
                        )

            if self.time.get_current_quarter() == 4 and self.map.get_navigability() < 0.2:
                print(Back.RED + f"运河因通航能力过低（{self.map.get_navigability()}）而废弃，提前结束模拟" + Back.RESET)
                break
            else:
                self.time.step()
            # self.time.step()

        self.end_time = datetime.now()  # 记录模拟结束时间
        self.display_total_simulation_time()
        self.social_network.plot_degree_distribution()
        # self.social_network.visualize()

    def display_total_simulation_time(self):
        """
        显示总模拟时间
        """
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")

    async def collect_group_decision(self, group_type, config, max_rounds=2):
        """
        收集群体决策
        :param group_type: 群体类型
        :param config: 群体配置
        :param max_rounds: 最大讨论轮数
        :return: 决策结果
        """
        print(f"开始收集 {group_type} 的决策")

        # 获取群体决策配置
        try:
            with open('config/simulation_config.yaml', 'r', encoding='utf-8') as f:
                sim_config = yaml.safe_load(f)
                group_decision_config = sim_config['simulation'].get('group_decision', {})
                # 根据群体类型获取对应的配置
                group_config = group_decision_config.get(group_type, {})
                group_decision_enabled = group_config.get('enabled', True)
                configured_max_rounds = group_config.get('max_rounds', 2)
        except Exception as e:
            print(f"读取群体决策配置失败，使用默认值：{e}")
            group_decision_enabled = True
            configured_max_rounds = max_rounds

        # 计算决策参数
        _, government_salary = self.calculate_total_salaries()
        if group_type == 'rebellion':
            group_stats = self.get_rebels_statistics()
            group_param = group_stats
        else:
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
            and not isinstance(member, RebelsInformationOfficer)
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
            or isinstance(member, RebelsInformationOfficer)
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
        _, salary = self.calculate_total_salaries()
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
            
            # 政府决策处理
            if group_type == "government":
                # 获取决策键并随机打乱顺序
                decision_keys = list(decision_data.keys())
                random.shuffle(decision_keys)

                # 按随机顺序处理政府决策
                for key in decision_keys:
                    if key == "maintenance_investment":
                        self.government.maintain_canal(
                            maintenance_investment=decision_data["maintenance_investment"]
                        )
                    elif key == "transport_ratio":
                        self.government.handle_transport_decision(
                            transport_ratio=decision_data["transport_ratio"]
                        )
                    elif key == "public_budget":
                        self.government.handle_public_budget(budget_allocation=decision_data["public_budget"], salary=salary)
                    elif key == "military_support":
                        self.government.support_military(budget_allocation=decision_data["military_support"])
                    elif key == "tax_adjustment":
                        self.government.adjust_tax_rate(decision_data["tax_adjustment"])

            # 叛军决策处理
            elif group_type == "rebellion":
                if decision_data.get("propaganda_budget", 0) > 0:
                    speech_count = decision_data["propaganda_budget"] / 10  # 每10两多一名叛军发言
                    self.calculate_propaganda_prob(speech_count)
                # 处理多个目标城镇
                if "target_towns" in decision_data:
                    for town in decision_data["target_towns"]:
                        strength = town.get("stage_rebellion", 0)
                        target = town.get('town_name', None)
                        self.propaganda_speech = decision_data.get("provocative_speech", "")
                        if target and strength > 0:
                            self.handle_rebellion(strength_investment=strength, target_town=target)
                else:
                    # 如果没有多个目标城镇，处理单个目标城镇
                    if decision_data.get("stage_rebellion", 0) > 0:
                        strength = decision_data["stage_rebellion"]
                        target = decision_data.get('target_town', None)
                        self.propaganda_speech = decision_data.get("provocative_speech", "")
                        if target:
                            self.handle_rebellion(strength_investment=strength, target_town=target)
            # 检查是否有未知动作
            for action in decision_data:
                if action not in ["public_budget", "transport_ratio", "maintenance_investment", 
                                "military_support", "tax_adjustment", "stage_rebellion", 
                                "propaganda_budget", "target_town", "target_towns", "provocative_speech"]:
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
        os.makedirs(os.path.dirname(filename), exist_ok=True)
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
        )

        # 分配新ID
        used_ids = set(self.residents.keys()) | set(self.social_network.hetero_graph.graph.nodes())
        new_id = max(used_ids) + 1 if used_ids else 1
        
        new_residents_with_new_ids = {}
        for i, (_, resident) in enumerate(new_residents.items()):
            while new_id in used_ids:  # 确保ID不重复
                new_id += 1
            resident.resident_id = new_id
            new_residents_with_new_ids[new_id] = resident
            used_ids.add(new_id)
            new_id += 1
            
        return new_residents_with_new_ids

    async def integrate_new_residents(self, new_residents):
        """将新居民整合到系统中"""
        if not new_residents:
            return

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

    def calculate_total_unemployment_rate(self):
        """
        计算所有城镇的平均失业率
        :return: 平均失业率（浮点数）
        """
        total_employed = 0
        total_residents = 0
        
        # 遍历所有城镇
        for town_name, town_data in self.towns.towns.items():
            # 获取该城镇的就业市场
            job_market = town_data['job_market']
            if job_market:
                # 计算该城镇的就业人数
                town_employed = sum(len(info["employed"]) for job, info in job_market.jobs_info.items() if job != "叛军")
                total_employed += town_employed
                # 获取该城镇的居民总数
                total_residents += len(town_data['residents'])
        
        # 计算总体失业率
        if total_residents == 0:
            return 0.0
        print(f"总体就业率: {total_employed} / {total_residents} = {total_employed / total_residents:.2f}")
        unemployment_rate = (1.0 - (total_employed / total_residents)) * 100
        return unemployment_rate


    def calculate_gdp(self):
        """
        计算GDP：所有居民收入总和减去基本生活所需值总和
        :return: GDP值（浮点数）
        """
        # GDP按照收入法计算：增加值＝劳动者报酬＋生产税净额＋固定资产折旧＋营业盈余 ，不必减去基本生活所需值
        if not self.residents:
            return 0.0
        # 计算所有居民的收入总和
        total_income = sum(resident.income for resident in self.residents.values() if resident.job != "叛军")
        gdp = total_income
        return gdp

    def handle_rebellion(self, strength_investment, target_town=None):
        """
        处理叛军叛乱事件（基于非线性优势损耗模型+随机扰动+极端优势保护）
        :param strength_investment: 叛军投入的力量
        :param target_town: 目标城镇名称
        :return: (是否成功, 政府军损耗, 叛军损耗)
        """
        # 参数配置
        BASE_LOSS_RATE = 0.1      # 基准损耗率c
        DECAY_FACTOR = 0.7        # 衰减系数d
        MAX_RATIO = 5             # 极端优势阈值α_max
        MIN_LOSS_RATE = 0.01      # 优势方最低损耗率
        RANDOM_RANGE = 0.03       # 随机扰动范围ε
        
        # 验证目标城镇
        if target_town and target_town not in self.towns.towns:
            print(f"目标城镇 {target_town} 不存在")
            return False
        if strength_investment <= 0:
            return False
        
        success = False
        # 获取战斗双方兵力
        town_data = self.towns.towns[target_town]
        town_defense = len(town_data['job_market'].jobs_info["官员及士兵"]["employed"])
        town_rebels = len(town_data['job_market'].jobs_info["叛军"]["employed"])
        rebel_strength = strength_investment
        gov_loss_rate = 0

        if town_rebels < strength_investment:
            print(f"目标城镇 {target_town} 叛军数量不足，未能成功发起叛乱")
            return False
        elif town_defense == 0:
            success = True
            loot_ratio = strength_investment / self.government.military_strength
            gov_loss_budget = int(self.government.budget * loot_ratio)
            self.rebellion.resources += gov_loss_budget

            #更新状态
            self.rebellion_records += 1
            print(f"\n=== 第 {self.rebellion_records} 次叛乱 ===")
            print(f"叛乱成功")
            print(f"战场：{target_town}")
            print(f"兵力对比：政府军 {town_defense} vs 叛军 {rebel_strength}")
            print(f"叛军获得资源{gov_loss_budget}")
            print(f"\n===========================")
            
            # 记录叛乱信息
            rebellion_info = {
                "id": self.rebellion_records,
                "time": self.time.get_current_time(),
                "target_town": target_town,
                "success": True,
                "rebel_strength": rebel_strength,
                "town_defense": town_defense,
                "rebel_loss": 0,
                "gov_loss": 0,
                "resource_change": gov_loss_budget
            }
            self.rebellion_history.append(rebellion_info)
        else:
            # 战斗损耗计算
            strength_ratio = town_defense / rebel_strength  # α = G/R
            success = True if strength_ratio < 1 else False

            
            # 1. 非线性损耗比例计算
            if strength_ratio > MAX_RATIO:
                # 极端优势保护(当兵力差距极大时，优势方损耗接近零)
                gov_loss_rate = MIN_LOSS_RATE
                rebel_loss_rate = BASE_LOSS_RATE * (MAX_RATIO ** DECAY_FACTOR)
            else:
                gov_loss_rate = BASE_LOSS_RATE / (strength_ratio ** DECAY_FACTOR)
                rebel_loss_rate = BASE_LOSS_RATE * (strength_ratio ** DECAY_FACTOR)
            
            # 2. 添加随机扰动
            random_factor = random.uniform(-RANDOM_RANGE, RANDOM_RANGE)
            gov_loss_rate += random_factor
            rebel_loss_rate += random_factor
            
            # 3. 计算实际损耗
            gov_loss = int(gov_loss_rate * town_defense)
            rebel_loss = int(rebel_loss_rate * rebel_strength)
            self.handle_army_loss("官员及士兵", gov_loss, target_town)
            self.handle_army_loss("叛军", rebel_loss, target_town)

            # 4. 计算叛军经济
            if success:
                loot_ratio = gov_loss / self.government.military_strength
                gov_loss_budget = int(self.government.budget * loot_ratio)
                self.rebellion.resources += gov_loss_budget
            else:
                loot_ratio = rebel_loss / self.government.military_strength
                rebel_loss_resources = int(self.rebellion.resources * loot_ratio)
                self.rebellion.resources -= rebel_loss_resources

            #更新状态
            self.rebellion_records += 1
            print(f"\n=== 第 {self.rebellion_records} 次叛乱 ===")
            print(f"叛乱成功" if success else f"叛乱失败")
            print(f"战场：{target_town}")
            print(f"兵力对比：政府军 {town_defense} vs 叛军 {rebel_strength}")
            print(f"损耗率：政府军 {gov_loss_rate*100:.1f}% | 叛军 {rebel_loss_rate*100:.1f}%")
            print(f"实际损耗：政府军 -{gov_loss} | 叛军 -{rebel_loss}")
            print(f"叛军获得资源{gov_loss_budget} " if success else f"叛军失去资源{rebel_loss_resources}")
            print(f"\n===========================")
    
        return True
    
    def handle_army_loss(self, army_type, actual_loss, target_town):
        """处理军队损耗"""
        # 从目标城镇中选择要移除的军队
        all_army_residents = []
        if target_town:
            town_data = self.towns.towns[target_town]
            if town_data.get('job_market'):
                target_army = [resident_id for resident_id in town_data['job_market'].jobs_info[army_type]["employed"]]
                all_army_residents.extend(target_army)
            
        # 从收集到的军队中随机选择要移除的人数
        if all_army_residents:
            selected_army = random.sample(all_army_residents, min(actual_loss, len(all_army_residents)))
            # 注销选中的军队居民
            for army_id in selected_army:
                if army_id in self.residents:
                    resident = self.residents[army_id]
                    resident.handle_death()
                    del self.residents[army_id]
                    self.population.death()
                    print(f"{army_type} {army_id} 战死，失去生命")

    def calculate_total_rebels(self):
        """
        计算叛军总数
        """
        total_rebels = 0
        
        # 遍历所有城镇
        for town_name, town_data in self.towns.towns.items():
            # 获取该城镇的就业市场
            job_market = town_data['job_market']
            if job_market:
                rebels_count = len(job_market.jobs_info["叛军"]["employed"])
                total_rebels += rebels_count
        
        return total_rebels

    def summarize_time_step_results(self):
        """总结当前时间步的各项指标变化"""
        current_idx = len(self.results["years"]) - 1
        if current_idx <= 0:
            return {}
        
        # 计算各项指标的变化率
        changes = {
            "人口变化率": self.calculate_change_rate("population", current_idx),
            "GDP变化率": self.calculate_change_rate("gdp", current_idx),
            "政府预算变化率": self.calculate_change_rate("government_budget", current_idx),
            "叛军力量变化率": self.calculate_change_rate("rebellion_strength", current_idx),
            "平均满意度变化": self.calculate_change_rate("average_satisfaction", current_idx),
            "失业率变化": self.calculate_change_rate("unemployment_rate", current_idx),
            "叛乱次数": self.results["rebellions"][current_idx],
            "叛军资源变化": self.calculate_change_rate("rebellion_resources", current_idx),
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
                f"- 叛军力量变化率: {'+' if changes_summary.get('叛军力量变化率', 0) > 0 else ''}{changes_summary.get('叛军力量变化率', 0):.2%}\n"
                f"- 平均满意度变化: {'+' if changes_summary.get('平均满意度变化', 0) > 0 else ''}{changes_summary.get('平均满意度变化', 0):.2%}\n"
                f"- 失业率变化: {'+' if changes_summary.get('失业率变化', 0) > 0 else ''}{changes_summary.get('失业率变化', 0):.2%}\n"
                f"- 叛乱次数: {changes_summary.get('叛乱次数', 0)}"
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
        
        elif group_type == 'rebellion':
            memory_content = (
                f"时间: {self.time.get_current_year()}\n"
                f"决策内容: {decision}\n"
                f"执行结果:\n"
                f"- 叛军力量变化率: {'+' if changes_summary.get('叛军力量变化率', 0) > 0 else ''}{changes_summary.get('叛军力量变化率', 0):.2%}\n"
                f"- 叛军资源变化: {'+' if changes_summary.get('叛军资源变化', 0) > 0 else ''}{changes_summary.get('叛军资源变化', 0):.2%}\n"
            )
            
            # 存储到所有叛军成员的记忆中
            for rebel in self.rebels_agents.values():
                if not isinstance(rebel, InformationOfficer):
                    await rebel.memory.write_record(
                        role_name=rebel.__class__.__name__,
                        content=memory_content,
                        is_user=False,
                        round_num=self.time.get_current_time(),
                        store_in_shared=True
                    )


    def get_rebels_statistics(self):
        """
        返回每个城市的叛军和官员数量统计
        :return: 包含城镇统计信息的列表，每个元素为字典，包含城镇名、叛军数和官员数
        """
        total_rebels = 0
        stats = []
        
        for town_name, town_data in self.towns.towns.items():
            town_job_market = town_data.get('job_market')
            if town_job_market:
                # 获取叛军统计
                rebel_total, rebel_count, salary = town_job_market.get_job_statistics("叛军")
                # 获取官员统计
                official_total, official_count, salary = town_job_market.get_job_statistics("官员及士兵")
                total_rebels += rebel_count
                
                # 添加到统计列表
                stats.append({
                    "town_name": town_name,
                    "rebel_count": rebel_count,
                    "official_count": official_count
                })
        return stats

    def calculate_total_salaries(self):
        """
        计算所有城镇的叛军和其他职业总收入
        :return: (叛军总收入, 其他职业总收入)
        """
        total_rebel_salary = 0
        total_other_salary = 0
        
        for town_name, town_data in self.towns.towns.items():
            if town_data.get('job_market'):
                total_rebel_salary += town_data['job_market'].get_rebel_total_salary()
                total_other_salary += town_data['job_market'].get_other_total_salary()
        
        return total_rebel_salary, total_other_salary
    
    def calculate_propaganda_prob(self, speech_count):
        """计算普通叛军发表煽动言论的概率"""
        total_rebels = self.rebellion.get_strength()
        if total_rebels == 0:
            self.propaganda_prob = 0.0
        else:
            self.propaganda_prob = round(speech_count / total_rebels, 2)
            self.propaganda_prob = max(0.0, min(1.0, self.propaganda_prob))  # 确保概率在0到1之间