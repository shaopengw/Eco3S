# main_template.py

from shared_imports import *
from src.simulation.simulator_yoursimulationname import YourSimulator

# 注意函数名为set_simulation_type，而不是set_simulation_name
SimulationContext.set_simulation_type("{模拟名称}")

def parse_args(default_config_path):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="实验参数配置")
    parser.add_argument("--config_path", type=str, default=default_config_path, help="配置文件路径")
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
    async def build_new_simulator(config: dict, config_path: str):
        simulator = await build_default_simulator_via_di(
            config=config,
            config_path=config_path,
            simulator_class=YourSimulator,
            residents_kwargs={
                "initial_population": (config.get("simulation") or {}).get("initial_population", 1000),
                "resident_info_path": (config.get("data") or {}).get("resident_info_path", ""),
                "resident_prompt_path": (config.get("data") or {}).get("resident_prompt_path", ""),
                "resident_actions_path": (config.get("data") or {}).get("resident_actions_path", ""),
                "window_size": 10,
            },
            logger=logging.getLogger('entrypoint_runner'),
        )

        return simulator

    def after_run(simulator: Any) -> None:
        plot_all_results(simulator.results)
        simulator.save_results()

    print("开始运行模拟...")
    await run_with_cache(
        config=config,
        config_path=config_path,
        cache_dir="./backups",
        simulator_class=YourSimulator,
        build_new_simulator=build_new_simulator,
        after_run=after_run,
    )

# ===== 以下代码块不可删除或修改 =====
if __name__ == "__main__":
    load_dotenv()
    
    # 解析参数和加载配置
    args = parse_args(default_config_path="config/[模拟名称]/simulation_config.yaml")
    
    if not os.path.exists(args.config_path):
        raise FileNotFoundError(f"配置文件未找到: {args.config_path}")
    
    with open(args.config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # 设置模拟名称
    if "simulation" in config and "simulation_name" in config["simulation"]:
        SimulationContext.set_simulation_name(config["simulation"]["simulation_name"])
    
    # 运行模拟
    asyncio.run(run_simulation(config, args.config_path))