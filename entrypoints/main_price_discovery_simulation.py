# main.py

from shared_imports import *
from src.simulation.simulator_price_discovery_simulation import PriceDiscoverySimulationSimulator

SimulationContext.set_simulation_type("price_discovery_simulation")

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


        # 创建模拟器


        simulator = PriceDiscoverySimulationSimulator(


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


        # 可视化和保存


        plot_all_results(simulator.results)


        simulator.save_results()


    except FileNotFoundError as e:


        logging.error(f"文件未找到: {e}")


        raise


    except KeyError as e:


        logging.error(f"配置项缺失: {e}")


        raise


    except Exception as e:


        logging.error(f"模拟运行错误: {e}")


        raise


def plot_exchange_prices_over_time(years, exchange_A_price, exchange_B_price, common_efficient_price):
    plt.figure(figsize=(12, 6))
    plt.plot(years, exchange_A_price, label="交易所A价格", color="blue", marker="o", markersize=3)
    plt.plot(years, exchange_B_price, label="交易所B价格", color="red", marker="s", markersize=3)
    plt.plot(years, common_efficient_price, label="共同有效价格", color="green", linestyle="--", linewidth=2)
    plt.xlabel("年份")
    plt.ylabel("价格")
    plt.title("交易所价格与共同有效价格对比")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"exchange_prices_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"交易所价格对比图已保存至：{save_path}")
    plt.close()
    return save_path

def plot_trade_volumes_over_time(years, exchange_A_volume, exchange_B_volume):
    plt.figure(figsize=(12, 6))
    plt.bar([y - 0.2 for y in years], exchange_A_volume, width=0.4, label="交易所A交易量", color="blue", alpha=0.7)
    plt.bar([y + 0.2 for y in years], exchange_B_volume, width=0.4, label="交易所B交易量", color="red", alpha=0.7)
    plt.xlabel("年份")
    plt.ylabel("交易量")
    plt.title("交易所交易量对比")
    plt.legend()
    plt.grid(True, alpha=0.3, axis='y')
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"trade_volumes_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"交易量对比图已保存至：{save_path}")
    plt.close()
    return save_path

def plot_contributions_over_time(years, exchange_A_contribution, exchange_B_contribution):
    plt.figure(figsize=(12, 6))
    plt.plot(years, exchange_A_contribution, label="交易所A贡献度", color="blue", marker="o", markersize=3)
    plt.plot(years, exchange_B_contribution, label="交易所B贡献度", color="red", marker="s", markersize=3)
    plt.xlabel("年份")
    plt.ylabel("贡献度")
    plt.title("交易所对共同有效价格的贡献度")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 1.1)
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"contributions_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"贡献度对比图已保存至：{save_path}")
    plt.close()
    return save_path

def plot_price_discovery_metrics(years, price_discovery_efficiency, price_stability):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    ax1.plot(years, price_discovery_efficiency, color="purple", marker="o", markersize=3)
    ax1.set_xlabel("年份")
    ax1.set_ylabel("价格发现效率")
    ax1.set_title("价格发现效率")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 1.1)
    
    ax2.plot(years, price_stability, color="orange", marker="s", markersize=3)
    ax2.set_xlabel("年份")
    ax2.set_ylabel("价格稳定性")
    ax2.set_title("价格稳定性")
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 1.1)
    
    plt.tight_layout()
    
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"price_discovery_metrics_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"价格发现指标图已保存至：{save_path}")
    plt.close()
    return save_path

def plot_all_results(data_dict):
    plot_paths = []
    years = data_dict.get('years', [])
    
    if 'exchange_A_price' in data_dict and 'exchange_B_price' in data_dict and 'common_efficient_price' in data_dict:
        plot_paths.append(plot_exchange_prices_over_time(
            years, 
            data_dict['exchange_A_price'], 
            data_dict['exchange_B_price'],
            data_dict['common_efficient_price']
        ))
    
    if 'exchange_A_volume' in data_dict and 'exchange_B_volume' in data_dict:
        plot_paths.append(plot_trade_volumes_over_time(
            years,
            data_dict['exchange_A_volume'],
            data_dict['exchange_B_volume']
        ))
    
    if 'exchange_A_contribution' in data_dict and 'exchange_B_contribution' in data_dict:
        plot_paths.append(plot_contributions_over_time(
            years,
            data_dict['exchange_A_contribution'],
            data_dict['exchange_B_contribution']
        ))
    
    if 'price_discovery_efficiency' in data_dict and 'price_stability' in data_dict:
        plot_paths.append(plot_price_discovery_metrics(
            years,
            data_dict['price_discovery_efficiency'],
            data_dict['price_stability']
        ))
    
    if 'population' in data_dict:
        plot_paths.append(plot_population_over_time(years, data_dict['population']))
    
    return plot_paths

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/price_discovery_simulation/simulation_config.yaml")
    
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