import json
import asyncio
from typing import Dict, Optional
from src.agents.rebels import OrdinaryRebel, RebelLeader, rebels_SharedInformationPool
from src.agents.rebels import Rebellion

async def generate_rebels_agents(
    rebellion_info_path: str,
    rebellion: Rebellion,
    agent_graph: Optional[Dict[int, OrdinaryRebel]] = None,
    agent_id_mapping: Optional[Dict[int, int]] = None,
    model_type: str = "gpt-3.5-turbo",
    shared_pool: Optional[rebels_SharedInformationPool] = None,
) -> Dict[int, OrdinaryRebel]:
    """
    生成并返回叛军的叛军图。

    参数:
        rebellion_info_path (str): 叛军信息文件的路径。
        rebellion (Rebellion): 叛军对象，用于关联叛军。
        agent_graph (Dict[int, OrdinaryRebel], 可选): 叛军图，默认为空。
        agent_id_mapping (Dict[int, int], 可选): 叛军 ID 与 Agent ID 的映射关系，默认为空。
        model_type (str, 可选): 模型类型，默认为 "gpt-3.5-turbo"。
        shared_pool (rebels_SharedInformationPool, 可选): 共享信息池，默认为空。

    返回:
        Dict[int, OrdinaryRebel]: 生成的叛军图。
    """
    if agent_id_mapping is None:
        agent_id_mapping = {}
    if agent_graph is None:
        agent_graph = {}
    if shared_pool is None:
        shared_pool = rebels_SharedInformationPool()

    # 读取叛军信息文件
    with open(rebellion_info_path, "r", encoding="utf-8", errors='ignore') as file:
        rebellion_info = json.load(file)

    async def process_rebel(i, rebel_data):
        """处理单个叛军的生成和注册"""
        agent_id = i + 1

        # 根据叛军类型创建对象
        if rebel_data["rank"] == "普通叛军":
            rebel = OrdinaryRebel(
                agent_id=agent_id,
                rebellion=rebellion,
                shared_pool=shared_pool,
            )
        elif rebel_data["rank"] == "叛军头子":
            rebel = RebelLeader(
                agent_id=agent_id,
                rebellion=rebellion,
                shared_pool=shared_pool,
            )
        else:
            raise ValueError(f"未知的叛军类型：{rebel_data['rank']}")

        # 设置叛军的初始属性
        rebel.role = rebel_data["role"]  # 角色
        rebel.mbti = rebel_data["mbti"]  # 人物性格

        # 将叛军添加到叛军图
        agent_graph[agent_id] = rebel

        # 将叛军 ID 与 Agent ID 映射
        agent_id_mapping[agent_id] = agent_id

        # 记录叛军生成日志
        # rebel.logger.info(f"{rebel_data['rank']} {agent_id} 生成成功。")

    # 创建并执行叛军生成任务
    tasks = [process_rebel(i, rebel_data) for i, rebel_data in enumerate(rebellion_info)]
    await asyncio.gather(*tasks)

    # 确保返回的 agent_graph 包含有效叛军对象
    if not all(isinstance(rebel, (OrdinaryRebel, RebelLeader)) for rebel in agent_graph.values()):
        raise TypeError("agent_graph 中包含非法对象")
    
    return agent_graph  # 返回生成的叛军图