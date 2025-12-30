"""
叛军数据分析模块
分析叛军log数据和城镇信息，统计沿河和非沿河城镇的叛乱情况
"""

import json
import re
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Tuple
from scipy import stats
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class RebellionAnalyzer:
    """叛军数据分析器"""
    
    def __init__(self, log_path, towns_data_path: str, start_year: int = 1650):
        """
        初始化分析器
        
        Args:
            log_path: 叛军log文件路径，可以是：
                     - 单个文件路径字符串
                     - 多个文件路径的列表
                     - 包含log文件的目录路径（会递归查找所有子文件夹中的rebels_*.log文件）
            towns_data_path: 城镇数据JSON文件路径
            start_year: 模拟开始年份，默认1650年
        """
        self.towns_data_path = Path(towns_data_path)
        self.start_year = start_year
        
        # 处理log路径，统一转换为路径列表
        self.log_paths = self._process_log_paths(log_path)
        print(f"找到 {len(self.log_paths)} 个叛军log文件")
        
        # 加载城镇数据
        self.canal_towns, self.non_canal_towns = self._load_towns_data()
        self.num_canal_towns = len(self.canal_towns)
        self.num_non_canal_towns = len(self.non_canal_towns)
        
        # 解析所有叛军决策记录
        self.all_rebellion_records = self._parse_all_rebellion_logs()
        
    def _load_towns_data(self) -> Tuple[set, set]:
        """
        加载城镇数据，区分沿河和非沿河城镇
        
        Returns:
            (沿河城镇集合, 非沿河城镇集合)
        """
        with open(self.towns_data_path, 'r', encoding='utf-8') as f:
            towns_data = json.load(f)
        
        # 收集所有沿河城镇
        canal_towns = set()
        if 'canals' in towns_data:
            for canal in towns_data['canals']:
                if 'towns' in canal:
                    for town in canal['towns']:
                        canal_towns.add(town['name'])
        
        # 收集所有非沿河城镇
        non_canal_towns = set()
        if 'other_towns' in towns_data:
            for town in towns_data['other_towns']:
                non_canal_towns.add(town['name'])
        
        print(f"沿河城镇 ({len(canal_towns)}个): {sorted(canal_towns)}")
        print(f"非沿河城镇 ({len(non_canal_towns)}个): {sorted(non_canal_towns)}")
        
        return canal_towns, non_canal_towns
    
    def _process_log_paths(self, log_path) -> List[Path]:
        """
        处理log路径参数，统一转换为路径列表
        
        Args:
            log_path: 可以是字符串、列表或Path对象
            
        Returns:
            Path对象列表
        """
        paths = []
        
        if isinstance(log_path, (str, Path)):
            path = Path(log_path)
            if path.is_dir():
                # 如果是目录，递归查找所有子文件夹中的rebels_*.log文件
                log_files = list(path.rglob('rebels_*.log'))
                if not log_files:
                    raise ValueError(f"目录 {path} 及其子目录中未找到rebels_*.log文件")
                paths.extend(sorted(log_files))
                print(f"在 {path} 及其子目录中找到 {len(log_files)} 个log文件")
            elif path.is_file():
                # 如果是文件，直接添加
                paths.append(path)
            else:
                raise ValueError(f"路径 {path} 不存在")
        elif isinstance(log_path, list):
            # 如果是列表，转换每个元素为Path
            for p in log_path:
                path = Path(p)
                if not path.is_file():
                    raise ValueError(f"文件 {path} 不存在")
                paths.append(path)
        else:
            raise ValueError(f"不支持的log_path类型: {type(log_path)}")
        
        return paths
    
    def _parse_rebellion_log(self, log_path: Path) -> List[Dict]:
        """
        解析单个叛军log文件，提取每年的叛乱决策
        
        Args:
            log_path: 单个log文件路径
            
        Returns:
            叛乱记录列表，每条记录包含年份和目标城镇信息
        """
        records = []
        
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 找到所有"叛军头子 X 的决策："的位置
        pattern = r'叛军头子 \d+ 的决策：'
        matches = list(re.finditer(pattern, content))
        
        year = self.start_year
        for i, match in enumerate(matches):
            try:
                # 找到JSON开始位置
                start_pos = match.end()
                
                # 手动解析JSON，通过括号匹配找到完整的JSON对象
                brace_count = 0
                json_start = -1
                json_end = -1
                
                for j in range(start_pos, len(content)):
                    char = content[j]
                    if char == '{':
                        if json_start == -1:
                            json_start = j
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0 and json_start != -1:
                            json_end = j + 1
                            break
                
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start:json_end]
                    decision = json.loads(json_str)
                    
                    if 'target_towns' in decision:
                        records.append({
                            'year': year,
                            'decision': decision
                        })
                        year += 1
                else:
                    print(f"警告: 第 {i+1} 条记录未找到完整的JSON")
                    year += 1
                    
            except json.JSONDecodeError as e:
                print(f"解析JSON失败: {e}")
                print(f"问题字符串: {json_str[:200] if 'json_str' in locals() else '未知'}...")
                year += 1
                continue
            except Exception as e:
                print(f"解析出错: {e}")
                year += 1
                continue
        
        return records
    
    def _parse_all_rebellion_logs(self) -> List[List[Dict]]:
        """
        解析所有叛军log文件
        
        Returns:
            二维列表，每个元素是一个log文件的记录列表
        """
        all_records = []
        
        for i, log_path in enumerate(self.log_paths, 1):
            print(f"\n解析第 {i}/{len(self.log_paths)} 个log文件: {log_path.name}")
            records = self._parse_rebellion_log(log_path)
            print(f"  成功解析 {len(records)} 年的决策记录")
            all_records.append(records)
        
        # 检查所有log的年份数是否一致
        year_counts = [len(records) for records in all_records]
        if len(set(year_counts)) > 1:
            print(f"\n警告: 不同log文件的年份数不一致: {year_counts}")
            print(f"将使用最小年份数: {min(year_counts)}")
        
        print(f"\n总共解析了 {len(all_records)} 个模拟运行")
        return all_records
    
    def analyze_yearly_rebellions(self) -> pd.DataFrame:
        """
        分析每年沿河和非沿河城镇的叛乱次数（多个log的平均值）
        
        Returns:
            包含年度统计的DataFrame，包括平均值和标准差
        """
        # 确定最小的年份数（以最短的模拟为准）
        min_years = min(len(records) for records in self.all_rebellion_records)
        
        yearly_data = []
        
        for year_idx in range(min_years):
            # 收集所有模拟在该年份的数据
            canal_counts = []
            non_canal_counts = []
            
            for records in self.all_rebellion_records:
                if year_idx >= len(records):
                    continue
                    
                record = records[year_idx]
                year = record['year']
                target_towns = record['decision'].get('target_towns', [])
                
                canal_count = 0
                non_canal_count = 0
                
                for town in target_towns:
                    town_name = town.get('town_name', '')
                    stage = town.get('stage_rebellion', 0)
                    
                    # 只统计发生叛乱的城镇（stage > 0）
                    if stage > 0:
                        if town_name in self.canal_towns:
                            canal_count += 1
                        elif town_name in self.non_canal_towns:
                            non_canal_count += 1
                
                canal_counts.append(canal_count)
                non_canal_counts.append(non_canal_count)
            
            # 计算平均值和标准差
            canal_mean = np.mean(canal_counts)
            canal_std = np.std(canal_counts, ddof=1) if len(canal_counts) > 1 else 0
            non_canal_mean = np.mean(non_canal_counts)
            non_canal_std = np.std(non_canal_counts, ddof=1) if len(non_canal_counts) > 1 else 0
            
            # 计算叛乱率（叛乱次数/城镇总数）
            canal_rate = canal_mean / self.num_canal_towns if self.num_canal_towns > 0 else 0
            non_canal_rate = non_canal_mean / self.num_non_canal_towns if self.num_non_canal_towns > 0 else 0
            
            yearly_data.append({
                '年份': self.start_year + year_idx,
                '沿河城镇叛乱次数': canal_mean,
                '沿河城镇标准差': canal_std,
                '沿河城镇叛乱率': canal_rate,
                '非沿河城镇叛乱次数': non_canal_mean,
                '非沿河城镇标准差': non_canal_std,
                '非沿河城镇叛乱率': non_canal_rate,
                '差距(次数)': canal_mean - non_canal_mean,
                '差距(率)': canal_rate - non_canal_rate,
                '样本数': len(canal_counts)
            })
        
        df = pd.DataFrame(yearly_data)
        return df
    
    def statistical_test(self, df: pd.DataFrame) -> Dict:
        """
        对沿河和非沿河城镇的叛乱次数和叛乱率进行独立样本T检验
        
        Args:
            df: 年度统计DataFrame
            
        Returns:
            统计检验结果字典
        """
        canal_rebellions = df['沿河城镇叛乱次数'].values
        non_canal_rebellions = df['非沿河城镇叛乱次数'].values
        canal_rates = df['沿河城镇叛乱率'].values
        non_canal_rates = df['非沿河城镇叛乱率'].values
        
        # 对叛乱次数进行T检验
        t_stat_count, p_value_count = stats.ttest_ind(canal_rebellions, non_canal_rebellions)
        
        # 对叛乱率进行T检验
        t_stat_rate, p_value_rate = stats.ttest_ind(canal_rates, non_canal_rates)
        
        # 计算Cohen's d (效应量)
        pooled_std_count = np.sqrt((canal_rebellions.std()**2 + non_canal_rebellions.std()**2) / 2)
        cohens_d_count = (canal_rebellions.mean() - non_canal_rebellions.mean()) / pooled_std_count if pooled_std_count > 0 else 0
        
        pooled_std_rate = np.sqrt((canal_rates.std()**2 + non_canal_rates.std()**2) / 2)
        cohens_d_rate = (canal_rates.mean() - non_canal_rates.mean()) / pooled_std_rate if pooled_std_rate > 0 else 0
        
        # 计算95%置信区间（使用t分布）
        n = len(canal_rebellions)
        se_count = pooled_std_count * np.sqrt(2/n)
        se_rate = pooled_std_rate * np.sqrt(2/n)
        ci_95 = stats.t.ppf(0.975, 2*n - 2)  # 95% 置信区间的t值
        
        mean_diff_count = canal_rebellions.mean() - non_canal_rebellions.mean()
        mean_diff_rate = canal_rates.mean() - non_canal_rates.mean()
        
        ci_lower_count = mean_diff_count - ci_95 * se_count
        ci_upper_count = mean_diff_count + ci_95 * se_count
        ci_lower_rate = mean_diff_rate - ci_95 * se_rate
        ci_upper_rate = mean_diff_rate + ci_95 * se_rate
        
        # 计算描述性统计
        results = {
            # 叛乱次数统计
            '沿河城镇平均叛乱次数': canal_rebellions.mean(),
            '沿河城镇叛乱次数标准差': canal_rebellions.std(),
            '非沿河城镇平均叛乱次数': non_canal_rebellions.mean(),
            '非沿河城镇叛乱次数标准差': non_canal_rebellions.std(),
            '叛乱次数T统计量': t_stat_count,
            '叛乱次数P值': p_value_count,
            '叛乱次数是否显著(p<0.05)': p_value_count < 0.05,
            '叛乱次数Cohens_d': cohens_d_count,
            '叛乱次数差异95%置信区间下限': ci_lower_count,
            '叛乱次数差异95%置信区间上限': ci_upper_count,
            
            # 叛乱率统计
            '沿河城镇平均叛乱率': canal_rates.mean(),
            '沿河城镇叛乱率标准差': canal_rates.std(),
            '非沿河城镇平均叛乱率': non_canal_rates.mean(),
            '非沿河城镇叛乱率标准差': non_canal_rates.std(),
            '叛乱率T统计量': t_stat_rate,
            '叛乱率P值': p_value_rate,
            '叛乱率是否显著(p<0.05)': p_value_rate < 0.05,
            '叛乱率Cohens_d': cohens_d_rate,
            '叛乱率差异95%置信区间下限': ci_lower_rate,
            '叛乱率差异95%置信区间上限': ci_upper_rate,
            
            # 城镇数量信息
            '沿河城镇数量': self.num_canal_towns,
            '非沿河城镇数量': self.num_non_canal_towns
        }
        
        return results
    
    def analyze_gap_trend(self, df: pd.DataFrame) -> Dict:
        """
        分析沿河和非沿河地区叛乱率差距的变化趋势
        
        Args:
            df: 年度统计DataFrame
            
        Returns:
            趋势分析结果
        """
        # 使用叛乱率差距进行分析（更科学）
        mid_point = len(df) // 2
        first_half_gap_rate = df['差距(率)'].iloc[:mid_point].mean()
        second_half_gap_rate = df['差距(率)'].iloc[mid_point:].mean()
        
        # 对叛乱率差距进行线性回归
        years = df['年份'].values - self.start_year  # 转换为相对年份
        gaps_rate = df['差距(率)'].values
        slope_rate, intercept_rate, r_value_rate, p_value_rate, std_err_rate = stats.linregress(years, gaps_rate)
        
        # 也计算叛乱次数差距的趋势（作为参考）
        gaps_count = df['差距(次数)'].values
        slope_count, intercept_count, r_value_count, p_value_count, std_err_count = stats.linregress(years, gaps_count)
        
        trend_result = {
            # 叛乱率差距趋势
            '前半段平均叛乱率差距': first_half_gap_rate,
            '后半段平均叛乱率差距': second_half_gap_rate,
            '叛乱率差距变化': second_half_gap_rate - first_half_gap_rate,
            '叛乱率差距趋势': '扩大' if second_half_gap_rate > first_half_gap_rate else '缩小',
            '叛乱率差距回归斜率': slope_rate,
            '叛乱率差距回归截距': intercept_rate,
            '叛乱率差距R方值': r_value_rate ** 2,
            '叛乱率差距趋势P值': p_value_rate,
            '叛乱率差距趋势是否显著(p<0.05)': p_value_rate < 0.05,
            
            # 叛乱次数差距趋势（参考）
            '叛乱次数差距回归斜率': slope_count,
            '叛乱次数差距R方值': r_value_count ** 2,
            '叛乱次数差距趋势P值': p_value_count,
            '叛乱次数差距趋势是否显著(p<0.05)': p_value_count < 0.05
        }
        
        return trend_result

    @staticmethod
    def _compute_gini(array: List[float]) -> float:
        """
        计算Gini系数用于表示地理或数值分布的不平等性
        """
        arr = np.array(array, dtype=float)
        if arr.size == 0:
            return 0.0
        # 如果所有值都为0，则Gini为0
        if np.all(arr == 0):
            return 0.0
        # 基本Gini计算
        sorted_arr = np.sort(arr)
        n = arr.size
        cumvals = np.cumsum(sorted_arr)
        gini = (2.0 * np.sum((np.arange(1, n+1) * sorted_arr))) / (n * cumvals[-1]) - (n + 1) / n
        return float(gini)

    def compute_additional_metrics(self) -> Dict:
        """
        计算用于跨实验比较的额外直观指标，基于所有解析到的模拟记录（self.all_rebellion_records）。

        返回示例字段：
            - 平均峰值强度（Mean Peak Intensity）
            - 平均到峰时间（Mean Time To Peak）
            - 城镇累积叛乱负担的Gini系数（Gini）
            - 城镇平均持续年数（Persistence）
            - 平均发生过叛乱的城镇比例（Prop Ever Rebel）
            - 叛乱率差距的AUC（AUC Gap）与波动（Volatility）
            - 沿河与非沿河城镇的首发年平均差（First Rebel Year Difference）
        """
        # 使用最小年份数进行对齐
        min_years = min(len(records) for records in self.all_rebellion_records)

        towns = set().union(self.canal_towns, self.non_canal_towns)
        if not towns:
            return {}

        per_run_town_cumulative = []  # 每次模拟中每个城镇的累积叛乱次数
        per_run_first_year = []  # 每次模拟中每个城镇的首发年（或np.nan）
        peak_intensities = []
        time_to_peaks = []
        prop_ever_rebel = []

        for records in self.all_rebellion_records:
            town_cum = {t: 0 for t in towns}
            town_first = {t: np.nan for t in towns}

            yearly_totals = []
            for year_idx in range(min_years):
                record = records[year_idx]
                target_towns = record['decision'].get('target_towns', [])
                total_rebel_towns = 0
                for town in target_towns:
                    name = town.get('town_name', '')
                    stage = town.get('stage_rebellion', 0)
                    if stage > 0 and name in towns:
                        town_cum[name] += 1
                        total_rebel_towns += 1
                        if np.isnan(town_first[name]):
                            town_first[name] = record['year']
                yearly_totals.append(total_rebel_towns)

            per_run_town_cumulative.append(town_cum)
            per_run_first_year.append(town_first)

            # 峰值强度与到峰时间
            yearly_totals = np.array(yearly_totals)
            peak_idx = int(np.argmax(yearly_totals))
            peak_intensities.append(float(yearly_totals.max()))
            time_to_peaks.append(float(peak_idx))

            # 发生过叛乱的城镇比例
            ever_rebel_count = sum(1 for v in town_cum.values() if v > 0)
            prop_ever_rebel.append(ever_rebel_count / len(towns))

        # 计算城镇层面的统计（基于每次模拟的累积值）
        # 将每次模拟的字典转换为每个城镇的列表
        town_names = sorted(list(towns))
        town_values_matrix = {t: [] for t in town_names}
        for run_dict in per_run_town_cumulative:
            for t in town_names:
                town_values_matrix[t].append(run_dict.get(t, 0))

        # 计算每个城镇的平均累积值
        town_mean_cum = np.array([np.mean(town_values_matrix[t]) for t in town_names])

        gini = float(self._compute_gini(town_mean_cum))
        mean_peak_intensity = float(np.mean(peak_intensities))
        mean_time_to_peak = float(np.mean(time_to_peaks))
        mean_prop_ever = float(np.mean(prop_ever_rebel))

        # Persistence: 每个城镇在一轮中被统计为叛乱的平均年数（先求每run的城镇均值，再平均）
        per_run_persistence = []
        for run_dict in per_run_town_cumulative:
            per_run_persistence.append(np.mean(list(run_dict.values())))
        persistence_mean = float(np.mean(per_run_persistence))

        # 首发年差异（沿河 vs 非沿河）——按run先计算均值，再跨run平均
        per_run_first_diff = []
        for run_first in per_run_first_year:
            canal_firsts = [v for k, v in run_first.items() if (k in self.canal_towns) and (not np.isnan(v))]
            non_canal_firsts = [v for k, v in run_first.items() if (k in self.non_canal_towns) and (not np.isnan(v))]
            if canal_firsts and non_canal_firsts:
                per_run_first_diff.append(np.mean(canal_firsts) - np.mean(non_canal_firsts))
        first_year_diff_mean = float(np.mean(per_run_first_diff)) if per_run_first_diff else float('nan')

        # 使用已有DF计算gap的AUC与波动
        try:
            df = self.analyze_yearly_rebellions()
            auc_gap = float(np.trapz(df['差距(率)'].values))
            gap_volatility = float(np.std(df['差距(率)'].values, ddof=1)) if len(df) > 1 else 0.0
        except Exception:
            auc_gap = float('nan')
            gap_volatility = float('nan')

        metrics = {
            '平均峰值强度': mean_peak_intensity,
            '平均到峰时间(相对开始年)': mean_time_to_peak,
            '城镇累积叛乱Gini': gini,
            '城镇平均持续年数(Persistence)': persistence_mean,
            '平均发生过叛乱的城镇比例': mean_prop_ever,
            '首发年(沿河 - 非沿河)平均差': first_year_diff_mean,
            '叛乱率差距AUC': auc_gap,
            '叛乱率差距波动(Std)': gap_volatility
        }

        return metrics

    def save_additional_metrics(self, metrics: Dict, output_path: str = None):
        """
        将额外的指标保存为JSON文件
        """
        if output_path is None:
            output_path = self.log_paths[0].parent / 'rebellion_additional_metrics.json'

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

        print(f"额外指标已保存至: {output_path}")
    
    def save_summary_csv(self, df: pd.DataFrame, output_path: str = None):
        """
        保存统计结果为CSV文件
        
        Args:
            df: 年度统计DataFrame
            output_path: 输出文件路径
        """
        if output_path is None:
            output_path = self.log_paths[0].parent / 'rebellion_analysis_summary.csv'
        
        # 确保输出目录存在
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n统计结果已保存至: {output_path}")
    
    def save_statistical_report(self, stats_results: Dict, trend_results: Dict, 
                                output_path: str = None):
        """
        保存统计检验报告
        
        Args:
            stats_results: 统计检验结果
            trend_results: 趋势分析结果
            output_path: 输出文件路径
        """
        if output_path is None:
            output_path = self.log_paths[0].parent / 'statistical_report.txt'
        
        # 确保输出目录存在
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("叛军数据统计分析报告\n")
            f.write("=" * 60 + "\n\n")
            
            f.write("一、城镇基本信息\n")
            f.write("-" * 60 + "\n")
            f.write(f"沿河城镇数量: {stats_results['沿河城镇数量']}\n")
            f.write(f"非沿河城镇数量: {stats_results['非沿河城镇数量']}\n\n")
            
            f.write("二、叛乱次数统计\n")
            f.write("-" * 60 + "\n")
            f.write(f"沿河城镇平均叛乱次数: {stats_results['沿河城镇平均叛乱次数']:.2f} ± {stats_results['沿河城镇叛乱次数标准差']:.2f}\n")
            f.write(f"非沿河城镇平均叛乱次数: {stats_results['非沿河城镇平均叛乱次数']:.2f} ± {stats_results['非沿河城镇叛乱次数标准差']:.2f}\n")
            f.write(f"T统计量: {stats_results['叛乱次数T统计量']:.4f}\n")
            p_count = stats_results['叛乱次数P值']
            if p_count < 0.0001:
                p_count_str = '<0.0001'
            else:
                p_count_str = f"{p_count:.4f}"
            f.write(f"P值: {p_count_str}\n")
            f.write(f"显著性(α=0.05): {'显著' if stats_results['叛乱次数是否显著(p<0.05)'] else '不显著'}\n")
            f.write(f"Cohens_d (效应量): {stats_results['叛乱次数Cohens_d']:.4f}\n")
            f.write(f"差异95%置信区间: [{stats_results['叛乱次数差异95%置信区间下限']:.2f}, {stats_results['叛乱次数差异95%置信区间上限']:.2f}]\n\n")
            
            f.write("三、叛乱率统计（关键指标）\n")
            f.write("-" * 60 + "\n")
            f.write(f"沿河城镇平均叛乱率: {stats_results['沿河城镇平均叛乱率']:.4f} ± {stats_results['沿河城镇叛乱率标准差']:.4f}\n")
            f.write(f"非沿河城镇平均叛乱率: {stats_results['非沿河城镇平均叛乱率']:.4f} ± {stats_results['非沿河城镇叛乱率标准差']:.4f}\n")
            f.write(f"T统计量: {stats_results['叛乱率T统计量']:.4f}\n")
            p_rate = stats_results['叛乱率P值']
            if p_rate < 0.0001:
                p_rate_str = '<0.0001'
            else:
                p_rate_str = f"{p_rate:.4f}"
            f.write(f"P值: {p_rate_str}\n")
            f.write(f"显著性(α=0.05): {'显著' if stats_results['叛乱率是否显著(p<0.05)'] else '不显著'}\n")
            f.write(f"Cohens_d (效应量): {stats_results['叛乱率Cohens_d']:.4f}\n")
            f.write(f"差异95%置信区间: [{stats_results['叛乱率差异95%置信区间下限']:.4f}, {stats_results['叛乱率差异95%置信区间上限']:.4f}]\n\n")
            
            # 效应量解释
            cohens_d = stats_results['叛乱率Cohens_d']
            if abs(cohens_d) < 0.2:
                effect_interpretation = "微小"
            elif abs(cohens_d) < 0.5:
                effect_interpretation = "小"
            elif abs(cohens_d) < 0.8:
                effect_interpretation = "中等"
            else:
                effect_interpretation = "大"
            f.write(f"效应量解释: {effect_interpretation}效应\n\n")
            
            f.write("四、叛乱率差距趋势分析（核心指标）\n")
            f.write("-" * 60 + "\n")
            f.write(f"前半段平均叛乱率差距: {trend_results['前半段平均叛乱率差距']:.4f}\n")
            f.write(f"后半段平均叛乱率差距: {trend_results['后半段平均叛乱率差距']:.4f}\n")
            f.write(f"叛乱率差距变化: {trend_results['叛乱率差距变化']:.4f} ({trend_results['叛乱率差距趋势']})\n")
            f.write(f"叛乱率差距回归斜率: {trend_results['叛乱率差距回归斜率']:.6f}\n")
            f.write(f"叛乱率差距回归截距: {trend_results['叛乱率差距回归截距']:.6f}\n")
            f.write(f"叛乱率差距R方值: {trend_results['叛乱率差距R方值']:.4f}\n")
            f.write(f"叛乱率差距趋势P值: {trend_results['叛乱率差距趋势P值']:.4f}\n")
            f.write(f"叛乱率差距趋势是否显著(p<0.05): {'显著' if trend_results['叛乱率差距趋势是否显著(p<0.05)'] else '不显著'}\n\n")
            
            f.write("五、叛乱次数差距趋势分析（参考指标）\n")
            f.write("-" * 60 + "\n")
            f.write(f"叛乱次数差距回归斜率: {trend_results['叛乱次数差距回归斜率']:.6f}\n")
            f.write(f"叛乱次数差距R方值: {trend_results['叛乱次数差距R方值']:.4f}\n")
            f.write(f"叛乱次数差距趋势P值: {trend_results['叛乱次数差距趋势P值']:.4f}\n")
            f.write(f"叛乱次数差距趋势是否显著(p<0.05): {'显著' if trend_results['叛乱次数差距趋势是否显著(p<0.05)'] else '不显著'}\n\n")
            
            f.write("六、结论总结\n")
            f.write("-" * 60 + "\n")
            if stats_results['叛乱率是否显著(p<0.05)']:
                if stats_results['沿河城镇平均叛乱率'] > stats_results['非沿河城镇平均叛乱率']:
                    f.write(f"✓ 沿河城镇的叛乱率显著高于非沿河城镇 (p={stats_results['叛乱率P值']:.4f})\n")
                    f.write(f"✓ 效应量为{effect_interpretation}效应 (Cohens_d={cohens_d:.4f})\n")
                    f.write(f"✓ 沿河地区受到的影响更大，更容易发生叛乱\n")
                else:
                    f.write(f"✗ 数据显示非沿河城镇叛乱率更高，与预期不符\n")
            else:
                f.write(f"✗ 沿河与非沿河城镇的叛乱率差异不显著 (p={stats_results['叛乱率P值']:.4f})\n")
                f.write(f"  需要更多数据或检查模型设置\n")
        
        print(f"统计报告已保存至: {output_path}")
    
    def plot_visualizations(self, df: pd.DataFrame, output_dir: str = None):
        """
        生成可视化图表
        
        Args:
            df: 年度统计DataFrame
            output_dir: 输出目录
        """
        if output_dir is None:
            output_dir = self.log_paths[0].parent
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置绘图风格
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        
        # 1. Time Series Line Chart
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(df['年份'], df['沿河城镇叛乱次数'], marker='o', label='Canal Towns', linewidth=2)
        ax.plot(df['年份'], df['非沿河城镇叛乱次数'], marker='s', label='Non-Canal Towns', linewidth=2)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Number of Rebellions', fontsize=12)
        ax.set_title('Rebellion Frequency Comparison: Canal vs Non-Canal Towns', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / 'rebellion_time_series.png', dpi=300, bbox_inches='tight')
        print(f"Time series chart saved to: {output_dir / 'rebellion_time_series.png'}")
        plt.close()
        
        # 2. Rebellion Rate Gap Trend Chart
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(df['年份'], df['差距(率)'], marker='o', color='red', linewidth=2, label='Rate Gap')
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        # Add trend line
        z = np.polyfit(df['年份'], df['差距(率)'], 1)
        p = np.poly1d(z)
        ax.plot(df['年份'], p(df['年份']), "b--", alpha=0.8, label=f'Trend Line (slope={z[0]:.6f})')
        
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Rebellion Rate Gap (Canal - Non-Canal)', fontsize=12)
        ax.set_title('Trend of Rebellion Rate Gap Between Canal and Non-Canal Towns', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / 'rebellion_rate_gap_trend.png', dpi=300, bbox_inches='tight')
        print(f"Rebellion rate gap trend chart saved to: {output_dir / 'rebellion_rate_gap_trend.png'}")
        plt.close()
        
        # 3. Boxplot Comparison
        fig, ax = plt.subplots(figsize=(10, 6))
        data_to_plot = [df['沿河城镇叛乱次数'], df['非沿河城镇叛乱次数']]
        bp = ax.boxplot(data_to_plot, tick_labels=['Canal Towns', 'Non-Canal Towns'], patch_artist=True)
        
        # Set boxplot colors
        colors = ['lightblue', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
        
        ax.set_ylabel('Number of Rebellions', fontsize=12)
        ax.set_title('Distribution Comparison of Rebellions: Canal vs Non-Canal Towns', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(output_dir / 'rebellion_boxplot.png', dpi=300, bbox_inches='tight')
        print(f"Boxplot saved to: {output_dir / 'rebellion_boxplot.png'}")
        plt.close()
        
        # 4. Stacked Bar Chart
        fig, ax = plt.subplots(figsize=(14, 6))
        x = df['年份']
        width = 0.8
        
        ax.bar(x, df['沿河城镇叛乱次数'], width, label='Canal Towns', color='steelblue')
        ax.bar(x, df['非沿河城镇叛乱次数'], width, bottom=df['沿河城镇叛乱次数'], 
               label='Non-Canal Towns', color='coral')
        
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Number of Rebellions', fontsize=12)
        ax.set_title('Stacked Distribution of Rebellions: Canal vs Non-Canal Towns', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_dir / 'rebellion_stacked_bar.png', dpi=300, bbox_inches='tight')
        print(f"Stacked bar chart saved to: {output_dir / 'rebellion_stacked_bar.png'}")
        plt.close()
        
        print(f"\n所有图表已单独保存完成！")
    
    def run_analysis(self, output_dir: str = None):
        """
        运行完整的分析流程
        
        Args:
            output_dir: 输出目录，默认为log文件所在目录
        """
        print("\n开始叛军数据分析...")
        
        # 分析年度叛乱数据
        df = self.analyze_yearly_rebellions()
        
        # 统计检验
        stats_results = self.statistical_test(df)
        
        # 趋势分析
        trend_results = self.analyze_gap_trend(df)

        # 额外跨实验比较指标（无论是否指定输出目录都计算）
        additional_metrics = self.compute_additional_metrics()

        # 保存结果
        if output_dir is None:
            output_dir = self.log_paths[0].parent
        
        self.save_summary_csv(df, str(Path(output_dir) / 'rebellion_analysis_summary.csv'))
        self.save_statistical_report(stats_results, trend_results, 
                                     str(Path(output_dir) / 'statistical_report.txt'))
        
        # 生成可视化
        # 保存额外指标
        self.save_additional_metrics(additional_metrics, str(Path(output_dir) / 'rebellion_additional_metrics.json'))
        self.plot_visualizations(df, output_dir)
        
        print("分析完成！所有结果已保存到:", output_dir)
        
        return df, stats_results, trend_results


def main():
    """
    主函数示例
    """
    # 方式1: 使用单个log文件
    # log_path = "history/default/20251224_100114_p200_y10_pid12948/rebels_20251224_100130_pid12948.log"
    
    # 方式2: 使用多个log文件列表
    # log_path = [
    #     "history/default/run1/rebels_xxx.log",
    #     "history/default/run2/rebels_xxx.log",
    #     "history/default/run3/rebels_xxx.log"
    # ]
    
    # 方式3: 使用目录（递归查找该目录及所有子目录中的rebels_*.log文件）
    log_path = "history/rebels_analyzer"
    
    towns_data_path = "config/default/towns_data.json"
    output_dir = "history/rebels_analyzer/rebellion_analysis_output"
    
    # 创建分析器
    analyzer = RebellionAnalyzer(
        log_path=log_path,
        towns_data_path=towns_data_path,
        start_year=1650
    )
    
    # 运行分析
    df, stats_results, trend_results = analyzer.run_analysis(output_dir=output_dir)


if __name__ == "__main__":
    main()
