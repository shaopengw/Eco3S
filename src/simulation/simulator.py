import asyncio
from datetime import datetime, timedelta
import json
from colorama import Back
from src.agents.resident_agent_generator import (generate_canal_agents)
from src.agents.government import OrdinaryGovernmentAgent, HighRankingGovernmentAgent
from src.agents.rebels import OrdinaryRebel, RebelLeader
from src.generator.resident_generate import generate_resident_data, save_resident_data

class Simulator:
    def __init__(self, map, time, job_market, government, government_officials, rebellion, rebels_agents, population, information_spread, residents):
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
        :param information_spread: 信息传播对象
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
        self.information_spread = information_spread
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
                offset = len(self.residents)  # 第一次生成的居民数量
                for resident_id, resident in new_residents.items():
                    new_resident_id = resident_id + offset
                    self.residents[new_resident_id] = resident
                    self.residents[new_resident_id].resident_id = new_resident_id  # 给居民编号
                self.population.birth(new_residents_count)
                print(f"{len(new_residents)} 名新居民已出生")
            
            # 基于LLM的决策--测试时建议暂时注释
            # 政府行为
            await self.government_decision_process()
            # 叛军行为
            await self.rebellion_decision_process()

            # 居民行为
            rebellions = 0
            for resident_name in list(self.residents.keys()):  # 使用 list() 确保在遍历时不会出错
                resident = self.residents[resident_name]
                await resident.decide_action_by_llm()  # 基于LLM的决策--测试时建议暂时注释
                # 更新居民寿命（次/年）
                print(f"居民{resident_name}健康值: {resident.health_index}")
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

    def display_total_simulation_time(self):
        """
        显示总模拟时间
        """
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")

    async def government_decision_process(self):
        """
        政府决策流程：
        1. 普通官员发表意见
        2. 普通官员互相讨论
        3. 高级官员做出决策
        4. 执行决策
        """
        # 1. 普通官员发表意见
        ordinary_officials = [official for official in self.government_officials.values() if isinstance(official, OrdinaryGovernmentAgent)]
        print(f"找到 {len(ordinary_officials)} 位普通官员")  # 输出普通官员的数量
        
        for official in ordinary_officials:
            opinion = await official.generate_opinion()
            official.express_opinion(opinion)

        # 2. 普通官员互相讨论
        discussion_report = ""
        if len(ordinary_officials) > 1:
            discussion_report = ordinary_officials[0].discuss_with_other_officials(ordinary_officials[1:])

        # 3. 高级官员做出决策
        high_ranking_officials = [official for official in self.government_officials.values() if isinstance(official, HighRankingGovernmentAgent)]
        if high_ranking_officials:
            decision = high_ranking_officials[0].make_decision(discussion_report)

            # 4. 执行决策
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

    # def execute_government_decision(decision, government):
    #     """
    #     执行高级官员的决策
    #     :param decision: 高级官员的决策内容，格式为 JSON 列表，例如：
    #         [
    #             {"action": "维护运河", "params": 2000000},
    #             {"action": "增加就业", "params": 1000000}
    #         ]
    #     :param government: Government 类的实例，用于执行具体动作
    #     """
    #     try:
    #         # 打印传入的 JSON 字符串，检查格式
    #         print(f"传入的决策内容：{decision}")
            
    #         # 解析决策内容
    #         decision_data = json.loads(decision)  # 将 JSON 字符串解析为列表

    #         # 遍历每个动作并执行
    #         for action_item in decision_data:
    #             action = action_item.get("action")
    #             param = action_item.get("params")

    #             if action == "增加就业":
    #                 government.provide_jobs(budget_allocation=param)
    #             elif action == "维护运河":
    #                 government.maintain_canals(budget_allocation=param)
    #             elif action == "提供公共服务":
    #                 government.provide_public_services(budget_allocation=param)
    #             elif action == "军需拨款":
    #                 government.support_military(budget_allocation=param)
    #             else:
    #                 print(f"未知的决策动作：{action}")
    #     except json.JSONDecodeError:
    #         print("决策内容格式错误，无法解析 JSON。")
    #     except Exception as e:
    #         print(f"执行决策时出错：{e}")