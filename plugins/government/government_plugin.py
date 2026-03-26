"""政府插件实现 - service 组合模式。

插件只负责生命周期与配置读取；业务能力由内部 Government(service) 提供。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.agents.government import Government
from src.influences import InfluenceRegistry
from src.interfaces import IMap, ITime, ITowns, ITransportEconomy
from src.plugins import IGovernmentPlugin, PluginContext


class DefaultGovernmentPlugin(IGovernmentPlugin):
    def __init__(
        self,
        map: IMap,
        towns: ITowns,
        time: ITime,
        transport_economy: Optional[ITransportEconomy] = None,
        military_strength: int = 0,
        initial_budget: float = 0.0,
        government_prompt_path: Optional[str] = None,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        super().__init__()
        self._map_param = map
        self._towns_param = towns
        self._time_param = time
        self._transport_economy_param = transport_economy
        self._military_strength_param = military_strength
        self._initial_budget_param = initial_budget
        self._government_prompt_path_param = government_prompt_path
        self._influence_registry_param = influence_registry
        self.logger = None

    def init(self, context: PluginContext) -> None:
        self._context = context
        self.logger = context.logger

        data_cfg = (context.config or {}).get("data", {})
        prompt_path = self._government_prompt_path_param
        if prompt_path is None and isinstance(data_cfg, dict):
            prompt_path = data_cfg.get("government_prompt_path")
        if not prompt_path:
            raise ValueError("DefaultGovernmentPlugin 缺少 government_prompt_path")

        transport = self._transport_economy_param
        if transport is None and context.registry is not None:
            transport_plugin = context.registry.get_plugin("transport_economy")
            if transport_plugin is not None:
                transport = transport_plugin.service

        self._service = Government(
            map=self._map_param,
            towns=self._towns_param,
            military_strength=self._military_strength_param,
            initial_budget=self._initial_budget_param,
            time=self._time_param,
            transport_economy=transport,
            government_prompt_path=prompt_path,
            influence_registry=self._influence_registry_param,
        )

    def on_load(self) -> None:
        if self.logger is not None:
            self.logger.info("DefaultGovernmentPlugin 正在加载")
        self._mark_loaded()

    def on_unload(self) -> None:
        if self.logger is not None:
            self.logger.info("DefaultGovernmentPlugin 正在卸载")
        self._mark_unloaded()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DefaultGovernment",
            "version": "1.0.0",
            "description": "默认政府系统插件（包装 Government 类）",
            "author": "AgentWorld Team",
            "dependencies": ["map", "time", "towns", "transport_economy"],
        }
