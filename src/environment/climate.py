import numpy as np
from typing import List

class ClimateSystem:
    def __init__(self, climate_data_path: str):
        """
        初始化气候系统
        :param climate_data_path: climate.csv文件路径
        """
        self.climate_data = self._load_climate_data(climate_data_path)
        self.climate_impact_threshold = 0.5  # 影响运河状态的阈值
        # self.current_climate = 0.0
        
    def _load_climate_data(self, path: str) -> List[float]:
        """
        加载气候数据
        :param path: 数据文件路径
        :return: 气候影响度列表
        """
        try:
            data = np.loadtxt(path, delimiter=',')
            # 处理NaN值，用0替代
            data[np.isnan(data)] = 0
            return data.tolist()
        except Exception as e:
            print(f"Error loading climate data: {e}")
            return []
    
    def get_current_impact(self, current_year: int = None) -> float:
        """
        获取当前年份的气候影响度
        :return: 气候影响度
        """
        current_year = int(current_year[:4])-1650
        if not self.climate_data or current_year >= len(self.climate_data):
            return 0.0
        return self.climate_data[current_year]
    
    def get_canal_impact_factor(self) -> float:
        """
        计算对运河的影响因子
        :return: 影响因子(0-1之间)
        """
        impact = self.get_current_impact()
        abs_impact = abs(impact)
        
        if abs_impact < self.climate_impact_threshold:
            return 0.0
        
        # 线性映射到0-1范围
        normalized_impact = (abs_impact - self.climate_impact_threshold) / (1.0 - self.climate_impact_threshold)
        return min(normalized_impact, 1.0)
