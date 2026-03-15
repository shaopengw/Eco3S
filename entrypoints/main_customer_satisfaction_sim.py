# main.py

from shared_imports import *

# 注意函数名为set_simulation_type,而不是set_simulation_name
SimulationContext.set_simulation_type("customer_satisfaction_sim")

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
    #将 government 注册到容器中
    container.register_instance(IGovernment, government)

    # 初始化政府官员
    government_officials = await generate_government_agents(
        government_info_path=config["data"].get("government_info_path", ""),
        government=government,
    )

    # 使用容器创建模拟器
    from src.simulation.simulator_customer_satisfaction_sim import CustomerSatisfactionSimSimulator
    simulator = CustomerSatisfactionSimSimulator(
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


        # 可视化和保存


        plot_all_results(simulator.results)


        simulator.save_results()


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        raise


def plot_customer_loyalty_over_time(years, customer_loyalty):
    plt.figure(figsize=(10, 6))
    plt.plot(years, customer_loyalty, label="Customer Loyalty", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Customer Loyalty (%)")
    plt.title("Customer Loyalty Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"customer_loyalty_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"顾客忠诚度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_purchase_decisions_over_time(years, purchase_decisions):
    plt.figure(figsize=(10, 6))
    plt.plot(years, purchase_decisions, label="Purchase Decisions", color="green", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Number of Purchase Decisions")
    plt.title("Purchase Decisions Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"purchase_decisions_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"购买决策数图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_all_results(data_dict):
    plot_paths = []
    years = data_dict.get('years') or data_dict.get('time_step') or data_dict.get('step', [])

    if 'rebellions' in data_dict:
        plot_paths.append(plot_rebellions_over_time(years, data_dict['rebellions']))
    if 'unemployment_rate' in data_dict:
        plot_paths.append(plot_unemployment_rate_over_time(years, data_dict['unemployment_rate']))
    if 'population' in data_dict:
        plot_paths.append(plot_population_over_time(years, data_dict['population']))
    if 'government_budget' in data_dict:
        plot_paths.append(plot_government_budget_over_time(years, data_dict['government_budget']))
    if 'rebellion_strength' in data_dict:
        plot_paths.append(plot_rebellion_strength_over_time(years, data_dict['rebellion_strength']))
    if 'average_satisfaction' in data_dict:
        plot_paths.append(plot_satisfaction_over_time(years, data_dict['average_satisfaction']))
    if 'customer_loyalty' in data_dict:
        plot_paths.append(plot_customer_loyalty_over_time(years, data_dict['customer_loyalty']))
    if 'purchase_decisions' in data_dict:
        plot_paths.append(plot_purchase_decisions_over_time(years, data_dict['purchase_decisions']))
    if 'tax_rate' in data_dict:
        plot_paths.append(plot_tax_rate_over_time(years, data_dict['tax_rate']))
    if 'river_navigability' in data_dict:
        plot_paths.append(plot_river_navigability_over_time(years, data_dict['river_navigability']))
    if 'gdp' in data_dict:
        plot_paths.append(plot_gdp_over_time(years, data_dict['gdp']))
    if 'urban_scale' in data_dict:
        plot_paths.append(plot_urban_scale_over_time(years, data_dict['urban_scale']))
    
    return plot_paths

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/customer_satisfaction_sim/simulation_config.yaml")
    
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