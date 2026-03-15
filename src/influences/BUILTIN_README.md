# builtin.py - 常用影响函数类

这个模块提供了三个常用的影响函数实现，用于建模模块间的简单影响关系。

## 类列表

### 1. ConstantInfluence - 常量影响

直接设置目标对象的属性为一个常量值。

**适用场景：**
- 初始化配置
- 设置基准值
- 固定参数

**参数：**
- `target_attr`: 要设置的目标属性名
- `value`: 常量值（可以是任何类型）

**示例：**

```python
from src.influences import ConstantInfluence

# 设置基准税率为15%
influence = ConstantInfluence(
    source='government',
    target='population',
    name='set_base_tax',
    target_attr='tax_rate',
    value=0.15
)

# 应用影响
context = {}
influence.apply(population, context)
# 结果: population.tax_rate = 0.15
```

**配置示例：**

```yaml
influences:
  - type: constant
    source: government
    target: population
    name: base_tax_rate
    params:
      target_attr: tax_rate
      value: 0.15
```

---

### 2. LinearInfluence - 线性影响

根据上下文变量进行线性计算：`result = coefficient × variable + constant`

**适用场景：**
- 线性关系建模
- 简单数学计算
- 比例影响

**参数：**
- `variable`: 上下文变量路径（支持点号分隔，如 `'climate.temperature'`）
- `coefficient`: 系数（默认1.0）
- `constant`: 常数项（默认0.0）
- `target_attr`: 目标属性名（可选，如不指定则只返回计算结果）
- `mode`: 影响模式
  - `'set'` - 直接设置（默认）
  - `'add'` - 累加到现有值
  - `'multiply'` - 乘以现有值

**示例：**

```python
from src.influences import LinearInfluence

# 温度每升高1度，死亡率增加0.01（累加模式）
influence = LinearInfluence(
    source='climate',
    target='population',
    name='temperature_death',
    variable='climate.temperature',
    coefficient=0.01,
    constant=0.0,
    target_attr='death_rate_modifier',
    mode='add'
)

# 应用影响
context = {'climate': climate}  # climate.temperature = 35
influence.apply(population, context)
# 结果: death_rate_modifier += 0.01 * 35 + 0.0 = 0.35
```

**配置示例：**

```yaml
influences:
  - type: linear
    source: climate
    target: population
    name: temperature_death_modifier
    params:
      variable: climate.temperature
      coefficient: 0.01
      constant: 0.0
      target_attr: death_rate_modifier
      mode: add
```

**高级用法 - 嵌套属性访问：**

```python
# 访问深层嵌套的属性
influence = LinearInfluence(
    source='region',
    target='statistics',
    name='nested_calc',
    variable='region.city.district.population',
    coefficient=0.001,
    constant=0.0
)

context = {
    'region': region_obj  # region_obj.city.district.population = 50000
}
result = influence.apply(stats, context)
# 结果: 0.001 * 50000 = 50.0
```

---

### 3. CodeInfluence - 代码影响

执行用户提供的Python代码片段来计算影响。代码在受限环境中执行以确保安全性。

**适用场景：**
- 复杂逻辑
- 多因素综合计算
- 条件判断
- 自定义算法

**安全限制：**
- 只能访问白名单中的内置函数
- 不能导入模块（math模块已预加载）
- 不能访问文件系统
- 不能执行系统命令

**可用内置函数：**
- 数学：`abs`, `min`, `max`, `sum`, `round`, `pow`
- 数学模块：`math.sqrt`, `math.sin`, `math.cos`, `math.log` 等
- 类型：`int`, `float`, `str`, `bool`
- 容器：`list`, `dict`, `tuple`, `set`, `len`
- 逻辑：`all`, `any`, `range`

**代码中可访问的变量：**
- `target`: 目标对象
- `context`: 完整的上下文字典
- 所有上下文中的模块（如 `climate`, `economy`, `population` 等）

**参数：**
- `code`: Python代码字符串
- `target_attr`: 要设置的目标属性名（可选）
- `result_var`: 结果变量名（默认 `'result'`）

**示例1 - 复杂满意度计算：**

```python
from src.influences import CodeInfluence

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

context = {
    'economy': economy,
    'gdp': 8000,
    'unemployment_rate': 0.1
}

influence.apply(towns, context)
# 结果: towns.satisfaction = 0.75
```

**示例2 - 条件判断：**

```python
code = """
if temperature > 40:
    result = 'extreme'
elif temperature > 30:
    result = 'hot'
else:
    result = 'normal'
"""

influence = CodeInfluence(
    source='climate',
    target='alert_system',
    name='temp_status',
    code=code,
    target_attr='status'
)
```

