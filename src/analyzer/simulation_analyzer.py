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

plt.rcParams['font.family'] = 'Times New Roman'  # Use Times New Roman font
plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign display issue
plt.rcParams['font.size'] = 14  # Increase base font size
plt.rcParams['axes.labelsize'] = 16  # Increase axis label size
plt.rcParams['axes.titlesize'] = 18  # Increase title size
plt.rcParams['xtick.labelsize'] = 14  # Increase x-tick label size
plt.rcParams['ytick.labelsize'] = 14  # Increase y-tick label size
plt.rcParams['legend.fontsize'] = 14  # Increase legend font size

class SimulationType(Enum):
    DEFAULT = "default"
    TEOG = "TEOG"
    INFO_PROPAGATION = "info_propagation"

class SimulationAnalyzer:
    # 定义特定指标的标记映射
    METRIC_LABELS = {
        'river_navigability': ('Canal Navigability', '(a)'),
        'unemployment_rate': ('Unemployment Rate', '(b)'),
        'average_satisfaction': ('Average Satisfaction', '(c)'),
        'rebellion_resources': ('Rebellion Resources', '(d)')
    }
    
    def __init__(self, simulation_type: SimulationType, p_value: Optional[int] = None, y_value: Optional[int] = None, input_files: Optional[List[str]] = None, output_dir: Optional[str] = None):
        """
        初始化模拟分析器
        :param simulation_type: 模拟类型
        :param p_value: 过滤参数p的值
        :param y_value: 过滤参数y的值
        :param input_files: 指定要分析的文件列表
        :param output_dir: 指定保存分析结果的目录
        """
        self.simulation_type = simulation_type
        self.history_folder = os.path.join("history", simulation_type.value)
        self.p_value = p_value
        self.y_value = y_value
        self.input_files = input_files
        self.custom_output_dir = output_dir
        
        # 创建带时间戳的输出目录（支持自定义保存地址）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.custom_output_dir:
            self.analysis_results_dir = os.path.join(self.custom_output_dir, timestamp)
        else:
            self.analysis_results_dir = os.path.join(self.history_folder, 'analysis_results', timestamp)
        os.makedirs(self.analysis_results_dir, exist_ok=True)
        self.analysis_results_full_path = os.path.abspath(self.analysis_results_dir)
        print(f"分析结果将保存至: {self.analysis_results_full_path}")
        
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
        
        if self.input_files:
            # 直接分析指定文件
            for file_path in self.input_files:
                try:
                    if file_path.endswith('.json'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            numeric_data = self.extract_numeric_data(data)
                            if numeric_data:
                                json_results.append(numeric_data)
                                print(f"从 {os.path.basename(file_path)} 提取了 {len(numeric_data)} 个指标")
                    elif file_path.endswith('.csv'):
                        df = pd.read_csv(file_path)
                        if 'years' not in df.columns:
                            print(f"警告：CSV文件 {os.path.basename(file_path)} 缺少必要的'years'列")
                            continue
                        csv_dataframes.append(df)
                        print(f"加载CSV文件: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"无法加载文件 {file_path}: {e}")
        else:
            # 遍历历史文件夹下的所有子文件夹（时间戳文件夹）
            for timestamp_dir in glob.glob(os.path.join(self.history_folder, "*")):
                if not os.path.isdir(timestamp_dir):
                    continue
                # ...existing code...
                dir_name = os.path.basename(timestamp_dir)
                p_match = re.search(r'_p(\d+)', dir_name) or re.search(r'p(\d+)', dir_name)
                y_match = re.search(r'_y(\d+)', dir_name) or re.search(r'y(\d+)', dir_name)
                current_p = int(p_match.group(1)) if p_match else None
                current_y = int(y_match.group(1)) if y_match else None
                if self.p_value is not None and current_p != self.p_value:
                    continue
                if self.y_value is not None and current_y != self.y_value:
                    continue
                running_data_files = glob.glob(os.path.join(timestamp_dir, "running_data_*.json"))
                running_data_files.extend(glob.glob(os.path.join(timestamp_dir, "running_data_*.csv")))
                for file_path in running_data_files:
                    try:
                        if file_path.endswith('.json'):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                numeric_data = self.extract_numeric_data(data)
                                if numeric_data:
                                    json_results.append(numeric_data)
                                    print(f"从 {os.path.basename(file_path)} 提取了 {len(numeric_data)} 个指标")
                        elif file_path.endswith('.csv'):
                            df = pd.read_csv(file_path)
                            if 'years' not in df.columns:
                                print(f"警告：CSV文件 {os.path.basename(file_path)} 缺少必要的'years'列")
                                continue
                            csv_dataframes.append(df)
                            print(f"加载CSV文件: {os.path.basename(file_path)}")
                    except Exception as e:
                        print(f"无法加载文件 {file_path}: {e}")
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
            df['years'] = pd.to_numeric(df['years'], errors='coerce')
            all_years.update(df['years'].dropna().unique())
        all_years = sorted([int(y) for y in all_years if not np.isnan(y)])
        
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

    def format_metric_name(self, metric: str) -> str:
        """
        格式化指标名称：将下划线替换为空格，每个单词首字母大写
        :param metric: 原始指标名
        :return: 格式化后的指标名
        """
        return ' '.join(word.capitalize() for word in metric.split('_'))
    
    def get_metric_title(self, metric: str) -> str:
        """
        获取指标的完整标题（包括标记）
        :param metric: 指标名
        :return: 完整标题
        """
        if metric in self.METRIC_LABELS:
            formatted_name, label = self.METRIC_LABELS[metric]
            return f'{label} {formatted_name}'
        else:
            return self.format_metric_name(metric)
    
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
                
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 绘制平均值线
            mean_line = ax.plot(years, result[f'{metric}_mean'], 
                               label='Mean', color='blue', linewidth=2)
            
            # 添加标准差区域
            if f'{metric}_std' in result:
                mean_array = np.array(result[f'{metric}_mean'])
                std_array = np.array(result[f'{metric}_std'])
                ax.fill_between(years, 
                               mean_array - std_array,
                               mean_array + std_array,
                               alpha=0.2, color='blue',
                               label='±1 Std Dev')
            
            # 添加最大值和最小值
            if f'{metric}_max' in result and f'{metric}_min' in result:
                ax.plot(years, result[f'{metric}_max'], 
                       '--', color='red', alpha=0.5, label='Maximum')
                ax.plot(years, result[f'{metric}_min'], 
                       '--', color='green', alpha=0.5, label='Minimum')
            
            ax.set_xlabel('Year')
            ax.set_ylabel(self.format_metric_name(metric))
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Limit x-axis ticks to maximum 20
            if len(years) > 20:
                step = len(years) // 20
                tick_indices = list(range(0, len(years), step))
                if len(years) - 1 not in tick_indices:
                    tick_indices.append(len(years) - 1)
                ax.set_xticks([years[i] for i in tick_indices])
            else:
                ax.set_xticks(years)
            
            # 添加标题到图片下方
            title_text = self.get_metric_title(metric)
            fig.text(0.5, -0.05, title_text, ha='center', fontsize=18, weight='bold')
            
            # 保存图表
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(self.analysis_results_dir, f'{metric}_time_series_{current_time}.png')
            plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
            plt.close()
            # 输出完整绝对路径
            save_path_full = os.path.abspath(save_path)
            print(f"已保存时序统计图：{save_path_full}")

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
        
        # 合并所有结果中的指标，保持第一次出现的顺序
        all_metrics = []
        seen_metrics = set()
        for result in results:
            for metric in result.keys():
                if metric not in seen_metrics:
                    all_metrics.append(metric)
                    seen_metrics.add(metric)
            
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

    def _find_common_suffix(self, strings: List[str]) -> str:
        """
        找出字符串列表的最长公共后缀
        :param strings: 字符串列表
        :return: 公共后缀
        """
        if not strings:
            return ""
        if len(strings) == 1:
            return strings[0]
        
        # 将字符串按下划线分割并反转
        split_strings = [s.split('_')[::-1] for s in strings]
        
        # 找出公共后缀部分
        common_parts = []
        min_length = min(len(s) for s in split_strings)
        
        for i in range(min_length):
            parts_at_i = [s[i] for s in split_strings]
            if len(set(parts_at_i)) == 1:  # 所有字符串在这个位置都相同
                common_parts.append(parts_at_i[0])
            else:
                break
        
        # 反转回来并用下划线连接
        return '_'.join(common_parts[::-1]) if common_parts else ""

    def plot_statistics(self, stats: Dict[str, Dict[str, float]], output_dir: str = "history"):
        """
        绘制统计图表
        :param stats: 统计数据
        :param output_dir: 输出目录
        """
        if not stats:
            print("警告：没有数据可以绘制图表")
            return
        
        # 首先按最后两个部分进行初步分组
        temp_groups = {}
        for metric_name, metric_data in stats.items():
            parts = metric_name.split('_')
            if len(parts) >= 2:
                temp_key = '_'.join(parts[-2:])
            else:
                temp_key = metric_name
            
            if temp_key not in temp_groups:
                temp_groups[temp_key] = []
            temp_groups[temp_key].append((metric_name, metric_data))
        
        # 对每个初步分组找出公共后缀作为真正的组键
        grouped_metrics = {}
        group_order = []
        
        for temp_key, metrics_list in temp_groups.items():
            metric_names = [m[0] for m in metrics_list]
            # 找出这组指标的公共后缀
            group_key = self._find_common_suffix(metric_names)
            
            # 如果没有公共后缀，使用临时键
            if not group_key:
                group_key = temp_key
            
            if group_key not in grouped_metrics:
                grouped_metrics[group_key] = []
                group_order.append(group_key)
            grouped_metrics[group_key].extend(metrics_list)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for group_key in group_order:  # 按原始顺序遍历组
            metrics_in_group = grouped_metrics[group_key]
            # 保持原始顺序，不再按平均值排序
            
            metrics = [m[0] for m in metrics_in_group]
            means = [m[1]['mean'] for m in metrics_in_group]
            stds = [m[1]['std'] for m in metrics_in_group]
            
            if not metrics:
                print(f"警告：组 '{group_key}' 中没有有效指标，跳过绘图。")
                continue

            # Limit to top 20 metrics if more than 20
            if len(metrics) > 20:
                metrics = metrics[:20]
                means = means[:20]
                stds = stds[:20]

            # 简化横坐标标签：移除与组键（标题）重复的后缀
            simplified_labels = []
            for metric in metrics:
                # 如果指标名称以组键结尾，则移除该后缀
                if metric.endswith(group_key) and len(metric) > len(group_key):
                    # 移除后缀和分隔符
                    prefix = metric[:-len(group_key)].rstrip('_')
                    simplified_labels.append(prefix if prefix else metric)
                else:
                    simplified_labels.append(metric)

            fig, ax = plt.subplots(figsize=(15, 8))
            x = np.arange(len(metrics))
            ax.bar(x, means, yerr=stds, align='center', alpha=0.8, capsize=5)
            
            ax.set_xticks(x)
            ax.set_xticklabels(simplified_labels, rotation=45, ha='right')
            ax.set_ylabel('Value')
            ax.grid(True, axis='y', linestyle='--', alpha=0.7)
            
            # 添加标题到图片下方
            title_text = f'{self.simulation_type.value} Simulation Statistics - {self.format_metric_name(group_key)}'
            fig.text(0.5, -0.05, title_text, ha='center', fontsize=18, weight='bold')
            
            # 调整布局以防止标签被切off
            plt.tight_layout()
            
            # 保存图表
            output_path = os.path.join(self.analysis_results_dir, f'statistics_{group_key}_{timestamp}.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
            plt.close()
            # 输出完整绝对路径
            output_path_full = os.path.abspath(output_path)
            print(f"已保存统计图表：{output_path_full}")

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
        
        # 保持原始顺序，不再排序
        
        report.append("\n| Metric | Mean | Std Dev | Min | Max | Count |")
        report.append("|--------|------|---------|-----|-----|-------|")
        
        for metric, data in stats.items():
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
        report_path = os.path.join(self.analysis_results_dir, f'{report_type}_statistics_report_{timestamp}.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        # 输出完整绝对路径
        report_path_full = os.path.abspath(report_path)
        print(f"已生成{report_type.upper()}统计报告：{report_path_full}")
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
            
        years = csv_data['years']
        
        # 提取所有指标（除了years）
        metrics = []
        seen_metrics = set()
        for key in csv_data.keys():
            if key != 'years':
                # 提取基本指标名（去掉_mean, _std等后缀）
                base_metric = key.rsplit('_', 1)[0]
                if base_metric not in seen_metrics:
                    metrics.append(base_metric)
                    seen_metrics.add(base_metric)
        
        # 生成详细报告
        report = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report.append(f"# {self.simulation_type.value} 模拟CSV统计报告")
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 添加整体统计概要
        report.append("\n## 统计概要（跨所有年份）")
        report.append("\n| Metric | Mean | Std Dev | Min | Max | Count |")
        report.append("|--------|------|---------|-----|-----|-------|")
        
        # 计算每个指标的整体统计数据
        overall_stats = {}
        for metric in metrics:
            if f'{metric}_mean' in csv_data:
                # 过滤掉NaN值
                mean_values = [v for v in csv_data[f'{metric}_mean'] if not np.isnan(v)]
                if not mean_values:
                    continue
                    
                overall_stats[metric] = {
                    'mean': np.mean(mean_values),
                    'std': np.std(mean_values) if len(mean_values) > 1 else 0,
                    'min': np.min(mean_values),
                    'max': np.max(mean_values),
                    'count': len(mean_values)
                }
                
                data = overall_stats[metric]
                report.append(
                    f"| {metric} | {data['mean']:.4f} | "
                    f"{data['std']:.4f} | "
                    f"{data['min']:.4f} | "
                    f"{data['max']:.4f} | "
                    f"{data['count']} |"
                )
        
        # 2. 为每个指标添加详细的年度数据表
        for metric in metrics:
            if f'{metric}_mean' not in csv_data:
                continue
                
            report.append(f"\n## {metric} - 年度详细数据")
            report.append("\n| Year | Mean | Std Dev | Min | Max |")
            report.append("|------|------|---------|-----|-----|")
            
            mean_data = csv_data.get(f'{metric}_mean', [])
            std_data = csv_data.get(f'{metric}_std', [])
            min_data = csv_data.get(f'{metric}_min', [])
            max_data = csv_data.get(f'{metric}_max', [])
            
            for i, year in enumerate(years):
                if i >= len(mean_data):
                    break
                    
                mean_val = mean_data[i] if i < len(mean_data) else np.nan
                std_val = std_data[i] if i < len(std_data) else np.nan
                min_val = min_data[i] if i < len(min_data) else np.nan
                max_val = max_data[i] if i < len(max_data) else np.nan
                
                # 格式化数值，处理NaN
                mean_str = f"{mean_val:.4f}" if not np.isnan(mean_val) else "N/A"
                std_str = f"{std_val:.4f}" if not np.isnan(std_val) else "N/A"
                min_str = f"{min_val:.4f}" if not np.isnan(min_val) else "N/A"
                max_str = f"{max_val:.4f}" if not np.isnan(max_val) else "N/A"
                
                report.append(
                    f"| {year} | {mean_str} | {std_str} | {min_str} | {max_str} |"
                )
        
        # 保存报告
        report_path = os.path.join(self.analysis_results_dir, f'csv_statistics_report_{timestamp}.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        # 输出完整绝对路径
        report_path_full = os.path.abspath(report_path)
        print(f"已生成CSV统计报告：{report_path_full}")
        return report_path

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='模拟结果分析工具')
    parser.add_argument('--type', type=str, choices=['default', 'TEOG', 'info_propagation'],
                      required=True, help='模拟类型')
    parser.add_argument('--p', type=int, help='过滤参数p的值')
    parser.add_argument('--y', type=int, help='过滤参数y的值')
    parser.add_argument('--input_files', type=str, nargs='*', help='指定要分析的文件路径（支持多个）')
    parser.add_argument('--output_dir', type=str, help='指定分析结果保存目录')

    args = parser.parse_args()

    # 创建分析器实例，支持新参数
    analyzer = SimulationAnalyzer(
        SimulationType(args.type),
        p_value=args.p,
        y_value=args.y,
        input_files=args.input_files,
        output_dir=args.output_dir
    )

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

    print(f"\n{'='*80}")
    print(f"分析完成！所有结果已保存至：")
    print(f"{analyzer.analysis_results_full_path}")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()