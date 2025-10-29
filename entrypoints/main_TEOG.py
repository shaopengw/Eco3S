from shared_imports import *
from src.simulation.simulator_TEOG import TEOGSimulator

# 设置当前模拟类型
SimulationContext.set_simulation_type("TEOG")

# 参数解析
parser = argparse.ArgumentParser(description="Arguments for simulation.")
parser.add_argument(
    "--config_path",
    type=str,
    help="Path to the YAML config file.",
    required=False,
    default="config/simulation_config.yaml",
)
parser.add_argument(
    "--resume_from_cache",
    action="store_true",
    help="Resume simulation from cached data if available.",
)
async def run_simulation(config):
    """运行模拟"""
    print(f"开始读取缓存文件...")

    # 从配置文件中获取 resume_from_cache
    resume_from_cache = config.get('simulation', {}).get('resume_from_cache', False)
    cache_dir = "./backups_TEOG"  # 缓存文件存放的目录
    cache_file = None  # 初始化 cache_file 变量

    # 获取模拟参数
    population = config['simulation']['initial_population']
    total_years = config['simulation']['total_years']
    
    # 使用SimulationCache查找最新的缓存文件
    result = SimulationCache.find_latest_cache(
        population=population,
        target_years=total_years,
        cache_dir=cache_dir
    )
    found_cache_file = result[0] if result else None
    found_year = result[1] if result else None
    
    simulator = None
    # 总是为当前运行生成一个新的缓存文件名
    # 这确保了如果模拟继续，cache_file 总是有效的路径
    cache_file = SimulationCache.generate_cache_filename(
        population=population,
        total_years=total_years,
        cache_dir=cache_dir,
        with_timestamp=True
    )

    if found_cache_file:
        if os.path.exists(found_cache_file):
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
                    # 使用SimulationCache加载缓存
                    simulator = SimulationCache.load_cache(
                        file_path=found_cache_file,
                        simulator_class=TEOGSimulator,
                        simulator_years=simulator_years,
                        config=config
                    )
                    if simulator:
                        print(f"成功从缓存加载模拟状态，将继续模拟 {simulator_years} 年...")
                        simulator.total_years = total_years  # 更新总年份
                    else:
                        print("缓存加载失败，将从头开始模拟...")
                        simulator = None # 确保如果加载失败，会创建一个新的模拟器
                except Exception as e:
                    print(f"加载缓存失败: {e}")
                    simulator = None # 确保如果加载失败，会创建一个新的模拟器
        else:
            logging.warning(f"文件 {found_cache_file} 不存在，将从头开始模拟...")
    else:
        print("没有发现匹配的缓存文件，将从头开始模拟...")

    if simulator is None:
        print("开始初始化......")
    
        # 初始化地图
        map = Map(width=config["simulation"]["map_width"], height=config["simulation"]["map_height"], data_file=config["data"]["towns_data_path"])
        map.initialize_map()
        
        
        # 初始化时间系统
        time = Time(
            start_year=config["simulation"]["start_year"],
            total_years=config["simulation"]["total_years"]
        )
        
        # 初始化人口系统
        population = Population(
            initial_population=config["simulation"]["initial_population"],
            birth_rate=config["simulation"]["birth_rate"]
        )

        # 初始化运输经济系统
        transport_economy = TransportEconomy(
            transport_cost=population.get_population() / 200,
            transport_task=population.get_population() / 2,
            maintenance_cost_base=population.get_population() * 0.4,
        )
        
        # 初始化居民
        resident_info_path = config["data"]["resident_info_path"]  # 居民信息文件路径
        residents = await generate_canal_agents(
            resident_info_path=resident_info_path,
            map=map,
            initial_population=config["simulation"]["initial_population"],
            resident_prompt_path=config["data"]["resident_prompt_path"],
            resident_actions_path=config["data"]["resident_actions_path"],
        )

        # 初始化城镇
        towns = Towns(map=map,initial_population=config["simulation"]["initial_population"]*20,job_market_config_path=config["data"]["jobs_config_path"])
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

        # 初始化政府
        government = Government(
            map=map,
            towns=towns,
            military_strength=0,
            initial_budget=0,
            time=time,
            transport_economy=transport_economy,
            government_prompt_path=config["data"]["government_prompt_path"],
        )

        # 初始化政府官员
        government_info_path = config["data"]["government_info_path"]  # 政府官员信息文件路径
        government_officials = await generate_government_agents(
            government_info_path=government_info_path,
            government=government,
        )

        climate_info_path = config["data"]["climate_info_path"]  # 气候信息文件路径
        climate = ClimateSystem(climate_info_path)  # 气候系统
        

        
        # 修改模拟器实例化
        simulator = TEOGSimulator(
            map=map,
            time=time,
            government=government,
            government_officials=government_officials,
            population=population,
            social_network=social_network,
            residents=residents,
            towns=towns,
            transport_economy=transport_economy,
            climate=climate,
            config=config,
            )
        print("初始化完成")

    # 运行模拟
    print("开始模拟......")
    try:
        await simulator.run()
        data_dict = {
            'years': simulator.results["years"],
            'population': simulator.results["population"],
            'government_budget': simulator.results["government_budget"],
            'average_satisfaction': simulator.results["average_satisfaction"],
            'tax_rate': simulator.results["tax_rate"],
            'river_navigability': simulator.results["river_navigability"],
            'gdp': simulator.results["gdp"],
            'urban_scale': simulator.results["urban_scale"],
        }
        plot_all_results(data_dict)

        # 保存结果
        print("模拟结束")

    except Exception as e:
        logging.error(f"模拟运行过程中发生错误: {e}")
    finally:
        if simulator and resume_from_cache: # 只有当 resume_from_cache 为 True 时才保存缓存
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

    # 设置模拟名称
    population = config["simulation"].get("initial_population")
    total_years = config["simulation"].get("total_years")
    SimulationContext.set_simulation_name(config["simulation"].get("simulation_name"), population, total_years)

    # 运行模拟
    asyncio.run(run_simulation(config))