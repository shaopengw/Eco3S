from .shared_imports import *
from src.agents.government import Government, OrdinaryGovernmentAgent, HighRankingGovernmentAgent, government_SharedInformationPool, InformationOfficer

async def generate_government_agents(
    government_info_path: str,  # 政府官员信息文件的路径
    government: Government,  # 政府对象，用于关联官员
    agent_graph: Optional[Dict[int, OrdinaryGovernmentAgent]] = None,  # 官员图，默认为空
    official_id_mapping: Optional[Dict[int, int]] = None,  # 官员 ID 与 Agent ID 的映射关系，默认为空
    shared_pool: Optional[government_SharedInformationPool] = None, # 共享资源池，默认为空
) -> Dict[int, OrdinaryGovernmentAgent]:
    """
    生成并返回政府官员的官员图。

    参数:
        government_info_path (str): 政府官员信息文件的路径。
        government (Government): 政府对象，用于关联官员。
        agent_graph (Dict[int, OrdinaryGovernmentAgent], 可选): 官员图，默认为空。
        official_id_mapping (Dict[int, int], 可选): 官员 ID 与 Agent ID 的映射关系，默认为空。

    返回:
        Dict[int, OrdinaryGovernmentAgent]: 生成的官员图。
    """
    if official_id_mapping is None:
        official_id_mapping = {}  # 初始化官员 ID 与 Agent ID 的映射字典
    if agent_graph is None:
        agent_graph = {}  # 初始化官员图
    if shared_pool is None:
        shared_pool = government_SharedInformationPool()  # 初始化共享资源池

    # 读取政府官员信息文件
    with open(government_info_path, "r", encoding="utf-8", errors='ignore') as file:
        government_info = json.load(file)

    async def process_official(i, official_data):
        """
        处理单个政府官员的生成和注册。
        """
        # 官员的唯一标识符
        official_id = i + 1

        # 根据官员类型创建对象
        if official_data["rank"] == "普通官员":
            official = OrdinaryGovernmentAgent(
                agent_id=official_id,
                government=government,
                shared_pool=shared_pool,
            )
        elif official_data["rank"] == "高级官员":
            official = HighRankingGovernmentAgent(
                agent_id=official_id,
                government=government,
                shared_pool=shared_pool,
            )
        else:
            raise ValueError(f"未知的官员类型：{official_data['rank']}")

        # 设置官员的初始属性
        official.mbti = official_data["mbti"]  # 人物性格
        # 派别属性
        if official_data["rank"] == "普通官员":
            official.function = official_data["function"]  # 职能
            official.faction = official_data["faction"]  # 派别

        # 将官员添加到官员图
        agent_graph[official_id] = official

        # 将官员 ID 与 Agent ID 映射
        official_id_mapping[official_id] = official_id

        # 记录官员生成日志
        # official.logger.info(f"{official_data['rank']} {official_id} 生成成功。")

    # 创建并执行官员生成任务
    tasks = [process_official(i, official_data) for i, official_data in enumerate(government_info)]
    await asyncio.gather(*tasks)

    # 创建一个信息整理官
    info_officer_id = len(agent_graph) + 1
    info_officer = InformationOfficer(
        agent_id=info_officer_id,
        government=government,
        shared_pool=shared_pool,
    )
    agent_graph[info_officer_id] = info_officer
    official_id_mapping[info_officer_id] = info_officer_id

     # 确保返回的 agent_graph 是一个包含有效官员对象的字典
    if not all(isinstance(official, (OrdinaryGovernmentAgent, HighRankingGovernmentAgent, InformationOfficer)) for official in agent_graph.values()):
        raise TypeError("agent_graph 中包含非法对象")
    
    return agent_graph  # 返回生成的官员图