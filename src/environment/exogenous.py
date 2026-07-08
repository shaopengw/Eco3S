"""
通用外生变量数据读取实现。

读取多列带表头 CSV（每列一个外生变量，每行一个时间步），
并按时间步索引提供取值，供仿真在每个时间步注入到 context。

设计参考 src/environment/climate.py 的加载与索引逻辑，但做成通用多变量机制。
"""

import csv
import math
from typing import Dict, List

from src.interfaces import IExogenousDataProvider


class ExogenousDataProvider(IExogenousDataProvider):
    def __init__(self, data_path: str):
        """
        初始化外生变量数据提供者。

        :param data_path: 多列带表头 CSV 文件路径
        """
        self._data: Dict[str, List[float]] = self._load_data(data_path)
        self._keys: List[str] = list(self._data.keys())

    @property
    def keys(self) -> List[str]:
        return list(self._keys)

    def _load_data(self, path: str) -> Dict[str, List[float]]:
        """
        加载外生变量数据。

        :param path: 数据文件路径
        :return: {列名: 数值序列}；加载失败返回空字典。

        Note:
            - 首行为列名（变量 key）。
            - 空值 / 无法解析 / NaN 一律按 0.0 处理（与 climate 习惯一致）。
        """
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                data: Dict[str, List[float]] = {name: [] for name in fieldnames if name}
                for row in reader:
                    for name in data.keys():
                        data[name].append(self._coerce_float(row.get(name)))
            return data
        except Exception as e:
            print(f"Error loading exogenous data: {e}")
            return {}

    @staticmethod
    def _coerce_float(raw) -> float:
        """把单元格转换为 float；空值 / 非数值 / NaN 统一返回 0.0。"""
        if raw is None:
            return 0.0
        text = str(raw).strip()
        if text == "" or text.lower() in ("nan", "na", "none"):
            return 0.0
        try:
            value = float(text)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(value):
            return 0.0
        return value

    def get_current_values(self, step_index: int) -> Dict[str, float]:
        """
        获取指定时间步上所有外生变量的取值。

        :param step_index: 时间步索引（从 0 开始）
        :return: {变量名: 取值}；无数据时返回空字典。
        """
        if not self._data:
            return {}
        return {key: self.get_value(key, step_index) for key in self._keys}

    def get_value(self, key: str, step_index: int) -> float:
        """
        获取单个外生变量在指定时间步的取值。

        :param key: 变量名（CSV 列名）
        :param step_index: 时间步索引（从 0 开始）
        :return: 变量取值；变量不存在或序列为空时返回 0.0；越界时返回末值。
        """
        series = self._data.get(key)
        if not series:
            return 0.0
        idx = int(step_index) if step_index is not None else 0
        if idx < 0:
            idx = 0
        if idx >= len(series):
            # 越界保持最后一步取值
            return series[-1]
        return series[idx]
