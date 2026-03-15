# 将硬编码公式迁移到影响函数系统 - 实施指南

本文档提供了将现有模块中的硬编码更新公式迁移到影响函数系统的详细指南。

## 概述

**已完成示例：** Map 模块
- 文件：`src/environment/map.py`
- 改造的方法：`update_river_condition()`, `decay_river_condition_naturally()`

**迁移优势：**
1. ✅ **配置驱动**：通过 YAML 文件调整公式，无需修改代码
2. ✅ **向后兼容**：未配置影响函数时自动使用默认公式
3. ✅ **可扩展**：轻松添加新的影响因素
4. ✅ **可组合**：多个影响函数可以组合使用
5. ✅ **可测试**：影响函数可以独立测试

## 迁移步骤（通用）

### 步骤 1：修改模块接口

在接口文件中添加影响函数相关方法。

**示例（IMap 接口）：**

```python
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.influences import InfluenceRegistry

class IYourModule(ABC):
    @abstractmethod
    def __init__(self, ..., influence_registry: Optional['InfluenceRegistry'] = None):
        """添加 influence_registry 参数（可选）"""
        pass
    
    @abstractmethod
    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """应用所有注册的影响函数"""
        pass
```

### 步骤 2：修改模块实现

在实现类中集成影响函数系统。

**2.1 修改构造函数：**

```python
class YourModule(IYourModule):
    def __init__(self, ..., influence_registry: Optional['InfluenceRegistry'] = None):
        # 其他初始化...
        self._influence_registry = influence_registry
```

**2.2 添加 apply_influences 方法：**

```python
def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
    """应用所有注册的影响函数到指定目标"""
    if self._influence_registry is None:
        return
    
    # 如果没有提供上下文，创建默认上下文
    if context is None:
        context = {}
    
    # 确保上下文中包含模块对象本身
    context['your_module'] = self
    
    # 获取所有影响该目标的影响函数
    influences = self._influence_registry.get_influences(target_name)
    
    # 应用每个影响函数
    for influence in influences:
        try:
            impact = influence.apply(self, context)
            if impact is not None:
                # 可以记录影响或采取其他行动
                pass
        except Exception as e:
            print(f"应用影响函数失败 ({influence.source}->{target_name}:{influence.name}): {e}")
```

### 步骤 3：改造现有更新方法

将硬编码公式替换为影响函数调用，同时保持向后兼容。

**改造模板：**

```python
def update_something(self, parameter1, parameter2):
    """
    更新某个属性
    :param parameter1: 参数1
    :param parameter2: 参数2
    """
    current_value = self.some_attribute
    
    # 构建上下文
    context = {
        'your_module': self,
        'parameter1': parameter1,
        'parameter2': parameter2,
        'current_value': current_value
    }
    
    # 首先尝试应用影响函数
    if self._influence_registry is not None:
        influences = self._influence_registry.get_influences('your_target_name')
        if influences:
            # 有配置的影响函数，应用它们
            self.apply_influences('your_target_name', context)
            return
    
    # 回退到默认公式（保持向后兼容）
    # 原硬编码公式：
    if parameter1 > 0:
        new_value = current_value * parameter1 + parameter2
    else:
        new_value = current_value * 0.9
    
    self.some_attribute = new_value
```

### 步骤 4：创建影响函数配置

为模块创建 YAML 配置文件。

**文件位置：** `config/your_module_influences.yaml`

```yaml
influences:
  # 替代原有的更新公式
  - type: code
    source: source_module
    target: your_target_name
    name: your_influence_name
    description: 影响描述
    params:
      code: |
        # 从上下文获取参数
        current = context.get('current_value', 0)
        param1 = context.get('parameter1', 1.0)
        param2 = context.get('parameter2', 0)
        
        # 实现原有的逻辑
        if param1 > 0:
            result = current * param1 + param2
        else:
            result = current * 0.9
      target_attr: some_attribute
      result_var: result
```

### 步骤 5：更新主程序集成

在主程序中加载影响函数配置。

```python
import yaml
from src.influences import InfluenceRegistry
from src.your_module import YourModule

# 加载影响函数配置
with open('config/your_module_influences.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 创建注册中心并加载配置
influence_registry = InfluenceRegistry()
influence_registry.load_from_config(config)

# 创建模块实例并传入注册中心
your_module = YourModule(
    ...,
    influence_registry=influence_registry
)
```

## 具体模块迁移指南

### 1. 经济系统（运输成本计算）

**目标模块：** `src/environment/transport_economy.py` 或类似

