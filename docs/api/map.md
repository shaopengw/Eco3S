# Map 模块 API 文档

## Map 类概述

地图系统核心类，负责管理地理信息、运河系统和城市网络。

### 初始化参数
- width: int - 地图宽度
- height: int - 地图高度
- data_file: str - 城市数据文件路径（默认'config/default/towns_data.json'）

### 核心属性
- grid: numpy.ndarray - 基础地图网格
- river_grid: numpy.ndarray - 运河网格系统
- navigability: float - 运河通航能力(0-1)
- town_graph: dict - 城市连接关系图
- town_dict: dict - 城市信息字典
- terrain_ruggedness: numpy.ndarray - 地形崎岖度数据

## 主要功能模块

### 初始化与数据加载

#### load_town_data
- 功能：从JSON文件加载城市数据和地图边界
- 参数：
  - data_file: str - JSON配置文件路径
- 返回：无

### 坐标系统

#### longitude_to_x/latitude_to_y
- 功能：地理坐标转换为地图坐标
- 参数：
  - longitude/latitude: float - 经度/纬度值
- 返回：int - 地图x/y坐标

### 运河系统管理

#### initialize_river
- 功能：初始化运河路线网络
- 参数：无
- 返回：无

#### update_river_condition
- 功能：更新运河状态
- 参数：
  - maintenance_ratio: float - 维护投入比例
- 返回：无
- 特点：
  - 维护比例≥1时通航能力+0.1×比例
  - 维护比例<1时通航能力-0.2×比例

#### decay_river_condition_naturally
- 功能：模拟运河自然衰退
- 参数：
  - climate_impact_factor: float - 气候影响因子(0-1)
- 返回：float - 当前通航能力
- 特点：包含自然衰减和气候影响

### 城市网络管理

#### initialize_town_graph
- 功能：初始化城市连接网络
- 参数：
  - max_distance: int - 最大连接距离（默认20）
- 返回：无

#### get_connected_towns
- 功能：获取与指定城市相连的城市
- 参数：
  - town_name: str - 城市名称
- 返回：list[str] - 相连城市名称列表

### 位置生成与检测

#### generate_random_location
- 功能：为指定城市生成随机位置
- 参数：
  - town_name: str - 城市名称
  - sigma: float - 正态分布标准差（默认2.0）
- 返回：tuple(int, int) - (x, y)坐标

### 地形系统

#### get_terrain_ruggedness
- 功能：获取地形崎岖度
- 参数：
  - location: tuple(int, int) - 位置坐标
- 返回：float - 崎岖度(0-1)

### 可视化功能

#### visualize_map
- 功能：可视化地图系统
- 参数：无
- 返回：无
- 显示内容：
  - 地形崎岖度（底图）
  - 运河系统（蓝色）
  - 运河城市（红色方块）
  - 其他城市（绿色三角）
  - 城市名称标注

## 常用方法组合

### 完整地图初始化
```python
map = Map(width, height, data_file)
map.initialize_map()
```

### 运河状态更新周期
```python
# 自然衰减
current_navigability = map.decay_river_condition_naturally(climate_impact)
# 政府维护
map.update_river_condition(maintenance_ratio)
```

### 城市位置查询
```python
# 获取运河城市
river_towns = map.get_river_towns()
# 获取其他城市
other_towns = map.get_non_river_towns()
```

## 配置文件依赖
- towns_data.json：城市和运河系统配置文件

## 注意事项
1. 坐标系统：
   - 左上角为原点(0,0)
   - x轴向右为正
   - y轴向下为正

2. 运河系统：
   - 通航能力范围：0-1
   - 低于0.2时发出警告
   - 受气候影响和自然衰减

3. 城市连接：
   - 基于欧几里得距离
   - 需要合理设置max_distance避免过密或过疏