"""政府插件实现"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from src.agents.government import Government
from src.influences import InfluenceRegistry
from src.interfaces import IMap, ITime, ITowns, ITransportEconomy
from src.plugins import BasePlugin, PluginContext


class DefaultGovernmentPlugin(Government, BasePlugin):
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
        BasePlugin.__init__(self)
        self._map_param = map
        self._towns_param = towns
        self._time_param = time
        self._transport_economy_param = transport_economy
        self._military_strength_param = military_strength
        self._initial_budget_param = initial_budget
        self._government_prompt_path_param = government_prompt_path
        self._influence_registry_param = influence_registry

    def init(self, context: PluginContext) -> None:
        self._context = context
        self.logger = context.logger

        data_cfg = (context.config or {}).get("data", {})
        prompt_path = self._government_prompt_path_param
        if prompt_path is None and isinstance(data_cfg, dict):
            # 通用候选键：优先政府专属 prompt，再兼容各项目命名
            for key in (
                "government_prompt_path",
                "federal_housing_agency_prompt_path",
                "agency_prompt_path",
            ):
                prompt_path = data_cfg.get(key)
                if prompt_path:
                    break
        if not prompt_path:
            # 最后回退到通用模板
            fallback = os.path.join(
                os.getcwd(), "config", "template", "entities", "government", "prompts.yaml"
            )
            if os.path.exists(fallback):
                prompt_path = fallback
        if not prompt_path:
            raise ValueError("DefaultGovernmentPlugin 缺少 government_prompt_path")

        transport = self._transport_economy_param
        if transport is None and context.registry is not None:
            transport_plugin = context.registry.get_plugin("transport_economy")
            if transport_plugin is not None:
                transport = transport_plugin

        Government.__init__(
            self,
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
            "description": "默认政府系统插件（直接实现 IGovernment）",
            "author": "AgentWorld Team",
            "dependencies": ["map", "time", "towns"],
        }
