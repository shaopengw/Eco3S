# main.py

from shared_imports import *
from src.simulation.simulator_pricing_model_simulation import PricingModelSimulationSimulator

# 注意函数名为set_simulation_type，而不是set_simulation_name
SimulationContext.set_simulation_type("pricing_model_simulation")

def parse_args(default_config_path):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="实验参数配置")
    parser.add_argument("--config_path", type=str, default=default_config_path, help="配置文件路径")
    parser.add_argument("--resume_from_cache", action="store_true", help="从缓存恢复模拟")
    return parser.parse_args()

async def run_simulation(config):


    resume_from_cache = config.get('resume_from_cache', False)


    try:


        required_paths = [


            config["data"].get("towns_data_path", ""),


            config["data"].get("resident_info_path", ""),


            config["data"].get("resident_prompt_path", ""),


            config["data"].get("resident_actions_path", ""),


            config["data"].get("jobs_config_path", "")


        ]


        for path in required_paths:


            if path and not os.path.exists(path):


                logging.warning(f"配置文件路径不存在: {path}")


        map = Map(


            width=config["simulation"]["map_width"],


            height=config["simulation"]["map_height"],


            data_file=config["data"].get("towns_data_path", "")


        )


        map.initialize_map()


        time = Time(


            start_time=config["simulation"].get("start_year", 2020),


            total_steps=config["simulation"].get("total_years", 10)


        )


        population = Population(


            initial_population=config["simulation"].get("initial_population", 1000),


            birth_rate=config["simulation"].get("birth_rate", 0.01)


        )


        residents = await generate_canal_agents(


            resident_info_path=config["data"].get("resident_info_path", ""),


            map=map,


            initial_population=config["simulation"].get("initial_population", 1000),


            resident_prompt_path=config["data"].get("resident_prompt_path", ""),


            resident_actions_path=config["data"].get("resident_actions_path", ""),


            window_size=10


        )


        towns = Towns(


            map=map,


            initial_population=config["simulation"].get("initial_population", 1000),


            job_market_config_path=config["data"].get("jobs_config_path", "")


        )


        towns.initialize_resident_groups(residents)


        social_network = SocialNetwork()


        social_network.initialize_network(residents, towns)


        for town_name, town_data in towns.towns.items():


            resident_group = town_data.get('resident_group')


            if resident_group:


                resident_group.set_social_network(social_network)


        simulator = PricingModelSimulationSimulator(


            map=map,


            time=time,


            population=population,


            social_network=social_network,


            residents=residents,


            towns=towns,


            config=config,


        )


        print("开始运行模拟...")


        await simulator.run()


        print("模拟完成。")


        plot_pricing_model_results(simulator.results)


        simulator.save_results()


    except FileNotFoundError as e:


        logging.error(f"文件未找到错误: {e}")


        raise


    except KeyError as e:


        logging.error(f"配置项缺失错误: {e}")


        raise


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        import traceback


        logging.error(traceback.format_exc())


        raise


def plot_equilibrium_price(years, equilibrium_price):
    plt.figure(figsize=(10, 6))
    plt.plot(years, equilibrium_price, label="Equilibrium Price", color="blue", marker="o")
    plt.xlabel("Time Period")
    plt.ylabel("Price")
    plt.title("Equilibrium Price Sequence Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"equilibrium_price_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"均衡价格图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_inventory_level(years, inventory_level):
    plt.figure(figsize=(10, 6))
    plt.plot(years, inventory_level, label="Inventory Level", color="green", marker="o")
    plt.xlabel("Time Period")
    plt.ylabel("Inventory")
    plt.title("Total Inventory Level Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"inventory_level_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"库存水平图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_stockout_probability(years, stockout_probability):
    plt.figure(figsize=(10, 6))
    stockout_pct = [p * 100 for p in stockout_probability]
    plt.plot(years, stockout_pct, label="Stockout Probability", color="red", marker="o")
    plt.xlabel("Time Period")
    plt.ylabel("Stockout Probability (%)")
    plt.title("Inventory Stockout Probability Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"stockout_probability_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"断档概率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_pricing_model_results(results):
    plot_paths = []
    years = results.get('years', [])
    
    if 'equilibrium_price' in results and results['equilibrium_price']:
        plot_paths.append(plot_equilibrium_price(years, results['equilibrium_price']))
    
    if 'inventory_level' in results and results['inventory_level']:
        plot_paths.append(plot_inventory_level(years, results['inventory_level']))
    
    if 'stockout_probability' in results and results['stockout_probability']:
        plot_paths.append(plot_stockout_probability(years, results['stockout_probability']))
    
    if 'average_satisfaction' in results and results['average_satisfaction']:
        plot_paths.append(plot_satisfaction_over_time(years, results['average_satisfaction']))
    
    if 'population' in results and results['population']:
        plot_paths.append(plot_population_over_time(years, results['population']))
    
    if 'gdp' in results and results['gdp']:
        plot_paths.append(plot_gdp_over_time(years, results['gdp']))
    
    return plot_paths
# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/pricing_model_simulation/simulation_config.yaml")
    
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