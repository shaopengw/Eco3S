"""
测试 builtin.py 中的影响函数 (Test Builtin Influences)
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.influences import (
    ConstantInfluence,
    LinearInfluence,
    CodeInfluence,
    ExprInfluence,
    InfluenceRegistry
)


# 创建测试对象
class MockModule:
    """模拟模块对象"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_constant_influence():
    """测试常量影响函数"""
    print("=" * 60)
    print("测试 ConstantInfluence")
    print("=" * 60)
    
    # 创建目标对象
    target = MockModule(tax_rate=0.0)
    
    # 创建常量影响
    influence = ConstantInfluence(
        source='government',
        target='population',
        name='set_base_tax',
        target_attr='tax_rate',
        value=0.15
    )
    
    print(f"\n1. 影响函数: {influence}")
    print(f"   设置前: target.tax_rate = {target.tax_rate}")
    
    # 应用影响
    context = {}
    result = influence.apply(target, context)
    
    print(f"   应用影响返回: {result}")
    print(f"   设置后: target.tax_rate = {target.tax_rate}")
    
    assert target.tax_rate == 0.15, f"Expected 0.15, got {target.tax_rate}"
    assert result == 0.15, f"Expected return value 0.15, got {result}"
    
    print("\n2. 测试设置不存在的属性:")
    target2 = MockModule()
    influence2 = ConstantInfluence(
        source='test',
        target='test',
        name='set_new_attr',
        target_attr='new_attribute',
        value=42
    )
    
    influence2.apply(target2, {})
    print(f"   新属性: target2.new_attribute = {target2.new_attribute}")
    assert target2.new_attribute == 42
    
    print("\n✓ ConstantInfluence 测试通过")
    return True


def test_linear_influence():
    """测试线性影响函数"""
    print("\n" + "=" * 60)
    print("测试 LinearInfluence")
    print("=" * 60)
    
    # 1. 测试基本线性计算（set模式）
    print("\n1. 测试 set 模式:")
    
    climate = MockModule(temperature=35.0)
    target = MockModule(death_rate_modifier=0.0)
    
    influence = LinearInfluence(
        source='climate',
        target='population',
        name='temperature_death',
        variable='climate.temperature',
        coefficient=0.01,
        constant=0.0,
        target_attr='death_rate_modifier',
        mode='set'
    )
    
    print(f"   影响函数: {influence}")
    print(f"   temperature = {climate.temperature}")
    print(f"   公式: 0.01 * temperature + 0.0")
    
    context = {'climate': climate}
    result = influence.apply(target, context)
    
    print(f"   计算结果: {result}")
    print(f"   death_rate_modifier = {target.death_rate_modifier}")
    
    assert abs(result - 0.35) < 0.001, f"Expected 0.35, got {result}"
    assert abs(target.death_rate_modifier - 0.35) < 0.001
    
    # 2. 测试 add 模式
    print("\n2. 测试 add 模式:")
    
    target.death_rate_modifier = 0.1  # 初始值
    
    influence2 = LinearInfluence(
        source='climate',
        target='population',
        name='temp_add',
        variable='climate.temperature',
        coefficient=0.01,
        constant=0.05,
        target_attr='death_rate_modifier',
        mode='add'
    )
    
    print(f"   初始值: {target.death_rate_modifier}")
    result2 = influence2.apply(target, context)
    print(f"   添加: 0.01 * 35 + 0.05 = {result2}")
    print(f"   最终值: {target.death_rate_modifier}")
    
    assert abs(target.death_rate_modifier - (0.1 + 0.35 + 0.05)) < 0.001
    
    # 3. 测试 multiply 模式
    print("\n3. 测试 multiply 模式:")
    
    target.growth_rate = 0.02
    
    influence3 = LinearInfluence(
        source='economy',
        target='population',
        name='gdp_growth',
        variable='economy.gdp',
        coefficient=0.0001,
        constant=1.0,
        target_attr='growth_rate',
        mode='multiply'
    )
    
    economy = MockModule(gdp=5000)
    context2 = {'economy': economy}
    
    print(f"   初始值: {target.growth_rate}")
    print(f"   乘数: 0.0001 * 5000 + 1.0 = 1.5")
    result3 = influence3.apply(target, context2)
    print(f"   最终值: {target.growth_rate}")
    
    assert abs(target.growth_rate - 0.03) < 0.001
    
    # 4. 测试嵌套属性访问
    print("\n4. 测试嵌套属性访问:")
    
    nested_obj = MockModule(
        level1=MockModule(
            level2=MockModule(
                value=100
            )
        )
    )
    
    influence4 = LinearInfluence(
        source='test',
        target='test',
        name='nested_test',
        variable='nested.level1.level2.value',
        coefficient=0.1,
        constant=5.0
    )
    
    context3 = {'nested': nested_obj}
    result4 = influence4.apply(None, context3)
    
    print(f"   嵌套值: nested.level1.level2.value = {nested_obj.level1.level2.value}")
    print(f"   计算: 0.1 * 100 + 5.0 = {result4}")
    
    assert abs(result4 - 15.0) < 0.001
    
    print("\n✓ LinearInfluence 测试通过")
    return True


