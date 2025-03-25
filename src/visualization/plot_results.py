import matplotlib.pyplot as plt

def plot_rebellions_over_time(years, rebellions):
    """
    绘制叛乱次数随时间变化的图表
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, rebellions, label="Rebellions", color="red", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Number of Rebellions")
    plt.title("Rebellions Over Time")
    plt.legend()
    plt.grid(True)
    
    # 保存图片
    save_dir = "e:/cyf/多智能体/AgentWorld/experiment_dataset/plot_results"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(save_dir, f"rebellions_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"叛乱次数图表已保存至：{save_path}")
    plt.close()

def plot_unemployment_rate_over_time(years, unemployment_rate):
    """
    绘制失业率随时间变化的图表
    :param years: 年份列表
    :param unemployment_rate: 失业率列表
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, unemployment_rate, label="Unemployment Rate", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Unemployment Rate")
    plt.title("Unemployment Rate Over Time")
    plt.legend()
    plt.grid(True)
    plt.show()

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
    plt.show()

def plot_government_budget_over_time(years, government_budget):
    """
    绘制政府预算随时间变化的图表
    :param years: 年份列表
    :param government_budget: 政府预算列表
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, government_budget, label="Government Budget", color="purple", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Government Budget")
    plt.title("Government Budget Over Time")
    plt.legend()
    plt.grid(True)
    plt.show()

def plot_all_results(years, rebellions, unemployment_rate, population, government_budget):
    """
    绘制所有结果的综合图表
    """
    plt.figure(figsize=(15, 10))

    # 叛乱次数随时间变化
    plt.subplot(2, 2, 1)
    plt.plot(years, rebellions, label="Rebellions", color="red", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Number of Rebellions")
    plt.title("Rebellions Over Time")
    plt.legend()
    plt.grid(True)

    # 失业率随时间变化
    plt.subplot(2, 2, 2)
    plt.plot(years, unemployment_rate, label="Unemployment Rate", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Unemployment Rate")
    plt.title("Unemployment Rate Over Time")
    plt.legend()
    plt.grid(True)

    # 人口数量随时间变化
    plt.subplot(2, 2, 3)
    plt.plot(years, population, label="Population", color="green", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Population")
    plt.title("Population Over Time")
    plt.legend()
    plt.grid(True)

    # 政府预算随时间变化
    plt.subplot(2, 2, 4)
    plt.plot(years, government_budget, label="Government Budget", color="purple", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Government Budget")
    plt.title("Government Budget Over Time")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    
    # 保存图片
    save_dir = "e:/cyf/多智能体/AgentWorld/experiment_dataset/plot_results"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(save_dir, f"all_results_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"综合结果图表已保存至：{save_path}")
    plt.close()

# 在文件开头添加必要的导入
import os
from datetime import datetime

if __name__ == "__main__":
    # 示例数据
    years = list(range(1650, 1701))
    rebellions = [0, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230]
    unemployment_rate = [0.1, 0.12, 0.15, 0.18, 0.2, 0.22, 0.25, 0.28, 0.3, 0.32, 0.35, 0.38, 0.4, 0.42, 0.45, 0.48, 0.5, 0.52, 0.55, 0.58, 0.6, 0.62, 0.65, 0.68, 0.7, 0.72, 0.75, 0.78, 0.8, 0.82, 0.85, 0.88, 0.9, 0.92, 0.95, 0.98, 1.0, 1.02, 1.05, 1.08, 1.1, 1.12, 1.15, 1.18, 1.2, 1.22, 1.25, 1.28, 1.3, 1.32, 1.35]
    population = [1000, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 1080, 1090, 1100, 1110, 1120, 1130, 1140, 1150, 1160, 1170, 1180, 1190, 1200, 1210, 1220, 1230, 1240, 1250, 1260, 1270, 1280, 1290, 1300, 1310, 1320, 1330, 1340, 1350, 1360, 1370, 1380, 1390, 1400, 1410, 1420, 1430, 1440, 1450, 1460, 1470, 1480, 1490, 1500]
    government_budget = [10000, 9800, 9600, 9400, 9200, 9000, 8800, 8600, 8400, 8200, 8000, 7800, 7600, 7400, 7200, 7000, 6800, 6600, 6400, 6200, 6000, 5800, 5600, 5400, 5200, 5000, 4800, 4600, 4400, 4200, 4000, 3800, 3600, 3400, 3200, 3000, 2800, 2600, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000, 800, 600, 400, 200, 0]