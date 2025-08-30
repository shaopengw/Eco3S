import asyncio
import json
import random
import pandas as pd
import os
import yaml
from colorama import Back
import logging
import networkx as nx
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional

from src.agents.resident import Resident
from src.environment.social_network import SocialNetwork
from src.environment.towns import Towns
from src.environment.time import Time

class PropagationStrategy(Enum):
    """信息传播策略枚举"""
    BROADCAST_WITH_COMMON_KNOWLEDGE = "BC_CK"
    BROADCAST_WITHOUT_COMMON_KNOWLEDGE = "BC_NCK"
    SEED_WITH_COMMON_KNOWLEDGE = "S_CK"
    SEED_WITHOUT_COMMON_KNOWLEDGE = "S_NCK"

class InfoPropagationSimulator:
    def __init__(self, map, time, population, social_network, residents, towns, config):
        """初始化信息传播模拟器"""
        self.map = map
        self.time = time
        self.population = population
        self.social_network = social_network
        self.residents = residents
        self.towns = towns
        self.config = config
        self.conversation_volume = 0
        
        # 实验相关参数
        self.current_strategy = None
        self.seed_count = 5  # 种子策略中的种子人物数量
        self.experiment_results = {
            "rounds": [],
            "strategy": [],
            "conversation_volume": [], #讨论数量
            "questionnaire_survey": [], #问卷调查结果
            "incentive_choices": [] #激励选项结果
        }
        
        # 初始化记录器
        self.setup_logger()
        
    def setup_logger(self):
        """设置日志记录器"""
        self.logger = logging.getLogger("info_propagation")
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(f"log/info_propagation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    async def run(self):
        """运行实验"""
        # 对每种策略进行实验
        for strategy in PropagationStrategy:
            self.current_strategy = strategy
            self.logger.info(f"开始执行策略: {strategy.value}")
            self.conversation_volume = 0  # 重置讨论内容计数器

            # 重置时间状态，确保每个策略从初始时间开始
            self.time.reset()  # 假设有时间重置方法

            # 运行指定年份的实验
            for year in range(self.config["simulation"]["total_years"]):
                await self.run_single_round(year)
            
            # 实验结束后进行问卷调查
            await self.run_questionnaire_survey()
            
            # 重置居民状态，准备下一个策略的实验
            self.reset_resident_states()

    async def run_single_round(self, year: int):
        """运行单轮实验"""
        self.logger.info(f"时间步 {year}, 策略 {self.current_strategy.value}")
        self.start_time = datetime.now()  # 记录模拟开始时间

        # 重置或确保时间状态正确
        if hasattr(self.time, 'set_current_time'):
            self.time.set_current_time(year)  # 设置当前时间
        
        # 1. 执行信息传播策略
        await self.execute_propagation_strategy()

        # 3. 收集数据
        self.collect_round_data(year)

    async def execute_propagation_strategy(self):
        """执行当前的信息传播策略"""
        if self.current_strategy in [PropagationStrategy.BROADCAST_WITH_COMMON_KNOWLEDGE, 
                                   PropagationStrategy.BROADCAST_WITHOUT_COMMON_KNOWLEDGE]:
            await self.execute_broadcast_strategy()
        else:
            await self.execute_seed_strategy()

    async def execute_broadcast_strategy(self):
        """执行广播策略"""
        message = self.generate_propaganda_message()
        
        # 如果是带公共知识的策略，添加公共通知
        if self.current_strategy == PropagationStrategy.BROADCAST_WITH_COMMON_KNOWLEDGE:
            public_notice = "所有村民都收到了这个信息。"
        else:
            public_notice = None
        
        message = {"content": message, "public_notice": public_notice}
        
        # 并行执行所有居民的接收和决策
        tasks = [resident.receive_and_decide_response(message) 
                for resident in self.residents.values()]
        speech_tasks = []
        if tasks:
            results = await asyncio.gather(*tasks)
            # 处理结果
            for i, result in enumerate(results):
                resident = list(self.residents.values())[i]
                if result:
                    speech, relation_type = result
                    speech_tasks.append(self.social_network.spread_speech_in_network(resident.resident_id, speech, relation_type))
                    self.conversation_volume += 1
            # 并发执行所有发言传播任务
            if speech_tasks:
                await asyncio.gather(*speech_tasks)

    async def execute_seed_strategy(self):
        """执行种子策略"""
        message = self.generate_propaganda_message()
        
        # 选择种子人物（基于社交网络中心度）
        seed_residents = self.select_seed_residents()
        
        # 准备不同类型的消息
        if self.current_strategy == PropagationStrategy.SEED_WITH_COMMON_KNOWLEDGE:
            seed_ids = [str(resident.resident_id) for resident in seed_residents]  # 转换为字符串
            public_notice = f"以下居民收到了信息：{', '.join(seed_ids)}"
            seed_message = {"content": message, "public_notice": public_notice}
            normal_message = {"content": None, "public_notice": public_notice}
        else:
            seed_message = {"content": message, "public_notice": None}
            normal_message = {"content": None, "public_notice": None}
        
        # 并行执行所有居民的接收和决策
        tasks = []
        speech_tasks = []
        
        for resident in self.residents.values():
            if resident in seed_residents:
                tasks.append(resident.receive_and_decide_response(seed_message))
            else:
                tasks.append(resident.receive_and_decide_response(normal_message))
        
        if tasks:
            results = await asyncio.gather(*tasks)
            # 处理结果
            for i, result in enumerate(results):
                resident = list(self.residents.values())[i]
                if result:
                    speech, relation_type = result
                    speech_tasks.append(self.social_network.spread_speech_in_network(resident.resident_id, speech, relation_type))
                    self.conversation_volume += 1
            # 并发执行所有发言传播任务
            if speech_tasks:
                await asyncio.gather(*speech_tasks)
        
        return

    def select_seed_residents(self) -> List[Resident]:
        """选择种子人物"""
        # 获取社交网络图
        graph = self.social_network.hetero_graph.graph
        
        # 计算多种中心度指标
        degree_centrality = nx.degree_centrality(graph)
        betweenness_centrality = nx.betweenness_centrality(graph)
        closeness_centrality = nx.closeness_centrality(graph)
        
        # 综合评分 = 0.4*度中心度 + 0.3*中介中心度 + 0.3*接近中心度
        combined_scores = {
            node: 0.4 * degree_centrality[node] + 
                 0.3 * betweenness_centrality[node] + 
                 0.3 * closeness_centrality[node]
            for node in graph.nodes()
        }
        
        # 按综合评分排序
        sorted_residents = sorted(combined_scores.items(), 
                                key=lambda x: x[1], 
                                reverse=True)
        
        # 选择前seed_count个居民作为种子
        selected_ids = [resident_id for resident_id, _ in sorted_residents[:self.seed_count]]
        return [self.residents[rid] for rid in selected_ids]

    def generate_propaganda_message(self) -> str:
        """从配置文件读取宣传信息"""
        with open(self.config['data']['message_config_path'], 'r', encoding='utf-8') as f:
            messages = yaml.safe_load(f)
        return messages['propaganda_message']

    def collect_round_data(self, year: int):
        """收集本轮数据"""
        conversation_volume = self.conversation_volume
        
        self.experiment_results["rounds"].append(year)
        self.experiment_results["strategy"].append(self.current_strategy.value)
        self.experiment_results["conversation_volume"].append(conversation_volume)
        
        # 初始化问卷调查和激励选择结果（只在每轮策略开始时）
        if year == 0:
            self.experiment_results["questionnaire_survey"].append(None)  # 占位符
            self.experiment_results["incentive_choices"].append(None)     # 占位符

    async def run_questionnaire_survey(self):
        """运行问卷调查"""
        with open(self.config['data']['questionnaire_path'], 'r', encoding='utf-8') as f:
            questionnaire_data = yaml.safe_load(f)
            questionnaire = questionnaire_data['questionnaire']
            correct_answer = questionnaire_data['answer'].strip()
        
        choices = []
        for resident in self.residents.values():
            choice = await resident.make_questionnaire_survey(questionnaire)
            if choice:  # 确保choice不为None
                choices.append(choice)
        
        # 初始化最后一题的A和B选项计数
        incentive_choices_a_count = 0
        incentive_choices_b_count = 0

        # 动态确定题目数量，最后一题为激励选项，不计入准确率计算
        total_questions_for_accuracy = len(correct_answer) - 1  # 使用正确答案长度来确定题目数量
        total_residents = len(choices)
        correct_counts = [0] * total_questions_for_accuracy  # 每个非激励问题的正确回答数
        
        for resident_choice in choices:
            # 确保resident_choice长度足够
            if len(resident_choice) < len(correct_answer):
                # 如果答案长度不足，跳过这个居民或填充默认值
                continue
            
            # 统计最后一题（激励选项）的A和B选项
            incentive_answer = resident_choice[-1]  # 最后一题的答案
            if incentive_answer == 'A':
                incentive_choices_a_count += 1
            elif incentive_answer == 'B':
                incentive_choices_b_count += 1

            # 计算前 total_questions_for_accuracy 题的准确率
            for i in range(total_questions_for_accuracy):
                if resident_choice[i] == correct_answer[i]:
                    correct_counts[i] += 1
        
        # 计算每个非激励问题的准确率
        question_accuracies = [count/total_residents * 100 for count in correct_counts]
        overall_accuracy = sum(correct_counts) / (total_residents * total_questions_for_accuracy) * 100
        
        # 将结果添加到experiment_results中
        # 确保每次迭代都添加一个元素，即使没有问卷数据也添加None或默认值
        if not self.experiment_results.get("questionnaire_survey"):
            self.experiment_results["questionnaire_survey"] = []
        if not self.experiment_results.get("incentive_choices"):
            self.experiment_results["incentive_choices"] = []

        # 只有当有choices时才添加实际数据，否则添加None或默认空字典
        if choices:
            self.experiment_results["questionnaire_survey"].append({
                "strategy": self.current_strategy.value,
                "choices": choices,
                "question_accuracies": question_accuracies,
                "overall_accuracy": overall_accuracy
            })
            self.experiment_results["incentive_choices"].append({
                "strategy": self.current_strategy.value,
                "incentive_choices_a_count": incentive_choices_a_count,
                "incentive_choices_b_count": incentive_choices_b_count
            })
        else:
            # 如果没有问卷数据，添加占位符以保持列表长度一致
            self.experiment_results["questionnaire_survey"].append(None)
            self.experiment_results["incentive_choices"].append(None)

        # 输出准确率结果
        print(f"\n问卷调查结果分析:")
        print(f"总体准确率: {overall_accuracy:.2f}%")
        print("各题目准确率:")
        for i, accuracy in enumerate(question_accuracies, 1):
            print(f"问题 {i}: {accuracy:.2f}%")
        
        print(f"\n最后一题统计:")
        print(f"选择A的人数: {incentive_choices_a_count}")
        print(f"选择B的人数: {incentive_choices_b_count}")

    def reset_resident_states(self):
        """重置居民状态，准备下一轮实验"""
        for resident in self.residents.values():
            resident.reset_experimental_state()
    
    # def save_results(self, filename="data/info_propagation_results.csv"):
    #     """保存实验结果"""
    #     os.makedirs(os.path.dirname(filename), exist_ok=True)
    #     df = pd.DataFrame(self.experiment_results)
    #     df.to_csv(filename, index=False)
    #     self.logger.info(f"实验结果已保存至 {filename}")
    def save_results(self, filename="data/info_propagation_results.csv"):
        """保存实验结果"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 创建主实验结果DataFrame（每个时间步的数据）
        main_results = pd.DataFrame({
            "round": self.experiment_results["rounds"],
            "strategy": self.experiment_results["strategy"],
            "conversation_volume": self.experiment_results["conversation_volume"]
        })
        
        # 创建问卷调查结果DataFrame（每个策略的数据）
        questionnaire_data = []
        strategies = list(PropagationStrategy)  # 获取所有策略
        
        for i, survey in enumerate(self.experiment_results["questionnaire_survey"]):
            strategy_name = strategies[i].value if i < len(strategies) else f"Unknown_{i}"
            
            if survey is not None:
                questionnaire_data.append({
                    "strategy": strategy_name,
                    "overall_accuracy": survey["overall_accuracy"],
                    "question_accuracies": survey["question_accuracies"]
                })
            else:
                questionnaire_data.append({
                    "strategy": strategy_name,
                    "overall_accuracy": None,
                    "question_accuracies": None
                })
        
        questionnaire_df = pd.DataFrame(questionnaire_data)
        
        # 创建激励选择结果DataFrame
        incentive_data = []
        for i, incentive in enumerate(self.experiment_results["incentive_choices"]):
            strategy_name = strategies[i].value if i < len(strategies) else f"Unknown_{i}"
            
            if incentive is not None:
                incentive_data.append({
                    "strategy": strategy_name,
                    "incentive_choices_a_count": incentive["incentive_choices_a_count"],
                    "incentive_choices_b_count": incentive["incentive_choices_b_count"]
                })
            else:
                incentive_data.append({
                    "strategy": strategy_name,
                    "incentive_choices_a_count": None,
                    "incentive_choices_b_count": None
                })
        
        incentive_df = pd.DataFrame(incentive_data)
        
        # 保存到不同的文件
        main_results.to_csv(filename, index=False)
        questionnaire_df.to_csv(filename.replace(".csv", "_questionnaire.csv"), index=False)
        incentive_df.to_csv(filename.replace(".csv", "_incentive.csv"), index=False)
        
        self.logger.info(f"实验结果已保存至 {filename} 和相关文件")