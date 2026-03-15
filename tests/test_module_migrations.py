"""
测试所有迁移到影响函数系统的模块
包括：TransportEconomy, Population, ClimateSystem, Resident, Government
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.environment.transport_economy import TransportEconomy
from src.environment.population import Population
from src.environment.climate import ClimateSystem
from src.agents.resident import Resident
from src.agents.government import Government
from src.influences import InfluenceRegistry
from src.influences.builtin import create_code_influence


def test_transport_economy_without_influences():
    """测试 TransportEconomy 向后兼容性（不使用影响函数）"""
    print("\n" + "="*60)
    print("Test 1: TransportEconomy - Backward Compatibility")
    print("="*60)
    
    # 创建不带影响函数的运输经济对象
    transport = TransportEconomy(
        transport_cost=100,
        transport_task=5000,
        maintenance_cost_base=200
    )
    
    # 测试河运价格计算
    print(f"\nInitial river price: {transport.river_price}")
    
    # 通航能力为 0.8
    river_price = transport.calculate_river_price(navigability=0.8)
    expected_price = 100 * (2 - 0.8)  # 120
    print(f"River price (navigability=0.8): {river_price}")
    print(f"Expected: {expected_price}")
    assert abs(river_price - expected_price) < 0.01, "River price calculation failed"
    print("[OK] River price calculation works")
    
    # 测试维护成本计算
    maintenance_cost = transport.calculate_maintenance_cost(navigability=0.8)
    expected_cost = 200 * ((2 - 0.8) ** 3)  # 200 * 1.728 = 345.6
    print(f"\nMaintenance cost (navigability=0.8): {maintenance_cost}")
    print(f"Expected: {expected_cost:.2f}")
    assert abs(maintenance_cost - expected_cost) < 0.1, "Maintenance cost calculation failed"
    print("[OK] Maintenance cost calculation works")
    
    # 测试总运输成本计算
    total_cost = transport.calculate_total_transport_cost(river_ratio=0.6)
    river_cost_calc = river_price * 0.6 * 5000
    sea_cost_calc = transport.sea_price * 0.4 * 5000
    expected_total = river_cost_calc + sea_cost_calc
    print(f"\nTotal transport cost (river_ratio=0.6): {total_cost}")
    print(f"Expected: {expected_total}")
    assert abs(total_cost - expected_total) < 0.1, "Total cost calculation failed"
    print("[OK] Total cost calculation works")
    
    print("\n[PASS] Test 1: TransportEconomy backward compatibility verified")


def test_transport_economy_with_influences():
    """测试 TransportEconomy 使用影响函数"""
    print("\n" + "="*60)
    print("Test 2: TransportEconomy - With Influence Functions")
    print("="*60)
    
    # 创建注册表并注册影响函数
    registry = InfluenceRegistry()
    
    # 注册河运价格影响函数
    river_price_config = {
        'name': 'custom_river_price',
        'type': 'code',
        'source': 'navigability',
        'target': 'river_price',
        'params': {
            'target_attr': '_river_price',
            'code': """
transport_economy = context['transport_economy']
navigability = context['navigability']
transport_cost = context['transport_cost']

# 自定义公式：价格与通航能力非线性关系
if navigability >= 0.8:
    price = transport_cost
elif navigability < 0.5:
    price = transport_cost * 2.5
else:
    price = transport_cost * (2.2 - navigability * 0.4)

