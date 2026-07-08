"""居民插件实现 - 封装/适配居民生成与访问。

目标：
- 像 government/rebellion 一样，作为一个可通过 PluginRegistry 获取的"模块插件"。
- 内部生成居民，并缓存到 self.residents，便于后续直接使用。

说明：
- 生成过程是异步的，因此对齐插件生命周期，
  这里提供一次性 async 初始化方法 init_residents()/ensure_initialized()。
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from src.agents.agent_generator import generate_agents
from src.influences import InfluenceRegistry
from src.interfaces import IMap
from src.plugins import BasePlugin, PluginContext


class DefaultResidentsPlugin(BasePlugin):
    """默认居民模块插件。

    注：类名保留 DefaultResidentsPlugin 以兼容已有代码，
    但内部已支持通过 entity_type 切换不同实体类型。
    """

    def __init__(
        self,
        map: IMap,
        resident_info_path: Optional[str] = None,
        resident_prompt_path: Optional[str] = None,
        resident_actions_path: Optional[str] = None,
        config_dir: Optional[str] = None,
        agent_profile_path: Optional[str] = None,
        window_size: int = 3,
        initial_population: Optional[int] = None,
        influence_registry: Optional[InfluenceRegistry] = None,
        entity_type: str = "resident",
    ):
        super().__init__()

        self._map_param = map
        self._resident_info_path_param = resident_info_path
        self._resident_prompt_path_param = resident_prompt_path
        self._resident_actions_path_param = resident_actions_path
        self._config_dir_param = config_dir
        self._agent_profile_path_param = agent_profile_path
        self._window_size_param = window_size
        self._initial_population_param = initial_population
        self._influence_registry_param = influence_registry
        self._entity_type_param = entity_type

        self._context: Optional[PluginContext] = None
        self.logger = None

        self._residents: Optional[Dict[int, Any]] = None
        self._resident_id_mapping: Dict[int, int] = {}
        self._shared_pool: Any = None

    def init(self, context: PluginContext) -> None:
        self._context = context
        self.logger = context.logger

    def on_load(self) -> None:
        if self.logger is not None:
            self.logger.info("DefaultResidentsPlugin 正在加载")
        self._mark_loaded()

    def on_unload(self) -> None:
        if self.logger is not None:
            self.logger.info("DefaultResidentsPlugin 正在卸载")
        self._mark_unloaded()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DefaultResidents",
            "version": "1.1.0",
            "description": "默认居民系统插件（支持 entity_type 切换）",
            "author": "AgentWorld Team",
            "dependencies": [
                "map",
            ],
        }

    @property
    def residents(self) -> Dict[int, Any]:
        return self._residents or {}

    async def init_residents(self, **kwargs) -> Dict[int, Any]:
        return await self.ensure_initialized(**kwargs)

    async def ensure_initialized(
        self,
        **kwargs,
    ) -> Dict[int, Any]:
        """确保 Agent 已生成（只生成一次，可用 force=True 强制重建）。

        参数优先级：kwargs > 构造参数 > context.config。
        """

        force = bool(kwargs.get("force", False))
        if self._residents is not None and not force:
            return self._residents

        if not self._context:
            raise RuntimeError("DefaultResidentsPlugin 未初始化（缺少 PluginContext）")

        data_cfg = (self._context.config or {}).get("data", {})
        sim_cfg = (self._context.config or {}).get("simulation", {})

        resident_info_path = (
            kwargs.get("resident_info_path")
            or self._resident_info_path_param
            or data_cfg.get("resident_info_path")
        )
        resident_prompt_path = (
            kwargs.get("resident_prompt_path")
            or self._resident_prompt_path_param
            or data_cfg.get("resident_prompt_path")
        )
        resident_actions_path = (
            kwargs.get("resident_actions_path")
            or self._resident_actions_path_param
            or data_cfg.get("resident_actions_path")
        )
        agent_profile_path = (
            kwargs.get("agent_profile_path")
            or self._agent_profile_path_param
            or data_cfg.get("agent_profile_path")
        )
        config_dir = kwargs.get("config_dir") or self._config_dir_param
        if not config_dir and agent_profile_path:
            config_dir = os.path.dirname(str(agent_profile_path)) or None

        # 同时支持 agent_profile 和 resident_profile（向后兼容）
        profile_config = None
        for key in ("agent_profile", "resident_profile"):
            if key in (self._context.config or {}):
                profile_config = self._context.config[key]
                break

        # 若未内联，尝试从文件路径加载
        if profile_config is None:
            import yaml

            if agent_profile_path and os.path.exists(agent_profile_path):
                with open(agent_profile_path, "r", encoding="utf-8") as f:
                    profile_config = yaml.safe_load(f)
            elif config_dir:
                auto_path = os.path.join(config_dir, "agent_profile.yaml")
                if os.path.exists(auto_path):
                    with open(auto_path, "r", encoding="utf-8") as f:
                        profile_config = yaml.safe_load(f)

        initial_population = kwargs.get("initial_population")
        if initial_population is None:
            initial_population = self._initial_population_param
        if initial_population is None:
            initial_population = sim_cfg.get("initial_population")
        if initial_population is None:
            initial_population = 10

        window_size = kwargs.get("window_size")
        if window_size is None:
            window_size = self._window_size_param

        agent_graph = kwargs.get("agent_graph")
        shared_pool = kwargs.get("shared_pool")
        resident_id_mapping = kwargs.get("resident_id_mapping")

        entity_type = kwargs.get("entity_type", self._entity_type_param)
        # 若 profile_config 中显式声明了 entity_type，以配置为准
        if isinstance(profile_config, dict) and "entity_type" in profile_config:
            entity_type = profile_config["entity_type"]

        # 判断是否使用新版通用生成器：agent_profile 中定义了 agents 列表
        use_generic_generator = isinstance(profile_config, dict) and profile_config.get("agents")

        if use_generic_generator:
            # 新版：使用 agent_generator.generate_agents，支持基于 config_dir 的自动探测
            group_counts = sim_cfg.get("group_counts")
            self._residents = await generate_agents(
                map=self._map_param,
                initial_population=int(initial_population),
                agent_profile=profile_config,
                agent_graph=agent_graph,
                shared_pool=shared_pool,
                prompts_path=str(resident_prompt_path) if resident_prompt_path else None,
                actions_path=str(resident_actions_path) if resident_actions_path else None,
                window_size=int(window_size),
                influence_registry=self._influence_registry_param,
                config_dir=config_dir,
                group_counts=group_counts,
            )

        # 缓存辅助对象
        if resident_id_mapping is not None:
            self._resident_id_mapping = resident_id_mapping
        if shared_pool is not None:
            self._shared_pool = shared_pool

        return self._residents

    async def generate(self, **kwargs) -> Dict[int, Any]:
        """兼容旧的"生成器插件"调用方式。"""
        return await self.ensure_initialized(**kwargs)
