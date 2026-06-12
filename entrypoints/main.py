from shared_imports import *
from src.simulation.simulator import Simulator

# 设置当前模拟类型
SimulationContext.set_simulation_type("default")

# 参数解析
parser = argparse.ArgumentParser(description="Arguments for simulation.")
parser.add_argument(
    "--config_path",
    type=str,
    help="Path to the YAML config file.",
    required=False,
    default="config/default/simulation_config.yaml",
)

# 主运行函数
async def run_simulation(config: dict[str, Any], config_path: str) -> None:
    """
    运行模拟
    :param config: 配置字典
    :param config_path: 配置文件路径
    """
    async def build_new_simulator(config: dict[str, Any], config_path: str):
        print("开始初始化......")
        simulator = await build_default_simulator_via_di(
            config=config,
            config_path=config_path,
            simulator_class=Simulator,
            residents_kwargs={
                "initial_population": config["simulation"]["initial_population"],
                "resident_info_path": (config.get("data") or {}).get("resident_info_path"),
                "resident_prompt_path": (config.get("data") or {}).get("resident_prompt_path"),
                "resident_actions_path": (config.get("data") or {}).get("resident_actions_path"),
            },
            logger=logging.getLogger("entrypoint_runner"),
        )
        print("初始化完成")
        return simulator

    print("开始模拟......")
    await run_with_cache(
        config=config,
        config_path=config_path,
        cache_dir="./backups",
        simulator_class=Simulator,
        build_new_simulator=build_new_simulator,
    )


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

    # 设置模拟名称
    population = config["simulation"].get("initial_population")
    total_years = config["simulation"].get("total_years")
    SimulationContext.set_simulation_name(config["simulation"].get("simulation_name"), population, total_years)

    # 运行模拟
    asyncio.run(run_simulation(config, args.config_path))
