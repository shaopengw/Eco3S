from __future__ import annotations

from typing import Any, Dict

from src.plugins import BasePlugin, PluginContext


class PluginTemplate(BasePlugin):
    """插件模板。复制后修改 name / description / plugin_class 即可。"""

    def __init__(self, **kwargs: Any):
        super().__init__()
        self._init_kwargs = dict(kwargs)

    def init(self, context: PluginContext) -> None:
        self._context = context
        self.logger = context.logger
        self._service = self

    def on_load(self) -> None:
        self._mark_loaded()

    def on_unload(self) -> None:
        self._mark_unloaded()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "plugin_template",
            "version": "0.1.0",
            "description": "插件模板：提供最小可运行骨架，复制后修改 name/description 即可",
            "author": "AgentWorld",
            "dependencies": [],
        }
