"""src.plugins.service_plugin

通用“业务实现包装器”插件基类。

设计目标：
- 插件类只负责生命周期（BasePlugin）与系统交互（PluginContext / EventBus）。
- 业务能力由内部 `service` 对象提供（实现 IMap/ITime/... 等业务接口）。
- 通过 `__getattr__` 自动转发未显式实现的属性/方法，避免每新增业务方法都要改插件代理。

这对应最初设计中的“Plugin 类包装业务实现”。
"""

from __future__ import annotations

from typing import Any, Optional

from .base_plugin import BasePlugin


class ServicePlugin(BasePlugin):
    """带 `service` 的插件基类。

    约定：子类在 init(context) 内创建/绑定 `self._service`。
    """

    def __init__(self):
        super().__init__()
        self._service: Optional[Any] = None

    @property
    def service(self) -> Any:
        if self._service is None:
            raise RuntimeError(f"{self.__class__.__name__} 的 service 尚未初始化")
        return self._service

    def __getattr__(self, name: str) -> Any:
        # 仅当常规属性查找失败时才会进入这里。
        service = object.__getattribute__(self, "_service")
        if service is None:
            raise AttributeError(name)
        return getattr(service, name)