**示例3 - 使用数学函数：**

```python
code = """
# 使用正弦函数模拟季节性变化
seasonal_effect = 1.0 + 0.2 * math.sin(day_of_year / 365 * 2 * math.pi)
result = base_value * seasonal_effect
"""

influence = CodeInfluence(
    source='time',
    target='agriculture',
    name='seasonal_production',
    code=code,
    target_attr='production_multiplier'
)
```

**示例4 - 访问目标对象：**

```python
code = """
# 自适应调整：根据目标对象当前状态决定影响
current_value = getattr(target, 'satisfaction', 0.5)

if current_value < 0.3:
    result = 'increase_support'
elif current_value > 0.7:
    result = 'reduce_support'
else:
    result = 'maintain'
"""

influence = CodeInfluence(
    source='government',
    target='towns',
    name='adaptive_policy',
    code=code,
    target_attr='policy_adjustment'
)
```

**配置示例：**

```yaml
influences:
  - type: code
    source: economy
    target: towns
    name: comprehensive_satisfaction
    params:
      code: |
        # 多因素计算
        gdp_factor = min(1.0, economy.gdp / 10000)
        unemployment_penalty = economy.unemployment_rate * 0.5
        result = max(0.0, gdp_factor - unemployment_penalty)
      target_attr: satisfaction
      result_var: result
```

**安全注意事项：**

⚠️ 出于安全考虑，通常不建议从外部配置文件加载 `CodeInfluence`。建议：

1. **受信任环境**：只在完全受信任的配置文件中使用
2. **代码审查**：加载前人工审查所有代码
3. **沙箱环境**：在隔离环境中测试
4. **程序化创建**：优先在代码中直接创建，而非从配置加载

---

## 工厂函数

每个类都提供了工厂函数用于从配置字典创建实例：

```python
from src.influences.builtin import (
    create_constant_influence,
    create_linear_influence,
    create_code_influence
)

# 从配置创建
config = {
    'source': 'climate',
    'target': 'population',
    'name': 'temp_effect',
    'params': {
        'variable': 'climate.temperature',
        'coefficient': 0.01,
        'constant': 0.0,
        'target_attr': 'death_modifier',
        'mode': 'add'
    }
}

influence = create_linear_influence(config)
```

这些工厂函数已自动注册到 `InfluenceRegistry`，支持通过配置文件加载。

---

## 与 InfluenceRegistry 集成

这三个类已自动注册到影响函数注册中心：

```python
from src.influences import InfluenceRegistry

registry = InfluenceRegistry()

# 工厂已自动注册，可以直接从配置加载
config = {
    'influences': [
        {'type': 'constant', ...},
        {'type': 'linear', ...},
        {'type': 'code', ...}
    ]
}

registry.load_from_config(config)
```

---

## 对比 builtin_influences.py

| 特性 | builtin.py | builtin_influences.py |
|------|------------|----------------------|
| 设计理念 | 简单直接 | 高级功能 |
| 常量设置 | ✓ ConstantInfluence | ✗ |
| 线性计算 | ✓ LinearInfluence (多模式) | ✓ LinearMultiplierInfluence (单一) |
| 阈值判断 | ✗ | ✓ ThresholdInfluence |
| 条件逻辑 | ✗ | ✓ ConditionalInfluence |
| 自定义代码 | ✓ CodeInfluence (受限) | ✓ LambdaInfluence (完全) |
| 配置加载 | 完全支持 | 部分支持（Lambda除外）|
| 安全性 | ✓ 受限环境 | ⚠️ 需要信任代码 |

**使用建议：**

- **简单场景**：使用 `builtin.py` 中的类
- **复杂逻辑**：
  - 需要阈值判断 → `ThresholdInfluence`
  - 需要条件组合 → `ConditionalInfluence`
  - 需要自定义逻辑且不加载配置 → `LambdaInfluence`
  - 需要从配置加载自定义逻辑 → `CodeInfluence`

---

## 测试

运行测试验证功能：

```bash
python test_builtin_influences.py
```

测试覆盖：
- ✓ ConstantInfluence - 常量设置和属性创建
- ✓ LinearInfluence - 三种模式（set/add/multiply）+ 嵌套属性访问
- ✓ CodeInfluence - 计算、数学函数、条件逻辑、target访问、错误处理
- ✓ InfluenceRegistry 集成 - 配置加载和应用

---

## 更多示例

完整的配置示例见：[config/influences_example.yaml](../config/influences_example.yaml)

集成指南见：[docs/INFLUENCE_INTEGRATION.md](../docs/INFLUENCE_INTEGRATION.md)
