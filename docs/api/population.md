# Population 模块 API 文档

## Population 类

### 功能概述
人口管理系统，负责模拟人口增长和变化，包括出生率调整、人口统计等。

### 初始化参数
- initial_population: int - 初始人口数量
- birth_rate: float - 初始出生率（默认0.01，即1%）

### 核心方法

#### 人口调控

##### update_birth_rate
- 功能：根据满意度更新出生率
- 参数：
  - satisfaction: float - 居民平均满意度(0-100)
- 返回：无
- 规则：
  - 满意度≥80：每超过80点增加0.2%出生率
  - 满意度≤50：每低于50点降低0.1%出生率
  - 50<满意度<80：保持基础出生率
  - 出生率范围：[1%, 50%]

##### birth
- 功能：增加指定数量人口
- 参数：
  - num: int - 新增人口数量
- 返回：int - 更新后总人口

##### death
- 功能：减少一个人口
- 参数：无
- 返回：无

#### 查询统计

##### get_population
- 功能：获取当前人口数量
- 参数：无
- 返回：int - 当前总人口

### 使用示例
```python
# 创建人口系统
population = Population(
    initial_population=1000,
    birth_rate=0.02
)

# 根据满意度更新出生率
population.update_birth_rate(satisfaction=85)

# 增加新生人口
population.birth(10)

# 处理人口死亡
population.death()

# 获取当前人口
total = population.get_population()
```