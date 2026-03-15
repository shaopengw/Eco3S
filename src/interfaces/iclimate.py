"""
气候系统抽象接口
定义气候系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict


class IClimateSystem(ABC):
    """
    气候系统抽象基类
    定义气候系统的所有核心功能，包括气候数据加载和气候影响度计算
    """

    @abstractmethod
    def __init__(self, climate_data_path: str, influence_registry: Optional[Any] = None):
        """
        初始化气候系统
        
        Args:
            climate_data_path: climate.csv文件路径
            influence_registry: 影响函数注册表（可选）
        """
        pass

    @abstractmethod
    def _load_climate_data(self, path: str) -> List[float]:
        """
        加载气候数据
        
        Args:
            path: 数据文件路径
            
        Returns:
            List[float]: 气候影响度列表
            
        Note:
            - 处理NaN值时用0替代
            - 加载失败时返回空列表
        """
        pass

    @abstractmethod
    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """
        应用影响函数到指定目标
        
        Args:
            target_name: 目标名称（如'climate_impact'等）
            context: 上下文数据字典，包含计算所需的所有数据
        """
        pass

    @abstractmethod
    def get_current_impact(self, current_year: int = None, start_year: int = None) -> float:
        """
        获取当前年份的气候影响度
        
        Args:
            current_year: 当前年份
            start_year: 起始年份
            
        Returns:
            float: 气候影响度（绝对值）
            
        Note:
            - 如果数据不存在或年份超出范围，返回0.0
            - 返回值为气候数据的绝对值
            - 可通过影响函数系统对原始数据进行调整或增强
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def climate_data(self) -> List[float]:
        """气候数据列表"""
        pass

    @property
    @abstractmethod
    def climate_impact_threshold(self) -> float:
        """影响运河状态的阈值"""
        pass
