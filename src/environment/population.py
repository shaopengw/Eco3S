class Population:
    def __init__(self, initial_population):
        """
        初始化人口类
        :param initial_population: 初始人口数量
        """
        self.population = initial_population
        self.birth_rate = 0.1  # 出生率
        self.death_rate = 0.1  # 死亡率

    def update_birth_rate(self, satisfaction):
        """
        根据居民平均满意度更新出生率
        :param satisfaction: 居民平均满意度（0-100）
        """
        base_rate = self.birth_rate
        
        if satisfaction >= 80:
            # 满意度高于80时，出生率上升
            # 每超过80一点，出生率增加0.2%
            increase = (satisfaction - 80) * 0.002
            self.birth_rate = min(0.2, base_rate + increase)  # 设置上限为20%
        elif satisfaction <= 50:
            # 满意度低于50时，出生率下降
            # 每低于50一点，出生率降低0.1%
            decrease = (50 - satisfaction) * 0.001
            self.birth_rate = max(0.05, base_rate - decrease)  # 设置下限为5%
        else:
            # 满意度在50-80之间，保持基础出生率
            self.birth_rate = base_rate

    def birth(self,num):
        """
        人口出生
        """
        self.population += num
        return self.population

    def death(self):
        """
        人口死亡
        """
        self.population -= 1

    def get_population(self):
        """
        获取当前人口数量
        :return: 当前人口数量
        """
        return self.population

    def simulate_year(self):
        """
        模拟一年的出生和死亡过程
        :return: 出生人数和死亡人数
        """
        births = self.birth()
        deaths = self.death()
        return births, deaths

    def print_population_status(self):
        """
        打印人口状态（用于调试）
        """
        print(f"Current Population: {self.population}")
        print(f"Birth Rate: {self.birth_rate * 100}%")
        print(f"Death Rate: {self.death_rate * 100}%")