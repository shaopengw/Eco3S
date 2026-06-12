from shared_imports import *
from src.simulation.simulator_survey_template import SurveySimulator

# 注意函数名为set_simulation_type，而不是set_simulation_name
SimulationContext.set_simulation_type("your_survey_experiment")

# 参数解析
parser = argparse.ArgumentParser(description="问卷调查实验参数配置")
parser.add_argument(
    "--config_path",
    type=str,
    help="配置文件路径",
    required=False,
    default="config/your_survey_experiment/simulation_config.yaml",
)

async def run_simulation(config, config_path):
    """运行问卷调查实验"""
    async def build_new_simulator(config: dict, config_path: str):
        print("开始初始化实验环境...")

        config_dir = os.path.dirname(config_path)
        modules_config_path = os.path.join(config_dir, "modules_config.yaml")

        influence_registry = load_influence_registry_from_dir(config_dir, logger=logging.getLogger('influences'))
        container = setup_container_for_simulation(influence_registry=influence_registry)

        print("正在初始化插件系统...")
        plugin_registry = initialize_plugin_system(
            config=config,
            modules_config_path=modules_config_path,
            container=container,
            logger=logging.getLogger('plugin_system')
        )

        init_result = await orchestrate_basic_runtime_init(
            plugin_registry=plugin_registry,
            config=config,
            residents_kwargs={
                "initial_population": config["simulation"]["initial_population"],
                "resident_info_path": config["data"]["resident_info_path"],
                "resident_prompt_path": config["data"]["resident_prompt_path"],
                "resident_actions_path": config["data"]["resident_actions_path"],
                "window_size": 10,
            },
        )
        residents = init_result.residents

        # 影响函数编排器：若 config_dir 下存在 influences.yaml，会通过 DI 注入的 InfluenceRegistry 提供 execution_order
        influence_manager = InfluenceManager(logger=logging.getLogger('influences'))

        simulator = SurveySimulator(
            plugin_registry=plugin_registry,
            residents=residents,
            config=config,
            influence_manager=influence_manager,
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
        simulator_class=SurveySimulator,
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

    # 设置模拟名称
    population = config.get("simulation", {}).get("initial_population")
    total_years = config.get("simulation", {}).get("total_years")
    SimulationContext.set_simulation_name(
        config.get("simulation", {}).get("simulation_name"),
        population=population,
        total_years=total_years,
    )

    # 运行实验
    asyncio.run(run_simulation(config, args.config_path))
