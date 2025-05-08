import numpy as np
import os
import matplotlib.pyplot as plt
from datetime import datetime
import json
import math
import random

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
        self.navigability = 1.0  # 初始运河通航能力为1.0（最佳状态）
        self.city_graph = {}  # 城市图（邻接表形式）
        self.city_dict = {}  # 存储城市信息
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
            self.city_data = data
            
        except Exception as e:
            print(f"加载城市数据失败: {e}")
            # 提供默认数据
            self.city_data = {
                "canal_cities": [],
                "other_cities": []
            }

    def _prepare_cities(self):
        """转换原始城市数据为带坐标的列表"""
        cities = []
        for city in self.city_data['canal_cities'] + self.city_data['other_cities']:
            x = self.longitude_to_x(city['longitude'])
            y = self.latitude_to_y(city['latitude'])
            city_type = 'canal' if city in self.city_data['canal_cities'] else 'non_canal'
            cities.append({'x': x, 'y': y, 'name': city['name'], 'type': city_type})
        return cities

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
        self.navigability = 1.0  # 重置运河通航能力
        
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
    
    def initialize_city_graph(self, max_distance=20):
        """
        初始化城市图，通过计算城市间距离来建立连接
        :param max_distance: 最大连接距离
        """
        all_cities = self._prepare_cities()
        self.city_graph = {}
        
        # 初始化城市字典和图
        for city in all_cities:
            city_name = city['name']
            self.city_dict[city_name] = {
                'location': (city['x'], city['y']),
                'type': city['type']
            }
            self.city_graph[city_name] = []

        # 计算城市间距离并建立连接
        for city1 in all_cities:
            for city2 in all_cities:
                if city1['name'] != city2['name']:
                    distance = self._calculate_distance(
                        (city1['x'], city1['y']),
                        (city2['x'], city2['y'])
                    )
                    if distance <= max_distance:
                        self.city_graph[city1['name']].append(city2['name'])

    def _calculate_distance(self, point1, point2):
        """
        计算两点间的欧几里得距离
        """
        return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

    def get_connected_cities(self, city_name):
        """
        获取与指定城市相连的所有城市
        :param city_name: 城市名称
        :return: 相连城市列表
        """
        return self.city_graph.get(city_name, [])

    def visualize_map(self):
        """
        可视化地图，显示沿河区域、市场城镇和地形崎岖指数
        """
        plt.figure(figsize=(10, 15))

        # 绘制地形崎岖指数
        plt.imshow(self.terrain_ruggedness, cmap='terrain', alpha=0.6, 
                extent=[0, self.width, self.height, 0])

        # 绘制沿河区域
        river_y, river_x = np.where(self.river_grid > 0)  # 改为>0以显示部分损坏的运河
        plt.scatter(river_x, river_y, color='blue', label='The Canal', s=10)

        # 准备城市数据
        canal_cities = []
        other_cities = []
        for city_name in self.city_dict:
            city_info = self.city_dict[city_name]
            if city_info['type'] == 'canal':
                canal_cities.append((city_info['location'][0], city_info['location'][1], city_name))
            else:
                other_cities.append((city_info['location'][0], city_info['location'][1], city_name))

        # 绘制运河城市和名称标注
        if canal_cities:
            canal_x = [city[0] for city in canal_cities]
            canal_y = [city[1] for city in canal_cities]
            plt.scatter(canal_x, canal_y, color='red', label='Canal Towns', s=50, marker='s')
            
            for x, y, name in canal_cities:
                plt.annotate(name, 
                            xy=(x, y),
                            xytext=(5, 5), 
                            textcoords='offset points',
                            fontsize=8,
                            fontproperties='SimHei',
                            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))
        
        # 绘制非运河城市和名称标注
        if other_cities:
            other_x = [city[0] for city in other_cities]
            other_y = [city[1] for city in other_cities]
            plt.scatter(other_x, other_y, color='green', label='Other Cities', s=50, marker='^')
            
            for x, y, name in other_cities:
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

    def update_river_condition(self, maint_factor=None):
        """
        更新运河的状态
        :param maint_factor: 维护系数的变化值，范围[-1,1]，表示通航能力的增减
        :return: 当前运河通航能力，如果系数不合法则返回提示信息
        """
        # 自然衰减
        natural_decay_rate=0.1
        self.navigability = max(0, self.navigability * (1 - natural_decay_rate))

        # 如果提供了维护系数，进行增量更新
        if maint_factor is not None:
            if not (-1 <= maint_factor <= 1):
                return f"维护系数变化值 {maint_factor} 不在有效范围[-1,1]内"
            self.navigability = max(0, min(1, self.navigability + maint_factor))

        # 更新运河网格的状态
        self.river_grid[self.river_grid > 0] = self.navigability
        
        return self.navigability

    def get_navigability(self):
        """
        获取当前运河通航能力
        :return: 通航能力值（0-1之间的浮点数）
        """
        return self.navigability

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

    def get_river_towns(self):
        """
        获取所有市场城镇的位置
        :return: 市场城镇的位置列表
        """
        towns = []
        for city in self.city_dict:
            if self.city_dict[city]['type'] == 'canal':
                towns.append(self.city_dict[city]['location'])
        return towns

    def get_non_river_towns(self):
        """
        获取所有非沿河城市的位置
        :return: 非沿河城市的位置列表
        """
        towns = []
        for city in self.city_dict:
            if self.city_dict[city]['type'] == 'non_canal':
                towns.append(self.city_dict[city]['location'])
        return towns
    
    def print_map(self):
        """
        打印地图（用于调试）
        """
        print("River Grid:")
        print(self.river_grid)
        print("city_graph:", self.city_graph)
        print("city_dict:", self.city_dict)

    def initialize_map(self):
        self.initialize_river()
        self.initialize_city_graph()

    def generate_random_location(self, city_name, sigma=2.0):
        """
        为指定城市生成一个随机位置
        :param city_name: 城市名称
        :param sigma: 正态分布标准差，默认2.0
        :return: ((x, y), town_id) 坐标元组和城镇ID
        """
        if city_name not in self.city_dict:
            return None
            
        city_info = self.city_dict[city_name]
        center_x, center_y = city_info['location']
        
        while True:
            # 生成正态分布的偏移量
            offset_x = int(random.gauss(0, sigma))
            offset_y = int(random.gauss(0, sigma))
            
            # 计算实际位置
            x = center_x + offset_x
            y = center_y + offset_y
            
            # 确保位置在地图范围内
            if 0 <= x < self.width and 0 <= y < self.height:
                return (x, y), city_name  # 返回坐标和城市名称作为town_id


if __name__ == "__main__":
    # 初始化地图
    map = Map(width=100, height=150)  # 调整尺寸以适应中国地图比例
    map.initialize_map()

    # 打印地图信息
    map.print_map()

    # 可视化地图
    map.visualize_map()