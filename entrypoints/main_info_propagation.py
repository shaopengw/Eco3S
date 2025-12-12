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
    default="config/info_propagation_config.yaml",
)

async def run_simulation(config):
    """运行信息传播实验"""
    print("开始初始化实验环境...")
    
    # 初始化地图
    map = Map(
        width=config["simulation"]["map_width"],
        height=config["simulation"]["map_height"],
        data_file=config["data"]["towns_data_path"]
    )
    map.initialize_map()
    
    # 初始化时间系统
    time = Time(
        start_time=config["simulation"]["start_year"],
        total_steps=config["simulation"]["total_years"]
    )
    
    # 初始化人口系统
    population = Population(
        initial_population=config["simulation"]["initial_population"],
        birth_rate=config["simulation"]["birth_rate"]
    )
    
    # 初始化居民
    residents = await generate_canal_agents(
        resident_info_path=config["data"]["resident_info_path"],
        map=map,
        initial_population=config["simulation"]["initial_population"],
        resident_prompt_path=config["data"]["resident_prompt_path"],
        resident_actions_path=config["data"]["resident_actions_path"],
        window_size=10
    )

    # 初始化城镇
    towns = Towns(
        map=map,
        initial_population=config["simulation"]["initial_population"],
        job_market_config_path=config["data"]["jobs_config_path"]
    )
    towns.initialize_resident_groups(residents)
        
    # 初始化社交网络
    social_network = SocialNetwork()
    social_network.initialize_network(residents, towns)
        
    # 为每个城镇的居民群组设置社交网络
    for town_name, town_data in towns.towns.items():
        resident_group = town_data.get('resident_group')
        if resident_group:
            resident_group.set_social_network(social_network)
    
    # 创建信息传播实验模拟器
    simulator = InfoPropagationSimulator(
        map=map,
        time=time,
        population=population,
        social_network=social_network,
        residents=residents,
        towns=towns,
        config=config
    )
    print("初始化完成")

    # 运行实验
    print("开始运行实验...")
    try:
        await simulator.run()
        
        # 可视化实验结果
        from src.utils.simulation_context import SimulationContext
        
        # 使用 SimulationContext 获取图表目录
        plot_dir = SimulationContext.get_plots_dir()
        
        # 确保图表目录存在
        SimulationContext.ensure_directories()
        
        plot_info_propagation_results(
            results=simulator.experiment_results,
            output_dir=plot_dir
        )
        simulator.save_results()
        print("实验完成，结果已保存")
        
        
    except Exception as e:
        logging.error(f"实验运行过程中发生错误: {e}")
        raise

def plot_info_propagation_results(results, output_dir):
    """绘制信息传播实验结果"""
    os.makedirs(output_dir, exist_ok=True)
    # 1. 绘制对话量柱状图
    plot_conversation_volume(results, output_dir)
    
    # 2. 绘制问卷调查准确率柱状图
    plot_questionnaire_accuracy(results, output_dir)
    
    # 3. 绘制激励性选择结果图
    plot_incentive_choices(results, output_dir)


def plot_conversation_volume(results, output_dir):
    """绘制对话量柱状图"""
    strategies = list(results.keys())
    conversation_volumes = [results[strategy]['conversation_volume'] for strategy in strategies]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(strategies, conversation_volumes, color=['#DBF1FA', '#BAD2E1', '#96C2D4', '#6CBAD8'])
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{height}', ha='center', va='bottom', fontsize=12)
    
    plt.title('conversation_volumes', fontsize=16, fontweight='bold')
    plt.xlabel('strategies', fontsize=12)
    plt.ylabel('conversation_volume', fontsize=12)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # 添加时间戳到文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    plt.savefig(os.path.join(output_dir, f'conversation_volume_{current_time}.png'), dpi=300, bbox_inches='tight')
    print(f"对话量图表已保存至：{os.path.join(output_dir, f'conversation_volume_{current_time}.png')}")
    plt.close()


def plot_questionnaire_accuracy(results, output_dir):
    """绘制知识问答准确率柱状图"""
    strategies = list(results.keys())
    accuracies = [results[strategy]['knowledge_survey']['overall_accuracy'] for strategy in strategies]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(strategies, accuracies, color=['#DBF1FA', '#BAD2E1', '#96C2D4', '#6CBAD8'])
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{height:.2f}%', ha='center', va='bottom', fontsize=12)
    
    plt.title('knowledge_survey_accuracy', fontsize=16, fontweight='bold')
    plt.xlabel('strategies', fontsize=12)
    plt.ylabel('accuracy(%)', fontsize=12)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # 添加时间戳到文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    plt.savefig(os.path.join(output_dir, f'knowledge_survey_accuracy_{current_time}.png'), dpi=300, bbox_inches='tight')
    print(f"知识问答准确率图表已保存至：{os.path.join(output_dir, f'knowledge_survey_accuracy_{current_time}.png')}")
    plt.close()


def plot_incentive_choices(results, output_dir):
    """绘制奖励问题选择结果图"""
    strategies = list(results.keys())
    a_counts = [results[strategy]['incentive_survey']['incentive_choices_a_count'] for strategy in strategies]
    b_counts = [results[strategy]['incentive_survey']['incentive_choices_b_count'] for strategy in strategies]
    
    x = np.arange(len(strategies))
    width = 0.35
    
    plt.figure(figsize=(12, 7))
    
    # 创建分组柱状图
    bars1 = plt.bar(x - width/2, a_counts, width, label='incentive_choices_a_count', color='#FF9999', alpha=0.8)
    bars2 = plt.bar(x + width/2, b_counts, width, label='incentive_choices_b_count', color='#66B2FF', alpha=0.8)
    
    # 添加数值标签
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:  # 只在有数值时显示标签
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                        f'{height}', ha='center', va='bottom', fontsize=11)
    
    plt.title('incentive_choices', fontsize=16, fontweight='bold')
    plt.xlabel('strategies', fontsize=12)
    plt.ylabel('incentive_choices', fontsize=12)
    plt.xticks(x, strategies)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # 添加时间戳到文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    plt.savefig(os.path.join(output_dir, f'incentive_survey_{current_time}.png'), dpi=300, bbox_inches='tight')
    print(f"激励性选择结果图表已保存至：{os.path.join(output_dir, f'incentive_survey_{current_time}.png')}")
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

    # 设置模拟名称，传入人口数和时间步数
    SimulationContext.set_simulation_name(
        config["simulation"].get("simulation_name"),
        population=config["simulation"]["initial_population"],
        total_years=config["simulation"]["total_years"]
    )

    # 运行实验
    asyncio.run(run_simulation(config))