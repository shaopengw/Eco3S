import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
import matplotlib
import os

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 优先使用中文字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题


# ==================== 数据定义 ====================
experiments = ['默认模拟', '群体投票机制', 
               '无极端天气', '高效维护群体']

metrics = ['平均峰值强度', '平均到达峰值时间', '累计负担基尼系数',
           '平均持续年数', '曾经叛乱比例',
           '速率差距AUC', '差距波动性']

# 所有实验的原始数据
data_raw = {
    '默认模拟': [25.0, 6.0, 0.2944, 6.156, 0.9778, 4.74, 0.1139],
    '群体投票机制': [25.2, 5.2, 0.2370, 6.089, 1.0000, 3.577, 0.1270],
    '无极端天气': [22.4, 5.8, 0.2704, 5.348, 0.9407, 3.903, 0.1417],
    '高效维护群体': [22.0, 9.2, 0.2994, 5.489, 0.9704, 4.223, 0.1018]
}

# ==================== 辅助函数 ====================
def normalize_for_comparison(values_dict, metric_names):
    """
    为雷达图标准化数据（0-1范围）
    """
    normalized = {}
    experiments_list = list(values_dict.keys())
    
    for exp in experiments_list:
        normalized[exp] = values_dict[exp].copy()
    
    # 分别处理每个指标
    for i in range(len(metric_names)):
        all_values = [values_dict[exp][i] for exp in experiments_list]
        max_val = max(all_values)
        min_val = min(all_values)
        
        # 这些指标越低越好
        if metric_names[i] in ['平均峰值强度', '累计负担基尼系数', 
                               '差距波动性', '平均持续年数',
                               '曾经叛乱比例']:
            for exp in experiments_list:
                normalized[exp][i] = 1 - (values_dict[exp][i] - min_val) / (max_val - min_val + 1e-8)
        else:  # 越高越好
            for exp in experiments_list:
                normalized[exp][i] = (values_dict[exp][i] - min_val) / (max_val - min_val + 1e-8)
    
    return normalized

def calculate_relative_change(base_exp='默认模拟'):
    """
    计算相对于基准实验的百分比变化
    """
    change_matrix = []
    for exp in experiments:
        changes = []
        for i, metric in enumerate(metrics):
            base_val = data_raw[base_exp][i]
            exp_val = data_raw[exp][i]
            
            # 确定方向
            if metric in ['平均峰值强度', '累计负担基尼系数', 
                         '平均持续年数', '曾经叛乱比例', 
                         '差距波动性']:
                change = ((base_val - exp_val) / base_val) * 100
            else:
                change = ((exp_val - base_val) / base_val) * 100
            changes.append(change)
        change_matrix.append(changes)
    
    return np.array(change_matrix)

# ==================== 图1：雷达图 ====================
def plot_radar_chart():
    fig = plt.figure(figsize=(14, 10))
    
    # 为雷达图标准化数据
    data_normalized = normalize_for_comparison(data_raw, metrics)
    
    # 极坐标设置
    angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]  # 闭合形状
    
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi/2)
    ax.set_theta_direction(-1)
    
    # 设置角度标签
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=11)
    
    # 设置径向标签
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=9)
    ax.set_ylabel('标准化分数', fontsize=11, labelpad=20)
    
    # 绘制每个实验
    colors = ['#FF6B6B', '#4ECDC4', '#96CEB4', '#FFD166']
    line_styles = ['-', '-.', ':', '-']
    
    for idx, exp in enumerate(experiments):
        values = data_normalized[exp].copy()
        values += values[:1]
        ax.plot(angles, values, linewidth=2.5, linestyle=line_styles[idx],
                color=colors[idx], label=exp, marker='o', markersize=5)
        ax.fill(angles, values, alpha=0.1, color=colors[idx])
    
    # 图例
    plt.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), 
               fontsize=10, frameon=True, fancybox=True)
    
    plt.title('雷达图：各实验的叛乱活动指标\n（绿色区域表示更好性能）', 
              fontsize=16, fontweight='bold', pad=40)
    plt.tight_layout()
    plt.show()

