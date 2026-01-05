"""
叛乱分析实验数据可视化脚本
包含三种可视化：外部因素柱状图、内部机制散点图、综合雷达图
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


# ==================== 全局配置 ====================
def configure_matplotlib():
    """配置matplotlib中文显示和样式"""
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False


# ==================== 数据定义 ====================
EXPERIMENT_DATA = {
    "默认模拟": {
        "平均峰值强度": 25.0,
        "平均到峰时间(相对开始年)": 7.2,
        "城镇累积叛乱Gini": 0.272,
        "城镇平均持续年数(Persistence)": 6.16,
        "平均发生过叛乱的城镇比例": 0.985
    },
    "政府群体投票机制": {
        "平均峰值强度": 25.2,
        "平均到峰时间(相对开始年)": 5.2,
        "城镇累积叛乱Gini": 0.237,
        "城镇平均持续年数(Persistence)": 6.09,
        "平均发生过叛乱的城镇比例": 1.0
    },
    "社交网络传播消融": {
        "平均峰值强度": 26.0,
        "平均到峰时间(相对开始年)": 4.83,
        "城镇累积叛乱Gini": 0.252,
        "城镇平均持续年数(Persistence)": 7.21,
        "平均发生过叛乱的城镇比例": 0.994
    },
    "无极端天气": {
        "平均峰值强度": 22.4,
        "平均到峰时间(相对开始年)": 5.8,
        "城镇累积叛乱Gini": 0.270,
        "城镇平均持续年数(Persistence)": 5.35,
        "平均发生过叛乱的城镇比例": 0.941
    },
    "高效维护组": {
        "平均峰值强度": 22.0,
        "平均到峰时间(相对开始年)": 9.2,
        "城镇累积叛乱Gini": 0.299,
        "城镇平均持续年数(Persistence)": 5.49,
        "平均发生过叛乱的城镇比例": 0.970
    },
    "无海运替代组": {
        "平均峰值强度": 17.6,
        "平均到峰时间(相对开始年)": 5.4,
        "城镇累积叛乱Gini": 0.364,
        "城镇平均持续年数(Persistence)": 4.90,
        "平均发生过叛乱的城镇比例": 0.867
    }
}


# ==================== 可视化函数 ====================
def plot_external_factors_impact(df_full: pd.DataFrame):
    """
    绘制外部驱动因素影响图（双Y轴柱状图）
    
    Args:
        df_full: 完整实验数据DataFrame
    """
    # 筛选外部因素实验
    external_experiments = ["默认模拟", "无海运替代组", "无极端天气"]
    df_external = df_full.loc[external_experiments, ["平均峰值强度", "平均发生过叛乱的城镇比例"]]
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    df_external['平均峰值强度'].plot(
        kind='bar', ax=ax1, color='skyblue', 
        position=0, width=0.3, label='平均峰值强度'
    )
    df_external['平均发生过叛乱的城镇比例'].plot(
        kind='bar', ax=ax2, color='salmon', 
        position=1, width=0.3, label='发生叛乱的城镇比例'
    )
    
    ax1.set_ylabel('平均峰值强度 (叛乱城镇数)')
    ax2.set_ylabel('发生过叛乱的城镇比例')
    ax1.set_xlabel('实验情景')
    ax1.set_xticklabels(df_external.index, rotation=0)
    
    fig.legend(loc="upper center", bbox_to_anchor=(0.5, 1.05), ncol=2)
    plt.title('外部驱动因素对危机严重性与范围的影响')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()


def plot_internal_mechanisms_impact(df_full: pd.DataFrame):
    """
    绘制内部机制影响图（三维散点图）
    
    Args:
        df_full: 完整实验数据DataFrame
    """
    # 筛选内部机制实验
    internal_experiments = ["默认模拟", "高效维护组", "政府群体投票机制", "社交网络传播消融"]
    df_internal = df_full.loc[
        internal_experiments, 
        ["平均到峰时间(相对开始年)", "城镇平均持续年数(Persistence)", "平均峰值强度"]
    ]
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # 散点图：x=爆发时间, y=持续时间, size&color=强度
    sizes = df_internal['平均峰值强度'] * 20
    scatter = ax.scatter(
        df_internal['平均到峰时间(相对开始年)'],
        df_internal['城镇平均持续年数(Persistence)'],
        s=sizes,
        c=df_internal['平均峰值强度'],
        cmap='viridis',
        alpha=0.7
    )
    
    # 添加实验名称标签
    for experiment_name in df_internal.index:
        ax.annotate(
            experiment_name,
            (df_internal.loc[experiment_name, '平均到峰时间(相对开始年)'],
             df_internal.loc[experiment_name, '城镇平均持续年数(Persistence)']),
            xytext=(5, 5),
            textcoords='offset points'
        )
    
    ax.set_xlabel('危机爆发时间 (年) → (爆发更晚)')
    ax.set_ylabel('叛乱平均持续年数 (年) → (更固化)')
    plt.title('内部机制对危机节奏、持续性与强度的影响')
    plt.colorbar(scatter, label='平均峰值强度 (严重程度)')
    plt.grid(True)
    fig.tight_layout()
    plt.show()


def plot_comprehensive_radar(df_full: pd.DataFrame):
    """
    绘制综合雷达图
    
    Args:
        df_full: 完整实验数据DataFrame
    """
    # 构建雷达图数据（正向化处理）
    df_radar = pd.DataFrame({
        '强度': df_full['平均峰值强度'],
        '波及范围': df_full['平均发生过叛乱的城镇比例'],
        '持续性': df_full['城镇平均持续年数(Persistence)'],
        '爆发速度': 10 - df_full['平均到峰时间(相对开始年)'],  # 越快越高
        '混乱程度': 1 - df_full['城镇累积叛乱Gini']  # 越混乱越高
    })
    
    # Min-Max归一化
    df_normalized = (df_radar - df_radar.min()) / (df_radar.max() - df_radar.min())
    
    # 设置雷达图角度
    labels = df_radar.columns.tolist()
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]  # 闭合
    
    # 绘制
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    for experiment_name, row in df_normalized.iterrows():
        values = row.tolist()
        values += values[:1]  # 闭合
        ax.plot(angles, values, label=experiment_name, linewidth=2)
        ax.fill(angles, values, alpha=0.2)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.title('各实验情景危机模式雷达图 (面积越大越严峻)')
    plt.show()


# ==================== 主程序 ====================
def main():
    """主程序：执行所有可视化"""
    configure_matplotlib()
    
    # 加载数据
    df_full = pd.DataFrame(EXPERIMENT_DATA).T
    
    # 生成三种可视化
    print("生成外部因素影响图...")
    plot_external_factors_impact(df_full)
    
    print("生成内部机制影响图...")
    plot_internal_mechanisms_impact(df_full)
    
    print("生成综合雷达图...")
    plot_comprehensive_radar(df_full)
    
    print("所有可视化已完成！")


if __name__ == "__main__":
    main()