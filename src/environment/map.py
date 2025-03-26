import numpy as np
import os
import matplotlib.pyplot as plt
from datetime import datetime

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
        初始化京杭大运河路线
        从北京到杭州的主要路线，使用实际经纬度的相对位置
        """
        # 清空原有的河道
        self.river_grid = np.zeros((self.size, self.size))
        
        # 定义运河的关键点（从北到南，使用实际经纬度转换的相对位置）
        river_points = [
            (0.05, 0.95),    # 北京   (116.4°E, 39.9°N)
            (0.07, 0.93),    # 通州   (116.7°E, 39.8°N)
            (0.15, 0.90),    # 天津   (117.2°E, 39.1°N)
            (0.20, 0.85),    # 沧州   (116.8°E, 38.3°N)
            (0.25, 0.80),    # 德州   (116.3°E, 37.4°N)
            (0.30, 0.75),    # 临清   (115.7°E, 36.9°N)
            (0.35, 0.73),    # 聊城   (115.9°E, 36.4°N)
            (0.40, 0.65),    # 济宁   (116.6°E, 35.4°N)
            (0.45, 0.60),    # 台儿庄 (117.7°E, 34.6°N)
            (0.50, 0.55),    # 徐州   (117.2°E, 34.3°N)
            (0.60, 0.50),    # 清江   (119.0°E, 33.6°N)
            (0.65, 0.45),    # 淮安   (119.1°E, 33.5°N)
            (0.75, 0.40),    # 扬州   (119.4°E, 32.4°N)
            (0.80, 0.35),    # 镇江   (119.4°E, 32.2°N)
            (0.85, 0.30),    # 苏州   (120.6°E, 31.3°N)
            (0.90, 0.25),    # 杭州   (120.2°E, 30.3°N)
        ]
        
        # 将比例坐标转换为实际网格坐标
        river_coords = [(int(x * self.size), int(y * self.size)) for x, y in river_points]
        
        # 连接各个点形成运河
        for i in range(len(river_coords) - 1):
            x1, y1 = river_coords[i]
            x2, y2 = river_coords[i + 1]
            # 使用线性插值连接两点
            steps = max(abs(x2 - x1), abs(y2 - y1)) * 2
            for step in range(steps + 1):
                t = step / steps
                x = int(x1 + t * (x2 - x1))
                y = int(y1 + t * (y2 - y1))
                if 0 <= x < self.size and 0 <= y < self.size:
                    self.river_grid[x, y] = 1
                    # 为运河添加一定宽度
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.size and 0 <= ny < self.size:
                                self.river_grid[nx, ny] = 1

    def initialize_market_towns(self):
        """
        初始化京杭大运河沿线的主要城市
        """
        # 清空原有的市场城镇
        self.market_towns = []
        self.town_names = []  # 添加城市名称列表
        
        # 定义主要城市的位置（从北到南）
        town_points = [
            (0.05, 0.95, "北京"),     # 北京   (116.4°E, 39.9°N)
            (0.07, 0.93, "通州"),     # 通州   (116.7°E, 39.8°N)
            (0.15, 0.90, "天津"),     # 天津   (117.2°E, 39.1°N)
            (0.20, 0.85, "沧州"),     # 沧州   (116.8°E, 38.3°N)
            (0.25, 0.80, "德州"),     # 德州   (116.3°E, 37.4°N)
            (0.30, 0.75, "临清"),     # 临清   (115.7°E, 36.9°N)
            (0.35, 0.73, "聊城"),     # 聊城   (115.9°E, 36.4°N)
            (0.40, 0.65, "济宁"),     # 济宁   (116.6°E, 35.4°N)
            (0.45, 0.60, "台儿庄"),   # 台儿庄 (117.7°E, 34.6°N)
            (0.50, 0.55, "徐州"),     # 徐州   (117.2°E, 34.3°N)
            (0.60, 0.50, "清江"),     # 清江   (119.0°E, 33.6°N)
            (0.65, 0.45, "淮安"),     # 淮安   (119.1°E, 33.5°N)
            (0.75, 0.40, "扬州"),     # 扬州   (119.4°E, 32.4°N)
            (0.80, 0.35, "镇江"),     # 镇江   (119.4°E, 32.2°N)
            (0.85, 0.30, "苏州"),     # 苏州   (120.6°E, 31.3°N)
            (0.90, 0.25, "杭州"),     # 杭州   (120.2°E, 30.3°N)
        ]
        
        # 将比例坐标转换为实际网格坐标
        for x, y, name in town_points:
            grid_x = int(x * self.size)
            grid_y = int(y * self.size)
            if 0 <= grid_x < self.size and 0 <= grid_y < self.size:
                self.market_towns.append((grid_x, grid_y))
                self.town_names.append(name)  # 保存城市名称

    def visualize_map(self):
        """
        可视化地图，显示沿河区域、市场城镇和地形崎岖指数
        """
        plt.figure(figsize=(12, 12))  # 增加图像大小以适应文字标注

        # 绘制地形崎岖指数
        plt.imshow(self.terrain_ruggedness, cmap='terrain', alpha=0.6, extent=[0, self.size, 0, self.size])

        # 绘制沿河区域
        river_x, river_y = np.where(self.river_grid == 1)
        plt.scatter(river_y, self.size - np.array(river_x), color='blue', label='River', s=10)

        # 绘制市场城镇和城市名称
        market_x = [town[0] for town in self.market_towns]
        market_y = [town[1] for town in self.market_towns]
        plt.scatter(market_y, self.size - np.array(market_x), color='red', label='Market Towns', s=50, marker='s')
        
        # 添加城市名称标注
        for i in range(len(self.market_towns)):
            x = market_x[i]
            y = market_y[i]
            name = self.town_names[i]
            # 在城市点右侧添加文字标注，设置中文字体
            plt.annotate(name, 
                        xy=(y, self.size - x),
                        xytext=(5, 5), 
                        textcoords='offset points',
                        fontsize=8,
                        fontproperties='SimHei',  # 使用黑体显示中文
                        bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))

        # 设置地图标题和标签
        plt.title("京杭大运河沿线地图", fontproperties='SimHei', fontsize=14)
        plt.xlabel("X 坐标", fontproperties='SimHei')
        plt.ylabel("Y 坐标", fontproperties='SimHei')
        plt.legend()
        plt.show()
        # # 保存图片
        # save_dir = "e:/cyf/多智能体/AgentWorld/experiment_dataset/map_data"
        # if not os.path.exists(save_dir):
        #     os.makedirs(save_dir)
        # current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        # save_path = os.path.join(save_dir, f"map_{current_time}.png")
        # plt.savefig(save_path, dpi=300, bbox_inches='tight')
        # print(f"地图已保存至：{save_path}")
        # plt.close()

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