# main_template.py

from shared_imports import *

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
    
    # TODO: 初始化环境对象
    # map = Map(...)
    # time = Time(...)
    # population = Population(...)
    # residents = await generate_canal_agents(...)
    # ... 其他对象
    
    # TODO: 创建模拟器
    # simulator = Simulator(map=map, time=time, ...)
    
    try:
        print("开始运行模拟...")
        # await simulator.run()
        print("模拟完成。")
        
        # TODO: 可视化和保存
        # plot_all_results(simulator.results)
        # simulator.save_results()
        
    except Exception as e:
        logging.error(f"模拟运行错误: {e}")
        raise

if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/simulation_config.yaml")
    
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