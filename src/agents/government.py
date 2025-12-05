from .shared_imports import *
from ..utils.logger import LogManager
load_dotenv()

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
        self.government_log = self.government.government_log

    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = self.government.prompts['ordinary_government_agent_system_message'].format(
            function=self.function, faction=self.faction, personality=self.personality)

    def get_current_situation_prompt(self, maintain_employment_cost):
        # 检查是否有运输经济模块
        if self.government.transport_economy:
            river_price = self.government.transport_economy.river_price
            sea_price = self.government.transport_economy.sea_price
            transport_task = self.government.transport_economy.transport_task
            maintenance_cost_base = self.government.transport_economy.maintenance_cost_base
            return self.government.prompts['get_current_situation_prompt'].format(
                budget=self.government.get_budget(), military_strength=self.government.get_military_strength(), tax_rate=self.government.get_tax_rate()*100,
                transport_task=transport_task, river_price=river_price, sea_price=sea_price, maintenance_cost_base=maintenance_cost_base,
                maintain_employment_cost=maintain_employment_cost)
        else:
            # 没有运输经济模块时，使用简化版本
            return self.government.prompts.get('get_current_situation_prompt_simple', 
                "当前政府预算：{budget}，军事力量：{military_strength}，税率：{tax_rate}%，维持就业成本：{maintain_employment_cost}").format(
                budget=self.government.get_budget(), 
                military_strength=self.government.get_military_strength(), 
                tax_rate=self.government.get_tax_rate()*100,
                maintain_employment_cost=maintain_employment_cost)

    async def generate_opinion(self, salary):
        """
        生成一句关于政治决策的意见
        :return: 生成的意见内容
        """
        maintain_employment_cost = salary * 0.05
        # 构建提示信息
        prompt = self.government.prompts['generate_opinion_prompt'].format(
            current_situation_prompt=self.get_current_situation_prompt(maintain_employment_cost))
        
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
            self.government_log.info(f"普通政府官员 {self.agent_id} 生成的意见：{opinion}")
            return opinion
        return "无法生成意见"

    async def generate_and_share_opinion(self, salary):
        """
        从共享信息池中获取信息并发表看法，将看法放入共享信息池
        """
        maintain_employment_cost = salary * 0.05
        # 获取最新讨论内容
        all_discussion = await self.shared_pool.get_all_discussions()
        if all_discussion:
            prompt = self.government.prompts['generate_and_share_opinion_prompt'].format(
                all_discussion=all_discussion, current_situation_prompt=self.get_current_situation_prompt(maintain_employment_cost))

            try:
                self.update_system_message()
                opinion = await self.generate_llm_response(prompt)
                if opinion:
                    await self.shared_pool.add_discussion(opinion)
                    self.government_log.info(f"普通官员 {self.agent_id} 回应了讨论：{opinion}")
            except Exception as e:
                self.government_log.error(f"普通官员 {self.agent_id} 在生成回应时出错：{e}")
        else:
            # 如果共享信息池为空，调用generate_opinion函数
            await self.generate_opinion(salary)

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
        self.government_log = self.government.government_log
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = self.government.prompts['high_ranking_government_agent_system_message'].format(personality=self.personality)

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
        # 政府和叛军的决策，只计算比例， 然后系统根据现有资源自动计算绝对值。这样避免LLM输出结果超过预算。
        current_budget = self.government.get_budget()

        # 获取维持当前就业所需的资金
        maintain_employment_cost = salary * 0.05

        # 检查是否有运输经济模块
        if self.government.transport_economy:
            # 获取运输经济相关参数
            river_price = self.government.transport_economy.river_price
            sea_price = self.government.transport_economy.sea_price
            transport_task = self.government.transport_economy.transport_task
            maintenance_cost_base = self.government.transport_economy.maintenance_cost_base
            
            # 计算各项支出的成本基准
            transport_cost_river = river_price * transport_task  # 全部河运成本
            transport_cost_sea = sea_price * transport_task      # 全部海运成本

            prompt = self.government.prompts['make_decision_prompt'].format(
                current_budget=current_budget, military_strength=self.government.get_military_strength(),
                tax_rate=self.government.get_tax_rate()*100, transport_task=transport_task, river_price=river_price,
                sea_price=sea_price, maintenance_cost_base=maintenance_cost_base, maintain_employment_cost=maintain_employment_cost,
                transport_cost_river=transport_cost_river, transport_cost_sea=transport_cost_sea, summary=summary)
        else:
            # 没有运输经济模块时，使用简化版本
            prompt = self.government.prompts.get('make_decision_prompt_simple',
                "当前预算：{current_budget}，军事力量：{military_strength}，税率：{tax_rate}%，维持就业成本：{maintain_employment_cost}。\n讨论总结：{summary}\n请做出决策。").format(
                current_budget=current_budget, 
                military_strength=self.government.get_military_strength(),
                tax_rate=self.government.get_tax_rate()*100, 
                maintain_employment_cost=maintain_employment_cost, 
                summary=summary)
        try:
            self.update_system_message()
            decision = await self.generate_llm_response(prompt)

            if decision:
                self.government_log.info(f"高级政府官员 {self.agent_id} 的决策：{decision}")
                # 清空共享信息池
                await self.shared_pool.clear_discussions()
                return decision
        except Exception as e:
            self.government_log.error(f"高级政府官员 {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def print_agent_status(self):
        """
        打印高级政府官员的状态
        """
        self.government_log.info(f"高级政府官员 {self.agent_id} 的状态：")
        self.government_log.info(f"  当前时间：{self.time}年")
        self.government_log.info(f"  人物性格：{self.personality}")

class Government:
    def __init__(self, map, towns, military_strength, initial_budget, time, transport_economy, government_prompt_path):
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
        with open(government_prompt_path, 'r', encoding='utf-8') as file:
            self.prompts = yaml.safe_load(file)

        self.government_log = LogManager.get_logger("government")

    def handle_public_budget(self, budget_allocation, salary, job_total_count,residents):
        """处理公共预算决策"""
        # 获取维持当前就业所需的资金
        maintain_employment_cost = salary * 0.05
        if budget_allocation == 0:
            self.government_log.info(f"政府执行决策 - 公共预算决策：不分配公共预算。")
            return
        if self.budget < budget_allocation:
            budget_allocation = self.budget
            self.government_log.info(f"政府执行决策 - 公共预算决策：预算不足，自动调整预算为{budget_allocation:.2f}两。")
            
        if budget_allocation > maintain_employment_cost:
            # 增加就业，根据比例计算增加的岗位数量
            job_increase_proportion = (budget_allocation - maintain_employment_cost) / maintain_employment_cost
            job_increase_amount = int(job_total_count * job_increase_proportion)
            if job_increase_amount > 0:
                self.towns.add_jobs_across_towns(job_increase_amount)
                self.government_log.info(f"政府执行决策 - 公共预算决策：增加 {job_increase_amount} 个工作岗位。")
        elif budget_allocation < maintain_employment_cost:
            # 减少就业，根据比例计算减少的岗位数量
            job_decrease_proportion = (maintain_employment_cost - budget_allocation) / maintain_employment_cost
            job_decrease_amount = int(job_total_count * job_decrease_proportion)
            if job_decrease_amount > 0:
                self.towns.remove_jobs_across_towns(job_decrease_amount, residents = residents)
                self.government_log.info(f"政府执行决策 - 公共预算决策：减少 {job_decrease_amount} 个工作岗位。")
        else:
            self.government_log.info(f"政府执行决策 - 维持现有就业岗位数量不变。")
        
        self.budget = max(0, self.budget - budget_allocation)

    def maintain_canal(self, maintenance_investment):
        """
        维护运河
        :param maintenance_investment: 投资金额
        :return: 是否维护成功
        """
        # 维护运河有各方面的影响：
        # 1. 改善运河状态（运河通航能力，取值范围：[0,1]），从而降低运输成本。否则运输成本上升，政府需要支出更多的预算来完成运输。
        # 2. 提供就业机会，增加居民满意度。但是提供的就业机会仅限运河沿线地区。（隐性）
        # 3. 政府预算减少
        # 计算并更新改善后的通航能力
        if maintenance_investment == 0:
            self.government_log.info(f"政府执行决策 - 未维护运河。")
            return
        if self.budget < maintenance_investment:
            self.government_log.info(f"政府执行决策 - 预算不足，未维护运河。")
            return
        maintenance_ratio = maintenance_investment / self.transport_economy.maintenance_cost_base
        self.map.update_river_condition(maintenance_ratio) 
        
        # 扣除支出
        self.budget = max(0, self.budget - maintenance_investment)
        self.government_log.info(f"政府执行决策 - 投入{maintenance_investment:.2f}两维护运河")
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
            transport_ratio = max(0, min(transport_ratio, max_affordable_ratio))
            print(f"预算不足，自动调整河运比例为{transport_ratio:.2f}")
            
        # 扣除运输成本
        self.budget = max(0, self.budget - total_cost)
        self.government_log.info(f"政府执行决策 - 河运比例：{transport_ratio:.2f}，实际支出：{total_cost:.2f}两")
        return True

    def support_military(self, budget_allocation):
        """
        军需拨款
        :param budget_allocation: 分配给军事力量的预算
        """
        if self.budget >= budget_allocation and budget_allocation >= 20:
            job_increase_amount = int(budget_allocation // 20)
            self.towns.add_jobs_across_towns(job_increase_amount,"官员及士兵")
            self.military_strength += job_increase_amount
            self.budget = max(0, self.budget - budget_allocation)
            self.government_log.info(f"政府执行决策 - 政府军事拨款{budget_allocation:.2f}两，军事力量增加了 {job_increase_amount}。")
        else:
            self.government_log.info(f"政府执行决策 - 政府因预算限制未支持军事力量。")

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
        self.government_log.info(f"政府执行决策 - 税率从 {old_rate*100:.1f}% 调整为 {self.tax_rate*100:.1f}%")
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
        self.prompts = government.prompts
        self.government_log = government.government_log


    async def summarize_discussions(self) -> str:
        """
        整理和总结所有讨论内容
        :return: 总结后的报告
        """
        discussions = await self.shared_pool.get_all_discussions()
        if not discussions:
            return "暂无讨论内容"
        
        prompt = self.prompts['summarize_discussions_prompt'].format(
            num_discussions=len(discussions), discussions="\n".join([f"{i+1}. {d}" for i, d in enumerate(discussions)]))

        try:
            summary = await self.generate_llm_response(prompt)
            if summary:
                self.government_log.info(f"信息整理官 {self.agent_id} 生成总结报告：{summary}")
                return summary
            return "无法生成总结报告"
        except Exception as e:
            self.government_log.error(f"信息整理官 {self.agent_id} 在生成总结报告时出错：{e}")
            return "无法生成总结报告"
