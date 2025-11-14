import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime
from src.utils.simulation_context import SimulationContext

# 配置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 优先使用中文字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题


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
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"rebellions_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"叛乱次数图表已保存至：{save_path}")
    plt.close()
    return save_path

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

    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"unemployment_rate_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"失业率图表已保存至：{save_path}")
    plt.close()
    return save_path

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
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"population_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"人口数量图表已保存至：{save_path}")
    plt.close()
    return save_path

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
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"government_budget_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"政府预算图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_rebellion_strength_over_time(years, rebellion_strength):
    plt.figure(figsize=(10, 6))
    plt.plot(years, rebellion_strength, label="Rebellion Strength", color="orange", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Rebellion Strength")
    plt.title("Rebellion Strength Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"rebellion_strength_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"叛乱强度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_satisfaction_over_time(years, average_satisfaction):
    plt.figure(figsize=(10, 6))
    plt.plot(years, average_satisfaction, label="Average Satisfaction", color="cyan", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Average Satisfaction")
    plt.title("Average Satisfaction Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"average_satisfaction_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"平均满意度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_tax_rate_over_time(years, tax_rate):
    plt.figure(figsize=(10, 6))
    plt.plot(years, tax_rate, label="Tax Rate", color="magenta", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Tax Rate")
    plt.title("Tax Rate Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"tax_rate_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"税率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_river_navigability_over_time(years, river_navigability):
    plt.figure(figsize=(10, 6))
    plt.plot(years, river_navigability, label="River Navigability", color="brown", marker="o")
    plt.xlabel("Year")
    plt.ylabel("River Navigability")
    plt.title("River Navigability Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"river_navigability_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"河流通航性图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_gdp_over_time(years, gdp):
    plt.figure(figsize=(10, 6))
    plt.plot(years, gdp, label="GDP", color="gray", marker="o")
    plt.xlabel("Year")
    plt.ylabel("GDP")
    plt.title("GDP Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"gdp_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"GDP图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_urban_scale_over_time(years, urban_scale):
    plt.figure(figsize=(10, 6))
    plt.plot(years, urban_scale, label="Urban Scale", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Urban Scale")
    plt.title("Urban Scale Over Time")
    plt.legend()
    plt.grid(True)
    
    # 确保目录存在
    SimulationContext.ensure_directories()
    plots_dir = SimulationContext.get_plots_dir()
    
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(plots_dir, f"urban_scale_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"城市规模图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_all_results(data_dict):
    """
    绘制所有结果的图表并保存数据表格
    """
    plot_paths = []
    years = data_dict.get('years', [])

    # 绘制各个指标的图表
    if 'rebellions' in data_dict:
        plot_paths.append(plot_rebellions_over_time(years, data_dict['rebellions']))
    if 'unemployment_rate' in data_dict:
        plot_paths.append(plot_unemployment_rate_over_time(years, data_dict['unemployment_rate']))
    if 'population' in data_dict:
        plot_paths.append(plot_population_over_time(years, data_dict['population']))
    if 'government_budget' in data_dict:
        plot_paths.append(plot_government_budget_over_time(years, data_dict['government_budget']))
    if 'rebellion_strength' in data_dict:
        plot_paths.append(plot_rebellion_strength_over_time(years, data_dict['rebellion_strength']))
    if 'average_satisfaction' in data_dict:
        plot_paths.append(plot_satisfaction_over_time(years, data_dict['average_satisfaction']))
    if 'tax_rate' in data_dict:
        plot_paths.append(plot_tax_rate_over_time(years, data_dict['tax_rate']))
    if 'river_navigability' in data_dict:
        plot_paths.append(plot_river_navigability_over_time(years, data_dict['river_navigability']))
    if 'gdp' in data_dict:
        plot_paths.append(plot_gdp_over_time(years, data_dict['gdp']))
    if 'urban_scale' in data_dict:
        plot_paths.append(plot_urban_scale_over_time(years, data_dict['urban_scale']))
    
    return plot_paths

if __name__ == "__main__":
    # 示例数据
    data_dict = {
        'years': list(range(1650, 1701)),
        'rebellions': [i * 2 for i in range(51)],
        'unemployment_rate': [i * 0.01 for i in range(51)],
        'population': [1000 + i * 10 for i in range(51)],
        'government_budget': [10000 - i * 200 for i in range(51)],
        'rebellion_strength': [i for i in range(51)],
        'average_satisfaction': [0.5 + i * 0.01 for i in range(51)],
        'tax_rate': [0.1 + i * 0.001 for i in range(51)],
        'river_navigability': [0.8 - i * 0.01 for i in range(51)],
        'gdp': [5000 + i * 100 for i in range(51)],
        'urban_scale': [100 + i * 5 for i in range(51)]
    }
    
    plot_paths = plot_all_results(data_dict)
    print("Generated plot paths:", plot_paths)