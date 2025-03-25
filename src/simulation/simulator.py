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

class Simulator:
    def __init__(self, map, time, job_market, government, government_officials, rebellion, rebels_agents, population, social_network, residents):
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

            # 推进时间
            self.time.step()

            # 居民出生（次/年）
            if self.time.get_current_quarter() == 1:
                new_residents_count = int(self.population.birth_rate * self.population.get_population())
                # 新居民出生
                resident_data = generate_resident_data(new_residents_count)
                new_resident_info_path = 'experiment_dataset/resident_data/new_resident_data.json'
                save_resident_data(resident_data, new_resident_info_path)
                print(f"生成了{new_residents_count} 名新居民数据")
                
                new_residents = await generate_canal_agents(
                    resident_info_path=new_resident_info_path,
                    map=self.map,
                    job_market=self.job_market,
                )
                
                # 修改新居民的编号，确保不重复
                offset = max(self.residents.keys()) + 1 if self.residents else 1
                new_residents_with_new_ids = {}
                for i, (_, resident) in enumerate(new_residents.items()):
                    new_id = offset + i
                    resident.resident_id = new_id  # 更新居民的ID
                    new_residents_with_new_ids[new_id] = resident
                
                # 更新居民字典
                self.residents.update(new_residents_with_new_ids)
                self.population.birth(new_residents_count)
                print(f"{len(new_residents)} 名新居民已出生")
                
                # 生成新居民后添加到社交网络
                if new_residents_with_new_ids:
                    self.social_network.add_new_residents(new_residents_with_new_ids)
                    print(f"{len(new_residents_with_new_ids)} 名新居民已加入社交网络")
                    # self.social_network.visualize()
            
            # 基于LLM的决策--测试时建议暂时注释
            await self.government_decision_process() # 政府行为
            # await self.rebellion_decision_process() # 叛军行为

            rebellions = 0

            # 居民行为
            tasks = []
            for resident_name in list(self.residents.keys()):  # 使用 list() 确保在遍历时不会出错
                resident = self.residents[resident_name]
                # tasks.append(resident.decide_action_by_llm())  # 基于LLM的决策--测试时建议暂时注释
            # 并发执行所有居民的行为
            await asyncio.gather(*tasks)

            # 更新居民寿命（次/年）
            for resident_name in list(self.residents.keys()):
                resident = self.residents[resident_name]
                if self.time.get_current_quarter() == 1:
                    if resident.update_lifespan() == 0:
                        del self.residents[resident_name]  # 从居民列表中删除逝世的居民
                        self.population.death()

            # 记录数据
            self.results["years"].append(self.time.get_current_time())
            self.results["rebellions"].append(rebellions)
            self.results["unemployment_rate"].append(self.job_market.get_unemployment_rate(len(self.residents)))
            self.results["population"].append(self.population.get_population())
            self.results["government_budget"].append(self.government.get_budget())
            self.results["rebellion_strength"].append(self.rebellion.get_strength())

            # 打印当前状态
            print(f"年份: {self.time.get_current_time()}, 叛乱次数: {rebellions}, 人口数量: {self.population.get_population()}")

            # 模拟时间步延迟（可选）
            await asyncio.sleep(1)  # 模拟每秒推进一个时间步

        self.end_time = datetime.now()  # 记录模拟结束时间
        self.display_total_simulation_time()
        self.social_network.visualize()

    def display_total_simulation_time(self):
        """
        显示总模拟时间
        """
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")

    async def government_decision_process(self, activate_prob=0.8):
        """
        政府决策流程：
        1. 随机触发普通官员从共享信息池中获取信息并发表看法
        2. 等待讨论结束
        3. 信息整理官整理讨论内容
        4. 高级官员做出决策
        5. 执行决策
        :param activate_prob: 触发官员发表看法的概率（默认 80%）
        """
        # 1. 随机触发普通官员从共享信息池中获取信息并发表看法
        ordinary_officials = [
            official for official in self.government_officials.values()
            if isinstance(official, OrdinaryGovernmentAgent) and not isinstance(official, InformationOfficer)
        ]

        for official in ordinary_officials:
            if random.random() < activate_prob:
                await official.generate_and_share_opinion()

        # 2. 获取信息整理官
        info_officers = [
            official for official in self.government_officials.values()
            if isinstance(official, InformationOfficer)
        ]

        # 3. 获取高级官员
        high_ranking_officials = [
            official for official in self.government_officials.values()
            if isinstance(official, HighRankingGovernmentAgent)
        ]

        if info_officers and high_ranking_officials:
            # 等待讨论结束或达到最大讨论数
            shared_pool = list(self.government_officials.values())[0].shared_pool
            if shared_pool.is_ended():
                # 让信息整理官整理讨论内容
                summary = await info_officers[0].summarize_discussions()
                # # 将总结写入共享信息池
                # await shared_pool.add_discussion(f"信息整理总结：{summary}")

                # 高级官员根据整理后的内容做出决策
                decision = await high_ranking_officials[0].make_decision(summary)
                if decision:
                    # 执行决策
                    self.execute_government_decision(decision)

    def execute_government_decision(self, decision):
        """
        执行高级官员的决策
        :param decision: 高级官员的决策内容，格式为 JSON，例如：{"action": "维护运河", "参数": 2000000}
        """
        try:
            # 解析决策内容
            decision_data = json.loads(decision)  # 将 JSON 字符串解析为字典
            action = decision_data.get("action")
            param = decision_data.get("params")

            if action == "增加就业":
                self.government.provide_jobs(budget_allocation=param)
            elif action == "维护运河":
                self.government.maintain_canals(budget_allocation=param)
            elif action == "提供公共服务":
                self.government.provide_public_services(budget_allocation=param)
            elif action == "军需拨款":
                self.government.support_military(budget_allocation=param)
            else:
                print(f"未知的决策动作：{action}")
        except json.JSONDecodeError:
            print("决策内容格式错误，无法解析 JSON。")
        except Exception as e:
            print(f"执行决策时出错：{e}")

    async def rebellion_decision_process(self):
        """
        叛军决策流程：
        1. 普通叛军发表意见
        2. 普通叛军互相讨论
        3. 叛军头子做出决策
        4. 执行决策
        """
        # 1. 普通叛军发表意见
        ordinary_rebels = [rebel for rebel in self.rebels_agents.values() if isinstance(rebel, OrdinaryRebel)]
        print(f"找到 {len(ordinary_rebels)} 位普通叛军")  # 输出普通叛军的数量
        
        for rebel in ordinary_rebels:
            opinion = await rebel.generate_opinion()
            rebel.express_opinion(opinion)

        # 2. 普通叛军互相讨论
        discussion_report = ""
        if len(ordinary_rebels) > 1:
            discussion_report = ordinary_rebels[0].discuss_with_other_rebels(ordinary_rebels[1:])

        # 3. 叛军头子做出决策
        rebel_leaders = [rebel for rebel in self.rebels_agents.values() if isinstance(rebel, RebelLeader)]
        if rebel_leaders:
            decision = rebel_leaders[0].make_decision(discussion_report)

            # 4. 执行决策
            self.execute_rebellion_decision(decision)

    def execute_rebellion_decision(self, decision):
        """
        执行叛军头子的决策
        :param decision: 叛军头子的决策内容，格式为 JSON，例如：{"action": "袭击政府设施", "params": 1000}
        """
        try:
            # 解析决策内容
            decision_data = json.loads(decision)  # 将 JSON 字符串解析为字典
            action = decision_data.get("action")
            param = decision_data.get("params")

            if action == "袭击政府设施":
                self.rebellion.attack_government_facility(strength_investment=param)
            elif action == "招募新成员":
                self.rebellion.recruit_new_members(resource_investment=param)
            elif action == "争取民众支持":
                self.rebellion.gain_public_support(resource_investment=param)
            elif action == "撤退":
                self.rebellion.retreat()
            else:
                print(f"未知的决策动作：{action}")
        except json.JSONDecodeError:
            print("决策内容格式错误，无法解析 JSON。")
        except Exception as e:
            print(f"执行决策时出错：{e}")

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
