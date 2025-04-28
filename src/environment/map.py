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
    
    def initialize_city_matrix(self):
        """
        初始化城市矩阵，矩阵的行列对应南北和东西方向，城市字典记录详细信息。
        """
        all_cities = self._prepare_cities()
        tolerance = 5

        # 按纬度（y）分组，每组内的城市y坐标差异在容差内
        latitude_groups = self._group_cities(all_cities, 'y', tolerance)

        city_matrix = []
        city_dict = {}

        # 处理每个纬度组（矩阵的行）
        for row_idx, lat_group in enumerate(latitude_groups):
            # 按经度（x）分组，每组内的城市x坐标差异在容差内
            longitude_groups = self._group_cities(lat_group, 'x', tolerance)

            # 生成当前行的代表城市并排序
            row_cities = [
                self._select_representative(lon_group) 
                for lon_group in longitude_groups
                if lon_group  # 过滤空组
            ]
            row_cities_sorted = sorted(row_cities, key=lambda c: c['x'])

            # 构建矩阵行和更新字典
            matrix_row = [city['name'] for city in row_cities_sorted]
            city_matrix.append(matrix_row)
            for col_idx, city in enumerate(row_cities_sorted):
                city_dict[city['name']] = {
                    'matrix_pos': (row_idx, col_idx),
                    'location': (city['x'], city['y']),
                    'type': city['type']
                }

        self.city_matrix = city_matrix
        self.city_dict = city_dict



    def _group_cities(self, cities, coord_key, tolerance):
        """将城市按坐标分组，容差内归为一组，返回分组列表"""
        if not cities:
            return []
        sorted_cities = sorted(cities, key=lambda c: c[coord_key])
        groups = []
        current_group = [sorted_cities[0]]
        base_coord = sorted_cities[0][coord_key]

        for city in sorted_cities[1:]:
            if abs(city[coord_key] - base_coord) <= tolerance:
                current_group.append(city)
            else:
                groups.append(current_group)
                current_group = [city]
                base_coord = city[coord_key]
        groups.append(current_group)
        return groups

    def _select_representative(self, city_group):
        """从同组中选择离基准点最近的城市作为代表"""
        base_x = city_group[0]['x']
        return min(city_group, key=lambda c: abs(c['x'] - base_x))

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
                return (x, y), f"town_{x}_{y}"

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
        print("city_matrix:", self.city_matrix)
        print("city_dict:", self.city_dict)
        # 打印城市矩阵
        self.print_city_matrix()

    def print_city_matrix(self):
        """
        以矩阵形式可视化城市矩阵，用于测试
        """
        if not self.city_matrix:
            print("城市矩阵为空")
            return
            
        # 获取最大列数，用于对齐
        max_name_length = max(
            max(len(city) if city else 0 for city in row)
            for row in self.city_matrix
        )
        
        # 打印矩阵
        print("\n城市矩阵 (北→南, 西→东):")
        print("-" * (max_name_length + 4) * len(self.city_matrix[0]))
        
        for row in self.city_matrix:
            # 打印每个城市，保持对齐
            row_str = ""
            for city in row:
                if city:
                    row_str += f"| {city:<{max_name_length}} "
                else:
                    row_str += f"| {'*':<{max_name_length}} "
            row_str += "|"
            print(row_str)
            print("-" * (max_name_length + 4) * len(row))

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
    # map.update_river_condition(year=1850)
    map.visualize_map()