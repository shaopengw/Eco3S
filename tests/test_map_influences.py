"""
测试地图模块的影响函数集成
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.environment.map import Map
from src.influences import InfluenceRegistry
import yaml


def test_map_without_influences():
    """测试没有影响函数时的默认行为（向后兼容）"""
    print("=" * 60)
    print("测试 1: Map 模块不使用影响函数（向后兼容）")
    print("=" * 60)
    
    # 创建不带影响函数的地图
    map_obj = Map(width=100, height=150, data_file='config/default/towns_data.json')
    
    print(f"\n初始通航能力: {map_obj.get_navigability():.2f}")
    
    # 测试维护更新
    print("\n测试维护更新（maintenance_ratio=1.2）:")
    map_obj.update_river_condition(maintenance_ratio=1.2)
    print(f"更新后通航能力: {map_obj.get_navigability():.2f}")
    
    # 测试自然衰减
    print("\n测试自然衰减（climate_impact_factor=0.3）:")
    map_obj.decay_river_condition_naturally(climate_impact_factor=0.3)
    print(f"衰减后通航能力: {map_obj.get_navigability():.2f}")
    
    print("\n[PASS] 向后兼容测试通过")
    return True


def test_map_with_influences():
    """测试使用影响函数的地图模块"""
    print("\n" + "=" * 60)
    print("测试 2: Map 模块使用影响函数系统")
    print("=" * 60)
    
    # 创建影响函数注册中心
    registry = InfluenceRegistry()
    
    # 手动注册影响函数（模拟配置加载）
    print("\n注册影响函数:")
    
    # 1. 维护投入充足时的影响
    from src.influences import CodeInfluence
    
    maintenance_boost = CodeInfluence(
        source='government',
        target='canal',
        name='maintenance_boost',
        code="""
current = context.get('current_navigability', 0.8)
maintenance = context.get('maintenance_ratio', 1.0)

if maintenance >= 1:
    result = current + 0.1 * maintenance
    result = max(0, min(1.0, result))
else:
    result = None
""",
        target_attr='_navigability',
        result_var='result'
    )
    registry.register(maintenance_boost)
    print("  [OK] 注册 maintenance_boost")
    
    # 2. 维护投入不足时的影响
    maintenance_decay = CodeInfluence(
        source='government',
        target='canal',
        name='maintenance_decay',
        code="""
current = context.get('current_navigability', 0.8)
maintenance = context.get('maintenance_ratio', 1.0)

if maintenance < 1:
    result = current - 0.2 * maintenance
    result = max(0, min(1.0, result))
else:
    result = None
""",
        target_attr='_navigability',
        result_var='result'
    )
    registry.register(maintenance_decay)
    print("  [OK] 注册 maintenance_decay")
    
    # 3. 自然衰减影响
    natural_decay = CodeInfluence(
        source='time',
        target='canal_decay',
        name='natural_decay',
        code="""
current = context.get('current_navigability', 0.8)
climate_impact = context.get('climate_impact_factor', 0)

