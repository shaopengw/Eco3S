class TransportEconomy:
    def __init__(self, transport_cost, transport_task, maintenance_cost_base=100):
        """
        初始化运输经济系统
        :param transport_cost: 基础运输成本
        :param transport_task: 年度运输任务量（吨）
        :param maintenance_cost_base: 基础维护成本
        """
        self.transport_cost = transport_cost  # 基础运输成本
        self.transport_task = transport_task  # 年度运输任务量
        self.maintenance_cost_base = maintenance_cost_base  # 基础维护成本
        self.river_price = transport_cost
        self.sea_price = round((self.transport_cost / 5),2)  # 初始化海运价格

    def calculate_river_price(self, navigability):
        """
        计算河运价格
        :param navigability: 通航能力（0-1）
        :return: 河运价格
        """
        # 通航值越低价格越高，最低为基础价格
        river_price = round(self.transport_cost * (2 - navigability),2)
        self.river_price = max(river_price, self.transport_cost) # 更新实例变量
        return self.river_price

    def calculate_maintenance_cost(self, navigability, exponent=3):
        """
        计算河运维护成本
        :param navigability: 当前通航能力（0-1）
        :param exponent: 指数
        :return: 维护成本
        """
        # 通航能力越低，维护成本以指数形式增加
        return round(self.maintenance_cost_base * ((2 - navigability) ** exponent), 2)


    def calculate_total_transport_cost(self, river_ratio):
        """
        计算总运输成本
        :param river_ratio: 河运比例（0-1）
        :return: 总运输成本
        """
        river_cost = self.river_price * river_ratio * self.transport_task
        sea_cost = self.sea_price * (1 - river_ratio) * self.transport_task
        
        return river_cost + sea_cost
