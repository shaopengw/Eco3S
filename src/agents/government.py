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
    def __init__(self, agent_id, government, shared_pool):
        super().__init__(agent_id, group_type='government', window_size=3)
        self.government = government
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        self.map = government.map
        self.function = None
        self.faction = None
        self.personality = None
        self.system_message = None

    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = (
            f"你为清代政府{self.function}官员，{self.faction}，你{self.personality}，朝廷正议政务。政府的目标是维持地方统治稳定，同时完成中央政府下达的航运任务。\n"
        )

    def get_current_situation_prompt(self, maintain_employment_cost):
        river_price = self.government.transport_economy.river_price
        sea_price = self.government.transport_economy.sea_price
        transport_task = self.government.transport_economy.transport_task
        return (
            f"当前国库有银{self.government.get_budget():.2f}两，兵力{self.government.get_military_strength():.2f}，税率: {self.government.get_tax_rate()*100:.1f}%"
            f"运输任务: {transport_task}吨,河运费(不可修改){river_price:.2f}两/吨，海运费(不可修改){sea_price:.2f}两/吨（海运低廉但岗位少，河运高费却可养人）\n"
            f"维持目前就业需资金{maintain_employment_cost:.2f}两。若公共预算高于此值，可增加就业；反之，将减少就业。"
            f"军事拨款需为20的整数倍（可以为0），每20两增加一单位兵力。总支出不应超出{self.government.get_budget():.2f}两"
        )

    async def generate_opinion(self, salary):
        """
        生成一句关于政治决策的意见
        :return: 生成的意见内容
        """
        maintain_employment_cost = salary * 0.5

        # 构建提示信息
        prompt = (
            f"请结合当前形势，立足本职，发言一句尽可能简短的中肯建议，必要时附具体数值佐证，只含公共预算、河运比例（0-1）、维护支出、军事拨款或税率调整。"
            + self.get_current_situation_prompt(maintain_employment_cost)
        )
        
        self.update_system_message()
        opinion = await self.generate_llm_response(prompt)
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

    async def generate_and_share_opinion(self, salary):
        """
        从共享信息池中获取信息并发表看法，将看法放入共享信息池
        """
        maintain_employment_cost = salary * 0.5
        # 获取最新讨论内容
        all_discussion = await self.shared_pool.get_all_discussions()
        if all_discussion:
            prompt = (
                f"众臣各抒己见，所言如下：\n"
                f"{all_discussion}"
                f"请结合自身立场与现实条件，发言一句尽可能简短的回应，可支持、反对或另提方案，务必考虑财政可行性。"
                + self.get_current_situation_prompt(maintain_employment_cost)
            )

            try:
                self.update_system_message()
                opinion = await self.generate_llm_response(prompt)
                if opinion:
                    await self.shared_pool.add_discussion(opinion)
                    government_log.info(f"普通官员 {self.agent_id} 回应了讨论：{opinion}")
            except Exception as e:
                government_log.error(f"普通官员 {self.agent_id} 在生成回应时出错：{e}")
        else:
            print("没有讨论内容")

class HighRankingGovernmentAgent(BaseAgent):
    def __init__(self, agent_id, government, shared_pool):
        """
        初始化高级政府官员类（决策者）
        :param agent_id: 政府官员的唯一标识符
        :param government: 政府对象，用于获取政府状态
        """
        super().__init__(agent_id, group_type='government', window_size=3)
        self.government = government
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        self.map = government.map
        self.system_message = None
        self.personality = None  # 人物性格
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = (
            f"你为清代政府最高决策者，你{self.personality}，朝廷正议政务，你负责根据下属讨论和当前状态做出最终决策。你的目标是维持地方统治稳定，同时完成中央政府下达的航运任务。\n"
        )

    async def make_decision(self, summary, salary):
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
        maintenance_cost_base = self.government.transport_economy.maintenance_cost_base
        transport_task = self.government.transport_economy.transport_task
        current_budget = self.government.get_budget()
        
        # 计算各项支出的成本基准
        transport_cost_river = river_price * transport_task  # 全部河运成本
        transport_cost_sea = sea_price * transport_task      # 全部海运成本
        
        # 获取维持当前就业所需的资金
        maintain_employment_cost = salary * 0.5

        decision_prompt = (
            f"当前政府预算: {current_budget:.2f}两,军事力量: {self.government.get_military_strength():.2f},税率: {self.government.get_tax_rate()*100:.1f}%\n"
            f"运输任务共{transport_task}吨,河运需{river_price:.2f}两/吨,海运需{sea_price:.2f}两/吨，维护运河基本运转需{maintenance_cost_base}两\n"
            f"维持目前就业需资金: {maintain_employment_cost:.2f}两。若公共预算高于此值，可增加就业；反之，将减少就业。"
            
            f"成本计算：\n"
            f"运输成本 = 河运比例×{transport_cost_river:.2f} + 海运比例×{transport_cost_sea:.2f}\n"
            f"总支出 = 运输成本 + 公共预算 + 维护资金 + 军事拨款\n"
            f"总支出必须 ≤ {current_budget:.2f}两。军事拨款需为20的整数倍，每20两增加一点军事力量。"
            
            f"下属讨论：\n{summary}\n\n"
            
            f"请做出合理决策，确保总支出不超预算。输出JSON，无需说明理由：\n"
            f'{{"public_budget": 公共预算（整数）, "transport_ratio": 河运比例（0-1）, "maintenance_investment": 维护资金（整数）, "military_support": 军事拨款（整数）, "tax_adjustment": 税率调整（-0.1到0.1）}}\n'
        )
        try:
            self.update_system_message()
            decision = await self.generate_llm_response(decision_prompt)

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
        government_log.info(f"  人物性格：{self.personality}")

