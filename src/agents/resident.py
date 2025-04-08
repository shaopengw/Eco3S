from .shared_imports import *
load_dotenv()

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

class ResidentSharedInformationPool:
    def __init__(self):
        self.shared_info = {
            'economic_status': {},
            'social_network': {},
            'environment_awareness': {}
        }

    def add_shared_info(self, key, value, category):
        if category not in self.shared_info:
            self.shared_info[category] = {}
        self.shared_info[category][key] = value

    def get_shared_info(self, category=None):
        if category:
            return self.shared_info.get(category, {})
        return self.shared_info

class Resident:
    def __init__(self, resident_id, location, job_market, shared_pool):
        """
        初始化居民类
        :param resident_id: 居民的唯一标识符
        :param location: 居民的初始位置 (x, y)
        :param job_market: 就业市场对象，用于获取工作机会
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.resident_id = resident_id
        self.location = location
        self.job_market = job_market
        self.shared_pool = shared_pool
        self.employed = False  # 是否就业
        self.job = None  # 当前工作
        self.income = 0  # 收入
        self.satisfaction = 100  # 对政府的满意度（0到100）
        self.rebellion_risk = 0  # 参与叛乱的风险（0到100）
        self.health_index = 10  # 居民的健康状况（0到10）
        self.lifespan = 100  # 居民的寿命

        # 初始化 CAMEL 框架组件
        self.model_manager = ModelManager()
        model_config = self.model_manager.get_random_model_config()
        self.model_type = ModelType(model_config["model_type"])
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=model_config["model_platform"],
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = ChatHistoryMemory(self.context_creator, window_size=5)

        # # 初始化日志
        # self.logger = logging.getLogger(name=f"resident_{resident_id}")
        # self.logger.setLevel(logging.DEBUG)
        # handler = logging.StreamHandler()
        # handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        # self.logger.addHandler(handler)

    def employ(self, job):
        """
        居民就业
        :param job: 工作名称
        """
        self.employed = True
        self.job = job
        self.income = 10  # 假设每份工作的收入为10
        self.satisfaction += 10  # 就业增加满意度
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 找到了工作：{job}。")

    def unemploy(self):
        """
        居民失业
        """
        self.employed = False
        self.job = None
        self.income = 0
        self.satisfaction -= 20  # 失业降低满意度
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 失业了。")

    def migrate(self, new_location):
        """
        居民迁徙
        :param new_location: 新位置的坐标 (x, y)
        """
        self.location = new_location
        resident_log.info(f"居民 {self.resident_id} 迁徙到了 {new_location}。")

    def evaluate_rebellion_risk(self):
        """
        评估参与叛乱的风险
        """
        if not self.employed:
            self.rebellion_risk += 30  # 失业增加叛乱风险
        if self.income < 50:
            self.rebellion_risk += 20  # 低收入增加叛乱风险
        if self.satisfaction < 50:
            self.rebellion_risk += 50  # 低满意度增加叛乱风险
        resident_log.info(f"居民 {self.resident_id} 的叛乱风险更新为 {self.rebellion_risk}。")

    async def receive_information(self, message_content):
        """
        接收信息（如政府政策、叛乱信息）
        """
        # print("触发receive_information--------------------------------")
        self.satisfaction += 5  # 接收信息增加满意度
        resident_log.info(f"居民 {self.resident_id} 收到了信息：{message_content}。")
    
        # 30% 的概率生成响应
        if random.random() < 0.8:
            # 使用 CAMEL 框架处理信息
            user_message = BaseMessage.make_user_message(
                role_name="政府",
                content=message_content,
            )
            self.memory.write_record(
                MemoryRecord(
                    message=user_message,
                    role_at_backend=OpenAIBackendRole.USER,
                )
            )
            
            # 获取当前的上下文
            openai_messages, _ = self.memory.get_context()
            if not openai_messages:
                openai_messages = [{
                    "role": "system",
                    "content": "你是一个清代中国大运河附近的居民。请根据收到的信息做出回应。回应要简短，不超过20个字。",
                }]
            
            # 调用模型生成回应
            try:
                response = await asyncio.to_thread(
                    lambda: self.model_backend.run(openai_messages)
                )
                response_content = response.choices[0].message.content
                
                # 随机选择一种关系类型进行传播
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                
                # 使用 asyncio.create_task 来避免阻塞
                await asyncio.create_task(
                    self.spread_speech_in_network(response_content, selected_type)
                )
                
                resident_log.info(f"居民 {self.resident_id} 对收到的信息做出回应：{response_content}")
                
                # 将响应记录到记忆中
                assistant_message = BaseMessage.make_assistant_message(
                    role_name="居民",
                    content=response_content,
                )
                self.memory.write_record(
                    MemoryRecord(
                        message=assistant_message,
                        role_at_backend=OpenAIBackendRole.ASSISTANT,
                    )
                )
            except Exception as e:
                resident_log.error(f"居民 {self.resident_id} 生成回应时出错：{e}")

    async def process_information(self):
        """
        处理接收到的信息并生成响应
        """
        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一个清代中国大运河附近的居民。请根据收到的信息做出回应。",
            }]

        response = await self.model_backend.run(openai_messages)
        resident_log.info(f"居民 {self.resident_id} 的回应：{response.choices[0].message.content}")

        # 将响应记录到记忆中
        assistant_message = BaseMessage.make_assistant_message(
            role_name="居民",
            content=response.choices[0].message.content,
        )
        self.memory.write_record(
            MemoryRecord(
                message=assistant_message,
                role_at_backend=OpenAIBackendRole.ASSISTANT,
            )
        )

    async def decide_action_by_llm(self):
        """
        通过LLM决定居民的行动，并随机生成对政府的态度发言。
        """
        # 获取当前居民状态的提示信息
        status_prompt = self.get_status_prompt()
        
        action_prompt = (
            f"请根据当前状态决定下一步行动。"
            f"以下是你的当前状态：{status_prompt}\n"
            f"你可以选择以下行动之一：\n"
            f"1. 参加叛乱\n"
            f"2. 继续目前的工作\n"
            f"3. 迁徙到其他位置\n"
            f"请返回选择的数字（1、2 或 3），并解释原因。"
            f"注意：必须返回单行的JSON字符串，格式如下：\n"
            f'{{"select": "1", "reason": "叛乱风险已达210，环境极其危险。农民收入微薄。健康极差，生存优先。"}}'
        )

        speech_prompt = (
            f"请根据当前状态决定下一步行动。"
            f"以下是你的当前状态：{status_prompt}\n"
            f"你可以选择以下行动之一：\n"
            f"1. 参加叛乱\n"
            f"2. 继续目前的工作\n"
            f"3. 迁徙到其他位置\n"
            f"请返回选择的数字（1、2 或 3），并解释原因。"
            f"\n同时，请根据当前状态对政府表达一个态度（积极或消极）"
            f"态度要与满意度（{self.satisfaction}）和叛乱风险（{self.rebellion_risk}）相符。"
            f"注意：必须返回单行的JSON字符串，格式如下：\n"
            f'{{"select": "1", "reason": "叛乱风险已达210，环境极其危险。农民收入微薄。健康极差，生存优先。", "speech": "政府的政策让我们的生活越来越艰难。"}}'
        )
        # 随机决定是否需要发言（20%的概率）
        need_speech = random.random() < 0.2
        user_msg = BaseMessage.make_user_message(
            role_name="居民",
            content=action_prompt if not need_speech else speech_prompt
        )
        # 将用户消息写入记忆系统
        self.memory.write_record(
            MemoryRecord(
                message=user_msg,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        # 获取当前的上下文
        openai_messages, _ = self.memory.get_context()
        # 如果上下文为空，加入系统消息
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一个模拟中的居民。请根据当前状态决定下一步行动。",
            }] + [user_msg.to_openai_user_message()]

        resident_log.info(f"居民 {self.resident_id} 正在决定行动，提示信息：{openai_messages}")

        # 调用模型进行推理
        try:
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)
            content = response.choices[0].message.content
            
            decision_data = json.loads(content)
            select = decision_data.get("select")
            reason = decision_data.get("reason")
            speech = decision_data.get("speech", "")
            
            resident_log.info(f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}")
            
            # 如果有发言，在社交网络中传播
            if speech:
                # 获取所有可能的关系类型
                relation_types = ["friend", "colleague", "family", "hometown"]
                # 随机选择一种关系类型
                selected_type = random.choice(relation_types)
                # 在社交网络中传播信息
                await self.spread_speech_in_network(speech, selected_type)

            return select, reason
            
        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 决策出错：{e}")
            return "2", "发生错误，继续当前工作"  # 默认选择继续工作

    async def spread_speech_in_network(self, speech: str, relation_type: str):
        """
        在社交网络中传播发言
        """
        try:
            if hasattr(self, 'social_network'):
                if relation_type in ["friend", "colleague"]:
                    # 在异质图中传播
                    neighbors = self.social_network.hetero_graph.get_neighbors(self.resident_id)
                    for neighbor_id in neighbors:
                        if self.social_network.hetero_graph.graph[self.resident_id][neighbor_id]["type"] == relation_type:
                            resident_log.info(f"居民 {self.resident_id} 向邻居 {neighbor_id} 传播信息：{speech}")
                            # 获取邻居居民对象并调用其receive_information方法
                            neighbor = self.social_network.residents.get(neighbor_id)
                            if neighbor:
                                await neighbor.receive_information(speech)
                            
                elif relation_type in ["family", "hometown"]:
                    # 在超图中传播
                    groups = [edge_id for edge_id in self.social_network.hyper_graph.get_node_hyperedges(self.resident_id)
                            if edge_id.startswith(relation_type)]
                    if groups:
                        selected_group = random.choice(groups)
                        resident_log.info(f"居民 {self.resident_id} 在群组 {selected_group} 中传播信息：{speech}")
                        members = self.social_network.hyper_graph.get_hyperedge_nodes(selected_group)
                        for member_id in members:
                            if member_id != self.resident_id:
                                # 获取群组成员对象并调用其receive_information方法
                                member = self.social_network.residents.get(member_id)
                                if member:
                                    await member.receive_information(speech)
                
        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 传播信息时出错：{e}")

    def get_status_prompt(self):
        """
        生成当前居民状态的提示信息。
        :return: 居民状态的字符串描述
        """
        status_prompt = (
            f"居民 ID: {self.resident_id}\n"
            f"位置: {self.location}\n"
            f"是否就业: {self.employed}\n"
            f"工作: {self.job}\n"
            f"收入: {self.income}\n"
            f"满意度: {self.satisfaction}\n"
            f"叛乱风险: {self.rebellion_risk}\n"
            f"健康状况: {self.health_index}\n"
            f"寿命: {self.lifespan}"
        )
        return status_prompt
    
    def print_resident_status(self):
        """
        打印居民状态（用于调试）
        """
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 的状态：")
        resident_log.info(f"  是否就业：{self.employed}")
        resident_log.info(f"  工作：{self.job}")
        resident_log.info(f"  收入：{self.income}")
        resident_log.info(f"  满意度：{self.satisfaction}")
        resident_log.info(f"  叛乱风险：{self.rebellion_risk}")
        resident_log.info(f"  健康状况：{self.health_index}")
        resident_log.info(f"  寿命：{self.lifespan}")

    def update_lifespan(self):
        """
        检查健康状况并更新寿命
        如果寿命更新后为0，认为该居民死亡，输出提示信息并从列表中删除该用户
        """
        if self.health_index <= 1:
            self.lifespan -= 5
        else:
            self.lifespan -= 1
        
        if self.lifespan <= 0:
            resident_log.info(f"居民 {self.resident_id} 的健康状况为 {self.health_index}，寿命更新为 {self.lifespan}，该居民已死亡。")
            return False
        else:
            resident_log.info(f"居民 {self.resident_id} 的健康状况为 {self.health_index}，寿命更新为 {self.lifespan}。")

