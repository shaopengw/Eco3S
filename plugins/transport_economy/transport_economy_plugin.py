"""交通经济插件实现"""

from typing import Dict, Any, Optional
from src.influences import InfluenceRegistry
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.transport_economy import TransportEconomy


class DefaultTransportEconomyPlugin(TransportEconomy, BasePlugin):
    """
    默认交通经济插件 - 直接继承 TransportEconomy 业务类 + BasePlugin 生命周期
    """

    def __init__(
        self,
        transport_cost: float = 1.0,
        transport_task: float = 500.0,
        maintenance_cost_base: float = 100.0,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        BasePlugin.__init__(self)
        self._transport_cost_param = transport_cost
        self._transport_task_param = transport_task
        self._maintenance_cost_base_param = maintenance_cost_base
        self._influence_registry_param = influence_registry

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 初始化 TransportEconomy 业务状态
        TransportEconomy.__init__(
            self,
            transport_cost=self._transport_cost_param,
            transport_task=self._transport_task_param,
            maintenance_cost_base=self._maintenance_cost_base_param,
            influence_registry=self._influence_registry_param,
        )

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info("DefaultTransportEconomyPlugin 正在加载")

        # 订阅事件
        self.subscribe_event(PluginEvent.MAP_INITIALIZED, self._on_map_initialized)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultTransportEconomyPlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.MAP_INITIALIZED, self._on_map_initialized)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultTransportEconomy",
            "version": "1.0.0",
            "description": "默认交通经济系统插件（直接实现 ITransportEconomy）",
            "author": "AgentWorld Team",
            "dependencies": ["map", "towns"]
        }

    # ===== 内部方法 =====

    def _on_map_initialized(self, data: Dict[str, Any]) -> None:
        """地图初始化时的处理"""
        self.logger.info("收到 map_initialized 事件")
