"""
常用内置影响函数 (Builtin Influence Functions)

提供常用的影响函数实现，包括：
- ConstantInfluence: 设置目标属性为常量值
- LinearInfluence: 根据上下文变量线性计算目标值
- CodeInfluence: 执行用户提供的Python代码片段（受限环境）

使用示例：
    # 1. 常量影响
    const_inf = ConstantInfluence(
        source='government',
        target='population',
        name='set_base_tax',
        target_attr='tax_rate',
        value=0.15
    )
    
    # 2. 线性影响
    linear_inf = LinearInfluence(
        source='climate',
        target='population',
        name='temperature_death',
        target_attr='death_rate_modifier',
        variable='climate.temperature',
        coefficient=0.01,
        constant=0.0
    )
    
    # 3. 代码影响
    code_inf = CodeInfluence(
        source='economy',
        target='towns',
        name='gdp_satisfaction',
        code='satisfaction = min(1.0, gdp / 10000)'
    )
"""

from typing import Any, Optional, Dict
import operator
import math
from .iinfluence import IInfluenceFunction


class ConstantInfluence(IInfluenceFunction):
    """
    常量影响函数
    
    直接设置目标对象的属性为一个常量值。
    适用于配置固定的影响效果，如设置基准税率、初始满意度等。
    
    属性：
        target_attr: 要设置的目标对象属性名
        value: 要设置的常量值
    
    示例：
        # 设置基准税率为15%
        influence = ConstantInfluence(
            source='government',
            target='population',
            name='set_base_tax',
            target_attr='tax_rate',
            value=0.15
        )
        
        # 应用影响
        context = {'government': government}
        influence.apply(population, context)
        # 结果: population.tax_rate = 0.15
    """
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        target_attr: str,
        value: Any,
        description: str = ""
    ):
        """
        初始化常量影响函数
        
        Args:
            source: 影响源模块名称
            target: 目标模块名称
            name: 影响函数名称
            target_attr: 目标对象的属性名（将被设置为value）
            value: 要设置的常量值（可以是任何类型）
            description: 影响描述（可选）
        """
        super().__init__(source, target, name, description or f"设置{target_attr}为{value}")
        self.target_attr = target_attr
        self.value = value
    
    def apply(self, target_obj, context: dict) -> Any:
        """
        应用常量影响，设置目标属性
        
        Args:
            target_obj: 目标模块对象
            context: 上下文字典（本影响不使用）
        
        Returns:
            设置的常量值
        """
        # 设置目标对象的属性
        if hasattr(target_obj, self.target_attr):
            setattr(target_obj, self.target_attr, self.value)
        else:
            # 如果属性不存在，创建它
            setattr(target_obj, self.target_attr, self.value)
        
        return self.value
    
    def __repr__(self) -> str:
        return (f"ConstantInfluence({self.source}->{self.target}:{self.name}, "
                f"attr={self.target_attr}, value={self.value})")


