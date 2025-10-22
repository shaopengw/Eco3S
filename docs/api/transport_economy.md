# Transport Economy 模块 API 文档

## TransportEconomy 类

### 功能概述
运输经济系统模拟器，负责模拟和管理运输成本、价格计算和维护成本等经济指标。实现了河运和海运的价格动态调整机制，以及基于通航能力的维护成本计算。

### 初始化
```python
TransportEconomy(transport_cost: float, transport_task: float, maintenance_cost_base: float = 100)
```
- 功能：创建运输经济系统实例
- 参数：
  - transport_cost: float - 基础运输成本
  - transport_task: float - 年度运输任务量（吨）
  - maintenance_cost_base: float - 基础维护成本（默认100）
- 初始化属性：
  - river_price: float - 河运价格（初始等于基础运输成本）
  - sea_price: float - 海运价格（初始为基础运输成本的1/5）

### 核心方法

#### calculate_river_price
- 功能：计算河运价格
- 参数：
  - navigability: float - 通航能力（0-1范围）
- 返回：
  - float - 计算后的河运价格
- 计算逻辑：
  - 基础公式：transport_cost * (2 - navigability)
  - 最低不低于基础运输成本
  - 结果保留2位小数
- 特点：
  - 通航能力越低，价格越高
  - 自动更新实例的river_price属性

#### calculate_maintenance_cost
- 功能：计算河运系统维护成本
- 参数：
  - navigability: float - 通航能力（0-1范围）
  - exponent: int - 指数（默认3）
- 返回：
  - float - 维护成本
- 计算逻辑：
  - 基础公式：maintenance_cost_base * ((2 - navigability) ** exponent)
  - 结果保留2位小数
- 特点：
  - 通航能力越低，维护成本指数增长
  - 可通过exponent参数调整增长曲线

#### calculate_total_transport_cost
- 功能：计算总体运输成本
- 参数：
  - river_ratio: float - 河运比例（0-1范围）
- 返回：
  - float - 总运输成本
- 计算逻辑：
  - 河运成本 = river_price * river_ratio * transport_task
  - 海运成本 = sea_price * (1 - river_ratio) * transport_task
  - 总成本 = 河运成本 + 海运成本

### 价格关系

#### 河运与海运价格对比
- 河运价格：动态变化，受通航能力影响
- 海运价格：固定为基础运输成本的1/5
- 价格关系：通常情况下河运更经济，但通航能力低时可能高于海运

### 成本影响因素

#### 通航能力影响
1. 对河运价格的影响：
   - 通航能力下降 → 价格上升
   - 最低不低于基础运输成本
   
2. 对维护成本的影响：
   - 通航能力下降 → 维护成本指数增长
   - 增长速率由exponent参数控制

### 使用示例

```python
# 初始化运输经济系统
transport_economy = TransportEconomy(
    transport_cost=100,    # 基础运输成本
    transport_task=1000,   # 年度运输任务
    maintenance_cost_base=100  # 基础维护成本
)

# 计算特定通航能力下的河运价格
river_price = transport_economy.calculate_river_price(navigability=0.8)

# 计算维护成本
maintenance_cost = transport_economy.calculate_maintenance_cost(
    navigability=0.8,
    exponent=3
)

# 计算总运输成本
total_cost = transport_economy.calculate_total_transport_cost(river_ratio=0.7)
```

### 与其他模块交互

#### Map模块
- 接收通航能力数据
- 影响运输成本计算

#### Government模块
- 提供成本数据支持决策
- 接收运输比例决策

### 注意事项

1. 数值范围：
   - navigability: [0, 1]
   - river_ratio: [0, 1]
   - exponent: 建议 ≥ 2

2. 计算精度：
   - 所有价格计算结果保留2位小数
   - 使用round()函数确保精确度

3. 性能考虑：
   - 计算开销小
   - 可频繁调用
   - 适合实时决策