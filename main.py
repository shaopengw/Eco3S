import argparse
import asyncio
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any

from src.environment.map import Map
from src.environment.time import Time
from src.environment.job_market import JobMarket
from src.environment.population import Population
# from src.environment.information_spread import InformationSpread
from src.environment.social_network import SocialNetwork
from src.agents.government import Government
from src.agents.rebels import Rebellion
from src.simulation.simulator import Simulator
from src.visualization.plot_results import plot_all_results
from src.agents.resident_agent_generator import generate_canal_agents
from src.agents.government_agent_generator import generate_government_agents
from src.agents.rebels_agent_generator import generate_rebels_agents
from src.generator.resident_generate import generate_resident_data, save_resident_data

# 确保 log 目录存在
log_dir = "./log"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 参数解析
parser = argparse.ArgumentParser(description="Arguments for simulation.")
parser.add_argument(
    "--config_path",
    type=str,
    help="Path to the YAML config file.",
    required=False,
    default="config/simulation_config.yaml",
)

# 主运行函数
async def run_simulation(config: dict[str, Any]) -> None:
    """
    运行模拟
    :param config: 配置字典
    """

    # # 角色生成-测试时注销
    # N = config["simulation"]["initial_population"]
    # resident_data = generate_resident_data(N)
    # output_path = 'experiment_dataset/resident_data/resident_data.json'
    # save_resident_data(resident_data, output_path)
    # print(f"生成了{N} 名居民数据，并保存到 {output_path}")

    # 初始化地图
    map = Map(size=config["simulation"]["map_size"])
    map.initialize_river()
    map.initialize_market_towns()

    # 初始化时间
    time = Time(start_year=config["simulation"]["start_year"], end_year=config["simulation"]["end_year"])

    # 初始化就业市场
    job_market = JobMarket()

    # 初始化政府
    government = Government(
        map=map,
        job_market=job_market,
        initial_budget=config["simulation"]["government_budget"],
        time=time,
    )

    # 初始化政府官员
    government_info_path = config["data"]["government_info_path"]  # 政府官员信息文件路径
    government_officials = await generate_government_agents(
        government_info_path=government_info_path,
        government=government,
        job_market=job_market,
    )

    # 初始化叛军
    rebellion = Rebellion(
        initial_strength=config["simulation"]["rebellion_initial_strength"],
        initial_resources=config["simulation"]["rebellion_initial_resources"],
        initial_support=config["simulation"]["rebellion_initial_support"],
    )

    # 初始化叛军成员
    rebellion_info_path = config["data"]["rebellion_info_path"]  # 叛军信息文件路径
    rebels_agents = await generate_rebels_agents(
        rebellion_info_path=rebellion_info_path,
        rebellion=rebellion,
    )

    # 初始化人口
    population = Population(initial_population=config["simulation"]["initial_population"])

    # 初始化居民
    resident_info_path = config["data"]["resident_info_path"]  # 居民信息文件路径
    residents = await generate_canal_agents(
        resident_info_path=resident_info_path,
        map=map,
        job_market=job_market,
    )

    # 初始化社交网络
    social_network = initialize_social_network(residents)

    # 可视化社交网络
    social_network.visualize()


    # 初始化模拟器
    simulator = Simulator(
        map=map,
        time=time,
        job_market=job_market,
        government=government,
        government_officials=government_officials,
        rebellion=rebellion,
        rebels_agents=rebels_agents,
        population=population,
        social_network=social_network,
        residents=residents,
    )
    print("初始化完成")

    # 运行模拟
    print("开始模拟......")
    await simulator.run()

    # 可视化结果
    plot_all_results(
        years=simulator.results["years"],
        rebellions=simulator.results["rebellions"],
        unemployment_rate=simulator.results["unemployment_rate"],
        population=simulator.results["population"],
        government_budget=simulator.results["government_budget"],
        # rebellion_strength=simulator.results["rebellion_strength"],
    )

    # 保存结果
    print("模拟结束")
    simulator.save_results()

def initialize_social_network(residents: dict) -> SocialNetwork:
    social_network = SocialNetwork()
    
    # 将居民添加到社交网络
    for resident_id, resident in residents.items():
        social_network.add_resident(resident_id, "resident")

    resident_ids = list(residents.keys())
    num_residents = len(resident_ids)
    
    # 为每个居民随机选择1-3个朋友
    for i in range(num_residents):
        # 获取当前居民已有的朋友数量
        current_friends = len([n for n in social_network.hetero_graph.get_neighbors(resident_ids[i]) 
                             if social_network.hetero_graph.graph[resident_ids[i]][n]["type"] == "friend"])
        if current_friends >= 3:
            continue
            
        num_friends = random.randint(1, min(3 - current_friends, num_residents - 1))
        potential_friends = [j for j in range(num_residents) if j != i]
        selected_friends = random.sample(potential_friends, num_friends)
        
        for friend_idx in selected_friends:
            social_network.add_relation(resident_ids[i], resident_ids[friend_idx], "friend")

    # 为每个居民随机选择1-3个同事
    for i in range(num_residents):
        # 获取当前居民已有的同事数量
        current_colleagues = len([n for n in social_network.hetero_graph.get_neighbors(resident_ids[i]) 
                                if social_network.hetero_graph.graph[resident_ids[i]][n]["type"] == "colleague"])
        if current_colleagues >= 3:
            continue
            
        num_colleagues = random.randint(1, min(3 - current_colleagues, num_residents - 1))
        potential_colleagues = [j for j in range(num_residents) if j != i]
        selected_colleagues = random.sample(potential_colleagues, num_colleagues)
        
        for colleague_idx in selected_colleagues:
            social_network.add_relation(resident_ids[i], resident_ids[colleague_idx], "colleague")

    # 随机生成家庭群体
    families = []
    for i in range(0, len(resident_ids), 4):  # 每 4 个居民组成一个家庭
        family_members = [resident_ids[j] for j in range(i, min(i + 4, len(resident_ids)))]
        families.append((f"family_{i//4}", family_members))
        # print(families)
    for group_id, members in families:
        social_network.add_group(group_id, members)

    # 根据地理位置建立同乡关系
    # 创建位置字典，键为区域坐标，值为该区域内的居民列表
    location_groups = {}
    for resident_id, resident in residents.items():
        # 获取居民位置并计算所属区域
        x, y = resident.location
        area_x = x // 10  # 将x坐标划分为10*10的区域
        area_y = y // 10  # 将y坐标划分为10*10的区域
        area_key = (area_x, area_y)
        
        # 将居民添加到对应的区域组
        if area_key not in location_groups:
            location_groups[area_key] = []
        location_groups[area_key].append(resident_id)

    # 为每个区域创建同乡关系
    for area_key, members in location_groups.items():
        if len(members) > 1:  # 只有当区域内有多个居民时才创建关系
            group_id = f"hometown_{area_key[0]}_{area_key[1]}"
            social_network.add_group(group_id, members)
            # print(f"创建同乡群体 {group_id}，成员：{members}")
            
            # 在同乡之间建立双向关系
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    social_network.add_relation(members[i], members[j], "hometown")

    return social_network

if __name__ == "__main__":
    # 解析命令行参数
    args = parser.parse_args()

    # 加载配置文件
    if os.path.exists(args.config_path):
        import yaml
        with open(args.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        raise FileNotFoundError(f"Config file not found: {args.config_path}")

    # 运行模拟
    asyncio.run(run_simulation(config))