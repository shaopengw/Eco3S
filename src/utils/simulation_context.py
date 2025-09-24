class SimulationContext:
    """模拟环境上下文管理器"""
    _current_simulation = "default"
    
    @classmethod
    def set_simulation_type(cls, simulation_type: str):
        """设置当前模拟类型"""
        cls._current_simulation = simulation_type
    
    @classmethod
    def get_simulation_type(cls) -> str:
        """获取当前模拟类型"""
        return cls._current_simulation