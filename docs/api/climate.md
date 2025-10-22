# Climate 模块 API 文档

## ClimateSystem 类

### 功能概述
气候系统模拟器，用于管理和提供气候对环境的影响数据。主要功能包括加载气候数据和计算特定时间点的气候影响程度。

### 初始化
```python
ClimateSystem(climate_data_path: str)
```
- 功能：创建气候系统实例
- 参数：
  - climate_data_path: str - 气候数据CSV文件路径
- 属性初始化：
  - climate_data: List[float] - 气候数据列表
  - climate_impact_threshold: float - 气候影响阈值（默认0.5）

### 核心方法

#### _load_climate_data
- 功能：从CSV文件加载气候数据
- 参数：
  - path: str - 数据文件路径
- 返回：
  - List[float] - 气候影响度列表
- 特点：
  - 自动处理NaN值（替换为0）
  - 出错时返回空列表
- 数据格式要求：
  - CSV格式
  - 单列数值数据
  - 按年份顺序排列

#### get_current_impact
- 功能：获取指定年份的气候影响度
- 参数：
  - current_year: int - 当前年份
  - start_year: int - 起始年份
- 返回：
  - float - 气候影响度（0.0-1.0）
- 特点：
  - 自动计算相对年份（current_year - start_year）
  - 超出数据范围返回0.0
  - 返回绝对值结果

### 数据结构

#### 气候数据文件(climate.csv)
- 格式：CSV文件
- 内容：单列数值数据
- 每行代表：一年的气候影响值
- 数值范围：[-1.0, 1.0]
- 示例：
```csv
0.2
-0.3
0.5
0.1
...
```

### 使用示例

```python
# 初始化气候系统
climate_system = ClimateSystem("experiment_dataset/climate_data/climate.csv")

# 获取特定年份的气候影响
impact = climate_system.get_current_impact(current_year=2025, start_year=2020)
```

### 依赖关系
- 外部依赖：
  - numpy：数据处理和计算
  - typing：类型注解

### 配置要求
- climate.csv文件要求：
  - 位置：experiment_dataset/climate_data/climate.csv
  - 格式：单列数值，逗号分隔
  - 数值范围：理想范围为[-1.0, 1.0]

### 与其他模块交互
- Map模块：
  - 提供气候影响值影响运河系统的衰减
  - 通过climate_impact_threshold控制影响程度

### 注意事项
1. 数据处理：
   - CSV文件必须按年份顺序排列
   - NaN值会自动转换为0
   - 数据超出范围时返回0.0

2. 影响机制：
   - 气候影响为绝对值
   - 阈值（climate_impact_threshold）用于判断是否影响运河系统

3. 错误处理：
   - 文件加载失败返回空列表
   - 年份超出范围返回0.0