class Government:
    def __init__(self, map, towns, military_strength, initial_budget, time, transport_economy):
        """
        初始化政府类
        """
        self.map = map
        self.towns = towns
        self.budget = initial_budget
        self.military_strength = military_strength
        self.time = time
        self.tax_rate = 0.1  # 初始税率为 10%
        self.residents = {}  # 添加居民引用
        self.transport_economy = transport_economy  # 运输经济模型引用

    def handle_public_budget(self,budget_allocation, salary):
        """处理公共预算决策"""
        if self.budget < budget_allocation:
            print("政府预算不足以提供工作。")
            return
        # 获取维持当前就业所需的资金
        maintain_employment_cost = salary * 0.5
        if budget_allocation > maintain_employment_cost:
            # 增加就业
            job_increase_amount = int((budget_allocation - maintain_employment_cost) / 10) # 假设每10两增加1个岗位
            if job_increase_amount > 0:
                self.towns.add_jobs_across_towns(job_increase_amount)
                government_log.info(f"政府执行决策 - 增加 {job_increase_amount} 个工作岗位。")
        elif budget_allocation < maintain_employment_cost:
            # 减少就业
            job_decrease_amount = int((maintain_employment_cost - budget_allocation) / 10) # 假设每10两减少1个岗位
            if job_decrease_amount > 0:
                self.towns.remove_jobs_across_towns(job_decrease_amount)
                government_log.info(f"政府执行决策 - 减少 {job_decrease_amount} 个工作岗位。")
        else:
            government_log.info(f"政府执行决策 - 维持现有就业岗位数量不变。")
        
        self.budget -= budget_allocation

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
        job_opportunities = int(maintenance_investment / 15)
        if job_opportunities > 0:
            self.towns.add_specific_job(job_opportunities,"canal","运河维护工", )
        
        # 扣除支出
        self.budget -= maintenance_investment
        government_log.info(f"政府执行决策 - 投入{maintenance_investment:.2f}两维护运河，新增就业岗位：{job_opportunities}个")
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
        government_log.info(f"政府执行决策 - 河运比例：{transport_ratio:.2f}，实际支出：{total_cost:.2f}两")
        return True

    def support_military(self, budget_allocation):
        """
        军需拨款
        :param budget_allocation: 分配给军事力量的预算
        """
        if self.budget >= budget_allocation and budget_allocation >= 20:
            job_increase_amount = budget_allocation // 20
            self.towns.add_jobs_across_towns(job_increase_amount,"官员及士兵")
            self.military_strength += job_increase_amount
            self.budget -= budget_allocation
            government_log.info(f"政府执行决策 - 政府军事拨款{budget_allocation}两，军事力量增加了 {budget_allocation * 0.1}。")
        else:
            government_log.info(f"政府执行决策 - 政府因预算限制未支持军事力量。")

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
        government_log.info(f"政府执行决策 - 税率从 {old_rate*100:.1f}% 调整为 {self.tax_rate*100:.1f}%")
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

class InformationOfficer(BaseAgent):
    def __init__(self, agent_id, government, shared_pool):
        super().__init__(agent_id, group_type='government', window_size=0)
        self.shared_pool = shared_pool
        self.memory = None


    async def summarize_discussions(self) -> str:
        """
        整理和总结所有讨论内容
        :return: 总结后的报告
        """
        discussions = await self.shared_pool.get_all_discussions()
        if not discussions:
            return "暂无讨论内容"
        
        prompt = (
            f"你为朝廷信息整理官员，请根据下列{len(discussions)}条朝堂讨论，用一句话尽可能简要地总结归纳核心观点，保留具体数值。"
            f"讨论内容：\n" + "\n".join([f"{i+1}. {d}" for i, d in enumerate(discussions)])
        )

        try:
            summary = await self.generate_llm_response(prompt)
            if summary:
                government_log.info(f"信息整理官 {self.agent_id} 生成总结报告：{summary}")
                return summary
            return "无法生成总结报告"
        except Exception as e:
            government_log.error(f"信息整理官 {self.agent_id} 在生成总结报告时出错：{e}")
            return "无法生成总结报告"
