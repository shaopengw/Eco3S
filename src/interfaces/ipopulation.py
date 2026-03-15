"""
人口系统抽象接口
定义人口系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict


class IPopulation(ABC):
    """
    人口系统抽象基类
    定义人口系统的所有核心功能，包括人口增长、出生率管理和人口统计
    """

    @abstractmethod
    def __init__(self, initial_population: int, birth_rate: float = 0.01,
                 influence_registry: Optional[Any] = None):
        """
        初始化人口类
        
        Args:
            initial_population: 初始人口数量
            birth_rate: 出生率，默认为0.01（1%）
            influence_registry: 影响函数注册表（可选）
        """
        pass

    @abstractmethod
    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """
        应用影响函数到指定目标
        
        Args:
            target_name: 目标名称（如'birth_rate'等）
            context: 上下文数据字典，包含计算所需的所有数据
        """
        pass

    @abstractmethod
    def update_birth_rate(self, satisfaction: float) -> None:
        """
        根据居民平均满意度更新出生率
        
        Args:
            satisfaction: 居民平均满意度（0-100）
            
        Note:
            - 满意度 >= 80: 出生率上升，每超过80一点，出生率增加0.2%，最高0.5
            - 满意度 <= 50: 出生率下降，每低于50一点，出生率降低0.1%，最低0.01
            - 满意度在50-80之间: 保持基础出生率
            - 可通过影响函数系统自定义计算逻辑
        """
        pass

    @abstractmethod
    def birth(self, num: int) -> int:
        """
        人口出生
        
        Args:
            num: 出生人数
            
        Returns:
            int: 更新后的人口数量
        """
        pass

    @abstractmethod
    def death(self) -> None:
        """
        人口死亡（减少1人）
        
        Note:
            如果人口已为0，会输出警告信息
        """
        pass

    @abstractmethod
    def get_population(self) -> int:
        """
        获取当前人口数量
        
        Returns:
            int: 当前人口数量
        """
        pass

    @abstractmethod
    def print_population_status(self) -> None:
        """
        打印人口状态（用于调试）
        输出当前人口数量和出生率
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def population(self) -> int:
        """当前人口数量"""
        pass

    @property
    @abstractmethod
    def birth_rate(self) -> float:
        """出生率"""
        pass
