"""
居民系统抽象接口
定义居民系统及相关组件的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple


class IResidentSharedInformationPool(ABC):
    """
    居民共享信息池抽象基类
    定义居民共享信息池的核心功能
    """

    @abstractmethod
    def __init__(self):
        """初始化共享信息池"""
        pass

    @abstractmethod
    def add_shared_info(self, key: str, value: Any, category: str) -> None:
        """
        添加共享信息
        
        Args:
            key: 信息键
            value: 信息值
            category: 信息类别（如'economic_status', 'social_network', 'environment_awareness'）
        """
        pass

    @abstractmethod
    def get_shared_info(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        获取共享信息
        
        Args:
            category: 信息类别，如果为None则返回所有类别
            
        Returns:
            Dict[str, Any]: 共享信息字典
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def shared_info(self) -> Dict[str, Dict[str, Any]]:
        """共享信息字典"""
        pass


class IResidentGroup(ABC):
    """
    居民群组抽象基类
    用于管理同一城镇的居民
    """

    @abstractmethod
    def __init__(self, town_name: str):
        """
        初始化居民群组
        
        Args:
            town_name: 城镇名称
        """
        pass

    @abstractmethod
    def add_resident(self, resident: Any) -> None:
        """
        添加居民到群组
        
        Args:
            resident: 居民对象
            
        Note:
            - 设置共享的 LLM 资源
            - 为每个居民创建独立的memory
            - 设置居民所属的群组
        """
        pass

    @abstractmethod
    def set_social_network(self, social_network: Any) -> None:
        """
        设置群组的社交网络
        
        Args:
            social_network: 社交网络对象
        """
        pass

    @abstractmethod
    def remove_resident(self, resident_id: int) -> None:
        """
        从群组中移除居民
        
        Args:
            resident_id: 居民ID
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def town_name(self) -> str:
        """城镇名称"""
        pass

    @property
    @abstractmethod
    def residents(self) -> Dict[int, Any]:
        """居民字典"""
        pass

    @property
    @abstractmethod
    def social_network(self) -> Optional[Any]:
        """社交网络对象"""
        pass


