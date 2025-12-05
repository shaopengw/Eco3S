# main.py

from shared_imports import *

# 设置模拟类型
SimulationContext.set_simulation_type("climate_migration_sim")

# 导入模拟器
from src.simulation.simulator_climate_migration_sim import ClimateMigrationSimSimulator

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


    try:


        # 初始化环境对象


        # 地图对象


        map = Map(


            width=config["simulation"]["map_width"],


            height=config["simulation"]["map_height"],


            data_file=config["data"].get("towns_data_path", "")


        )


        map.initialize_map()


        # 时间对象


        time = Time(


            start_time=config["simulation"].get("start_year", 2020),


            total_steps=config["simulation"].get("total_years", 10)


        )


        # 人口对象


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


        # 城镇对象


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


        # 政府对象


        government = Government(


            map=map,


            towns=towns,


            military_strength=0,


            initial_budget=0,


            time=time,


            transport_economy=None,


            government_prompt_path=config["data"].get("government_prompt_path", ""),


        )


        # 政府官员对象


        government_officials = await generate_government_agents(


            government_info_path=config["data"].get("government_info_path", ""),


            government=government,


        )


        # 气候系统对象


        climate_info_path = config["data"].get("climate_info_path", "")


        climate = ClimateSystem(climate_info_path)


        # 创建模拟器


        simulator = ClimateMigrationSimSimulator(


            map=map,


            time=time,


            population=population,


            social_network=social_network,


            residents=residents,


            towns=towns,


            config=config,


            government=government,


            government_officials=government_officials,


            climate=climate,


        )


        print("开始运行模拟...")


        await simulator.run()


        print("模拟完成。")


        # 可视化和保存


        try:


            plot_all_results(simulator.results)


        except Exception as e:


            logging.warning(f"可视化结果时出现警告: {e}")


        simulator.save_results()


    except FileNotFoundError as e:


        logging.error(f"文件未找到错误: {e}")


        raise


    except KeyError as e:


        logging.error(f"配置文件缺少必要的键: {e}")


        raise


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        raise


def plot_temperature_over_time(years, temperature):
    plt.figure(figsize=(10, 6))
    plt.plot(years, temperature, label="Temperature", color="red", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Temperature (°C)")
    plt.title("Temperature Over Time")
    plt.legend()
    plt.grid(True)
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"temperature_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"温度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_extreme_events_over_time(years, extreme_events):
    plt.figure(figsize=(10, 6))
    plt.plot(years, extreme_events, label="Extreme Events", color="orange", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Number of Extreme Events")
    plt.title("Extreme Events Over Time")
    plt.legend()
    plt.grid(True)
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"extreme_events_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"极端事件图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_migration_rate_over_time(years, migration_rate):
    plt.figure(figsize=(10, 6))
    plt.plot(years, migration_rate, label="Migration Rate", color="purple", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Migration Rate (%)")
    plt.title("Migration Rate Over Time")
    plt.legend()
    plt.grid(True)
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"migration_rate_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"迁移率图表已保存至：{save_path}")
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
    if 'tax_rate' in data_dict:
        plot_paths.append(plot_tax_rate_over_time(years, data_dict['tax_rate']))
    if 'river_navigability' in data_dict:
        plot_paths.append(plot_river_navigability_over_time(years, data_dict['river_navigability']))
    if 'gdp' in data_dict:
        plot_paths.append(plot_gdp_over_time(years, data_dict['gdp']))
    if 'urban_scale' in data_dict:
        plot_paths.append(plot_urban_scale_over_time(years, data_dict['urban_scale']))
    if 'temperature' in data_dict:
        plot_paths.append(plot_temperature_over_time(years, data_dict['temperature']))
    if 'extreme_events' in data_dict:
        plot_paths.append(plot_extreme_events_over_time(years, data_dict['extreme_events']))
    if 'migration_rate' in data_dict:
        plot_paths.append(plot_migration_rate_over_time(years, data_dict['migration_rate']))
    return plot_paths

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/climate_migration_sim/simulation_config.yaml")
    
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