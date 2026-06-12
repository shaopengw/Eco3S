import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# 配置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class AutoPlotter:
    """
    自动绘图器：根据模拟结果文件或数据字典自动生成图表。

    支持的绘图模式：
    - line:       折线图（默认时间序列）
    - bar:        柱状图
    - area:       面积图
    - stacked_area: 堆叠面积图
    - grouped_bar: 分组柱状图（多列同图）
    - multi_axis:  多Y轴图（不同量纲的列放在一起）
    - scatter:    散点图
    - heatmap:    热力图
    - combo:      组合图（柱状+折线）
    """

    TIME_COL_CANDIDATES = [
        'year', 'years', 'time', 'period', 'periods',
        'step', 'steps', 'round', 'iteration', 'tick'
    ]

    COLOR_PALETTE = [
        '#4ECDC4', '#FF6B6B', '#9B59B6', '#FF9F43',
        '#3498DB', '#F1C40F', '#2ECC71', '#E91E63',
        '#9C88FF', '#A8E6CF', '#FF6348', '#00D2D3'
    ]

    def __init__(
        self,
        data: Union[pd.DataFrame, Dict[str, Any]],
        output_dir: Optional[str] = None,
        plot_config: Optional[Dict[str, Any]] = None
    ):
        self.df = self._normalize_data(data)
        self.output_dir = output_dir
        self.plot_config = plot_config or {}
        self.time_col = self._infer_time_column()
        self._color_index = 0
        self._color_map: Dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # 构造方法
    # ------------------------------------------------------------------ #
    @classmethod
    def from_csv(
        cls,
        path: str,
        output_dir: Optional[str] = None,
        plot_config: Optional[Dict[str, Any]] = None
    ) -> "AutoPlotter":
        df = pd.read_csv(path)
        return cls(df, output_dir=output_dir, plot_config=plot_config)

    @classmethod
    def from_json(
        cls,
        path: str,
        output_dir: Optional[str] = None,
        plot_config: Optional[Dict[str, Any]] = None
    ) -> "AutoPlotter":
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(data, output_dir=output_dir, plot_config=plot_config)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        output_dir: Optional[str] = None,
        plot_config: Optional[Dict[str, Any]] = None
    ) -> "AutoPlotter":
        return cls(data, output_dir=output_dir, plot_config=plot_config)

    @classmethod
    def from_simulator(
        cls,
        simulator: Any,
        output_dir: Optional[str] = None,
        plot_config: Optional[Dict[str, Any]] = None
    ) -> "AutoPlotter":
        if hasattr(simulator, 'results') and isinstance(simulator.results, dict):
            return cls(simulator.results, output_dir=output_dir, plot_config=plot_config)
        raise ValueError("Simulator 没有可用的 results 属性")

    # ------------------------------------------------------------------ #
    # 数据归一化
    # ------------------------------------------------------------------ #
    def _normalize_data(self, data: Union[pd.DataFrame, Dict[str, Any]]) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()

        if isinstance(data, dict):
            # 尝试判断是否是时间序列 dict（值为等长 list）
            lists = {k: v for k, v in data.items() if isinstance(v, (list, tuple, np.ndarray))}
            if lists and len(set(len(v) for v in lists.values())) == 1:
                return pd.DataFrame(data)

            # 否则视为嵌套 JSON（如 info_propagation 的结果）
            flat = self._flatten_dict(data)
            if flat:
                df = pd.DataFrame.from_dict(flat, orient='index')
                return df.reset_index().rename(columns={'index': 'category'})

            return pd.DataFrame(data)

        raise TypeError(f"不支持的数据类型: {type(data)}")

    @staticmethod
    def _flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict[str, Dict[str, Any]]:
        """
        将嵌套 dict 扁平化。
        假设顶层键是类别（如策略名），底层键是指标。
        返回 {category: {flattened_key: value}}。
        """
        result: Dict[str, Dict[str, Any]] = {}
        for top_key, top_val in d.items():
            if not isinstance(top_val, dict):
                continue
            flat = {}
            stack = [(top_val, '')]
            while stack:
                current, prefix = stack.pop()
                if isinstance(current, dict):
                    for k, v in current.items():
                        new_key = f"{prefix}{sep}{k}" if prefix else k
                        if isinstance(v, dict):
                            stack.append((v, new_key))
                        elif isinstance(v, (int, float)):
                            flat[new_key] = v
                elif isinstance(current, (int, float)):
                    flat[prefix] = current
            if flat:
                result[str(top_key)] = flat
        return result

    # ------------------------------------------------------------------ #
    # 推断辅助
    # ------------------------------------------------------------------ #
    def _infer_time_column(self) -> Optional[str]:
        for col in self.TIME_COL_CANDIDATES:
            if col in self.df.columns:
                return col
        # 没有标准时间列时，若存在 category / group / name / label 列，作为类别轴使用
        for col in self.df.columns:
            if col.lower() in ('category', 'group', 'name', 'label'):
                return col
        # 兜底：使用第一列
        if len(self.df.columns) > 0:
            return self.df.columns[0]
        return None

    def _get_numeric_columns(self) -> List[str]:
        cols = []
        for c in self.df.columns:
            if c == self.time_col:
                continue
            # 尝试转为数值，忽略无法转换的
            try:
                converted = pd.to_numeric(self.df[c], errors='coerce')
                if converted.notna().sum() > 0:
                    cols.append(c)
            except Exception:
                continue
        return cols

    def _fallback_mode(self) -> str:
        """没有任何配置时的极简兜底：标准时间序列 -> line，其他 -> bar。"""
        if self.time_col is not None and self.time_col.lower() in self.TIME_COL_CANDIDATES:
            return 'line'
        return 'bar'

    def _get_color(self, key: Union[str, int]) -> str:
        if isinstance(key, str) and key in self._color_map:
            return self._color_map[key]
        idx = self._color_index % len(self.COLOR_PALETTE)
        color = self.COLOR_PALETTE[idx]
        self._color_index += 1
        if isinstance(key, str):
            self._color_map[key] = color
        return color

    # ------------------------------------------------------------------ #
    # 底层绘图与保存
    # ------------------------------------------------------------------ #
    def _ensure_output_dir(self):
        if self.output_dir is None:
            try:
                from src.utils.simulation_context import SimulationContext
                self.output_dir = SimulationContext.get_plots_dir()
                SimulationContext.ensure_directories()
            except Exception:
                self.output_dir = os.path.join(os.getcwd(), 'plot_results')
        os.makedirs(self.output_dir, exist_ok=True)

    def _save_fig(self, suffix: str) -> str:
        self._ensure_output_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        safe = suffix.replace('/', '_').replace('\\', '_').replace(' ', '_').replace('.', '_')
        filename = f"{safe}_{timestamp}_pid{pid}.png"
        path = os.path.join(self.output_dir, filename)
        plt.savefig(path, dpi=300, bbox_inches='tight')
        print(f"图表已保存至：{path}")
        return path

    def _x_values(self):
        if self.time_col and self.time_col in self.df.columns:
            return self.df[self.time_col]
        return range(len(self.df))

    # ------------------------------------------------------------------ #
    # 单图模式
    # ------------------------------------------------------------------ #
    def _plot_line(self, col: str, title: Optional[str] = None, ax=None, color=None) -> Optional[str]:
        close_fig = ax is None
        if close_fig:
            fig, ax = plt.subplots(figsize=(10, 6))
        x = range(len(self.df))
        y = pd.to_numeric(self.df[col], errors='coerce')
        c = color or self._get_color(col)
        ax.plot(x, y, label=col, color=c, marker='o', linewidth=2, markersize=4)
        ax.set_xticks(x[::max(1, len(x)//10)])
        tick_labels = self.df[self.time_col] if self.time_col else x
        ax.set_xticklabels(tick_labels[::max(1, len(x)//10)], rotation=45 if len(self.df) > 10 else 0)
        ax.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax.set_ylabel(col, fontsize=12)
        ax.set_title(title or f'{col}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        if close_fig:
            path = self._save_fig(col)
            plt.close(fig)
            return path
        return None

    def _plot_bar(self, col: str, title: Optional[str] = None, ax=None, color=None) -> Optional[str]:
        close_fig = ax is None
        if close_fig:
            fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(self.df))
        y = pd.to_numeric(self.df[col], errors='coerce')
        c = color or self._get_color(col)
        ax.bar(x, y, color=c, alpha=0.8, label=col)
        ax.set_xticks(x)
        tick_labels = self.df[self.time_col] if self.time_col else x
        ax.set_xticklabels(tick_labels, rotation=45 if len(self.df) > 8 else 0)
        ax.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax.set_ylabel(col, fontsize=12)
        ax.set_title(title or f'{col}', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        ax.legend()
        if close_fig:
            path = self._save_fig(col)
            plt.close(fig)
            return path
        return None

    def _plot_area(self, col: str, title: Optional[str] = None, ax=None, color=None) -> Optional[str]:
        close_fig = ax is None
        if close_fig:
            fig, ax = plt.subplots(figsize=(10, 6))
        x = range(len(self.df))
        y = pd.to_numeric(self.df[col], errors='coerce')
        c = color or self._get_color(col)
        ax.fill_between(x, y, alpha=0.4, color=c)
        ax.plot(x, y, color=c, marker='o', linewidth=2, label=col)
        ax.set_xticks(x[::max(1, len(x)//10)])
        tick_labels = self.df[self.time_col] if self.time_col else x
        ax.set_xticklabels(tick_labels[::max(1, len(x)//10)], rotation=45 if len(self.df) > 10 else 0)
        ax.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax.set_ylabel(col, fontsize=12)
        ax.set_title(title or f'{col}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        if close_fig:
            path = self._save_fig(col)
            plt.close(fig)
            return path
        return None

    def _plot_scatter(self, x_col: str, y_col: str) -> Optional[str]:
        fig, ax = plt.subplots(figsize=(10, 6))
        x = pd.to_numeric(self.df[x_col], errors='coerce')
        y = pd.to_numeric(self.df[y_col], errors='coerce')
        ax.scatter(x, y, color=self._get_color(y_col), alpha=0.7, s=60)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(y_col, fontsize=12)
        ax.set_title(f'{y_col} vs {x_col}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        path = self._save_fig(f'{y_col}_vs_{x_col}')
        plt.close(fig)
        return path

    # ------------------------------------------------------------------ #
    # 组合图模式
    # ------------------------------------------------------------------ #
    def _plot_grouped_bar(self, cols: List[str], title: Optional[str] = None) -> Optional[str]:
        if not cols:
            return None
        fig, ax = plt.subplots(figsize=(max(10, len(cols) * 2), 6))
        x = np.arange(len(self.df))
        width = 0.8 / len(cols)
        for i, col in enumerate(cols):
            y = pd.to_numeric(self.df[col], errors='coerce')
            offset = (i - len(cols) / 2 + 0.5) * width
            ax.bar(x + offset, y, width, label=col, color=self._get_color(col), alpha=0.85)
        ax.set_xticks(x)
        tick_labels = self.df[self.time_col] if self.time_col else x
        ax.set_xticklabels(tick_labels, rotation=45 if len(self.df) > 8 else 0)
        ax.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax.set_ylabel('Value', fontsize=12)
        ax.set_title(title or 'Grouped Bar Chart', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        path = self._save_fig(title or 'grouped_bar')
        plt.close(fig)
        return path

    def _plot_stacked_area(self, cols: List[str], title: Optional[str] = None) -> Optional[str]:
        if not cols:
            return None
        fig, ax = plt.subplots(figsize=(10, 6))
        x = range(len(self.df))
        ys = [pd.to_numeric(self.df[c], errors='coerce') for c in cols]
        ax.stackplot(x, *ys, labels=cols, colors=[self._get_color(c) for c in cols], alpha=0.7)
        ax.set_xticks(x[::max(1, len(x)//10)])
        tick_labels = self.df[self.time_col] if self.time_col else x
        ax.set_xticklabels(tick_labels[::max(1, len(x)//10)])
        ax.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax.set_ylabel('Value', fontsize=12)
        ax.set_title(title or 'Stacked Area Chart', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        path = self._save_fig(title or 'stacked_area')
        plt.close(fig)
        return path

    def _plot_multi_axis(self, cols: List[str], title: Optional[str] = None) -> Optional[str]:
        if not cols:
            return None
        fig, ax1 = plt.subplots(figsize=(10, 6))
        x = self._x_values()
        axes = [ax1]
        for i, col in enumerate(cols):
            y = pd.to_numeric(self.df[col], errors='coerce')
            ax = axes[0] if i == 0 else ax1.twinx()
            if i > 0:
                ax.spines['right'].set_position(('outward', 60 * (i - 1)))
                axes.append(ax)
            ax.plot(x, y, label=col, color=self._get_color(col), marker='o', linewidth=2)
            ax.set_ylabel(col, color=self._get_color(col), fontsize=11)
            ax.tick_params(axis='y', labelcolor=self._get_color(col))
        ax1.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax1.set_title(title or 'Multi-Axis Chart', fontsize=14, fontweight='bold')
        lines = []
        labels = []
        for ax in axes:
            l, lbl = ax.get_legend_handles_labels()
            lines.extend(l)
            labels.extend(lbl)
        ax1.legend(lines, labels, loc='best')
        ax1.grid(True, alpha=0.3)
        path = self._save_fig(title or 'multi_axis')
        plt.close(fig)
        return path

    def _plot_combo(self, bar_cols: List[str], line_cols: List[str], title: Optional[str] = None) -> Optional[str]:
        if not bar_cols and not line_cols:
            return None
        fig, ax1 = plt.subplots(figsize=(10, 6))
        x = np.arange(len(self.df))
        ax1.set_xticks(x)
        tick_labels = self.df[self.time_col] if self.time_col else x
        ax1.set_xticklabels(tick_labels, rotation=45 if len(self.df) > 8 else 0)

        width = 0.8 / max(len(bar_cols), 1)
        for i, col in enumerate(bar_cols):
            y = pd.to_numeric(self.df[col], errors='coerce')
            offset = (i - len(bar_cols) / 2 + 0.5) * width
            ax1.bar(x + offset, y, width, label=col, color=self._get_color(col), alpha=0.8)

        ax1.set_xlabel(self.time_col or 'Index', fontsize=12)
        ax1.set_ylabel('Bar Value', fontsize=12)

        if line_cols:
            ax2 = ax1.twinx()
            for col in line_cols:
                y = pd.to_numeric(self.df[col], errors='coerce')
                ax2.plot(x, y, label=col, color=self._get_color(col), marker='o', linewidth=2)
            ax2.set_ylabel('Line Value', fontsize=12)
            # 合并 legend
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')
        else:
            ax1.legend()

        ax1.set_title(title or 'Combo Chart', fontsize=14, fontweight='bold')
        ax1.grid(axis='y', alpha=0.3)
        path = self._save_fig(title or 'combo')
        plt.close(fig)
        return path

    def _plot_heatmap(self, cols: List[str], title: Optional[str] = None) -> Optional[str]:
        if not cols:
            return None
        fig, ax = plt.subplots(figsize=(max(8, len(cols) * 1.5), max(6, len(self.df) * 0.4)))
        data = self.df[cols].apply(pd.to_numeric, errors='coerce')
        im = ax.imshow(data.values, cmap='YlGnBu', aspect='auto')
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(cols, rotation=45, ha='right')
        yticks = range(len(self.df))
        ax.set_yticks(yticks[::max(1, len(yticks)//15)])
        if self.time_col:
            ax.set_yticklabels(self.df[self.time_col].iloc[::max(1, len(yticks)//15)])
        ax.set_title(title or 'Heatmap', fontsize=14, fontweight='bold')
        fig.colorbar(im, ax=ax)
        path = self._save_fig(title or 'heatmap')
        plt.close(fig)
        return path

    # ------------------------------------------------------------------ #
    # 对外主接口
    # ------------------------------------------------------------------ #
    def plot_all(self) -> List[str]:
        """根据配置自动生成所有图表，返回保存路径列表。"""
        paths: List[str] = []
        if self.df.empty:
            print("数据为空，跳过绘图")
            return paths

        exclude = set(self.plot_config.get('exclude_columns', []))
        numeric_cols = [c for c in self._get_numeric_columns() if c not in exclude]

        if not numeric_cols:
            print("没有可用的数值列，跳过绘图")
            return paths

        # 1. 处理分组配置
        groups = self.plot_config.get('groups', [])
        grouped_cols: set = set()
        for grp in groups:
            grp_cols = [c for c in grp.get('columns', []) if c in numeric_cols]
            if not grp_cols:
                continue
            mode = grp.get('mode', 'grouped_bar')
            title = grp.get('title', 'Group Chart')
            if mode == 'grouped_bar':
                p = self._plot_grouped_bar(grp_cols, title)
            elif mode == 'stacked_area':
                p = self._plot_stacked_area(grp_cols, title)
            elif mode == 'multi_axis':
                p = self._plot_multi_axis(grp_cols, title)
            elif mode == 'combo':
                bar_cols = grp.get('bar_columns', [])
                line_cols = grp.get('line_columns', [])
                p = self._plot_combo(bar_cols, line_cols, title)
            elif mode == 'heatmap':
                p = self._plot_heatmap(grp_cols, title)
            elif mode == 'scatter' and len(grp_cols) >= 2:
                p = self._plot_scatter(grp_cols[0], grp_cols[1])
            else:
                p = None
            if p:
                paths.append(p)
            grouped_cols.update(grp_cols)

        # 2. 处理剩余单列
        default_mode = self.plot_config.get('default_mode', self._fallback_mode())
        remaining = [c for c in numeric_cols if c not in grouped_cols]
        for col in remaining:
            col_cfg = self.plot_config.get('columns', {}).get(col, {})
            mode = col_cfg.get('mode', default_mode)
            if mode == 'line':
                p = self._plot_line(col)
            elif mode == 'bar':
                p = self._plot_bar(col)
            elif mode == 'area':
                p = self._plot_area(col)
            else:
                p = self._plot_line(col)
            if p:
                paths.append(p)

        return paths

# ======================================================================
# 便捷函数
# ======================================================================
def auto_plot_results(
    data_source: Union[str, pd.DataFrame, Dict[str, Any]],
    output_dir: Optional[str] = None,
    plot_config: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    自动根据数据源生成图表。

    Parameters
    ----------
    data_source : str | DataFrame | dict
        CSV/JSON 文件路径，或 DataFrame，或 dict。
    output_dir : str, optional
        图表输出目录。
    plot_config : dict, optional
        绘图配置，支持 exclude_columns、columns、groups 等。

    Returns
    -------
    List[str]
        生成的图表文件路径列表。
    """
    if isinstance(data_source, str):
        if data_source.endswith('.csv'):
            plotter = AutoPlotter.from_csv(data_source, output_dir=output_dir, plot_config=plot_config)
        elif data_source.endswith('.json'):
            plotter = AutoPlotter.from_json(data_source, output_dir=output_dir, plot_config=plot_config)
        else:
            raise ValueError(f"不支持的文件格式: {data_source}")
    elif isinstance(data_source, pd.DataFrame):
        plotter = AutoPlotter(data_source, output_dir=output_dir, plot_config=plot_config)
    elif isinstance(data_source, dict):
        plotter = AutoPlotter.from_dict(data_source, output_dir=output_dir, plot_config=plot_config)
    else:
        raise TypeError(f"不支持的数据源类型: {type(data_source)}")
    return plotter.plot_all()


def auto_plot_from_directory(
    data_dir: str,
    output_dir: Optional[str] = None,
    plot_config: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    扫描目录中的结果文件并自动绘图。
    优先使用最新的 CSV，其次 JSON。
    """
    if not os.path.exists(data_dir):
        print(f"目录不存在: {data_dir}")
        return []

    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]

    if csv_files:
        csv_files.sort(key=lambda f: os.path.getctime(os.path.join(data_dir, f)), reverse=True)
        latest = os.path.join(data_dir, csv_files[0])
        return auto_plot_results(latest, output_dir=output_dir, plot_config=plot_config)

    if json_files:
        json_files.sort(key=lambda f: os.path.getctime(os.path.join(data_dir, f)), reverse=True)
        latest = os.path.join(data_dir, json_files[0])
        return auto_plot_results(latest, output_dir=output_dir, plot_config=plot_config)

    print(f"目录中未找到 CSV 或 JSON 结果文件: {data_dir}")
    return []
