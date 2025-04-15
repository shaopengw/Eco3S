# 暂时废弃

class InformationSpread:
    def __init__(self, map):
        """
        初始化信息传播类
        :param map: 地图对象，用于获取地理信息
        """
        self.map = map
        self.information_grid = {}  # 存储每个位置的信息状态

    def initialize_information(self):
        """
        初始化信息状态
        假设初始时只有市场城镇有信息
        """
        for town in self.map.get_river_towns():
            self.information_grid[town] = True  # 市场城镇初始有信息

    def spread_information(self, agents):
        """
        传播信息
        :param agents: 所有居民Agent的列表
        """
        for agent in agents:
            if self.has_information(agent.location):
                # 如果Agent所在位置有信息，则Agent接收信息
                agent.receive_information()
                # 将信息传播到相邻位置
                self.spread_to_neighbors(agent.location)

    def has_information(self, location):
        """
        检查某个位置是否有信息
        :param location: 位置的坐标 (x, y)
        :return: 是否有信息（布尔值）
        """
        return self.information_grid.get(location, False)

    def spread_to_neighbors(self, location):
        """
        将信息传播到相邻位置
        :param location: 当前位置的坐标 (x, y)
        """
        x, y = location
        neighbors = [
            (x - 1, y), (x + 1, y),  # 上下
            (x, y - 1), (x, y + 1),  # 左右
            (x - 1, y - 1), (x - 1, y + 1),  # 左上、右上
            (x + 1, y - 1), (x + 1, y + 1)  # 左下、右下
        ]

        for neighbor in neighbors:
            if self.is_valid_location(neighbor):
                self.information_grid[neighbor] = True

    def is_valid_location(self, location):
        """
        检查位置是否在地图范围内
        :param location: 位置的坐标 (x, y)
        :return: 是否有效（布尔值）
        """
        x, y = location
        return 0 <= x < self.map.get_map_size() and 0 <= y < self.map.get_map_size()

    def get_information_coverage(self):
        """
        获取信息覆盖率（有信息的位置占总位置的比例）
        :return: 信息覆盖率（0到1之间的值）
        """
        total_locations = self.map.get_map_size() ** 2
        informed_locations = len(self.information_grid)
        return informed_locations / total_locations

    def print_information_grid(self):
        """
        打印信息网格（用于调试）
        """
        for location, has_info in self.information_grid.items():
            print(f"Location {location}: {'Has Info' if has_info else 'No Info'}")