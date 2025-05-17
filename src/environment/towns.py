from collections import defaultdict
from typing import Dict, List, Any
from src.agents.resident import ResidentGroup
from src.environment.job_market import JobMarket
import random

class Towns:
    def __init__(self, map, initial_population=10):
        self.towns = defaultdict(lambda: {
            'info': {},
            'residents': {},
            'resident_group': None,
            'job_market': None
        })
        self.initialize_towns(map, initial_population)

    def initialize_towns(self, map, initial_population):
        """初始化所有城镇信息"""
        # 首先计算城镇总数
        total_towns = len(map.town_dict)
        if total_towns == 0:
            print("警告: 地图中没有城镇")
            return
        
        # 计算每个城镇的初始人口，确保为整数
        residents_per_town = int(initial_population / total_towns)
        # 处理除不尽的情况，将剩余人口分配给第一个城镇
        remaining_residents = initial_population - (residents_per_town * total_towns)
        
        for i, (town_name, town_info) in enumerate(map.town_dict.items()):
            x, y = town_info['location']
            # 确保坐标在有效范围内
            if not (0 <= x < map.width and 0 <= y < map.height):
                print(f"警告: 城市 {town_name} 的坐标 ({x}, {y}) 超出地图范围")
                continue
                
            town_info = {
                'name': town_name,
                'location': town_info['location'],
                'type': town_info['type']
            }
            
            # 检查位置信息是否完整
            if None in town_info['location']:
                print(f"警告: 城市 {town_name} 的位置信息不完整")
                continue
                
            self.towns[town_name]['info'] = town_info
            self.towns[town_name]['resident_group'] = ResidentGroup(town_name)
            
            # 根据城镇类型初始化就业市场
            town_type = "沿河" if town_info['type'] == 'canal' else "非沿河"
            # 为第一个城镇添加剩余人口
            current_town_population = residents_per_town + (remaining_residents if i == 0 else 0)
            self.towns[town_name]['job_market'] = JobMarket(town_type=town_type, initial_jobs_count=current_town_population)

    def initialize_resident_groups(self, residents: Dict[int, 'Resident']):
        """
        根据居民的town属性初始化居民群组并分配工作
        :param residents: 居民字典，key为居民ID，value为居民对象
        """


        # 根据居民的town属性进行分组并同时分配工作
        for resident_id, resident in residents.items():
            if resident.town:
                town_name = resident.town
                
                if town_name:
                    # 添加居民到城镇
                    self.add_resident(resident, town_name)

                    # 计算当前城镇的就业率
                    town_data = self.towns[town_name]
                    current_employed = sum(len(info["employed"]) for info in town_data['job_market'].jobs_info.values())
                    total_residents = len(town_data['residents'])
                    employment_rate = current_employed / total_residents if total_residents > 0 else 0
                    
                    # 如果就业率低于90%，尝试为该居民分配工作
                    if employment_rate < 0.9:
                        if town_data['job_market']:
                            town_data['job_market'].get_job(resident)
                        else:
                            print(f"警告: 城镇 {town_data['info']['name']} 没有就业市场")
                else:
                    print(f"警告: 无法找到居民 {resident_id} 所在的城镇 {resident.town}")
    
    def add_resident(self, resident, town_name):
        """添加居民到指定城镇"""
        self.towns[town_name]['residents'][resident.resident_id] = resident
        if self.towns[town_name]['resident_group'] is None:
            self.towns[town_name]['resident_group'] = ResidentGroup(town_name)
        self.towns[town_name]['resident_group'].add_resident(resident)

    def get_nearest_town(self, location):
        """获取最近的城镇名称"""
        min_distance = float('inf')
        nearest_town_name = None
        
        for town_name, town_data in self.towns.items():
            town_loc = town_data['info']['location']
            distance = ((location[0] - town_loc[0]) ** 2 + 
                       (location[1] - town_loc[1]) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_town_name = town_name
        
        return nearest_town_name

    def get_town_residents(self, town_name):
        """获取指定城镇的所有居民"""
        return self.towns[town_name]['residents']

    def get_hometown_group(self, town_name):
        """获取指定城镇的同乡群组ID"""
        return self.towns[town_name].get('hometown_group')

    def update_hometown_group(self, town_name, group_id):
        """更新城镇的同乡群组ID"""
        self.towns[town_name]['hometown_group'] = group_id

    def get_town_job_market(self, town_name):
        """获取指定城镇的就业市场"""
        return self.towns[town_name]['job_market']

    def print_towns_status(self):
        """打印所有城镇状态"""
        for town_name, town_data in self.towns.items():
            print(f"\n城镇 {town_name} 状态:")
            print(f"中心位置: {town_data['info']['location']}")
            print(f"类型: {town_data['info']['type']}")
            print(f"居民数量: {len(town_data['residents'])}")
            print("就业市场状态:")
            town_data['job_market'].print_job_market_status()

    def remove_jobs_across_towns(self, total_jobs_to_remove):
        """
        将要减少的岗位均匀分布给所有城镇
        :param total_jobs_to_remove: 需要减少的总岗位数量
        """
        # 获取所有城镇数量
        total_towns = len(self.towns)
        if total_towns == 0:
            print("警告: 没有可用的城镇")
            return

        # 计算每个城镇需要减少的岗位数量，确保为整数
        jobs_per_town = int(total_jobs_to_remove / total_towns)
        # 处理除不尽的情况，将剩余岗位分配给第一个城镇
        remaining_jobs = total_jobs_to_remove - (jobs_per_town * total_towns)

        # 遍历所有城镇并减少岗位
        for i, (town_name, town_data) in enumerate(self.towns.items()):
            if town_data['job_market']:
                # 为第一个城镇添加剩余岗位
                current_town_jobs = jobs_per_town + (remaining_jobs if i == 0 else 0)
                town_data['job_market'].remove_random_jobs(current_town_jobs)
            else:
                print(f"警告: 城镇 {town_name} 没有就业市场")

        print(f"已在所有城镇中均匀减少总计 {total_jobs_to_remove} 个工作岗位")