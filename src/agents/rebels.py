from .shared_imports import *
load_dotenv()

if "sphinx" not in sys.modules:
    rebellion_log = logging.getLogger(name="rebels.agent")
    rebellion_log.setLevel("DEBUG")
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_handler = logging.FileHandler(f"./log/rebels.agent-{str(now)}.log")
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
    rebellion_log.addHandler(file_handler)

class OrdinaryRebel:
    def __init__(self, rebel_id, rebellion, shared_pool):
        """
        初始化普通叛军类
        :param rebel_id: 叛军的唯一标识符
        :param rebellion: 叛军对象，用于获取叛军状态
        """
        self.rebel_id = rebel_id
        self.rebellion = rebellion
        self.shared_pool = shared_pool
        self.opinions = []  # 收集意见
        self.time = 0  # 当前时间（年）

        # 初始化叛军属性
        self.role = None  # 角色
        self.mbti = None  # 人物性格
        # 初始化 CAMEL 框架组件

        # api_type = os.getenv("API_TYPE", "OPENAI")
        # model_type_env = os.getenv(f"{api_type}_MODEL_TYPE", "gpt-3.5-turbo")
        # self.model_type = ModelType(model_type_env)
        
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
        self.memory = ChatHistoryMemory(self.context_creator, window_size=3)
        # 系统消息
        self.system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content="你是一位普通叛军，负责根据个人属性和叛军状态提出意见。"
        )

    async def generate_opinion(self):
        """
        利用 AI 生成一句关于叛军行动的意见
        :return: 生成的意见内容
        """
        # 获取当前叛军状态
        rebellion_status = (
            f"当前叛军状态：\n"
            f"力量: {self.rebellion.get_strength()}\n"
            f"资源: {self.rebellion.get_resources()}\n"
            f"支持度: {self.rebellion.get_support()}\n"
        )

        # 构建提示信息
        prompt = (
            f"你是一位普通叛军，以下是你的个人属性：\n"
            f"角色: {self.role}\n"
            f"人物性格: {self.mbti}\n"
            f"{rebellion_status}\n"
            f"请根据你的个人属性和当前叛军状态，提出一句关于叛军行动的意见。"
        )

        # 使用 CAMEL 框架生成意见
        user_message = BaseMessage.make_user_message(
            role_name="普通叛军",
            content=prompt,
        )
        self.memory.write_record(
            MemoryRecord(
                message=user_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        
        # 获取历史信息
        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": self.system_message.role_name,
                "content": self.system_message.content,
            }] + [user_message.to_openai_user_message()]

        rebellion_log.info(f"普通叛军 {self.rebel_id} 正在生成意见，提示信息：{openai_messages}")

        try:
            # 调用模型生成意见
            # response = self.model_backend.run(openai_messages)
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)  # 异步运行模型
            opinion = response.choices[0].message.content
            rebellion_log.info(f"普通叛军 {self.rebel_id} 生成的意见：{opinion}")
            return opinion
        except Exception as e:
            rebellion_log.error(f"普通叛军 {self.rebel_id} 在生成意见时出错：{e}")
            return "无法生成意见"

    async def generate_and_share_opinion(self):
        """
        从共享信息池中获取信息并发表看法，将看法放入共享信息池
        """
        # 获取最新讨论内容
        latest_discussion = await self.shared_pool.get_latest_discussion()
        
        if latest_discussion:
            # 构建提示信息，让AI决定是否回应以及如何回应
            prompt = (
                f"你是一位叛军成员，以下是你的个人属性：\n"
                f"角色: {self.role}\n"
                f"人物性格: {self.mbti}\n"
                f"\n最新的讨论内容是：{latest_discussion}\n"
                f"\n请根据你的个人属性和立场，决定是否对这个观点发表看法。"
                f"如果决定发表看法，可以选择支持、反对或提出新的建议。"
                f"请用简短的一句话回复，语气要符合叛军的特点。"
                f"如果决定不回复，请返回'不予置评'。"
            )
            
            # 使用CAMEL框架生成回应
            user_message = BaseMessage.make_user_message(
                role_name="普通叛军",
                content=prompt,
            )
            
            try:
                response = await asyncio.to_thread(self.model_backend.run, [user_message.to_openai_user_message()])
                opinion = response.choices[0].message.content
                
                # 如果AI决定回复，则添加到共享信息池
                if opinion and opinion != "不予置评":
                    await self.shared_pool.add_discussion(opinion)
                    rebellion_log.info(f"普通叛军 {self.rebel_id} 回应了讨论：{opinion}")
                
            except Exception as e:
                rebellion_log.error(f"普通叛军 {self.rebel_id} 在生成回应时出错：{e}")
        else:
            # 如果没有讨论内容，生成新话题
            opinion = await self.generate_opinion()
            await self.shared_pool.add_discussion(opinion)
            rebellion_log.info(f"普通叛军 {self.rebel_id} 发起了新讨论：{opinion}")

    def get_opinions(self):
        """
        获取当前叛军的所有意见
        :return: 叛军的意见列表
        """
        return self.opinions
    