**待迁移的硬编码公式示例：**
```python
# 运输成本计算
def calculate_transport_cost(self, distance, cargo_size):
    base_cost = distance * 0.1
    size_modifier = cargo_size * 0.05
    terrain_modifier = self.get_terrain_factor()
    
    return base_cost + size_modifier + terrain_modifier
```

**迁移后的实现：**

```python
def calculate_transport_cost(self, distance, cargo_size):
    """计算运输成本"""
    # 构建上下文
    context = {
        'transport': self,
        'distance': distance,
        'cargo_size': cargo_size,
        'terrain_factor': self.get_terrain_factor()
    }
    
    # 尝试应用影响函数
    if self._influence_registry is not None:
        influences = self._influence_registry.get_influences('transport_cost')
        if influences:
            # 初始化成本为0
            self._temp_transport_cost = 0.0
            self.apply_influences('transport_cost', context)
            return self._temp_transport_cost
    
    # 回退到默认公式
    base_cost = distance * 0.1
    size_modifier = cargo_size * 0.05
    terrain_modifier = self.get_terrain_factor()
    
    return base_cost + size_modifier + terrain_modifier
```

**配置文件：** `config/transport_influences.yaml`

```yaml
influences:
  # 基础距离成本
  - type: linear
    source: distance
    target: transport_cost
    name: distance_cost
    params:
      variable: distance
      coefficient: 0.1
      constant: 0.0
      target_attr: _temp_transport_cost
      mode: add
  
  # 货物大小影响
  - type: linear
    source: cargo
    target: transport_cost
    name: cargo_size_cost
    params:
      variable: cargo_size
      coefficient: 0.05
      constant: 0.0
      target_attr: _temp_transport_cost
      mode: add
  
  # 地形影响
  - type: code
    source: terrain
    target: transport_cost
    name: terrain_cost
    params:
      code: |
        terrain = context.get('terrain_factor', 1.0)
        result = terrain
      target_attr: _temp_transport_cost
      result_var: result
  
  # 运河通航影响（新增）
  - type: code
    source: canal
    target: transport_cost
    name: canal_discount
    params:
      code: |
        # 如果有可用的运河，降低运输成本
        if hasattr(context.get('map'), 'get_navigability'):
            navigability = context['map'].get_navigability()
            if navigability > 0.5:
                # 运河可用时降低30%成本
                discount = 0.3 * navigability
                current = getattr(target, '_temp_transport_cost', 0)
                result = current * (1 - discount)
            else:
                result = None
        else:
            result = None
      target_attr: _temp_transport_cost
      result_var: result
```

### 2. 人口模块（出生率/死亡率计算）

**待迁移公式：**
```python
def calculate_birth_rate(self):
    base_rate = 0.02
    prosperity_modifier = self.prosperity * 0.01
    health_modifier = self.health_level * 0.005
    return base_rate + prosperity_modifier + health_modifier
```

**迁移后：**

```python
def calculate_birth_rate(self):
    """计算出生率"""
    context = {
        'population': self,
        'prosperity': self.prosperity,
        'health_level': self.health_level
    }
    
    if self._influence_registry is not None:
        influences = self._influence_registry.get_influences('birth_rate')
        if influences:
            self._temp_birth_rate = 0.0
            self.apply_influences('birth_rate', context)
            return self._temp_birth_rate
    
    # 默认公式
    base_rate = 0.02
    prosperity_modifier = self.prosperity * 0.01
    health_modifier = self.health_level * 0.005
    return base_rate + prosperity_modifier + health_modifier
```

**配置文件：**

```yaml
influences:
  - type: constant
    source: base
    target: birth_rate
    name: base_birth_rate
    params:
      target_attr: _temp_birth_rate
      value: 0.02
  
  - type: linear
    source: economy
    target: birth_rate
    name: prosperity_effect
    params:
      variable: prosperity
      coefficient: 0.01
      constant: 0.0
      target_attr: _temp_birth_rate
      mode: add
  
  - type: linear
    source: health
    target: birth_rate
    name: health_effect
    params:
      variable: health_level
      coefficient: 0.005
      constant: 0.0
      target_attr: _temp_birth_rate
      mode: add
```

### 3. 气候模块（温度/降雨更新）

**待迁移公式：**
```python
def update_temperature(self, season):
    base_temp = self.base_temperature[season]
    random_variation = random.gauss(0, 2)
    trend = self.climate_trend * 0.1
    
    self.temperature = base_temp + random_variation + trend
```

**迁移后：**

