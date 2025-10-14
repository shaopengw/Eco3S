import os
from datetime import datetime

class SimulationContext:
    """模拟环境上下文管理器"""
    _current_simulation = "default"  # 模拟类型，如 "info_propagation"
    _simulation_name = None  # 具体实验的标识，通常是时间戳，如 "20250926_155825"
    _base_history_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')), 'history')
    
    @classmethod
    def set_simulation_type(cls, simulation_type: str):
        """设置当前模拟类型（如 info_propagation）"""
        cls._current_simulation = simulation_type
        
    @classmethod
    def get_simulation_type(cls) -> str:
        """获取当前模拟类型"""
        return cls._current_simulation
    
    @classmethod
    def set_simulation_name(cls, simulation_name: str = None, population: int = None, total_years: int = None):
        """设置当前模拟名称，如果不提供或为空字符串则使用时间戳+p人口数+y时间步数"""
        if simulation_name is None or simulation_name == "":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if population is not None and total_years is not None:
                simulation_name = f"{timestamp}_p{population}_y{total_years}"
            else:
                simulation_name = timestamp
            print(f"设置模拟名称为: {simulation_name}")
        cls._simulation_name = simulation_name

    @classmethod
    def get_simulation_name(cls) -> str:
        """获取当前模拟名称，如果未设置则返回基于时间戳的默认名称"""
        return cls._simulation_name
    
    @classmethod
    def get_current_simulation_dir(cls) -> str:
        """获取当前模拟类型的目录路径（如 history/info_propagation/）"""
        return os.path.join(cls._base_history_dir, cls._current_simulation)
    
    @classmethod
    def get_current_test_dir(cls) -> str:
        """获取当前具体实验的目录路径"""
        simulation_name = cls.get_simulation_name()
        simulation_dir = cls.get_current_simulation_dir()
        return os.path.join(simulation_dir, simulation_name)
    
    @classmethod
    def get_logs_dir(cls) -> str:
        """获取日志目录路径"""
        return cls.get_current_test_dir()
    
    @classmethod
    def get_plots_dir(cls) -> str:
        """获取图表目录路径"""
        return os.path.join(cls.get_current_test_dir(), "plot_results")
    
    @classmethod
    def get_data_dir(cls) -> str:
        """获取数据目录路径"""
        return cls.get_current_test_dir()
    
    @classmethod
    def ensure_directories(cls):
        """确保所有必要的目录都存在"""
        os.makedirs(cls.get_logs_dir(), exist_ok=True)
        os.makedirs(cls.get_plots_dir(), exist_ok=True)
        os.makedirs(cls.get_data_dir(), exist_ok=True)