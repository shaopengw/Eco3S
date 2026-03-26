"""居民插件实现 - 封装/适配居民生成与访问。

目标：
- 像 government/rebellion 一样，作为一个可通过 PluginRegistry 获取的“模块插件”。
- 内部复用 generate_canal_agents 生成居民，并缓存到 self.residents，便于后续直接使用。

说明：
- 生成过程是异步的（generate_canal_agents 为 async），因此对齐插件生命周期，
  这里提供一次性 async 初始化方法 init_residents()/ensure_initialized()。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.plugins import IResidentsPlugin, PluginContext
from src.interfaces import IMap
from src.influences import InfluenceRegistry
from src.agents.resident_agent_generator import generate_canal_agents


class DefaultResidentsPlugin(IResidentsPlugin):
    """默认居民模块插件。"""

    def __init__(
        self,
        map: IMap,
        resident_info_path: Optional[str] = None,
        resident_prompt_path: Optional[str] = None,
        resident_actions_path: Optional[str] = None,
        window_size: int = 3,
        initial_population: Optional[int] = None,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        super().__init__()

        self._map_param = map
        self._resident_info_path_param = resident_info_path
        self._resident_prompt_path_param = resident_prompt_path
        self._resident_actions_path_param = resident_actions_path
        self._window_size_param = window_size
        self._initial_population_param = initial_population
        self._influence_registry_param = influence_registry

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
            "version": "1.0.0",
            "description": "默认居民系统插件（封装 generate_canal_agents，并缓存 residents 结果）",
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
        """确保居民已生成（只生成一次，可用 force=True 强制重建）。

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
        if not resident_info_path:
            raise ValueError("DefaultResidentsPlugin 缺少 resident_info_path")
        if not resident_prompt_path:
            raise ValueError("DefaultResidentsPlugin 缺少 resident_prompt_path")
        if not resident_actions_path:
            raise ValueError("DefaultResidentsPlugin 缺少 resident_actions_path")

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

        self._residents = await generate_canal_agents(
            resident_info_path=str(resident_info_path),
            map=self._map_param,
            initial_population=int(initial_population),
            agent_graph=agent_graph,
            shared_pool=shared_pool,
            resident_id_mapping=resident_id_mapping,
            resident_prompt_path=str(resident_prompt_path),
            resident_actions_path=str(resident_actions_path),
            window_size=int(window_size),
            influence_registry=self._influence_registry_param,
        )

        # 缓存辅助对象（如果调用方没有传入映射/共享池，则 generate_canal_agents 内部会创建）
        if resident_id_mapping is not None:
            self._resident_id_mapping = resident_id_mapping
        if shared_pool is not None:
            self._shared_pool = shared_pool

        return self._residents

    async def generate(self, **kwargs) -> Dict[int, Any]:
        """兼容旧的“生成器插件”调用方式。"""
        return await self.ensure_initialized(**kwargs)
