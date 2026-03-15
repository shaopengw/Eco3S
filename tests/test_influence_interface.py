"""
测试影响函数接口 (Test Influence Function Interface)
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.influences import IInfluenceFunction


class TestInfluence(IInfluenceFunction):
    """测试用的具体影响函数实现"""
    
    def __init__(self):
        super().__init__(
            source="climate",
            target="population",
            name="test_influence",
            description="这是一个测试影响函数"
        )
    
    def apply(self, target_obj, context: dict):
        """
        测试实现：计算气候对人口的影响
        """
        # 验证上下文
        self.validate_context(context, ['climate', 'time'])
        
        climate = context['climate']
        time = context['time']
        
        # 模拟计算影响
        impact = {
            'death_rate': 0.01,
            'migration_rate': 0.05,
            'timestamp': time
        }
        
        return impact


def test_influence_function():
    """测试影响函数接口"""
    print("=" * 60)
    print("测试影响函数接口")
    print("=" * 60)
    
    # 创建测试影响函数
    influence = TestInfluence()
    
    # 测试属性
    print(f"\n1. 测试属性:")
    print(f"   source: {influence.source}")
    print(f"   target: {influence.target}")
    print(f"   name: {influence.name}")
    print(f"   description: {influence.description}")
    
    assert influence.source == "climate", "source 属性测试失败"
    assert influence.target == "population", "target 属性测试失败"
    assert influence.name == "test_influence", "name 属性测试失败"
    print("   ✓ 所有属性测试通过")
    
    # 测试 apply 方法
    print(f"\n2. 测试 apply 方法:")
    
    # 创建模拟上下文
    mock_climate = type('MockClimate', (), {'is_extreme': lambda: True})()
    mock_time = "2024-01-01"
    
    context = {
        'climate': mock_climate,
        'time': mock_time,
        'population': None
    }
    
    target_obj = None  # 目标对象（在这个测试中不使用）
    
    try:
        result = influence.apply(target_obj, context)
        print(f"   影响结果: {result}")
        assert isinstance(result, dict), "返回结果应该是字典"
        assert 'death_rate' in result, "结果应包含 death_rate"
        assert 'migration_rate' in result, "结果应包含 migration_rate"
        print("   ✓ apply 方法测试通过")
    except Exception as e:
        print(f"   ✗ apply 方法测试失败: {e}")
        return False
    
    # 测试上下文验证
    print(f"\n3. 测试上下文验证:")
    
    invalid_context = {'climate': mock_climate}  # 缺少 'time'
    
    try:
        influence.apply(target_obj, invalid_context)
        print("   ✗ 应该抛出 ValueError")
        return False
    except ValueError as e:
        print(f"   ✓ 正确抛出 ValueError: {e}")
    
    # 测试字符串表示
    print(f"\n4. 测试字符串表示:")
    print(f"   str(influence): {str(influence)}")
    print(f"   repr(influence): {repr(influence)}")
    
    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_influence_function()
    sys.exit(0 if success else 1)
