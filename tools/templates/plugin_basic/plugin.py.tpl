from __future__ import annotations

from typing import Any, Dict

from src.plugins import BasePlugin, PluginContext


class {plugin_class}(BasePlugin):
    def __init__(self, **kwargs: Any):
        super().__init__()
        self._init_kwargs = dict(kwargs)

    def init(self, context: PluginContext) -> None:
        self._context = context
        self.logger = context.logger
        self._service = self  # 兜底：保持 service 存在

    def on_load(self) -> None:
        self._mark_loaded()

    def on_unload(self) -> None:
        self._mark_unloaded()

    def get_metadata(self) -> Dict[str, Any]:
        return {{
            "name": "{name}",
            "version": "{version}",
            "description": "{description}",
            "author": "{author}",
            "dependencies": [],
        }}
