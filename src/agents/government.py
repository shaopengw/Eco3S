from .shared_imports import *
load_dotenv()

if "sphinx" not in sys.modules:
    government_log = logging.getLogger(name="government.agent")
    government_log.setLevel("DEBUG")
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs("./log", exist_ok=True)
    file_handler = logging.FileHandler(f"./log/government.agent-{str(now)}.log")
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
    government_log.addHandler(file_handler)

class OrdinaryGovernmentAgent:
    def __init__(self, agent_id, government, shared_pool):

        self.agent_id = agent_id
        self.government = government
        self.shared_pool = shared_pool 
        self.time = 0  # 当前时间（年）

        # 初始化官员属性
        self.function = None  # 职能
        self.mbti = None  # 人物性格

        # 初始化 CAMEL 框架组件
        # 根据API类型获取模型类型
        api_type = os.getenv("API_TYPE", "OPENAI")
        model_type_env = os.getenv(f"{api_type}_MODEL_TYPE", "gpt-3.5-turbo")
        self.model_type = ModelType(model_type_env)
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = ChatHistoryMemory(self.context_creator, window_size=3)
        # 系统消息
        self.system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content="你是一位普通政府官员，负责根据个人属性和政府状态提出意见。"
        )

    async def generate_opinion(self):
        """
        利用 AI 生成一句关于政治决策的意见
        :return: 生成的意见内容
        """
        # 获取当前政府状态
        government_status = (
            f"当前政府状态：\n"
            f"预算: {self.government.get_budget()}\n"
            f"军事力量: {self.government.get_military_strength()}\n"
            f"运河维护政策支持: {self.government.policy_support_canal}\n"
        )

        # 从共享信息池中获取最新的讨论内容
        latest_discussion = await self.shared_pool.get_latest_discussion()
        if latest_discussion:
            discussion_context = f"讨论内容：\n{latest_discussion}\n"
        else:
            discussion_context = f"讨论内容：\n"

        # 构建提示信息
        prompt = (
            f"你是一位普通代会政府官员，以下是你的个人属性：\n"
            f"职能: {self.function}\n"
            f"人物性格: {self.mbti}\n"
            f"{government_status}\n"
            f"{discussion_context}\n"
            f"请根据你的个人属性、当前政府状态和讨论内容，提出一句关于大运河运营的政治决策的意见。尽可能简洁，不必说明理由。"
        )

        # 使用 CAMEL 框架生成意见
        user_message = BaseMessage.make_user_message(
            role_name="普通政府官员",
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

        government_log.info(f"普通政府官员 {self.agent_id} 正在生成意见，提示信息：{openai_messages}")

        try:
            # 调用模型生成意见
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)  # 异步运行模型
            # response = self.model_backend.run(openai_messages)
            opinion = response.choices[0].message.content
            # # 只保存模型的回复内容到记忆
            # self.memory.write_record(
            #     MemoryRecord(
            #         message=BaseMessage.make_assistant_message(
            #             role_name="普通政府官员",
            #             content=opinion,
            #         ),
            #         role_at_backend=OpenAIBackendRole.ASSISTANT,
            #     )
            # )
            government_log.info(f"普通政府官员 {self.agent_id} 生成的意见：{opinion}")
            return opinion
        except Exception as e:
            government_log.error(f"普通政府官员 {self.agent_id} 在生成意见时出错：{e}")
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
                f"你是一位普通清代政府官员，以下是你的个人属性：\n"
                f"职能: {self.function}\n"
                f"人物性格: {self.mbti}\n"
                f"\n最新的讨论内容是：{latest_discussion}\n"
                f"\n请根据你的个人属性和立场，决定是否对这个观点发表看法。"
                f"如果决定发表看法，可以选择支持、反对或提出新的建议。"
                f"请用简短的一句话回复，语气要符合清朝官员的特点。"
                f"如果决定不回复，请返回'不予置评'。"
            )
            
            # 使用CAMEL框架生成回应
            user_message = BaseMessage.make_user_message(
                role_name="普通政府官员",
                content=prompt,
            )
            
            try:
                response = await asyncio.to_thread(self.model_backend.run, [user_message.to_openai_user_message()])
                opinion = response.choices[0].message.content
                
                # 如果AI决定回复，则添加到共享信息池
                if opinion and opinion != "不予置评":
                    await self.shared_pool.add_discussion(opinion)
                    government_log.info(f"普通官员 {self.agent_id} 回应了讨论：{opinion}")
                
            except Exception as e:
                government_log.error(f"普通官员 {self.agent_id} 在生成回应时出错：{e}")
        else:
            # 如果没有讨论内容，生成新话题
            opinion = await self.generate_opinion()
            await self.shared_pool.add_discussion(opinion)
            government_log.info(f"普通官员 {self.agent_id} 发起了新讨论：{opinion}")
    