transport_economy._river_price = round(price, 2)
"""
        }
    }
    river_price_influence = create_code_influence(river_price_config)
    registry.register(river_price_influence)
    
    # 创建带影响函数的运输经济对象
    transport = TransportEconomy(
        transport_cost=100,
        transport_task=5000,
        maintenance_cost_base=200,
        influence_registry=registry
    )
    
    # 测试高通航能力（应该使用基础价格）
    price_high = transport.calculate_river_price(navigability=0.9)
    print(f"\nRiver price (navigability=0.9): {price_high}")
    assert price_high == 100, "High navigability price should be base cost"
    print("[OK] High navigability pricing works")
    
    # 测试低通航能力（应该大幅增加）
    price_low = transport.calculate_river_price(navigability=0.3)
    print(f"River price (navigability=0.3): {price_low}")
    assert price_low > 200, "Low navigability should significantly increase price"
    print("[OK] Low navigability pricing works")
    
    print("\n[PASS] Test 2: TransportEconomy with influences verified")


def test_population_without_influences():
    """测试 Population 向后兼容性（不使用影响函数）"""
    print("\n" + "="*60)
    print("Test 3: Population - Backward Compatibility")
    print("="*60)
    
    # 创建不带影响函数的人口对象
    pop = Population(initial_population=1000, birth_rate=0.02)
    
    print(f"\nInitial population: {pop.population}")
    print(f"Initial birth rate: {pop.birth_rate}")
    
    # 测试高满意度（应增加出生率）
    pop.update_birth_rate(satisfaction=85)
    expected_rate = 0.02 + (85 - 80) * 0.002  # 0.02 + 0.01 = 0.03
    print(f"\nBirth rate after high satisfaction (85): {pop.birth_rate}")
    print(f"Expected: {expected_rate}")
    assert abs(pop.birth_rate - expected_rate) < 0.001, "High satisfaction birth rate failed"
    print("[OK] High satisfaction birth rate works")
    
    # 重置并测试低满意度（应降低出生率）
    pop.birth_rate = 0.02
    pop.update_birth_rate(satisfaction=40)
    expected_rate = 0.02 - (50 - 40) * 0.001  # 0.02 - 0.01 = 0.01
    print(f"\nBirth rate after low satisfaction (40): {pop.birth_rate}")
    print(f"Expected: {expected_rate}")
    assert abs(pop.birth_rate - expected_rate) < 0.001, "Low satisfaction birth rate failed"
    print("[OK] Low satisfaction birth rate works")
    
    # 测试中等满意度（应保持不变）
    pop.birth_rate = 0.02
    pop.update_birth_rate(satisfaction=65)
    print(f"\nBirth rate after medium satisfaction (65): {pop.birth_rate}")
    assert pop.birth_rate == 0.02, "Medium satisfaction should keep birth rate unchanged"
    print("[OK] Medium satisfaction birth rate works")
    
    print("\n[PASS] Test 3: Population backward compatibility verified")


def test_population_with_influences():
    """测试 Population 使用影响函数"""
    print("\n" + "="*60)
    print("Test 4: Population - With Influence Functions")
    print("="*60)
    
    # 创建注册表并注册影响函数
    registry = InfluenceRegistry()
    
    # 注册自定义出生率影响函数（考虑经济繁荣）
    birth_rate_config = {
        'name': 'custom_birth_rate',
        'type': 'code',
        'source': 'satisfaction',
        'target': 'birth_rate',
        'params': {
            'target_attr': '_birth_rate',
            'code': """
population = context['population']
satisfaction = context['satisfaction']
economic_prosperity = context.get('economic_prosperity', 50)

# 基础出生率调整
if satisfaction >= 80:
    rate = 0.02 + (satisfaction - 80) * 0.002
elif satisfaction <= 50:
    rate = 0.02 - (50 - satisfaction) * 0.001
else:
    rate = 0.02

# 经济繁荣额外奖励
if economic_prosperity > 80:
    rate += 0.01

