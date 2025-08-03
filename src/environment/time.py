class Time:
    def __init__(self, start_year, total_years):
        """
        初始化时间类
        :param start_year: 模拟的起始年份
        :param total_years: 模拟的总年数
        """
        self.start_year = start_year
        self.total_years = total_years
        self.end_year = start_year + total_years - 1
        self.current_year = start_year

    def step(self):
        """
        推进时间步长（一年）
        """
        self.current_year += 1

    def is_end(self):
        """
        检查是否到达模拟结束时间
        :return: 是否到达结束时间（布尔值）
        """
        return self.current_year > self.end_year

    def get_current_time(self):
        """
        获取当前时间（年份）
        :return: 当前时间的字符串表示（如 "1650"）
        """
        return str(self.current_year)

    def get_start_time(self):
        """
        获取起始时间（年份）
        :return: 起始时间的字符串表示（如 "1650"）
        """
        return self.start_year

    def get_current_year(self):
        """
        获取当前年份
        :return: 当前年份
        """
        return self.current_year

    def get_total_time_steps(self):
        """
        获取模拟的总时间步长（年数）
        :return: 总时间步长
        """
        return self.total_years

    def get_elapsed_time_steps(self):
        """
        获取已经过去的时间步长（年数）
        :return: 已经过去的时间步长
        """
        return self.current_year - self.start_year

    def reset(self):
        """
        重置时间到起始年份
        """
        self.current_year = self.start_year

    def update_total_years(self, new_total_years):
        """更新总模拟年数，并相应调整结束年份"""
        self.total_years = new_total_years
        self.end_year = self.current_year + new_total_years - 1