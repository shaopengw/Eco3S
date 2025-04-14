import json
import asyncio
import random
from typing import Dict, Optional
from src.agents.resident import Resident, ResidentSharedInformationPool
from src.environment.job_market import JobMarket
from src.environment.map import Map

async def generate_canal_agents(
    resident_info_path: str,  # 居民信息文件的路径
    map: Map,  # 地图对象，用于分配居民的位置
    job_market: JobMarket,  # 就业市场对象，用于居民找工作
    agent_graph: Optional[Dict[int, Resident]] = None,  # 居民图，默认为空
    shared_pool: Optional[ResidentSharedInformationPool] = None, # 共享资源池，默认为空
    resident_id_mapping: Optional[Dict[int, int]] = None,  # 居民 ID 与 Agent ID 的映射关系，默认为空
    model_type: str = "gpt-3.5-turbo",  # 模型类型，默认为 GPT-3.5-turbo
) -> Dict[int, Resident]:
    """
    生成并返回运河居民的居民图。

    参数:
        resident_info_path (str): 居民信息文件的路径。
        map (Map): 地图对象，用于分配居民的位置。
        job_market (JobMarket): 就业市场对象，用于居民找工作。
        agent_graph (Dict[int, Resident], 可选): 居民图，默认为空。
        resident_id_mapping (Dict[int, int], 可选): 居民 ID 与 Agent ID 的映射关系，默认为空。
        model_type (str, 可选): 模型类型，默认为 "gpt-3.5-turbo"。

    返回:
        Dict[int, Resident]: 生成的居民图。
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

    async def process_resident(i, resident_data):
        # 居民的唯一标识符
        resident_id = i + 1

        # 获取位置和城镇ID
        location, town_id = assign_resident_location(resident_data, map)
        
        # 创建居民对象
        resident = Resident(
            resident_id=resident_id,
            job_market=job_market,
            shared_pool=shared_pool,
        )

        # 设置居民的初始属性
        resident.income = resident_data["income"]  # 收入
        resident.satisfaction = resident_data["satisfaction"]
        resident.health_index = resident_data["health_index"]  # 健康状况
        resident.lifespan = resident_data["lifespan"]  # 寿命
        resident.town = town_id
        resident.location = location

        # 如果居民有职业，分配工作
        if resident_data["profession"] != "其他":
            resident.employ(resident_data["profession"])

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
    :return: ((x, y), town_id) 坐标元组和城镇ID
    """
    # 定义正态分布的标准差（控制聚集程度）
    sigma = 2.0
    
    if resident_data["residence"] == "沿河":
        # 从沿河城市中随机选择一个
        town = map.get_market_towns()
        town_idx = random.randint(0, len(town) - 1)
        center_x, center_y = town[town_idx]
        town_id = f"market_town_{town_idx}"
    else:
        # 从非沿河城市中随机选择一个
        town = map.get_non_river_towns()
        town_idx = random.randint(0, len(town) - 1)
        center_x, center_y = town[town_idx]
        town_id = f"non_river_town_{town_idx}"
    
    # 在城市中心周围生成正态分布的随机位置
    while True:
        # 生成正态分布的偏移量
        offset_x = int(random.gauss(0, sigma))
        offset_y = int(random.gauss(0, sigma))
        
        # 计算实际位置
        x = center_x + offset_x
        y = center_y + offset_y
        
        # 确保位置在地图范围内
        if 0 <= x < map.width and 0 <= y < map.height:
            # 对于沿河居民，确保位置在河流附近（可选）
            if resident_data["residence"] != "沿河" or map.is_river_nearby((x, y)):
                return ((x, y), town_id)
            # 如果沿河居民位置不在河流附近，则继续循环生成新位置
        # 如果位置超出地图范围，则继续循环生成新位置