population._birth_rate = max(0.01, min(0.5, rate))
"""
        }
    }
    birth_rate_influence = create_code_influence(birth_rate_config)
    registry.register(birth_rate_influence)
    
    # 创建带影响函数的人口对象
    pop = Population(
        initial_population=1000,
        birth_rate=0.02,
        influence_registry=registry
    )
    
    # 测试高满意度 + 高经济繁荣
    pop._birth_rate = 0.02
    
    # 手动构建完整上下文并应用
    full_context = {
        'population': pop,
        'satisfaction': 85,
        'current_birth_rate': pop.birth_rate,
        'population_size': pop.population,
        'economic_prosperity': 90
    }
    pop.apply_influences('birth_rate', full_context)
    
    print(f"\nBirth rate with high satisfaction (85) and prosperity (90): {pop.birth_rate}")
    # 应该是 0.02 + 0.01 (satisfaction bonus) + 0.01 (economy bonus) = 0.04
    assert pop.birth_rate > 0.03, "Economic prosperity should boost birth rate"
    print("[OK] Economic prosperity boost works")
    
    print("\n[PASS] Test 4: Population with influences verified")


def test_climate_without_influences():
    """测试 ClimateSystem 向后兼容性（不使用影响函数）"""
    print("\n" + "="*60)
    print("Test 5: ClimateSystem - Backward Compatibility")
    print("="*60)
    
    # 创建临时测试数据文件
    test_data_path = 'test_climate_data.csv'
    with open(test_data_path, 'w') as f:
        # 写入10年的气候数据
        f.write(','.join([str(i * 0.1) for i in range(10)]))
    
    try:
        # 创建不带影响函数的气候系统
        climate = ClimateSystem(climate_data_path=test_data_path)
        
        print(f"\nClimate data loaded: {len(climate.climate_data)} years")
        
        # 测试获取第5年的气候影响
        impact = climate.get_current_impact(current_year=2005, start_year=2000)
        expected_impact = abs(climate.climate_data[5])  # 0.5
        print(f"\nClimate impact (year 5): {impact}")
        print(f"Expected: {expected_impact}")
        assert abs(impact - expected_impact) < 0.01, "Climate impact retrieval failed"
        print("[OK] Climate impact retrieval works")
        
        # 测试超出范围
        impact_out = climate.get_current_impact(current_year=2050, start_year=2000)
        print(f"\nClimate impact (out of range): {impact_out}")
        assert impact_out == 0.0, "Out of range should return 0"
        print("[OK] Out of range handling works")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_data_path):
            os.remove(test_data_path)
    
    print("\n[PASS] Test 5: ClimateSystem backward compatibility verified")


def test_climate_with_influences():
    """测试 ClimateSystem 使用影响函数"""
    print("\n" + "="*60)
    print("Test 6: ClimateSystem - With Influence Functions")
    print("="*60)
    
    # 创建临时测试数据文件
    test_data_path = 'test_climate_data.csv'
    with open(test_data_path, 'w') as f:
        # 写入10年的气候数据
        f.write(','.join([str(i * 0.1) for i in range(10)]))
    
    try:
        # 创建注册表并注册影响函数
        registry = InfluenceRegistry()
        
        # 注册极端事件放大器
        extreme_config = {
            'name': 'extreme_amplifier',
            'type': 'code',
            'source': 'climate_data',
            'target': 'climate_impact',
            'params': {
                'code': """
raw_impact = context['raw_impact']
result = context['result']

# 放大高影响事件
if raw_impact > 0.7:
    result['climate_impact'] = raw_impact * 1.5
elif raw_impact > 0.5:
    result['climate_impact'] = raw_impact * 1.2
