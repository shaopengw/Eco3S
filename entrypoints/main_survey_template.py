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
        plot_dir = SimulationContext.get_plots_dir()
        SimulationContext.ensure_directories()
        # TODO: 根据实验需求添加可视化
        # plot_survey_results(
        #     results=simulator.experiment_results,
        #     output_dir=plot_dir
        # )
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

# TODO: 根据实验需求实现可视化函数
def plot_survey_results(results, output_dir):
    """
    绘制问卷调查实验结果
    
    Args:
        results: 实验结果字典
        output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 示例1：绘制对话量
    # plot_conversation_volume(results, output_dir)
    
    # 示例2：绘制问卷准确率
    # plot_survey_accuracy(results, output_dir)
    
    pass

def plot_conversation_volume(results, output_dir):
    """绘制对话量柱状图"""
    # TODO: 提取对话量数据
    rounds = []
    volumes = []
    for key, value in results.items():
        if key.startswith('round_'):
            rounds.append(key)
            volumes.append(value.get('conversation_volume', 0))
    
    if not rounds:
        return
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(rounds, volumes, color='#6CBAD8')
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=10)
    
    plt.title('Conversation Volume by Round', fontsize=14, fontweight='bold')
    plt.xlabel('Round', fontsize=12)
    plt.ylabel('Conversation Volume', fontsize=12)
    plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plt.savefig(os.path.join(output_dir, f'conversation_volume_{timestamp}.png'), 
                dpi=300, bbox_inches='tight')
    print(f"对话量图表已保存至：{os.path.join(output_dir, f'conversation_volume_{timestamp}.png')}")
    plt.close()

def plot_survey_accuracy(results, output_dir):
    """绘制问卷准确率图表"""
    # TODO: 提取问卷调查数据
    survey_results = results.get('final_survey', {})
    
    if not survey_results:
        return
    
    question_accuracies = survey_results.get('question_accuracies', [])
    overall_accuracy = survey_results.get('overall_accuracy', 0)
    
    if not question_accuracies:
        return
    
    questions = [f'Q{i+1}' for i in range(len(question_accuracies))]
    
    plt.figure(figsize=(12, 6))
    bars = plt.bar(questions, question_accuracies, color='#96C2D4')
    
    # 添加整体准确率线
    plt.axhline(y=overall_accuracy, color='r', linestyle='--', 
                label=f'Overall: {overall_accuracy:.1f}%')
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=9)
    
    plt.title('Survey Question Accuracy', fontsize=14, fontweight='bold')
    plt.xlabel('Question', fontsize=12)
    plt.ylabel('Accuracy (%)', fontsize=12)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plt.savefig(os.path.join(output_dir, f'survey_accuracy_{timestamp}.png'), 
                dpi=300, bbox_inches='tight')
    print(f"问卷准确率图表已保存至：{os.path.join(output_dir, f'survey_accuracy_{timestamp}.png')}")
    plt.close()

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
    SimulationContext.set_simulation_name(config["simulation"].get("simulation_name"))

    # 运行实验
    asyncio.run(run_simulation(config, args.config_path))
