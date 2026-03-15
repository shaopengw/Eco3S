"""
内置影响函数实现 (Built-in Influence Functions)

提供开箱即用的影响函数实现和工厂方法。
这些内置影响函数涵盖了常见的影响模式。

可用的影响函数类型：
- linear_multiplier: 线性乘法器影响
- threshold: 阈值触发影响
- conditional: 条件影响
- lambda: 自定义Lambda影响
"""

from typing import Any, Callable, Dict, Optional
from .iinfluence import IInfluenceFunction


# ============================================================
# 线性乘法器影响 (Linear Multiplier Influence)
# ============================================================

class LinearMultiplierInfluence(IInfluenceFunction):
    """
    线性乘法器影响函数
    
    计算影响 = 源值 * 倍率
    
    适用场景：
    - 气候影响人口死亡率
    - 交通成本影响贸易量
    - 税率影响满意度
    """
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        multiplier: float = 1.0,
        source_key: str = 'value',
        description: str = ""
    ):
        """
        初始化线性乘法器影响
        
        Args:
            source: 源模块名称
            target: 目标模块名称
            name: 影响函数名称
            multiplier: 乘法倍率
            source_key: 从源对象中获取值的键名
            description: 描述信息
        """
        super().__init__(source, target, name, description)
        self.multiplier = multiplier
        self.source_key = source_key
    
    def apply(self, target_obj: Any, context: dict) -> float:
        """
        应用线性乘法器影响
        
        Args:
            target_obj: 目标对象（未使用，影响值由调用者应用）
            context: 上下文，必须包含源模块
        
        Returns:
            影响值 = 源值 * 倍率
        """
        self.validate_context(context, [self.source])
        
        source_obj = context[self.source]
        
        # 获取源值
        if hasattr(source_obj, self.source_key):
            source_value = getattr(source_obj, self.source_key)
        elif isinstance(source_obj, dict) and self.source_key in source_obj:
            source_value = source_obj[self.source_key]
        else:
            raise ValueError(
                f"Cannot get '{self.source_key}' from source '{self.source}'"
            )
        
        # 计算影响
        impact = source_value * self.multiplier
        return impact


def create_linear_multiplier_influence(config: dict) -> LinearMultiplierInfluence:
    """
    创建线性乘法器影响函数
    
    Args:
        config: 配置字典，格式：
            {
                'source': 'climate',
                'target': 'population',
                'name': 'temperature_death',
                'params': {
                    'multiplier': 0.01,
                    'source_key': 'temperature'
                }
            }
    """
    params = config.get('params', {})
    return LinearMultiplierInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        multiplier=params.get('multiplier', 1.0),
        source_key=params.get('source_key', 'value'),
        description=config.get('description', '')
    )


# ============================================================
# 阈值触发影响 (Threshold Influence)
# ============================================================

class ThresholdInfluence(IInfluenceFunction):
    """
    阈值触发影响函数
    
    当源值超过阈值时触发影响。
    
    适用场景：
    - 气候极端事件（温度 > 35°C）
    - 满意度低于阈值引发叛乱
    - 人口密度超标影响卫生
    """
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        threshold: float,
        impact_value: Any = True,
        source_key: str = 'value',
        compare_op: str = 'gt',  # gt, gte, lt, lte, eq
        description: str = ""
    ):
        """
        初始化阈值触发影响
        
        Args:
            source: 源模块名称
            target: 目标模块名称
            name: 影响函数名称
            threshold: 阈值
            impact_value: 触发时的影响值
            source_key: 源值的键名
            compare_op: 比较操作符（gt/gte/lt/lte/eq）
            description: 描述信息
        """
        super().__init__(source, target, name, description)
        self.threshold = threshold
        self.impact_value = impact_value
        self.source_key = source_key
        self.compare_op = compare_op
        
        # 比较函数映射
        self._ops = {
            'gt': lambda x, t: x > t,
            'gte': lambda x, t: x >= t,
            'lt': lambda x, t: x < t,
            'lte': lambda x, t: x <= t,
            'eq': lambda x, t: x == t
        }
    
    def apply(self, target_obj: Any, context: dict) -> Any:
        """
        应用阈值触发影响
        
        Returns:
            如果触发返回 impact_value，否则返回 None
        """
        self.validate_context(context, [self.source])
        
        source_obj = context[self.source]
        
        # 获取源值
        if hasattr(source_obj, self.source_key):
            source_value = getattr(source_obj, self.source_key)
        elif isinstance(source_obj, dict) and self.source_key in source_obj:
            source_value = source_obj[self.source_key]
        else:
            raise ValueError(
                f"Cannot get '{self.source_key}' from source '{self.source}'"
            )
        
        # 检查阈值
        compare_fn = self._ops.get(self.compare_op)
        if not compare_fn:
            raise ValueError(f"Unknown compare operator: {self.compare_op}")
        
        if compare_fn(source_value, self.threshold):
            return self.impact_value
        
        return None


