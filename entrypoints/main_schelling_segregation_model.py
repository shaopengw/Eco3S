# main.py

from shared_imports import *
from src.simulation.simulator_schelling_segregation_model import SchellingSegregationModelSimulator

# 注意函数名为set_simulation_type，而不是set_simulation_name
SimulationContext.set_simulation_type("schelling_segregation_model")

def parse_args(default_config_path):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="实验参数配置")
    parser.add_argument("--config_path", type=str, default=default_config_path, help="配置文件路径")
    parser.add_argument("--resume_from_cache", action="store_true", help="从缓存恢复模拟")
    return parser.parse_args()

async def run_simulation(config, config_path):


    try:
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
            resident_info_path=config.get("data", {}).get("resident_info_path", ""),
            map=map,
            initial_population=config["simulation"].get("initial_population", 1000),
            resident_prompt_path=config.get("data", {}).get("resident_prompt_path", ""),
            resident_actions_path=config.get("data", {}).get("resident_actions_path", ""),
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

        # 为初始居民随机分配类型（A或B）
        import random
        for resident in residents.values():
            if not hasattr(resident, 'resident_type'):
                resident.resident_type = random.choice(['A', 'B'])

        # 使用容器创建模拟器
        simulator = SchellingSegregationModelSimulator(
            container=container,
            residents=residents,
            config=config,
            loaded_plugins=loaded_plugins
        )


        print("开始运行模拟...")


        await simulator.run()


        print("模拟完成。")


        simulator.save_results()


        print("开始生成可视化图表...")


        visualize_results(simulator.result_file)


        print("可视化完成。")


    except KeyError as e:


        logging.error(f"配置文件缺少必要字段: {e}")


        raise


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        raise


def plot_migration_rate_over_time(years, migration_rate):
    plt.figure(figsize=(10, 6))
    plt.plot(years, migration_rate, label="Migration Rate", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Migration Rate (%)")
    plt.title("Resident Migration Rate Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"migration_rate_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"迁移率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_average_similarity_over_time(years, average_similarity):
    plt.figure(figsize=(10, 6))
    plt.plot(years, average_similarity, label="Average Similarity", color="green", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Average Similarity")
    plt.title("Average Neighbor Similarity Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"average_similarity_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"平均相似度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_segregation_index_over_time(years, segregation_index):
    plt.figure(figsize=(10, 6))
    plt.plot(years, segregation_index, label="Segregation Index", color="red", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Segregation Index")
    plt.title("Spatial Segregation Index Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"segregation_index_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"隔离指数图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_resident_types_over_time(years, type_a_population, type_b_population):
    plt.figure(figsize=(10, 6))
    plt.plot(years, type_a_population, label="Type A Population", color="blue", marker="o")
    plt.plot(years, type_b_population, label="Type B Population", color="orange", marker="s")
    plt.xlabel("Year")
    plt.ylabel("Population")
    plt.title("Resident Type Distribution Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"resident_types_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"居民类型分布图表已保存至：{save_path}")
    plt.close()
    return save_path

def visualize_results(result_file):
    if not os.path.exists(result_file):
        print(f"数据文件不存在: {result_file}")
        return
    import pandas as pd
    df = pd.read_csv(result_file)
    
    plot_paths = []
    
    if 'years' in df.columns and 'population' in df.columns:
        plot_paths.append(plot_population_over_time(df['years'].tolist(), df['population'].tolist()))
    
    if 'years' in df.columns and 'migration_rate' in df.columns:
        plot_paths.append(plot_migration_rate_over_time(df['years'].tolist(), df['migration_rate'].tolist()))
    
    if 'years' in df.columns and 'average_satisfaction' in df.columns:
        plot_paths.append(plot_satisfaction_over_time(df['years'].tolist(), df['average_satisfaction'].tolist()))
    
    if 'years' in df.columns and 'average_similarity' in df.columns:
        plot_paths.append(plot_average_similarity_over_time(df['years'].tolist(), df['average_similarity'].tolist()))
    
    if 'years' in df.columns and 'segregation_index' in df.columns:
        plot_paths.append(plot_segregation_index_over_time(df['years'].tolist(), df['segregation_index'].tolist()))
    
    if 'years' in df.columns and 'type_a_population' in df.columns and 'type_b_population' in df.columns:
        plot_paths.append(plot_resident_types_over_time(
            df['years'].tolist(),
            df['type_a_population'].tolist(),
            df['type_b_population'].tolist()
        ))
    
    print(f"已生成 {len(plot_paths)} 个可视化图表")
    return plot_paths


def plot_population_over_time(years, population):
    plt.figure(figsize=(10, 6))
    plt.plot(years, population, label="Population", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Population")
    plt.title("Population Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"population_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"人口图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_satisfaction_over_time(years, satisfaction):
    plt.figure(figsize=(10, 6))
    plt.plot(years, satisfaction, label="Average Satisfaction", color="purple", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Satisfaction")
    plt.title("Average Satisfaction Over Time")
    plt.legend()
    plt.grid(True)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"satisfaction_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"满意度图表已保存至：{save_path}")
    plt.close()
    return save_path

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/schelling_segregation_model/simulation_config.yaml")
    
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