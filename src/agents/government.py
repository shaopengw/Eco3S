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

class OrdinaryGovernmentAgent(BaseAgent):
    def __init__(self, agent_id, government, shared_pool, model_type=None):
        super().__init__(agent_id, group_type='government', window_size=3)
        self.government = government
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        self.map = government.map
        self.function = None
        self.faction = None
        self.mbti = None
        self.system_message = "你是一位政府普通官员，负责根据自身属性和政府状态提出政策建议，政策目标是维护统治的稳定性。"
        self.opinion_prompt_template = (
            "你是一位清代政府普通官员，以下是你的个人属性：\n"
            "职能: {role}\n"
            "人物性格: {mbti}\n"
            "\n所有官员的观点包括：{discussions}\n"
            "\n请根据你的个人属性和立场，对这些观点发表自己的看法。"
            "可以选择支持、反对或提出新的观点。"
            "请用简短的一句话回复。"
        )

    async def generate_opinion(self):
        """
        生成一句关于政治决策的意见
        :return: 生成的意见内容
        """
        river_price = self.government.transport_economy.river_price
        sea_price = self.government.transport_economy.sea_price
        
        # 获取当前政府状态
        government_status = (
            f"当前政府状态：\n"
            f"财政预算: {self.government.get_budget():.2f}两,\n"
            f"军事力量: {self.government.get_military_strength():.2f},\n"
            f"河运价格（固定）: {river_price:.2f}两/吨,海运价格（固定）： {sea_price:.2f}两/吨。注意：海运为新兴市场，便宜但无法提供岗位；河运为传统市场，更贵但能提供就业岗位，加强民生。\n"
        )

        # 构建提示信息
        prompt = (
            f"你是一位清代政府普通官员，以下是你的个人属性：\n"
            f"职能: {self.function},"
            f"派别：{self.faction},"
            f"人物性格: {self.mbti},"
            f"{government_status}\n"
            f"请根据你的个人属性以及当前政府状态和讨论内容，提出一个或多个具体决策意见，可以只关心自己职能范围内的内容：\n"
            f"就业预算（整数）、河运比例（0-1之间的小数）、维护资金（整数）、军事拨款（整数）、税率调整（-0.1到0.1之间的小数）\n"
            f"请用一句话概括你的建议，并给出具体的数值建议"
        )
        opinion = await self.generate_llm_response(prompt, self.system_message)
        if opinion:
            await self.memory.write_record(
                role_name="普通政府官员",
                content=f"我的意见：{opinion}",
                is_user=False,
                store_in_shared=False  # 不存入共享记忆
                )
            await self.shared_pool.add_discussion(opinion)
            government_log.info(f"普通政府官员 {self.agent_id} 生成的意见：{opinion}")
            return opinion
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
                f"你是一位清代政府普通官员，以下是你的个人属性：\n"
                f"\n职能: {self.function}"
                f"\n派别: {self.faction}"
                f"\n人物性格: {self.mbti}"
                f"\n所有官员的观点包括：{all_discussion}"
                f"\n请根据你的个人属性、派别和立场，对这些观点发表自己的看法。"
                f"可以选择支持、反对或提出新的观点。"
                f"请用简短的一句话回复，并给出具体的数值建议"
            )

            try:
                opinion = await self.generate_llm_response(prompt, self.system_message)
                if opinion:
                    await self.shared_pool.add_discussion(opinion)
                    government_log.info(f"普通官员 {self.agent_id} 回应了讨论：{opinion}")
            except Exception as e:
                government_log.error(f"普通官员 {self.agent_id} 在生成回应时出错：{e}")
        else:
            # 如果没有讨论内容，生成新话题
            print("没有讨论内容")
            # opinion = await self.generate_opinion()
            # await self.shared_pool.add_discussion(opinion)
            # government_log.info(f"普通官员 {self.agent_id} 发起了新讨论：{opinion}")

