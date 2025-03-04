class Population:
    def __init__(self, initial_population):
        """
        初始化人口类
        :param initial_population: 初始人口数量
        """
        self.population = initial_population
        self.birth_rate = 0.1  # 出生率
        self.death_rate = 0.1  # 死亡率

    def birth(self,num):
        """
        模拟人口出生
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

    def set_birth_rate(self, birth_rate):
        """
        设置出生率
        :param birth_rate: 新的出生率（0到1之间的值）
        """
        self.birth_rate = birth_rate

    def set_death_rate(self, death_rate):
        """
        设置死亡率
        :param death_rate: 新的死亡率（0到1之间的值）
        """
        self.death_rate = death_rate

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