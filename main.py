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
    print("开始初始化......")
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
    # 将可视化移到主线程中执行
    try:
        social_network.visualize()
    except Exception as e:
        print(f"社交网络可视化失败：{e}")

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
    # 添加这一行
    simulator.initialize_resident_social_network()
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
    
    # 将居民字典添加到社交网络
    social_network.residents = residents
    
    # 将居民添加到社交网络 - O(n)
    resident_ids = list(residents.keys())
    for resident_id in resident_ids:
        social_network.add_resident(resident_id, "resident")

    num_residents = len(resident_ids)
    
    # 使用字典存储每个居民的关系数量
    relation_counts = {
        resident_id: {"friend": 0, "colleague": 0} 
        for resident_id in resident_ids
    }
    
    # 批量建立朋友和同事关系 - O(n)
    for resident_id in resident_ids:
        if relation_counts[resident_id]["friend"] < 3:
            # 随机选择未达到上限的居民作为朋友
            potential_friends = [
                rid for rid in resident_ids 
                if rid != resident_id 
                and relation_counts[rid]["friend"] < 3
            ][:10]  # 限制候选池大小
            
            if potential_friends:
                num_to_add = min(
                    3 - relation_counts[resident_id]["friend"],
                    len(potential_friends)
                )
                new_friends = random.sample(potential_friends, num_to_add)
                
                for friend_id in new_friends:
                    social_network.add_relation(resident_id, friend_id, "friend")
                    relation_counts[resident_id]["friend"] += 1
                    relation_counts[friend_id]["friend"] += 1

        # 类似地建立同事关系
        if relation_counts[resident_id]["colleague"] < 3:
            potential_colleagues = [
                rid for rid in resident_ids 
                if rid != resident_id 
                and relation_counts[rid]["colleague"] < 3
            ][:10]
            
            if potential_colleagues:
                num_to_add = min(
                    3 - relation_counts[resident_id]["colleague"],
                    len(potential_colleagues)
                )
                new_colleagues = random.sample(potential_colleagues, num_to_add)
                
                for colleague_id in new_colleagues:
                    social_network.add_relation(resident_id, colleague_id, "colleague")
                    relation_counts[resident_id]["colleague"] += 1
                    relation_counts[colleague_id]["colleague"] += 1

    # 优化家族分配 - O(n)
    # 随机生成家族群体
    families = []
    remaining_residents = set(resident_ids)  # 使用集合提高性能
    family_id = 0
    
    while remaining_residents:
        # 如果剩余居民少于最小家族规模，直接作为最后一个家族
        if len(remaining_residents) < 5:
            family_members = remaining_residents
            remaining_residents = set()  # 清空剩余居民
        else:
            # 随机确定家族规模(5-15人)
            family_size = random.randint(5, min(15, len(remaining_residents)))
            family_members = set(random.sample(list(remaining_residents), family_size))
            remaining_residents -= family_members
        
        families.append((f"family_{family_id}", list(family_members)))
        family_id += 1
        
        # 创建家族关系
        social_network.add_group(f"family_{family_id}", list(family_members))
        member_list = list(family_members)
        for i, member1 in enumerate(member_list):
            for member2 in member_list[i+1:]:
                social_network.add_relation(member1, member2, "family")

    # 优化同乡关系建立 - O(n)
    location_groups = {}
    for resident_id, resident in residents.items():
        x, y = resident.location
        area_key = (x // 20, y // 20)  # 增大区域大小，减少分组数量
        location_groups.setdefault(area_key, set()).add(resident_id)

    # 批量建立同乡关系
    for area_key, members in location_groups.items():
        if len(members) > 1:
            group_id = f"hometown_{area_key[0]}_{area_key[1]}"
            member_list = list(members)
            social_network.add_group(group_id, member_list)
            
            # 随机选择部分同乡建立关系，而不是全部建立
            for member in member_list:
                potential_neighbors = random.sample(
                    [m for m in member_list if m != member],
                    min(5, len(members) - 1)  # 限制每个人的同乡关系数量
                )
                for neighbor in potential_neighbors:
                    social_network.add_relation(member, neighbor, "hometown")

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