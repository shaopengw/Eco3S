"""
外生变量数据提供者抽象接口
定义按时间步从数据文件读取外生变量（exogenous variable）的核心功能。

外生变量指因果链中「只作为 cause、从不作为 effect」的根驱动参数，
其每个时间步的取值由预先编排好的数据文件提供，而非仿真内部计算，
从而让下游因果链产生更明显、更可控的可观察变化。
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class IExogenousDataProvider(ABC):
    """
    外生变量数据提供者抽象基类。

    数据文件为多列带表头 CSV：每一列是一个外生变量（列名即变量 key），
    每一行对应一个时间步。
    """

    @abstractmethod
    def __init__(self, data_path: str):
        """
        初始化外生变量数据提供者。

        Args:
            data_path: 外生变量数据文件（多列带表头 CSV）路径
        """
        pass

    @abstractmethod
    def get_current_values(self, step_index: int) -> Dict[str, float]:
        """
        获取指定时间步上所有外生变量的取值。

        Args:
            step_index: 时间步索引（从 0 开始）

        Returns:
            Dict[str, float]: {变量名: 取值}；无数据时返回空字典。

        Note:
            - step_index 越界时返回末值（保持最后一步取值），无数据时为空。
        """
        pass

    @abstractmethod
    def get_value(self, key: str, step_index: int) -> float:
        """
        获取单个外生变量在指定时间步的取值。

        Args:
            key: 变量名（CSV 列名）
            step_index: 时间步索引（从 0 开始）

        Returns:
            float: 变量取值；变量不存在时返回 0.0。
        """
        pass

    @property
    @abstractmethod
    def keys(self) -> List[str]:
        """所有外生变量名（CSV 列名）列表。"""
        pass

