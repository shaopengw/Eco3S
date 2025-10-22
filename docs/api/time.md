# Time 模块 API 文档

## Time 类

### 功能概述
时间管理系统，负责管理模拟过程中的时间流逝，包括年份计算和时间步长控制。

### 初始化参数
- start_year: int - 模拟起始年份
- total_years: int - 模拟总年数

### 核心属性
- start_year: int - 起始年份
- end_year: int - 结束年份（start_year + total_years - 1）
- current_year: int - 当前年份
- total_years: int - 总年数

### 核心方法

#### 时间控制

##### step
- 功能：时间前进一年
- 参数：无
- 返回：无

##### reset
- 功能：重置到起始年份
- 参数：无
- 返回：无

##### update_total_years
- 功能：更新模拟总年数
- 参数：
  - new_total_years: int - 新的总年数
- 返回：无
- 说明：自动更新end_year

#### 时间查询

##### get_current_time
- 功能：获取当前年份字符串
- 返回：str - 当前年份

##### get_current_year
- 功能：获取当前年份数值
- 返回：int - 当前年份

##### get_start_time
- 功能：获取起始年份
- 返回：int - 起始年份

##### get_total_time_steps
- 功能：获取总时间步数
- 返回：int - 总年数

##### get_elapsed_time_steps
- 功能：获取已过时间步数
- 返回：int - 已过年数

#### 状态检查

##### is_end
- 功能：检查是否结束
- 返回：bool - 是否到达结束年份

### 使用示例
```python
# 创建时间系统（1650年开始，模拟10年）
time = Time(
    start_year=1650,
    total_years=10
)

# 时间前进一年
time.step()

# 检查是否结束
if time.is_end():
    print("模拟结束")

# 获取当前年份
current_year = time.get_current_year()

# 重置时间
time.reset()

# 更新模拟时长
time.update_total_years(15)
```

### 计算规则
- 结束年份 = 起始年份 + 总年数 - 1
- 已过年数 = 当前年份 - 起始年份
- 结束判定 = 当前年份 > 结束年份