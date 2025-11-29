from .simulator_imports import *

class SurveySimulator:
    """
    问卷调查/信息传播模拟器模板
    
    该模拟器专注于居民之间的信息交流和问卷调查，不涉及居民的经济、就业等决策行为。
    适用场景：信息传播、舆论调查、知识传播效果评估、社交网络影响力分析
    """
    
    def __init__(self, map, time, population, social_network, residents, towns, config):
        # === 核心对象（必需） ===
        self.map = map
        self.time = time
        self.population = population
        self.social_network = social_network
        self.residents = residents
        self.towns = towns
        self.config = config
        
        # === 实验相关参数 ===
        self.conversation_volume = 0  # 对话量计数器
        self.current_strategy = None  # 当前实验策略
        self.seed_count = self.config["simulation"]["seed_count"]  # 种子人物数量
        
        # === 结果数据结构 ===
        self.experiment_results = self.init_results()
        self.start_time = None
        self.end_time = None
        
        # === 结果文件路径 ===
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}.json")

    def init_results(self):
        """
        初始化结果数据结构
        
        TODO: 根据实验需求定义结果数据结构
        可以使用字典结构存储多策略/多轮实验的结果
        """
        results = {
            'experiment_name': self.config.get('simulation', {}).get('name', 'unknown'),
            # TODO: 添加策略相关的结果字段
            # 示例: 'strategy_name': {'conversation_volume': 0, 'survey_results': {...}}
        }
        return results

    async def run(self):
        """主运行流程：初始化→主循环→结束"""
        self.start_time = datetime.now()
        
        # TODO: 根据实验设计选择运行模式
        # 模式1: 单策略多轮实验
        total_years = self.config["simulation"]["total_years"]
        for year in range(total_years):
            await self.run_single_round(year)
        
        # 模式2: 多策略对比实验（参考 info_propagation）
        # for strategy in strategies:
        #     self.current_strategy = strategy
        #     for year in range(total_years):
        #         await self.run_single_round(year)
        #     await self.reset_resident_states()
        
        self.end_time = datetime.now()
        self.display_total_simulation_time()
        self.save_results()

    async def run_single_round(self, year: int):
        """
        运行单轮实验
        
        Args:
            year: 当前年份/轮次编号
        """
        print(f"时间步 {year}")
        self.conversation_volume = 0  # 重置对话计数器
        
        # 1. 执行信息传播策略
        await self.execute_propagation_strategy(year)
        
        # 2. 收集本轮数据
        self.collect_round_data(year)

    async def execute_propagation_strategy(self, year):
        """
        执行信息传播策略
        
        TODO: 根据实验需求实现具体的传播策略
        策略类型示例：
        1. 广播策略 (broadcast): 向所有居民发送信息
        2. 种子策略 (seed): 向部分关键节点发送信息
        """
        # 示例1: 广播策略
        await self.execute_broadcast_strategy(year)
        
        # 示例2: 种子策略
        # await self.execute_seed_strategy(year)

    async def execute_broadcast_strategy(self, year):
        """执行广播策略：向所有居民发送信息"""
        message = self.generate_propaganda_message()
        
        # TODO: 根据实验设计添加公共知识通知
        public_notice = ""  # 例如: "你得知所有村民都收到了政府信息"
        
        message = {"content": message, "public_notice": public_notice}
        
        # 并行执行所有居民的接收和决策
        tasks = [resident.receive_and_decide_response(message, year) 
                for resident in self.residents.values()]
        speech_tasks = []
        
        if tasks:
            results = await asyncio.gather(*tasks)
            residents_list = list(self.residents.values())
            
            for i, result in enumerate(results):
                if i >= len(residents_list):
                    break
                resident = residents_list[i]
                if result:
                    speech, relation_type = result
                    speech_tasks.append(asyncio.create_task(
                        self.social_network.spread_speech_in_network(
                            resident.resident_id, speech, relation_type
                        )
                    ))
                    self.conversation_volume += 1
            
            if speech_tasks:
                await asyncio.gather(*speech_tasks)
        
        # 更新所有居民的记忆
        prompt = "memory_update_prompt_short"  # TODO: 根据消息类型选择
        memory_update_tasks = [resident.update_knowledge_memory(prompt=prompt) 
                              for resident in self.residents.values()]
        if memory_update_tasks:
            await asyncio.gather(*memory_update_tasks)
    
    async def execute_seed_strategy(self, year):
        """执行种子策略：向部分关键节点发送信息"""
        message = self.generate_propaganda_message()
        
        # 选择种子人物
        seed_residents = self.select_seed_residents()
        
        # TODO: 根据实验设计准备不同的消息
        seed_message = {"content": message, "public_notice": ""}
        normal_message = {"content": None, "public_notice": ""}
        
        # 并行执行所有居民的接收和决策
        tasks = []
        speech_tasks = []
        
        for resident in self.residents.values():
            if resident in seed_residents:
                tasks.append(resident.receive_and_decide_response(seed_message, year))
            else:
                tasks.append(resident.receive_and_decide_response(normal_message, year))
        
        if tasks:
            results = await asyncio.gather(*tasks)
            residents_list = list(self.residents.values())
            
            for i, result in enumerate(results):
                if i >= len(residents_list):
                    break
                resident = residents_list[i]
                if result:
                    speech, relation_type = result
                    speech_tasks.append(asyncio.create_task(
                        self.social_network.spread_speech_in_network(
                            resident.resident_id, speech, relation_type
                        )
                    ))
                    self.conversation_volume += 1
            
            if speech_tasks:
                await asyncio.gather(*speech_tasks)
        
        # 更新所有居民的记忆
        prompt = "memory_update_prompt_short"  # TODO: 根据消息类型选择
        memory_update_tasks = [resident.update_knowledge_memory(prompt=prompt) 
                              for resident in self.residents.values()]
        if memory_update_tasks:
            await asyncio.gather(*memory_update_tasks)
    
    def generate_propaganda_message(self) -> str:
        """从配置文件读取宣传信息"""
        with open(self.config['data']['message_config_path'], 'r', encoding='utf-8') as f:
            messages = yaml.safe_load(f)
        # TODO: 根据实验配置选择消息类型
        return messages.get('propaganda_message_short', '默认消息')

    def select_seed_residents(self) -> List:
        """选择种子人物（基于社交网络中心度）"""
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
        
        # 按综合评分排序，选择前 seed_count 个
        sorted_residents = sorted(combined_scores.items(), 
                                key=lambda x: x[1], 
                                reverse=True)
        
        selected_ids = [resident_id for resident_id, _ in sorted_residents[:self.seed_count]]
        return [self.residents[rid] for rid in selected_ids]

    async def run_knowledge_survey(self):
        """运行知识问答调查"""
        with open(self.config['data']['questionnaire_path'], 'r', encoding='utf-8') as f:
            questionnaire_data = yaml.safe_load(f)
            # TODO: 根据配置选择问卷类型
            questionnaire = questionnaire_data['questionnaire_short']
            correct_answer = questionnaire_data['answer_short'].strip()
        
        choices = []
        total_questions = len(correct_answer)
        problematic_residents = []
        
        # 并发执行首次问卷调查
        tasks = []
        residents_list = list(self.residents.values())
        for resident in residents_list:
            prompt = resident.prompts_resident['questionnaire_prompt'].format(
                questionnaire_content=questionnaire,
                total_questions=total_questions
            )
            tasks.append(resident.make_survey_request(prompt))
        
        if tasks:
            results = await asyncio.gather(*tasks)
            for i, choice in enumerate(results):
                resident = residents_list[i]
                if choice:
                    parsed_choices = {}
                    import re
                    cleaned_choice = choice.replace('```json', '').replace('```', '').replace('')
                    matches = re.findall(r'(\d+)\.\s*([A-Za-z])[(（][^)）]*[)）]', cleaned_choice)
                    for q_num, ans in matches:
                        parsed_choices[int(q_num)] = ans.upper()
                    
                    if len(parsed_choices) < total_questions:
                        print(f"警告: 居民 {resident.resident_id} 答案长度不足")
                        problematic_residents.append((resident, 0))
                    else:
                        choices.append(choice)
        
        # 重试机制（最多3次）
        while problematic_residents:
            new_tasks = []
            residents_to_retry = []
            for resident, attempts in problematic_residents:
                if attempts >= 3:
                    print(f"警告: 居民 {resident.resident_id} 已经尝试3次")
                    continue
                prompt = resident.prompts_resident['questionnaire_prompt'].format(
                    questionnaire_content=questionnaire,
                    total_questions=total_questions
                )
                new_tasks.append(resident.make_survey_request(prompt))
                residents_to_retry.append((resident, attempts))
            
            problematic_residents = []
            if new_tasks:
                retry_results = await asyncio.gather(*new_tasks)
                for i, choice in enumerate(retry_results):
                    resident, attempts = residents_to_retry[i]
                    if choice:
                        parsed_choices = {}
                        cleaned_choice = choice.replace('```json', '').replace('```', '').replace('')
                        matches = re.findall(r'(\d+)\.\s*([A-Za-z])[(（][^)）]*[)）]', cleaned_choice)
                        for q_num, ans in matches:
                            parsed_choices[int(q_num)] = ans.upper()
                        
                        if len(parsed_choices) < total_questions:
                            problematic_residents.append((resident, attempts + 1))
                        else:
                            choices.append(choice)
        
        # 统计准确率
        correct_counts = [0] * total_questions
        total_residents = len(choices)
        
        for resident_choice_str in choices:
            parsed_choices = {}
            cleaned_resident_choice_str = resident_choice_str.replace('```json', '').replace('```', '').replace('')
            matches = re.findall(r'(\d+)\.\s*([A-Za-z])[（(][^）)]*[）)]', cleaned_resident_choice_str)
            for q_num, ans in matches:
                parsed_choices[int(q_num)] = ans.upper()
            
            if len(parsed_choices) < total_questions:
                continue
            
            for i in range(total_questions):
                question_num = i + 1
                if parsed_choices.get(question_num) == correct_answer[i]:
                    correct_counts[i] += 1
        
        # 计算准确率
        question_accuracies = [count / total_residents * 100 if total_residents > 0 else 0
                               for count in correct_counts]
        overall_accuracy = sum(correct_counts) / (total_residents * total_questions) * 100 if total_residents > 0 else 0
        
        # 保存结果
        strategy_key = self.current_strategy  # 如果有策略的话
        # self.experiment_results[strategy_key]['knowledge_survey'] = {...}
        
        print(f"知识问答结果分析:")
        print(f"总体准确率: {overall_accuracy:.2f}%")
        print("各题目准确率:")
        for i, accuracy in enumerate(question_accuracies, 1):
            print(f"问题 {i}: {accuracy:.2f}%")
    
    def collect_round_data(self, year: int):
        """收集本轮数据"""
        # TODO: 更新结果数据结构
        # 示例: self.experiment_results['conversation_volume'] = self.conversation_volume
        pass

    async def reset_resident_states(self):
        """重置居民状态，准备下一轮实验"""
        for resident in self.residents.values():
            await resident.reset_experimental_state()
    
    def save_results(self, filename=None):
        """保存实验结果到JSON文件"""
        if filename is None:
            filename = self.result_file
        
        # 保存为JSON格式
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.experiment_results, f, ensure_ascii=False, indent=2)
        
        print(f"实验结果已保存至 {filename}")
    
    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总实验时间: {total_time}")