class RebelLeader:
    def __init__(self, leader_id, rebellion, shared_pool):
        self.leader_id = leader_id
        self.rebellion = rebellion
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        
        # 初始化叛军头子属性
        self.role = None  # 角色
        self.mbti = None  # 人物性格

        # 初始化模型管理器
        self.model_manager = ModelManager()
        model_config = self.model_manager.get_random_model_config()
        self.model_type = ModelType(model_config["model_type"])
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=model_config["model_platform"],
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        # self.system_message = "你是一个叛军头子，负责根据下属叛军的讨论和当前叛军状态做出最终决策。"

        # 初始化记忆系统
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = ChatHistoryMemory(self.context_creator, window_size=5)

    async def make_decision(self, discussion_report):
        """
        根据普通叛军的讨论作出决策
        :param discussion_report: 普通叛军的讨论报告
        :return: 决策结果
        """
        # 等待讨论结束
        if not self.shared_pool.is_ended():
            return None
            
        # 使用 CAMEL 框架来做决策
        decision_message = BaseMessage.make_user_message(
            role_name="叛军头子",
            content=(
                f"你是一个叛军头子，负责根据下属叛军的讨论和当前叛军状态做出最终决策。\n"
                f"请从以下动作中选择一个，并提供一个参数：\n"
                f"- 袭击政府设施: 参数为 `力量投入`（整数）\n"
                f"- 招募新成员: 参数为 `资源投入`（整数）\n"
                f"- 争取民众支持: 参数为 `资源投入`（整数）\n"
                f"- 撤退: 参数为 `无`\n"
                f"\n"
                f"当前叛军状态：\n"
                f"力量: {self.rebellion.get_strength()}\n"
                f"资源: {self.rebellion.get_resources()}\n"
                f"支持度: {self.rebellion.get_support()}\n"
                f"\n"
                f"普通叛军们的讨论报告：\n{discussion_report}\n"
                f"\n"
                f"请根据以上信息和状态作出最终决策，输出格式为 JSON，例如：\n"
                f'{{"action": "袭击政府设施", "params": 1000}}'
            )
        )
        
        # 将讨论内容写入记忆系统
        self.memory.write_record(
            MemoryRecord(
                message=decision_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        
        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一个叛军头子，负责根据下属叛军的讨论和当前叛军状态做出最终决策。"
            }] + [decision_message.to_openai_user_message()]

        rebellion_log.info(f"叛军头子 {self.leader_id} 正在处理决策，提示信息：{openai_messages}")
        
        try:
            # 调用模型做出最终决策
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)
            decision = response.choices[0].message.content
            rebellion_log.info(f"叛军头子 {self.leader_id} 的决策：{decision}")
            # 清空共享信息池
            await self.shared_pool.clear_discussions()
            return decision
        except Exception as e:
            rebellion_log.error(f"叛军头子 {self.leader_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def print_leader_status(self):
        """
        打印叛军头子的状态
        """
        rebellion_log.info(f"叛军头子 {self.leader_id} 的状态：")
        rebellion_log.info(f"  当前时间：{self.time}年")
        rebellion_log.info(f"  角色：{self.role}")
        rebellion_log.info(f"  人物性格：{self.mbti}")

class Rebellion:
    def __init__(self, initial_strength, initial_resources, initial_support):
        """
        初始化叛军类
        :param initial_strength: 初始力量
        :param initial_resources: 初始资源
        :param initial_support: 初始支持度
        """
        self.strength = initial_strength
        self.resources = initial_resources
        self.support = initial_support

    def attack_government_facility(self, strength_investment):
        """
        袭击政府设施
        :param strength_investment: 投入的力量
        """
        if self.strength >= strength_investment:
            self.strength -= strength_investment * 0.1  # 力量消耗
            print(f"叛军成功袭击了政府设施，消耗了 {strength_investment * 0.1} 力量。")
        else:
            print("叛军力量不足以袭击政府设施。")

    def recruit_new_members(self, resource_investment):
        """
        招募新成员
        :param resource_investment: 投入的资源
        """
        if self.resources >= resource_investment:
            self.strength += resource_investment * 0.1  # 假设每投入1单位资源，力量增加0.1
            self.resources -= resource_investment
            print(f"叛军成功招募了新成员，力量增加了 {resource_investment * 0.1}。")
        else:
            print("叛军资源不足以招募新成员。")

    def gain_public_support(self, resource_investment):
        """
        争取民众支持
        :param resource_investment: 投入的资源
        """
        if self.resources >= resource_investment:
            self.support += resource_investment * 0.1  # 假设每投入1单位资源，支持度增加0.1
            self.resources -= resource_investment
            print(f"叛军成功争取了民众支持，支持度增加了 {resource_investment * 0.1}。")
        else:
            print("叛军资源不足以争取民众支持。")

    def retreat(self):
        """
        撤退
        """
        print("叛军决定撤退。")

    def get_strength(self):
        """
        获取当前力量
        :return: 当前力量
        """
        return self.strength

    def get_resources(self):
        """
        获取当前资源
        :return: 当前资源
        """
        return self.resources

    def get_support(self):
        """
        获取当前支持度
        :return: 当前支持度
        """
        return self.support

    def print_rebellion_status(self):
        """
        打印叛军状态（用于调试）
        """
        print(f"叛军力量: {self.strength}")
        print(f"叛军资源: {self.resources}")
        print(f"叛军支持度: {self.support}")

class rebels_SharedInformationPool:
    def __init__(self, max_discussions: int = 5):
        """
        初始化共享信息池
        :param max_discussions: 最大讨论数量
        """
        self.discussions = []  # 存储所有讨论内容
        self.max_discussions = max_discussions  # 最大讨论数量
        self.is_discussion_ended = False  # 讨论是否结束
        self.lock = asyncio.Lock()  # 用于异步操作的锁

    async def add_discussion(self, discussion) -> bool:
        """添加讨论内容到共享信息池"""
        async with self.lock:
            if self.is_discussion_ended:
                return False
            self.discussions.append(discussion)
            if len(self.discussions) >= self.max_discussions:
                self.is_discussion_ended = True
            return True

    async def get_latest_discussion(self):
        """获取最新的讨论内容"""
        async with self.lock:
            if self.discussions:
                return self.discussions[-1]
            return None

    async def get_all_discussions(self):
        """获取所有讨论内容"""
        async with self.lock:
            return self.discussions if self.discussions else []

    async def clear_discussions(self):
        """清空所有讨论内容"""
        async with self.lock:
            self.discussions.clear()

    def is_ended(self) -> bool:
        """检查讨论是否结束"""
        return self.is_discussion_ended