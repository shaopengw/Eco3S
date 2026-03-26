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
    default="config/TEOG/simulation_config.yaml",
)
async def run_simulation(config, config_path):
    """运行模拟"""
    async def build_new_simulator(config, config_path):
        print("开始初始化......")

        simulator = await build_teog_simulator_via_di(
            config=config,
            config_path=config_path,
            simulator_class=TEOGSimulator,
            residents_kwargs={
                "initial_population": (config.get("simulation") or {}).get("initial_population"),
                "resident_info_path": (config.get("data") or {}).get("resident_info_path"),
                "resident_prompt_path": (config.get("data") or {}).get("resident_prompt_path"),
                "resident_actions_path": (config.get("data") or {}).get("resident_actions_path"),
            },
            logger=logging.getLogger("entrypoint_runner"),
        )

        print("初始化完成")
        return simulator

    def post_resume(simulator: Any) -> None:
        try:
            simulator.total_years = config['simulation']['total_years']
        except Exception:
            pass

    def after_run(simulator: Any) -> None:
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

    print("开始模拟......")
    await run_with_cache(
        config=config,
        config_path=config_path,
        cache_dir="./backups_TEOG",
        simulator_class=TEOGSimulator,
        build_new_simulator=build_new_simulator,
        post_resume=post_resume,
        after_run=after_run,
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