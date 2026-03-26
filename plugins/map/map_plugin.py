"""地图插件实现 - 包装器模式"""

from typing import Dict, Any, Optional
from src.plugins import IMapPlugin, PluginContext
from src.influences import InfluenceRegistry
from src.environment.map import Map


class DefaultMapPlugin(IMapPlugin):
    """
    默认地图插件 - 包装现有 Map 类
    """
    
    def __init__(
        self,
        width: int = 100,
        height: int = 100,
        data_file: str = 'config/default/towns_data.json',
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        """
        初始化地图插件
        
        Args:
            width: 地图宽度
            height: 地图高度
            data_file: 城镇数据文件路径
        """
        super().__init__()
        
        # 保存参数
        self._width_param = width
        self._height_param = height
        self._data_file_param = data_file
        self._influence_registry_param = influence_registry
        self._map = None
        self._initialized = False
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 允许从运行配置覆盖地图参数
        sim_cfg = (context.config or {}).get('simulation', {})
        if isinstance(sim_cfg, dict):
            if isinstance(sim_cfg.get('map_width'), int):
                self._width_param = int(sim_cfg['map_width'])
            if isinstance(sim_cfg.get('map_height'), int):
                self._height_param = int(sim_cfg['map_height'])

        data_cfg = (context.config or {}).get('data', {})
        if isinstance(data_cfg, dict):
            towns_path = data_cfg.get('towns_data_path')
            if isinstance(towns_path, str) and towns_path.strip():
                self._data_file_param = towns_path.strip()
        
        # 创建原始 Map 实例
        self._map = Map(
            width=self._width_param,
            height=self._height_param,
            data_file=self._data_file_param,
            influence_registry=self._influence_registry_param,
        )
        self._service = self._map
        self._influence_registry = getattr(self._map, "_influence_registry", None) or self._influence_registry_param
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultMapPlugin 正在加载 ({self._map.width}x{self._map.height})")
        
        # 订阅事件
        self.context.event_bus.subscribe('simulation_start', self._on_simulation_start)
        
        self._initialized = True
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultMapPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('simulation_start', self._on_simulation_start)
        
        self._initialized = False
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultMap",
            "version": "1.0.0",
            "description": "默认地图实现插件（包装 Map 类）",
            "author": "AgentWorld Team",
            "dependencies": []
        }
    
    def initialize_map(self) -> None:
        """初始化地图"""
        self._map.initialize_map()
        
        # 发布事件
        self.context.event_bus.publish('map_initialized', {
            'width': self._map.width,
            'height': self._map.height
        })
    
    # ===== 内部方法 =====
    
    def _on_simulation_start(self, data: Dict[str, Any]) -> None:
        """模拟开始时的处理"""
        self.logger.info("收到 simulation_start 事件")

