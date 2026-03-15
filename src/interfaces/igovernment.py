"""
政府系统抽象接口
定义政府系统及相关Agent的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple


class IOrdinaryGovernmentAgent(ABC):
    """
    普通政府官员抽象基类
    定义普通政府官员的核心功能
    """

    @abstractmethod
    def __init__(self, agent_id: str, government: Any, shared_pool: Any):
        """
        初始化普通政府官员
        
        Args:
            agent_id: 官员ID
            government: 政府对象
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
    def get_current_situation_prompt(self, maintain_employment_cost: float) -> str:
        """
        获取当前形势的提示词
        
        Args:
            maintain_employment_cost: 维持就业成本
            
        Returns:
            str: 当前形势的描述
        """
        pass

    @abstractmethod
    async def generate_opinion(self, salary: float) -> str:
        """
        生成一句关于政治决策的意见
        
        Args:
            salary: 薪资信息
            
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
    async def make_decision(self, summary: str, salary: float) -> str:
        """
        根据讨论总结作出决策（用于非独裁模式）
        
        Args:
            summary: 讨论总结或高级官员的总结发言
            salary: 薪资信息
            
        Returns:
            str: 决策结果
        """
        pass


class IHighRankingGovernmentAgent(ABC):
    """
    高级政府官员抽象基类（决策者）
    定义高级政府官员的核心功能
    """

    @abstractmethod
    def __init__(self, agent_id: str, government: Any, shared_pool: Any):
        """
        初始化高级政府官员
        
        Args:
            agent_id: 官员ID
            government: 政府对象
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
    async def summarize_discussion_for_voting(self, summary: str, salary: float) -> str:
        """
        高级官员总结讨论，为后续投票提供参考（用于非独裁模式）
        
        Args:
            summary: 信息整理官的总结
            salary: 薪资信息
            
        Returns:
            str: 高级官员的总结发言
        """
        pass

    @abstractmethod
    async def make_decision(self, summary: str, salary: float) -> str:
        """
        根据普通政府官员的讨论作出决策
        
        Args:
            summary: 讨论总结
            salary: 薪资信息
            
        Returns:
            str: 决策结果
        """
        pass

    @abstractmethod
    def print_agent_status(self) -> None:
        """
        打印高级政府官员的状态
        """
        pass


class IGovernment(ABC):
    """
    政府系统抽象基类
    定义政府系统的所有核心功能
    """

    @abstractmethod
    def __init__(
        self, 
        map: Any, 
        towns: Any, 
        military_strength: int, 
        initial_budget: float, 
        time: Any, 
        transport_economy: Optional[Any], 
        government_prompt_path: str
    ):
        """
        初始化政府系统
        
        Args:
            map: 地图对象
            towns: 城镇对象
            military_strength: 军事力量
            initial_budget: 初始预算
            time: 时间对象
            transport_economy: 运输经济模型引用（可选）
            government_prompt_path: 政府提示词配置文件路径
        """
        pass

    @abstractmethod
    def handle_public_budget(
        self, 
        budget_allocation: float, 
        salary: float, 
        job_total_count: int, 
        residents: Dict[int, Any]
    ) -> None:
        """
        处理公共预算决策
        
        Args:
            budget_allocation: 预算分配金额
            salary: 薪资
            job_total_count: 总岗位数
            residents: 居民字典
            
        Note:
            - 如果预算分配大于维持就业成本，增加就业岗位
            - 如果小于维持就业成本，减少就业岗位
        """
        pass

    @abstractmethod
    def maintain_canal(self, maintenance_investment: float) -> bool:
        """
        维护运河
        
        Args:
            maintenance_investment: 投资金额
            
        Returns:
            bool: 是否维护成功
            
        Note:
            - 改善运河状态（运河通航能力）
            - 提供就业机会
            - 减少政府预算
        """
        pass

    @abstractmethod
    def handle_transport_decision(self, transport_ratio: float) -> bool:
        """
        处理运输决策
        
        Args:
            transport_ratio: 河运投入比例（0-1）
            
        Returns:
            bool: 是否决策成功
        """
        pass

    @abstractmethod
    def support_military(self, budget_allocation: float) -> None:
        """
        军需拨款
        
        Args:
            budget_allocation: 分配给军事力量的预算
            
        Note:
            - 增加军事力量
            - 创建官员及士兵岗位
        """
        pass

    @abstractmethod
    def get_budget(self) -> float:
        """
        获取当前预算
        
        Returns:
            float: 当前预算
        """
        pass

    @abstractmethod
    def get_military_strength(self) -> int:
        """
        获取当前军事力量
        
        Returns:
            int: 当前军事力量
        """
        pass

    @abstractmethod
    def adjust_tax_rate(self, adjustment: float) -> float:
        """
        调整税率并更新居民满意度
        
        Args:
            adjustment: 税率调整值（正数表示增加，负数表示减少）
            
        Returns:
            float: 调整后的税率
            
        Note:
            税率限制在 0% 到 50% 之间
        """
        pass

    @abstractmethod
    def get_tax_rate(self) -> float:
        """
        获取当前税率
        
        Returns:
            float: 当前税率
        """
        pass

    @abstractmethod
    def print_government_status(self) -> None:
        """
        打印政府状态（用于调试）
        """
        pass

    @abstractmethod
    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        应用所有注册的影响函数到指定目标
        
        Args:
            target_name: 目标名称（如 'tax_rate'）
            context: 上下文字典，包含影响函数所需的所有数据
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def map(self) -> Any:
        """地图对象"""
        pass

    @property
    @abstractmethod
    def towns(self) -> Any:
        """城镇对象"""
        pass

    @property
    @abstractmethod
    def budget(self) -> float:
        """当前预算"""
        pass

    @property
    @abstractmethod
    def military_strength(self) -> int:
        """军事力量"""
        pass

    @property
    @abstractmethod
    def tax_rate(self) -> float:
        """税率"""
        pass

    @property
    @abstractmethod
    def transport_economy(self) -> Optional[Any]:
        """运输经济模型引用"""
        pass


class IGovernmentSharedInformationPool(ABC):
    """
    政府共享信息池抽象基类
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


class IInformationOfficer(ABC):
    """
    信息整理官抽象基类
    定义信息整理官的核心功能
    """

    @abstractmethod
    def __init__(self, agent_id: str, government: Any, shared_pool: Any):
        """
        初始化信息整理官
        
        Args:
            agent_id: 官员ID
            government: 政府对象
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
