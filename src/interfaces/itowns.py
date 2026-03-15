"""
城镇系统抽象接口
定义城镇系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


class ITowns(ABC):
    """
    城镇系统抽象基类
    定义城镇系统的所有核心功能，包括城镇管理、居民分配和就业市场管理
    """

    @abstractmethod
    def __init__(self, map: Any, initial_population: int = 10, job_market_config_path: Optional[Path] = None):
        """
        初始化城镇系统
        
        Args:
            map: 地图对象
            initial_population: 初始人口数量，默认为10
            job_market_config_path: 就业市场配置文件路径
        """
        pass

    @abstractmethod
    def _create_town_dict(self) -> Dict[str, Any]:
        """
        创建一个新的城镇字典结构
        
        Returns:
            Dict[str, Any]: 城镇字典，包含info、residents、resident_group、job_market等字段
        """
        pass

    @abstractmethod
    def initialize_towns(self, map: Any, initial_population: int, job_market_config_path: Optional[Path] = None) -> None:
        """
        初始化所有城镇信息
        
        Args:
            map: 地图对象
            initial_population: 初始人口数量
            job_market_config_path: 就业市场配置文件路径
            
        Note:
            - 检查城镇坐标是否在有效范围内
            - 将初始人口均匀分配到各个城镇
            - 为每个城镇初始化就业市场
        """
        pass

    @abstractmethod
    def initialize_resident_groups(self, residents: Dict[int, Any]) -> None:
        """
        根据居民的town属性初始化居民群组并分配工作
        
        Args:
            residents: 居民字典，key为居民ID，value为居民对象
            
        Note:
            - 按城镇分组居民
            - 批量处理每个城镇的居民
            - 批量分配工作
        """
        pass

    @abstractmethod
    def add_resident(self, resident: Any, town_name: str) -> None:
        """
        添加居民到指定城镇
        
        Args:
            resident: 居民对象
            town_name: 城镇名称
        """
        pass

    @abstractmethod
    def batch_add_residents(self, residents_list: List[Any], town_name: str) -> None:
        """
        批量添加居民到指定城镇
        
        Args:
            residents_list: 居民对象列表
            town_name: 城镇名称
        """
        pass

    @abstractmethod
    def get_nearest_town(self, location: Tuple[int, int]) -> Optional[str]:
        """
        获取最近的城镇名称
        
        Args:
            location: 位置坐标 (x, y)
            
        Returns:
            Optional[str]: 最近的城镇名称
        """
        pass

    @abstractmethod
    def get_town_residents(self, town_name: str) -> Dict[int, Any]:
        """
        获取指定城镇的所有居民
        
        Args:
            town_name: 城镇名称
            
        Returns:
            Dict[int, Any]: 居民字典，key为居民ID，value为居民对象
        """
        pass

    @abstractmethod
    def get_hometown_group(self, town_name: str) -> Optional[str]:
        """
        获取指定城镇的同乡群组ID
        
        Args:
            town_name: 城镇名称
            
        Returns:
            Optional[str]: 同乡群组ID
        """
        pass

    @abstractmethod
    def update_hometown_group(self, town_name: str, group_id: str) -> None:
        """
        更新城镇的同乡群组ID
        
        Args:
            town_name: 城镇名称
            group_id: 群组ID
        """
        pass

    @abstractmethod
    def get_town_job_market(self, town_name: str) -> Any:
        """
        获取指定城镇的就业市场
        
        Args:
            town_name: 城镇名称
            
        Returns:
            Any: 就业市场对象
        """
        pass

    @abstractmethod
    def print_towns_status(self) -> None:
        """
        打印所有城镇状态
        包括位置、类型、居民数量和就业市场状态
        """
        pass

    @abstractmethod
    def print_towns(self) -> None:
        """
        打印所有城镇状态的摘要
        统计沿河城镇和非沿河城镇的总居民数量
        """
        pass

    @abstractmethod
    def remove_jobs_across_towns(self, total_jobs_to_remove: int, residents: Dict[int, Any]) -> None:
        """
        将要减少的岗位均匀分布给所有城镇
        
        Args:
            total_jobs_to_remove: 需要减少的总岗位数量
            residents: 居民字典
            
        Note:
            - 计算每个城镇需要减少的岗位数量
            - 将剩余岗位分配给第一个城镇
        """
        pass

    @abstractmethod
    def process_town_job_requests(self, town_job_requests: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Tuple[List[int], float]]:
        """
        处理城镇的求职信息
        
        Args:
            town_job_requests: 字典，键为城镇名称，值为该城镇的求职请求列表
            
        Returns:
            Dict[str, Tuple[List[int], float]]: 处理结果，键为城镇名称，值为(录用居民ID列表, 总支出)
        """
        pass

    @abstractmethod
    def remove_resident_in_town(self, resident_id: int, town_name: str, job_type: Optional[str] = None) -> bool:
        """
        处理居民删除逻辑
        
        Args:
            resident_id: 居民ID
            town_name: 城镇名称
            job_type: 工作类型（可选）
            
        Returns:
            bool: 是否成功删除
            
        Note:
            - 从就业市场中移除
            - 从城镇居民列表中移除
            - 从居民群组中移除
        """
        pass

    @abstractmethod
    def adjust_job_market(self, change_rate: float, residents: Dict[int, Any]) -> None:
        """
        更新所有城镇的就业市场
        
        Args:
            change_rate: 运河状态的变化率（-1到1之间的值）
            residents: 居民字典
        """
        pass

    @abstractmethod
    def add_jobs(self, add_job_amount: int, job_name: Optional[str] = None, 
                 town_type: Optional[str] = None, use_random_assignment: bool = True) -> None:
        """
        通用的岗位增加方法，支持多种场景
        
        Args:
            add_job_amount: 需要增加的总岗位数量
            job_name: 指定的工作岗位名称（可选）
            town_type: 城镇类型过滤条件（可选，如'canal'或'non_canal'；不指定则应用于所有城镇）
            use_random_assignment: 是否使用随机岗位分配方式（默认True）
                - True: 使用 job_market.add_random_jobs() 随机增加岗位
                - False: 使用 job_market.add_job() 增加指定岗位
            
        Note:
            - 如果岗位数小于城镇数，随机选取岗位数个城镇增加工作
            - 否则平均分配给所有符合条件的城镇
            - 剩余岗位分配给第一个城镇
            
        Examples:
            # 在所有城镇随机增加100个岗位
            add_jobs(100)
            
            # 在所有城镇增加100个"官员及士兵"岗位
            add_jobs(100, job_name="官员及士兵")
            
            # 在沿河城镇增加50个"河运工人"岗位（不使用随机分配）
            add_jobs(50, job_name="河运工人", town_type="canal", use_random_assignment=False)
        """
        pass

    @abstractmethod
    def add_jobs_across_towns(self, add_job_amount: int, specific_job: Optional[str] = None) -> None:
        """
        将要增加的岗位均匀分布给所有城镇
        
        .. deprecated::
            使用 add_jobs() 替代此方法
            
        Args:
            add_job_amount: 需要增加的总岗位数量
            specific_job: 指定的工作类型（可选）
            
        Note:
            - 如果岗位数小于城镇数，随机选取岗位数个城镇增加工作
            - 否则平均分配给所有城镇
        """
        pass

    @abstractmethod
    def add_specific_job(self, add_job_amount: int, town_type: str, job_name: str) -> None:
        """
        在特定类型的城镇中随机增加指定数量的工作岗位
        
        .. deprecated::
            使用 add_jobs() 替代此方法
            
        Args:
            add_job_amount: 需要增加的总岗位数量
            town_type: 城镇类型
            job_name: 指定的工作岗位名称
            
        Note:
            - 只在指定类型的城镇中增加岗位
            - 如果岗位数小于城镇数，随机选取岗位数个城镇
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def towns(self) -> Dict[str, Dict[str, Any]]:
        """
        城镇字典
        键为城镇名称，值为城镇数据（包含info、residents、resident_group、job_market等）
        """
        pass