class LinearInfluence(IInfluenceFunction):
    """
    线性影响函数
    
    根据上下文中的变量进行线性计算：result = coefficient * variable + constant
    可以从上下文中读取嵌套属性（如 'climate.temperature'）。
    
    属性：
        target_attr: 要修改的目标对象属性名（可选，如果不指定则只返回计算结果）
        variable: 上下文变量路径（如 'climate.temperature', 'economy.gdp'）
        coefficient: 系数（乘数）
        constant: 常数项（偏置）
        mode: 影响模式 ('set' 直接设置, 'add' 累加, 'multiply' 乘以)
    
    示例：
        # 温度每升高1度，死亡率增加0.01
        influence = LinearInfluence(
            source='climate',
            target='population',
            name='temperature_death',
            target_attr='death_rate_modifier',
            variable='climate.temperature',
            coefficient=0.01,
            constant=0.0,
            mode='add'
        )
        
        # 应用影响
        context = {'climate': climate}  # climate.temperature = 35
        result = influence.apply(population, context)
        # 结果: death_rate_modifier += 0.01 * 35 + 0.0 = 0.35
    """
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        variable: str,
        coefficient: float = 1.0,
        constant: float = 0.0,
        target_attr: Optional[str] = None,
        mode: str = 'set',
        description: str = ""
    ):
        """
        初始化线性影响函数
        
        Args:
            source: 影响源模块名称
            target: 目标模块名称
            name: 影响函数名称
            variable: 上下文变量路径（支持点号分隔的嵌套属性）
            coefficient: 系数（默认1.0）
            constant: 常数项（默认0.0）
            target_attr: 目标属性名（可选，如不指定则只返回计算结果）
            mode: 影响模式 - 'set'(设置), 'add'(累加), 'multiply'(乘以)
            description: 影响描述（可选）
        """
        super().__init__(
            source, target, name,
            description or f"线性影响: {coefficient}*{variable}+{constant}"
        )
        self.variable = variable
        self.coefficient = coefficient
        self.constant = constant
        self.target_attr = target_attr
        self.mode = mode
        
        if mode not in ['set', 'add', 'multiply']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'set', 'add', or 'multiply'")
    
    def _get_variable_value(self, context: dict) -> Optional[float]:
        """
        从上下文中获取变量值
        
        Args:
            context: 上下文字典
        
        Returns:
            变量值（转换为float），如果无法获取则返回None
        """
        parts = self.variable.split('.')
        value = context
        
        try:
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
                
                if value is None:
                    return None
            
            # 尝试转换为float
            return float(value)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
    
    def apply(self, target_obj, context: dict) -> Optional[float]:
        """
        应用线性影响
        
        Args:
            target_obj: 目标模块对象
            context: 上下文字典
        
        Returns:
            计算得到的影响值，如果无法计算则返回None
        """
        # 获取变量值
        var_value = self._get_variable_value(context)
        if var_value is None:
            return None
        
        # 线性计算
        result = self.coefficient * var_value + self.constant
        
        # 如果指定了目标属性，则修改它
        if self.target_attr:
            if self.mode == 'set':
                setattr(target_obj, self.target_attr, result)
            elif self.mode == 'add':
                current = getattr(target_obj, self.target_attr, 0)
                setattr(target_obj, self.target_attr, current + result)
            elif self.mode == 'multiply':
                current = getattr(target_obj, self.target_attr, 1)
                setattr(target_obj, self.target_attr, current * result)
        
        return result
    
    def __repr__(self) -> str:
        return (f"LinearInfluence({self.source}->{self.target}:{self.name}, "
                f"{self.coefficient}*{self.variable}+{self.constant})")


