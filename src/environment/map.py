import numpy as np
import matplotlib.pyplot as plt
import json
import math
import random
from colorama import Back

class Map:
    def __init__(self, width, height, data_file='config/towns_data.json'):
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
        self.navigability = 0.8  # 初始运河通航能力
        self.town_graph = {}  # 城市图（邻接表形式）
        self.town_dict = {}  # 存储城市信息
        self.terrain_ruggedness = np.random.rand(height, width)
        
        # 加载城市数据和地图边界
        self.load_town_data(data_file)

    def load_town_data(self, data_file):
        """
        从JSON文件加载城市数据和地图边界
        :param data_file: JSON文件路径
        """
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.town_data = data
            
            # 从配置文件加载地图边界
            boundaries = data.get('map_boundaries', {
                'min_longitude': 109.0,
                'max_longitude': 125.0,
                'min_latitude': 30.0,
                'max_latitude': 41.0
            })
            
            self.min_longitude = boundaries['min_longitude']
            self.max_longitude = boundaries['max_longitude']
            self.min_latitude = boundaries['min_latitude']
            self.max_latitude = boundaries['max_latitude']
            
        except Exception as e:
            print(f"加载城市数据失败: {e}")
            # 提供默认数据
            self.town_data = {
                "canals": [],
                "other_towns": []
            }
            # 使用默认边界
            self.min_longitude = 109.0
            self.max_longitude = 125.0
            self.min_latitude = 30.0
            self.max_latitude = 41.0

    def _prepare_towns(self):
        """转换原始城市数据为带坐标的列表"""
        towns = []
        # 处理多条运河
        for canal in self.town_data.get('canals', []):
            for town in canal.get('towns', []):
                x = self.longitude_to_x(town['longitude'])
                y = self.latitude_to_y(town['latitude'])
                towns.append({'x': x, 'y': y, 'name': town['name'], 'type': 'canal', 'river_name': canal['name']})

        # 处理其他城市
        for town in self.town_data.get('other_towns', []):
            x = self.longitude_to_x(town['longitude'])
            y = self.latitude_to_y(town['latitude'])
            towns.append({'x': x, 'y': y, 'name': town['name'], 'type': 'non_canal'})
        return towns

    def longitude_to_x(self, longitude):
        """
        将经度转换为地图x坐标
        """
        # 防止除零错误
        if self.max_longitude == self.min_longitude:
            return self.width // 2  # 返回中心点
        return int((longitude - self.min_longitude) / (self.max_longitude - self.min_longitude) * self.width)

    def latitude_to_y(self, latitude):
        """
        将纬度转换为地图y坐标
        """
        # 纬度越高，y坐标越小（北在上）
        # 防止除零错误
        if self.max_latitude == self.min_latitude:
            return self.height // 2  # 返回中心点
        return int((self.max_latitude - latitude) / (self.max_latitude - self.min_latitude) * self.height)

    def initialize_river(self):
        """
        初始化所有运河路线
        """
        self.river_grid = np.zeros((self.height, self.width))
        self.navigability = 1.0  # 重置运河通航能力
        
        # 遍历 canals 列表中的每个运河（河流）
        for canal in self.town_data.get('canals', []):
            river_points = []
            # 直接遍历运河中的城镇
            for town in canal.get('towns', []):
                x = self.longitude_to_x(town['longitude'])
                y = self.latitude_to_y(town['latitude'])
                river_points.append((x, y, town['name']))
                
            # 连接各个点形成运河
            for i in range(len(river_points) - 1):
                x1, y1, _ = river_points[i]
                x2, y2, _ = river_points[i + 1]
                steps = max(abs(x2 - x1), abs(y2 - y1)) * 2
                
                # 如果两个点相同，跳过
                if steps == 0:
                    continue
                    
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
    
    def initialize_town_graph(self, max_distance=20):
        """
        初始化城市图，通过计算城市间距离来建立连接
        :param max_distance: 最大连接距离
        """
        all_towns = self._prepare_towns()
        self.town_graph = {}
        
        # 初始化城市字典和图
        for town in all_towns:
            town_name = town['name']
            self.town_dict[town_name] = {
                'location': (town['x'], town['y']),
                'type': town['type']
            }
            self.town_graph[town_name] = []

        # 计算城市间距离并建立连接
        for town1 in all_towns:
            for town2 in all_towns:
                if town1['name'] != town2['name']:
                    distance = self._calculate_distance(
                        (town1['x'], town1['y']),
                        (town2['x'], town2['y'])
                    )
                    if distance <= max_distance:
                        self.town_graph[town1['name']].append(town2['name'])

    def _calculate_distance(self, point1, point2):
        """
        计算两点间的欧几里得距离
        """
        return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

    def get_connected_towns(self, town_name):
        """
        获取与指定城市相连的所有城市
        :param town_name: 城市名称
        :return: 相连城市列表，如果城市不存在则返回None
        """
        if town_name not in self.town_dict:
            print(f"警告：城市 {town_name} 不存在")
            return None
        return self.town_graph.get(town_name, []).copy()

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
        plt.scatter(river_x, river_y, color='blue', label='Canals', s=10) # 标签改为Canals

        # 准备城市数据
        canal_towns = []
        other_towns = []
        for town_name in self.town_dict:
            town_info = self.town_dict[town_name]
            if town_info['type'] == 'canal':
                canal_towns.append((town_info['location'][0], town_info['location'][1], town_name))
            else:
                other_towns.append((town_info['location'][0], town_info['location'][1], town_name))

        # 绘制运河城市和名称标注
        if canal_towns:
            canal_x = [town[0] for town in canal_towns]
            canal_y = [town[1] for town in canal_towns]
            plt.scatter(canal_x, canal_y, color='red', label='Canal Towns', s=50, marker='s')
            
            for x, y, name in canal_towns:
                plt.annotate(name, 
                            xy=(x, y),
                            xytext=(5, 5), 
                            textcoords='offset points',
                            fontsize=8,
                            fontproperties='SimHei',
                            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))
        
        # 绘制非运河城市和名称标注
        if other_towns:
            other_x = [town[0] for town in other_towns]
            other_y = [town[1] for town in other_towns]
            plt.scatter(other_x, other_y, color='green', label='Other towns', s=50, marker='^')
            
            for x, y, name in other_towns:
                plt.annotate(name, 
                            xy=(x, y),
                            xytext=(5, 5), 
                            textcoords='offset points',
                            fontsize=8,
                            fontproperties='SimHei',
                            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))

        plt.title("地图", fontproperties='SimHei', fontsize=14)
        plt.xlabel("经度方向", fontproperties='SimHei')
        plt.ylabel("纬度方向", fontproperties='SimHei')
        plt.legend()
        plt.show()

    def update_river_condition(self, maintenance_ratio):
        """
        根据政府维护决策更新运河状态。
        :param maintenance_ratio: 维护投入比例。
        """
        current_navigability = self.get_navigability()

        if maintenance_ratio >= 1:
            # 每增加一倍通航能力额外增加 0.1
            new_navigability = current_navigability + 0.1 * maintenance_ratio
        else:
            # 每减少一倍通航能力减少 0.2
            new_navigability = current_navigability - 0.2 * maintenance_ratio

        # 确保通航能力在 0 到 1 之间
        self.navigability = max(0, min(1.0, new_navigability))

        # 更新运河网格的状态
        self.river_grid[self.river_grid > 0] = self.navigability

        # 增加通航值低于0.2的警告
        if self.navigability < 0.2:
            print(Back.RED + f"运河已废弃，通航能力为 {self.navigability:.2f}" + Back.RESET)

        
        # 增加通航值低于0.2的警告
        if self.navigability < 0.2:
            print(Back.RED + f"运河已废弃，通航能力为 {self.navigability:.2f}" + Back.RESET)

    def decay_river_condition_naturally(self, climate_impact_factor=0):
        """
        每年根据自然衰减和气候影响自然更新运河状态。
        :param climate_impact_factor: 气候影响因子，范围[0,1]，表示气候对运河的负面影响。
        :return: 当前运河通航能力。
        """
            
        # 自然衰减和气候影响
        natural_decay_rate = 0.1
        old_navigability = self.navigability
        self.navigability = max(0, self.navigability * (1 - natural_decay_rate) - climate_impact_factor * 0.6)

        # 更新运河网格的状态
        self.river_grid[self.river_grid > 0] = self.navigability

        print(f"运河自然衰减:{old_navigability}* (1 - {natural_decay_rate}) - {climate_impact_factor} * 0.6 = {self.navigability:.2f}")

        return self.navigability

    def get_navigability(self):
        """
        获取当前运河通航能力
        :return: 通航能力值（0-1之间的浮点数）
        """
        return self.navigability

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
        for town in self.town_dict:
            if self.town_dict[town]['type'] == 'canal':
                towns.append(self.town_dict[town]['location'])
        return towns

    def get_non_river_towns(self):
        """
        获取所有非沿河城市的位置
        :return: 非沿河城市的位置列表
        """
        towns = []
        for town in self.town_dict:
            if self.town_dict[town]['type'] == 'non_canal':
                towns.append(self.town_dict[town]['location'])
        return towns
    
    def print_map(self):
        """
        打印地图（用于调试）
        """
        print("River Grid:", self.river_grid)
        print("town_graph:", self.town_graph)
        print("town_dict:", self.town_dict)

    def initialize_map(self):
        self.initialize_river()
        self.initialize_town_graph()

    def generate_random_location(self, town_name, sigma=2.0):
        """
        为指定城市生成一个随机位置
        :param town_name: 城市名称
        :param sigma: 正态分布标准差，默认2.0
        :return: (x, y) 坐标元组
        """
        if town_name not in self.town_dict:
            return None
                
        town_info = self.town_dict[town_name]
        center_x, center_y = town_info['location']
        
        attempts = 0
        max_attempts = 100  # 防止无限循环
        
        while attempts < max_attempts:
            # 生成正态分布的偏移量
            offset_x = int(random.gauss(0, sigma))
            offset_y = int(random.gauss(0, sigma))
            
            # 计算实际位置
            x = center_x + offset_x
            y = center_y + offset_y
            
            # 确保位置在地图范围内
            if 0 <= x < self.width and 0 <= y < self.height:
                return (x, y)
                
            attempts += 1
            
        # 如果多次尝试都失败，返回城市中心点
        return (center_x, center_y)


if __name__ == "__main__":
    # 初始化地图
    map = Map(width=100, height=150,data_file='config/TEOG/towns_data.json')
    map.initialize_map()

    # 打印地图信息
    map.print_map()

    # 可视化地图
    map.visualize_map()