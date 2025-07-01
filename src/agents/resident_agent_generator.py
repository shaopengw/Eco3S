import json
import asyncio
import random
from typing import Dict, Optional
from src.agents.resident import Resident, ResidentSharedInformationPool
from src.environment.map import Map

async def generate_canal_agents(
    resident_info_path: str,  # 居民信息文件的路径
    map: Map,  # 地图对象，用于分配居民的位置
    initial_population: int = 10,  # 初始人口数量
    agent_graph: Optional[Dict[int, Resident]] = None,  # 居民图，默认为空
    shared_pool: Optional[ResidentSharedInformationPool] = None, # 共享资源池，默认为空
    resident_id_mapping: Optional[Dict[int, int]] = None,  # 居民 ID 与 Agent ID 的映射关系，默认为空
) -> Dict[int, Resident]:
    """
    生成并返回运河居民的居民图。
    """
    if resident_id_mapping is None:
        resident_id_mapping = {}  # 初始化居民 ID 与 Agent ID 的映射字典
    if agent_graph is None:
        agent_graph = {}  # 初始化居民图
    if shared_pool is None:
        shared_pool = ResidentSharedInformationPool()  # 初始化共享资源池

    # 读取居民信息文件
    with open(resident_info_path, "r", encoding="utf-8", errors='ignore') as file:
        resident_info = json.load(file)
        # 确保不超过文件中的数据总量
        initial_population = min(initial_population, len(resident_info))
        # 只取需要的数量
        resident_info = resident_info[:initial_population]

    async def process_resident(i, resident_data):
        # 居民的唯一标识符
        resident_id = i + 1

        # 获取位置和城镇ID
        location, town_name = assign_resident_location(resident_data, map)
        
        # 创建居民对象
        resident = Resident(
            resident_id=resident_id,
            job_market=None,
            shared_pool=shared_pool,
            map=map
        )

        # 设置居民的初始属性
        resident.income = resident_data["income"]  # 收入
        resident.satisfaction = resident_data["satisfaction"]
        resident.health_index = resident_data["health_index"]  # 健康状况
        resident.lifespan = resident_data["lifespan"]  # 寿命
        resident.town = town_name
        resident.location = location
        resident.mbti = resident_data["mbti"]

        # 将居民添加到居民图
        agent_graph[resident_id] = resident

        # 将居民 ID 与 Agent ID 映射
        resident_id_mapping[resident_id] = resident_id

        # 记录居民生成日志
        # resident.logger.info(f"居民 {resident_id} 在 {town}{location} 生成成功。姓名：{resident_data['realname']}, 性别：{resident_data['gender']}, 职业：{resident_data['profession']}, 收入：{resident.income} 两白银, 满意度：{resident.satisfaction}, 健康状况：{resident.health_index}")

    # 创建并执行居民生成任务
    tasks = [process_resident(i, resident_data) for i, resident_data in enumerate(resident_info)]
    await asyncio.gather(*tasks)

    return agent_graph  # 返回生成的居民图


def assign_resident_location(resident_data, map):
    """
    分配居民的位置和所属城镇
    :param resident_data: 居民数据字典，包含"residence"字段
    :param map: Map类实例
    :return: ((x, y), town_name) 坐标元组和城市名称
    """
    # 从城市字典中随机选择一个城市
    canal_towns = [name for name, info in map.town_dict.items() if info['type'] == 'canal']
    non_canal_towns = [name for name, info in map.town_dict.items() if info['type'] == 'non_canal']
    
    if resident_data["residence"] == "沿河":
        if not canal_towns:
            return None
        town_name = random.choice(canal_towns)
    else:
        if not non_canal_towns:
            return None
        town_name = random.choice(non_canal_towns)
    
    location = map.generate_random_location(town_name)
    return location, town_name