class IResident(ABC):
    """
    居民抽象基类
    定义居民的所有核心功能
    """

    @abstractmethod
    def __init__(
        self, 
        resident_id: int, 
        job_market: Any, 
        shared_pool: Any, 
        map: Any, 
        prompts_resident: Dict[str, Any], 
        actions_config: Dict[str, Any],
        window_size: int = 3,
        lightweight: bool = False
    ):
        """
        初始化居民
        
        Args:
            resident_id: 居民ID
            job_market: 就业市场对象
            shared_pool: 共享信息池
            map: 地图对象
            prompts_resident: 居民提示词配置
            actions_config: 行动配置
            window_size: 记忆窗口大小，默认为3
            lightweight: 如果为True，跳过BaseAgent的重量级初始化，稍后由ResidentGroup设置共享资源
        """
        pass

    @abstractmethod
    def set_group(self, group: Optional[Any]) -> None:
        """
        设置居民所属的群组
        
        Args:
            group: 群组对象
        """
        pass

    @abstractmethod
    def get_social_network(self) -> Optional[Any]:
        """
        通过群组获取社交网络
        
        Returns:
            Optional[Any]: 社交网络对象
        """
        pass

    @abstractmethod
    def employ(self, job: str, salary: Optional[float] = None) -> None:
        """
        居民就业
        
        Args:
            job: 工作名称
            salary: 工作收入，如果未指定则使用职业默认收入
            
        Note:
            如果是叛军职业，会输出特殊的日志信息
        """
        pass

    @abstractmethod
    def unemploy(self) -> None:
        """
        居民失业
        """
        pass

    @abstractmethod
    def update_system_message(self, basic_living_cost: float = 0, tax_rate: float = 0) -> None:
        """
        更新系统提示词，包含居民当前的状态信息
        
        Args:
            basic_living_cost: 基本生活成本
            tax_rate: 税率
        """
        pass

    @abstractmethod
    async def receive_information(self, message_content: str) -> Optional[str]:
        """
        接收信息（如政府政策、叛乱信息）
        
        Args:
            message_content: 信息内容
            
        Returns:
            Optional[str]: 可选的回应内容
        """
        pass

    @abstractmethod
    async def decide_action_by_llm(
        self, 
        tax_rate: float = 0, 
        basic_living_cost: float = 0, 
        climate_impact: float = 0, 
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        通过LLM决定居民的行动，并随机生成对政府的态度发言。同时更新满意度
        
        Args:
            tax_rate: 当前税率，默认为0
            basic_living_cost: 基本生活成本，默认为0
            climate_impact: 天气影响因子，默认为0
            **kwargs: 其他可选参数，会被添加到上下文信息中
            
        Returns:
            Optional[Dict[str, Any]]: 决策结果，包含选择、原因、发言等信息
        """
        pass

    @abstractmethod
    async def execute_decision(self, select: Any, *args, **kwargs) -> bool:
        """
        根据配置动态执行居民的决策
        
        Args:
            select: 选择的动作编号
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 是否执行成功
        """
        pass

    @abstractmethod
    def handle_work(
        self, 
        desired_job: Optional[str] = None, 
        min_salary: Optional[float] = None
    ) -> Any:
        """
        处理居民寻找工作或继续工作的逻辑
        
        Args:
            desired_job: 期望职业
            min_salary: 可接受的最低收入
            
        Returns:
            Any: True表示继续工作，字典表示求职信息
        """
        pass

    @abstractmethod
    async def generate_provocative_opinion(self, probability: float, speech: str) -> str:
        """
        处理居民是叛军时的特殊逻辑，生成煽动性言论
        
        Args:
            probability: 发言概率
            speech: 发言内容
            
        Returns:
            str: 生成的言论
        """
        pass

    @abstractmethod
    async def receive_and_decide_response(self, message: Dict[str, Any], year: int) -> None:
        """
        接收公共知识通知，由LLM决定是否发言
        
        Args:
            message: 消息字典
            year: 年份
        """
        pass

    @abstractmethod
    async def make_survey_request(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        通用方法：构建提示词，获取LLM响应并进行初步清理
        
        Args:
            prompt: 提示词
            
        Returns:
            Optional[Dict[str, Any]]: 清理后的响应数据
        """
        pass

    @abstractmethod
    async def update_knowledge_memory(self, prompt: str) -> None:
        """
        定期更新居民的知识记忆,专注于居民个人的知识和经历总结
        
        Args:
            prompt: 更新提示词
        """
        pass

    @abstractmethod
    def print_resident_status(self) -> None:
        """
        打印居民状态（用于调试）
        """
        pass

    @abstractmethod
    def handle_death(self) -> bool:
        """
        处理居民死亡的逻辑
        
        Returns:
            bool: 是否成功处理死亡
            
        Note:
            - 从就业市场和城镇中移除
            - 从社交网络中移除
        """
        pass

    @abstractmethod
    def update_resident_status(self, basic_living_cost: float) -> bool:
        """
        更新居民状况，包括健康状况和寿命
        
        Args:
            basic_living_cost: 基本生活成本
            
        Returns:
            bool: 如果居民死亡则返回True，否则返回False
        """
        pass

    @abstractmethod
    def update_health_index(self, basic_living_cost: float) -> None:
        """
        根据收入和满意度等因素更新健康状况
        
        Args:
            basic_living_cost: 基本生活成本
        """
        pass

    @abstractmethod
    def update_lifespan(self) -> bool:
        """
        检查健康状况并更新寿命
        
        Returns:
            bool: 如果寿命更新后为0，认为该居民死亡，返回True
        """
        pass

    @abstractmethod
    def get_random_direction_town(self, map: Any) -> Optional[str]:
        """
        随机选择一个相邻城市进行迁移
        
        Args:
            map: 地图对象
            
        Returns:
            Optional[str]: 目标城镇名称
        """
        pass

    @abstractmethod
    async def migrate_to_new_town(self, map: Any, update_job: bool = True) -> bool:
        """
        迁移到新城镇
        
        Args:
            map: 地图对象
            update_job: 是否更新职业，如果为False则保留原职业
            
        Returns:
            bool: 是否迁移成功
        """
        pass

    @abstractmethod
    def set_town(self, town_name: str, towns_manager: Any) -> None:
        """
        设置居民所在的城镇和towns_manager
        
        Args:
            town_name: 城镇名称
            towns_manager: 城镇管理器
        """
        pass

    @abstractmethod
    async def reset_experimental_state(self) -> None:
        """
        重置居民实验状态，主要用于删除记忆
        """
        pass

    @abstractmethod
    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        应用所有注册的影响函数到指定目标
        
        Args:
            target_name: 目标名称（如 'health_index', 'satisfaction'）
            context: 上下文字典，包含影响函数所需的所有数据
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def resident_id(self) -> int:
        """居民ID"""
        pass

    @property
    @abstractmethod
    def location(self) -> Optional[Tuple[int, int]]:
        """居民位置"""
        pass

    @property
    @abstractmethod
    def town(self) -> Optional[str]:
        """所在城镇"""
        pass

    @property
    @abstractmethod
    def employed(self) -> bool:
        """是否就业"""
        pass

    @property
    @abstractmethod
    def job(self) -> Optional[str]:
        """当前工作"""
        pass

    @property
    @abstractmethod
    def income(self) -> float:
        """收入"""
        pass

    @property
    @abstractmethod
    def satisfaction(self) -> float:
        """对政府的满意度（0到100）"""
        pass

    @property
    @abstractmethod
    def health_index(self) -> int:
        """居民的健康状况（0到10）"""
        pass

    @property
    @abstractmethod
    def lifespan(self) -> int:
        """居民的寿命"""
        pass

    @property
    @abstractmethod
    def personality(self) -> Optional[str]:
        """性格"""
        pass

    @property
    @abstractmethod
    def group(self) -> Optional[Any]:
        """所属群组"""
        pass