```yaml
influences:
  - type: code
    source: season
    target: temperature
    name: seasonal_temperature
    params:
      code: |
        import random
        season = context.get('season', 'spring')
        base_temps = {'spring': 15, 'summer': 25, 'autumn': 15, 'winter': 5}
        
        base_temp = base_temps.get(season, 15)
        random_variation = random.gauss(0, 2)
        trend = context.get('climate_trend', 0) * 0.1
        
        result = base_temp + random_variation + trend
      target_attr: temperature
```

## 最佳实践

### 1. 命名约定

- **Target名称**：使用描述性名称，如 `canal`, `transport_cost`, `birth_rate`
- **Source名称**：表示影响来源，如 `government`, `climate`, `economy`
- **Influence名称**：清晰描述影响类型，如 `maintenance_boost`, `distance_cost`

### 2. 上下文设计

确保上下文包含所有必要的信息：

```python
context = {
    'module': self,           # 模块对象本身
    'param1': value1,         # 方法参数
    'param2': value2,
    'current_state': state,   # 当前状态
    'other_modules': {...}    # 其他相关模块
}
```

### 3. 临时属性

使用临时属性存储计算结果：

```python
# 在影响函数中累积结果
self._temp_transport_cost = 0.0

# 最后返回
return self._temp_transport_cost
```

### 4. 错误处理

始终添加 try-except 以避免单个影响函数失败影响整个系统：

```python
for influence in influences:
    try:
        impact = influence.apply(self, context)
    except Exception as e:
        print(f"影响函数错误: {e}")
        continue
```

### 5. 向后兼容

保持默认公式作为回退方案：

```python
if self._influence_registry is not None:
    # 尝试使用影响函数
    if influences:
        ...
        return result

# 回退到默认公式
return default_calculation()
```

## 测试

为每个迁移的模块创建测试文件：

```python
def test_module_without_influences():
    """测试向后兼容性"""
    module = YourModule()
    result = module.update_method(args)
    assert result == expected

def test_module_with_influences():
    """测试影响函数系统"""
    registry = InfluenceRegistry()
    # 加载配置...
    module = YourModule(influence_registry=registry)
    result = module.update_method(args)
    assert result == expected
```

## 迁移优先级建议

1. **高优先级**（频繁调用，复杂公式）：
   - 运河维护和衰减 ✅ **已完成**
   - 运输成本计算
   - 人口变化（出生率/死亡率）
   - 经济指标（GDP、税收）

2. **中优先级**（定期更新）：
   - 气候变化
   - 资源消耗
   - 社交网络影响力

3. **低优先级**（简单计算）：
   - 固定配置值
   - 一次性初始化

## 常见问题

### Q: 性能会受影响吗？

A: 影响函数系统增加的开销很小（主要是字典查找和函数调用）。如果性能关键，可以：
- 缓存影响函数查询结果
- 只在必要时调用 `apply_influences()`
- 使用预编译的影响函数

### Q: 如何调试影响函数？

A: 添加详细日志：

```python
for influence in influences:
    print(f"应用影响: {influence.name}")
    impact = influence.apply(self, context)
    print(f"  结果: {impact}")
```

### Q: 如何处理复杂的多步骤更新？

A: 使用多个目标和顺序应用：

```python
# 步骤1：计算基础值
self.apply_influences('base_calculation', context)

# 步骤2：应用修正
context['base_value'] = self.base_value
self.apply_influences('modifiers', context)

# 步骤3：最终调整
self.apply_influences('final_adjustment', context)
```

## 总结

通过将硬编码公式迁移到影响函数系统，您可以：

1. **提高灵活性**：通过配置文件调整模拟行为
2. **增强可维护性**：公式集中管理，易于理解和修改
3. **支持实验**：快速测试不同的影响关系和参数
4. **保持兼容性**：渐进式迁移，不破坏现有功能

## 已完成的模块迁移

### 1. Map 模块（运河系统）

**迁移内容：** 运河通航能力更新计算

**参考文件：**
- 接口：`src/interfaces/imap.py`
- 实现：`src/environment/map.py`
- 配置示例：`config/examples/map_influences_example.yaml`
- 测试：`test_map_influences.py`

**影响函数数量：** 6个（基础更新、低维护惩罚、高维护奖励等）

### 2. TransportEconomy 模块（运输经济系统）

**迁移内容：** 河运价格计算、维护成本计算、总运输成本计算

