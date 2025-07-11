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
        self.personality = None  # 人物性格
        self.system_message = None  # 系统提示词
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = (
            f"你是清代叛军的{self.role}头目，你{self.personality}，正参与密谋下一步行动。\n"
        )
    
    async def generate_opinion(self, towns_stats):
        """
        生成一句关于叛军行动的意见
        :return: 生成的意见内容
        """
        towns_analysis = self.analysis_towns_stats(towns_stats)
        # 构建提示信息
        prompt = (
            f"当前叛军总兵力{self.rebellion.get_strength()}，总预算{self.rebellion.get_resources()}两\n"
            f"各城镇力量分布（叛军：官兵）：\n" + "\n".join(towns_analysis) + "\n"
            f"请结合当前形势，立足本职，发言一句尽可能简短的下一步行动建议。附具体数值佐证，只含全国宣传预算（整数），发动叛乱目标城镇名称，目标城镇兵力投入（不超过目标城镇叛军数）。不要解释，不得违反兵力限制。"
        )
        self.update_system_message()
        opinion = await self.generate_llm_response(prompt)
        if opinion:
            await self.memory.write_record(
                role_name="普通叛军头目之一",
                content=f"我的意见：{opinion}",
                is_user=False,
                store_in_shared=False  # 不存入共享记忆
                )
            await self.shared_pool.add_discussion(opinion)
            rebellion_log.info(f"普通叛军 {self.agent_id} 生成的意见：{opinion}")
            return opinion
        return "无法生成意见"

    async def generate_and_share_opinion(self, salary):
        """
        从共享信息池中获取信息并发表看法，将看法放入共享信息池
        """
        # 获取所有讨论内容
        all_discussion = await self.shared_pool.get_all_discussions()
        if all_discussion:
            prompt = (
                f"\n众人各抒己见，所言如下：{all_discussion}\n"
                f"请立足本职与立场，发言一句尽可能简短的回应，可表支持、反对，或另陈己见。"
            )

            try:
                self.update_system_message()
                opinion = await self.generate_llm_response(prompt)
                if opinion:
                    await self.shared_pool.add_discussion(opinion)
                    rebellion_log.info(f"普通叛军 {self.agent_id} 回应了讨论：{opinion}")
            except Exception as e:
                rebellion_log.error(f"普通叛军 {self.agent_id} 在生成回应时出错：{e}")
        else:
            # 如果没有讨论内容，生成新话题
            opinion = await self.generate_opinion(salary)
            await self.shared_pool.add_discussion(opinion)
            rebellion_log.info(f"普通叛军 {self.agent_id} 发起了新讨论：{opinion}")

    def analysis_towns_stats(self, towns_stats):
        """分析各城镇的力量对比"""
        towns_analysis = []
        for town in towns_stats:
            rebel_count = town['rebel_count']
            official_count = town['official_count']
            if rebel_count > 0:  # 只有当叛军数量大于0时才添加到提示词中
                towns_analysis.append(f"{town['town_name']}: {rebel_count}：{official_count}")
        return towns_analysis

class RebelLeader(BaseAgent):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(agent_id, group_type='rebellion', window_size=3)
        self.rebellion = rebellion
        self.shared_pool = shared_pool
        self.time = 0  # 当前时间（年）

        # 初始化叛军头子属性
        self.role = None  # 角色
        self.personality = None  # 人物性格
        # 系统消息
        self.system_message = None
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = (
            f"你是清代叛军组织的首领，你{self.personality}，你的目标是确保叛军组织的生存和壮大（拥有更多的成员和金钱）。叛军正密谋下一步行动。\n"
        )

    async def make_decision(self, summary, towns_stats):
        """
        根据普通叛军的讨论作出决策
        :param summary: 普通叛军的讨论报告
        :return: 决策结果
        """
        # 等待讨论结束
        if not self.shared_pool.is_ended():
            return None
        towns_analysis = self.analysis_towns_stats(towns_stats)

        # 使用 CAMEL 框架来做决策
        # 历史决策信息，让叛军可以自己从中总结不同决策带来的后果。
        decision_prompt = (
            f"你是清代地方叛军组织的首领，负责根据下属的讨论和当前叛军状态做出最终决策。\n"
            f"当前叛军总兵力{self.rebellion.get_strength()}，资源总计{self.rebellion.get_resources()}两\n"
            f"各城镇力量分布（叛军：官兵）：\n" + "\n".join(towns_analysis) + "\n"
            f"下属建议：\n{summary}\n"
            f"在做决策时，请考虑各城镇叛军和官兵的力量对比，优先选择叛军多或官兵少的城镇出击。宣传可以煽动民众不满情绪，从而加入叛军。\n"
            f"输出JSON，无需说明理由：\n"
            # f'{{"stage_rebellion": 发动叛乱的力量投入（整数）, "recruit_members": 招募新成员的资源投入（整数,每12两可招募1人）, "maintain_status": 维持现状（设为1表示选择维持现状，设为0表示不选择）, "target_town": 发动叛乱目标城镇名称（字符串）}}'
            f'{{ "propaganda_budget": 宣传预算（整数）, "target_town": 发动叛乱目标城镇名称（字符串）,"stage_rebellion": 发动叛乱的兵力投入（整数，不超过目标城镇叛军数）}}'

        )

        try:
            # 调用模型做出最终决策
            self.update_system_message()
            decision = await self.generate_llm_response(decision_prompt)

            if decision:
                rebellion_log.info(f"叛军头子 {self.agent_id} 的决策：{decision}")
                # 清空共享信息池
                await self.shared_pool.clear_discussions()
                return decision
        except Exception as e:
            rebellion_log.error(f"叛军头子 {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def analysis_towns_stats(self, towns_stats):
        """分析各城镇的力量对比"""
        towns_analysis = []
        for town in towns_stats:
            rebel_count = town['rebel_count']
            official_count = town['official_count']
            if rebel_count > 0:  # 只有当叛军数量大于0时才添加到提示词中
                towns_analysis.append(f"{town['town_name']}: {rebel_count}：{official_count}")
        return towns_analysis
    
    def print_leader_status(self):
        """
        打印叛军头子的状态
        """
        rebellion_log.info(f"叛军头子 {self.agent_id} 的状态：")
        rebellion_log.info(f"  当前时间：{self.time}年")
        rebellion_log.info(f"  角色：{self.role}")
        rebellion_log.info(f"  人物性格：{self.personality}")

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
    def __init__(self, initial_strength, initial_resources, towns):
        """
        初始化叛军类
        :param initial_strength: 初始力量
        :param initial_resources: 初始资源
        """
        self.strength = initial_strength
        self.resources = initial_resources
        self.towns = towns

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