class HighRankingGovernmentAgent(BaseAgent):
    def __init__(self, agent_id, government, shared_pool):
        """
        初始化高级政府官员类（决策者）
        :param agent_id: 政府官员的唯一标识符
        :param government: 政府对象，用于获取政府状态
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        super().__init__(agent_id, group_type='government', window_size=3)
        self.government = government
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        self.map = government.map

        # 初始化官员属性
        self.function = None  # 职能
        self.mbti = None  # 人物性格
        
        # 系统消息
        self.system_message = "你是一个清代地方政府高级官员，负责根据下属官员的讨论和当前政府状态做出最终决策，你的目标是维持地方统治稳定，同时完成中央政府下达的航运任务。其中航运包括河运和海运，河运具有创造大量沿线就业岗位的优势，而海运具有成本极低的优势。"

    async def make_decision(self, summary):
        """
        根据普通政府官员的讨论作出决策
        :return: 决策结果
        """
        # 等待讨论结束
        if not self.shared_pool.is_ended():
            return None
        # 政府状态删去运河维护政策支持，改为运河状态（通航比率），增加当前失业率
        #       决策为多个动作的组合。如果支出之和大于财政预算，则优先满足重要的（决策按照重要性排序）。
        # TODO: (考虑)政府和叛军的决策，只计算比例， 然后系统根据现有资源自动计算绝对值。这样避免LLM输出结果超过预算。
        # ... existing code ...

        river_price = self.government.transport_economy.river_price
        sea_price = self.government.transport_economy.sea_price
        transport_task = self.government.transport_economy.transport_task
        current_budget = self.government.get_budget()
        
        # 计算各项支出的成本基准
        transport_cost_river = river_price * transport_task  # 全部河运成本
        transport_cost_sea = sea_price * transport_task      # 全部海运成本

        decision_prompt = (
            f"你是清代政府高级官员，负责根据下属讨论做出最终决策。\n\n"
            f"当前状态：\n"
            f"预算: {current_budget:.2f}两,军事力量: {self.government.get_military_strength():.2f},税率: {self.government.get_tax_rate()*100:.1f}%\n"
            f"运输任务: {transport_task}吨,河运: {river_price:.2f}两/吨,海运: {sea_price:.2f}两/吨\n\n"
            
            f"成本计算：\n"
            f"运输成本 = 河运比例×{transport_cost_river:.2f} + 海运比例×{transport_cost_sea:.2f}\n"
            f"总支出 = 运输成本 + 就业预算 + 维护资金 + 军事拨款\n"
            f"总支出必须 ≤ {current_budget:.2f}两\n\n"
            
            f"下属讨论：\n{summary}\n\n"
            
            f"请做出合理决策，确保总支出不超预算。输出JSON：\n"
            f'{{"increase_employment": 就业预算（整数）, "transport_ratio": 河运比例（0-1）, "maintenance_investment": 维护资金（整数）, "military_support": 军事拨款（整数）, "tax_adjustment": 税率调整（-0.1到0.1）}}\n'
        )
        # decision_prompt = (
        #     f"你是一位清代政府高级官员，负责根据下属官员的讨论和当前政府状态做出最终决策。\n"
        #     f"当前政府状态：\n"
        #     f"财政预算: {self.government.get_budget()}\n"
        #     f"军事力量: {self.government.get_military_strength()}\n"
        #     f"运输总任务量: {transport_task}吨,"
        #     f"河运价格: {river_price:.2f}两/吨,海运价格： {sea_price:.2f}两/吨。注意：海运便宜但无法提供岗位，河运更贵且需要额外投入维护资金，但能提供就业岗位，加强民生。\n"
        #     f"当前税率: {self.government.get_tax_rate()*100:.1f}%\n"
        #     f"\n"
        #     f"下属官员们的讨论报告：\n{summary}\n"
        #     f"\n"
        #     f"你需要通过设置合理的税率获得财政收入，合理分配预算支出和运输比例，以尽可能少的成本完成施政目标。不需要解释理由，务必确认支出总额不高于当前财政预算。输出为 JSON，严格遵守以下格式：\n"
            # f'{{"increase_employment": 提供就业的预算分配（整数）, "transport_ratio": 运输投入比例（浮点数，0-1，0表示全部海运，1表示全部河运）, "maintenance_investment": 维护运河投入资金（整数，如果不维护则为0）, "military_support": 军需拨款的预算分配（整数）, "tax_adjustment": 税率调整值（浮点数，范围-0.1到0.1）}}\n'
        #  )
        try:
            # 调用模型做出最终决策
            decision = await self.generate_llm_response(decision_prompt, self.system_message)

            if decision:
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
    def __init__(self, map, job_market, military_strength, initial_budget, time, transport_economy):
        """
        初始化政府类
        :param map: 地图对象，用于获取地理信息
        :param job_market: 就业市场对象，用于提供就业机会
        :param initial_budget: 初始预算
        """
        self.map = map
        self.job_market = job_market
        self.budget = initial_budget
        self.military_strength = military_strength
        self.time = time
        self.tax_rate = 0.1  # 初始税率为 10%
        self.residents = {}  # 添加居民引用
        self.transport_economy = transport_economy  # 运输经济模型引用

    def provide_jobs(self,budget_allocation):
        """
        提供就业机会
        """
        # TODO : 提供就业机会/以工代赈，不仅限于运河沿线地区，而是均匀分布在各地区。
        if self.budget >= budget_allocation:
            job_amount = int(budget_allocation / 10)
            self.job_market.add_random_jobs(job_amount)
            self.budget -= budget_allocation
            print(f"政府提供{job_amount}个工作岗位。")
        else:
            print("政府预算不足以提供工作。")

    def maintain_canal(self, maintenance_investment):
        """
        维护运河
        :param maintenance_investment: 投资金额
        :return: 是否维护成功
        """
        # 维护运河有三个方面的影响：
        # 1. 改善运河状态（运河通航能力，取值范围：[0,1]），从而降低运输成本。否则运输成本上升，政府需要支出更多的预算来完成运输。
        # 2. 提供就业机会，增加居民满意度。但是提供的就业机会仅限运河沿线地区。
        # 3. 政府预算减少
        # 计算并更新改善后的通航能力
        maintenance_ratio = maintenance_investment / self.transport_economy.maintenance_cost_base
        self.map.update_river_condition(maintenance_ratio) 
        
        # 提供就业机会
        job_opportunities = int(maintenance_investment / 100)
        if job_opportunities > 0:
            self.job_market.add_job("运河维护工人", job_opportunities)
        
        # 扣除支出
        self.budget -= maintenance_investment
        
        print(f"政府维护运河。通航能力：{self.map.get_navigability():.2f}，支出：{maintenance_investment:.2f}两，新增就业岗位：{job_opportunities}个")
        return True

    def handle_transport_decision(self, transport_ratio):
        """
        处理运输决策
        :param transport_ratio: 河运投入比例（0-1）
        :return: 是否决策成功
        """
        # 计算总运输成本
        total_cost = self.transport_economy.calculate_total_transport_cost(transport_ratio)
        
        # 检查预算是否充足，不足则自动调整比例
        if self.budget < total_cost:
            # 计算最大可负担比例
            max_affordable_ratio = self.budget / (self.transport_economy.river_price * self.transport_economy.transport_task)
            transport_ratio = min(transport_ratio, max_affordable_ratio)
            print(f"预算不足，自动调整河运比例为{transport_ratio:.2f}")
        
        # 扣除运输成本
        self.budget -= total_cost
        
        print(f"政府运输决策。河运比例：{transport_ratio:.2f}，实际支出：{total_cost:.2f}两")
        return True

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
            self.is_discussion_ended = False

    def is_ended(self) -> bool:
        """
        检查讨论是否结束
        """
        return self.is_discussion_ended

class InformationOfficer(OrdinaryGovernmentAgent):
    def __init__(self, agent_id, government, shared_pool, model_type="gpt-3.5-turbo"):
        super().__init__(agent_id, government, shared_pool, model_type)
        self.function = "信息整理官"
        self.system_message = "你是清代政府高级官员的秘书，负责整理和总结主要官员的讨论内容。"

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
            f"你是清代政府高级官员的秘书，请你整理以下{len(discussions)}条关于政府决策的讨论内容，"
            f"提供一个简明扼要的总结报告。报告中应包含讨论中提及的具体数值建议，尽可能简洁。\n\n"\
            f"讨论内容：\n" + "\n".join([f"{i+1}. {d}" for i, d in enumerate(discussions)])
        )

        try:
            summary = await self.generate_llm_response(prompt)
            if summary:
                government_log.info(f"信息整理官 {self.agent_id} 生成的总结报告：{summary}")
                return summary
            return "无法生成总结报告"
        except Exception as e:
            government_log.error(f"信息整理官 {self.agent_id} 在生成总结报告时出错：{e}")
            return "无法生成总结报告"
