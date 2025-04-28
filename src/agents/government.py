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
    def __init__(self, agent_id, government, shared_pool, model_type=None):
        self.model_type = model_type
        self.agent_id = agent_id
        self.government = government
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        self.map = government.map

        # 初始化官员属性
        self.function = None  # 职能
        self.mbti = None  # 人物性格

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
        # self.memory = ChatHistoryMemory(self.context_creator, window_size=3)
        self.memory = MemoryManager(
            agent_id=self.agent_id,
            model_type=self.model_type,
            group_type='government',  # 指定为政府群体
            window_size=3
        )
        # 系统消息
        self.system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content="你是一位普通政府官员，负责根据个人属性和政府状态提出意见。"
        )

    async def generate_opinion(self):
        """
        生成一句关于政治决策的意见
        :return: 生成的意见内容
        """
        # 获取当前政府状态
        government_status = (
            f"当前政府状态：\n"
            f"财政预算: {self.government.get_budget()}\n"
            f"军事力量: {self.government.get_military_strength()}\n"
            f"运河通航比率: {self.map.get_navigability()}（海运通航比率：{1-self.map.get_navigability()}）\n"
        )

        # 构建提示信息
        prompt = (
            f"你是一位普通清代政府官员，以下是你的个人属性：\n"
            f"职能: {self.function}\n"
            f"人物性格: {self.mbti}\n"
            f"{government_status}\n"
            f"请根据你的个人属性、当前政府状态和讨论内容，提出一句关于大运河运营的政治决策的意见。尽可能简洁，不必说明理由。"
        )

        # 使用 CAMEL 框架生成意见
        user_message = BaseMessage.make_user_message(
            role_name="普通政府官员",
            content=prompt,
        )

        # 获取历史信息
        openai_messages = await self.memory.get_context_messages(prompt)
        if not openai_messages:
            openai_messages = [{
                "role": self.system_message.role_name,
                "content": self.system_message.content,
            }] + [user_message.to_openai_user_message()]

        government_log.info(f"普通政府官员 {self.agent_id} 正在生成意见，提示信息：{openai_messages}")

        try:
            # 调用模型生成意见
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)  # 异步运行模型
            opinion = response.choices[0].message.content
            # 决策存入个人记忆
            await self.memory.write_record(
                role_name="普通政府官员",
                content=f"我的意见：{opinion}",
                is_user=False,
                store_in_shared=False  # 不存入共享记忆
                )
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
        all_discussion = await self.shared_pool.get_all_discussions()
        if all_discussion:
            # 构建提示信息，让AI决定是否回应以及如何回应
            prompt = (
                f"你是一位普通清代政府官员，以下是你的个人属性：\n"
                f"职能: {self.function}\n"
                f"人物性格: {self.mbti}\n"
                f"\n所有官员的观点包括：{all_discussion}\n"
                f"\n请根据你的个人属性和立场，对这些观点发表看法。"
                f"可以选择支持、反对或提出新的观点。"
                f"请用简短的一句话回复，语气要符合清朝官员的特点。"
            )

            # 使用CAMEL框架生成回应
            user_message = BaseMessage.make_user_message(
                role_name="普通政府官员",
                content=prompt,
            )

            try:
                response = await asyncio.to_thread(self.model_backend.run, [user_message.to_openai_user_message()])
                opinion = response.choices[0].message.content
                # 回复信息添加到共享信息池
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
        self.map = government.map

        # 初始化官员属性
        self.function = None  # 职能
        self.mbti = None  # 人物性格

        # 初始化 CAMEL 框架组件
        # 根据API类型获取模型类型
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
        # self.memory = ChatHistoryMemory(self.context_creator, window_size=5)
        self.memory = MemoryManager(
            agent_id=self.agent_id,
            model_type=self.model_type,
            group_type='government',  # 指定为政府群体
            window_size=5
        )

    async def make_decision(self, summary, round_num):
        """
        根据普通政府官员的讨论作出决策
        :return: 决策结果
        """
        # 等待讨论结束
        if not self.shared_pool.is_ended():
            return None
        # TODO :政府状态删去运河维护政策支持，改为运河状态（通航比率），增加当前失业率
        #       决策内容删去提供公共服务。
        #       可以考虑决策结果可以是多个动作的组合。如果支出之和大于财政预算，则优先满足重要的（决策按照重要性排序）。
        decision_prompt = (
            f"你是一个高级政府官员，负责根据下属官员的讨论和当前政府状态做出最终决策。\n"
            f"请为以下每个政策分配预算或调整参数。你需要合理分配总预算，建议保留20%-30%的预算作为储备，以应对突发事件。\n"
            f"输出格式为 JSON，包含以下字段：\n"
            f"- increase_employment: 增加就业的预算分配（整数）\n"
            # f"- canal_navigability: 运河通航比率（浮点数，范围0到1，1表示完全通航，0表示完全不通航。注意：海运通航比率将自动设为1-运河通航比率）\n"
            f"- maintain_canal: 维护运河的预算分配（整数）\n"
            f"- military_support: 军需拨款的预算分配（整数）\n"
            f"- tax_adjustment: 税率调整值（浮点数，范围-0.1到0.1）\n"
            f"\n"
            f"当前政府状态：\n"
            f"财政预算: {self.government.get_budget()}\n"
            f"军事力量: {self.government.get_military_strength()}\n"
            f"运河通航比率: {self.map.get_navigability()}（海运通航比率：{1-self.map.get_navigability()}）\n"
            f"当前税率: {self.government.get_tax_rate()*100:.1f}%\n"
            f"\n"
            f"普通政府官员们的讨论报告：\n{summary}\n"
            f"\n"
            f"请根据以上信息和状态作出最终决策，不要解释理由，只需输出JSON格式的决策结果。记住要保留足够的预算储备。例如：\n"
            f'{{"increase_employment": 100000, "canal_navigability": 0.8, "military_support": 50000, "tax_adjustment": -0.02}}'
        )

        # 获取历史上下文
        openai_messages = await self.memory.get_context_messages(decision_prompt)
        if not openai_messages:
            openai_messages = [{
                "role": "系统",
                "content": "你是一个高级政府官员，你的目标是维持社会稳定，完成航运任务。其中航运包括河运和海运，河运具有提供运河沿线就业岗位的优势，但是成本相比海运高。你需要根据下属官员的讨论和当前政府状态做出最终决策。"
            }]

        government_log.info(f"高级政府官员 {self.agent_id} 正在处理决策，提示信息：{openai_messages}")

        try:
            # 调用模型做出最终决策
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)
            decision = response.choices[0].message.content

            # 将讨论内容和决策合并写入记忆系统
            combined_content = f"讨论总结：\n{summary}\n\n决策结果：\n{decision}"
            await self.memory.write_record(
                role_name="高级政府官员",
                content=combined_content,
                is_user=False,
                round_num=round_num
            )

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
        self.time = time
        self.tax_rate = 0.1  # 初始税率为 10%
        self.residents = {}  # 添加居民引用

    def provide_jobs(self,budget_allocation):
        """
        提供就业机会
        """
        # TODO : 提供就业机会/以工代赈，不仅限于运河沿线地区，而是均匀分布在各地区。
        if self.budget >= budget_allocation:
            self.job_market.add_job("Canal Maintenance")
            self.budget -= budget_allocation
            print("政府提供运河维护工作。")
        else:
            print("政府预算不足以提供工作。")

    def maintain_canal(self, budget_allocation):
        """
        维护运河
        :param budget_allocation: 预算分配
        :return: 是否维护成功
        """
        # TODO : 维护运河有三个方面的影响：
        # 1. 改善运河状态（运河通航能力，取值范围：[0,1]），从而降低运输成本。否则运输成本上升，政府需要支出更多的预算来完成运输。
        # 2. 提供就业机会，增加居民满意度。但是提供的就业机会仅限运河沿线地区。
        # 3. 政府预算减少：支出=预算分配+运输成本=预算分配+运河状态*河运成本系数+（1-运河状态）*海运成本系数。
        #   河运成本系数 = 0.5，海运成本系数 = 0.1。
        if self.budget >= budget_allocation:
            # 1. 改善运河状态，维护系数与预算分配成正比
            # 假设每1000两可以提升0.1的通航能力
            maint_factor = min(1.0, budget_allocation / 10000)
            current_navigability = self.map.update_river_condition(maint_factor)
            
            # 2. 计算运输成本
            # 河运成本系数 = 0.5，海运成本系数 = 0.1
            transport_cost = (current_navigability * 0.5 + (1 - current_navigability) * 0.1) * budget_allocation
            
            # 3. 提供就业机会（仅限运河沿线地区）
            # 假设每100两预算可以提供1个工作岗位
            job_opportunities = int(budget_allocation / 100)
            if job_opportunities > 0:
                self.job_market.add_jobs("运河维护工人", job_opportunities)
            
            # 扣除总支出（预算分配+运输成本）
            total_cost = budget_allocation + transport_cost
            self.budget -= total_cost
            
            print(f"政府维护运河。通航能力：{current_navigability:.2f}，总支出：{total_cost:.2f}两，新增就业岗位：{job_opportunities}个")
            return True
        else:
            print(f"政府预算不足（需要{budget_allocation}两），无法维护运河。")
            return False

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
        #  TODO : 无论是否镇压叛乱，都要消耗军事力量。如果成功镇压叛乱，则居民满意度不变，否则将减少就业岗位（逻辑：地区动乱，商业衰败，居民失业）
        if self.military_strength >= rebellion_strength:
            self.military_strength -= rebellion_strength * 0.1  # 军事力量消耗
            print(f"政府成功压制了强度为 {rebellion_strength} 的叛乱。")
            return True
        else:
            print(f"政府未能压制强度为 {rebellion_strength} 的叛乱。")
            return False

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

    def adjust_tax_rate(self, adjustment):
        """
        调整税率并更新居民满意度
        :param adjustment: 税率调整值（浮点数，正数表示增加，负数表示减少）
        """
        old_rate = self.tax_rate
        # 限制税率在 0% 到 50% 之间
        self.tax_rate = max(0.0, min(0.5, self.tax_rate + adjustment))

        # # 根据税率变化调整所有居民的满意度
        # for resident in self.residents.values():
        #     if self.tax_rate > old_rate:
        #         # 税率上升，满意度下降（影响更大）
        #         resident.satisfaction -= (self.tax_rate - old_rate) * 200
        #     else:
        #         # 税率下降，满意度上升（影响较小）
        #         resident.satisfaction += (old_rate - self.tax_rate) * 100

        #     # 确保满意度在合理范围内
        #     resident.satisfaction = max(0, min(100, resident.satisfaction))

        print(f"税率从 {old_rate*100:.1f}% 调整到 {self.tax_rate*100:.1f}%")
        return self.tax_rate

    def get_tax_rate(self):
        """
        获取当前税率
        :return: 当前税率
        """
        return self.tax_rate

    def print_government_status(self):
        """
        打印政府状态（用于调试）
        """
        print(f"政府预算: {self.budget}")
        print(f"军事力量: {self.military_strength}")
        print(f"运河通航比率: {self.map.get_navigability()}（海运通航比率：{1-self.map.get_navigability()}）")
        print(f"当前税率: {self.tax_rate*100:.1f}%")

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
