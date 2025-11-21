class Time:
    def __init__(self, start_time, total_steps):
        """
        初始化时间类
        :param start_time: 模拟的起始时间
        :param total_steps: 模拟的总时间步数
        """
        self.start_time = start_time
        self.total_steps = total_steps
        self.end_time = start_time + total_steps - 1
        self.current_time = start_time

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