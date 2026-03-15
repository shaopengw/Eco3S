# main.py

from shared_imports import *

# 注意函数名为set_simulation_type,而不是set_simulation_name
SimulationContext.set_simulation_type("asset_market_bubble_sim")

from src.simulation.simulator_asset_market_bubble_sim import AssetMarketBubbleSimSimulator

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

    # 手动创建 government
    time = container.resolve(ITime)
    government = Government(
        map=map,
        towns=towns,
        military_strength=0,
        initial_budget=0,
        time=time,
        transport_economy=None,
        government_prompt_path=config["data"].get("government_prompt_path", ""),
    )
    # 将 government 注册到容器中
    container.register_instance(IGovernment, government)

    # 初始化政府官员
    government_officials = await generate_government_agents(
        government_info_path=config["data"].get("government_info_path", ""),
        government=government,
    )

    # 使用容器创建模拟器
    simulator = AssetMarketBubbleSimSimulator(
        container=container,
        government_officials=government_officials,
        residents=residents,
        config=config,
        loaded_plugins=loaded_plugins
    )


    try:


        print("开始运行模拟...")


        await simulator.run()


        print("模拟完成。")


        if hasattr(simulator, 'results'):


            plot_asset_market_results(simulator.results)


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        raise


def plot_asset_market_results(results):
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    
    periods = results.get('periods', [])
    if not periods:
        print("无可视化数据")
        return []
    
    plot_paths = []
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    axes[0, 0].plot(periods, results['asset_price'], color='blue', marker='o')
    axes[0, 0].set_xlabel('交易期')
    axes[0, 0].set_ylabel('资产价格')
    axes[0, 0].set_title('资产价格变化')
    axes[0, 0].grid(True)
    
    axes[0, 1].plot(periods, results['trading_volume'], color='green', marker='s')
    axes[0, 1].set_xlabel('交易期')
    axes[0, 1].set_ylabel('交易量')
    axes[0, 1].set_title('交易量变化')
    axes[0, 1].grid(True)
    
    axes[1, 0].plot(periods, results['price_deviation'], color='red', marker='^')
    axes[1, 0].axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    axes[1, 0].set_xlabel('交易期')
    axes[1, 0].set_ylabel('价格偏离率 (%)')
    axes[1, 0].set_title('价格偏离基础价值')
    axes[1, 0].grid(True)
    
    axes[1, 1].plot(periods, results['bid_ask_spread'], color='purple', marker='d')
    axes[1, 1].set_xlabel('交易期')
    axes[1, 1].set_ylabel('买卖价差')
    axes[1, 1].set_title('市场流动性指标')
    axes[1, 1].grid(True)
    
    plt.tight_layout()
    save_path = os.path.join(plots_dir, f"asset_market_overview_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"资产市场综合图表已保存至：{save_path}")
    plt.close()
    plot_paths.append(save_path)
    
    return plot_paths

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/asset_market_bubble_sim/simulation_config.yaml")
    
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