"""
运输经济系统抽象接口
定义运输经济系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict


class ITransportEconomy(ABC):
    """
    运输经济系统抽象基类
    定义运输经济系统的所有核心功能，包括运输成本计算、维护成本计算和价格管理
    """

    @abstractmethod
    def __init__(self, transport_cost: float, transport_task: float, maintenance_cost_base: float = 100,
                 influence_registry: Optional[Any] = None):
        """
        初始化运输经济系统
        
        Args:
            transport_cost: 基础运输成本
            transport_task: 年度运输任务量（吨）
            maintenance_cost_base: 基础维护成本，默认为100
            influence_registry: 影响函数注册表（可选）
        """
        pass

    @abstractmethod
    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """
        应用影响函数到指定目标
        
        Args:
            target_name: 目标名称（如'river_price', 'maintenance_cost'等）
            context: 上下文数据字典，包含计算所需的所有数据
        """
        pass

    @abstractmethod
    def calculate_river_price(self, navigability: float) -> float:
        """
        计算河运价格
        
        Args:
            navigability: 通航能力（0-1）
            
        Returns:
            float: 河运价格
            
        Note:
            - 通航值越低价格越高
            - 价格最低为基础价格
            - 默认公式: transport_cost * (2 - navigability)
            - 可通过影响函数系统自定义计算逻辑
        """
        pass

    @abstractmethod
    def calculate_maintenance_cost(self, navigability: float, exponent: int = 3) -> float:
        """
        计算河运维护成本
        
        Args:
            navigability: 当前通航能力（0-1）
            exponent: 指数，默认为3
            
        Returns:
            float: 维护成本
            
        Note:
            - 通航能力越低，维护成本以指数形式增加
            - 默认公式: maintenance_cost_base * ((2 - navigability) ^ exponent)
            - 可通过影响函数系统自定义计算逻辑
        """
        pass

    @abstractmethod
    def calculate_total_transport_cost(self, river_ratio: float) -> float:
        """
        计算总运输成本
        
        Args:
            river_ratio: 河运比例（0-1）
            
        Returns:
            float: 总运输成本
            
        Note:
            - 总成本 = 河运成本 + 海运成本
            - 默认公式: river_price * river_ratio * transport_task + sea_price * (1 - river_ratio) * transport_task
            - 可通过影响函数系统自定义计算逻辑
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def transport_cost(self) -> float:
        """基础运输成本"""
        pass

    @property
    @abstractmethod
    def transport_task(self) -> float:
        """年度运输任务量（吨）"""
        pass

    @property
    @abstractmethod
    def maintenance_cost_base(self) -> float:
        """基础维护成本"""
        pass

    @property
    @abstractmethod
    def river_price(self) -> float:
        """当前河运价格"""
        pass

    @property
    @abstractmethod
    def sea_price(self) -> float:
        """海运价格（约为基础运输成本的1/5）"""
        pass
