"""
地图模块抽象接口
定义地图系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from src.influences import InfluenceRegistry


class IMap(ABC):
    """
    地图模块抽象基类
    定义地图系统的所有核心功能，包括地图初始化、城市管理、运河系统和地形处理
    """

    @abstractmethod
    def __init__(self, width: int, height: int, data_file: str = 'config/default/towns_data.json', 
                 influence_registry: Optional['InfluenceRegistry'] = None):
        """
        初始化地图
        
        Args:
            width: 地图宽度
            height: 地图高度
            data_file: 城市数据文件路径
            influence_registry: 影响函数注册中心（可选）
        """
        pass

    @abstractmethod
    def load_town_data(self, data_file: str) -> None:
        """
        从JSON文件加载城市数据和地图边界
        
        Args:
            data_file: JSON文件路径
            
        Raises:
            Exception: 当文件加载失败时抛出异常
        """
        pass

    @abstractmethod
    def longitude_to_x(self, longitude: float) -> int:
        """
        将经度转换为地图x坐标
        
        Args:
            longitude: 经度值
            
        Returns:
            int: 对应的x坐标
        """
        pass

    @abstractmethod
    def latitude_to_y(self, latitude: float) -> int:
        """
        将纬度转换为地图y坐标（纬度越高，y坐标越小，即北在上）
        
        Args:
            latitude: 纬度值
            
        Returns:
            int: 对应的y坐标
        """
        pass

    @abstractmethod
    def initialize_river(self) -> None:
        """
        初始化所有运河路线
        根据配置文件中的运河数据，在地图网格上标记运河位置
        """
        pass

    @abstractmethod
    def initialize_town_graph(self, max_distance: float = 20) -> None:
        """
        初始化城市图，通过计算城市间距离来建立连接
        
        Args:
            max_distance: 最大连接距离，超过此距离的城市不会建立连接
        """
        pass

    @abstractmethod
    def get_connected_towns(self, town_name: str) -> Optional[List[str]]:
        """
        获取与指定城市相连的所有城市
        
        Args:
            town_name: 城市名称
            
        Returns:
            Optional[List[str]]: 相连城市名称列表，如果城市不存在则返回None
        """
        pass

    @abstractmethod
    def visualize_map(self, output_file: str = 'experiment_dataset\\plot_results\\map_visualization.png') -> None:
        """
        可视化地图，显示沿河区域、市场城镇和地形崎岖指数
        
        Args:
            output_file: 输出文件路径
        """
        pass

    @abstractmethod
    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        应用所有注册的影响函数到指定目标
        
        Args:
            target_name: 目标名称（如 'canal', 'navigability'）
            context: 上下文字典，包含影响函数所需的所有数据
        """
        pass

    @abstractmethod
    def update_river_condition(self, maintenance_ratio: float) -> None:
        """
        根据政府维护决策更新运河状态
        
        Args:
            maintenance_ratio: 维护投入比例
                
        Note:
            现在通过影响函数系统计算更新，如果没有配置影响函数则使用默认公式：
            - 大于等于1：每增加一倍通航能力额外增加0.1
            - 小于1：每减少一倍通航能力减少0.2
            通航能力会被限制在0到1之间
            当通航能力低于0.2时会输出警告
        """
        pass

    @abstractmethod
    def decay_river_condition_naturally(self, climate_impact_factor: float = 0) -> float:
        """
        每年根据自然衰减和气候影响自然更新运河状态
        
        Args:
            climate_impact_factor: 气候影响因子，范围[0,1]，表示气候对运河的负面影响
            
        Returns:
            float: 当前运河通航能力
            
        Note:
            现在通过影响函数系统计算更新，如果没有配置影响函数则使用默认公式：
            自然衰减率为10%，气候影响系数为0.6
        """
        pass

    @abstractmethod
    def get_navigability(self) -> float:
        """
        获取当前运河通航能力
        
        Returns:
            float: 通航能力值（0-1之间的浮点数）
        """
        pass

    @abstractmethod
    def get_terrain_ruggedness(self, location: Tuple[int, int]) -> float:
        """
        获取某个位置的地形崎岖指数
        
        Args:
            location: 位置的坐标 (x, y)
            
        Returns:
            float: 地形崎岖指数（0到1之间的值）
        """
        pass

    @abstractmethod
    def get_river_towns(self) -> List[Tuple[int, int]]:
        """
        获取所有运河城镇的位置
        
        Returns:
            List[Tuple[int, int]]: 运河城镇的位置列表
        """
        pass

    @abstractmethod
    def get_non_river_towns(self) -> List[Tuple[int, int]]:
        """
        获取所有非沿河城市的位置
        
        Returns:
            List[Tuple[int, int]]: 非沿河城市的位置列表
        """
        pass

    @abstractmethod
    def print_map(self) -> None:
        """
        打印地图信息（用于调试）
        输出river_grid、town_graph和town_dict的内容
        """
        pass

    @abstractmethod
    def initialize_map(self) -> None:
        """
        初始化地图
        执行initialize_river和initialize_town_graph两个初始化步骤
        """
        pass

    @abstractmethod
    def generate_random_location(self, town_name: str, sigma: float = 2.0) -> Optional[Tuple[int, int]]:
        """
        为指定城市生成一个随机位置（基于正态分布）
        
        Args:
            town_name: 城市名称
            sigma: 正态分布标准差，默认2.0
            
        Returns:
            Optional[Tuple[int, int]]: (x, y) 坐标元组，如果城市不存在或生成失败则返回None
            
        Note:
            生成的位置围绕城市中心呈正态分布
            会确保位置在地图范围内
            最多尝试100次，失败则返回城市中心点
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def width(self) -> int:
        """地图宽度"""
        pass

    @property
    @abstractmethod
    def height(self) -> int:
        """地图高度"""
        pass

    @property
    @abstractmethod
    def grid(self) -> np.ndarray:
        """地图网格"""
        pass

    @property
    @abstractmethod
    def river_grid(self) -> np.ndarray:
        """运河网格"""
        pass

    @property
    @abstractmethod
    def navigability(self) -> float:
        """运河通航能力"""
        pass

    @property
    @abstractmethod
    def town_graph(self) -> Dict[str, List[str]]:
        """城市图（邻接表形式）"""
        pass

    @property
    @abstractmethod
    def town_dict(self) -> Dict[str, Dict[str, Any]]:
        """城市信息字典"""
        pass

    @property
    @abstractmethod
    def terrain_ruggedness(self) -> np.ndarray:
        """地形崎岖度矩阵"""
        pass
