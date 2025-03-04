import json
import asyncio
import random
from typing import Dict, Optional
from src.agents.resident import Resident
from src.environment.job_market import JobMarket
from src.environment.map import Map

async def generate_canal_agents(
    resident_info_path: str,  # 居民信息文件的路径
    map: Map,  # 地图对象，用于分配居民的位置
    job_market: JobMarket,  # 就业市场对象，用于居民找工作
    agent_graph: Optional[Dict[int, Resident]] = None,  # 居民图，默认为空
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

    # 读取居民信息文件
    with open(resident_info_path, "r", encoding="utf-8", errors='ignore') as file:
        resident_info = json.load(file)

    async def process_resident(i, resident_data):
        """
        处理单个居民的生成和注册。
        """
        # 居民的唯一标识符
        resident_id = i + 1

        # 分配居民的位置
        if resident_data["residence"] == "沿河":
            location = (random.randint(0, map.size - 1), map.size // 2)  # 沿河区域
        else:
            location = (random.randint(0, map.size - 1), random.randint(0, map.size - 1))  # 非沿河区域

        # 创建居民对象
        resident = Resident(
            resident_id=resident_id,
            location=location,
            job_market=job_market,
            model_type=model_type,
        )

        # 设置居民的初始属性
        resident.income = resident_data["income"]  # 收入
        resident.satisfaction = resident_data["satisfaction"]
        resident.health_index = resident_data["health_index"]  # 健康状况
        resident.lifespan = resident_data["lifespan"]  # 寿命

        # 如果居民有职业，分配工作
        if resident_data["profession"] != "其他":
            resident.employ(resident_data["profession"])

        # 将居民添加到居民图
        agent_graph[resident_id] = resident

        # 将居民 ID 与 Agent ID 映射
        resident_id_mapping[resident_id] = resident_id

        # 记录居民生成日志
        resident.logger.info(f"居民 {resident_id} 在 {location} 生成成功。姓名：{resident_data['realname']}, 性别：{resident_data['gender']}, 职业：{resident_data['profession']}, 收入：{resident.income} 两白银, 满意度：{resident.satisfaction}, 健康状况：{resident.health_index}")

    # 创建并执行居民生成任务
    tasks = [process_resident(i, resident_data) for i, resident_data in enumerate(resident_info)]
    await asyncio.gather(*tasks)

    return agent_graph  # 返回生成的居民图