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
from src.simulation.simulator_info_propagation import InfoPropagationSimulator
from src.visualization.plot_results import plot_all_results
from src.agents.resident_agent_generator import generate_canal_agents
from src.environment.towns import Towns
from dotenv import load_dotenv

# 确保日志目录存在
log_dir = "./log"
os.makedirs(log_dir, exist_ok=True)

# 参数解析
parser = argparse.ArgumentParser(description="信息传播实验参数配置")
parser.add_argument(
    "--config_path",
    type=str,
    help="配置文件路径",
    required=False,
    default="config/info_propagation_config.yaml",
)

async def run_simulation(config):
    """运行信息传播实验"""
    print("开始初始化实验环境...")
    
    # 初始化地图
    map = Map(
        width=config["simulation"]["map_width"],
        height=config["simulation"]["map_height"],
        data_file=config["data"]["towns_data_path"]
    )
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
    
    # 初始化居民
    residents = await generate_canal_agents(
        resident_info_path=config["data"]["resident_info_path"],
        map=map,
        initial_population=config["simulation"]["initial_population"],
        resident_prompt_path=config["data"]["resident_prompt_path"],
    )

    # 初始化城镇
    towns = Towns(
        map=map,
        initial_population=config["simulation"]["initial_population"],
        job_market_config_path=config["data"]["jobs_config_path"]
    )
    towns.initialize_resident_groups(residents)
        
    # 初始化社交网络
    social_network = SocialNetwork()
    social_network.initialize_network(residents, towns)
        
    # 为每个城镇的居民群组设置社交网络
    for town_name, town_data in towns.towns.items():
        resident_group = town_data.get('resident_group')
        if resident_group:
            resident_group.set_social_network(social_network)
    
    # 创建信息传播实验模拟器
    simulator = InfoPropagationSimulator(
        map=map,
        time=time,
        population=population,
        social_network=social_network,
        residents=residents,
        towns=towns,
        config=config
    )
    print("初始化完成")

    # 运行实验
    print("开始运行实验...")
    try:
        await simulator.run()
        
        # 可视化实验结果
        plot_info_propagation_results(
            results=simulator.experiment_results,
            output_dir="experiment_dataset/plot_results/info_propagation"
        )
        simulator.save_results()
        print("实验完成，结果已保存")
        
        
    except Exception as e:
        logging.error(f"实验运行过程中发生错误: {e}")
        raise

def plot_info_propagation_results(results, output_dir):
    """绘制信息传播实验结果"""
    print(results)
    os.makedirs(output_dir, exist_ok=True)
    # 激励性选择的结果分析
    plot_incentive_choices(results, output_dir)


def plot_incentive_choices(results, output_dir):
    """绘制激励性选择结果图"""
    # 实现激励性选择结果可视化逻辑
    pass

if __name__ == "__main__":
    # 加载环境变量
    load_dotenv()
    
    # 解析命令行参数
    args = parser.parse_args()

    # 加载配置文件
    if os.path.exists(args.config_path):
        with open(args.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        raise FileNotFoundError(f"配置文件未找到: {args.config_path}")

    # 运行实验
    asyncio.run(run_simulation(config))