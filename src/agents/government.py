from .shared_imports import *
from ..utils.logger import LogManager
from .agent_group import AgentGroup
from src.interfaces import (
    IOrdinaryGovernmentAgent,
    IHighRankingGovernmentAgent,
    IGovernment,
    IGovernmentSharedInformationPool,
    IGovernmentInformationOfficer
)
load_dotenv()

_MAINTAIN_EMPLOYMENT_RATE = 0.05


def _calc_maintain_employment_cost(salary: float) -> float:
    return salary * _MAINTAIN_EMPLOYMENT_RATE

class OrdinaryGovernmentAgent(AgentGroup.DiscussionMemberAgentBase, IOrdinaryGovernmentAgent):
    def __init__(self, agent_id, government, shared_pool):
        super().__init__(agent_id, group_type='government', shared_pool=shared_pool, window_size=3)
        self.government = government
        self.time = 0  # 当前时间（年）
        self.map = government.map
        self.function = None
        self.faction = None
        self.personality = None
        self.system_message = None
        self.government_log = self.government.government_log

    def get_memory_role_name(self) -> str:
        return "普通政府官员"

    def get_logger(self):
        return self.government_log

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
            maintenance_cost = self.government.transport_economy.calculate_maintenance_cost(self.government.map.get_navigability())
            return self.government.prompts['get_current_situation_prompt'].format(
                budget=self.government.get_budget(), military_strength=self.government.get_military_strength(), tax_rate=self.government.get_tax_rate()*100,
                transport_task=transport_task, river_price=river_price, sea_price=sea_price, maintenance_cost_base=maintenance_cost,
                maintain_employment_cost=maintain_employment_cost)
        else:
            # 没有运输经济模块时，使用简化版本
            return self.government.prompts.get('get_current_situation_prompt_simple', 
                "当前政府预算：{budget}，军事力量：{military_strength}，税率：{tax_rate}%，维持就业成本：{maintain_employment_cost}").format(
                budget=self.government.get_budget(), 
                military_strength=self.government.get_military_strength(), 
                tax_rate=self.government.get_tax_rate()*100,
                maintain_employment_cost=maintain_employment_cost)

    def build_generate_opinion_prompt(self, salary):
        maintain_employment_cost = _calc_maintain_employment_cost(salary)
        return self.government.prompts['generate_opinion_prompt'].format(
            current_situation_prompt=self.get_current_situation_prompt(maintain_employment_cost)
        )

    def build_generate_and_share_opinion_prompt(self, all_discussions, salary):
        maintain_employment_cost = _calc_maintain_employment_cost(salary)
        return self.government.prompts['generate_and_share_opinion_prompt'].format(
            all_discussion=all_discussions,
            current_situation_prompt=self.get_current_situation_prompt(maintain_employment_cost),
        )

    async def make_decision(self, summary, salary):
        """
        根据讨论总结作出决策（用于非独裁模式）
        :param summary: 讨论总结或高级官员的总结发言
        :param salary: 薪资信息
        :return: 决策结果
        """
        current_budget = self.government.get_budget()
        maintain_employment_cost = _calc_maintain_employment_cost(salary)

        # 检查是否有运输经济模块
        if self.government.transport_economy:
            # 获取运输经济相关参数
            river_price = self.government.transport_economy.river_price
            sea_price = self.government.transport_economy.sea_price
            transport_task = self.government.transport_economy.transport_task
            maintenance_cost = self.government.transport_economy.calculate_maintenance_cost(self.government.map.get_navigability())
            
            # 计算各项支出的成本基准
            transport_cost_river = river_price * transport_task  # 全部河运成本
            transport_cost_sea = sea_price * transport_task      # 全部海运成本

            prompt = self.government.prompts['make_decision_prompt'].format(
                current_budget=current_budget, military_strength=self.government.get_military_strength(),
                tax_rate=self.government.get_tax_rate()*100, transport_task=transport_task, river_price=river_price,
                sea_price=sea_price, maintenance_cost_base=maintenance_cost, maintain_employment_cost=maintain_employment_cost,
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
                self.government_log.info(f"普通政府官员 {self.agent_id} 的决策：{decision}")
                return decision
        except Exception as e:
            self.government_log.error(f"普通政府官员 {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

class HighRankingGovernmentAgent(AgentGroup.DiscussionLeaderAgentBase, IHighRankingGovernmentAgent):
    def __init__(self, agent_id, government, shared_pool):
        """
        初始化高级政府官员类（决策者）
        :param agent_id: 政府官员的唯一标识符
        :param government: 政府对象，用于获取政府状态
        """
        super().__init__(agent_id, group_type='government', shared_pool=shared_pool, window_size=3)
        self.government = government
        self.time = 0  # 当前时间（年）
        self.map = government.map
        self.system_message = None
        self.personality = None  # 人物性格
        self.government_log = self.government.government_log

    def get_logger(self):
        return self.government_log
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = self.government.prompts['high_ranking_government_agent_system_message'].format(personality=self.personality)

    async def summarize_discussion_for_voting(self, summary, salary):
        """
        高级官员总结讨论，为后续投票提供参考（用于非独裁模式）
        :param summary: 信息整理官的总结
        :param salary: 薪资信息
        :return: 高级官员的总结发言
        """
        current_budget = self.government.get_budget()
        maintain_employment_cost = _calc_maintain_employment_cost(salary)
        
        # 检查是否有运输经济模块
        if self.government.transport_economy:
            river_price = self.government.transport_economy.river_price
            sea_price = self.government.transport_economy.sea_price
            transport_task = self.government.transport_economy.transport_task
            maintenance_cost = self.government.transport_economy.calculate_maintenance_cost(self.government.map.get_navigability())
            
            prompt = self.government.prompts['summarize_discussion_for_voting_prompt'].format(
                summary=summary,
                current_budget=current_budget,
                military_strength=self.government.get_military_strength(),
                tax_rate=self.government.get_tax_rate()*100,
                transport_task=transport_task,
                river_price=river_price,
                sea_price=sea_price,
                maintenance_cost_base=maintenance_cost,
                maintain_employment_cost=maintain_employment_cost
            )
        else:
            prompt = f"众官已充分讨论，信息官归纳如下：\n{summary}\n\n请用2-3句话总结要点，为后续投票提供参考。"
        
        try:
            self.update_system_message()
            leader_summary = await self.generate_llm_response(prompt)
            if leader_summary:
                self.government_log.info(f"高级政府官员 {self.agent_id} 的总结发言：{leader_summary}")
                return leader_summary
        except Exception as e:
            self.government_log.error(f"高级政府官员 {self.agent_id} 在总结讨论时出错：{e}")
            return summary  # 如果出错，返回原始总结

    def build_make_decision_prompt(self, summary, salary):
        current_budget = self.government.get_budget()
        maintain_employment_cost = _calc_maintain_employment_cost(salary)

        if self.government.transport_economy:
            river_price = self.government.transport_economy.river_price
            sea_price = self.government.transport_economy.sea_price
            transport_task = self.government.transport_economy.transport_task
            maintenance_cost = self.government.transport_economy.calculate_maintenance_cost(
                self.government.map.get_navigability()
            )

            transport_cost_river = river_price * transport_task
            transport_cost_sea = sea_price * transport_task

            return self.government.prompts['make_decision_prompt'].format(
                current_budget=current_budget,
                military_strength=self.government.get_military_strength(),
                tax_rate=self.government.get_tax_rate() * 100,
                transport_task=transport_task,
                river_price=river_price,
                sea_price=sea_price,
                maintenance_cost_base=maintenance_cost,
                maintain_employment_cost=maintain_employment_cost,
                transport_cost_river=transport_cost_river,
                transport_cost_sea=transport_cost_sea,
                summary=summary,
            )

        return self.government.prompts.get(
            'make_decision_prompt_simple',
            "当前预算：{current_budget}，军事力量：{military_strength}，税率：{tax_rate}%，维持就业成本：{maintain_employment_cost}。\n讨论总结：{summary}\n请做出决策。",
        ).format(
            current_budget=current_budget,
            military_strength=self.government.get_military_strength(),
            tax_rate=self.government.get_tax_rate() * 100,
            maintain_employment_cost=maintain_employment_cost,
            summary=summary,
        )

    def print_agent_status(self):
        """
        打印高级政府官员的状态
        """
        self.government_log.info(f"高级政府官员 {self.agent_id} 的状态：")
        self.government_log.info(f"  当前时间：{self.time}年")
        self.government_log.info(f"  人物性格：{self.personality}")

class Government(AgentGroup, IGovernment):
    def __init__(self, map, towns, military_strength, initial_budget, time, transport_economy, government_prompt_path, influence_registry=None):
        """
        初始化政府类
        :param influence_registry: 影响函数注册表（可选）
        """
        AgentGroup.__init__(self, prompts_path=government_prompt_path, logger_name="government", group_type="government")
        self._map = map
        self._towns = towns
        self._budget = initial_budget
        self._military_strength = military_strength
        self.time = time
        self._tax_rate = 0.1  # 初始税率为 10%
        self.residents = {}  # 添加居民引用
        self._transport_economy = transport_economy  # 运输经济模型引用
        self._influence_registry = influence_registry
        self.government_log = self.group_log
    
    # 实现 IGovernment 接口的 property
    @property
    def map(self):
        """地图对象"""
        return self._map
    
    @property
    def towns(self):
        """城镇对象"""
        return self._towns
    
    @property
    def budget(self) -> float:
        """当前预算"""
        return self._budget
    
    @budget.setter
    def budget(self, value: float):
        """设置预算"""
        self._budget = value
    
    @property
    def military_strength(self) -> int:
        """军事力量"""
        return self._military_strength
    
    @military_strength.setter
    def military_strength(self, value: int):
        """设置军事力量"""
        self._military_strength = value
    
    @property
    def tax_rate(self) -> float:
        """税率"""
        return self._tax_rate
    
    @tax_rate.setter
    def tax_rate(self, value: float):
        """设置税率"""
        self._tax_rate = value
    
    @property
    def transport_economy(self):
        """运输经济模型引用"""
        return self._transport_economy

    def handle_public_budget(self, budget_allocation, salary, job_total_count,residents):
        """处理公共预算决策"""
        # 获取维持当前就业所需的资金
        maintain_employment_cost = _calc_maintain_employment_cost(salary)
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
        
        # 构建上下文
        result = {'new_tax_rate': self.tax_rate + adjustment}
        context = {
            'government': self,
            'old_tax_rate': old_rate,
            'adjustment': adjustment,
            'result': result
        }
        
        # 尝试使用影响函数系统
        if self._influence_registry is not None:
            influences = self._influence_registry.get_influences('tax_rate')
            if influences:
                # 使用影响函数计算新税率
                self.apply_influences('tax_rate', context)
                self.tax_rate = result['new_tax_rate']
                self.government_log.info(f"政府执行决策 - 税率从 {old_rate*100:.1f}% 调整为 {self.tax_rate*100:.1f}%")
                return self.tax_rate
        
        # 回退到默认逻辑（向后兼容）
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

    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        应用所有注册的影响函数到指定目标
        
        :param target_name: 目标名称（如 'tax_rate'）
        :param context: 上下文字典，包含影响函数所需的所有数据
        """
        if self._influence_registry is None:
            return
        
        # 如果没有提供上下文，创建默认上下文
        if context is None:
            context = {}
        
        # 确保上下文中包含 government 对象本身
        context['government'] = self
        
        # 获取所有影响该目标的影响函数
        influences = self._influence_registry.get_influences(target_name)
        
        # 应用每个影响函数
        for influence in influences:
            try:
                impact = influence.apply(self, context)
                if impact is not None:
                    # 可以记录影响或采取其他行动
                    pass
            except Exception as e:
                self.government_log.error(f"应用影响函数失败 ({influence.source}->{target_name}:{influence.name}): {e}")

class government_SharedInformationPool(AgentGroup.SharedInformationPoolBase, IGovernmentSharedInformationPool):
    def __init__(self, max_discussions: int = 5):
        super().__init__(max_discussions=max_discussions)


class InformationOfficer(AgentGroup.DiscussionInformationOfficerBase, IGovernmentInformationOfficer):
    def __init__(self, agent_id, government, shared_pool):
        super().__init__(
            agent_id=agent_id,
            group_type='government',
            shared_pool=shared_pool,
            prompts=government.prompts,
            logger=government.government_log,
            window_size=0,
        )
        self.memory = None

