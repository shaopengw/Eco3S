from .shared_imports import *
from ..utils.logger import LogManager
from .agent_group import AgentGroup
from typing import Any, Dict, Optional
from src.interfaces import (
    IOrdinaryRebel,
    IRebelLeader,
    IRebellion,
    IRebelsSharedInformationPool,
    IRebelInformationOfficer
)

try:
    from src.influences import InfluenceRegistry
except ImportError:
    InfluenceRegistry = None
load_dotenv()

class OrdinaryRebel(AgentGroup.DiscussionMemberAgentBase, IOrdinaryRebel):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(agent_id, group_type='rebellion', shared_pool=shared_pool, window_size=3)
        self.rebellion = rebellion
        self.time = 0  # 当前时间（年）
        self.role = None  # 角色
        self.personality = None  # 人物性格
        self.system_message = None  # 系统提示词
        self.rebellion_log = self.rebellion.rebellion_log

    def get_memory_role_name(self) -> str:
        return "普通叛军头目之一"

    def get_logger(self):
        return self.rebellion_log
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = self.rebellion.prompts['ordinary_rebel_system_message'].format(
            role=self.role, personality=self.personality)

    def build_generate_opinion_prompt(self, towns_stats):
        towns_analysis = self.analysis_towns_stats(towns_stats)
        strength = self.rebellion.get_strength()
        resources = self.rebellion.get_resources()

        return self.rebellion.prompts['generate_opinion_prompt'].format(
            strength=strength,
            resources=resources,
            towns_analysis="\n".join(towns_analysis),
        )

    def build_generate_and_share_opinion_prompt(self, all_discussions, group_param):
        return self.rebellion.prompts['generate_and_share_opinion_prompt'].format(
            all_discussion=all_discussions
        )

    def analysis_towns_stats(self, towns_stats):
        """分析各城镇的力量对比"""
        towns_analysis = []
        for town in towns_stats:
            rebel_count = town['rebel_count']
            official_count = town['official_count']
            if rebel_count > 0:  # 只有当叛军数量大于0时才添加到提示词中
                towns_analysis.append(f"{town['town_name']}: 叛军{rebel_count}人，官兵{official_count}人。")
        return towns_analysis

class RebelLeader(AgentGroup.DiscussionLeaderAgentBase, IRebelLeader):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(
            agent_id,
            group_type='rebellion',
            shared_pool=shared_pool,
            window_size=3,
            logger=rebellion.rebellion_log,
        )
        self.rebellion = rebellion
        self.time = 0  # 当前时间（年）

        # 初始化叛军头子属性
        self.role = None  # 角色
        self.personality = None  # 人物性格
        # 系统消息
        self.system_message = None
        self.rebellion_log = self.rebellion.rebellion_log
    
    def update_system_message(self):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        self.system_message = self.rebellion.prompts['rebel_leader_system_message'].format(personality=self.personality)

    def build_make_decision_prompt(self, summary, towns_stats):
        towns_analysis = self.analysis_towns_stats(towns_stats)
        strength = self.rebellion.get_strength()
        resources = self.rebellion.get_resources()
        summary = ("下属建议：" + summary) if summary else ""

        return self.rebellion.prompts['make_decision_prompt'].format(
            strength=strength,
            resources=resources,
            towns_analysis="\n".join(towns_analysis),
            summary=summary,
        )

    def analysis_towns_stats(self, towns_stats):
        """分析各城镇的力量对比"""
        towns_analysis = []
        for town in towns_stats:
            rebel_count = town['rebel_count']
            official_count = town['official_count']
            if rebel_count > 0:  # 只有当叛军数量大于0时才添加到提示词中
                towns_analysis.append(f"{town['town_name']}: 叛军{rebel_count}人，官兵{official_count}人。")
        return towns_analysis
    
    def print_leader_status(self):
        """
        打印叛军头子的状态
        """
        self.rebellion_log.info(f"叛军头子 {self.agent_id} 的状态：")
        self.rebellion_log.info(f"  当前时间：{self.time}年")
        self.rebellion_log.info(f"  角色：{self.role}")
        self.rebellion_log.info(f"  人物性格：{self.personality}")

class InformationOfficer(AgentGroup.DiscussionInformationOfficerBase, IRebelInformationOfficer):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(
            agent_id=agent_id,
            group_type='rebellion',
            shared_pool=shared_pool,
            prompts=rebellion.prompts,
            logger=rebellion.rebellion_log,
            window_size=0,
        )
        self.memory = None
        self.role = "信息整理官"
        self.rebellion = rebellion
        self.rebellion_log = rebellion.rebellion_log

# 所有决策的后果需要存储到记忆中，叛军可以从中学习。
class Rebellion(AgentGroup, IRebellion):
    def __init__(
        self,
        initial_strength,
        initial_resources,
        towns,
        rebels_prompt_path,
        influence_registry: Optional['Any'] = None,
    ):
        """
        初始化叛军类
        :param initial_strength: 初始力量
        :param initial_resources: 初始资源
        """
        AgentGroup.__init__(self, prompts_path=rebels_prompt_path, logger_name="rebels", group_type="rebels")
        self._strength = initial_strength
        self._resources = initial_resources
        self._towns = towns
        self.rebellion_log = self.group_log
        self._influence_registry = influence_registry
    
    # 实现 IRebellion 接口的 property
    @property
    def strength(self) -> int:
        """叛军力量"""
        return self._strength
    
    @strength.setter
    def strength(self, value: int):
        """设置叛军力量"""
        self._strength = value
    
    @property
    def resources(self) -> float:
        """叛军资源"""
        return self._resources
    
    @resources.setter
    def resources(self, value: float):
        """设置叛军资源"""
        self._resources = value
    
    @property
    def towns(self):
        """城镇对象"""
        return self._towns

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

    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """应用所有注册的影响函数到指定目标。"""
        if self._influence_registry is None:
            return

        if context is None:
            context = {}

        context['rebellion'] = self

        influences = self._influence_registry.get_influences(target_name)
        for influence in influences:
            try:
                influence.apply(self, context)
            except Exception as e:
                self.rebellion_log.error(f"应用影响函数失败 ({influence.source}->{target_name}:{influence.name}): {e}")

class RebelsSharedInformationPool(AgentGroup.SharedInformationPoolBase, IRebelsSharedInformationPool):
    def __init__(self, max_discussions: int = 5):
        super().__init__(max_discussions=max_discussions)


