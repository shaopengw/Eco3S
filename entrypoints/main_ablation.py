"""
消融实验专用入口文件
实验四：LLM驱动的复杂行为消融 (Ablation of LLM-driven Behavior)

使用规则决策替代LLM决策，以便对比两种决策模型的效果
"""

from shared_imports import *
# 导入消融实验模拟器
from src.simulation.simulator_ablation import SimulatorAblation

# 设置当前模拟类型
SimulationContext.set_simulation_type("default")

# 参数解析
parser = argparse.ArgumentParser(description="Arguments for ablation experiment simulation.")
parser.add_argument(
    "--config_path",
    type=str,
    help="Path to the YAML config file.",
    required=False,
    default="config/default/simulation_config.yaml",
)
parser.add_argument(
    "--resume_from_cache",
    action="store_true",
    help="Resume simulation from cached data if available.",
)
parser.add_argument(
    "--save_cache",
    action="store_true",
    help="Save simulation state to cache file after completion.",
)

# 主运行函数
async def run_simulation(config: dict[str, Any]) -> None:
    """
    运行消融实验模拟
    :param config: 配置字典
    """
    print("=" * 60)
    print("消融实验模式：使用规则决策替代LLM决策")
    print("=" * 60)
    print(f"开始读取缓存文件...")

    # 从配置文件中获取缓存相关配置
    resume_from_cache = config.get('simulation', {}).get('resume_from_cache', False)
    save_cache = config.get('simulation', {}).get('save_cache', False)
    cache_dir = "./backups_ABLATION"  # 消融实验使用独立的缓存目录

    # 获取模拟参数
    population = config['simulation']['initial_population']
    total_years = config['simulation']['total_years']
    
    simulator = None
    cache_file = None
    # 设置缓存文件路径
    cache_file = SimulationCache.generate_cache_filename(
        population=population,
        total_years=total_years,
        cache_dir=cache_dir,
        with_timestamp=True
    )
    
    # 只有当resume_from_cache为True时才查找和加载缓存
    if resume_from_cache:
        print(f"开始查找缓存文件...")
        # 使用SimulationCache查找最新的缓存文件
        result = SimulationCache.find_latest_cache(
            population=population,
            target_years=total_years,
            cache_dir=cache_dir
        )
        found_cache_file = result[0] if result else None
        found_year = result[1] if result else None
        
        if found_cache_file and os.path.exists(found_cache_file):
            if found_year == total_years:
                response = input(f"发现已有的模拟文件 {found_cache_file}，是否需要重新模拟？(Y/N): ")
                if response.upper() == 'Y':
                    print(f"将从头开始模拟...")
                else:
                    return  # 结束函数，不再继续
            elif found_year < total_years:
                try:
                    print(f"尝试从缓存文件 {found_cache_file} 加载模拟状态...")
                    simulator_years = total_years - found_year
                    # 使用SimulationCache加载缓存（使用SimulatorAblation类）
                    simulator = SimulationCache.load_cache(
                        file_path=found_cache_file,
                        simulator_class=SimulatorAblation,  # 使用消融实验模拟器
                        simulator_years=simulator_years,
                        config=config
                    )
                    if simulator:
                        print(f"成功从缓存加载模拟状态，将继续模拟 {simulator_years} 年...")
                    else:
                        print("缓存加载失败，将从头开始模拟...")
                        simulator = None
                except Exception as e:
                    print(f"加载缓存失败: {e}")
                    simulator = None
        else:
            print("未找到可用的缓存文件，将从头开始模拟...")
    
    if simulator is None:
        print("开始初始化（消融实验模式）......")
        
        # 初始化地图
        map = Map(width=config["simulation"]["map_width"], height=config["simulation"]["map_height"], data_file=config["data"]["towns_data_path"])
        map.initialize_map()
        
        # 初始化时间
        time = Time(start_time=config["simulation"]["start_year"], 
                   total_steps=config["simulation"]["total_years"])

        # 初始化人口
        population = Population(
            initial_population=config["simulation"]["initial_population"],
            birth_rate=config["simulation"]["birth_rate"]
        )

        # 初始化运输经济系统
        transport_economy = TransportEconomy(
            transport_cost=1,
            transport_task=population.get_population() / 4,
            maintenance_cost_base=population.get_population() * 0.2,
        )

        # 初始化居民
        resident_info_path = config["data"]["resident_info_path"]
        residents = await generate_canal_agents(
            resident_info_path=resident_info_path,
            map=map,
            initial_population=config["simulation"]["initial_population"],
            resident_prompt_path=config["data"]["resident_prompt_path"],
            resident_actions_path=config["data"]["resident_actions_path"],
        )

        # 初始化城镇
        towns = Towns(map=map, initial_population=config["simulation"]["initial_population"], job_market_config_path=config["data"]["jobs_config_path"])
        towns.initialize_resident_groups(residents)
        
        # 初始化社交网络
        social_network = SocialNetwork()
        social_network.initialize_network(residents, towns)
        
        # 为每个城镇的居民群组设置社交网络
        for town_name, town_data in towns.towns.items():
            resident_group = town_data.get('resident_group')
            if resident_group:
                resident_group.set_social_network(social_network)
        
        # 可视化社交网络
        try:
            social_network.visualize()
        except Exception as e:
            print(f"社交网络可视化失败：{e}")
        try:
            social_network.plot_degree_distribution()
        except Exception as e:
            print(f"社交网络节点度分布可视化失败：{e}")

        # 计算所有城镇的总叛军和官兵数量
        total_rebels = 0
        total_military = 0
        for city_name, town_data in towns.towns.items():
            job_market = town_data['job_market']
            if job_market:
                rebels_count = len(job_market.jobs_info["叛军"]["employed"])
                military_count = len(job_market.jobs_info["官员及士兵"]["employed"])
                total_rebels += rebels_count
                total_military += military_count

        # 初始化政府
        government = Government(
            map=map,
            towns=towns,
            military_strength=total_military,
            initial_budget=0,
            time=time,
            transport_economy=transport_economy,
            government_prompt_path=config["data"]["government_prompt_path"],
        )

        # 初始化政府官员
        government_info_path = config["data"]["government_info_path"]
        government_officials = await generate_government_agents(
            government_info_path=government_info_path,
            government=government,
        )

        # 初始化叛军
        rebellion = Rebellion(
            initial_strength=total_rebels,
            initial_resources=total_rebels * 10,
            towns=towns,
            rebels_prompt_path=config["data"]["rebels_prompt_path"],
        )

        # 初始化叛军成员
        rebellion_info_path = config["data"]["rebellion_info_path"]
        rebels_agents = await generate_rebels_agents(
            rebellion_info_path=rebellion_info_path,
            rebellion=rebellion,
        )
        
        # 初始化气候系统
        climate_info_path = config["data"]["climate_info_path"]
        climate = ClimateSystem(climate_info_path)

        # 创建消融实验模拟器
        simulator = SimulatorAblation(
            map=map,
            time=time,
            government=government,
            government_officials=government_officials,
            rebellion=rebellion,
            rebels_agents=rebels_agents,
            population=population,
            social_network=social_network,
            residents=residents,
            towns=towns,
            transport_economy=transport_economy,
            climate=climate,
            config=config,
        )
        
        print("初始化完成（消融实验模式）")

    # 运行模拟
    print("\n开始运行消融实验模拟...")
    print("=" * 60)
    try:
        await simulator.run()
        # 可视化结果
        data_dict = {
            'years': simulator.results["years"],
            'rebellions': simulator.results["rebellions"],
            'unemployment_rate': simulator.results["unemployment_rate"],
            'population': simulator.results["population"],
            'government_budget': simulator.results["government_budget"],
            'rebellion_strength': simulator.results["rebellion_strength"],
            'average_satisfaction': simulator.results["average_satisfaction"],
            'tax_rate': simulator.results["tax_rate"],
            'river_navigability': simulator.results["river_navigability"],
            'gdp': simulator.results["gdp"],
        }
        plot_all_results(data_dict)
        
        print("=" * 60)
        print("消融实验模拟完成！")

    except Exception as e:
        logging.error(f"消融实验模拟运行过程中发生错误: {e}")
    finally:
        if simulator and save_cache and cache_file:  # 只有当 save_cache 为 True 时才保存缓存
            try:
                # 使用SimulationCache保存缓存
                if SimulationCache.save_cache(simulator, cache_file):
                    print(f"模拟状态已保存到缓存文件 {cache_file}。")
                else:
                    print("保存缓存失败。")
            except Exception as e:
                print(f"保存缓存失败: {e}")


if __name__ == "__main__":
    load_dotenv()  # 加载.env环境变量
    # 解析命令行参数
    args = parser.parse_args()

    # 加载配置文件
    if os.path.exists(args.config_path):
        with open(args.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        raise FileNotFoundError(f"Config file not found: {args.config_path}")

    # 将命令行参数添加到配置中
    config["resume_from_cache"] = args.resume_from_cache
    config["save_cache"] = args.save_cache

    # 设置模拟名称
    population = config["simulation"].get("initial_population")
    total_years = config["simulation"].get("total_years")
    SimulationContext.set_simulation_name(config["simulation"].get("simulation_name"), population, total_years)

    # 运行模拟
    asyncio.run(run_simulation(config))
