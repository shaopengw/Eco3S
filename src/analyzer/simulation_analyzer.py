import re
import os
import pandas as pd
import numpy as np
from enum import Enum
import glob
import json
from typing import List, Dict, Any, Optional, Tuple
import matplotlib.pyplot as plt
from datetime import datetime

# 配置matplotlib支持中文显示
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']  # 使用微软雅黑或黑体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

class SimulationType(Enum):
    DEFAULT = "default"
    TEOG = "TEOG"
    INFO_PROPAGATION = "info_propagation"

class SimulationAnalyzer:
    def __init__(self, simulation_type: SimulationType, p_value: Optional[int] = None, y_value: Optional[int] = None):
        """
        初始化模拟分析器
        :param simulation_type: 模拟类型
        :param p_value: 过滤参数p的值
        :param y_value: 过滤参数y的值
        """
        self.simulation_type = simulation_type
        self.history_folder = os.path.join("history", simulation_type.value)
        self.p_value = p_value
        self.y_value = y_value
        
        # 定义每种模拟类型的关键指标
        self.metrics = {
            SimulationType.DEFAULT: [
                "unemployment_rate", "population", "government_budget",
                "rebellion_strength", "average_satisfaction", "tax_rate",
                "river_navigability", "gdp"
            ],
            SimulationType.TEOG: [
                "population", "government_budget", "average_satisfaction",
                "tax_rate", "river_navigability", "gdp", "urban_scale"
            ],
            SimulationType.INFO_PROPAGATION: [
                "information_spread_rate", "belief_change_rate",
                "network_density", "average_influence"
            ]
        }

    def extract_numeric_data(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
        """
        递归提取数值型数据
        :param data: 输入数据字典
        :param prefix: 当前键的前缀
        :return: 数值型数据字典
        """
        numeric_data = {}
        for key, value in data.items():
            current_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, (int, float)):
                numeric_data[current_key] = float(value)
            elif isinstance(value, dict):
                # 递归处理嵌套字典
                nested_data = self.extract_numeric_data(value, current_key)
                numeric_data.update(nested_data)
        
        return numeric_data

    def load_simulation_results(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        加载历史运行数据
        :return: 运行数据列表 (json_results, csv_results)
        """
        json_results = []
        csv_dataframes = []
        
        # 遍历历史文件夹下的所有子文件夹（时间戳文件夹）
        for timestamp_dir in glob.glob(os.path.join(self.history_folder, "*")):
            if not os.path.isdir(timestamp_dir):
                continue
            
            # 提取文件夹名称中的p和y值进行过滤
            dir_name = os.path.basename(timestamp_dir)
            p_match = re.search(r'p(\d+)', dir_name)
            y_match = re.search(r'y(\d+)', dir_name)
            
            current_p = int(p_match.group(1)) if p_match else None
            current_y = int(y_match.group(1)) if y_match else None
            
            if self.p_value is not None and current_p != self.p_value:
                # print(f"跳过文件夹 {dir_name}: p值不匹配 (期望: {self.p_value}, 实际: {current_p})")
                continue
            if self.y_value is not None and current_y != self.y_value:
                # print(f"跳过文件夹 {dir_name}: y值不匹配 (期望: {self.y_value}, 实际: {current_y})")
                continue
                
            # 查找运行数据文件 (支持json和csv)
            running_data_files = glob.glob(os.path.join(timestamp_dir, "running_data_*.json"))
            running_data_files.extend(glob.glob(os.path.join(timestamp_dir, "running_data_*.csv")))
            
            for file_path in running_data_files:
                try:
                    if file_path.endswith('.json'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            numeric_data = self.extract_numeric_data(data)
                            if numeric_data:  # 只添加非空数据
                                json_results.append(numeric_data)
                                print(f"从 {os.path.basename(file_path)} 提取了 {len(numeric_data)} 个指标")
                    elif file_path.endswith('.csv'):
                        df = pd.read_csv(file_path)
                        if 'years' not in df.columns:
                            print(f"警告：CSV文件 {os.path.basename(file_path)} 缺少必要的'years'列")
                            continue
                        
                        # 收集所有CSV数据框
                        csv_dataframes.append(df)
                        print(f"加载CSV文件: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"无法加载文件 {file_path}: {e}")
        
        # 处理所有CSV数据框
        csv_results = self.process_csv_data(csv_dataframes) if csv_dataframes else {}
        
        return json_results, csv_results

    def process_csv_data(self, dataframes: List[pd.DataFrame]) -> Dict[str, Any]:
        """
        处理多个CSV数据框，合并相同年份相同指标的数据
        :param dataframes: 包含时序数据的DataFrame列表
        :return: 处理后的数据字典
        """
        if not dataframes:
            return {}
            
        # 合并所有年份
        all_years = set()
        for df in dataframes:
            all_years.update(df['years'].unique())
        all_years = sorted(list(all_years))
        
        # 初始化结果字典
        processed_data = {'years': all_years}
        
        # 获取所有指标（除了years）
        all_metrics = set()
        for df in dataframes:
            all_metrics.update([col for col in df.columns if col != 'years'])
        
        # 为每个指标创建一个空的DataFrame，索引为年份
        metric_data = {metric: pd.DataFrame(index=all_years) for metric in all_metrics}
        
        # 填充每个指标的数据
        for df in dataframes:
            for metric in all_metrics:
                if metric in df.columns:
                    # 对于每个年份，收集该指标的所有值
                    for year in df['years'].unique():
                        values = df[df['years'] == year][metric].values
                        if year not in metric_data[metric].index:
                            continue
                        
                        # 将值添加到对应的年份行
                        if f'values_{metric}' not in metric_data[metric].columns:
                            metric_data[metric][f'values_{metric}'] = [[] for _ in range(len(all_years))]
                        
                        year_idx = metric_data[metric].index.get_loc(year)
                        metric_data[metric].at[year, f'values_{metric}'].extend(values.tolist())
        
        # 计算每个指标每个年份的统计值
        for metric, df in metric_data.items():
            if f'values_{metric}' not in df.columns:
                continue
                
            # 计算统计值
            mean_values = []
            std_values = []
            min_values = []
            max_values = []
            
            for year in all_years:
                values = df.loc[year, f'values_{metric}']
                if values:
                    mean_values.append(np.mean(values))
                    std_values.append(np.std(values))
                    min_values.append(np.min(values))
                    max_values.append(np.max(values))
                else:
                    # 如果没有数据，使用NaN
                    mean_values.append(np.nan)
                    std_values.append(np.nan)
                    min_values.append(np.nan)
                    max_values.append(np.nan)
            
            # 将统计值添加到结果字典
            processed_data[f'{metric}_mean'] = mean_values
            processed_data[f'{metric}_std'] = std_values
            processed_data[f'{metric}_min'] = min_values
            processed_data[f'{metric}_max'] = max_values
        
        return processed_data

    def plot_time_series_statistics(self, result: Dict[str, Any]):
        """
        为CSV数据绘制时序统计图
        :param result: 包含时序统计数据的字典
        """
        if not result or 'years' not in result:
            print("警告：没有有效的时序数据可以绘图")
            return
                
        years = result['years']
        
        # 遍历所有指标（跳过years）
        metrics = set()
        for key in result.keys():
            if key != 'years':
                # 提取基本指标名（去掉_mean, _std等后缀）
                base_metric = key.rsplit('_', 1)[0]
                metrics.add(base_metric)
        
        # 为每个基本指标创建一个图表
        for metric in metrics:
            if f'{metric}_mean' not in result:
                continue
                
            plt.figure(figsize=(12, 6))
            
            # 绘制平均值线
            mean_line = plt.plot(years, result[f'{metric}_mean'], 
                               label='平均值', color='blue', linewidth=2)
            
            # 添加标准差区域
            if f'{metric}_std' in result:
                mean_array = np.array(result[f'{metric}_mean'])
                std_array = np.array(result[f'{metric}_std'])
                plt.fill_between(years, 
                               mean_array - std_array,
                               mean_array + std_array,
                               alpha=0.2, color='blue',
                               label='±1 标准差')
            
            # 添加最大值和最小值
            if f'{metric}_max' in result and f'{metric}_min' in result:
                plt.plot(years, result[f'{metric}_max'], 
                       '--', color='red', alpha=0.5, label='最大值')
                plt.plot(years, result[f'{metric}_min'], 
                       '--', color='green', alpha=0.5, label='最小值')
            
            plt.title(f'{metric} 时序统计')
            plt.xlabel('年份')
            plt.ylabel(metric)
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            # 保存图表
            plots_dir = os.path.join(self.history_folder, 'analysis_results')
            os.makedirs(plots_dir, exist_ok=True)
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(plots_dir, f'{metric}_time_series_{current_time}.png')
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"已保存时序统计图：{save_path}")

    def calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """
        计算统计数据
        :param results: 运行数据列表
        :return: 统计数据字典
        """
        if not results:
            print("警告：没有找到任何有效的数据进行分析")
            return {}
            
        stats = {}
        
        # 合并所有结果中的指标
        all_metrics = set()
        for result in results:
            all_metrics.update(result.keys())
            
        for metric in all_metrics:
            values = [result[metric] for result in results if metric in result]
            if not values:
                continue
                
            stats[metric] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'count': len(values)
            }
        
        return stats

    def plot_statistics(self, stats: Dict[str, Dict[str, float]], output_dir: str = "history"):
        """
        绘制统计图表
        :param stats: 统计数据
        :param output_dir: 输出目录
        """
        if not stats:
            print("警告：没有数据可以绘制图表")
            return
            
        # 确保输出目录存在
        os.makedirs(os.path.join(output_dir, self.simulation_type.value, 'analysis_results'), exist_ok=True)
        
        # 根据指标名称的后缀进行分组
        grouped_metrics = {}
        for metric_name, metric_data in stats.items():
            # 从指标名称的末尾开始匹配，将最后两个词相同的指标视为同一组
            parts = metric_name.split('_')
            if len(parts) >= 2:
                group_key = '_'.join(parts[-2:]) # 取最后两个部分作为组键
            else:
                group_key = metric_name # 如果不足两个部分，则使用完整指标名作为组键
            
            if group_key not in grouped_metrics:
                grouped_metrics[group_key] = []
            grouped_metrics[group_key].append((metric_name, metric_data))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for group_key, metrics_in_group in grouped_metrics.items():
            # 按平均值绝对值排序组内指标
            sorted_group_metrics = sorted(
                metrics_in_group,
                key=lambda x: abs(x[1]['mean']),
                reverse=True
            )
            
            metrics = [m[0] for m in sorted_group_metrics]
            means = [m[1]['mean'] for m in sorted_group_metrics]
            stds = [m[1]['std'] for m in sorted_group_metrics]
            
            if not metrics:
                print(f"警告：组 '{group_key}' 中没有有效指标，跳过绘图。")
                continue

            plt.figure(figsize=(15, 8))
            x = np.arange(len(metrics))
            plt.bar(x, means, yerr=stds, align='center', alpha=0.8, capsize=5)
            
            plt.title(f'{self.simulation_type.value} 模拟统计数据 - {group_key}')
            plt.xticks(x, metrics, rotation=45, ha='right')
            plt.ylabel('数值')
            plt.grid(True, axis='y', linestyle='--', alpha=0.7)
            
            # 调整布局以防止标签被切off
            plt.tight_layout()
            
            # 保存图表
            output_path = os.path.join(output_dir, self.simulation_type.value,'analysis_results', f'statistics_{group_key}_{timestamp}.png')
            plt.savefig(output_path)
            plt.close()

    def generate_report(self, stats: Dict[str, Dict[str, float]], output_dir: str = "history", report_type: str = "json"):
        """
        生成统计报告
        :param stats: 统计数据
        :param output_dir: 输出目录
        :param report_type: 报告类型 (json 或 csv)
        """
        if not stats:
            print(f"警告：没有{report_type}数据可以生成报告")
            return
            
        report = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report.append(f"# {self.simulation_type.value} 模拟{report_type.upper()}统计报告")
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("\n## 统计概要")
        
        # 按平均值降序排序指标
        sorted_metrics = sorted(stats.items(), key=lambda x: abs(x[1]['mean']) if 'mean' in x[1] else 0, reverse=True)
        
        report.append("\n| 指标 | 平均值 | 标准差 | 最小值 | 最大值 | 样本数 |")
        report.append("|------|--------|--------|--------|--------|--------|")
        
        for metric, data in sorted_metrics:
            mean_val = data.get('mean', 'N/A')
            std_val = data.get('std', 'N/A')
            min_val = data.get('min', 'N/A')
            max_val = data.get('max', 'N/A')

            # 检查并处理 numpy.nan 值
            mean_val = 'N/A' if pd.isna(mean_val) else mean_val
            std_val = 'N/A' if pd.isna(std_val) else std_val
            min_val = 'N/A' if pd.isna(min_val) else min_val
            max_val = 'N/A' if pd.isna(max_val) else max_val

            # 应用格式化，只对数值类型进行浮点数格式化
            formatted_mean = f"{mean_val:.4f}" if isinstance(mean_val, (int, float)) else str(mean_val)
            formatted_std = f"{std_val:.4f}" if isinstance(std_val, (int, float)) else str(std_val)
            formatted_min = f"{min_val:.4f}" if isinstance(min_val, (int, float)) else str(min_val)
            formatted_max = f"{max_val:.4f}" if isinstance(max_val, (int, float)) else str(max_val)

            report.append(
                f"| {metric} | {formatted_mean} | "
                f"{formatted_std} | "
                f"{formatted_min} | "
                f"{formatted_max} | "
                f"{data.get('count', 'N/A')} |"
            )
        
        # 保存报告
        os.makedirs(os.path.join(output_dir, self.simulation_type.value, 'analysis_results'), exist_ok=True)
        report_path = os.path.join(output_dir, self.simulation_type.value,'analysis_results', f'{report_type}_statistics_report_{timestamp}.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print(f"已生成{report_type.upper()}统计报告：{report_path}")
        return report_path

    def generate_csv_report(self, csv_data: Dict[str, Any], output_dir: str = "history"):
        """
        为CSV数据生成统计报告
        :param csv_data: CSV数据
        :param output_dir: 输出目录
        """
        if not csv_data or 'years' not in csv_data:
            print("警告：没有有效的CSV数据可以生成报告")
            return
            
        # 提取所有指标（除了years）
        metrics = set()
        for key in csv_data.keys():
            if key != 'years':
                # 提取基本指标名（去掉_mean, _std等后缀）
                base_metric = key.rsplit('_', 1)[0]
                metrics.add(base_metric)
        
        # 计算每个指标的统计数据
        stats = {}
        for metric in metrics:
            if f'{metric}_mean' in csv_data:
                # 过滤掉NaN值
                mean_values = [v for v in csv_data[f'{metric}_mean'] if not np.isnan(v)]
                if not mean_values:
                    continue
                    
                stats[metric] = {
                    'mean': np.mean(mean_values),
                    'std': np.std(mean_values) if len(mean_values) > 1 else 0,
                    'min': np.min(mean_values),
                    'max': np.max(mean_values),
                    'count': len(mean_values)
                }
        
        # 生成报告
        return self.generate_report(stats, output_dir, "csv")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='模拟结果分析工具')
    parser.add_argument('--type', type=str, choices=['default', 'TEOG', 'info_propagation'],
                      required=True, help='模拟类型')
    parser.add_argument('--p', type=int, help='过滤参数p的值')
    parser.add_argument('--y', type=int, help='过滤参数y的值')
    
    args = parser.parse_args()
    
    # 创建分析器实例
    analyzer = SimulationAnalyzer(SimulationType(args.type), p_value=args.p, y_value=args.y)
    
    # 加载运行数据
    json_results, csv_results = analyzer.load_simulation_results()
    
    if not json_results and not csv_results:
        print(f"未找到任何运行数据文件")
        return
    
    print(f"找到 {len(json_results)} 个JSON运行数据文件和 {len(csv_results.keys()) if isinstance(csv_results, dict) and 'years' in csv_results else 0} 个CSV运行数据文件")
    
    stats = {} # Initialize stats to avoid NameError if json_results is empty

    if json_results:
        # 计算统计数据 (只针对JSON数据)
        stats = analyzer.calculate_statistics(json_results)
        
        # 生成统计图表 (只针对JSON数据)
        analyzer.plot_statistics(stats)
        
        # 生成报告 (只针对JSON数据)
        analyzer.generate_report(stats)
    else:
        print("警告：未找到JSON运行数据文件，跳过JSON数据分析、绘图和报告生成。")

    if csv_results and isinstance(csv_results, dict) and 'years' in csv_results:
        # 生成时序统计图（针对CSV数据）
        analyzer.plot_time_series_statistics(csv_results)
        
        # 为CSV数据生成统计报告
        analyzer.generate_csv_report(csv_results)
    else:
        print("警告：未找到CSV运行数据文件，跳过CSV时序数据绘图和报告生成。")
    
    print(f"分析完成！结果保存在 history/{args.type}/analysis_results/ 目录下")

if __name__ == "__main__":
    main()