"""
测试影响函数注册中心 (Test Influence Registry)
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.influences import (
    IInfluenceFunction,
    InfluenceRegistry,
    LinearMultiplierInfluence,
    ThresholdInfluence,
    ConditionalInfluence
)


class TestInfluence(IInfluenceFunction):
    """测试用的简单影响函数"""
    
    def __init__(self, source: str, target: str, name: str):
        super().__init__(source, target, name, "测试影响函数")
    
    def apply(self, target_obj, context: dict):
        return 42


def test_influence_registry():
    """测试影响函数注册中心"""
    print("=" * 60)
    print("测试影响函数注册中心")
    print("=" * 60)
    
    # 创建注册中心
    registry = InfluenceRegistry()
    print("\n1. 创建 InfluenceRegistry")
    print(f"   {registry}")
    
    # 测试注册影响函数
    print("\n2. 测试注册影响函数:")
    
    influence1 = TestInfluence('climate', 'population', 'test1')
    influence2 = TestInfluence('climate', 'towns', 'test2')
    influence3 = TestInfluence('transport', 'towns', 'test3')
    
    registry.register(influence1)
    registry.register(influence2)
    registry.register(influence3)
    
    print(f"   已注册 3 个影响函数")
    print(f"   注册中心状态: {registry}")
    
    # 测试按目标查询
    print("\n3. 测试按目标查询:")
    
    pop_influences = registry.get_influences('population')
    print(f"   影响 'population' 的函数: {len(pop_influences)} 个")
    assert len(pop_influences) == 1
    assert pop_influences[0].name == 'test1'
    
    towns_influences = registry.get_influences('towns')
    print(f"   影响 'towns' 的函数: {len(towns_influences)} 个")
    assert len(towns_influences) == 2
    
    # 测试按源查询
    print("\n4. 测试按源查询:")
    
    climate_influences = registry.get_influences_by_source('climate')
    print(f"   来自 'climate' 的函数: {len(climate_influences)} 个")
    assert len(climate_influences) == 2
    
    # 测试按名称查询
    print("\n5. 测试按名称查询:")
    
    found = registry.get_influence_by_name('climate', 'population', 'test1')
    print(f"   查找 climate->population:test1: {'找到' if found else '未找到'}")
    assert found is not None
    assert found.name == 'test1'
    
    # 测试统计信息
    print("\n6. 测试统计信息:")
    
    stats = registry.get_statistics()
    print(f"   总影响函数数: {stats['total_influences']}")
    print(f"   目标模块: {list(stats['targets'].keys())}")
    print(f"   源模块: {list(stats['sources'].keys())}")
    print(f"   可用类型: {stats['registered_types']}")
    
    assert stats['total_influences'] == 3
    
    # 测试从配置加载
    print("\n7. 测试从配置加载:")
    
    config = {
        'influences': [
            {
                'type': 'linear_multiplier',
                'source': 'climate',
                'target': 'population',
                'name': 'temperature_death',
                'params': {
                    'multiplier': 0.01,
                    'source_key': 'temperature'
                }
            },
            {
                'type': 'threshold',
                'source': 'economy',
                'target': 'towns',
                'name': 'gdp_growth',
                'params': {
                    'threshold': 1000,
                    'impact_value': 0.05,
                    'source_key': 'gdp',
                    'compare_op': 'gt'
                }
            }
        ]
    }
    
    loaded_count = registry.load_from_config(config)
    print(f"   从配置加载了 {loaded_count} 个影响函数")
    assert loaded_count == 2
    
    # 验证加载的影响函数
    print("\n8. 验证加载的影响函数:")
    
    temp_death = registry.get_influence_by_name('climate', 'population', 'temperature_death')
    assert temp_death is not None
    assert isinstance(temp_death, LinearMultiplierInfluence)
    print(f"   ✓ LinearMultiplierInfluence 加载成功")
    
    gdp_growth = registry.get_influence_by_name('economy', 'towns', 'gdp_growth')
    assert gdp_growth is not None
    assert isinstance(gdp_growth, ThresholdInfluence)
    print(f"   ✓ ThresholdInfluence 加载成功")
    
    # 测试取消注册
    print("\n9. 测试取消注册:")
    
    success = registry.unregister('climate', 'population', 'test1')
    print(f"   取消注册 climate->population:test1: {'成功' if success else '失败'}")
    assert success
    
    pop_influences = registry.get_influences('population')
    print(f"   现在影响 'population' 的函数: {len(pop_influences)} 个")
    assert len(pop_influences) == 1  # 只剩 temperature_death
    
    # 测试清空
    print("\n10. 测试清空注册中心:")
    
    before_count = len(registry.get_all_influences())
    registry.clear()
    after_count = len(registry.get_all_influences())
    
    print(f"   清空前: {before_count} 个")
    print(f"   清空后: {after_count} 个")
    assert after_count == 0
    
    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)
    return True


def test_builtin_influences():
    """测试内置影响函数"""
    print("\n" + "=" * 60)
    print("测试内置影响函数")
    print("=" * 60)
    
    # 测试 LinearMultiplierInfluence
    print("\n1. 测试 LinearMultiplierInfluence:")
    
    influence = LinearMultiplierInfluence(
        source='climate',
        target='population',
        name='temp_impact',
        multiplier=0.01,
        source_key='temperature'
    )
    
    context = {
        'climate': type('Climate', (), {'temperature': 35})()
    }
    
    result = influence.apply(None, context)
    print(f"   温度 35°C * 0.01 = {result}")
    assert abs(result - 0.35) < 0.001  # 浮点数精度问题
    print(f"   ✓ LinearMultiplierInfluence 测试通过")
    
    # 测试 ThresholdInfluence
    print("\n2. 测试 ThresholdInfluence:")
    
    influence = ThresholdInfluence(
        source='economy',
        target='towns',
        name='gdp_threshold',
        threshold=1000,
        impact_value='high_growth',
        source_key='gdp',
        compare_op='gt'
    )
    
    # 测试超过阈值的情况
    context1 = {
        'economy': type('Economy', (), {'gdp': 1500})()
    }
    result1 = influence.apply(None, context1)
    print(f"   GDP 1500 > 1000: {result1}")
    assert result1 == 'high_growth'
    
    # 测试未超过阈值的情况
    context2 = {
        'economy': type('Economy', (), {'gdp': 800})()
    }
    result2 = influence.apply(None, context2)
    print(f"   GDP 800 > 1000: {result2}")
    assert result2 is None
    print(f"   ✓ ThresholdInfluence 测试通过")
    
    # 测试 ConditionalInfluence
    print("\n3. 测试 ConditionalInfluence:")
    
    influence = ConditionalInfluence(
        source='time',
        target='agriculture',
        name='seasonal_bonus',
        conditions={
            'time.season': 'spring',
            'climate.rainfall': 'adequate'
        },
        impact_value=1.2
    )
    
    # 测试条件满足的情况
    context1 = {
        'time': type('Time', (), {'season': 'spring'})(),
        'climate': type('Climate', (), {'rainfall': 'adequate'})()
    }
    result1 = influence.apply(None, context1)
    print(f"   春季且降雨充足: {result1}")
    assert result1 == 1.2
    
    # 测试条件不满足的情况
    context2 = {
        'time': type('Time', (), {'season': 'winter'})(),
        'climate': type('Climate', (), {'rainfall': 'adequate'})()
    }
    result2 = influence.apply(None, context2)
    print(f"   冬季且降雨充足: {result2}")
    assert result2 is None
    print(f"   ✓ ConditionalInfluence 测试通过")
    
    print("\n" + "=" * 60)
    print("内置影响函数测试通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success1 = test_influence_registry()
    success2 = test_builtin_influences()
    sys.exit(0 if (success1 and success2) else 1)