def test_code_influence():
    """测试代码影响函数"""
    print("\n" + "=" * 60)
    print("测试 CodeInfluence")
    print("=" * 60)
    
    # 1. 测试简单计算
    print("\n1. 测试简单计算:")
    
    economy = MockModule(gdp=8000, unemployment_rate=0.1)
    towns = MockModule(satisfaction=0.0)
    
    code = """
# GDP影响基础满意度
base = min(1.0, gdp / 10000)
# 失业率降低满意度
unemployment_penalty = unemployment_rate * 0.5
# 最终满意度
result = max(0.0, base - unemployment_penalty)
"""
    
    influence = CodeInfluence(
        source='economy',
        target='towns',
        name='satisfaction_calc',
        code=code,
        target_attr='satisfaction',
        result_var='result'
    )
    
    print(f"   代码:\n{code}")
    
    context = {
        'economy': economy,
        'gdp': economy.gdp,
        'unemployment_rate': economy.unemployment_rate
    }
    
    result = influence.apply(towns, context)
    
    print(f"   计算结果: {result}")
    print(f"   towns.satisfaction = {towns.satisfaction}")
    
    expected = max(0.0, min(1.0, 8000/10000) - 0.1*0.5)
    assert abs(result - expected) < 0.001
    assert abs(towns.satisfaction - expected) < 0.001
    
    # 2. 测试数学函数
    print("\n2. 测试数学函数:")
    
    target2 = MockModule(value=0.0)
    
    code2 = """
# math 模块已经在命名空间中，可以直接使用
result = math.sqrt(25) + math.sin(0)
"""
    
    influence2 = CodeInfluence(
        source='test',
        target='test',
        name='math_test',
        code=code2,
        target_attr='value'
    )
    
    result2 = influence2.apply(target2, {})
    print(f"   sqrt(25) + sin(0) = {result2}")
    print(f"   target2.value = {target2.value}")
    
    assert abs(result2 - 5.0) < 0.001
    
    # 3. 测试条件逻辑
    print("\n3. 测试条件逻辑:")
    
    target3 = MockModule(status='')
    
    code3 = """
if temperature > 40:
    result = 'extreme'
elif temperature > 30:
    result = 'hot'
else:
    result = 'normal'
"""
    
    influence3 = CodeInfluence(
        source='climate',
        target='test',
        name='temp_status',
        code=code3,
        target_attr='status'
    )
    
    context3 = {'temperature': 35}
    result3 = influence3.apply(target3, context3)
    
    print(f"   temperature = 35")
    print(f"   status = {result3}")
    
    assert result3 == 'hot'
    assert target3.status == 'hot'
    
    # 4. 测试访问target对象
    print("\n4. 测试访问target对象:")
    
    target4 = MockModule(base_value=10, multiplier=2)
    
    code4 = """
# 可以访问target对象的属性
result = target.base_value * target.multiplier
"""
    
    influence4 = CodeInfluence(
        source='test',
        target='test',
        name='target_access',
        code=code4
    )
    
    result4 = influence4.apply(target4, {})
    print(f"   target.base_value = {target4.base_value}")
    print(f"   target.multiplier = {target4.multiplier}")
    print(f"   result = {result4}")
    
    assert result4 == 20
    
    # 5. 测试错误处理
    print("\n5. 测试错误处理:")
    
    code5 = """
# 访问不存在的变量
result = undefined_variable * 2
"""
    
    influence5 = CodeInfluence(
        source='test',
        target='test',
        name='error_test',
        code=code5
    )
    
    result5 = influence5.apply(target4, {})
    print(f"   错误代码执行结果: {result5}")
    assert result5 is None  # 应该返回None
    
    print("\n✓ CodeInfluence 测试通过")
    return True


