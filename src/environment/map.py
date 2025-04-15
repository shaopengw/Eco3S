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
        self.city_matrix = []
        self.city_dict = {}
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
    
    def initialize_city_matrix(self):
        """
        初始化城市矩阵，行列分别对应东西方向和南北方向
        矩阵中的每个元素代表该位置的城市，None表示无城市
        :return: 城市矩阵和城市字典
        """
        # 获取所有城市
        all_cities = []
        for city in self.city_data['canal_cities'] + self.city_data['other_cities']:
            x = self.longitude_to_x(city['longitude'])
            y = self.latitude_to_y(city['latitude'])
            all_cities.append({
                'x': x,
                'y': y,
                'name': city['name'],
                'type': 'canal' if city in self.city_data['canal_cities'] else 'non_canal'
            })
        
        # 按经度(东西方向)和纬度(南北方向)排序
        # 经度越小越西，纬度越小越南
        sorted_by_longitude = sorted(all_cities, key=lambda c: c['x'])
        sorted_by_latitude = sorted(all_cities, key=lambda c: c['y'])
        
        # 创建城市矩阵
        # 行表示南北方向(纬度)，列表示东西方向(经度)
        city_matrix = []
        city_dict = {}
        
        # 先按纬度(南北)分组
        for lat_group in self._group_by(sorted_by_latitude, 'y'):
            row = []
            # 在每个纬度组内按经度(东西)排序
            for city in sorted(lat_group, key=lambda c: c['x']):
                row.append(city['name'])
                city_dict[city['name']] = {
                    'matrix_pos': (len(city_matrix), len(row)-1),
                    'location': (city['x'], city['y']),
                    'type': city['type']
                }
            city_matrix.append(row)
        
        self.city_matrix = city_matrix
        self.city_dict = city_dict

    def _group_by(self, iterable, key):
        """
        辅助函数：按指定key分组
        """
        groups = {}
        for item in iterable:
            groups.setdefault(item[key], []).append(item)
        return groups.values()

    def get_west_city(self, city_name):
        """
        获取指定城市西边的最近城市
        :param city_name: 城市名称
        :return: 西边的城市名称，若无则返回None
        """
        if not hasattr(self, 'city_matrix'):
            self.initialize_city_matrix()
        
        if city_name not in self.city_dict:
            return None
        
        row, col = self.city_dict[city_name]['matrix_pos']
        if col > 0:
            return self.city_matrix[row][col-1]
        return None

    def get_east_city(self, city_name):
        """
        获取指定城市东边的最近城市
        :param city_name: 城市名称
        :return: 东边的城市名称，若无则返回None
        """
        if not hasattr(self, 'city_matrix'):
            self.initialize_city_matrix()
        
        if city_name not in self.city_dict:
            return None
        
        row, col = self.city_dict[city_name]['matrix_pos']
        if col < len(self.city_matrix[row])-1:
            return self.city_matrix[row][col+1]
        return None

    def get_north_city(self, city_name):
        """
        获取指定城市北边的最近城市
        :param city_name: 城市名称
        :return: 北边的城市名称，若无则返回None
        """
        if not hasattr(self, 'city_matrix'):
            self.initialize_city_matrix()
        
        if city_name not in self.city_dict:
            return None
        
        row, col = self.city_dict[city_name]['matrix_pos']
        if row > 0:
            # 在北边的行中寻找相同列或最近列的城市
            north_row = self.city_matrix[row-1]
            if col < len(north_row):
                return north_row[col]
            elif len(north_row) > 0:
                return north_row[-1]  # 返回该行最东边的城市
        return None

    def get_south_city(self, city_name):
        """
        获取指定城市南边的最近城市
        :param city_name: 城市名称
        :return: 南边的城市名称，若无则返回None
        """
        if not hasattr(self, 'city_matrix'):
            self.initialize_city_matrix()
        
        if city_name not in self.city_dict:
            return None
        
        row, col = self.city_dict[city_name]['matrix_pos']
        if row < len(self.city_matrix)-1:
            # 在南边的行中寻找相同列或最近列的城市
            south_row = self.city_matrix[row+1]
            if col < len(south_row):
                return south_row[col]
            elif len(south_row) > 0:
                return south_row[-1]  # 返回该行最东边的城市
        return None
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
        print("River Towns:", self.get_river_towns)
        print("Non-River Towns:", self.get_non_river_towns)

    def initialize_map(self):
        self.initialize_river()
        self.initialize_city_matrix()


if __name__ == "__main__":
    # 初始化地图
    map = Map(width=100, height=150)  # 调整尺寸以适应中国地图比例
    map.initialize_map()

    # 打印地图信息
    map.print_map()

    # 可视化地图
    map.visualize_map()

    # 更新运河状态并重新可视化
    map.update_river_condition(year=1850)
    map.visualize_map()