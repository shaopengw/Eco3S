from .shared_imports import *

from typing import Callable, Tuple

from src.interfaces.iagent_group import IAgentGroup


class AgentGroup(IAgentGroup):
    """群体系统基类（政府/叛军/其他群体）。

    设计目标：
    - 作为可继承的大类，提供一组通用能力（prompts、日志、讨论调度等）。
    - 不内置任何具体群体（不包含 Government/Rebellion 的领域逻辑）。
    - 具体群体在外部“按需继承或调用”，以便后续扩展新群体类型。

    说明：
    - 讨论调度能力是通用的，可由 Simulator/群体自身调用。
    """

    def __init__(self, prompts_path: str, logger_name: str, group_type: Optional[str] = None):
        self.group_type = group_type or logger_name
        with open(prompts_path, 'r', encoding='utf-8') as file:
            self.prompts = yaml.safe_load(file)
        self.group_log = LogManager.get_logger(logger_name)

    @staticmethod
    async def generate_agents_from_info_json(
        info_path: str,
        *,
        group_obj: Any,
        rank_factories: Dict[str, Callable[[int, Any, Any], Any]],
        shared_pool: Optional[Any] = None,
        shared_pool_factory: Optional[Callable[[], Any]] = None,
        agent_graph: Optional[Dict[int, Any]] = None,
        id_mapping: Optional[Dict[int, int]] = None,
        init_agent: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
        add_info_officer: Optional[Callable[[int, Any, Any], Any]] = None,
        validate_types: Optional[Tuple[type, ...]] = None,
        rank_field: str = "rank",
        encoding: str = "utf-8",
    ) -> tuple[Dict[int, Any], Dict[int, int], Any]:
        """从 JSON 信息文件批量生成 agent 图谱（通用版）。

        设计目的：
        - 复用政府/叛军等“群体成员生成”几乎一致的底层流程。
        - 通过 rank_factories / init_agent / add_info_officer 注入差异点，避免引入领域模块循环依赖。

        返回： (agent_graph, id_mapping, shared_pool)
        """

        if agent_graph is None:
            agent_graph = {}
        if id_mapping is None:
            id_mapping = {}

        if shared_pool is None:
            if shared_pool_factory is None:
                raise ValueError("shared_pool 为空且 shared_pool_factory 未提供")
            shared_pool = shared_pool_factory()

        with open(info_path, "r", encoding=encoding, errors="ignore") as file:
            info_list = json.load(file)
        if not isinstance(info_list, list):
            raise TypeError("信息文件 JSON 顶层必须是 list")

        base_id = max(agent_graph.keys(), default=0)

        async def process_one(i: int, data: Dict[str, Any]) -> None:
            agent_id = base_id + i + 1
            rank = data.get(rank_field)
            if rank not in rank_factories:
                raise ValueError(f"未知的类型：{rank}")

            agent = rank_factories[rank](agent_id, group_obj, shared_pool)
            if init_agent is not None:
                init_agent(agent, data)

            agent_graph[agent_id] = agent
            id_mapping[agent_id] = agent_id

        tasks = [process_one(i, data) for i, data in enumerate(info_list)]
        if tasks:
            await asyncio.gather(*tasks)

        if add_info_officer is not None:
            info_id = max(agent_graph.keys(), default=0) + 1
            info_agent = add_info_officer(info_id, group_obj, shared_pool)
            agent_graph[info_id] = info_agent
            id_mapping[info_id] = info_id

        if validate_types is not None:
            if not all(isinstance(a, validate_types) for a in agent_graph.values()):
                raise TypeError("agent_graph 中包含非法对象")

        return agent_graph, id_mapping, shared_pool

    # 讨论调度 / 配置读取
    @staticmethod
    def load_group_decision_settings(group_type: str, default_enabled: bool = True, default_max_rounds: int = 2):
        """从 simulation_config.yaml 读取群体决策配置。

        兼容 config 结构：
        - simulation.group_decision.<group_type>.{enabled,max_rounds}
        - 读取失败则回退到默认值
        """
        try:
            with open(f'config/{SimulationContext.get_simulation_type()}/simulation_config.yaml', 'r', encoding='utf-8') as f:
                sim_config = yaml.safe_load(f) or {}
                group_decision_config = (sim_config.get('simulation') or {}).get('group_decision', {})
                # 兼容两种结构：
                # 1) group_decision: { enabled, max_rounds }  (如 TEOG)
                # 2) group_decision: { government: {..}, rebellion: {..} }
                if isinstance(group_decision_config, dict) and (
                    'enabled' in group_decision_config or 'max_rounds' in group_decision_config
                ):
                    enabled = group_decision_config.get('enabled', default_enabled)
                    max_rounds = group_decision_config.get('max_rounds', default_max_rounds)
                else:
                    group_config = group_decision_config.get(group_type, {}) if isinstance(group_decision_config, dict) else {}
                    enabled = group_config.get('enabled', default_enabled)
                    max_rounds = group_config.get('max_rounds', default_max_rounds)
                return enabled, max_rounds
        except Exception:
            return default_enabled, default_max_rounds

    @staticmethod
    def _iter_agents(agents: Any) -> List[Any]:
        if agents is None:
            return []
        if isinstance(agents, dict):
            return list(agents.values())
        if isinstance(agents, list):
            return list(agents)
        if isinstance(agents, tuple):
            return list(agents)
        return list(agents)

    @staticmethod
    def _pick_shared_pool(agent_list: List[Any]):
        for member in agent_list:
            if hasattr(member, 'shared_pool') and getattr(member, 'shared_pool') is not None:
                return getattr(member, 'shared_pool')
        return None

    @staticmethod
    def _filter_members(
        agent_list: List[Any],
        ordinary_type: type,
        leader_type: type,
        info_officer_types: tuple[type, ...],
    ):
        leaders = [m for m in agent_list if isinstance(m, leader_type)]
        info_officers = [m for m in agent_list if isinstance(m, info_officer_types)] if info_officer_types else []
        ordinary_members = [
            m for m in agent_list
            if isinstance(m, ordinary_type)
            and not isinstance(m, leader_type)
            and (not info_officer_types or not isinstance(m, info_officer_types))
        ]
        return leaders, info_officers, ordinary_members

    async def orchestrate_group_decision(
        self,
        *,
        agents: Any,
        group_param: Any,
        group_type: Optional[str] = None,
        ordinary_type: type,
        leader_type: type,
        info_officer_types: tuple[type, ...] = (),
        enabled: bool | None = None,
        max_rounds: int | None = None,
        shuffle: bool = True,
    ) -> Optional[str]:
        """统一的群体讨论->决策调度。

        - enabled/max_rounds 若不提供，则从配置读取。
        - agents 支持 dict / list。
        - 依赖约定：成员提供 shared_pool，普通成员实现 generate_opinion/generate_and_share_opinion，
          信息官实现 summarize_discussions，领导者实现 make_decision。
        """
        group_type = group_type or getattr(self, 'group_type', None)
        if not group_type:
            raise ValueError("orchestrate_group_decision 缺少 group_type（参数未提供且实例未设置 group_type）")

        agent_list = self._iter_agents(agents)
        if not agent_list:
            return None

        if enabled is None or max_rounds is None:
            cfg_enabled, cfg_max_rounds = self.load_group_decision_settings(group_type)
            enabled = cfg_enabled if enabled is None else enabled
            max_rounds = cfg_max_rounds if max_rounds is None else max_rounds

        leaders, info_officers, ordinary_members = self._filter_members(
            agent_list, ordinary_type=ordinary_type, leader_type=leader_type, info_officer_types=info_officer_types
        )
        if not leaders:
            return None
        leader = leaders[0]

        # 不启用群体决策：直接决策
        if not enabled:
            return await leader.make_decision("直接决策模式，无群体讨论。", group_param)

        if not ordinary_members:
            return None

        shared_pool = self._pick_shared_pool(agent_list)
        if shared_pool is None:
            return None
        await shared_pool.clear_discussions()

        # 轮次 1：初始意见
        members = list(ordinary_members)
        if shuffle:
            members = random.sample(members, len(members))
        await asyncio.gather(*[m.generate_opinion(group_param) for m in members])

        # 轮次 2..N：回应讨论
        for round_num in range(2, int(max_rounds) + 1):
            try:
                self.group_log.info(f"第{round_num}轮决策")
            except Exception:
                pass

            members_round = list(ordinary_members)
            if shuffle:
                members_round = random.sample(members_round, len(members_round))
            await asyncio.gather(*[m.generate_and_share_opinion(group_param) for m in members_round])

        # 信息官总结 -> 领导决策
        if not info_officers:
            return await leader.make_decision("(无信息官) 讨论结束，请直接决策。", group_param)

        discussion_summary = await info_officers[0].summarize_discussions()
        if not discussion_summary:
            return None
        return await leader.make_decision(discussion_summary, group_param)

    class SharedInformationPoolBase:
        """共享信息池的通用实现。"""

        def __init__(self, max_discussions: int = 5):
            self.discussions: List[str] = []
            self.max_discussions = max_discussions
            self.is_discussion_ended = False
            self.lock = asyncio.Lock()

        async def add_discussion(self, discussion: str) -> bool:
            async with self.lock:
                if self.is_discussion_ended:
                    return False
                self.discussions.append(discussion)
                if len(self.discussions) >= self.max_discussions:
                    self.is_discussion_ended = True
                return True

        async def get_latest_discussion(self) -> Optional[str]:
            async with self.lock:
                return self.discussions[-1] if self.discussions else None

        async def get_all_discussions(self) -> List[str]:
            async with self.lock:
                return list(self.discussions) if self.discussions else []

        async def clear_discussions(self) -> None:
            async with self.lock:
                self.discussions.clear()
                self.is_discussion_ended = False

    class DiscussionMemberAgentBase(BaseAgent):
        """具备“发表意见/参与讨论”的普通成员通用流程。

        子类只需要实现：
        - update_system_message()
        - build_generate_opinion_prompt(group_param)
        - build_generate_and_share_opinion_prompt(all_discussions, group_param)
        - get_memory_role_name()
        - get_logger()
        """

        def __init__(
            self,
            agent_id: str,
            group_type: str,
            shared_pool: Any,
            window_size: int = 3,
            *,
            logger: Any = None,
            memory_role_name: Optional[str] = None,
        ):
            super().__init__(agent_id, group_type=group_type, window_size=window_size)
            self.shared_pool = shared_pool

            # 可选：通用样板信息下沉
            self._logger = logger
            self._memory_role_name = memory_role_name

        def get_memory_role_name(self) -> str:
            if self._memory_role_name:
                return str(self._memory_role_name)
            return self.__class__.__name__

        def get_logger(self):
            if self._logger is not None:
                return self._logger
            try:
                return LogManager.get_logger(str(getattr(self, 'group_type', 'agent')))
            except Exception:
                return logging.getLogger(str(getattr(self, 'group_type', 'agent')))

        def build_generate_opinion_prompt(self, group_param: Any) -> str:
            raise NotImplementedError

        def build_generate_and_share_opinion_prompt(self, all_discussions: List[str], group_param: Any) -> str:
            raise NotImplementedError

        async def _write_opinion_memory_record(self, opinion: str) -> None:
            if not self.memory:
                return
            await self.memory.write_record(
                role_name=self.get_memory_role_name(),
                content=f"我的意见：{opinion}",
                is_user=False,
                store_in_shared=False,
            )

        async def generate_opinion(self, group_param: Any) -> str:
            prompt = self.build_generate_opinion_prompt(group_param)
            self.update_system_message()
            opinion = await self.generate_llm_response(prompt)

            if opinion:
                await self._write_opinion_memory_record(opinion)
                await self.shared_pool.add_discussion(opinion)
                self.get_logger().info(f"{self.__class__.__name__} {self.agent_id} 生成的意见：{opinion}")
                return opinion

            return "无法生成意见"

        async def generate_and_share_opinion(self, group_param: Any) -> None:
            all_discussion = await self.shared_pool.get_all_discussions()
            if all_discussion:
                prompt = self.build_generate_and_share_opinion_prompt(all_discussion, group_param)
                try:
                    self.update_system_message()
                    opinion = await self.generate_llm_response(prompt)
                    if opinion:
                        await self.shared_pool.add_discussion(opinion)
                        self.get_logger().info(f"{self.__class__.__name__} {self.agent_id} 回应了讨论：{opinion}")
                except Exception as e:
                    self.get_logger().error(f"{self.__class__.__name__} {self.agent_id} 在生成回应时出错：{e}")
            else:
                await self.generate_opinion(group_param)

    class DiscussionLeaderAgentBase(BaseAgent):
        """具备“最终决策”的领导者通用流程。"""

        def __init__(
            self,
            agent_id: str,
            group_type: str,
            shared_pool: Any,
            window_size: int = 3,
            *,
            logger: Any = None,
        ):
            super().__init__(agent_id, group_type=group_type, window_size=window_size)
            self.shared_pool = shared_pool

            self._logger = logger

        def get_logger(self):
            if self._logger is not None:
                return self._logger
            try:
                return LogManager.get_logger(str(getattr(self, 'group_type', 'agent')))
            except Exception:
                return logging.getLogger(str(getattr(self, 'group_type', 'agent')))

        def build_make_decision_prompt(self, summary: str, group_param: Any) -> str:
            raise NotImplementedError

        async def make_decision(self, summary: str, group_param: Any) -> str:
            prompt = self.build_make_decision_prompt(summary, group_param)
            try:
                self.update_system_message()
                decision = await self.generate_llm_response(prompt)
                if decision:
                    self.get_logger().info(f"{self.__class__.__name__} {self.agent_id} 的决策：{decision}")
                    await self.shared_pool.clear_discussions()
                    return decision
            except Exception as e:
                self.get_logger().error(f"{self.__class__.__name__} {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    class DiscussionInformationOfficerBase(BaseAgent):
        """信息整理官通用流程：汇总共享池讨论。"""

        def __init__(
            self,
            agent_id: str,
            group_type: str,
            shared_pool: Any,
            prompts: Dict[str, Any],
            logger: Any,
            window_size: int = 0,
        ):
            super().__init__(agent_id, group_type=group_type, window_size=window_size)
            self.shared_pool = shared_pool
            self.prompts = prompts
            self._logger = logger

        def get_prompt_key(self) -> str:
            return 'summarize_discussions_prompt'

        def get_logger(self):
            return self._logger

        async def summarize_discussions(self) -> str:
            discussions = await self.shared_pool.get_all_discussions()
            if not discussions:
                return "暂无讨论内容"

            prompt = self.prompts[self.get_prompt_key()].format(
                num_discussions=len(discussions),
                discussions="\n".join([f"{i + 1}. {d}" for i, d in enumerate(discussions)]),
            )

            try:
                summary = await self.generate_llm_response(prompt)
                if summary:
                    self.get_logger().info(f"{self.__class__.__name__} {self.agent_id} 生成总结报告：{summary}")
                    return summary
                return "无法生成总结报告"
            except Exception as e:
                self.get_logger().error(f"{self.__class__.__name__} {self.agent_id} 在生成总结报告时出错：{e}")
                return "无法生成总结报告"