**参考文件：**
- 接口：`src/interfaces/itransport_economy.py`
- 实现：`src/environment/transport_economy.py`
- 配置示例：`config/examples/transport_economy_influences_example.yaml`
- 测试：`test_module_migrations.py` (Test 1-2)

**影响函数数量：** 9个（河运价格、维护成本、运输成本混合等）

### 3. Population 模块（人口系统）

**迁移内容：** 出生率计算（基于满意度和经济状况）

**参考文件：**
- 接口：`src/interfaces/ipopulation.py`
- 实现：`src/environment/population.py`
- 配置示例：`config/examples/population_influences_example.yaml`
- 测试：`test_module_migrations.py` (Test 3-4)

**影响函数数量：** 10个（满意度影响、经济繁荣影响、冲突惩罚等）

### 4. ClimateSystem 模块（气候系统）

**迁移内容：** 气候影响计算和放大器

**参考文件：**
- 接口：`src/interfaces/iclimate_system.py`
- 实现：`src/environment/climate.py`
- 配置示例：`config/examples/climate_influences_example.yaml`
- 测试：`test_module_migrations.py` (Test 5-6)

**影响函数数量：** 11个（基础影响、极端事件放大、季节性修正等）

### 5. Resident 模块（居民健康系统）

**迁移内容：** 居民健康指数计算（基于职业、收入、满意度）

**参考文件：**
- 接口：`src/interfaces/iresident.py`
- 实现：`src/agents/resident.py`
- 配置示例：`config/examples/resident_health_influences_example.yaml`
- 测试：`test_module_migrations.py` (Test 7-8)

**影响函数数量：** 10个（6个核心 + 4个可选扩展）

**核心影响函数：**
- `rebel_health_penalty`：叛军职业惩罚 (-2)
- `no_income_penalty`：无收入惩罚 (-2)
- `low_income_penalty`：低收入惩罚 (-1)
- `high_income_recovery`：高收入恢复 (+0.5 或 +1)
- `low_satisfaction_penalty`：低满意度惩罚 (-1)
- `high_satisfaction_recovery`：高满意度恢复 (+0.5 或 +1)

**可选扩展影响函数（默认禁用）：**
- `environmental_health_impact`：环境污染影响
- `healthcare_bonus`：医疗系统加成
- `age_related_decline`：年龄相关衰退
- `social_network_health_bonus`：社交网络健康加成

**迁移特点：**
- 采用 `health_change` 累加模式，所有影响先累加后应用
- 支持复杂的多因素组合（如叛军 + 高收入 = -2 + 0.5）
- 健康指数自动限制在 [0, 10] 范围内
- 完全向后兼容，未配置影响函数时使用默认逻辑

**使用示例：**

```python
# 创建带健康影响函数的居民
from src.influences import InfluenceRegistry

registry = InfluenceRegistry()
registry.load_from_yaml('config/examples/resident_health_influences_example.yaml')

resident = Resident(
    resident_id=1,
    job_market=job_market,
    shared_pool=shared_pool,
    map=map_obj,
    prompts_resident=prompts,
    actions_config=actions,
    influence_registry=registry
)

# 健康更新会自动应用配置的影响函数
resident.update_health_index(basic_living_cost=1000)
```

**扩展场景示例：**

```yaml
# 流行病场景
- name: pandemic_penalty
  type: constant
  source: pandemic
  target: health_index
  params:
    value: -3.0
    target_attr: health_change
    use_result_dict: true
    mode: add

# 医疗政策加成
- name: free_healthcare_bonus
  type: code
  source: government_policy
  target: health_index
  params:
    code: |
      policy = context.get('healthcare_policy', 'none')
      if policy == 'universal':
          context['result']['health_change'] += 1.0
```

### 6. Government 模块（政府税率系统）

**迁移内容：** 税率调整规则和边界限制

**参考文件：**
- 接口：`src/interfaces/igovernment.py`
- 实现：`src/agents/government.py`
- 配置示例：`config/examples/government_tax_influences_example.yaml`
- 测试：`test_module_migrations.py` (Test 9-10)

**影响函数数量：** 10个（3个核心 + 7个可选扩展）

**核心影响函数：**
- `min_tax_rate_limit`：税率下限（基础场景：0%）
- `max_tax_rate_limit`：税率上限（基础场景：50%）
- `gradual_adjustment_limit`：单次最大调整幅度限制（10%）

