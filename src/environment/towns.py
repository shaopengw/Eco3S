from collections import defaultdict
from typing import Dict, List, Any
from src.agents.resident import ResidentGroup
from src.environment.job_market import JobMarket

class Towns:
    def __init__(self, map):
        self.towns = defaultdict(lambda: {
            'info': {},
            'residents': {},
            'resident_group': None,
            'job_market': None
        })
        self.initialize_towns(map)
    
    def initialize_towns(self, map):
        """初始化所有城镇信息"""
        for city_name, city_info in map.city_dict.items():
            x, y = city_info['location']
            town_id = f"town_{x}_{y}"
            town_info = {
                'id': town_id,
                'name': city_name,
                'location': city_info['location'],
                'type': city_info['type']
            }
            self.towns[town_id]['info'] = town_info
            self.towns[town_id]['resident_group'] = ResidentGroup(town_id)
            self.towns[town_id]['job_market'] = JobMarket()  # 为每个城镇创建独立的就业市场
    
    def initialize_resident_groups(self, residents: Dict[int, 'Resident']):
        """
        根据居民的town属性初始化居民群组
        :param residents: 居民字典，key为居民ID，value为居民对象
        """
        # 根据居民的town属性进行分组
        for resident_id, resident in residents.items():
            if resident.town and resident_id not in self.towns[resident.town]['residents']:
                self.add_resident(resident, resident.town)
    
    def add_resident(self, resident, town_id):
        """添加居民到指定城镇"""
        self.towns[town_id]['residents'][resident.resident_id] = resident
        if self.towns[town_id]['resident_group'] is None:
            self.towns[town_id]['resident_group'] = ResidentGroup(town_id)
        self.towns[town_id]['resident_group'].add_resident(resident)
    
    def get_nearest_town(self, location):
        """获取最近的城镇ID"""
        min_distance = float('inf')
        nearest_town_id = None
        
        for town_id, town_data in self.towns.items():
            town_loc = town_data['info']['location']
            distance = ((location[0] - town_loc[0]) ** 2 + 
                       (location[1] - town_loc[1]) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_town_id = town_id
        
        return nearest_town_id
    
    def get_town_residents(self, town_id):
        """获取指定城镇的所有居民"""
        return self.towns[town_id]['residents']

    def get_hometown_group(self, town_id):
        """获取指定城镇的同乡群组ID"""
        return self.towns[town_id].get('hometown_group')

    def update_hometown_group(self, town_id, group_id):
        """更新城镇的同乡群组ID"""
        self.towns[town_id]['hometown_group'] = group_id

    def get_town_job_market(self, town_id):
        """获取指定城镇的就业市场"""
        return self.towns[town_id]['job_market']

    def print_towns_status(self):
        """打印所有城镇状态"""
        for town_id, town_data in self.towns.items():
            print(f"\n城镇 {town_data['info']['name']} ({town_id}) 状态:")
            print(f"位置: {town_data['info']['location']}")
            print(f"类型: {town_data['info']['type']}")
            print(f"居民数量: {len(town_data['residents'])}")
            print("就业市场状态:")
            town_data['job_market'].print_job_market_status()