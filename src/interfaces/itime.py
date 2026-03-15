"""
时间系统抽象接口
定义时间系统的核心功能接口
"""

from abc import ABC, abstractmethod


class ITime(ABC):
    """
    时间系统抽象基类
    定义时间系统的所有核心功能，包括时间推进、时间检查和时间重置
    """

    @abstractmethod
    def __init__(self, start_time: int, total_steps: int):
        """
        初始化时间类
        
        Args:
            start_time: 模拟的起始时间
            total_steps: 模拟的总时间步数
        """
        pass

    @abstractmethod
    def step(self) -> None:
        """
        推进一个时间步
        将当前时间增加1
        """
        pass

    @abstractmethod
    def is_end(self) -> bool:
        """
        检查是否到达模拟结束时间
        
        Returns:
            bool: 是否到达结束时间
        """
        pass

    @abstractmethod
    def get_elapsed_time_steps(self) -> int:
        """
        获取已经过去的时间步数
        
        Returns:
            int: 已经过去的时间步数
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        重置时间到起始时间
        """
        pass

    @abstractmethod
    def update_total_steps(self, new_total_steps: int) -> None:
        """
        更新总时间步数，并相应调整结束时间
        
        Args:
            new_total_steps: 新的总时间步数
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def start_time(self) -> int:
        """起始时间"""
        pass

    @property
    @abstractmethod
    def total_steps(self) -> int:
        """总时间步数"""
        pass

    @property
    @abstractmethod
    def end_time(self) -> int:
        """结束时间"""
        pass

    @property
    @abstractmethod
    def current_time(self) -> int:
        """当前时间"""
        pass
