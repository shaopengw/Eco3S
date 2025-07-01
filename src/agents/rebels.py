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

class OrdinaryRebel(BaseAgent):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(agent_id, group_type='rebellion', window_size=3)
        self.rebellion = rebellion
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）
        self.role = None  # 角色
        self.mbti = None  # 人物性格

        self.system_message = "你是清代政府划定的非法武装组织（叛军）主要头目之一，请你根据个人属性和所在叛军的状态提出意见。你的目的是使叛军组织生存和壮大（即：拥有更多的钱和人员）。"

    async def generate_opinion(self):
        """
        生成一句关于叛军行动的意见
        :return: 生成的意见内容
        """

        # 构建提示信息
        prompt = (
            f"你是清代叛军的主要头目之一（{self.mbti}），负责{self.role}工作。\n"
            f"当前叛军兵力{self.rebellion.get_strength()}，资源总计{self.rebellion.get_resources()}两\n"
            f"请根据你的个人属性、当前叛军状态和讨论内容，提出下一步行动的建议。请你用一句话概括，不必说明理由。"
        )

        opinion = await self.generate_llm_response(prompt, self.system_message)
        if opinion:
            rebellion_log.info(f"普通叛军 {self.agent_id} 生成的意见：{opinion}")
            return opinion
        return "无法生成意见"

    async def generate_and_share_opinion(self):
        """
        从共享信息池中获取信息并发表看法，将看法放入共享信息池
        """
        # 获取所有讨论内容
        all_discussion = await self.shared_pool.get_all_discussions()
        if all_discussion:
            prompt = (
                f"你是清代叛军的主要头目之一（{self.mbti}），负责{self.role}工作。\n"
                f"\n所有成员的观点包括：{all_discussion}\n"
                f"\n请根据你的个人属性和立场，对这些观点发表看法。"
                f"可以选择支持、反对或提出新的观点。"
                f"请用简短的一句话回复。"
            )

            try:
                opinion = await self.generate_llm_response(prompt, self.system_message)
                if opinion:
                    await self.shared_pool.add_discussion(opinion)
                    rebellion_log.info(f"普通叛军 {self.agent_id} 回应了讨论：{opinion}")
            except Exception as e:
                rebellion_log.error(f"普通叛军 {self.agent_id} 在生成回应时出错：{e}")
        else:
            # 如果没有讨论内容，生成新话题
            opinion = await self.generate_opinion()
            await self.shared_pool.add_discussion(opinion)
            rebellion_log.info(f"普通叛军 {self.agent_id} 发起了新讨论：{opinion}")

class RebelLeader(BaseAgent):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(agent_id, group_type='rebellion', window_size=3)
        self.rebellion = rebellion
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）

        # 初始化叛军头子属性
        self.role = None  # 角色
        self.mbti = None  # 人物性格
        
        # 系统消息
        self.system_message = "你是一个清代地方叛军组织首领，你的目标是确保叛军组织的生存和壮大（拥有更多的成员和金钱）。"

    async def make_decision(self, summary, towns_stats):
        """
        根据普通叛军的讨论作出决策
        :param summary: 普通叛军的讨论报告
        :return: 决策结果
        """
        # 等待讨论结束
        if not self.shared_pool.is_ended():
            return None

        # 分析各城镇的力量对比
        towns_analysis = []
        for town in towns_stats:
            rebel_count = town['rebel_count']
            official_count = town['official_count']
            towns_analysis.append(f"{town['town_name']}: {rebel_count}：{official_count}")

        # 使用 CAMEL 框架来做决策
        # 历史决策信息，让叛军可以自己从中总结不同决策带来的后果。
        decision_prompt = (
            f"你是清代地方叛军组织的首领，负责根据下属的讨论和当前叛军状态做出最终决策。\n"
            f"当前叛军兵力{self.rebellion.get_strength()}，资源总计{self.rebellion.get_resources()}两\n"
            f"各城镇力量分布（叛军：官兵）：\n" + "\n".join(towns_analysis) + "\n"
            f"下属建议：\n{summary}\n"
            f"在做决策时，请考虑各城镇叛军和官兵的力量对比，优先选择叛军多或官兵少的城镇出击。\n"
            f"输出JSON，无需说明理由：\n"
            f'{{"stage_rebellion": 发动叛乱的力量投入（整数）, "recruit_members": 招募新成员的资源投入（整数）, "maintain_status": 维持现状（设为1表示选择维持现状，设为0表示不选择）, "target_town": 发动叛乱目标城镇名称（字符串）}}'

        )

        try:
            # 调用模型做出最终决策
            decision = await self.generate_llm_response(decision_prompt, self.system_message)

            if decision:
                rebellion_log.info(f"叛军头子 {self.agent_id} 的决策：{decision}")
                # 清空共享信息池
                await self.shared_pool.clear_discussions()
                return decision
        except Exception as e:
            rebellion_log.error(f"叛军头子 {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def print_leader_status(self):
        """
        打印叛军头子的状态
        """
        rebellion_log.info(f"叛军头子 {self.agent_id} 的状态：")
        rebellion_log.info(f"  当前时间：{self.time}年")
        rebellion_log.info(f"  角色：{self.role}")
        rebellion_log.info(f"  人物性格：{self.mbti}")

class InformationOfficer(BaseAgent):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(agent_id, group_type='rebellion', window_size=0)
        self.shared_pool = shared_pool
        self.role = "信息整理官"

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
            f"作为叛军信息整理官，请根据下列{len(discussions)}条讨论内容，用一句话尽可能简要地总结归纳核心观点，保留具体数值。"
            f"讨论内容：\n" + "\n".join([f"{i+1}. {d}" for i, d in enumerate(discussions)])
        )

        try:
            summary = await self.generate_llm_response(prompt)
            if summary:
                rebellion_log.info(f"叛军信息整理官 {self.agent_id} 生成的总结报告：{summary}")
                return summary
            return "无法生成总结报告"
        except Exception as e:
            rebellion_log.error(f"叛军信息整理官 {self.agent_id} 在生成总结报告时出错：{e}")
            return "无法生成总结报告"
# TODO： 所有决策的后果需要存储到记忆中，叛军可以从中学习。
class Rebellion:
    def __init__(self, initial_strength, initial_resources, job_market):
        """
        初始化叛军类
        :param initial_strength: 初始力量
        :param initial_resources: 初始资源
        """
        self.strength = initial_strength
        self.resources = initial_resources
        self.job_market = job_market

    def recruit_new_members(self, resource_investment):
        """
        招募新成员
        :param resource_investment: 投入的资源
        """
        if self.resources >= resource_investment:
            # 计算可以招募的新成员数量（假设每100两可以提供1个职位）
            job_opportunities = int(resource_investment / 100)

            # 在就业市场增加叛军职位
            if job_opportunities > 0:
                self.job_market.add_job("叛军", job_opportunities)
            self.resources -= resource_investment

            print(f"叛军成功花费{resource_investment}，发布了 {job_opportunities} 个叛军职位。")
        else:
            print("叛军资源不足以招募新成员。")

    def maintain_status(self):
        """
        维持现状，获取基本收入
        """
        income_rate=0.01
        income = int(self.strength * income_rate)  # 计算收入
        self.resources += income  # 增加资源
        print(f"叛军维持现状，获得基本收入 {income} 。")

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

    def print_rebellion_status(self):
        """
        打印叛军状态（用于调试）
        """
        print(f"叛军力量: {self.strength}")
        print(f"叛军资源: {self.resources}")

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
        return True
