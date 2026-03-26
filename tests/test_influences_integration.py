"""
测试影响函数系统集成
验证配置文件加载和模块初始化是否正常工作
"""

import os
import sys
import yaml
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.influences import InfluenceRegistry
from src.utils.di_helpers import setup_container_for_simulation

def test_influences_loading():
    """测试影响函数配置加载"""
    print("=" * 60)
    print("测试 1: 影响函数配置加载")
    print("=" * 60)
    
    # 初始化 InfluenceRegistry
    influence_registry = InfluenceRegistry(logger=logging.getLogger('test_influences'))
    
    # 加载配置
    config_path = 'config/default/influences.yaml'
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            influences_config = yaml.safe_load(f)
        
        loaded_count = influence_registry.load_from_config(influences_config)
        print(f"✓ 成功加载 {loaded_count} 个影响函数")
        
        # 获取统计信息
        stats = influence_registry.get_statistics()
        print(f"\n统计信息:")
        print(f"  - 总影响函数数量: {stats['total_influences']}")
        print(f"  - 影响的目标模块: {list(stats['targets'].keys())}")
        
        for target, count in stats['targets'].items():
            print(f"    * {target}: {count} 个影响函数")
        
        return True
        
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_container_with_influences():
    """测试 DIContainer 与影响函数集成（简化版）。

    当前架构下：核心模块由插件系统创建；DIContainer 只负责在插件构造期提供共享服务。
    这里验证 InfluenceRegistry 能被注册并通过容器获取。
    """
    print("\n" + "=" * 60)
    print("测试 2: DIContainer 与影响函数集成")
    print("=" * 60)
    
    try:
        # 加载模拟配置
        sim_config_path = 'config/default/simulation_config.yaml'
        with open(sim_config_path, 'r', encoding='utf-8') as f:
            sim_config = yaml.safe_load(f)
        
        # 初始化 InfluenceRegistry
        influence_registry = InfluenceRegistry(logger=logging.getLogger('test_container'))
        
        # 加载影响函数配置
        influences_config_path = 'config/default/influences.yaml'
        with open(influences_config_path, 'r', encoding='utf-8') as f:
            influences_config = yaml.safe_load(f)
        
        loaded_count = influence_registry.load_from_config(influences_config)
        print(f"✓ 加载了 {loaded_count} 个影响函数")
        
        # 设置容器
        modules_config_path = 'config/default/modules_config.yaml'
        container = setup_container_for_simulation(influence_registry)
        print("✓ 成功创建 DIContainer")
        
        # 验证 InfluenceRegistry 能从容器获取
        reg2 = container.get(InfluenceRegistry)
        ok = reg2 is influence_registry
        print("\n共享服务测试:")
        print(f"  - InfluenceRegistry 注册成功: {ok}")

        return ok
        
    except Exception as e:
        print(f"❌ 容器集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_influence_functions():
    """测试影响函数是否可查询"""
    print("\n" + "=" * 60)
    print("测试 3: 影响函数查询")
    print("=" * 60)
    
    try:
        # 初始化并加载
        influence_registry = InfluenceRegistry(logger=logging.getLogger('test_query'))
        
        with open('config/default/influences.yaml', 'r', encoding='utf-8') as f:
            influences_config = yaml.safe_load(f)
        
        influence_registry.load_from_config(influences_config)
        
        # 测试查询
        targets_to_test = ['canal_condition', 'river_price', 'birth_rate', 'climate_impact', 'tax_rate']
        
        for target in targets_to_test:
            influences = influence_registry.get_influences(target)
            print(f"\n  {target}: {len(influences)} 个影响函数")
            for inf in influences:
                print(f"    - {inf.name} ({inf.source} -> {inf.target})")
        
        return True
        
    except Exception as e:
        print(f"❌ 影响函数查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "影响函数系统集成测试" + " " * 26 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    results = []
    
    # 测试 1: 配置加载
    results.append(("配置加载", test_influences_loading()))
    
    # 测试 2: 容器集成
    results.append(("容器集成", test_container_with_influences()))
    
    # 测试 3: 影响函数查询
    results.append(("影响函数查询", test_influence_functions()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！影响函数系统集成成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit(main())
