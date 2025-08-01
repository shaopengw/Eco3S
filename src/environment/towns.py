from collections import defaultdict
from typing import Dict
from src.agents.resident import ResidentGroup
from src.environment.job_market import JobMarket
import random

class Towns:
    def __init__(self, map, initial_population=10):
        self.towns = defaultdict(self._create_town_dict)
        self.initialize_towns(map, initial_population)
    
    def _create_town_dict(self):
        """创建一个新的城镇字典结构"""
        return {
            'info': {},
            'residents': {},
            'resident_group': None,
            'job_market': None
        }

    def initialize_towns(self, map, initial_population):
        """初始化所有城镇信息"""
        # 首先计算城镇总数
        total_towns = len(map.town_dict)
        if total_towns == 0:
            print("警告: 地图中没有城镇")
            return
        
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
            
            # 初始化就业市场
            town_type = "沿河" if town_info['type'] == 'canal' else "非沿河"
            # 计算每个城镇的初始人口
            if initial_population < total_towns:
                residents_per_town = 1
                remaining_residents = 0
            else:
                residents_per_town = int(initial_population / total_towns)
                # 处理除不尽的情况，将剩余人口分配给第一个城镇
                remaining_residents = initial_population - (residents_per_town * total_towns)
            current_town_population = residents_per_town + (1 if i < remaining_residents else 0)
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

                    # 分配工作
                    town_data = self.towns[town_name]
                    if town_data['job_market']:
                        town_data['job_market'].assign_job(resident)
                        # print(f"居民 {resident_id} 尝试为城镇 {town_name} 分配工作")
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
        resident.set_town(town_name, self)

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

    def print_towns(self):
        """打印所有城镇状态"""
        river_town_residents = 0
        non_river_town_residents = 0

        for town_name, town_data in self.towns.items():
            # print(f"\n城镇 {town_name} 状态:")
            # print(f"中心位置: {town_data['info']['location']}")
            # print(f"类型: {town_data['info']['type']}")
            # print(f"居民数量: {len(town_data['residents'])}")
            # print("就业市场状态:")
            # town_data['job_market'].print_job_market_status()

            if town_data['info']['type'] == 'canal':
                river_town_residents += len(town_data['residents'])
            else:
                non_river_town_residents += len(town_data['residents'])

        print(f"\n沿河城镇总居民数量: {river_town_residents}")
        print(f"非沿河城镇总居民数量: {non_river_town_residents}")


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

    def process_town_job_requests(self, town_job_requests):
        """
        处理城镇的求职信息
        :param town_job_requests: 字典，键为城镇名称，值为该城镇的求职请求列表
        """
        results = {}
        for town_name, requests in town_job_requests.items():
            if town_name not in self.towns:
                print(f"警告：城镇 {town_name} 不存在")
                continue
                
            job_market = self.towns[town_name]['job_market']
            if not job_market:
                print(f"警告：城镇 {town_name} 没有就业市场")
                continue
            
            # 为每个请求添加居民对象信息
            complete_requests = []
            for request in requests:
                resident_id = request.get("resident_id")
                if resident_id in self.towns[town_name]['residents']:
                    resident = self.towns[town_name]['residents'][resident_id]
                    complete_requests.append({
                        "resident": resident,
                        "desired_job": request["desired_job"],
                        "min_salary": request["min_salary"]
                    })
            # 处理该城镇的所有求职申请
            hired_residents = job_market.process_job_applications(complete_requests)
            results[town_name] = hired_residents
            
        return results

    def remove_resident_in_town(self, resident_id, town_name, job_type=None):
        """
        处理居民删除逻辑
        :param resident_id: 居民ID
        :param town_name: 城镇名称
        :param job_type: 工作类型（可选）
        :return: 是否成功删除
        """
        if town_name not in self.towns:
            print(f"警告：城镇 {town_name} 不存在")
            return False
            
        town_data = self.towns[town_name]
        
        # 从就业市场中移除
        if town_data['job_market']:
            town_data['job_market'].remove_resident(resident_id, job_type)
            
        # 从城镇居民列表中移除
        if resident_id in town_data['residents']:
            del town_data['residents'][resident_id]
            
        # 从居民群组中移除
        if town_data['resident_group']:
            town_data['resident_group'].remove_resident(resident_id)
            
        return True

    def adjust_job_market(self, change_rate, residents):
        """
        更新所有城镇的就业市场
        :param change_rate: 运河状态的变化率（-1到1之间的值）
        :param residents: 居民字典，key为居民ID，value为居民对象
        """
        for town_name, town_data in self.towns.items():
            # 获取城镇的就业市场
            job_market = town_data['job_market']
            if job_market:
                # 调用就业市场的调整方法
                job_market.adjust_canal_maintenance_jobs(change_rate, residents)
            else:
                print(f"警告：城镇 {town_name} 没有就业市场")

    def add_jobs_across_towns(self, add_job_amount,specific_job=None):
        """
        将要增加的岗位均匀分布给所有城镇
        :param add_job_amount: 需要增加的总岗位数量
        :param specific_job: 指定的工作类型（可选）
        """
        # 获取所有城镇数量
        total_towns = len(self.towns)
        if total_towns == 0:
            print("警告: 没有可用的城镇")
            return

        # 如果岗位数小于城镇数，随机选取岗位数个城镇来增加工作岗位
        if add_job_amount < total_towns:
            selected_towns = random.sample(list(self.towns.items()), add_job_amount)
        else:
            # 平均分配岗位数量给所有城镇
            jobs_per_town = int(add_job_amount / total_towns)
            remaining_jobs = add_job_amount - (jobs_per_town * total_towns)
            selected_towns = list(self.towns.items())

        # 遍历所有选中的城镇并增加岗位
        for i, (town_name, town_data) in enumerate(selected_towns):
            if town_data['job_market']:
                # 为第一个城镇添加剩余岗位
                if add_job_amount < total_towns:
                    current_town_jobs = 1
                else:
                    current_town_jobs = jobs_per_town + (remaining_jobs if i == 0 else 0)
                town_data['job_market'].add_random_jobs(current_town_jobs, specific_job)
            else:
                print(f"警告: 城镇 {town_name} 没有就业市场")

        print(f"已在所有城镇中均匀增加总计 {add_job_amount} 个工作岗位")

    def add_specific_job(self, add_job_amount, town_type, job_name):
        """
        在特定类型的城镇中随机增加指定数量的工作岗位，并指定工作岗位的名称
        :param add_job_amount: 需要增加的总岗位数量
        :param town_type: 城镇类型
        :param job_name: 指定的工作岗位名称
        """
        # 获取所有指定类型的城镇
        specific_towns = [(town_name, town_data) for town_name, town_data in self.towns.items() if town_data['info']['type'] == town_type]

        # 获取指定类型的城镇数量
        total_specific_towns = len(specific_towns)
        if total_specific_towns == 0:
            print(f"警告: 没有可用的 {town_type} 城镇")
            return

        # 如果岗位数小于城镇数，随机选取岗位数个城镇来增加工作岗位
        if add_job_amount < total_specific_towns:
            selected_towns = random.sample(specific_towns, add_job_amount)
            jobs_per_town = 1
            remaining_jobs = 0
        else:
            # 平均分配岗位数量给所有城镇
            jobs_per_town = add_job_amount // total_specific_towns
            remaining_jobs = add_job_amount - (jobs_per_town * total_specific_towns)
            selected_towns = specific_towns

        # 遍历所有选中的城镇并增加岗位
        for i, (town_name, town_data) in enumerate(selected_towns):
            job_market = town_data['job_market']
            if job_market:
                # 计算当前城镇需要增加的岗位数
                if add_job_amount < total_specific_towns:
                    current_town_jobs = 1
                elif i == 0:
                    current_town_jobs = jobs_per_town + remaining_jobs
                else:
                    current_town_jobs = jobs_per_town
                
                # 增加工作岗位
                job_market.add_job(job_name, current_town_jobs)
            else:
                print(f"警告: 城镇 {town_name} 没有就业市场")
        print(f"已在 {town_type} 城镇中均匀增加总计 {add_job_amount} 个工作岗位 {job_name}")
