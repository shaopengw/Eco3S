"""
气候插件实现 - 包装器模式
"""
from typing import Dict, Any, List
from src.plugins import IClimatePlugin, PluginContext
from src.interfaces import IClimateSystem
from src.environment.climate import ClimateSystem


class DefaultClimatePlugin(IClimatePlugin):
    """
    默认气候插件 - 包装现有 ClimateSystem 类
    """
    
    def __init__(self, climate_data_path: str = 'experiment_dataset/climate_data/climate.csv'):
        """
        初始化气候插件
        
        Args:
            climate_data_path: 气候数据文件路径
        """
        super().__init__()
        
        # 保存参数
        self._climate_data_path_param = climate_data_path
        self._climate = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建原始 ClimateSystem 实例
        self._climate = ClimateSystem(climate_data_path=self._climate_data_path_param)
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info("DefaultClimatePlugin 正在加载")
        
        # 订阅事件
        self.context.event_bus.subscribe('time_advanced', self._on_time_advanced)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultClimatePlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('time_advanced', self._on_time_advanced)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultClimate",
            "version": "1.0.0",
            "description": "默认气候系统插件（包装 ClimateSystem 类）",
            "author": "AgentWorld Team",
            "dependencies": ["default_map", "default_time"]
        }
    
    # ===== IClimateSystem 接口属性 - 代理到内部 ClimateSystem 实例 =====
    
    @property
    def climate_data(self) -> List[float]:
        return self._climate.climate_data
    
    @property
    def climate_impact_threshold(self) -> float:
        return self._climate.climate_impact_threshold
    
    # ===== IClimateSystem 接口方法 - 代理到内部 ClimateSystem 实例 =====
    
    def get_current_impact(self, current_year: int = None, start_year: int = None) -> float:
        """获取当前年份的气候影响度"""
        impact = self._climate.get_current_impact(current_year, start_year)
        
        # 发布气候影响事件
        if impact > self.climate_impact_threshold:
            self.context.event_bus.publish('extreme_climate_event', {
                'year': current_year,
                'impact': impact
            })
        
        return impact
    
    def is_extreme_event(self, impact: float) -> bool:
        """判断是否为极端气候事件"""
        return self._climate.is_extreme_event(impact)
    
    def get_climate_description(self, impact: float) -> str:
        """获取气候描述"""
        return self._climate.get_climate_description(impact)
    
    def _load_climate_data(self, path: str) -> List[float]:
        """加载气候数据"""
        return self._climate._load_climate_data(path)
    
    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """应用影响函数"""
        self._climate.apply_influences(target_name, context)
    
    # ===== 内部方法 =====
    
    def _on_time_advanced(self, data: Dict[str, Any]) -> None:
        """时间推进时的处理"""
        self.logger.debug(f"时间推进到: {data.get('new_time')}")
