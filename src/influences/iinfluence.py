"""
影响函数抽象接口 (Influence Function Interface)

定义了模块间影响关系的抽象基类。
影响函数描述了一个模块（source）如何影响另一个模块（target）。

核心概念：
- source: 影响源模块的名称（如 "climate", "transport_economy"）
- target: 目标模块的名称（如 "population", "towns"）
- name: 影响函数的名称，用于标识具体的影响类型
- apply: 应用影响的方法，接收目标对象和上下文，返回影响结果

示例：
    class ClimateToPopulationInfluence(IInfluenceFunction):
        def __init__(self):
            super().__init__(
                source="climate",
                target="population",
                name="extreme_weather_death"
            )
        
        def apply(self, target_obj, context: dict):
            climate = context.get('climate')
            if climate and climate.is_extreme_event():
                impact = climate.get_current_impact()
                # 根据气候影响计算人口死亡
                death_rate = impact * 0.01
                return death_rate
            return 0.0
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class IInfluenceFunction(ABC):
    """
    影响函数抽象基类
    
    定义了模块间影响关系的标准接口。所有具体的影响函数都应该继承此类。
    
    Attributes:
        source (str): 影响源模块的名称
        target (str): 目标模块的名称
        name (str): 影响函数的唯一标识名称
        description (str): 影响函数的描述信息（可选）
    
    Methods:
        apply: 应用影响的核心方法
        validate_context: 验证上下文是否包含必需的信息
    """
    
    def __init__(self, source: str, target: str, name: str, description: str = ""):
        """
        初始化影响函数
        
        Args:
            source: 影响源模块的名称（如 "climate", "transport_economy"）
            target: 目标模块的名称（如 "population", "towns"）
            name: 影响函数的名称，应具有描述性（如 "extreme_weather_death"）
            description: 影响函数的详细描述（可选）
        
        Example:
            influence = MyInfluence(
                source="climate",
                target="population",
                name="temperature_birth_rate",
                description="极端温度影响出生率"
            )
        """
        self._source = source
        self._target = target
        self._name = name
        self._description = description
    
    @property
    def source(self) -> str:
        """影响源模块的名称"""
        return self._source
    
    @property
    def target(self) -> str:
        """目标模块的名称"""
        return self._target
    
    @property
    def name(self) -> str:
        """影响函数的唯一标识名称"""
        return self._name
    
    @property
    def description(self) -> str:
        """影响函数的描述信息"""
        return self._description
    
    @abstractmethod
    def apply(self, target_obj: Any, context: dict) -> Any:
        """
        应用影响函数
        
        这是影响函数的核心方法，定义了如何将影响应用到目标对象上。
        
        Args:
            target_obj: 目标模块的实例（或关键属性）
                - 可以是完整的模块实例（如 Population 对象）
                - 也可以是模块的特定属性（如人口数量、气候数据等）
                - 具体类型取决于影响函数的设计
            
            context: 包含模拟状态的上下文字典，通常包括：
                - 'time': ITime 实例，当前模拟时间
                - 'map': IMap 实例，地图信息
                - 'climate': IClimateSystem 实例（如果需要）
                - 'transport_economy': ITransportEconomy 实例（如果需要）
                - 'population': IPopulation 实例（如果需要）
                - 'towns': ITowns 实例（如果需要）
                - 'social_network': ISocialNetwork 实例（如果需要）
                - 其他模块实例或全局变量
        
        Returns:
            影响的结果，类型取决于具体实现：
                - 可以是数值（如死亡人数、迁移率）
                - 可以是布尔值（是否触发某个事件）
                - 可以是字典（包含多个影响维度）
                - 可以是 None（如果影响直接修改了 target_obj）
        
        Raises:
            ValueError: 如果上下文缺少必需的信息
            TypeError: 如果 target_obj 类型不匹配
        
        Example:
            def apply(self, target_obj, context: dict):
                # 验证上下文
                climate = context.get('climate')
                if not climate:
                    raise ValueError("Context must contain 'climate'")
                
                # 计算影响
                if climate.is_extreme_event():
                    impact = climate.get_current_impact()
                    death_rate = impact * 0.01
                    return death_rate
                
                return 0.0
        """
        pass
    
    def validate_context(self, context: dict, required_keys: list) -> bool:
        """
        验证上下文是否包含所有必需的键
        
        Args:
            context: 上下文字典
            required_keys: 必需的键列表
        
        Returns:
            如果所有必需的键都存在且不为None，返回True；否则返回False
        
        Raises:
            ValueError: 如果缺少必需的键
        
        Example:
            def apply(self, target_obj, context: dict):
                self.validate_context(context, ['climate', 'time'])
                # 继续执行影响逻辑...
        """
        missing_keys = [key for key in required_keys if key not in context or context[key] is None]
        
        if missing_keys:
            raise ValueError(
                f"Influence '{self.name}' requires keys {missing_keys} in context, "
                f"but they are missing or None"
            )
        
        return True
    
    def __str__(self) -> str:
        """返回影响函数的字符串表示"""
        return f"<{self.__class__.__name__}: {self.source} -> {self.target} [{self.name}]>"
    
    def __repr__(self) -> str:
        """返回影响函数的详细表示"""
        return (
            f"{self.__class__.__name__}("
            f"source='{self.source}', "
            f"target='{self.target}', "
            f"name='{self.name}'"
            f")"
        )