**可选扩展影响函数（默认禁用）：**
- `wartime_tax_limit`：战争时期税率上限（70%）
- `recession_tax_reduction`：经济衰退强制降税（15%）
- `democratic_tax_limit`：民主制度下基于满意度的税率约束
- `ancient_autocracy_high_tax`：古代专制高税率（80%）
- `fiscal_crisis_emergency_tax`：财政危机紧急税（60%）
- `progressive_tax_by_satisfaction`：满意度分层累进税率系统
- `rebellion_risk_tax_adjustment`：叛乱风险自动降税

**迁移特点：**
- 使用 `result['new_tax_rate']` 存储计算结果
- 支持多重边界条件叠加（如战争+财政危机）
- 完全向后兼容，未配置影响函数时使用默认限制（0%-50%）
- 所有边界和规则可通过配置文件动态调整

**使用示例：**

```python
# 创建带税率影响函数的政府
from src.influences import InfluenceRegistry

registry = InfluenceRegistry()
registry.load_from_yaml('config/examples/government_tax_influences_example.yaml')

government = Government(
    map=map_obj,
    towns=towns,
    military_strength=100,
    initial_budget=10000,
    time=time_obj,
    transport_economy=transport_econ,
    government_prompt_path='config/default/government_prompts.yaml',
    influence_registry=registry
)

# 税率调整会自动应用配置的边界和规则
government.adjust_tax_rate(0.15)  # 尝试增加15%税率
```

**场景组合示例：**

```yaml
# 场景1：民主制度 + 低满意度
- 启用 democratic_tax_limit（满意度<30时上限20%）
- 启用 progressive_tax_by_satisfaction（累进税率）
- 结果：双重约束，税率最多20%

# 场景2：战争 + 财政危机
- 启用 wartime_tax_limit（战争上限70%）
- 启用 fiscal_crisis_emergency_tax（危机上限60%）
- 结果：取最严格的约束，上限60%

# 场景3：经济衰退 + 叛乱风险
- 启用 recession_tax_reduction（GDP<-5%强制降到15%）
- 启用 rebellion_risk_tax_adjustment（叛军>5%强制降到20%）
- 结果：取最严格的约束，上限15%
```

**历史场景模拟：**

```yaml
# 古代专制（明朝）
- 启用 ancient_autocracy_high_tax（上限80%）
- 禁用 democratic_tax_limit
- 结果：高税率压迫，易引发叛乱

# 现代民主
- 启用 democratic_tax_limit（基于满意度）
- 启用 progressive_tax_by_satisfaction（累进税）
- 结果：税率受民意约束，需平衡财政与满意度
```

**技术细节：**

原始硬编码逻辑：
```python
def adjust_tax_rate(self, adjustment):
    old_rate = self.tax_rate
    # 固定限制：0% 到 50%
    self.tax_rate = max(0.0, min(0.5, self.tax_rate + adjustment))
    return self.tax_rate
```

迁移后的两阶段逻辑：
```python
def adjust_tax_rate(self, adjustment):
    old_rate = self.tax_rate
    
    # 构建上下文
    result = {'new_tax_rate': self.tax_rate + adjustment}
    context = {
        'government': self,
        'old_tax_rate': old_rate,
        'adjustment': adjustment,
        'result': result
    }
    
    # 阶段1：尝试使用影响函数
    if self._influence_registry is not None:
        influences = self._influence_registry.get_influences('tax_rate')
        if influences:
            self.apply_influences('tax_rate', context)
            self.tax_rate = result['new_tax_rate']
            return self.tax_rate
    
    # 阶段2：回退到默认逻辑（向后兼容）
    self.tax_rate = max(0.0, min(0.5, self.tax_rate + adjustment))
    return self.tax_rate
```

**应用价值：**

1. **历史研究**：模拟不同历史时期的税收政策（古代专制 vs 现代民主）
2. **政策实验**：测试不同税率限制对经济和满意度的影响
3. **危机应对**：动态调整税率边界应对战争、灾害、叛乱等危机
4. **制度对比**：对比不同政治制度下的税收能力和约束
5. **经济模拟**：研究税率与经济增长、财政收支的平衡关系

## 迁移统计

| 模块 | 影响函数数量 | 测试用例 | 状态 |
|------|------------|---------|------|
| Map | 6 | 4 | ✅ 完成 |
| TransportEconomy | 9 | 2 | ✅ 完成 |
| Population | 10 | 2 | ✅ 完成 |
| ClimateSystem | 11 | 2 | ✅ 完成 |
| Resident | 10 | 2 | ✅ 完成 |
| Government | 10 | 2 | ✅ 完成 |
| **总计** | **56** | **14** | **6/6** |

所有测试通过率：**100%** (14/14 测试用例)