"""
            }
        }
        extreme_amplifier = create_code_influence(extreme_config)
        registry.register(extreme_amplifier)
        
        # 创建带影响函数的气候系统
        climate = ClimateSystem(
            climate_data_path=test_data_path,
            influence_registry=registry
        )
        
        # 测试中等影响（应该放大1.2倍）
        impact_medium = climate.get_current_impact(current_year=2006, start_year=2000)
        raw_val = abs(climate.climate_data[6])  # 0.6
        expected = raw_val * 1.2  # 0.72
        print(f"\nClimate impact with amplifier (year 6, raw=0.6): {impact_medium}")
        print(f"Expected (1.2x amplification): {expected}")
        assert abs(impact_medium - expected) < 0.01, "Medium impact amplification failed"
        print("[OK] Medium impact amplification works")
        
        # 测试高影响（应该放大1.5倍）
        impact_high = climate.get_current_impact(current_year=2008, start_year=2000)
        raw_val = abs(climate.climate_data[8])  # 0.8
        expected = raw_val * 1.5  # 1.2
        print(f"\nClimate impact with amplifier (year 8, raw=0.8): {impact_high}")
        print(f"Expected (1.5x amplification): {expected}")
        assert abs(impact_high - expected) < 0.01, "High impact amplification failed"
        print("[OK] High impact amplification works")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_data_path):
            os.remove(test_data_path)
    
    print("\n[PASS] Test 6: ClimateSystem with influences verified")


def test_resident_health_without_influences():
    """测试 Resident 健康计算向后兼容性（不使用影响函数）"""
    print("\n" + "="*60)
    print("Test 7: Resident Health - Backward Compatibility")
    print("="*60)
    
    # 创建简化的 Resident 对象（使用轻量级模式）
    class MockJobMarket:
        pass
    
    class MockSharedPool:
        pass
    
    class MockMap:
        pass
    
    resident = Resident(
        resident_id=1,
        job_market=MockJobMarket(),
        shared_pool=MockSharedPool(),
        map=MockMap(),
        prompts_resident={},
        actions_config={},
        lightweight=True,
        influence_registry=None  # 不使用影响函数
    )
    
    # 设置初始状态
    resident._health_index = 5
    resident._income = 0
    resident._satisfaction = 50
    resident._job = "农民"
    
    print(f"\nInitial health: {resident.health_index}")
    print(f"Income: {resident.income}, Satisfaction: {resident.satisfaction}")
    
    # 测试1：无收入场景（应该 -2）
    resident._income = 0
    resident.update_health_index(basic_living_cost=1000)
    expected_health = 5 - 2  # 3
    print(f"\nHealth after no income: {resident.health_index}")
    print(f"Expected: {expected_health}")
    assert resident.health_index == expected_health, "No income penalty failed"
    print("[OK] No income penalty works (-2)")
    
    # 测试2：低收入场景（应该 -1）
    resident._health_index = 5
    resident._income = 500  # 低于基本生活成本1000
    resident.update_health_index(basic_living_cost=1000)
    expected_health = 5 - 1  # 4
    print(f"\nHealth after low income (500<1000): {resident.health_index}")
    print(f"Expected: {expected_health}")
    assert resident.health_index == expected_health, "Low income penalty failed"
    print("[OK] Low income penalty works (-1)")
    
    # 测试3：高收入场景（应该 +1）
    resident._health_index = 5
    resident._income = 2500  # 高于2倍基本生活成本
    resident.update_health_index(basic_living_cost=1000)
    expected_health = 5 + 1  # 6
    print(f"\nHealth after high income (2500>2000): {resident.health_index}")
    print(f"Expected: {expected_health}")
    assert resident.health_index == expected_health, "High income recovery failed"
    print("[OK] High income recovery works (+1)")
    
    # 测试4：低满意度场景（应该 -1）
    resident._health_index = 5
    resident._income = 1200  # 正常收入
    resident._satisfaction = 20  # 低满意度
    resident.update_health_index(basic_living_cost=1000)
    expected_health = 5 - 1  # 4
    print(f"\nHealth after low satisfaction (20<30): {resident.health_index}")
    print(f"Expected: {expected_health}")
    assert resident.health_index == expected_health, "Low satisfaction penalty failed"
    print("[OK] Low satisfaction penalty works (-1)")
    
    # 测试5：叛军职业场景（应该 -2）
    resident._health_index = 5
    resident._income = 1200
    resident._satisfaction = 50
    resident._job = "叛军"
    resident.update_health_index(basic_living_cost=1000)
    expected_health = 5 - 2  # 3
    print(f"\nHealth after rebel job: {resident.health_index}")
    print(f"Expected: {expected_health}")
    assert resident.health_index == expected_health, "Rebel job penalty failed"
    print("[OK] Rebel job penalty works (-2)")
    
    print("\n[PASS] Test 7: Resident health backward compatibility verified")


def test_resident_health_with_influences():
    """测试 Resident 健康计算使用影响函数"""
    print("\n" + "="*60)
    print("Test 8: Resident Health - With Influence Functions")
    print("="*60)
    
    # 创建注册表并注册影响函数
    registry = InfluenceRegistry()
    
    # 注册叛军职业惩罚
    rebel_config = {
        'name': 'rebel_health_penalty',
        'type': 'code',
        'source': 'job',
        'target': 'health_index',
        'params': {
            'code': """
