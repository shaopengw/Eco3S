import numpy as np
import os
import matplotlib.pyplot as plt
from datetime import datetime
import json
import math

class Map:
    def __init__(self, width, height, data_file='src\environment\cities_data.json'):
        """
        初始化地图
        :param width: 地图宽度
        :param height: 地图高度
        :param data_file: 城市数据文件路径
        """
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width))
        self.river_grid = np.zeros((height, width))
        self.market_towns = []
        self.town_names = []
        self.non_river_towns = []
        self.non_river_town_names = []
        self.terrain_ruggedness = np.random.rand(height, width)
        
        # 加载城市数据
        self.load_city_data(data_file)
        
        # 计算地图边界（中国大致经纬度范围）
        self.min_longitude = 109
        self.max_longitude = 125.0
        self.min_latitude = 30.0
        self.max_latitude = 41.0

    def load_city_data(self, data_file):
        """
        从JSON文件加载城市数据
        :param data_file: JSON文件路径
        """
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 加载运河城市
            for city in data['canal_cities']:
                self.town_names.append(city['name'])
                # 坐标将在initialize方法中转换
                
            # 加载非运河城市
            for city in data['other_cities']:
                self.non_river_town_names.append(city['name'])
                
            self.city_data = data
            
        except Exception as e:
            print(f"加载城市数据失败: {e}")
            # 提供默认数据
            self.city_data = {
                "canal_cities": [],
                "other_cities": []
            }

    def longitude_to_x(self, longitude):
        """
        将经度转换为地图x坐标
        """
        return int((longitude - self.min_longitude) / (self.max_longitude - self.min_longitude) * self.width)

    def latitude_to_y(self, latitude):
        """
        将纬度转换为地图y坐标
        """
        # 纬度越高，y坐标越小（北在上）
        return int((self.max_latitude - latitude) / (self.max_latitude - self.min_latitude) * self.height)

    def initialize_river(self):
        """
        初始化京杭大运河路线
        """
        self.river_grid = np.zeros((self.height, self.width))
        
        # 获取运河城市坐标点
        river_points = []
        for city in self.city_data['canal_cities']:
            x = self.longitude_to_x(city['longitude'])
            y = self.latitude_to_y(city['latitude'])
            river_points.append((x, y, city['name']))
        
        # 连接各个点形成运河
        for i in range(len(river_points) - 1):
            x1, y1, _ = river_points[i]
            x2, y2, _ = river_points[i + 1]
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
        
        for city in self.city_data['canal_cities']:
            x = self.longitude_to_x(city['longitude'])
            y = self.latitude_to_y(city['latitude'])
            if 0 <= x < self.width and 0 <= y < self.height:
                self.market_towns.append((x, y))
                self.town_names.append(city['name'])

    def initialize_non_river_towns(self):
        """
        初始化非沿河城市
        """
        self.non_river_towns = []
        self.non_river_town_names = []
        
        for city in self.city_data['other_cities']:
            x = self.longitude_to_x(city['longitude'])
            y = self.latitude_to_y(city['latitude'])
            if 0 <= x < self.width and 0 <= y < self.height:
                self.non_river_towns.append((x, y))
                self.non_river_town_names.append(city['name'])

    def visualize_map(self):
        """
        可视化地图，显示沿河区域、市场城镇和地形崎岖指数
        """
        plt.figure(figsize=(10, 15))

        # 绘制地形崎岖指数
        plt.imshow(self.terrain_ruggedness, cmap='terrain', alpha=0.6, 
                  extent=[0, self.width, self.height, 0])

        # 绘制沿河区域
        river_y, river_x = np.where(self.river_grid == 1)
        plt.scatter(river_x, river_y, color='blue', label='The Canal', s=10)

        # 绘制市场城镇和城市名称
        market_x = [town[0] for town in self.market_towns]
        market_y = [town[1] for town in self.market_towns]
        plt.scatter(market_x, market_y, color='red', label='Canal Towns', s=50, marker='s')
        
        # 添加运河城市名称标注
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
        
        # 绘制非沿河城市
        non_river_x = [town[0] for town in self.non_river_towns]
        non_river_y = [town[1] for town in self.non_river_towns]
        plt.scatter(non_river_x, non_river_y, color='green', label='Other Cities', s=50, marker='^')
        
        # 添加非沿河城市名称标注
        for i in range(len(self.non_river_towns)):
            x = non_river_x[i]
            y = non_river_y[i]
            name = self.non_river_town_names[i]
            plt.annotate(name, 
                        xy=(x, y),
                        xytext=(5, 5), 
                        textcoords='offset points',
                        fontsize=8,
                        fontproperties='SimHei',
                        bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))

        plt.title("中国主要城市与京杭大运河地图", fontproperties='SimHei', fontsize=14)
        plt.xlabel("经度方向 (东→西)", fontproperties='SimHei')
        plt.ylabel("纬度方向 (北→南)", fontproperties='SimHei')
        plt.legend()
        plt.show()

    # 其他方法保持不变...
    def get_river_damage_level(self, year):
        """
        获取运河的损坏程度
        :param year: 当前年份
        :return: 运河损坏程度（0到1之间的值，1表示完全损坏）
        """
        if year < 1826:
            return 0.0
        else:
            return min(1.0, (year - 1826) / 100)

    def update_river_condition(self, year):
        """
        更新运河的状态
        :param year: 当前年份
        """
        damage_level = self.get_river_damage_level(year)
        self.river_grid[self.river_grid == 1] = 1 - damage_level

    def is_river_nearby(self, location):
        """
        判断某个位置是否靠近运河
        :param location: 位置的坐标 (x, y)
        :return: 是否靠近运河（布尔值）
        """
        x, y = location
        return self.river_grid[y, x] > 0.5

    def get_terrain_ruggedness(self, location):
        """
        获取某个位置的地形崎岖指数
        :param location: 位置的坐标 (x, y)
        :return: 地形崎岖指数（0到1之间的值）
        """
        x, y = location
        return self.terrain_ruggedness[y, x]

    def get_market_towns(self):
        """
        获取所有市场城镇的位置
        :return: 市场城镇的位置列表
        """
        return self.market_towns
    
    def get_non_river_towns(self):
        """
        获取所有非沿河城市的位置
        :return: 非沿河城市的位置列表
        """
        return self.non_river_towns
    
    def print_map(self):
        """
        打印地图（用于调试）
        """
        print("River Grid:")
        print(self.river_grid)
        print("Market Towns:", self.market_towns)
        print("Non-River Towns:", self.non_river_towns)

if __name__ == "__main__":
    # 初始化地图
    map = Map(width=100, height=150)  # 调整尺寸以适应中国地图比例
    
    # 初始化河流和城市
    map.initialize_river()
    map.initialize_market_towns()
    map.initialize_non_river_towns()

    # 打印地图信息
    map.print_map()

    # 可视化地图
    map.visualize_map()

    # 更新运河状态并重新可视化
    map.update_river_condition(year=1850)
    map.visualize_map()