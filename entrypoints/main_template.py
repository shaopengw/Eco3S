# main_template.py

from shared_imports import *
from src.simulation.simulator_template import YourSimulator

# 注意函数名为set_simulation_type，而不是set_simulation_name
SimulationContext.set_simulation_type("{模拟名称}")

def parse_args(default_config_path):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="实验参数配置")
    parser.add_argument("--config_path", type=str, default=default_config_path, help="配置文件路径")
    parser.add_argument("--resume_from_cache", action="store_true", help="从缓存恢复模拟")
    return parser.parse_args()

async def run_simulation(config, config_path):
    """
    实验主入口：初始化环境→运行模拟→保存结果
    
    实现步骤：
    1. 根据config初始化环境对象（map, time, population等）
    2. 创建模拟器实例（Simulator或其子类）
    3. 运行模拟器：await simulator.run()
    4. 保存结果和可视化
    """
    resume_from_cache = config.get('resume_from_cache', False)
    
    # 初始化插件系统（可选）
    print("正在初始化插件系统...")
    config_dir = os.path.dirname(config_path)
    modules_config_path = os.path.join(config_dir, "modules_config.yaml")
    plugin_registry, loaded_plugins = initialize_plugin_system(
        config=config,
        modules_config_path=modules_config_path,
        logger=logging.getLogger('plugin_system')
    )
    
    #初始化环境对象（请填写所有必需参数，参考下方示例）
    # 地图对象
    map: IMap = Map(
        width=config["simulation"]["map_width"],
        height=config["simulation"]["map_height"],
        data_file=config["data"].get("towns_data_path", "")
    )
    map.initialize_map() # 不可改动

    # 时间对象
    time: ITime = Time(
        start_time=config["simulation"].get("start_year", 2020),
        total_steps=config["simulation"].get("total_years", 10)
    )

    # 人口对象
    population: IPopulation = Population(
        initial_population=config["simulation"].get("initial_population", 1000),
        birth_rate=config["simulation"].get("birth_rate", 0.01)
    )

    # 运输经济对象（如有）
    transport_economy: ITransportEconomy = TransportEconomy(
        transport_cost=population.get_population() / 200,
        transport_task=population.get_population() / 2,
        maintenance_cost_base=population.get_population() * 0.4,
    )

    # 居民对象
    residents = await generate_canal_agents( # 函数名generate_canal_agents不可修改
        resident_info_path=config["data"].get("resident_info_path", ""),
        map=map,
        initial_population=config["simulation"].get("initial_population", 1000),
        resident_prompt_path=config["data"].get("resident_prompt_path", ""),
        resident_actions_path=config["data"].get("resident_actions_path", ""),
        window_size=10
    )

    # 城镇对象
    towns: ITowns = Towns(
        map=map,
        initial_population=config["simulation"].get("initial_population", 1000),
        job_market_config_path=config["data"].get("jobs_config_path", "")
    )
    # 重要：初始化居民组，不可删除
    towns.initialize_resident_groups(residents)

    # 社交网络对象
    social_network: ISocialNetwork = SocialNetwork()
    social_network.initialize_network(residents, towns)
    for town_name, town_data in towns.towns.items():
        resident_group = town_data.get('resident_group')
        if resident_group:
            resident_group.set_social_network(social_network)

    # 政府对象（如有）
    government: IGovernment = Government(
        map=map,
        towns=towns,
        military_strength=0,
        initial_budget=0,
        time=time,
        transport_economy=transport_economy,
        government_prompt_path=config["data"].get("government_prompt_path", ""),
    )

    # 政府官员对象（如有）
    government_officials = await generate_government_agents(
        government_info_path=config["data"].get("government_info_path", ""),
        government=government,
    )

    # 叛军对象（如有）
    rebellion: IRebellion = Rebellion(
        initial_strength=0,
        initial_resources=0,
        towns=towns,
        rebels_prompt_path=config["data"].get("rebels_prompt_path", ""),
    )

    # 叛军成员对象（如有）
    rebels_agents = await generate_rebels_agents(
        rebellion_info_path=config["data"].get("rebellion_info_path", ""),
        rebellion=rebellion,
    )

    # 气候系统对象（如有）
    climate_info_path = config["data"].get("climate_info_path", "")
    climate: IClimateSystem = ClimateSystem(climate_info_path)

    # TODO: 创建模拟器（使用container和loaded_plugins）
    simulator = YourSimulator(
        container=container,
        residents=residents,
        config=config,
        government_officials=government_officials,
        rebels_agents=rebels_agents,
        loaded_plugins=loaded_plugins
    )
    
    try:
        print("开始运行模拟...")
        await simulator.run()
        print("模拟完成。")
        
        # 可视化和保存
        plot_all_results(simulator.results)
        simulator.save_results()
        
    except Exception as e:
        logging.error(f"模拟运行错误: {e}")
        raise

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/[模拟名称]/simulation_config.yaml")
    
    if not os.path.exists(args.config_path):
        raise FileNotFoundError(f"配置文件未找到: {args.config_path}")
    
    with open(args.config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    config["resume_from_cache"] = args.resume_from_cache
    
    # 设置模拟名称
    if "simulation" in config and "simulation_name" in config["simulation"]:
        SimulationContext.set_simulation_name(config["simulation"]["simulation_name"])
    
    # 运行模拟
    asyncio.run(run_simulation(config))