def test_expr_influence():
    """测试 ExprInfluence：inputs + expr + 回写行为。"""
    print("\n" + "=" * 60)
    print("测试 ExprInfluence")
    print("=" * 60)

    target = MockModule(river_price=0.0, transport_cost=10.0, maintenance_cost_base=2.0)
    context = {
        'navigability': 0.8,
        'result': {},
    }

    inf = ExprInfluence(
        source='map',
        target='river_price',
        name='river_price_expr',
        inputs={
            'navigability': {'path': 'context.navigability', 'default': 0.8, 'coerce': 'float'},
            'transport_cost': {'path': 'target.transport_cost', 'default': 0.0, 'coerce': 'float'},
        },
        expr='max(round(transport_cost * (2 - navigability), 2), transport_cost)',
        target_attr='river_price',
    )

    result = inf.apply(target, context)
    assert abs(result - 12.0) < 1e-6
    assert abs(target.river_price - 12.0) < 1e-6

    inf2 = ExprInfluence(
        source='map',
        target='maintenance_cost',
        name='maintenance_cost_expr',
        inputs={
            'navigability': 'context.navigability',
            'exponent': {'value': 3, 'coerce': 'float'},
            'maintenance_cost_base': {'path': 'target.maintenance_cost_base', 'default': 0.0, 'coerce': 'float'},
        },
        expr='maintenance_cost_base * ((2 - navigability) ** exponent)',
        result_key='maintenance_cost',
    )

    result2 = inf2.apply(target, context)
    assert 'maintenance_cost' in context['result']
    assert abs(context['result']['maintenance_cost'] - result2) < 1e-9

    print("\n✓ ExprInfluence 测试通过")
    return True


def test_registry_integration():
    """测试与注册中心的集成"""
    print("\n" + "=" * 60)
    print("测试与 InfluenceRegistry 的集成")
    print("=" * 60)
    
    registry = InfluenceRegistry()
    
    # 测试从配置加载
    config = {
        'influences': [
            {
                'type': 'constant',
                'source': 'government',
                'target': 'population',
                'name': 'base_tax',
                'params': {
                    'target_attr': 'tax_rate',
                    'value': 0.15
                }
            },
            {
                'type': 'linear',
                'source': 'climate',
                'target': 'population',
                'name': 'temp_death',
                'params': {
                    'variable': 'climate.temperature',
                    'coefficient': 0.01,
                    'constant': 0.0,
                    'target_attr': 'death_modifier',
                    'mode': 'add'
                }
            },
            {
                'type': 'code',
                'source': 'economy',
                'target': 'towns',
                'name': 'satisfaction',
                'params': {
                    'code': 'result = min(1.0, gdp / 10000)',
                    'target_attr': 'satisfaction'
                }
            },
            {
                'type': 'expr',
                'source': {
                    'module': 'economy',
                    'inputs': {
                        'gdp': {'path': 'context.gdp', 'default': 0.0, 'coerce': 'float'}
                    }
                },
                'target': 'population',
                'name': 'gdp_factor',
                'params': {
                    'expr': 'gdp / 10000',
                    'target_attr': 'gdp_factor'
                }
            }
        ]
    }
    
    print("\n加载配置:")
    loaded = registry.load_from_config(config)
    print(f"   成功加载 {loaded} 个影响函数")
    
    assert loaded == 4
    
    # 验证影响函数
    print("\n验证加载的影响函数:")
    
    const_inf = registry.get_influence_by_name('government', 'population', 'base_tax')
    assert const_inf is not None
    assert isinstance(const_inf, ConstantInfluence)
    print(f"   ✓ ConstantInfluence: {const_inf}")
    
    linear_inf = registry.get_influence_by_name('climate', 'population', 'temp_death')
    assert linear_inf is not None
    assert isinstance(linear_inf, LinearInfluence)
    print(f"   ✓ LinearInfluence: {linear_inf}")
    
    code_inf = registry.get_influence_by_name('economy', 'towns', 'satisfaction')
    assert code_inf is not None
    assert isinstance(code_inf, CodeInfluence)
    print(f"   ✓ CodeInfluence: {code_inf}")

    expr_inf = registry.get_influence_by_name('economy', 'population', 'gdp_factor')
    assert expr_inf is not None
    assert isinstance(expr_inf, ExprInfluence)
    print(f"   ✓ ExprInfluence: {expr_inf}")
    
    # 测试应用
    print("\n测试应用影响:")
    
    population = MockModule(tax_rate=0.0, death_modifier=0.0, gdp_factor=0.0)
    climate = MockModule(temperature=30)
    context = {
        'climate': climate,
        'population': population,
        'gdp': 8000,
    }
    
    # 应用所有影响到 population
    for influence in registry.get_influences('population'):
        result = influence.apply(population, context)
        print(f"   {influence.name}: {result}")
    
    print(f"\n   最终状态:")
    print(f"   - tax_rate: {population.tax_rate}")
    print(f"   - death_modifier: {population.death_modifier}")
    
    assert population.tax_rate == 0.15
    assert abs(population.death_modifier - 0.30) < 0.001
    assert abs(population.gdp_factor - 0.8) < 0.001
    
    print("\n✓ 注册中心集成测试通过")
    return True


if __name__ == "__main__":
    try:
        test_constant_influence()
        test_linear_influence()
        test_code_influence()
        test_expr_influence()
        test_registry_integration()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
