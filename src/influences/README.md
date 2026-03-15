# 影响函数系统 (Influence Functions System)

## 概述

影响函数系统用于描述模拟中各个模块之间的影响关系。通过定义影响函数，可以灵活地建模一个模块如何影响另一个模块的行为或状态。

## 核心概念

### IInfluenceFunction 接口

`IInfluenceFunction` 是所有影响函数的抽象基类，定义了影响函数的标准接口。

**核心属性：**
- `source` (str): 影响源模块的名称（如 "climate", "transport_economy"）
- `target` (str): 目标模块的名称（如 "population", "towns"）
- `name` (str): 影响函数的唯一标识名称
- `description` (str): 影响函数的描述信息（可选）

**核心方法：**
- `apply(target_obj, context: dict) -> Any`: 应用影响的核心方法
- `validate_context(context: dict, required_keys: list) -> bool`: 验证上下文

## 使用示例

### 1. 创建自定义影响函数

```python
from src.influences import IInfluenceFunction

class ClimateToPopulationInfluence(IInfluenceFunction):
    """气候对人口的影响"""
    
    def __init__(self):
        super().__init__(
            source="climate",
            target="population",
            name="extreme_weather_death",
            description="极端天气导致的人口死亡"
        )
    
    def apply(self, target_obj, context: dict):
        """
        计算极端天气对人口的影响
        
        Args:
            target_obj: Population 实例
            context: 包含 'climate', 'time' 等的上下文字典
        
        Returns:
            死亡人数（int）
        """
        # 验证上下文
        self.validate_context(context, ['climate', 'time'])
        
        climate = context['climate']
        time = context['time']
        
        # 检查是否是极端天气事件
        if not climate.is_extreme_event():
            return 0
        
        # 计算影响
        impact = climate.get_current_impact()
        current_population = target_obj.get_population()
        
        # 极端天气导致的死亡率：影响值 * 0.01
        death_rate = impact * 0.01
        deaths = int(current_population * death_rate)
        
        return deaths
```

### 2. 使用影响函数

```python
# 在模拟器中使用
class Simulator:
    def __init__(self, ...):
        # 创建影响函数
        self.climate_to_population = ClimateToPopulationInfluence()
    
    async def step(self):
        # 构建上下文
        context = {
            'climate': self.climate,
            'time': self.time,
            'map': self.map,
            'population': self.population
        }
        
        # 应用影响
        deaths = self.climate_to_population.apply(
            target_obj=self.population,
            context=context
        )
        
        # 更新人口
        if deaths > 0:
            self.population.death(deaths)
            print(f"极端天气导致 {deaths} 人死亡")
```

### 3. 复杂影响函数示例

```python
class TransportToTownsInfluence(IInfluenceFunction):
    """交通经济对城镇发展的影响"""
    
    def __init__(self):
        super().__init__(
            source="transport_economy",
            target="towns",
            name="river_trade_growth",
            description="河道通航带来的贸易增长"
        )
    
    def apply(self, target_obj, context: dict):
        """
        计算交通对城镇经济的影响
        
        Returns:
            dict: {
                'town_name': growth_rate,  # 每个城镇的增长率
                ...
            }
        """
        self.validate_context(context, ['transport_economy', 'map'])
        
        transport = context['transport_economy']
        map_obj = context['map']
        towns = target_obj
        
        growth_rates = {}
        
        for town_name, town_data in towns.towns.items():
            # 检查城镇是否靠近可通航河道
            navigability = map_obj.get_navigability()
            
            if navigability > 0.7:  # 河道通航良好
                # 计算贸易增长率
                river_price = transport.river_price
                base_growth = 0.02  # 基础增长率 2%
                
                # 河道价格越低，贸易越活跃，增长越快
                price_factor = max(0, (100 - river_price) / 100)
                growth_rate = base_growth * (1 + price_factor)
                
                growth_rates[town_name] = growth_rate
            else:
                growth_rates[town_name] = 0.0
        
        return growth_rates
```

## 设计原则

### 1. 单一职责
每个影响函数应该只描述一种特定的影响关系。

### 2. 显式依赖
通过 `validate_context` 明确声明影响函数需要哪些上下文信息。

### 3. 灵活返回
`apply` 方法的返回值可以是：
- 数值（如死亡人数、增长率）
- 布尔值（是否触发事件）
- 字典（多维度的影响结果）
- None（直接修改 target_obj）

### 4. 可组合性
多个影响函数可以组合使用，描述复杂的因果关系。

## 常见使用模式

### 模式1：直接修改目标对象

```python
def apply(self, target_obj, context: dict):
    # 直接修改目标对象的状态
    target_obj.some_property += 10
    return None  # 不需要返回值
```

### 模式2：返回影响值

```python
def apply(self, target_obj, context: dict):
    # 计算影响值，由调用者决定如何应用
    impact_value = self._calculate_impact(context)
    return impact_value
```

### 模式3：条件触发

```python
def apply(self, target_obj, context: dict):
    # 检查是否触发某个事件
    if self._should_trigger(context):
        return {'triggered': True, 'data': {...}}
    return {'triggered': False}
```

## 最佳实践

1. **明确命名**：使用描述性的名称，清楚表达影响的来源和目标
2. **文档完整**：为 `apply` 方法提供详细的文档字符串
3. **错误处理**：使用 `validate_context` 验证必需的上下文信息
4. **可测试性**：设计时考虑单元测试，影响函数应该易于测试
5. **日志记录**：在关键影响发生时记录日志，便于调试和分析

## 扩展方向

### 1. 影响强度
为影响函数添加强度参数，允许动态调整影响的大小：

```python
class WeightedInfluence(IInfluenceFunction):
    def __init__(self, source, target, name, weight=1.0):
        super().__init__(source, target, name)
        self.weight = weight
    
    def apply(self, target_obj, context: dict):
        base_impact = self._calculate_base_impact(context)
        return base_impact * self.weight
```

### 2. 影响链
支持影响函数的链式组合：

```python
class InfluenceChain:
    def __init__(self, influences: List[IInfluenceFunction]):
        self.influences = influences
    
    def apply(self, initial_obj, context: dict):
        result = initial_obj
        for influence in self.influences:
            result = influence.apply(result, context)
        return result
```

### 3. 条件影响
基于条件动态选择影响函数：

```python
class ConditionalInfluence(IInfluenceFunction):
    def __init__(self, source, target, name, condition_fn, influence_fn):
        super().__init__(source, target, name)
        self.condition = condition_fn
        self.influence = influence_fn
    
    def apply(self, target_obj, context: dict):
        if self.condition(context):
            return self.influence(target_obj, context)
        return None
```

## 与插件系统集成

影响函数可以作为插件的一部分，实现模块化的影响系统：

```python
# plugins/my_influence/influence_plugin.py
from src.influences import IInfluenceFunction
from src.plugins import BasePlugin

class MyInfluencePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.influences = []
    
    def on_load(self):
        # 注册影响函数
        self.influences.append(ClimateToPopulationInfluence())
        self.influences.append(TransportToTownsInfluence())
    
    def get_influences(self):
        return self.influences
```

## 参考资料

- [src/influences/iinfluence.py](iinfluence.py) - 接口定义
- [test_influence_interface.py](../../test_influence_interface.py) - 测试示例