class CodeInfluence(IInfluenceFunction):
    """
    代码影响函数
    
    执行用户提供的Python代码片段来计算影响。
    为了安全性，代码在受限环境中执行，只能访问有限的内置函数和上下文变量。
    
    安全限制：
    - 只能访问白名单中的内置函数（数学运算、基本逻辑等）
    - 不能导入模块
    - 不能访问文件系统
    - 不能执行系统命令
    
    可用内置函数：
    - 数学: abs, min, max, sum, round, pow
    - 数学模块: math.sqrt, math.sin, math.cos, math.log 等
    - 逻辑: all, any, bool, int, float, str
    - 集合: len, list, dict, tuple, set
    
    代码变量：
    - target: 目标对象
    - context: 完整的上下文字典
    - 所有上下文中的模块（如 climate, economy, population 等）
    
    属性：
        code: Python代码字符串
        target_attr: 要设置的目标属性名（可选）
        result_var: 代码执行后从哪个变量读取结果（默认'result'）
    
    示例：
        # 复杂的满意度计算
        influence = CodeInfluence(
            source='economy',
            target='towns',
            name='satisfaction_calc',
            target_attr='satisfaction',
            code='''
# GDP影响基础满意度
base = min(1.0, gdp / 10000)
# 失业率降低满意度
unemployment_penalty = unemployment_rate * 0.5
# 最终满意度
result = max(0.0, base - unemployment_penalty)
'''
        )
        
        # 应用影响
        context = {
            'economy': economy,  # economy.gdp=8000, economy.unemployment_rate=0.1
            'gdp': 8000,
            'unemployment_rate': 0.1
        }
        influence.apply(towns, context)
        # 结果: towns.satisfaction = max(0.0, min(1.0, 8000/10000) - 0.1*0.5) = 0.75
    """
    
    # 安全的内置函数白名单
    SAFE_BUILTINS = {
        # 数学运算
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'round': round,
        'pow': pow,
        # 类型转换和检查
        'int': int,
        'float': float,
        'str': str,
        'bool': bool,
        'len': len,
        # 容器
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        # 逻辑
        'all': all,
        'any': any,
        'range': range,
        # 常量
        'True': True,
        'False': False,
        'None': None,
        # 数学模块
        'math': math,
    }
    
    def __init__(
        self,
        source: str,
        target: str,
        name: str,
        code: str,
        target_attr: Optional[str] = None,
        result_var: str = 'result',
        description: str = ""
    ):
        """
        初始化代码影响函数
        
        Args:
            source: 影响源模块名称
            target: 目标模块名称
            name: 影响函数名称
            code: Python代码字符串（在受限环境中执行）
            target_attr: 目标属性名（可选，如果指定则将结果设置到该属性）
            result_var: 代码执行后读取结果的变量名（默认'result'）
            description: 影响描述（可选）
        
        Raises:
            ValueError: 如果代码包含非法语法
        """
        super().__init__(
            source, target, name,
            description or f"代码影响: {code[:50]}..."
        )
        self.code = code
        self.target_attr = target_attr
        self.result_var = result_var
        
        # 验证代码语法
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            raise ValueError(f"代码语法错误: {e}")
    
    def _prepare_namespace(self, target_obj, context: dict) -> dict:
        """
        准备代码执行的命名空间
        
        Args:
            target_obj: 目标对象
            context: 上下文字典
        
        Returns:
            包含受限内置函数和上下文变量的命名空间
        """
        namespace = {
            '__builtins__': self.SAFE_BUILTINS,
            'target': target_obj,
            'context': context,
        }
        
        # 添加上下文中的所有变量（扁平化访问）
        for key, value in context.items():
            if not key.startswith('_'):  # 跳过私有变量
                namespace[key] = value
        
        return namespace
    
    def apply(self, target_obj, context: dict) -> Any:
        """
        应用代码影响
        
        Args:
            target_obj: 目标模块对象
            context: 上下文字典
        
        Returns:
            代码执行的结果（从result_var变量读取），如果失败则返回None
        
        Raises:
            执行错误会被捕获并打印，返回None
        """
        # 准备命名空间
        namespace = self._prepare_namespace(target_obj, context)
        
        try:
            # 在受限环境中执行代码
            exec(self.code, namespace, namespace)
            
            # 获取结果
            result = namespace.get(self.result_var)
            
            # 如果指定了目标属性，设置它
            if self.target_attr and result is not None:
                setattr(target_obj, self.target_attr, result)
            
            return result
            
        except Exception as e:
            # 执行失败，打印错误并返回None
            print(f"代码影响执行失败 ({self.source}->{self.target}:{self.name}): {e}")
            return None
    
    def __repr__(self) -> str:
        code_preview = self.code.replace('\n', ' ')[:50]
        return f"CodeInfluence({self.source}->{self.target}:{self.name}, code='{code_preview}...')"


# 工厂函数，用于从配置创建影响函数

def create_constant_influence(config: dict) -> ConstantInfluence:
    """
    从配置创建常量影响函数
    
    配置格式:
        {
            'source': 'module_a',
            'target': 'module_b',
            'name': 'influence_name',
            'params': {
                'target_attr': 'attribute_name',
                'value': 0.15
            }
        }
    """
    params = config.get('params', {})
    return ConstantInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        target_attr=params['target_attr'],
        value=params['value'],
        description=config.get('description', '')
    )


def create_linear_influence(config: dict) -> LinearInfluence:
    """
    从配置创建线性影响函数
    
    配置格式:
        {
            'source': 'module_a',
            'target': 'module_b',
            'name': 'influence_name',
            'params': {
                'variable': 'module_a.attribute',
                'coefficient': 0.01,
                'constant': 0.0,
                'target_attr': 'attribute_name',  # 可选
                'mode': 'add'  # 可选: 'set', 'add', 'multiply'
            }
        }
    """
    params = config.get('params', {})
    return LinearInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        variable=params['variable'],
        coefficient=params.get('coefficient', 1.0),
        constant=params.get('constant', 0.0),
        target_attr=params.get('target_attr'),
        mode=params.get('mode', 'set'),
        description=config.get('description', '')
    )


def create_code_influence(config: dict) -> CodeInfluence:
    """
    从配置创建代码影响函数
    
    注意：出于安全考虑，通常不建议从配置文件加载代码影响。
    此函数主要用于受信任的配置来源。
    
    配置格式:
        {
            'source': 'module_a',
            'target': 'module_b',
            'name': 'influence_name',
            'params': {
                'code': 'result = min(1.0, gdp / 10000)',
                'target_attr': 'attribute_name',  # 可选
                'result_var': 'result'  # 可选
            }
        }
    """
    params = config.get('params', {})
    return CodeInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        code=params['code'],
        target_attr=params.get('target_attr'),
        result_var=params.get('result_var', 'result'),
        description=config.get('description', '')
    )
