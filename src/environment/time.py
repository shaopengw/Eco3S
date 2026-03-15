from src.interfaces import ITime

class Time(ITime):
    def __init__(self, start_time, total_steps):
        """
        初始化时间类
        :param start_time: 模拟的起始时间
        :param total_steps: 模拟的总时间步数
        """
        self._start_time = start_time
        self._total_steps = total_steps
        self._end_time = start_time + total_steps - 1
        self._current_time = start_time
    
    # 实现 ITime 接口的 property
    @property
    def start_time(self) -> int:
        """起始时间"""
        return self._start_time
    
    @property
    def total_steps(self) -> int:
        """总时间步数"""
        return self._total_steps
    
    @total_steps.setter
    def total_steps(self, value: int):
        """设置总时间步数"""
        self._total_steps = value
        self._end_time = self._start_time + value - 1
    
    @property
    def end_time(self) -> int:
        """结束时间"""
        return self._end_time
    
    @property
    def current_time(self) -> int:
        """当前时间"""
        return self._current_time
    
    @current_time.setter
    def current_time(self, value: int):
        """设置当前时间"""
        self._current_time = value

    def step(self):
        """
        推进一个时间步
        """
        self.current_time += 1

    def is_end(self):
        """
        检查是否到达模拟结束时间
        :return: 是否到达结束时间（布尔值）
        """
        return self.current_time > self.end_time

    def get_elapsed_time_steps(self):
        """
        获取已经过去的时间步数
        :return: 已经过去的时间步数
        """
        return self.current_time - self.start_time

    def reset(self):
        """
        重置时间到起始时间
        """
        self.current_time = self.start_time

    def update_total_steps(self, new_total_steps):
        """更新总时间步数，并相应调整结束时间"""
        self.total_steps = new_total_steps
        self.end_time = self.current_time + new_total_steps - 1