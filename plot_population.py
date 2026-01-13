import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime
from src.utils.simulation_context import SimulationContext

# 配置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 优先使用中文字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题


def plot_population_over_time(years, population):
    """
    绘制人口数量随时间变化的图表
    :param years: 年份列表
    :param population: 人口数量列表
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, population, label="Population", color="green", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Population")
    plt.title("Population Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化（添加进程ID避免并行冲突）
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    save_path = os.path.join(plots_dir, f"population_{current_time}_pid{pid}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"人口数量图表已保存至：{save_path}")
    plt.close()
    return save_path


if __name__ == "__main__":
    # 设置模拟类型（必须在使用SimulationContext之前）
    SimulationContext.set_simulation_type("financial_herd_behavior_sim")
    
    # 从CSV文件读取数据
    import sys
    
    if len(sys.argv) > 1:
        # 如果提供了命令行参数，使用该文件路径
        csv_file = sys.argv[1]
    else:
        # 否则使用默认路径
        csv_file = r"e:\cyf\多智能体\AgentWorld\history\financial_herd_behavior_sim\financial_herd_behavior_sim\running_data_20260112_132956_pid18436.csv"
    
    print(f"正在处理文件: {csv_file}")
    
    try:
        # 读取CSV文件
        df = pd.read_csv(csv_file)
        
        if 'years' not in df.columns or 'population' not in df.columns:
            print("错误：CSV文件缺少必要的列（years或population）")
        else:
            years = df['years'].tolist()
            population = df['population'].tolist()
            
            print(f"从文件读取数据：{len(years)}个时间点")
            print(f"人口范围：{min(population)} - {max(population)}")
            
            # 生成图表
            plot_population_over_time(years, population)
            
    except FileNotFoundError:
        print(f"错误：找不到文件 {csv_file}")
    except Exception as e:
        print(f"错误：{e}")
        import traceback
        traceback.print_exc()