def create_threshold_influence(config: dict) -> ThresholdInfluence:
    """创建阈值触发影响函数"""
    params = config.get('params', {})
    return ThresholdInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        threshold=params.get('threshold', 0),
        impact_value=params.get('impact_value', True),
        source_key=params.get('source_key', 'value'),
        compare_op=params.get('compare_op', 'gt'),
        description=config.get('description', '')
    )


# ============================================================
# 条件影响 (Conditional Influence)
# ============================================================

class ConditionalInfluence(IInfluenceFunction):
    """
    条件影响函数
    
    根据多个条件决定是否应用影响。
    
    适用场景：
    - 复杂的触发条件（多个因素共同作用）
    - 季节性影响（只在特定时间生效）
    - 地区性影响（只在特定区域生效）
    """
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        conditions: Dict[str, Any],
        impact_value: Any,
        description: str = ""
    ):
        """
        初始化条件影响
        
        Args:
            source: 源模块名称
            target: 目标模块名称
            name: 影响函数名称
            conditions: 条件字典，格式：{'module.key': value, ...}
            impact_value: 满足条件时的影响值
            description: 描述信息
        """
        super().__init__(source, target, name, description)
        self.conditions = conditions
        self.impact_value = impact_value
    
    def apply(self, target_obj: Any, context: dict) -> Any:
        """
        应用条件影响
        
        Returns:
            如果所有条件都满足返回 impact_value，否则返回 None
        """
        # 检查所有条件
        for condition_key, expected_value in self.conditions.items():
            # 解析条件键（格式：module.attribute）
            parts = condition_key.split('.')
            if len(parts) < 2:
                raise ValueError(
                    f"Invalid condition key format: {condition_key}. "
                    f"Expected format: 'module.attribute'"
                )
            
            module_name = parts[0]
            attr_path = parts[1:]
            
            # 获取模块
            if module_name not in context:
                return None  # 缺少必需模块，条件不满足
            
            # 获取属性值
            obj = context[module_name]
            for attr in attr_path:
                if hasattr(obj, attr):
                    obj = getattr(obj, attr)
                elif isinstance(obj, dict) and attr in obj:
                    obj = obj[attr]
                else:
                    return None  # 属性不存在，条件不满足
            
            # 检查值是否匹配
            if obj != expected_value:
                return None  # 条件不满足
        
        # 所有条件都满足
        return self.impact_value


def create_conditional_influence(config: dict) -> ConditionalInfluence:
    """创建条件影响函数"""
    params = config.get('params', {})
    return ConditionalInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        conditions=params.get('conditions', {}),
        impact_value=params.get('impact_value', True),
        description=config.get('description', '')
    )


# ============================================================
# Lambda 影响 (Lambda Influence)
# ============================================================

class LambdaInfluence(IInfluenceFunction):
    """
    Lambda 影响函数
    
    使用自定义函数计算影响。
    提供最大的灵活性，适用于复杂的影响逻辑。
    
    注意：此类主要用于程序化创建，不建议从配置文件加载。
    """
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        compute_fn: Callable[[Any, dict], Any],
        description: str = ""
    ):
        """
        初始化 Lambda 影响
        
        Args:
            source: 源模块名称
            target: 目标模块名称
            name: 影响函数名称
            compute_fn: 计算函数，签名：(target_obj, context) -> impact
            description: 描述信息
        """
        super().__init__(source, target, name, description)
        self.compute_fn = compute_fn
    
    def apply(self, target_obj: Any, context: dict) -> Any:
        """应用 Lambda 影响"""
        return self.compute_fn(target_obj, context)


def create_lambda_influence(config: dict) -> LambdaInfluence:
    """
    创建 Lambda 影响函数
    
    注意：此工厂方法主要用于占位，实际使用中应直接实例化 LambdaInfluence。
    从配置文件加载Lambda函数存在安全风险，不推荐使用。
    """
    raise NotImplementedError(
        "Lambda influences should be created programmatically, "
        "not from configuration files due to security concerns."
    )