job = context.get('job', '')
if job == "叛军":
    context['result']['health_change'] = context['result'].get('health_change', 0) - 2
"""
        }
    }
    registry.register(create_code_influence(rebel_config))
    
    # 注册无收入惩罚
    no_income_config = {
        'name': 'no_income_penalty',
        'type': 'code',
        'source': 'income',
        'target': 'health_index',
        'params': {
            'code': """
income = context.get('income', 0)
if income <= 0:
    context['result']['health_change'] = context['result'].get('health_change', 0) - 2
"""
        }
    }
    registry.register(create_code_influence(no_income_config))
    
    # 注册高收入恢复
    high_income_config = {
        'name': 'high_income_recovery',
        'type': 'code',
        'source': 'income',
        'target': 'health_index',
        'params': {
            'code': """
income = context.get('income', 0)
basic_living_cost = context.get('basic_living_cost', 1000)
job = context.get('job')

if income >= basic_living_cost * 2:
    recovery = 0.5 if job == "叛军" else 1.0
    context['result']['health_change'] = context['result'].get('health_change', 0) + recovery
"""
        }
    }
    registry.register(create_code_influence(high_income_config))
    
    # 创建模拟对象
    class MockJobMarket:
        pass
    
    class MockSharedPool:
        pass
    
    class MockMap:
        pass
    
    # 创建带影响函数的 Resident
    resident = Resident(
        resident_id=2,
        job_market=MockJobMarket(),
        shared_pool=MockSharedPool(),
        map=MockMap(),
        prompts_resident={},
        actions_config={},
        lightweight=True,
        influence_registry=registry
    )
    
    # 测试1：叛军 + 高收入（应该 -2 + 0.5 = -1.5）
    resident._health_index = 5
    resident._income = 3000  # 高收入
    resident._satisfaction = 50
    resident._job = "叛军"
    
    print(f"\nInitial health: {resident.health_index}")
    print(f"Job: 叛军, Income: 3000 (high), Satisfaction: 50")
    
    resident.update_health_index(basic_living_cost=1000)
    expected_change = -2 + 0.5  # -1.5
    expected_health = int(max(0, min(10, 5 + expected_change)))  # 3
    print(f"\nHealth after rebel + high income: {resident.health_index}")
    print(f"Expected change: {expected_change}, Expected health: {expected_health}")
    assert resident.health_index == expected_health, "Rebel + high income calculation failed"
    print("[OK] Complex scenario (rebel + high income) works")
    
    # 测试2：无收入（应该 -2）
    resident._health_index = 5
    resident._income = 0
    resident._job = "农民"
    resident.update_health_index(basic_living_cost=1000)
    expected_health = 5 - 2  # 3
    print(f"\nHealth after no income: {resident.health_index}")
    print(f"Expected: {expected_health}")
    assert resident.health_index == expected_health, "No income with influences failed"
    print("[OK] No income penalty with influences works")
    
    print("\n[PASS] Test 8: Resident health with influences verified")


def test_government_tax_without_influences():
    """测试 Government 税率调整向后兼容性（不使用影响函数）"""
    print("\n" + "="*60)
    print("Test 9: Government Tax Rate - Backward Compatibility")
    print("="*60)
    
    # 创建模拟对象
    class MockMap:
        def get_navigability(self):
            return 0.8
    
    class MockTowns:
        pass
    
    class MockTime:
        pass
    
    # 创建测试配置文件（临时）
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write('ordinary_government_agent_system_message: ""\n')
        f.write('get_current_situation_prompt: ""\n')
        temp_prompt_file = f.name
    
    try:
        # 创建不带影响函数的政府对象
        government = Government(
            map=MockMap(),
            towns=MockTowns(),
            military_strength=100,
            initial_budget=10000,
            time=MockTime(),
            transport_economy=None,
            government_prompt_path=temp_prompt_file,
            influence_registry=None  # 不使用影响函数
        )
        
        print(f"\nInitial tax rate: {government.tax_rate * 100:.1f}%")
        
        # 测试1：正常调整（增加15%）
        government.tax_rate = 0.1
        government.adjust_tax_rate(0.15)
        expected_rate = 0.25  # 0.1 + 0.15
        print(f"\nTax rate after +15% adjustment: {government.tax_rate * 100:.1f}%")
        print(f"Expected: {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Tax rate increase failed"
        print("[OK] Tax rate increase works")
        
        # 测试2：上限测试（尝试超过50%）
        government.tax_rate = 0.45
        government.adjust_tax_rate(0.1)  # 尝试增加到55%
        expected_rate = 0.5  # 应该被限制在50%
        print(f"\nTax rate after trying to exceed limit: {government.tax_rate * 100:.1f}%")
        print(f"Expected (capped at 50%): {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Tax rate upper limit failed"
        print("[OK] Tax rate upper limit works (50%)")
        
        # 测试3：下限测试（尝试低于0%）
        government.tax_rate = 0.05
        government.adjust_tax_rate(-0.1)  # 尝试降低到-5%
        expected_rate = 0.0  # 应该被限制在0%
        print(f"\nTax rate after trying to go negative: {government.tax_rate * 100:.1f}%")
        print(f"Expected (capped at 0%): {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Tax rate lower limit failed"
        print("[OK] Tax rate lower limit works (0%)")
        
        # 测试4：负向调整
        government.tax_rate = 0.3
        government.adjust_tax_rate(-0.1)
        expected_rate = 0.2  # 0.3 - 0.1
        print(f"\nTax rate after -10% adjustment: {government.tax_rate * 100:.1f}%")
        print(f"Expected: {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Tax rate decrease failed"
        print("[OK] Tax rate decrease works")
        
    finally:
        # 清理临时文件
        import os
        if os.path.exists(temp_prompt_file):
            os.remove(temp_prompt_file)
    
    print("\n[PASS] Test 9: Government tax rate backward compatibility verified")


def test_government_tax_with_influences():
    """测试 Government 税率调整使用影响函数"""
    print("\n" + "="*60)
    print("Test 10: Government Tax Rate - With Influence Functions")
    print("="*60)
    
    # 创建注册表并注册影响函数
    registry = InfluenceRegistry()
    
    # 注册税率下限影响函数（5%最低税率）
    min_tax_config = {
        'name': 'custom_min_tax_rate',
        'type': 'code',
        'source': 'tax_adjustment',
        'target': 'tax_rate',
        'params': {
            'code': """
