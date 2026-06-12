"""叛军插件实现"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.agents.rebels import Rebellion
from src.influences import InfluenceRegistry
from src.interfaces import ITowns
from src.plugins import BasePlugin, PluginContext


class DefaultRebellionPlugin(Rebellion, BasePlugin):
    def __init__(
        self,
        towns: ITowns,
        initial_strength: int = 0,
        initial_resources: float = 0.0,
        rebels_prompt_path: Optional[str] = None,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        BasePlugin.__init__(self)
        self._towns_param = towns
        self._initial_strength_param = initial_strength
        self._initial_resources_param = initial_resources
        self._rebels_prompt_path_param = rebels_prompt_path
        self._influence_registry_param = influence_registry

    def init(self, context: PluginContext) -> None:
        self._context = context
        self.logger = context.logger

        data_cfg = (context.config or {}).get("data", {})
        prompt_path = self._rebels_prompt_path_param
        if prompt_path is None and isinstance(data_cfg, dict):
            prompt_path = data_cfg.get("rebels_prompt_path")
        if not prompt_path:
            raise ValueError("DefaultRebellionPlugin 缺少 rebels_prompt_path")

        Rebellion.__init__(
            self,
            initial_strength=self._initial_strength_param,
            initial_resources=self._initial_resources_param,
            towns=self._towns_param,
            rebels_prompt_path=prompt_path,
            influence_registry=self._influence_registry_param,
        )

    def on_load(self) -> None:
        if self.logger is not None:
            self.logger.info("DefaultRebellionPlugin 正在加载")
        self._mark_loaded()

    def on_unload(self) -> None:
        if self.logger is not None:
            self.logger.info("DefaultRebellionPlugin 正在卸载")
        self._mark_unloaded()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DefaultRebellion",
            "version": "1.0.0",
            "description": "默认叛军系统插件（直接实现 IRebellion）",
            "author": "AgentWorld Team",
            "dependencies": ["towns"],
        }
