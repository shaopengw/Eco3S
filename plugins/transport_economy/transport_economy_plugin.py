"""交通经济插件实现 - 包装器模式"""

from typing import Dict, Any, Optional
from src.plugins import ITransportEconomyPlugin, PluginContext
from src.influences import InfluenceRegistry
from src.environment.transport_economy import TransportEconomy


class DefaultTransportEconomyPlugin(ITransportEconomyPlugin):
    """
    默认交通经济插件 - 包装现有 TransportEconomy 类
    """
    
    def __init__(
        self,
        transport_cost: float = 1.0,
        transport_task: float = 500.0,
        maintenance_cost_base: float = 100.0,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        """
        初始化交通经济插件
        
        Args:
            transport_cost: 基础运输成本
            transport_task: 年度运输任务量（吨）
            maintenance_cost_base: 基础维护成本
        """
        super().__init__()
        
        # 保存参数
        self._transport_cost_param = transport_cost
        self._transport_task_param = transport_task
        self._maintenance_cost_base_param = maintenance_cost_base
        self._influence_registry_param = influence_registry
        self._transport_economy = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建原始 TransportEconomy 实例
        self._transport_economy = TransportEconomy(
            transport_cost=self._transport_cost_param,
            transport_task=self._transport_task_param,
            maintenance_cost_base=self._maintenance_cost_base_param,
            influence_registry=self._influence_registry_param,
        )
        self._service = self._transport_economy

        self._influence_registry = (
            getattr(self._transport_economy, "_influence_registry", None) or self._influence_registry_param
        )
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultTransportEconomyPlugin 正在加载")
        
        # 订阅事件
        self.context.event_bus.subscribe('map_initialized', self._on_map_initialized)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultTransportEconomyPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('map_initialized', self._on_map_initialized)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultTransportEconomy",
            "version": "1.0.0",
            "description": "默认交通经济系统插件（包装 TransportEconomy 类）",
            "author": "AgentWorld Team",
            "dependencies": ["map", "towns"]
        }
    
    # ===== 内部方法 =====
    
    def _on_map_initialized(self, data: Dict[str, Any]) -> None:
        """地图初始化时的处理"""
        self.logger.info("收到 map_initialized 事件")
