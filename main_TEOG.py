import argparse
import asyncio
import logging
import os
import yaml
from datetime import datetime
from typing import Any

from src.environment.map import Map
from src.environment.time import Time
from src.environment.population import Population
from src.environment.social_network import SocialNetwork
from src.environment.climate import ClimateSystem
from src.agents.government import Government
from src.agents.rebels import Rebellion
from src.simulation.simulator_TEOG import TEOGSimulator
from src.visualization.plot_results import plot_all_results
from src.agents.resident_agent_generator import generate_canal_agents
from src.agents.government_agent_generator import generate_government_agents
from src.agents.rebels_agent_generator import generate_rebels_agents
from src.generator.resident_generate import generate_resident_data, save_resident_data
from src.environment.towns import Towns
from src.environment.transport_economy import TransportEconomy
from dotenv import load_dotenv
import json

# 确保 log 目录存在
log_dir = "./log"

# 参数解析
parser = argparse.ArgumentParser(description="Arguments for simulation.")
parser.add_argument(
    "--config_path",
    type=str,
    help="Path to the YAML config file.",
    required=False,
    default="config/simulation_config.yaml",
)
parser.add_argument(
    "--resume_from_cache",
    action="store_true",
    help="Resume simulation from cached data if available.",
)
async def run_simulation(config):
    """运行模拟"""
    print("开始初始化......")
    
    # 初始化地图
    map = Map(width=config["simulation"]["map_width"], height=config["simulation"]["map_height"], data_file=config["data"]["towns_data_path"])
    map.initialize_map()
    
    
    # 初始化时间系统
    time = Time(
        start_year=config["simulation"]["start_year"],
        total_years=config["simulation"]["total_years"]
    )
    
    # 初始化人口系统
    population = Population(
        initial_population=config["simulation"]["initial_population"],
        birth_rate=config["simulation"]["birth_rate"]
    )

    # 初始化运输经济系统
    transport_economy = TransportEconomy(
        transport_cost=population.get_population() / 200,
        transport_task=population.get_population() / 2,
        maintenance_cost_base=population.get_population() * 0.4,
    )
    

    
    # 初始化居民
    resident_info_path = config["data"]["resident_info_path"]  # 居民信息文件路径
    residents = await generate_canal_agents(
        resident_info_path=resident_info_path,
        map=map,
        initial_population=config["simulation"]["initial_population"],
        resident_prompt_path=config["data"]["resident_prompt_path"],
    )

    # 初始化城镇
    towns = Towns(map=map,initial_population=config["simulation"]["initial_population"],job_market_config_path=config["data"]["jobs_config_path"])
    towns.initialize_resident_groups(residents)
        
    # 初始化社交网络
    social_network = SocialNetwork()
    social_network.initialize_network(residents, towns)
        
    # 为每个城镇的居民群组设置社交网络
    for town_name, town_data in towns.towns.items():
        resident_group = town_data.get('resident_group')
        if resident_group:
            resident_group.set_social_network(social_network)
        
    # 可视化社交网络
    try:
        social_network.visualize()
    except Exception as e:
        print(f"社交网络可视化失败：{e}")
    try:
        social_network.plot_degree_distribution()
    except Exception as e:
        print(f"社交网络节点度分布可视化失败：{e}")

    # 初始化政府
    government = Government(
        map=map,
        towns=towns,
        military_strength=0,
        initial_budget=0,
        time=time,
        transport_economy=transport_economy,
        government_prompt_path=config["data"]["government_prompt_path"],
    )

    # 初始化政府官员
    government_info_path = config["data"]["government_info_path"]  # 政府官员信息文件路径
    government_officials = await generate_government_agents(
        government_info_path=government_info_path,
        government=government,
    )

    climate_info_path = config["data"]["climate_info_path"]  # 气候信息文件路径
    climate = ClimateSystem(climate_info_path)  # 气候系统
    

    
    # 修改模拟器实例化
    simulator = TEOGSimulator(
        map=map,
        time=time,
        government=government,
        government_officials=government_officials,
        population=population,
        social_network=social_network,
        residents=residents,
        towns=towns,
        transport_economy=transport_economy,
        climate=climate,
        )
    print("初始化完成")

    # 运行模拟
    print("开始模拟......")
    await simulator.run()

    plot_all_results(
        years=simulator.results["years"],
        population=simulator.results["population"],
        government_budget=simulator.results["government_budget"],
        average_satisfaction=simulator.results["average_satisfaction"],
        tax_rate=simulator.results["tax_rate"],
        river_navigability=simulator.results["river_navigability"],
        gdp=simulator.results["gdp"],
        urban_scale=simulator.results["urban_scale"],
    )

if __name__ == "__main__":
    load_dotenv()  # 加载.env环境变量
    # 解析命令行参数
    args = parser.parse_args()

    # 加载配置文件
    if os.path.exists(args.config_path):
        import yaml
        with open(args.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        raise FileNotFoundError(f"Config file not found: {args.config_path}")

    # 将命令行参数添加到配置中
    config["resume_from_cache"] = args.resume_from_cache

    # 运行模拟
    asyncio.run(run_simulation(config))