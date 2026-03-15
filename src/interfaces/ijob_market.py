"""
就业市场抽象接口
定义就业市场系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class IJobMarket(ABC):
    """
    就业市场抽象基类
    定义就业市场的所有核心功能，包括工作管理、职位分配和薪资管理
    """

    @abstractmethod
    def __init__(self, town_type: str = "非沿河", initial_jobs_count: int = 100, config_path: Optional[Path] = None):
        """
        初始化就业市场类
        
        Args:
            town_type: 城镇类型（"沿河"或"非沿河"）
            initial_jobs_count: 初始工作总数
            config_path: 职业配置文件路径，如果为None则使用默认路径
        """
        pass

    @abstractmethod
    def _initialize_jobs(self, total_count: int) -> None:
        """
        根据比例初始化各类工作的数量
        
        Args:
            total_count: 总工作数量
            
        Note:
            - 如果总岗位数小于总职业数，每个职业分配一个岗位
            - 否则先为每个职业分配一个岗位，剩余按比例分配
        """
        pass

    @abstractmethod
    def add_job(self, job: str, num: int = 1) -> None:
        """
        添加工作机会
        
        Args:
            job: 工作名称
            num: 添加该工作的数量，默认为1
        """
        pass

    @abstractmethod
    def remove_job(self, job: str) -> None:
        """
        移除工作机会
        
        Args:
            job: 工作名称
        """
        pass

    @abstractmethod
    def assign_specific_job(self, resident: Any, job_type: str, actual_salary: Optional[float] = None) -> bool:
        """
        分配指定职业给指定居民
        
        Args:
            resident: 居民对象
            job_type: 职业类型
            actual_salary: 实际支付的居民收入，如果为None则使用基础收入
            
        Returns:
            bool: 是否分配成功
        """
        pass

    @abstractmethod
    def assign_specific_job_withoutcheck(self, resident: Any, job_type: str) -> bool:
        """
        分配指定职业给指定居民，不判断空缺，直接增加工作总数和就职人数
        
        Args:
            resident: 居民对象
            job_type: 职业类型
            
        Returns:
            bool: 是否分配成功
        """
        pass

    @abstractmethod
    def assign_job(self, resident: Any) -> None:
        """
        随机分配工作给居民
        
        Args:
            resident: 居民对象
            
        Note:
            如果没有可用工作，将居民设置为失业状态
        """
        pass

    @abstractmethod
    def get_available_jobs(self) -> Dict[str, int]:
        """
        获取当前可用工作列表
        
        Returns:
            Dict[str, int]: 可用工作及其剩余数量的字典
        """
        pass

    @abstractmethod
    def get_employed_residents(self) -> Dict[str, Dict[int, float]]:
        """
        获取已就业居民信息
        
        Returns:
            Dict[str, Dict[int, float]]: 职业及其从业人员ID和薪资的字典
        """
        pass

    @abstractmethod
    def print_job_market_status(self) -> None:
        """
        打印就业市场状态（用于调试）
        """
        pass

    @abstractmethod
    def remove_resident(self, resident_id: int, job_type: Optional[str] = None) -> bool:
        """
        从就业市场中删除指定居民的信息
        
        Args:
            resident_id: 居民ID
            job_type: 工作类型，如果不指定则搜索所有工作类型
            
        Returns:
            bool: 是否成功删除
        """
        pass

    @abstractmethod
    def get_job_statistics(self, job_type: str) -> Optional[Tuple[int, int, float]]:
        """
        获取指定职业的统计信息
        
        Args:
            job_type: 职业类型
            
        Returns:
            Optional[Tuple[int, int, float]]: (总岗位数, 当前就业人数, 薪资)，
                                               如果职业不存在则返回None
        """
        pass

    @abstractmethod
    def remove_random_jobs(self, num_jobs: int, residents: Dict[int, Any]) -> None:
        """
        随机减少指定数量的工作岗位
        
        Args:
            num_jobs: 需要减少的工作岗位数量
            residents: 居民字典
            
        Note:
            - 按比例分配每个职业要减少的数量
            - 如果减少后工作数量小于当前就业人数，会随机解雇部分员工
        """
        pass

    @abstractmethod
    def adjust_canal_maintenance_jobs(self, change_rate: float, residents: Dict[int, Any]) -> None:
        """
        根据运河状态的变化率调整运河维护工的数量
        
        Args:
            change_rate: 运河状态的变化率（-1到1之间的值）
            residents: 居民字典
            
        Note:
            - 只处理沿河城镇
            - 只处理负变化率的情况
            - 至少减少1个岗位
        """
        pass

    @abstractmethod
    def get_vacant_jobs(self) -> Dict[str, int]:
        """
        获取所有空工作岗位的名称和数量
        
        Returns:
            Dict[str, int]: 字典，键为工作名称，值为空缺数量
        """
        pass

    @abstractmethod
    def get_job_salary(self, job_type: str) -> Optional[float]:
        """
        获取指定职业的收入
        
        Args:
            job_type: 职业类型
            
        Returns:
            Optional[float]: 收入金额，如果职业不存在则返回None
        """
        pass

    @abstractmethod
    def process_job_applications(self, job_requests: List[Dict[str, Any]]) -> Tuple[List[int], float]:
        """
        处理求职申请
        
        Args:
            job_requests: 求职申请列表，每个申请包含居民信息、期望职业和最低收入要求
            
        Returns:
            Tuple[List[int], float]: (成功录用的居民ID列表, 总支出)
            
        Note:
            - 按职业类型分组处理申请
            - 所有申请者按最低收入要求排序
            - 溢出的申请者会随机分配到其他有空缺的岗位
        """
        pass

    @abstractmethod
    def get_rebel_total_salary(self) -> float:
        """
        获取叛军总收入
        
        Returns:
            float: 叛军总收入
        """
        pass

    @abstractmethod
    def get_other_total_salary(self) -> float:
        """
        获取除叛军外其他职业的总收入
        
        Returns:
            float: 其他职业总收入
        """
        pass

    @abstractmethod
    def add_random_jobs(self, num_jobs: int, specific_job: Optional[str] = None) -> None:
        """
        随机增加指定数量的工作岗位（除叛军外）
        
        Args:
            num_jobs: 需要增加的工作岗位数量
            specific_job: 指定的职业名称，如果为None则随机分配
            
        Raises:
            ValueError: 如果指定了无效的职业名称
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def town_type(self) -> str:
        """城镇类型"""
        pass

    @property
    @abstractmethod
    def jobs_info(self) -> Dict[str, Dict[str, Any]]:
        """职业信息字典"""
        pass

    @property
    @abstractmethod
    def professions_ratio(self) -> Dict[str, Dict[str, List[float]]]:
        """职业比例配置"""
        pass
