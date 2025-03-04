import numpy as np
import matplotlib.pyplot as plt

class Map:
    def __init__(self, size):
        """
        初始化地图
        :param size: 地图的大小（size x size 的网格）
        """
        self.size = size
        self.grid = np.zeros((size, size))  # 基础网格
        self.river_grid = np.zeros((size, size))  # 沿河区域
        self.market_towns = []  # 市场城镇的位置列表
        self.terrain_ruggedness = np.random.rand(size, size)  # 地形崎岖指数（随机生成）

    def initialize_river(self):
        """
        初始化沿河区域
        假设运河从地图的中间穿过（纵向）
        """
        self.river_grid[:, self.size // 2] = 1  # 沿河区域标记为1

    def initialize_market_towns(self):
        """
        初始化市场城镇
        假设市场城镇沿运河每隔一定距离分布
        """
        for i in range(0, self.size, 5):  # 每隔5个网格设置一个市场城镇
            self.market_towns.append((i, self.size // 2))  # 市场城镇位于沿河区域

    def get_river_damage_level(self, year):
        """
        获取运河的损坏程度
        :param year: 当前年份
        :return: 运河损坏程度（0到1之间的值，1表示完全损坏）
        """
        # 假设运河损坏程度随时间线性增加
        if year < 1826:
            return 0.0  # 1826年之前运河完好
        else:
            return min(1.0, (year - 1826) / 100)  # 每年增加1%的损坏

    def update_river_condition(self, year):
        """
        更新运河的状态
        :param year: 当前年份
        """
        damage_level = self.get_river_damage_level(year)
        self.river_grid[self.river_grid == 1] = 1 - damage_level  # 损坏程度越高，运河状态越差

    def is_river_nearby(self, location):
        """
        判断某个位置是否靠近运河
        :param location: 位置的坐标 (x, y)
        :return: 是否靠近运河（布尔值）
        """
        x, y = location
        return self.river_grid[x, y] == 1

    def get_terrain_ruggedness(self, location):
        """
        获取某个位置的地形崎岖指数
        :param location: 位置的坐标 (x, y)
        :return: 地形崎岖指数（0到1之间的值）
        """
        x, y = location
        return self.terrain_ruggedness[x, y]

    def get_market_towns(self):
        """
        获取所有市场城镇的位置
        :return: 市场城镇的位置列表
        """
        return self.market_towns

    def get_map_size(self):
        """
        获取地图的大小
        :return: 地图的大小（size x size）
        """
        return self.size

    def visualize_map(self):
        """
        可视化地图，显示沿河区域、市场城镇和地形崎岖指数
        """
        plt.figure(figsize=(10, 10))

        # 绘制地形崎岖指数
        plt.imshow(self.terrain_ruggedness, cmap='terrain', alpha=0.6, extent=[0, self.size, 0, self.size])

        # 绘制沿河区域
        river_x, river_y = np.where(self.river_grid == 1)
        plt.scatter(river_y, self.size - np.array(river_x), color='blue', label='River', s=10)

        # 绘制市场城镇
        market_x = [town[0] for town in self.market_towns]
        market_y = [town[1] for town in self.market_towns]
        plt.scatter(market_y, self.size - np.array(market_x), color='red', label='Market Towns', s=50, marker='s')

        # 设置地图标题和标签
        plt.title("Map Visualization: River, Market Towns, and Terrain Ruggedness")
        plt.xlabel("X Coordinate")
        plt.ylabel("Y Coordinate")
        plt.legend()

        # 显示地图
        plt.show()

    def print_map(self):
        """
        打印地图（用于调试）
        """
        print("River Grid:")
        print(self.river_grid)
        print("Market Towns:", self.market_towns)

if __name__ == "__main__":
    # 初始化地图
    map = Map(size=100)
    map.initialize_river()
    map.initialize_market_towns()

    # 打印地图信息
    map.print_map()

    # 可视化地图
    map.visualize_map()

    # 更新运河状态并重新可视化
    map.update_river_condition(year=1850)
    map.visualize_map()