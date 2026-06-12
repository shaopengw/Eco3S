"""气候插件实现
直接继承 ClimateSystem 业务类和 BasePlugin。
"""

from typing import Dict, Any, Optional
from src.influences import InfluenceRegistry
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.climate import ClimateSystem


class DefaultClimatePlugin(ClimateSystem, BasePlugin):
    """
    默认气候插件 - 直接继承 ClimateSystem 业务类 + BasePlugin 生命周期
    """

    def __init__(
        self,
        climate_data_path: str = 'experiment_dataset/climate_data/climate.csv',
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        BasePlugin.__init__(self)
        self._climate_data_path_param = climate_data_path
        self._influence_registry_param = influence_registry
        # 不在这里调用 ClimateSystem.__init__，等 init() 中配置覆盖后再初始化

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 重新初始化 ClimateSystem 业务状态
        ClimateSystem.__init__(
            self,
            climate_data_path=self._climate_data_path_param,
            influence_registry=self._influence_registry_param,
        )

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info("DefaultClimatePlugin 正在加载")

        # 订阅事件
        self.subscribe_event(PluginEvent.TIME_ADVANCED, self._on_time_advanced)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultClimatePlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.TIME_ADVANCED, self._on_time_advanced)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultClimate",
            "version": "1.0.0",
            "description": "默认气候系统插件（直接实现 IClimateSystem）",
            "author": "AgentWorld Team",
            "dependencies": ["map", "time"]
        }

    def get_current_impact(self, current_year: int = None, start_year: int = None) -> float:
        """获取当前年份的气候影响度（重写以发布事件）"""
        impact = ClimateSystem.get_current_impact(self, current_year, start_year)

        # 发布气候影响事件
        if impact > self.climate_impact_threshold:
            self.publish_event(PluginEvent.EXTREME_CLIMATE_EVENT, {
                'year': current_year,
                'impact': impact
            })

        return impact

    # ===== 内部方法 =====

    def _on_time_advanced(self, data: Dict[str, Any]) -> None:
        """时间推进时的处理"""
        self.logger.debug(f"时间推进到: {data.get('new_time')}")