# ==================== 图2：条形图比较 ====================
def plot_bar_charts():
    fig, axes = plt.subplots(2, 4, figsize=(16, 10))
    axes = axes.flatten()
    
    key_metrics = [
        ('平均峰值强度', '叛乱城镇数量', '越低越好'),
        ('平均到达峰值时间', '年数', '越高越好（延迟爆发）'),
        ('累计负担基尼系数', '系数', '越低越好（分布更均匀）'),
        ('平均持续年数', '年数', '越低越好'),
        ('曾经叛乱比例', '比率', '越低越好'),
        ('速率差距AUC', '累计差异', '越低越好（运河优势更小）'),
        ('差距波动性', '标准差', '越低越好（更稳定）'),
        ('基尼系数比较', '系数', '重点：决策机制')
    ]
    
    x_pos = np.arange(len(experiments))
    bar_width = 0.7
    
    for idx, (metric_name, unit, note) in enumerate(key_metrics):
        ax = axes[idx]
        
        if idx < 7:  # 前7个指标来自完整列表
            metric_idx = metrics.index(metric_name)
            values = [data_raw[exp][metric_idx] for exp in experiments]
        else:  # 特殊的基尼系数比较
            values = [data_raw[exp][2] for exp in experiments]
            metric_name = '累计负担基尼系数'
        
        # 确定最优方向
        if '越低越好' in note:
            colors = ['lightgreen' if v == min(values) else 'lightcoral' for v in values]
        else:
            colors = ['lightgreen' if v == max(values) else 'lightcoral' for v in values]
        
        bars = ax.bar(x_pos, values, width=bar_width, color=colors, 
                     edgecolor='black', alpha=0.8)
        
        # 添加数值标签
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, height + 0.02*max(values),
                   f'{value:.3f}', ha='center', va='bottom', fontsize=9)
        
        # X轴标签（旋转以提高可读性）
        ax.set_xticks(x_pos)
        if idx >= 6:  # 底行
            ax.set_xticklabels(experiments, rotation=25, ha='right', fontsize=9)
        else:
            ax.set_xticklabels(experiments, rotation=15, fontsize=9)
        
        ax.set_ylabel(f'{unit}', fontsize=10)
        ax.set_title(f'{metric_name}\n{note}', fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
    
    plt.suptitle('关键叛乱指标：跨实验比较', 
                fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.show()

# ==================== 图3：相对变化热力图 ====================
def plot_heatmap():
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # 计算百分比变化
    change_matrix = calculate_relative_change()
    
    # 创建热力图
    im = ax.imshow(change_matrix, cmap='RdYlGn', aspect='auto', 
                  vmin=-25, vmax=25)
    
    # 添加百分比文本
    for i in range(len(experiments)):
        for j in range(len(metrics)):
            text_color = "white" if abs(change_matrix[i, j]) > 15 else "black"
            ax.text(j, i, f'{change_matrix[i, j]:+.1f}%',
                   ha="center", va="center", color=text_color, fontsize=10,
                   fontweight='bold' if abs(change_matrix[i, j]) > 10 else 'normal')
    
    # 配置坐标轴
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels(metrics, rotation=45, ha='right', fontsize=11)
    ax.set_yticks(np.arange(len(experiments)))
    ax.set_yticklabels(experiments, fontsize=11)
    
    # 在行之间添加网格线
    for i in range(1, len(experiments)):
        ax.axhline(i - 0.5, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
    
    # 高亮群体投票行
    voting_idx = experiments.index('群体投票机制')
    ax.add_patch(Rectangle((-0.5, voting_idx-0.5), len(metrics), 1,
                          fill=False, edgecolor='blue', linewidth=2.5,
                          linestyle='--', alpha=0.8))
    
    # 颜色条
    cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.set_ylabel('相对于默认模拟的百分比变化\n（绿色=改进，红色=恶化）', 
                      rotation=-90, va="bottom", fontsize=11)
    
    plt.title('热力图：跨实验的相对性能变化\n（高亮：群体投票机制）', 
             fontsize=15, fontweight='bold', pad=25)
    plt.tight_layout()
    plt.show()

# ==================== 图4：决策机制重点分析 ====================
def plot_decision_mechanisms():
    # 重点分析两种决策机制
    decision_experiments = ['默认模拟', '群体投票机制']
    
    fig = plt.figure(figsize=(15, 10))
    
    # 决策机制数据
    decision_data = {exp: data_raw[exp] for exp in decision_experiments}
    
    # 1. 关键指标并列比较
    ax1 = plt.subplot(2, 3, 1)
    
    comparison_metrics = ['平均峰值强度', '平均到达峰值时间', 
                         '累计负担基尼系数', '速率差距AUC']
    metric_indices = [0, 1, 2, 5]
    
    x = np.arange(len(comparison_metrics))
    width = 0.25
    
    colors_decision = ['#FF6B6B', '#45B7D1']
    
    for i, exp in enumerate(decision_experiments):
        values = [decision_data[exp][idx] for idx in metric_indices]
        offset = width * (i - 0.5)
        ax1.bar(x + offset, values, width, label=exp, color=colors_decision[i],
               alpha=0.8, edgecolor='black')
    
    ax1.set_xticks(x)
    ax1.set_xticklabels(['峰值\n强度', '到达峰值\n时间', '基尼\n系数', 
                        'AUC\n差距'], fontsize=10)
    ax1.set_ylabel('指标值')
    ax1.legend(fontsize=9)
    ax1.set_title('关键指标：决策机制比较', fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 2. 基尼系数比较（饼图）
    ax2 = plt.subplot(2, 3, 2)
    gini_values = [decision_data[exp][2] for exp in decision_experiments]
    labels_short = ['默认\n（专制）', '群体\n投票']
    colors_pie = ['#FF9999', '#9999FF']
    
    wedges, texts, autotexts = ax2.pie(gini_values, labels=labels_short, 
                                       colors=colors_pie, autopct='%1.1f%%',
                                       startangle=90, textprops={'fontsize': 9})
    
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontweight('bold')
    
    ax2.set_title('叛乱负担分布（基尼系数）\n越低=分布越均匀', 
                 fontweight='bold')
    
    # 3. 叛乱传播比较
    ax3 = plt.subplot(2, 3, 3)
    spread_values = [decision_data[exp][4] * 100 for exp in decision_experiments]
    
    bars = ax3.bar(labels_short, spread_values, color=colors_decision, 
                  edgecolor='black', alpha=0.8)
    ax3.set_ylim(95, 101)
    ax3.set_ylabel('城镇百分比 (%)')
    ax3.set_title('叛乱地理传播\n（越高=传播越广）', 
                 fontweight='bold')
    
    for bar, value in zip(bars, spread_values):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, height + 0.2,
                f'{value:.1f}%', ha='center', va='bottom', fontsize=10)
    
    # 4. 时间动态指标
    ax4 = plt.subplot(2, 3, 4)
    time_metrics = ['到达峰值时间', '差距波动性', '持久性']
    time_indices = [1, 6, 3]
    time_data = [[decision_data[exp][idx] for exp in decision_experiments] 
                for idx in time_indices]
    
    x_time = np.arange(len(decision_experiments))
    for i, (metric_name, values) in enumerate(zip(time_metrics, time_data)):
        ax4.plot(x_time, values, marker='o', linewidth=2.5, markersize=8,
                label=metric_name)
    
    ax4.set_xticks(x_time)
    ax4.set_xticklabels(labels_short, fontsize=10)
    ax4.set_ylabel('数值')
    ax4.legend(fontsize=9)
    ax4.set_title('决策机制的时间动态', fontweight='bold')
    ax4.grid(True, alpha=0.3)
    
    # 5. 决策机制的雷达图
    ax5 = plt.subplot(2, 3, 5, polar=True)
    
    # 选择雷达图的关键指标
    radar_metrics = ['平均峰值强度', '累计负担基尼系数', 
                    '速率差距AUC', '平均到达峰值时间', '差距波动性']
    radar_indices = [0, 2, 5, 1, 6]
    
    angles_radar = np.linspace(0, 2*np.pi, len(radar_metrics), endpoint=False)
    angles_radar = np.concatenate((angles_radar, [angles_radar[0]]))
    
    # 为雷达图标准化
    def normalize_values(values, lower_better=True, all_values_list=None):
        if all_values_list is None:
            all_values_list = [values]
        min_val = min([min(vals) for vals in all_values_list])
        max_val = max([max(vals) for vals in all_values_list])
        
        if lower_better:
            return [1 - (v - min_val)/(max_val - min_val + 1e-8) for v in values]
        else:
            return [(v - min_val)/(max_val - min_val + 1e-8) for v in values]
    
    # 收集所有值用于标准化
    all_values_per_metric = []
    for idx in radar_indices:
        metric_values = [decision_data[exp][idx] for exp in decision_experiments]
        all_values_per_metric.append(metric_values)
    
    # 绘制每种机制
    for i, exp in enumerate(decision_experiments):
        values = []
        for j, idx in enumerate(radar_indices):
            # 确定是否越低越好
            metric_name = metrics[idx]
            lower_better = metric_name in ['平均峰值强度', '累计负担基尼系数', 
                                         '差距波动性', '平均持续年数']
            
            current_value = decision_data[exp][idx]
            norm_value = normalize_values([current_value], lower_better, 
                                         [all_values_per_metric[j]])[0]
            values.append(norm_value)
        
        values = values + [values[0]]
        ax5.plot(angles_radar, values, 'o-', linewidth=2, label=exp,
                color=colors_decision[i], markersize=6)
        ax5.fill(angles_radar, values, alpha=0.1, color=colors_decision[i])
    
    ax5.set_xticks(angles_radar[:-1])
    ax5.set_xticklabels(['峰值\n强度', '基尼\n系数', 'AUC\n差距',
                        '到达峰值\n时间', '差距\n波动性'], fontsize=9)
    ax5.set_ylim(0, 1)
    ax5.set_title('雷达图：决策机制性能\n（越靠近外边缘越好）', 
                 fontweight='bold', pad=20)
    ax5.legend(loc='upper right', bbox_to_anchor=(1.4, 1.1), fontsize=9)
    
    # 6. 摘要表格
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('tight')
    ax6.axis('off')
    
    summary_data = [
        ['指标', '默认', '群体投票', '最佳'],
        ['基尼系数', '0.294', '0.237', '群体投票'],
        ['叛乱传播', '97.8%', '100%', '默认'],
        ['AUC差距', '4.74', '3.58', '群体投票'],
        ['到达峰值时间', '6.0 年', '5.2 年', '默认'],
        ['峰值强度', '25.0', '25.2', '默认']
    ]
    
    table = ax6.table(cellText=summary_data, loc='center', 
                     cellLoc='center', colWidths=[0.25, 0.25, 0.25, 0.25])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)
    
    # 样式化表格
    for (i, j), cell in table.get_celld().items():
        if i == 0:  # 标题行
            cell.set_text_props(fontweight='bold')
            cell.set_facecolor('#E8E8E8')
        if j == 3 and i > 0:  # "最佳"列
            if cell.get_text().get_text() == '群体投票':
                cell.set_facecolor('#90EE90')  # 浅绿色
            elif cell.get_text().get_text() == '默认':
                cell.set_facecolor('#ADD8E6')  # 浅蓝色
    
    ax6.set_title('性能摘要：决策机制', fontweight='bold', pad=20)
    
    plt.suptitle('决策机制分析：从专制到群体投票', 
                fontsize=16, fontweight='bold', y=1.05)
    plt.tight_layout()
    plt.show()

# ==================== 图5：综合散点矩阵 ====================
def plot_scatter_matrix():
    # 选择4个关键指标进行两两比较
    selected_metrics = ['平均峰值强度', '累计负担基尼系数',
                       '平均到达峰值时间', '速率差距AUC']
    selected_indices = [0, 2, 1, 5]
    
    fig, axes = plt.subplots(4, 4, figsize=(16, 16))
    
    # 为所有配对创建散点图
    for i in range(4):
        for j in range(4):
            ax = axes[i, j]
            
            if i == j:  # 对角线：直方图
                values = [data_raw[exp][selected_indices[i]] for exp in experiments]
                ax.hist(values, bins=8, alpha=0.7, color='skyblue', edgecolor='black')
                ax.set_title(f'分布：{selected_metrics[i]}', fontsize=10)
                ax.grid(True, alpha=0.3)
            else:  # 非对角线：散点图
                x_values = [data_raw[exp][selected_indices[j]] for exp in experiments]
                y_values = [data_raw[exp][selected_indices[i]] for exp in experiments]
                
                # 按实验着色
                colors_scatter = ['#FF6B6B', '#4ECDC4', '#96CEB4', '#FFD166']
                
                for k, exp in enumerate(experiments):
                    ax.scatter(x_values[k], y_values[k], color=colors_scatter[k],
                              s=100, alpha=0.8, edgecolor='black', linewidth=1,
                              label=exp if (i==0 and j==3) else "")
                
                # 添加实验标签
                for k, exp in enumerate(experiments):
                    ax.annotate(exp[:15], (x_values[k], y_values[k]),
                               xytext=(5, 5), textcoords='offset points',
                               fontsize=8, alpha=0.8)
                
                ax.grid(True, alpha=0.3)
            
            # 设置标签
            if i == 3:  # 底行
                ax.set_xlabel(selected_metrics[j], fontsize=10)
            if j == 0:  # 左列
                ax.set_ylabel(selected_metrics[i], fontsize=10)
    
    # 向一个子图添加图例
    axes[0, 3].legend(fontsize=9, loc='upper left', bbox_to_anchor=(1.05, 1))
    
    plt.suptitle('两两比较：关键叛乱活动指标', 
                fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.show()

# ==================== 图6：性能摘要仪表板 ====================
def plot_performance_dashboard():
    fig = plt.figure(figsize=(16, 12))
    
    # 1. 综合分数计算
    ax1 = plt.subplot(3, 3, 1)
    
    # 定义综合分数的权重（总和为1.0）
    weights = [0.15, 0.15, 0.20, 0.10, 0.10, 0.15, 0.15]
    
    def calculate_score(exp_data):
        normalized_scores = []
        for i in range(len(metrics)):
            all_values = [data_raw[exp][i] for exp in experiments]
            
            if metrics[i] in ['平均峰值强度', '累计负担基尼系数',
                             '平均持续年数', '曾经叛乱比例',
                             '差距波动性']:
                # 越低越好
                min_val = min(all_values)
                max_val = max(all_values)
                score = 1 - (exp_data[i] - min_val) / (max_val - min_val + 1e-8)
            else:
                # 越高越好
                min_val = min(all_values)
                max_val = max(all_values)
                score = (exp_data[i] - min_val) / (max_val - min_val + 1e-8)
            
            normalized_scores.append(score * weights[i])
        
        return sum(normalized_scores)
    
    # 计算分数
    scores = {exp: calculate_score(data_raw[exp]) for exp in experiments}
    sorted_exps = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    exp_names = [exp for exp, _ in sorted_exps]
    score_values = [score for _, score in sorted_exps]
    
    bars = ax1.barh(exp_names, score_values, color='steelblue', alpha=0.8)
    
    # 添加分数标签
    for bar, score in zip(bars, score_values):
        width = bar.get_width()
        ax1.text(width + 0.01, bar.get_y() + bar.get_height()/2,
                f'{score:.3f}', ha='left', va='center', fontsize=10)
    
    ax1.set_xlabel('综合分数（0-1范围）')
    ax1.set_title('总体性能排名', fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')
    
    # 2. 权衡分析：效率 vs 公平性
    ax2 = plt.subplot(3, 3, 2)
    
    # 效率指标：到达峰值时间（越高=延迟危机效率越高）
    # 公平性指标：基尼系数（越低=分布越公平）
    
    efficiency = [data_raw[exp][1] for exp in experiments]  # 到达峰值时间
    equity = [1 - data_raw[exp][2] for exp in experiments]  # 反转的基尼系数（越高=越公平）
    
    # 将两者标准化到0-1范围
    eff_normalized = [(e - min(efficiency)) / (max(efficiency) - min(efficiency)) 
                     for e in efficiency]
    eq_normalized = [(e - min(equity)) / (max(equity) - min(equity)) 
                    for e in equity]
    
    # 绘制权衡图
    scatter = ax2.scatter(eff_normalized, eq_normalized, s=200, 
                         c=range(len(experiments)), cmap='viridis', 
                         edgecolor='black', alpha=0.8)
    
    # 添加实验标签
    for i, exp in enumerate(experiments):
        ax2.annotate(exp, (eff_normalized[i], eq_normalized[i]),
                    xytext=(10, 5), textcoords='offset points',
                    fontsize=9, fontweight='bold')
    
    ax2.set_xlabel('效率（标准化的到达峰值时间）\n越高=延迟危机时间越长')
    ax2.set_ylabel('公平性（1 - 标准化基尼系数）\n越高=分布越均匀')
    ax2.set_title('权衡：效率 vs 公平性', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # 添加象限标签
    ax2.text(0.05, 0.95, '低效率\n高公平性', transform=ax2.transAxes,
            fontsize=9, ha='left', va='top', bbox=dict(boxstyle='round', alpha=0.2))
    ax2.text(0.95, 0.95, '高效率\n高公平性', transform=ax2.transAxes,
            fontsize=9, ha='right', va='top', bbox=dict(boxstyle='round', alpha=0.2))
    ax2.text(0.05, 0.05, '低效率\n低公平性', transform=ax2.transAxes,
            fontsize=9, ha='left', va='bottom', bbox=dict(boxstyle='round', alpha=0.2))
    ax2.text(0.95, 0.05, '高效率\n低公平性', transform=ax2.transAxes,
            fontsize=9, ha='right', va='bottom', bbox=dict(boxstyle='round', alpha=0.2))
    
    # 3. 改进矩阵
    ax3 = plt.subplot(3, 3, 3)
    
    # 计算相对于默认实验的改进
    improvements = []
    for exp in experiments:
        if exp == '默认模拟':
            improvements.append(0)
        else:
            # 计算该实验比默认实验更好的指标数量
            better_count = 0
            for i in range(len(metrics)):
                exp_val = data_raw[exp][i]
                default_val = data_raw['默认模拟'][i]
                
                # 检查是否更好（取决于指标方向）
                if metrics[i] in ['平均峰值强度', '累计负担基尼系数',
                                 '平均持续年数', '曾经叛乱比例',
                                 '差距波动性']:
                    if exp_val < default_val:
                        better_count += 1
                else:
                    if exp_val > default_val:
                        better_count += 1
            
            improvements.append(better_count / len(metrics) * 100)  # 百分比
    
    bars3 = ax3.bar(experiments, improvements, color='lightcoral', alpha=0.8)
    
    # 将群体投票着色为不同颜色
    voting_idx = experiments.index('群体投票机制')
    bars3[voting_idx].set_color('lightgreen')
    
    ax3.set_ylabel('改进指标百分比 (%)')
    ax3.set_title('相对于默认模拟的改进', fontweight='bold')
    ax3.set_xticklabels(experiments, rotation=45, ha='right', fontsize=9)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. 时间动态比较
    ax4 = plt.subplot(3, 3, 4)
    
    temporal_metrics = ['平均到达峰值时间', '平均持续年数', '差距波动性']
    temporal_indices = [1, 3, 6]
    
    x_temp = np.arange(len(temporal_metrics))
    width_temp = 0.15
    
    for i, exp in enumerate(experiments):
        values = [data_raw[exp][idx] for idx in temporal_indices]
        offset = width_temp * (i - 1.5)
        ax4.bar(x_temp + offset, values, width_temp, label=exp, alpha=0.8)
    
    ax4.set_xticks(x_temp)
    ax4.set_xticklabels(['到达峰值\n时间', '持续\n年数', '差距\n波动性'],
                       fontsize=9)
    ax4.set_ylabel('数值')
    ax4.set_title('时间动态比较', fontweight='bold')
    ax4.legend(fontsize=8, ncol=2)
    ax4.grid(True, alpha=0.3, axis='y')
    
    # 5. 空间分布指标
    ax5 = plt.subplot(3, 3, 5)
    
    spatial_metrics = ['累计负担基尼系数', '曾经叛乱比例',
                      '速率差距AUC']
    spatial_indices = [2, 4, 5]
    
    x_spatial = np.arange(len(spatial_metrics))
    
    # 分组条形图
    for i, exp in enumerate(experiments[:3]):  # 前3个实验以求清晰
        values = [data_raw[exp][idx] for idx in spatial_indices]
        ax5.bar(x_spatial + i*0.25, values, 0.25, label=exp, alpha=0.8)
    
    ax5.set_xticks(x_spatial + 0.25)
    ax5.set_xticklabels(['基尼\n系数', '叛乱\n比例', 'AUC\n差距'],
                       fontsize=9)
    ax5.set_ylabel('数值')
    ax5.set_title('空间分布指标', fontweight='bold')
    ax5.legend(fontsize=8)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. 决策机制有效性
    ax6 = plt.subplot(3, 3, 6)
    
    decision_groups = ['默认模拟', '群体投票机制']
    
    # 有效性分数：基尼系数（公平性）和到达峰值时间（效率）的组合
    effectiveness_scores = []
    for exp in decision_groups:
        # 标准化基尼系数（越低越好）和到达峰值时间（越高越好）
        gini_score = 1 - (data_raw[exp][2] - min([data_raw[d][2] for d in decision_groups])) / \
                    (max([data_raw[d][2] for d in decision_groups]) - 
                     min([data_raw[d][2] for d in decision_groups]) + 1e-8)
        time_score = (data_raw[exp][1] - min([data_raw[d][1] for d in decision_groups])) / \
                    (max([data_raw[d][1] for d in decision_groups]) - 
                     min([data_raw[d][1] for d in decision_groups]) + 1e-8)
        
        effectiveness = 0.6 * gini_score + 0.4 * time_score  # 加权组合
        effectiveness_scores.append(effectiveness)
    
    bars6 = ax6.bar(['默认\n（专制）', '群体\n投票'],
                   effectiveness_scores, color=['#FF6B6B', '#45B7D1'])
    
    ax6.set_ylabel('有效性分数 (0-1)')
    ax6.set_title('决策机制有效性\n（60% 公平性 + 40% 效率）', 
                 fontweight='bold')
    ax6.grid(True, alpha=0.3, axis='y')
    
    # 添加数值标签
    for bar, score in zip(bars6, effectiveness_scores):
        height = bar.get_height()
        ax6.text(bar.get_x() + bar.get_width()/2, height + 0.02,
                f'{score:.3f}', ha='center', va='bottom', fontsize=10)
    
    # 7. 气候影响分析
    ax7 = plt.subplot(3, 3, 7)
    
    # 比较默认 vs 无极端天气
    metrics_to_compare = ['平均峰值强度', '平均到达峰值时间',
                         '累计负担基尼系数', '平均持续年数']
    indices_to_compare = [0, 1, 2, 3]
    
    default_vals = [data_raw['默认模拟'][i] for i in indices_to_compare]
    no_weather_vals = [data_raw['无极端天气'][i] for i in indices_to_compare]
    
    x_climate = np.arange(len(metrics_to_compare))
    width_climate = 0.35
    
    ax7.bar(x_climate - width_climate/2, default_vals, width_climate,
           label='默认（有天气）', alpha=0.8)
    ax7.bar(x_climate + width_climate/2, no_weather_vals, width_climate,
           label='无极端天气', alpha=0.8)
    
    ax7.set_xticks(x_climate)
    ax7.set_xticklabels(['峰值\n强度', '到达峰值\n时间', '基尼\n系数',
                        '持续\n年数'], fontsize=9)
    ax7.set_ylabel('指标值')
    ax7.set_title('极端天气的影响\n（气候作为催化剂）', fontweight='bold')
    ax7.legend(fontsize=8)
    ax7.grid(True, alpha=0.3, axis='y')
    
    # 8. 政策干预有效性
    ax8 = plt.subplot(3, 3, 8)
    
    # 比较默认 vs 高效维护
    intervention_metrics = ['平均峰值强度', '平均到达峰值时间',
                           '累计负担基尼系数', '速率差距AUC']
    intervention_indices = [0, 1, 2, 5]
    
    default_interv = [data_raw['默认模拟'][i] for i in intervention_indices]
    efficient_interv = [data_raw['高效维护群体'][i] for i in intervention_indices]
    
    # 计算百分比变化
    changes = []
    for i, idx in enumerate(intervention_indices):
        default_val = default_interv[i]
        efficient_val = efficient_interv[i]
        
        # 确定方向
        if metrics[idx] in ['平均峰值强度', '累计负担基尼系数',
                           '平均持续年数', '曾经叛乱比例',
                           '差距波动性']:
            change = ((default_val - efficient_val) / default_val) * 100
        else:
            change = ((efficient_val - default_val) / default_val) * 100
        changes.append(change)
    
    x_policy = np.arange(len(intervention_metrics))
    colors_policy = ['lightgreen' if c > 0 else 'lightcoral' for c in changes]
    
    bars8 = ax8.bar(x_policy, changes, color=colors_policy, edgecolor='black')
    
    ax8.set_xticks(x_policy)
    ax8.set_xticklabels(['峰值\n强度', '到达峰值\n时间', '基尼\n系数',
                        'AUC\n差距'], fontsize=9)
    ax8.set_ylabel('百分比变化 (%)')
    ax8.set_title('政策干预影响\n（高效维护）', fontweight='bold')
    ax8.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax8.grid(True, alpha=0.3, axis='y')
    
    # 添加数值标签
    for bar, change in zip(bars8, changes):
        height = bar.get_height()
        ax8.text(bar.get_x() + bar.get_width()/2, height + (1 if height > 0 else -3),
                f'{change:+.1f}%', ha='center', va='bottom' if height > 0 else 'top',
                fontsize=9)
    
    # 9. 最终结论摘要
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis('tight')
    ax9.axis('off')
    
    conclusions = [
        '关键发现：',
        '1. 群体投票提高公平性',
        '   （基尼系数：0.294 → 0.237，-19.5%）',
        '2. 但降低决策效率',
        '   （到达峰值时间：6.0 → 5.2 年）',
        '3. 极端天气是关键催化剂',
        '   （多个指标改善）',
        '4. 政策可以延迟但不能防止',
        '   （维护：+3.2 年到峰值）',
        '5. 权衡：公平性 vs 速度',
        '   不存在完美解决方案'
    ]
    
    # 添加带格式的文本
    for i, line in enumerate(conclusions):
        if '关键发现' in line:
            ax9.text(0.05, 0.95 - i*0.1, line, transform=ax9.transAxes,
                    fontsize=12, fontweight='bold', va='top')
        elif any(word in line for word in ['提高', '关键催化剂', '延迟']):
            ax9.text(0.05, 0.95 - i*0.1, line, transform=ax9.transAxes,
                    fontsize=10, fontweight='bold', va='top', color='green')
        elif any(word in line for word in ['降低', '权衡']):
            ax9.text(0.05, 0.95 - i*0.1, line, transform=ax9.transAxes,
                    fontsize=10, fontweight='bold', va='top', color='red')
        else:
            ax9.text(0.05, 0.95 - i*0.1, line, transform=ax9.transAxes,
                    fontsize=10, va='top')
    
    ax9.set_title('实验结论摘要', fontweight='bold', pad=20)
    
    plt.suptitle('综合分析仪表板：叛乱活动实验', 
                fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.show()

# ==================== 主执行 ====================
if __name__ == "__main__":
    print("=" * 70)
    print("叛乱活动跨实验分析")
    print("=" * 70)
    print(f"实验数量：{len(experiments)}")
    print(f"每个实验的指标数量：{len(metrics)}")
    print("\n分析的实验：")
    for i, exp in enumerate(experiments, 1):
        print(f"  {i}. {exp}")
    
    print("\n生成可视化...")
    
    # 生成所有图表
    plot_radar_chart()
    plot_bar_charts()
    plot_heatmap()
    plot_decision_mechanisms()
    plot_scatter_matrix()
    plot_performance_dashboard()
    
    print("\n" + "=" * 70)
    print("分析完成")
    print("=" * 70)
    
    # 打印摘要统计
    print("\n摘要统计：")
    print("-" * 40)
    
    # 为每个指标找到最佳表现者
    for i, metric in enumerate(metrics):
        values = [data_raw[exp][i] for exp in experiments]
        
        if metric in ['平均峰值强度', '累计负担基尼系数',
                     '平均持续年数', '曾经叛乱比例',
                     '差距波动性']:
            best_idx = np.argmin(values)
            best_value = min(values)
            direction = "越低"
        else:
            best_idx = np.argmax(values)
            best_value = max(values)
            direction = "越高"
        
        best_exp = experiments[best_idx]
        print(f"{metric}：")
        print(f"  {direction}越好")
        print(f"  最佳：{best_exp} = {best_value:.3f}")
        print(f"  默认：{data_raw['默认模拟'][i]:.3f}")
        
        if best_exp != '默认模拟':
            change_pct = ((data_raw['默认模拟'][i] - best_value) / 
                         data_raw['默认模拟'][i] * 100)
            if direction == "越高":
                change_pct = -change_pct
            print(f"  改进：{change_pct:+.1f}%")
        print()