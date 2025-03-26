import numpy as np
import os
import matplotlib.pyplot as plt
from datetime import datetime

class Map:
    def __init__(self, width, height):
        """
        初始化地图
        """
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width))
        self.river_grid = np.zeros((height, width))
        self.market_towns = []
        self.town_names = []
        # 定义京杭大运河沿线城市的位置（从北到南）
        self.canal_points = [
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
        self.terrain_ruggedness = np.random.rand(height, width)

    def initialize_river(self):
        """
        初始化京杭大运河路线
        """
        self.river_grid = np.zeros((self.height, self.width))
        
        # 提取河流坐标点，y坐标需要反转以匹配地理方向（北上南下）
        river_points = [(x, 1-y) for x, y, _ in self.canal_points]
        river_coords = [(int(x * self.width), int(y * self.height)) for x, y in river_points]
        
        # 连接各个点形成运河
        for i in range(len(river_coords) - 1):
            x1, y1 = river_coords[i]
            x2, y2 = river_coords[i + 1]
            steps = max(abs(x2 - x1), abs(y2 - y1)) * 2
            for step in range(steps + 1):
                t = step / steps
                x = int(x1 + t * (x2 - x1))
                y = int(y1 + t * (y2 - y1))
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.river_grid[y, x] = 1
                    # 为运河添加一定宽度
                    for dy, dx in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,0), (0,1), (1,-1), (1,0), (1,1)]:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < self.height and 0 <= nx < self.width:
                            self.river_grid[ny, nx] = 1

    def initialize_market_towns(self):
        """
        初始化京杭大运河沿线的主要城市
        """
        self.market_towns = []
        self.town_names = []
        
        # 直接使用已定义的城市坐标，y坐标需要反转
        for x, y, name in self.canal_points:
            grid_x = int(x * self.width)
            grid_y = int((1-y) * self.height)  # 反转y坐标
            if 0 <= grid_x < self.width and 0 <= grid_y < self.height:
                self.market_towns.append((grid_x, grid_y))
                self.town_names.append(name)

    def visualize_map(self):
        """
        可视化地图，显示沿河区域、市场城镇和地形崎岖指数
        """
        plt.figure(figsize=(10, 15))

        # 绘制地形崎岖指数，翻转y轴方向
        plt.imshow(self.terrain_ruggedness, cmap='terrain', alpha=0.6, 
                  extent=[0, self.width, self.height, 0])  # 修改extent顺序

        # 绘制沿河区域
        river_y, river_x = np.where(self.river_grid == 1)
        plt.scatter(river_x, river_y, color='blue', label='River', s=10)

        # 绘制市场城镇和城市名称
        market_x = [town[0] for town in self.market_towns]
        market_y = [town[1] for town in self.market_towns]
        plt.scatter(market_x, market_y, color='red', label='Market Towns', s=50, marker='s')
        
        # 添加城市名称标注
        for i in range(len(self.market_towns)):
            x = market_x[i]
            y = market_y[i]
            name = self.town_names[i]
            plt.annotate(name, 
                        xy=(x, y),
                        xytext=(5, 5), 
                        textcoords='offset points',
                        fontsize=8,
                        fontproperties='SimHei',
                        bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))

        plt.title("京杭大运河沿线地图", fontproperties='SimHei', fontsize=14)
        plt.xlabel("东西方向", fontproperties='SimHei')
        plt.ylabel("南北方向", fontproperties='SimHei')
        plt.legend()
        plt.show()

    def get_map_size(self):
        """
        获取地图的尺寸
        :return: 地图的宽度和高度
        """
        return self.width, self.height

if __name__ == "__main__":
    # 初始化地图
    map = Map(width=100, height=150)  # 修改为长方形尺寸
    map.initialize_river()
    map.initialize_market_towns()

    # 打印地图信息
    # map.print_map()

    # 可视化地图
    map.visualize_map()

    # 更新运河状态并重新可视化
    map.update_river_condition(year=1850)
    map.visualize_map()