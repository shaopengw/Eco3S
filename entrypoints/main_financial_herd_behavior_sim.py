# main.py

from shared_imports import *

# 注意函数名为set_simulation_type，而不是set_simulation_name
SimulationContext.set_simulation_type("financial_herd_behavior_sim")

def parse_args(default_config_path):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="实验参数配置")
    parser.add_argument("--config_path", type=str, default=default_config_path, help="配置文件路径")
    parser.add_argument("--resume_from_cache", action="store_true", help="从缓存恢复模拟")
    return parser.parse_args()

async def run_simulation(config, config_path):


    resume_from_cache = config.get('resume_from_cache', False)

    # 初始化插件系统
    print("正在初始化插件系统...")
    config_dir = os.path.dirname(config_path)
    modules_config_path = os.path.join(config_dir, "modules_config.yaml")
    plugin_registry, loaded_plugins = initialize_plugin_system(
        config=config,
        modules_config_path=modules_config_path,
        logger=logging.getLogger('plugin_system')
    )

    # 初始化 DIContainer
    container = setup_container_for_simulation(modules_config_path, config)

    # 获取 map 实例并初始化
    map = container.resolve(IMap)
    map.initialize_map()

    # 生成居民
    residents = await generate_canal_agents(
        resident_info_path=config["data"].get("resident_info_path", ""),
        map=map,
        initial_population=config["simulation"].get("initial_population", 1000),
        resident_prompt_path=config["data"].get("resident_prompt_path", ""),
        resident_actions_path=config["data"].get("resident_actions_path", ""),
        window_size=10
    )

    # 获取 towns 并初始化居民组
    towns = container.resolve(ITowns)
    towns.initialize_resident_groups(residents)

    # 获取社交网络并初始化
    social_network = container.resolve(ISocialNetwork)
    social_network.initialize_network(residents, towns)

    for town_name, town_data in towns.towns.items():
        resident_group = town_data.get('resident_group')
        if resident_group:
            resident_group.set_social_network(social_network)

    # 使用容器创建模拟器
    from src.simulation.simulator_financial_herd_behavior_sim import FinancialHerdBehaviorSimSimulator
    simulator = FinancialHerdBehaviorSimSimulator(
        container=container,
        residents=residents,
        config=config,
        loaded_plugins=loaded_plugins
    )


    try:


        print("开始运行模拟...")


        await simulator.run()


        print("模拟完成。")


        plot_financial_herd_results(simulator.results)


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        raise


def plot_asset_price_over_time(years, asset_price):
    plt.figure(figsize=(10, 6))
    plt.plot(years, asset_price, label="Asset Price", color="blue", marker="o")
    plt.xlabel("Trading Day")
    plt.ylabel("Asset Price")
    plt.title("Asset Price Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"asset_price_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"资产价格图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_asset_price_volatility_over_time(years, volatility):
    plt.figure(figsize=(10, 6))
    plt.plot(years, volatility, label="Asset Price Volatility", color="red", marker="o")
    plt.xlabel("Trading Day")
    plt.ylabel("Volatility")
    plt.title("Asset Price Volatility Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"asset_price_volatility_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"资产价格波动率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_trading_frequency_over_time(years, trading_frequency):
    plt.figure(figsize=(10, 6))
    plt.plot(years, trading_frequency, label="Trading Frequency", color="green", marker="o")
    plt.xlabel("Trading Day")
    plt.ylabel("Trading Frequency")
    plt.title("Trading Frequency Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"trading_frequency_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"交易频率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_portfolio_concentration_over_time(years, concentration):
    plt.figure(figsize=(10, 6))
    plt.plot(years, concentration, label="Portfolio Concentration", color="purple", marker="o")
    plt.xlabel("Trading Day")
    plt.ylabel("Portfolio Concentration (HHI)")
    plt.title("Portfolio Concentration Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"portfolio_concentration_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"持仓集中度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_behavior_concentration_over_time(years, concentration):
    plt.figure(figsize=(10, 6))
    plt.plot(years, concentration, label="Behavior Concentration", color="orange", marker="o")
    plt.xlabel("Trading Day")
    plt.ylabel("Behavior Concentration")
    plt.title("Behavior Concentration Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"behavior_concentration_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"行为集中度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_financial_herd_results(data_dict):
    plot_paths = []
    years = data_dict.get('years', [])
    
    if 'asset_price' in data_dict and data_dict['asset_price']:
        plot_paths.append(plot_asset_price_over_time(years, data_dict['asset_price']))
    
    if 'asset_price_volatility' in data_dict and data_dict['asset_price_volatility']:
        plot_paths.append(plot_asset_price_volatility_over_time(years, data_dict['asset_price_volatility']))
    
    if 'trading_frequency' in data_dict and data_dict['trading_frequency']:
        plot_paths.append(plot_trading_frequency_over_time(years, data_dict['trading_frequency']))
    
    if 'portfolio_concentration' in data_dict and data_dict['portfolio_concentration']:
        plot_paths.append(plot_portfolio_concentration_over_time(years, data_dict['portfolio_concentration']))
    
    if 'behavior_concentration' in data_dict and data_dict['behavior_concentration']:
        plot_paths.append(plot_behavior_concentration_over_time(years, data_dict['behavior_concentration']))
    
    if 'population' in data_dict and data_dict['population']:
        plot_paths.append(plot_population_over_time(years, data_dict['population']))
    
    if 'average_satisfaction' in data_dict and data_dict['average_satisfaction']:
        plot_paths.append(plot_satisfaction_over_time(years, data_dict['average_satisfaction']))
    
    return plot_paths

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/financial_herd_behavior_sim/simulation_config.yaml")
    
    if not os.path.exists(args.config_path):
        raise FileNotFoundError(f"配置文件未找到: {args.config_path}")
    
    with open(args.config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    config["resume_from_cache"] = args.resume_from_cache
    
    # 设置模拟名称
    if "simulation" in config and "simulation_name" in config["simulation"]:
        SimulationContext.set_simulation_name(config["simulation"]["simulation_name"])
    
    # 运行模拟
    asyncio.run(run_simulation(config, args.config_path))