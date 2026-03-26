from __future__ import annotations

import json
import asyncio
import random
from typing import Dict, Optional, Any, TYPE_CHECKING
import yaml
from src.agents.resident import Resident, ResidentSharedInformationPool
from src.environment.map import Map
from src.generator.resident_generate import generate_resident_data, save_resident_data

if TYPE_CHECKING:
    from src.influences import InfluenceRegistry

async def generate_canal_agents(
    resident_info_path: str,  # 居民信息文件的路径
    map: Map,  # 地图对象，用于分配居民的位置
    initial_population: int = 10,  # 初始人口数量
    agent_graph: Optional[Dict[int, Resident]] = None,  # 居民图，默认为空
    shared_pool: Optional[ResidentSharedInformationPool] = None, # 共享资源池，默认为空
    resident_id_mapping: Optional[Dict[int, int]] = None,  # 居民 ID 与 Agent ID 的映射关系，默认为空
    resident_prompt_path: Optional[str] = None,  # 居民提示语文件路径，默认为空
    resident_actions_path: Optional[str] = None,  # 居民行为配置文件路径，默认为空
    window_size: int = 3,
    influence_registry: Optional[InfluenceRegistry] = None,
) -> Dict[int, Resident]:
    """
    生成并返回运河居民的居民图。
    """
    import time as time_module
    start_time = time_module.time()
    print(f"[居民生成] 开始生成居民...")
    
    if resident_id_mapping is None:
        resident_id_mapping = {}  # 初始化居民 ID 与 Agent ID 的映射字典
    if agent_graph is None:
        agent_graph = {}  # 初始化居民图
    if shared_pool is None:
        shared_pool = ResidentSharedInformationPool()  # 初始化共享资源池

    # 预加载配置文件
    with open(resident_prompt_path, 'r', encoding='utf-8') as file:
        prompts_resident = yaml.safe_load(file)
    with open(resident_actions_path, 'r', encoding='utf-8') as file:
        actions_config = yaml.safe_load(file)

    # 读取居民信息文件
    with open(resident_info_path, "r", encoding="utf-8", errors='ignore') as file:
        resident_info = json.load(file)
        # 确保不超过文件中的数据总量
        initial_population = min(initial_population, len(resident_info))
        # 只取需要的数量
        resident_info = resident_info[:initial_population]

    # 使用并发批量创建居民对象
    
    # 定义创建单个居民的函数
    def create_single_resident(i, resident_data):
        resident_id = i + 1

        # 获取位置和城镇ID
        location, town_name = assign_resident_location(resident_data, map)
        
        # 创建居民对象（轻量级模式，不创建重量级对象）
        resident = Resident(
            resident_id=resident_id,
            job_market=None,
            shared_pool=shared_pool,
            map=map,
            prompts_resident=prompts_resident,
            actions_config=actions_config,
            window_size=window_size,
            lightweight=True,  # 关键：使用轻量级初始化
            influence_registry=influence_registry,
        )
        
        # 设置居民的初始属性
        resident.income = resident_data["income"]  # 收入
        resident.satisfaction = resident_data["satisfaction"]
        resident.health_index = resident_data["health_index"]  # 健康状况
        resident.lifespan = resident_data["lifespan"]  # 寿命
        resident.town = town_name
        resident.location = location
        resident.personality = resident_data["personality"]
        
        return resident_id, resident
    
    # 使用线程池并发创建（因为Resident.__init__不是异步的）
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import os
    
    if initial_population == 0:
        return agent_graph

    # 根据CPU核心数确定线程数，但不超过居民数量
    max_workers = min(os.cpu_count() * 2, initial_population, 32)  # 最多32个线程
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_index = {
            executor.submit(create_single_resident, i, resident_data): i 
            for i, resident_data in enumerate(resident_info)
        }
        
        # 收集结果
        for future in as_completed(future_to_index):
            try:
                resident_id, resident = future.result()
                agent_graph[resident_id] = resident
                resident_id_mapping[resident_id] = resident_id
                
                completed += 1

            except Exception as e:
                print(f"[居民生成] 创建居民失败: {e}")
                import traceback
                traceback.print_exc()

    total_time = time_module.time() - start_time
    print(f"[居民生成] 全部居民创建完成，总耗时: {total_time:.2f}秒")
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
    
    town_name = None
    location = None

    if resident_data["residence"] == "沿河":
        if canal_towns:
            town_name = random.choice(canal_towns)
    else:
        if non_canal_towns:
            town_name = random.choice(non_canal_towns)
    
    if town_name:
        location = map.generate_random_location(town_name)
    else:
        # 如果没有合适的城镇，则随机选择一个城镇
        all_towns = list(map.town_dict.keys())
        if all_towns:
            town_name = random.choice(all_towns)
            location = map.generate_random_location(town_name)
        else:
            # 如果没有任何城镇，返回默认值或抛出错误
            # 这里选择返回一个默认的无效位置和城镇名，或者可以根据需求抛出异常
            return (0, 0), "UnknownTown"

    return location, town_name

async def generate_new_residents(
    count,
    map,
    residents,
    social_network,
    resident_prompt_path,
    resident_actions_path,
    influence_registry: Optional[InfluenceRegistry] = None,
):
    """生成新居民并初始化"""
    # 生成居民数据
    resident_data = generate_resident_data(count)
    new_resident_info_path = 'experiment_dataset/resident_data/new_resident_data.json'
    save_resident_data(resident_data, new_resident_info_path)

    # 生成居民实例
    new_residents = await generate_canal_agents(
        resident_info_path=new_resident_info_path,
        map=map,
        resident_prompt_path=resident_prompt_path,
        resident_actions_path=resident_actions_path,
        influence_registry=influence_registry,
    )

    # 分配新ID
    used_ids = set(residents.keys())
    if social_network is not None:
        used_ids |= set(social_network.hetero_graph.graph.nodes())
    new_id = max(used_ids) + 1 if used_ids else 1
    
    new_residents_with_new_ids = {}
    for i, (_, resident) in enumerate(new_residents.items()):
        while new_id in used_ids:  # 确保ID不重复
            new_id += 1
        resident.resident_id = new_id
        new_residents_with_new_ids[new_id] = resident
        used_ids.add(new_id)
        new_id += 1
        
    return new_residents_with_new_ids