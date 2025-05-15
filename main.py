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
from src.environment.towns import Towns
from dotenv import load_dotenv

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
    map = Map(width=config["simulation"]["map_width"], height=config["simulation"]["map_height"])
    map.initialize_map()
    
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
    )

    # 初始化叛军
    rebellion = Rebellion(
        initial_strength=config["simulation"]["rebellion_initial_strength"],
        initial_resources=config["simulation"]["rebellion_initial_resources"],
        job_market=job_market,
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
        initial_population=config["simulation"]["initial_population"],
    )

    # 初始化城镇
    towns = Towns(map=map,initial_population=config["simulation"]["initial_population"],)
    towns.initialize_resident_groups(residents)

    # 打印初始化状态-----测试用
    # print("\n初始化城镇和就业市场状态：")
    # towns.print_towns_status()
    
    # 初始化社交网络
    social_network = SocialNetwork()
    social_network.initialize_network(residents, towns)

    # 可视化社交网络
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
        towns=towns,
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

    # 运行模拟
    asyncio.run(run_simulation(config))