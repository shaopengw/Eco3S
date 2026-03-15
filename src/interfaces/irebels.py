"""
叛军系统抽象接口
定义叛军系统及相关Agent的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple


class IOrdinaryRebel(ABC):
    """
    普通叛军抽象基类
    定义普通叛军的核心功能
    """

    @abstractmethod
    def __init__(self, agent_id: str, rebellion: Any, shared_pool: Any):
        """
        初始化普通叛军
        
        Args:
            agent_id: 叛军ID
            rebellion: 叛军对象
            shared_pool: 共享信息池
        """
        pass

    @abstractmethod
    def update_system_message(self) -> None:
        """
        更新系统提示词，包含当前的状态信息
        """
        pass

    @abstractmethod
    async def generate_opinion(self, towns_stats: List[Dict[str, Any]]) -> str:
        """
        生成一句关于叛军行动的意见
        
        Args:
            towns_stats: 各城镇的统计信息
            
        Returns:
            str: 生成的意见内容
        """
        pass

    @abstractmethod
    async def generate_and_share_opinion(self, salary: float) -> None:
        """
        从共享信息池中获取信息并发表看法，将看法放入共享信息池
        
        Args:
            salary: 薪资信息
        """
        pass

    @abstractmethod
    def analysis_towns_stats(self, towns_stats: List[Dict[str, Any]]) -> List[str]:
        """
        分析各城镇的力量对比
        
        Args:
            towns_stats: 各城镇的统计信息
            
        Returns:
            List[str]: 各城镇的分析结果
        """
        pass


class IRebelLeader(ABC):
    """
    叛军头子抽象基类
    定义叛军头子的核心功能
    """

    @abstractmethod
    def __init__(self, agent_id: str, rebellion: Any, shared_pool: Any):
        """
        初始化叛军头子
        
        Args:
            agent_id: 头子ID
            rebellion: 叛军对象
            shared_pool: 共享信息池
        """
        pass

    @abstractmethod
    def update_system_message(self) -> None:
        """
        更新系统提示词，包含当前的状态信息
        """
        pass

    @abstractmethod
    async def make_decision(self, summary: str, towns_stats: List[Dict[str, Any]]) -> str:
        """
        根据普通叛军的讨论作出决策
        
        Args:
            summary: 普通叛军的讨论报告
            towns_stats: 各城镇的统计信息
            
        Returns:
            str: 决策结果
        """
        pass

    @abstractmethod
    def analysis_towns_stats(self, towns_stats: List[Dict[str, Any]]) -> List[str]:
        """
        分析各城镇的力量对比
        
        Args:
            towns_stats: 各城镇的统计信息
            
        Returns:
            List[str]: 各城镇的分析结果
        """
        pass

    @abstractmethod
    def print_leader_status(self) -> None:
        """
        打印叛军头子的状态
        """
        pass


class IRebellion(ABC):
    """
    叛军系统抽象基类
    定义叛军系统的所有核心功能
    """

    @abstractmethod
    def __init__(
        self, 
        initial_strength: int, 
        initial_resources: float, 
        towns: Any, 
        rebels_prompt_path: str
    ):
        """
        初始化叛军系统
        
        Args:
            initial_strength: 初始力量
            initial_resources: 初始资源
            towns: 城镇对象
            rebels_prompt_path: 叛军提示词配置文件路径
        """
        pass

    @abstractmethod
    def maintain_status(self) -> None:
        """
        维持现状，获取基本收入
        
        Note:
            收入率为力量的1%
        """
        pass

    @abstractmethod
    def get_strength(self) -> int:
        """
        获取当前力量
        
        Returns:
            int: 当前力量
        """
        pass

    @abstractmethod
    def get_resources(self) -> float:
        """
        获取当前资源
        
        Returns:
            float: 当前资源
        """
        pass

    @abstractmethod
    def print_rebellion_status(self) -> None:
        """
        打印叛军状态（用于调试）
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def strength(self) -> int:
        """叛军力量"""
        pass

    @property
    @abstractmethod
    def resources(self) -> float:
        """叛军资源"""
        pass

    @property
    @abstractmethod
    def towns(self) -> Any:
        """城镇对象"""
        pass


class IRebelsSharedInformationPool(ABC):
    """
    叛军共享信息池抽象基类
    定义共享信息池的核心功能
    """

    @abstractmethod
    def __init__(self, max_discussions: int = 5):
        """
        初始化共享信息池
        
        Args:
            max_discussions: 最大讨论数量，默认为5
        """
        pass

    @abstractmethod
    async def add_discussion(self, discussion: str) -> bool:
        """
        添加讨论内容到共享信息池
        
        Args:
            discussion: 讨论内容
            
        Returns:
            bool: 是否成功添加（如果讨论已结束则返回False）
        """
        pass

    @abstractmethod
    async def get_latest_discussion(self) -> Optional[str]:
        """
        获取最新的讨论内容
        
        Returns:
            Optional[str]: 最新的讨论内容
        """
        pass

    @abstractmethod
    async def get_all_discussions(self) -> List[str]:
        """
        获取所有讨论内容
        
        Returns:
            List[str]: 所有讨论内容的列表
        """
        pass

    @abstractmethod
    async def clear_discussions(self) -> None:
        """
        清空所有讨论内容
        """
        pass


class IRebelInformationOfficer(ABC):
    """
    叛军信息整理官抽象基类
    定义信息整理官的核心功能
    """

    @abstractmethod
    def __init__(self, agent_id: str, rebellion: Any, shared_pool: Any):
        """
        初始化信息整理官
        
        Args:
            agent_id: 官员ID
            rebellion: 叛军对象
            shared_pool: 共享信息池
        """
        pass

    @abstractmethod
    async def summarize_discussions(self) -> str:
        """
        整理和总结所有讨论内容
        
        Returns:
            str: 总结后的报告
        """
        pass
