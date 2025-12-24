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

async def run_simulation(config):


    """


    实验主入口：初始化环境→运行模拟→保存结果


    实现步骤：


    1. 根据config初始化环境对象（map, time, population等）


    2. 创建模拟器实例（Simulator或其子类）


    3. 运行模拟器：await simulator.run()


    4. 保存结果和可视化


    """


    resume_from_cache = config.get('resume_from_cache', False)


    # 初始化环境对象


    # 地图对象 - 设计文档显示地图宽度/高度未涉及，移除相关参数


    map = Map(


        width=config["simulation"].get("map_width", 100),


        height=config["simulation"].get("map_height", 100),


        data_file=config["data"].get("towns_data_path", "")


    )


    map.initialize_map()  # 不可改动


    # 时间对象 - 设计文档显示起始年份和总年数未涉及，提供默认值


    time = Time(


        start_time=config["simulation"].get("start_year", 2020),


        total_steps=config["simulation"].get("total_years", 10)


    )


    # 人口对象 - 设计文档显示出生率未涉及，提供默认值


    population = Population(


        initial_population=config["simulation"].get("initial_population", 1000),


        birth_rate=config["simulation"].get("birth_rate", 0.01)


    )


    # 居民对象


    residents = await generate_canal_agents(


        resident_info_path=config["data"].get("resident_info_path", ""),


        map=map,


        initial_population=config["simulation"].get("initial_population", 1000),


        resident_prompt_path=config["data"].get("resident_prompt_path", ""),


        resident_actions_path=config["data"].get("resident_actions_path", ""),


        window_size=10


    )


    # 城镇对象 - 设计文档显示城镇数量未涉及，但代码需要初始化


    towns = Towns(


        map=map,


        initial_population=config["simulation"].get("initial_population", 1000),


        job_market_config_path=config["data"].get("jobs_config_path", "")


    )


    # 重要：初始化居民组，不可删除


    towns.initialize_resident_groups(residents)


    # 社交网络对象


    social_network = SocialNetwork()


    social_network.initialize_network(residents, towns)


    for town_name, town_data in towns.towns.items():


        resident_group = town_data.get('resident_group')


        if resident_group:


            resident_group.set_social_network(social_network)


    # 创建模拟器 - 根据Simulator的__init__参数，移除不需要的government和government_officials


    from src.simulation.simulator_customer_satisfaction_sim import CustomerSatisfactionSimSimulator


    simulator = CustomerSatisfactionSimSimulator(


        map=map,


        time=time,


        population=population,


        social_network=social_network,


        residents=residents,


        towns=towns,


        config=config,


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
    asyncio.run(run_simulation(config))