class HighRankingGovernmentAgent:
    def __init__(self, agent_id, government, shared_pool):
        """
        初始化高级政府官员类（决策者）
        :param agent_id: 政府官员的唯一标识符
        :param government: 政府对象，用于获取政府状态
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.agent_id = agent_id
        self.government = government
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        
        # 初始化官员属性
        self.function = None  # 职能
        self.mbti = None  # 人物性格

        # 初始化 CAMEL 框架组件
        # 根据API类型获取模型类型
        api_type = os.getenv("API_TYPE", "OPENAI")
        model_type_env = os.getenv(f"{api_type}_MODEL_TYPE", "gpt-3.5-turbo")
        self.model_type = ModelType(model_type_env)
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = ChatHistoryMemory(self.context_creator, window_size=5)

    async def make_decision(self, summary):
        """
        根据普通政府官员的讨论作出决策
        :param discussion_report: 普通政府官员的讨论报告
        :return: 决策结果
        """
        # 等待讨论结束
        if not self.shared_pool.is_ended():
            return None
        
        # 获取讨论总结
        discussion_report = summary
        
        # 使用 CAMEL 框架来做决策
        decision_message = BaseMessage.make_user_message(
            role_name="高级政府官员",
            content=(
                f"你是一个高级政府官员，负责根据下属官员的讨论和当前政府状态做出最终决策。\n"
                f"请从以下动作中选择一个，并提供一个参数：\n"
                f"- 增加就业: 参数为 `预算分配`（整数）\n"
                f"- 维护运河: 参数为 `预算分配`（整数）\n"
                f"- 提供公共服务: 参数为 `预算分配`（整数）\n"
                f"- 军需拨款: 参数为 `预算分配`（整数）\n"
                f"\n"
                f"当前政府状态：\n"
                f"预算: {self.government.get_budget()}\n"
                f"军事力量: {self.government.get_military_strength()}\n"
                f"运河维护政策支持: {self.government.policy_support_canal}\n"
                f"\n"
                f"普通政府官员们的讨论报告：\n{discussion_report}\n"
                f"\n"
                f"请根据以上信息和状态作出最终决策，输出格式为 JSON，例如：\n"
                f'{{"action": "维护运河", "params": 2000000}}'
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
                "content": "你是一个高级政府官员，负责根据下属官员的讨论和当前政府状态做出最终决策。"
            }] + [decision_message.to_openai_user_message()]

        government_log.info(f"高级政府官员 {self.agent_id} 正在处理决策，提示信息：{openai_messages}")
        
        try:
            # 调用模型做出最终决策
            response = self.model_backend.run(openai_messages)
            decision = response.choices[0].message.content
            government_log.info(f"高级政府官员 {self.agent_id} 的决策：{decision}")
            # 清空共享信息池
            await self.shared_pool.clear_discussions()
            return decision
        except Exception as e:
            government_log.error(f"高级政府官员 {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def print_agent_status(self):
        """
        打印高级政府官员的状态
        """
        government_log.info(f"高级政府官员 {self.agent_id} 的状态：")
        government_log.info(f"  当前时间：{self.time}年")
        government_log.info(f"  职能：{self.function}")
        government_log.info(f"  人物性格：{self.mbti}")

class Government:
    def __init__(self, map, job_market, initial_budget, time):
        """
        初始化政府类
        :param map: 地图对象，用于获取地理信息
        :param job_market: 就业市场对象，用于提供就业机会
        :param initial_budget: 初始预算
        """
        self.map = map
        self.job_market = job_market
        self.budget = initial_budget
        self.military_strength = 100  # 初始军事力量
        self.policy_support_canal = True  # 是否支持运河维护
        self.time = time

    def provide_jobs(self,budget_allocation):
        """
        提供就业机会
        """
        if self.budget >= budget_allocation:
            self.job_market.add_job("Canal Maintenance")
            self.budget -= budget_allocation
            print("政府提供运河维护工作。")
        else:
            print("政府预算不足以提供工作。")

    def maintain_canals(self, budget_allocation):
        """
        维护运河
        """
        if self.policy_support_canal and self.budget >= budget_allocation:
            self.map.update_river_condition(year=self.time.get_current_year())
            self.budget -= budget_allocation
            print("政府维护运河。")
        else:
            print("政府因政策或预算限制未维护运河。")

    def support_military(self, budget_allocation):
        """
        军需拨款
        :param budget_allocation: 分配给军事力量的预算
        """
        if self.budget >= budget_allocation:
            self.military_strength += budget_allocation * 0.1  # 假设每投入1单位预算，军事力量增加0.1
            self.budget -= budget_allocation
            print(f"政府支持军事力量，军事力量增加了 {budget_allocation * 0.1}。")
        else:
            print("政府因预算限制未支持军事力量。")
        
    def suppress_rebellion(self, rebellion_strength):
        """
        镇压叛乱
        :param rebellion_strength: 叛乱的强度
        :return: 是否成功镇压叛乱（布尔值）
        """
        if self.military_strength >= rebellion_strength:
            self.military_strength -= rebellion_strength * 0.1  # 军事力量消耗
            print(f"政府成功压制了强度为 {rebellion_strength} 的叛乱。")
            return True
        else:
            print(f"政府未能压制强度为 {rebellion_strength} 的叛乱。")
            return False
    def provide_public_services(self, budget_allocation):
        """
        提供公共服务（如粮食救济）
        """
        if self.budget >= budget_allocation:
            self.budget -= budget_allocation
            print("政府提供公共服务（如粮食救济）。")
        else:
            print("政府预算不足以提供公共服务。")

    def set_policy_support_canal(self, support):
        """
        设置是否支持运河维护的政策
        :param support: 是否支持运河维护（布尔值）
        """
        self.policy_support_canal = support
        print(f"政府关于运河维护政策的支持已设置为 {support}。")

    def get_budget(self):
        """
        获取当前预算
        :return: 当前预算
        """
        return self.budget

    def get_military_strength(self):
        """
        获取当前军事力量
        :return: 当前军事力量
        """
        return self.military_strength

    def print_government_status(self):
        """
        打印政府状态（用于调试）
        """
        print(f"政府预算: {self.budget}")
        print(f"军事力量: {self.military_strength}")
        print(f"运河维护政策支持: {self.policy_support_canal}")

class government_SharedInformationPool:
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
        """
        添加讨论内容到共享信息池
        :param discussion: 讨论内容
        :return: 是否成功添加（如果讨论已结束则返回False）
        """
        async with self.lock:
            if self.is_discussion_ended:
                return False
            self.discussions.append(discussion)
            if len(self.discussions) >= self.max_discussions:
                self.is_discussion_ended = True
            return True

    async def get_latest_discussion(self):
        """
        获取最新的讨论内容
        :return: 最新的讨论内容
        """
        async with self.lock:
            if self.discussions:
                latest_discussion = self.discussions[-1]
                return latest_discussion
            else:
                return None

    async def get_all_discussions(self):
        """
        获取所有讨论内容
        :return: 所有讨论内容的列表
        """
        async with self.lock:
            if self.discussions:
                return self.discussions
            else:
                return []
    async def clear_discussions(self):
        """
        清空所有讨论内容
        """
        async with self.lock:
            self.discussions.clear()

    def is_ended(self) -> bool:
        """
        检查讨论是否结束
        """
        return self.is_discussion_ended

class InformationOfficer(OrdinaryGovernmentAgent):
    def __init__(self, agent_id, government, shared_pool, model_type="gpt-3.5-turbo"):
        super().__init__(agent_id, government, shared_pool, model_type)
        self.function = "信息整理官"
        self.system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content="你是一位政府信息整理官，负责整理和总结其他官员的讨论内容。"
        )

    async def summarize_discussions(self) -> str:
        """
        整理和总结所有讨论内容
        :return: 总结后的报告
        """
        discussions = await self.shared_pool.get_all_discussions()
        if not discussions:
            return "暂无讨论内容"

        # 构建提示信息
        prompt = (
            f"作为信息整理官，请你整理以下{len(discussions)}条关于大运河管理的讨论内容，"
            f"提供一个简明扼要的总结报告。\n\n"
            f"讨论内容：\n" + "\n".join([f"{i+1}. {d}" for i, d in enumerate(discussions)])
        )

        # 使用 CAMEL 框架生成总结
        user_message = BaseMessage.make_user_message(
            role_name="信息整理官",
            content=prompt,
        )

        openai_messages = [{
            "role": self.system_message.role_name,
            "content": self.system_message.content,
        }, user_message.to_openai_user_message()]

        try:
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)
            summary = response.choices[0].message.content
            government_log.info(f"信息整理官 {self.agent_id} 生成的总结报告：{summary}")
            return summary
        except Exception as e:
            government_log.error(f"信息整理官 {self.agent_id} 在生成总结报告时出错：{e}")
            return "无法生成总结报告"