result = context['result']
new_tax_rate = result.get('new_tax_rate', 0.1)

# 自定义最低税率：5%
min_rate = 0.05
if new_tax_rate < min_rate:
    result['new_tax_rate'] = min_rate
"""
        }
    }
    registry.register(create_code_influence(min_tax_config))
    
    # 注册税率上限影响函数（30%最高税率，比默认50%更严格）
    max_tax_config = {
        'name': 'custom_max_tax_rate',
        'type': 'code',
        'source': 'tax_adjustment',
        'target': 'tax_rate',
        'params': {
            'code': """
result = context['result']
new_tax_rate = result.get('new_tax_rate', 0.1)

# 自定义最高税率：30%（民主制度）
max_rate = 0.3
if new_tax_rate > max_rate:
    result['new_tax_rate'] = max_rate
"""
        }
    }
    registry.register(create_code_influence(max_tax_config))
    
    # 创建模拟对象
    class MockMap:
        def get_navigability(self):
            return 0.8
    
    class MockTowns:
        pass
    
    class MockTime:
        pass
    
    # 创建测试配置文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write('ordinary_government_agent_system_message: ""\n')
        f.write('get_current_situation_prompt: ""\n')
        temp_prompt_file = f.name
    
    try:
        # 创建带影响函数的政府对象
        government = Government(
            map=MockMap(),
            towns=MockTowns(),
            military_strength=100,
            initial_budget=10000,
            time=MockTime(),
            transport_economy=None,
            government_prompt_path=temp_prompt_file,
            influence_registry=registry
        )
        
        # 测试1：自定义下限（应该限制在5%）
        government.tax_rate = 0.08
        government.adjust_tax_rate(-0.05)  # 尝试降低到3%
        expected_rate = 0.05  # 应该被限制在5%
        print(f"\nTax rate after trying to go below custom minimum: {government.tax_rate * 100:.1f}%")
        print(f"Expected (capped at custom 5%): {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Custom minimum tax rate failed"
        print("[OK] Custom minimum tax rate works (5%)")
        
        # 测试2：自定义上限（应该限制在30%）
        government.tax_rate = 0.25
        government.adjust_tax_rate(0.1)  # 尝试增加到35%
        expected_rate = 0.3  # 应该被限制在30%
        print(f"\nTax rate after trying to exceed custom maximum: {government.tax_rate * 100:.1f}%")
        print(f"Expected (capped at custom 30%): {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Custom maximum tax rate failed"
        print("[OK] Custom maximum tax rate works (30%)")
        
        # 测试3：正常范围内调整（5%-30%）
        government.tax_rate = 0.15
        government.adjust_tax_rate(0.05)
        expected_rate = 0.2  # 15% + 5% = 20%
        print(f"\nTax rate after normal adjustment within range: {government.tax_rate * 100:.1f}%")
        print(f"Expected: {expected_rate * 100:.1f}%")
        assert abs(government.tax_rate - expected_rate) < 0.001, "Normal adjustment with influences failed"
        print("[OK] Normal tax rate adjustment with custom rules works")
        
    finally:
        # 清理临时文件
        import os
        if os.path.exists(temp_prompt_file):
            os.remove(temp_prompt_file)
    
    print("\n[PASS] Test 10: Government tax rate with influences verified")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Starting Module Migration Tests")
    print("Testing: TransportEconomy, Population, ClimateSystem")
    print("="*60)
    
    try:
        # TransportEconomy 测试
        test_transport_economy_without_influences()
        test_transport_economy_with_influences()
        
        # Population 测试
        test_population_without_influences()
        test_population_with_influences()
        
        # ClimateSystem 测试
        test_climate_without_influences()
        test_climate_with_influences()
        
        # Resident 测试
        test_resident_health_without_influences()
        test_resident_health_with_influences()
        
        # Government 测试
        test_government_tax_without_influences()
        test_government_tax_with_influences()
        
        # 所有测试通过
        print("\n" + "="*60)
        print("[PASS] ALL TESTS PASSED")
        print("="*60)
        print("\nSummary:")
        print("- TransportEconomy: [OK] 2/2 tests passed")
        print("- Population: [OK] 2/2 tests passed")
        print("- ClimateSystem: [OK] 2/2 tests passed")
        print("- Resident: [OK] 2/2 tests passed")
        print("- Government: [OK] 2/2 tests passed")
        print("\nAll modules successfully migrated to influence function system!")
        print("="*60)
        
        return 0
        
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
