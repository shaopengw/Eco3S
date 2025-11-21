# Time 模块 API 文档

## Time 类

### 功能概述
时间管理系统，负责管理模拟过程中的时间流逝，支持任意时间单位的时间步长控制。

### 初始化参数
- start_time: int - 模拟起始时间
- total_steps: int - 模拟总时间步数

### 核心属性
- start_time: int - 起始时间
- end_time: int - 结束时间（start_time + total_steps - 1）
- current_time: int - 当前时间
- total_steps: int - 总时间步数

### 核心方法

#### 时间控制

##### step
- 功能：时间前进一个时间步
- 参数：无
- 返回：无

##### reset
- 功能：重置到起始时间
- 参数：无
- 返回：无

##### update_total_steps
- 功能：更新模拟总时间步数
- 参数：
  - new_total_steps: int - 新的总时间步数
- 返回：无
- 说明：自动更新end_time

#### 时间查询

##### get_elapsed_time_steps
- 功能：获取已过时间步数
- 返回：int - 已过时间步数

#### 状态检查

##### is_end
- 功能：检查是否结束
- 返回：bool - 是否到达结束时间

### 使用示例
```python
# 创建时间系统（从时间1650开始，模拟10个时间步）
time = Time(
    start_time=1650,
    total_steps=10
)

# 时间前进一个时间步
time.step()

# 检查是否结束
if time.is_end():
    print("模拟结束")

# 获取当前时间
current_time = time.current_time

# 重置时间
time.reset()

```

### 计算规则
- 结束时间 = 起始时间 + 总时间步数 - 1
- 已过时间步数 = 当前时间 - 起始时间
- 结束判定 = 当前时间 > 结束时间

### 设计说明
- 时间单位灵活，可以是秒、分钟、小时、天、月、年等任意单位
- 支持任意起始时间点和时间步长
- 提供整数和字符串两种时间表示方式