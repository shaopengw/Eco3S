"""
影响函数系统 (Influence Functions System)

该模块定义了模块间影响关系的抽象接口和具体实现。
影响函数用于描述一个模块如何影响另一个模块的行为或状态。

主要组件：
- IInfluenceFunction: 影响函数的抽象接口
- InfluenceRegistry: 影响函数注册中心
- 各种内置的影响函数实现

使用示例：
    from src.influences import IInfluenceFunction, InfluenceRegistry
    
    # 创建注册中心
    registry = InfluenceRegistry()
    
    # 注册影响函数
    registry.register(my_influence)
    
    # 从配置加载
    registry.load_from_config(config_dict)
    
    # 查询影响函数
    influences = registry.get_influences('population')
"""

from .iinfluence import IInfluenceFunction
from .influence_registry import InfluenceRegistry
from .influence_manager import InfluenceManager
from .builtin_influences import (
    LinearMultiplierInfluence,
    ThresholdInfluence,
    ConditionalInfluence,
    LambdaInfluence,
)
from .builtin import (
    ConstantInfluence,
    LinearInfluence,
    CodeInfluence,
    ExprInfluence,
)

__all__ = [
    'IInfluenceFunction',
    'InfluenceRegistry',
    'InfluenceManager',
    'LinearMultiplierInfluence',
    'ThresholdInfluence',
    'ConditionalInfluence',
    'LambdaInfluence',
    'ConstantInfluence',
    'LinearInfluence',
    'CodeInfluence',
    'ExprInfluence',
]