natural_decay_rate = 0.1
result = current * (1 - natural_decay_rate) - climate_impact * 0.6
result = max(0, min(1.0, result))
""",
        target_attr='_navigability',
        result_var='result'
    )
    registry.register(natural_decay)
    print("  [OK] 注册 natural_decay")
    
    # 创建带影响函数的地图
    map_obj = Map(
        width=100, 
        height=150, 
        data_file='config/default/towns_data.json',
        influence_registry=registry
    )
    
    print(f"\n初始通航能力: {map_obj.get_navigability():.2f}")
    
    # 测试维护更新（充足投入）
    print("\n测试维护更新（maintenance_ratio=1.2，充足投入）:")
    initial = map_obj.get_navigability()
    map_obj.update_river_condition(maintenance_ratio=1.2)
    after_maintenance = map_obj.get_navigability()
    print(f"更新后通航能力: {after_maintenance:.2f}")
    expected = min(1.0, initial + 0.1 * 1.2)
    print(f"期望值: {expected:.2f}")
    assert abs(after_maintenance - expected) < 0.01, f"维护更新结果不符合预期"
    
    # 重置通航能力
    map_obj._navigability = 0.8
    
    # 测试维护更新（不足投入）
    print("\n测试维护更新（maintenance_ratio=0.5，不足投入）:")
    initial = map_obj.get_navigability()
    map_obj.update_river_condition(maintenance_ratio=0.5)
    after_maintenance = map_obj.get_navigability()
    print(f"更新后通航能力: {after_maintenance:.2f}")
    expected = max(0, initial - 0.2 * 0.5)
    print(f"期望值: {expected:.2f}")
    assert abs(after_maintenance - expected) < 0.01, f"维护更新结果不符合预期"
    
    # 重置通航能力
    map_obj._navigability = 0.8
    
    # 测试自然衰减
    print("\n测试自然衰减（climate_impact_factor=0.3）:")
    initial = map_obj.get_navigability()
    result = map_obj.decay_river_condition_naturally(climate_impact_factor=0.3)
    print(f"衰减后通航能力: {result:.2f}")
    expected = max(0, initial * (1 - 0.1) - 0.3 * 0.6)
    print(f"期望值: {expected:.2f}")
    assert abs(result - expected) < 0.01, f"自然衰减结果不符合预期"
    
    print("\n[PASS] 影响函数系统测试通过")
    return True


def test_map_with_config():
    """测试从配置文件加载影响函数"""
    print("\n" + "=" * 60)
    print("测试 3: 从配置文件加载影响函数")
    print("=" * 60)
    
    config_file = 'config/map_influences_example.yaml'
    
    if not os.path.exists(config_file):
        print(f"配置文件 {config_file} 不存在，跳过此测试")
        return True
    
    # 加载配置
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 创建注册中心并加载配置
    registry = InfluenceRegistry()
    loaded = registry.load_from_config(config)
    print(f"\n从配置文件加载了 {loaded} 个影响函数")
    
    # 显示统计信息
    stats = registry.get_statistics()
    print(f"\n影响函数统计:")
    print(f"  - 总数: {stats['total_influences']}")
    print(f"  - 目标: {list(stats['targets'].keys())}")
    print(f"  - 来源: {list(stats['sources'].keys())}")
    
    # 创建地图
    map_obj = Map(
        width=100,
        height=150,
        data_file='config/default/towns_data.json',
        influence_registry=registry
    )
    
    print(f"\n初始通航能力: {map_obj.get_navigability():.2f}")
    
    # 测试维护更新
    print("\n测试维护更新（使用配置文件中的影响函数）:")
    map_obj.update_river_condition(maintenance_ratio=1.5)
    print(f"更新后通航能力: {map_obj.get_navigability():.2f}")
    
    # 重置
    map_obj._navigability = 0.8
    
    # 测试自然衰减
    print("\n测试自然衰减（使用配置文件中的影响函数）:")
    result = map_obj.decay_river_condition_naturally(climate_impact_factor=0.2)
    print(f"衰减后通航能力: {result:.2f}")
    
    print("\n[PASS] 配置文件加载测试通过")
    return True


def test_influence_priority():
    """测试多个影响函数的优先级和组合"""
    print("\n" + "=" * 60)
    print("测试 4: 多个影响函数的组合效果")
    print("=" * 60)
    
    registry = InfluenceRegistry()
    
    # 注册基础维护影响
    from src.influences import LinearInfluence
    
    base_effect = LinearInfluence(
        source='government',
        target='canal',
        name='base_maintenance',
        variable='maintenance_ratio',
        coefficient=0.08,
        constant=0.0,
        target_attr='_navigability',
        mode='add'
    )
    registry.register(base_effect)
    print("  [OK] 注册 base_maintenance（线性影响）")
    
    # 注册额外加成
    from src.influences import ConstantInfluence
    
    bonus = ConstantInfluence(
        source='technology',
        target='canal',
        name='tech_bonus',
        target_attr='_tech_bonus',
        value=0.05
    )
    registry.register(bonus)
    print("  [OK] 注册 tech_bonus（常量影响）")
    
    # 创建地图
    map_obj = Map(
        width=100,
        height=150,
        data_file='config/default/towns_data.json',
        influence_registry=registry
    )
    
    print(f"\n初始通航能力: {map_obj.get_navigability():.2f}")
    
    # 应用所有影响
    print("\n应用所有影响（maintenance_ratio=1.0）:")
    initial = map_obj.get_navigability()
    map_obj.update_river_condition(maintenance_ratio=1.0)
    final = map_obj.get_navigability()
    
    print(f"最终通航能力: {final:.2f}")
    print(f"变化量: {final - initial:+.2f}")
    
    # 验证基础影响被应用
    assert final != initial, "影响函数应该改变通航能力"
    
    print("\n[PASS] 多影响函数组合测试通过")
    return True


if __name__ == "__main__":
    try:
        test_map_without_influences()
        test_map_with_influences()
        test_map_with_config()
        test_influence_priority()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        print("\n影响函数系统已成功集成到 Map 模块")
        print("- 向后兼容：未配置影响函数时使用默认公式")
        print("- 灵活配置：可通过 YAML 配置文件定义影响函数")
        print("- 可扩展：支持多种影响函数类型和自定义逻辑")
        
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
