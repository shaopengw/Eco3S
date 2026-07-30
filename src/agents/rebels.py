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


class _SafeFormatDict(dict):
    """format_map 安全字典：缺失键填充占位提示，避免 KeyError。"""
    def __missing__(self, key):
        return f"[未提供:{key}]"


def _build_member_template_vars(member, base_vars):
    """合并成员 profile 与基础变量，供系统消息模板安全 format。"""
    merged = {}
    profile = getattr(member, "profile", None)
    if isinstance(profile, dict):
        merged.update(profile)
    merged.update({k: v for k, v in base_vars.items() if v is not None})
    try:
        merged.setdefault("profile_vars_doc", member._build_profile_vars_doc())
    except Exception:
        merged.setdefault("profile_vars_doc", "")
    return merged


def _member_getattr(obj, name: str):
    """成员通用 __getattr__：类上不存在的属性回退到 profile 读取。"""
    if name.startswith("_") or name in ("profile", "attr", "set_attr"):
        raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{name}'")
    profile = obj.__dict__.get("profile")
    if isinstance(profile, dict) and name in profile:
        return profile[name]
    raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{name}'")


class OrdinaryRebel(AgentGroup.DiscussionMemberAgentBase, IOrdinaryRebel):
    def __init__(self, agent_id, rebellion, shared_pool):
        super().__init__(agent_id, group_type='rebellion', shared_pool=shared_pool, window_size=3)
        self.rebellion = rebellion
        self.time = 0  # 当前时间（年）
        self.role = None  # 角色
        self.personality = None  # 人物性格
        self.system_message = None  # 系统提示词
        self.rebellion_log = self.rebellion.rebellion_log

    def __getattr__(self, name: str):
        return _member_getattr(self, name)

    def get_memory_role_name(self) -> str:
        return "普通叛军头目之一"

    def get_logger(self):
        return self.rebellion_log

    def update_system_message(self):
        """
        更新系统提示词。注入 role/personality 及 profile 中的自定义画像字段。
        """
        base_vars = {"role": self.role, "personality": self.personality}
        template_vars = _build_member_template_vars(self, base_vars)
        self.system_message = self.rebellion.prompts['ordinary_rebel_system_message'].format_map(
            _SafeFormatDict(template_vars))

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

    def __getattr__(self, name: str):
        return _member_getattr(self, name)

    def update_system_message(self):
        """
        更新系统提示词。注入 personality 及 profile 中的自定义画像字段。
        """
        base_vars = {"role": self.role, "personality": self.personality}
        template_vars = _build_member_template_vars(self, base_vars)
        self.system_message = self.rebellion.prompts['rebel_leader_system_message'].format_map(
            _SafeFormatDict(template_vars))

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

    async def execute_group_turn(self, agents: Dict[int, Any], simulator_context: Optional[Any] = None) -> None:
        """叛军群体一轮决策并作用于世界的通用入口。

        由 BaseSimulator.execute_group_agent_actions 在每回合调用。
        默认实现从 simulator_context 获取 towns_stats，调用 orchestrate_group_decision
        收集叛军 LLM 决策，再调用 apply_decision 记录/执行。
        """
        if not agents:
            return

        group_param = None
        if simulator_context is not None and hasattr(simulator_context, "get_rebels_statistics"):
            try:
                group_param = simulator_context.get_rebels_statistics()
            except Exception as e:
                self.rebellion_log.warning(f"计算叛军决策参数失败：{e}")

        decision = await self.orchestrate_group_decision(
            agents=agents,
            group_param=group_param,
            group_type="rebellion",
            ordinary_type=OrdinaryRebel,
            leader_type=RebelLeader,
            info_officer_types=(InformationOfficer,),
        )

        if decision:
            self.rebellion_log.info(f"叛军群体决策：{decision}")
            self.apply_decision(decision, simulator_context=simulator_context)

    def apply_decision(self, decision: Any, simulator_context: Optional[Any] = None) -> None:
        """将叛军群体决策作用于世界。

        默认实现仅解析并记录决策内容。项目特定插件/子类应覆写以执行
        具体动作（如煽动叛乱、宣传等）。
        """
        if decision is None:
            return

        decision_data = decision
        if isinstance(decision, str):
            try:
                decision_data = json.loads(decision)
            except json.JSONDecodeError:
                import re
                matches = re.findall(r'\{[^{}]*\}', decision)
                for match in matches:
                    try:
                        decision_data = json.loads(match)
                        break
                    except json.JSONDecodeError:
                        continue

        self.rebellion_log.info(f"叛军决策已记录：{decision_data}")

class RebelsSharedInformationPool(AgentGroup.SharedInformationPoolBase, IRebelsSharedInformationPool):
    def __init__(self, max_discussions: int = 5):
        super().__init__(max_discussions=max_discussions)


