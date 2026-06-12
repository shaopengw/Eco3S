from shared_imports import *
from src.simulation.simulator_info_propagation import InfoPropagationSimulator

# 设置当前模拟类型
SimulationContext.set_simulation_type("info_propagation")

# 参数解析
parser = argparse.ArgumentParser(description="信息传播实验参数配置")
parser.add_argument(
    "--config_path",
    type=str,
    help="配置文件路径",
    required=False,
    default="config/info_propagation/simulation_config.yaml",
)

async def run_simulation(config, config_path):
    """运行信息传播实验"""
    async def build_new_simulator(config: dict, config_path: str):
        print("开始初始化实验环境...")

        simulator = await build_info_propagation_simulator_via_di(
            config=config,
            config_path=config_path,
            simulator_class=InfoPropagationSimulator,
            residents_kwargs={
                "initial_population": (config.get("simulation") or {}).get("initial_population"),
                "resident_info_path": (config.get("data") or {}).get("resident_info_path"),
                "resident_prompt_path": (config.get("data") or {}).get("resident_prompt_path"),
                "resident_actions_path": (config.get("data") or {}).get("resident_actions_path"),
                "window_size": 10,
            },
            logger=logging.getLogger("entrypoint_runner"),
        )

        print("初始化完成")
        return simulator

    def after_run(simulator: Any) -> None:
        simulator.save_results()
        print("实验完成，结果已保存")

    print("开始运行实验...")
    await run_with_cache(
        config=config,
        config_path=config_path,
        cache_dir="./backups",
        simulator_class=InfoPropagationSimulator,
        build_new_simulator=build_new_simulator,
        after_run=after_run,
    )

if __name__ == "__main__":
    # 加载环境变量
    load_dotenv()
    
    # 解析命令行参数
    args = parser.parse_args()

    # 加载配置文件
    if os.path.exists(args.config_path):
        with open(args.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        raise FileNotFoundError(f"配置文件未找到: {args.config_path}")

    # 设置模拟名称，传入人口数和时间步数
    SimulationContext.set_simulation_name(
        config["simulation"].get("simulation_name"),
        population=config["simulation"]["initial_population"],
        total_years=config["simulation"]["total_years"]
    )

    # 运行实验
    asyncio.run(run_simulation(config, args.config_path))