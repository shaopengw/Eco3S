import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime


def plot_rebellions_over_time(years, rebellions, experiment_type="default"):
    """
    绘制叛乱次数随时间变化的图表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, rebellions, label="Rebellions", color="red", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Number of Rebellions")
    plt.title("Rebellions Over Time")
    plt.legend()
    plt.grid(True)
    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 保存图片
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"rebellions_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"叛乱次数图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_unemployment_rate_over_time(years, unemployment_rate, experiment_type="default"):
    """
    绘制失业率随时间变化的图表
    :param years: 年份列表
    :param unemployment_rate: 失业率列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, unemployment_rate, label="Unemployment Rate", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Unemployment Rate")
    plt.title("Unemployment Rate Over Time")
    plt.legend()
    plt.grid(True)

    # 获取当前时间并格式化
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"unemployment_rate_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"失业率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_population_over_time(years, population, experiment_type="default"):
    """
    绘制人口数量随时间变化的图表
    :param years: 年份列表
    :param population: 人口数量列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, population, label="Population", color="green", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Population")
    plt.title("Population Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"population_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"人口数量图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_government_budget_over_time(years, government_budget, experiment_type="default"):
    """
    绘制政府预算随时间变化的图表
    :param years: 年份列表
    :param government_budget: 政府预算列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, government_budget, label="Government Budget", color="purple", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Government Budget")
    plt.title("Government Budget Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"government_budget_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"政府预算图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_rebellion_strength_over_time(years, rebellion_strength, experiment_type="default"):
    """
    绘制叛乱强度随时间变化的图表
    :param years: 年份列表
    :param rebellion_strength: 叛乱强度列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, rebellion_strength, label="Rebellion Strength", color="orange", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Rebellion Strength")
    plt.title("Rebellion Strength Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"rebellion_strength_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"叛乱强度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_satisfaction_over_time(years, average_satisfaction, experiment_type="default"):
    """
    绘制平均满意度随时间变化的图表
    :param years: 年份列表
    :param average_satisfaction: 平均满意度列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, average_satisfaction, label="Average Satisfaction", color="cyan", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Average Satisfaction")
    plt.title("Average Satisfaction Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"average_satisfaction_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"平均满意度图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_tax_rate_over_time(years, tax_rate, experiment_type="default"):
    """
    绘制税率随时间变化的图表
    :param years: 年份列表
    :param tax_rate: 税率列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, tax_rate, label="Tax Rate", color="magenta", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Tax Rate")
    plt.title("Tax Rate Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"tax_rate_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"税率图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_river_navigability_over_time(years, river_navigability, experiment_type="default"):
    """
    绘制河流通航性随时间变化的图表
    :param years: 年份列表
    :param river_navigability: 河流通航性列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, river_navigability, label="River Navigability", color="brown", marker="o")
    plt.xlabel("Year")
    plt.ylabel("River Navigability")
    plt.title("River Navigability Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"river_navigability_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"河流通航性图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_gdp_over_time(years, gdp, experiment_type="default"):
    """
    绘制GDP随时间变化的图表
    :param years: 年份列表
    :param gdp: GDP列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, gdp, label="GDP", color="gray", marker="o")
    plt.xlabel("Year")
    plt.ylabel("GDP")
    plt.title("GDP Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"gdp_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"GDP图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_urban_scale_over_time(years, urban_scale, experiment_type="default"):
    """
    绘制城市规模随时间变化的图表
    :param years: 年份列表
    :param urban_scale: 城市规模列表
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plt.figure(figsize=(10, 6))
    plt.plot(years, urban_scale, label="Urban Scale", color="blue", marker="o")
    plt.xlabel("Year")
    plt.ylabel("Urban Scale")
    plt.title("Urban Scale Over Time")
    plt.legend()
    plt.grid(True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "experiment_dataset/plot_results"
    save_dir = os.path.join(base_dir, experiment_type)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, f"urban_scale_{current_time}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"城市规模图表已保存至：{save_path}")
    plt.close()
    return save_path

def plot_all_results(years, experiment_type="default", rebellions=None, unemployment_rate=None, population=None, 
                    government_budget=None, rebellion_strength=None, average_satisfaction=None, tax_rate=None, 
                    river_navigability=None, gdp=None, urban_scale=None):
    """
    绘制所有结果的图表并保存数据表格
    :param experiment_type: 实验类型，用于确定保存路径的子文件夹
    """
    plot_paths = []

    # 绘制各个指标的图表
    if rebellions is not None:
        plot_paths.append(plot_rebellions_over_time(years, rebellions, experiment_type))
    if unemployment_rate is not None:
        plot_paths.append(plot_unemployment_rate_over_time(years, unemployment_rate, experiment_type))
    if population is not None:
        plot_paths.append(plot_population_over_time(years, population, experiment_type))
    if government_budget is not None:
        plot_paths.append(plot_government_budget_over_time(years, government_budget, experiment_type))
    if rebellion_strength is not None:
        plot_paths.append(plot_rebellion_strength_over_time(years, rebellion_strength, experiment_type))
    if average_satisfaction is not None:
        plot_paths.append(plot_satisfaction_over_time(years, average_satisfaction, experiment_type))
    if tax_rate is not None:
        plot_paths.append(plot_tax_rate_over_time(years, tax_rate, experiment_type))
    if river_navigability is not None:
        plot_paths.append(plot_river_navigability_over_time(years, river_navigability, experiment_type))
    if gdp is not None:
        plot_paths.append(plot_gdp_over_time(years, gdp, experiment_type))
    if urban_scale is not None:
        plot_paths.append(plot_urban_scale_over_time(years, urban_scale, experiment_type))
    
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