"""
地图插件实现 - 包装器模式
"""
from typing import Dict, Any, Optional
import numpy as np
from src.plugins import IMapPlugin, PluginContext
from src.interfaces import IMap
from src.environment.map import Map


class DefaultMapPlugin(IMapPlugin):
    """
    默认地图插件 - 包装现有 Map 类
    """
    
    def __init__(self, width: int = 100, 
                 height: int = 100,
                 data_file: str = 'config/default/towns_data.json'):
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
        self._map = None
        self._initialized = False
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建原始 Map 实例
        self._map = Map(
            width=self._width_param,
            height=self._height_param,
            data_file=self._data_file_param
        )
    
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
    
    # ===== IMap 接口属性 - 代理到内部 Map 实例 =====
    
    @property
    def width(self) -> int:
        return self._map.width
    
    @property
    def height(self) -> int:
        return self._map.height
    
    @property
    def grid(self) -> np.ndarray:
        return self._map.grid
    
    @property
    def river_grid(self) -> np.ndarray:
        return self._map.river_grid
    
    @river_grid.setter
    def river_grid(self, value: np.ndarray):
        self._map.river_grid = value
    
    @property
    def navigability(self) -> float:
        return self._map.navigability
    
    @navigability.setter
    def navigability(self, value: float):
        self._map.navigability = value
    
    @property
    def town_graph(self) -> dict:
        return self._map.town_graph
    
    @town_graph.setter
    def town_graph(self, value: dict):
        self._map.town_graph = value
    
    @property
    def town_dict(self) -> dict:
        return self._map.town_dict
    
    @town_dict.setter
    def town_dict(self, value: dict):
        self._map.town_dict = value
    
    @property
    def terrain_ruggedness(self) -> np.ndarray:
        return self._map.terrain_ruggedness
    
    # ===== IMap 接口方法 - 代理到内部 Map 实例 =====
    
    def initialize_map(self) -> None:
        """初始化地图"""
        self._map.initialize_map()
        
        # 发布事件
        self.context.event_bus.publish('map_initialized', {
            'width': self._map.width,
            'height': self._map.height
        })
    
    def get_distance(self, pos1: tuple, pos2: tuple) -> float:
        """计算两点距离"""
        return self._map.get_distance(pos1, pos2)
    
    def load_town_data(self, data_file: str) -> None:
        """加载城镇数据"""
        self._map.load_town_data(data_file)
    
    def initialize_river(self) -> None:
        """初始化运河"""
        self._map.initialize_river()
    
    def initialize_town_graph(self) -> None:
        """初始化城镇图"""
        self._map.initialize_town_graph()
    
    def get_connected_towns(self, town_name: str) -> list:
        """获取与指定城镇连接的城镇"""
        return self._map.get_connected_towns(town_name)
    
    def get_river_towns(self) -> list:
        """获取沿河城镇"""
        return self._map.get_river_towns()
    
    def get_non_river_towns(self) -> list:
        """获取非沿河城镇"""
        return self._map.get_non_river_towns()
    
    def get_navigability(self) -> float:
        """获取运河通航能力"""
        return self._map.get_navigability()
    
    def update_river_condition(self, maintenance_level: float) -> None:
        """更新运河状况"""
        self._map.update_river_condition(maintenance_level)
    
    def decay_river_condition_naturally(self, climate_impact_factor=0) -> None:
        """自然衰减运河状况"""
        self._map.decay_river_condition_naturally(climate_impact_factor)
    
    def get_terrain_ruggedness(self, location: tuple) -> float:
        """获取指定位置的地形崎岖度"""
        return self._map.get_terrain_ruggedness(location)
    
    def generate_random_location(self, town_name: str, sigma: float = 2.0) -> Optional[tuple]:
        """生成随机位置"""
        return self._map.generate_random_location(town_name, sigma)
    
    def longitude_to_x(self, longitude: float) -> int:
        """经度转换为 x 坐标"""
        return self._map.longitude_to_x(longitude)
    
    def latitude_to_y(self, latitude: float) -> int:
        """纬度转换为 y 坐标"""
        return self._map.latitude_to_y(latitude)
    
    def visualize_map(self) -> None:
        """可视化地图"""
        self._map.visualize_map()
    
    def print_map(self) -> None:
        """打印地图"""
        self._map.print_map()
    
    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """应用影响函数"""
        self._map.apply_influences(target_name, context)
    
    # ===== 内部方法 =====
    
    def _on_simulation_start(self, data: Dict[str, Any]) -> None:
        """模拟开始时的处理"""
        self.logger.info("收到 simulation_start 事件")

