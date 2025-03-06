import json
import asyncio
from typing import Dict, Optional
from src.agents.rebellion import OrdinaryRebel, RebelLeader
from src.agents.rebellion import Rebellion

async def generate_rebellion_agents(
    rebellion_info_path: str,  # 叛军信息文件的路径
    rebellion: Rebellion,  # 叛军对象，用于关联叛军
    agent_graph: Optional[Dict[int, OrdinaryRebel]] = None,  # 叛军图，默认为空
    rebel_id_mapping: Optional[Dict[int, int]] = None,  # 叛军 ID 与 Agent ID 的映射关系，默认为空
    model_type: str = "gpt-3.5-turbo",  # 模型类型，默认为 GPT-3.5-turbo
) -> Dict[int, OrdinaryRebel]:
    """
    生成并返回叛军的叛军图。

    参数:
        rebellion_info_path (str): 叛军信息文件的路径。
        rebellion (Rebellion): 叛军对象，用于关联叛军。
        agent_graph (Dict[int, OrdinaryRebel], 可选): 叛军图，默认为空。
        rebel_id_mapping (Dict[int, int], 可选): 叛军 ID 与 Agent ID 的映射关系，默认为空。
        model_type (str, 可选): 模型类型，默认为 "gpt-3.5-turbo"。

    返回:
        Dict[int, OrdinaryRebel]: 生成的叛军图。
    """
    if rebel_id_mapping is None:
        rebel_id_mapping = {}  # 初始化叛军 ID 与 Agent ID 的映射字典
    if agent_graph is None:
        agent_graph = {}  # 初始化叛军图

    # 读取叛军信息文件
    with open(rebellion_info_path, "r", encoding="utf-8", errors='ignore') as file:
        rebellion_info = json.load(file)

    async def process_rebel(i, rebel_data):
        """
        处理单个叛军的生成和注册。
        """
        # 叛军的唯一标识符
        rebel_id = i + 1

        # 根据叛军类型创建对象
        if rebel_data["rank"] == "普通叛军":
            rebel = OrdinaryRebel(
                rebel_id=rebel_id,
                rebellion=rebellion,
                model_type=model_type,
            )
        elif rebel_data["rank"] == "叛军头子":
            rebel = RebelLeader(
                leader_id=rebel_id,
                rebellion=rebellion,
                model_type=model_type,
            )
        else:
            raise ValueError(f"未知的叛军类型：{rebel_data['rank']}")

        # 设置叛军的初始属性
        rebel.role = rebel_data["role"]  # 角色
        rebel.persona = rebel_data["persona"]  # 人物性格

        # 将叛军添加到叛军图
        agent_graph[rebel_id] = rebel

        # 将叛军 ID 与 Agent ID 映射
        rebel_id_mapping[rebel_id] = rebel_id

        # 记录叛军生成日志
        # rebel.logger.info(f"{rebel_data['rank']} {rebel_id} 生成成功。")

    # 创建并执行叛军生成任务
    tasks = [process_rebel(i, rebel_data) for i, rebel_data in enumerate(rebellion_info)]
    await asyncio.gather(*tasks)

    # 确保返回的 agent_graph 是一个包含有效叛军对象的字典
    if not all(isinstance(rebel, (OrdinaryRebel, RebelLeader)) for rebel in agent_graph.values()):
        raise TypeError("agent_graph 中包含非法对象")
    
    return agent_graph  # 返回生成的叛军图