import asyncio
import json
import random
import pandas as pd
import re
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
    SEED_WITHOUT_COMMON_KNOWLEDGE = "S_NCK"
    SEED_WITH_COMMON_KNOWLEDGE = "S_CK"
    BROADCAST_WITHOUT_COMMON_KNOWLEDGE = "BC_NCK"
    BROADCAST_WITH_COMMON_KNOWLEDGE = "BC_CK"

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
        self.seed_count = self.config["simulation"]["seed_count"]  # 种子策略中的种子人物数量
        
        self.experiment_results = {
            strategy.value: {
                'conversation_volume': 0,
                'knowledge_survey': {
                    'choices': [],
                    'question_accuracies': [],
                    'overall_accuracy': 0.0
                },
                'incentive_survey': {
                    'incentive_choices_a_count': 0,
                    'incentive_choices_b_count': 0
                }
            }
            for strategy in PropagationStrategy
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
            print(f"{Back.GREEN}策略 {strategy.value} 实验开始{Back.RESET}")
            self.logger.info(f"开始执行策略: {strategy.value}")
            self.conversation_volume = 0  # 重置讨论内容计数器

            # 重置时间状态，确保每个策略从初始时间开始
            self.time.reset()  # 假设有时间重置方法

            # 运行指定年份的实验
            for year in range(self.config["simulation"]["total_years"]):
                await self.run_single_round(year)
            
            # 运行知识问答调查
            print("\n开始进行知识问答调查...")
            await self.run_knowledge_survey()
            
            # 运行奖励问题调查
            print("\n开始进行奖励问题调查...")
            await self.run_incentive_survey()
            
            # 保存当前策略的结果
            self.save_strategy_results()
            
            # 重置居民状态，准备下一个策略的实验
            await self.reset_resident_states()
            print(f"居民状态已重置")

    async def run_single_round(self, year: int):
        """运行单轮实验"""
        self.logger.info(f"时间步 {year}, 策略 {self.current_strategy.value}")
        self.start_time = datetime.now()  # 记录模拟开始时间

        # 重置或确保时间状态正确
        if hasattr(self.time, 'set_current_time'):
            self.time.set_current_time(year)  # 设置当前时间
        
        # 1. 执行信息传播策略
        await self.execute_propagation_strategy(year)

        # 3. 收集数据
        self.collect_round_data(year)

    async def execute_propagation_strategy(self, year):
        """执行当前的信息传播策略"""
        if self.current_strategy in [PropagationStrategy.BROADCAST_WITH_COMMON_KNOWLEDGE, 
                                   PropagationStrategy.BROADCAST_WITHOUT_COMMON_KNOWLEDGE]:
            await self.execute_broadcast_strategy(year)
        else:
            await self.execute_seed_strategy(year)

    async def execute_broadcast_strategy(self, year):
        """执行广播策略"""
        message = self.generate_propaganda_message()
        
        # 如果是带公共知识的策略，添加公共通知
        if self.current_strategy == PropagationStrategy.BROADCAST_WITH_COMMON_KNOWLEDGE:
            public_notice = "你得知所有村民都收到了政府信息，并且所有村民都得知你收到了政府信息。"
        else:
            public_notice = ""
        
        message = {"content": message, "public_notice": public_notice}
        
        # 并行执行所有居民的接收和决策
        tasks = [resident.receive_and_decide_response(message,year) 
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
        #更新所有居民的记忆
        memory_update_tasks = [resident.update_knowledge_memory() for resident in self.residents.values()]
        if memory_update_tasks:
            await asyncio.gather(*memory_update_tasks)

    async def execute_seed_strategy(self, year):
        """执行种子策略"""
        message = self.generate_propaganda_message()
        
        # 选择种子人物（基于社交网络中心度）
        seed_residents = self.select_seed_residents()
        
        # 准备不同类型的消息
        if self.current_strategy == PropagationStrategy.SEED_WITH_COMMON_KNOWLEDGE:
            public_notice_normal = f"全村只有部分村民收到了政府信息。"
            public_notice_seed = f"全村只有部分村民收到政府信息，所有村民都得知你收到了政府信息。"
            seed_message = {"content": message, "public_notice": public_notice_seed}
            normal_message = {"content": None, "public_notice": public_notice_normal}
        else:
            public_notice_normal = f""
            public_notice_seed = f""
            seed_message = {"content": message, "public_notice": public_notice_seed}
            normal_message = {"content": None, "public_notice": public_notice_normal}
        
        # 并行执行所有居民的接收和决策
        tasks = []
        speech_tasks = []
        
        for resident in self.residents.values():
            if resident in seed_residents:
                tasks.append(resident.receive_and_decide_response(seed_message,year))
            else:
                tasks.append(resident.receive_and_decide_response(normal_message,year))
        
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
        #更新所有居民的记忆
        memory_update_tasks = [resident.update_knowledge_memory() for resident in self.residents.values()]
        if memory_update_tasks:
            await asyncio.gather(*memory_update_tasks)
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
        if self.config['simulation']['message_type'] == 'S':
            return messages['propaganda_message_short']
        else:
            return messages['propaganda_message_long']

    def collect_round_data(self, year: int):
        """收集本轮数据"""
        # 更新当前策略的对话量
        strategy_key = self.current_strategy.value
        self.experiment_results[strategy_key]['conversation_volume'] = self.conversation_volume

    async def run_knowledge_survey(self):
        """运行知识问答调查"""
        with open(self.config['data']['questionnaire_path'], 'r', encoding='utf-8') as f:
            questionnaire_data = yaml.safe_load(f)
            if self.config['simulation']['message_type'] == 'S':
                questionnaire = questionnaire_data['questionnaire_short']
                correct_answer = questionnaire_data['answer_short'].strip()
            else:
                questionnaire = questionnaire_data['questionnaire_long']
                correct_answer = questionnaire_data['answer_long'].strip()

        choices = []
        total_questions = len(correct_answer)  # 总题目数
        problematic_residents = []  # 用于记录有问题的居民

        for resident in self.residents.values():
            prompt = resident.prompts_resident['questionnaire_prompt'].format(
                questionnaire_content=questionnaire,
                total_questions=total_questions
            )
            choice = await resident.make_survey_request(prompt)
            if choice:  # 确保choice不为None
                parsed_choices = {}
                import re
                # 预处理：去除LLM可能添加的```json```标记和多余的换行符
                cleaned_choice = choice.replace('```json', '').replace('```', '').replace('\n', '')
                # 使用正则表达式匹配所有 "数字. 字母" 的组合（忽略括号内的选择理由）
                matches = re.findall(r'(\d+)\.\s*([A-Za-z])\([^)]*\)', cleaned_choice)
                for q_num, ans in matches:
                    parsed_choices[int(q_num)] = ans.upper()

                # 确保解析后的答案数量足够
                if len(parsed_choices) < total_questions:
                    print(f"警告: 居民 {resident} 答案长度不足，期望{total_questions}，实际{len(parsed_choices)}")
                    problematic_residents.append((resident, 0))  # 记录居民及尝试次数
                    continue

                choices.append(choice)

        # 如果有有问题的居民，重新进行问卷调查，最多3次
        while problematic_residents:
            resident, attempts = problematic_residents.pop()
            if attempts >= 3:
                print(f"警告: 居民 {resident} 已经尝试3次，仍然答案长度不足")
                continue
            prompt = resident.prompts_resident['questionnaire_prompt'].format(
                questionnaire_content=questionnaire,
                total_questions=total_questions
            )
            choice = await resident.make_survey_request(prompt)
            if choice:
                parsed_choices = {}
                # 预处理：去除LLM可能添加的```json```标记和多余的换行符
                cleaned_choice = choice.replace('```json', '').replace('```', '').replace('\n', '')
                matches = re.findall(r'(\d+)\.\s*([A-Za-z])\([^)]*\)', cleaned_choice)
                for q_num, ans in matches:
                    parsed_choices[int(q_num)] = ans.upper()

                if len(parsed_choices) < total_questions:
                    print(f"警告: 居民 {resident} 答案长度不足，期望{total_questions}，实际{len(parsed_choices)}")
                    problematic_residents.append((resident, attempts + 1))  # 再次记录居民及增加尝试次数
                else:
                    choices.append(choice)

        # 初始化计数
        correct_counts = [0] * total_questions  # 每个知识问题的正确回答数
        total_residents = len(choices)

        for resident_choice_str in choices:
            # 解析答案
            parsed_choices = {}
            # 预处理：去除LLM可能添加的```json```标记和多余的换行符
            cleaned_resident_choice_str = resident_choice_str.replace('```json', '').replace('```', '').replace('\n', '')
            matches = re.findall(r'(\d+)\.\s*([A-Za-z])\([^)]*\)', cleaned_resident_choice_str)
            for q_num, ans in matches:
                parsed_choices[int(q_num)] = ans.upper()

            # 确保解析后的答案数量足够
            if len(parsed_choices) < total_questions:
                print(f"警告: 居民答案长度不足，期望{total_questions}，实际{len(parsed_choices)}")
                continue

            # 计算每题的准确率
            for i in range(total_questions):
                question_num = i + 1  # 题号从1开始
                if parsed_choices.get(question_num) == correct_answer[i]:
                    correct_counts[i] += 1

        # 计算每个知识问题的准确率
        question_accuracies = [count / total_residents * 100 if total_residents > 0 else 0
                               for count in correct_counts]
        overall_accuracy = sum(correct_counts) / (total_residents * total_questions) * 100 if total_residents > 0 else 0

        # 更新当前策略的结果
        strategy_key = self.current_strategy.value
        self.experiment_results[strategy_key]['knowledge_survey'] = {
            'choices': choices,
            'question_accuracies': question_accuracies,
            'overall_accuracy': overall_accuracy
        }

        # 输出准确率结果
        print(f"\n知识问答结果分析:")
        print(f"总体准确率: {overall_accuracy:.2f}%")
        print("各题目准确率:")
        for i, accuracy in enumerate(question_accuracies, 1):
            print(f"问题 {i}: {accuracy:.2f}%")

    async def run_incentive_survey(self):
        """运行奖励问题调查"""
        incentive_choices_a_count = 0
        incentive_choices_b_count = 0
        total_responses = 0

        for resident in self.residents.values():
            prompt = resident.prompts_resident['incentive_questionnaire_prompt'].format()
            response = await resident.make_survey_request(prompt)
            if response:
                # 清理LLM返回的字符串并解析JSON
                cleaned_response = response.strip()
                cleaned_response = re.sub(r"^```json\s*|\s*```$", "", cleaned_response, flags=re.DOTALL).strip()

                try:
                    response_json = json.loads(cleaned_response)
                    select = response_json.get("select", '').upper()
                    reason = response_json.get("reason", '')
                    
                    total_responses += 1
                    if select == 'A':
                        incentive_choices_a_count += 1
                    elif select == 'B':
                        incentive_choices_b_count += 1

                except json.JSONDecodeError as e:
                    self.logger.error(f"居民 {resident.resident_id} 解析奖励问题JSON响应出错: {e}, 原始响应: '{cleaned_response}'")
                    continue

        # 更新当前策略的结果
        strategy_key = self.current_strategy.value
        self.experiment_results[strategy_key]['incentive_survey'] = {
            'incentive_choices_a_count': incentive_choices_a_count,
            'incentive_choices_b_count': incentive_choices_b_count
        }

        # 输出统计结果
        print(f"\n奖励问题统计:")
        print(f"总回答人数: {total_responses}，选择A的人数: {incentive_choices_a_count}，选择B的人数: {incentive_choices_b_count}")

    def save_strategy_results(self):
        """保存当前策略的结果"""
        strategy_key = self.current_strategy.value

    async def reset_resident_states(self):
        """重置居民状态，准备下一轮实验"""
        for resident in self.residents.values():
            await resident.reset_experimental_state()
    
    def save_results(self, filename="data/info_propagation_results.json"):
        """保存实验结果到JSON文件"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 保存为JSON格式
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.experiment_results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"实验结果已保存至 {filename}")