import numpy as np
from typing import List, Optional, Any, Dict
from src.interfaces import IClimateSystem

class ClimateSystem(IClimateSystem):
    def __init__(self, climate_data_path: str, influence_registry: Optional[Any] = None):
        """
        初始化气候系统
        :param climate_data_path: climate.csv文件路径
        :param influence_registry: 影响函数注册表（可选）
        """
        self._climate_data = self._load_climate_data(climate_data_path)
        self._climate_impact_threshold = 0.5  # 影响运河状态的阈值
        self._influence_registry = influence_registry
        # self.current_climate = 0.0
    
    @property
    def climate_data(self) -> List[float]:
        """气候数据列表"""
        return self._climate_data
    
    @property
    def climate_impact_threshold(self) -> float:
        """影响运河状态的阈值"""
        return self._climate_impact_threshold
    
    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """
        应用影响函数到指定目标
        :param target_name: 目标名称（如'climate_impact'）
        :param context: 上下文数据字典
        """
        if self._influence_registry is None:
            return
        
        influences = self._influence_registry.get_influences(target_name)
        if not influences:
            return
        
        for influence in influences:
            try:
                influence.apply(self, context)
            except Exception as e:
                print(f"[ClimateSystem] Error applying influence to {target_name}: {e}")
        
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
    
    def get_current_impact(self, current_year: int = None, start_year: int = None) -> float:
        """
        获取当前年份的气候影响度
        :return: 气候影响度
        """
        current_year = int(current_year) - start_year
        if not self._climate_data or current_year >= len(self._climate_data):
            return 0.0
        
        # 获取原始数据
        raw_impact = abs(self._climate_data[current_year])
        
        # 构建上下文
        result = {'climate_impact': raw_impact}
        context = {
            'climate_system': self,
            'current_year': current_year,
            'start_year': start_year,
            'raw_impact': raw_impact,
            'climate_data': self._climate_data,
            'result': result
        }
        
        # 尝试使用影响函数
        if self._influence_registry is not None:
            influences = self._influence_registry.get_influences('climate_impact')
            if influences:
                self.apply_influences('climate_impact', context)
                return result['climate_impact']
        
        # 回退到默认行为（向后兼容）
        return raw_impact

