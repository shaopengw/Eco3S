# Towns 模块 API 文档

## Towns 类

### 功能概述
城镇管理系统，负责管理城镇、居民分配和就业市场。

### 初始化参数
- map: Map - 地图系统对象
- initial_population: int - 初始人口数量（默认10）
- job_market_config_path: str - 就业市场配置文件路径

### 城镇数据结构
```python
{
    'info': {
        'name': str,
        'location': tuple(x, y),
        'type': str  # 'canal' 或 'non_canal'
    },
    'residents': dict,  # 居民字典
    'resident_group': ResidentGroup,
    'job_market': JobMarket
}
```

### 核心方法

#### 城镇初始化
##### initialize_towns
- 功能：初始化所有城镇信息
- 参数：
  - map: Map - 地图对象
  - initial_population: int - 初始人口
  - job_market_config_path: str - 配置路径
- 返回：无

##### initialize_resident_groups
- 功能：初始化居民群组并分配工作
- 参数：
  - residents: Dict[int, Resident] - 居民字典
- 返回：无

#### 居民管理
##### add_resident
- 功能：添加居民到指定城镇
- 参数：
  - resident: Resident - 居民对象
  - town_name: str - 城镇名称
- 返回：无

##### remove_resident_in_town
- 功能：从城镇移除居民
- 参数：
  - resident_id: int - 居民ID
  - town_name: str - 城镇名称
  - job_type: str - 工作类型（可选）
- 返回：bool - 是否成功

#### 就业市场管理
##### process_town_job_requests
- 功能：处理城镇求职请求
- 参数：
  - town_job_requests: dict - 城镇求职信息
- 返回：dict - 处理结果

##### add_jobs_across_towns
- 功能：在所有城镇增加岗位
- 参数：
  - add_job_amount: int - 增加数量
  - specific_job: str - 指定工作类型（可选）
- 返回：无

##### remove_jobs_across_towns
- 功能：在所有城镇减少岗位
- 参数：
  - total_jobs_to_remove: int - 减少数量
  - residents: dict - 居民字典
- 返回：无

##### adjust_job_market
- 功能：根据运河状态调整就业市场
- 参数：
  - change_rate: float - 变化率(-1到1)
  - residents: dict - 居民字典
- 返回：无

#### 查询方法
##### get_nearest_town
- 功能：获取最近的城镇
- 参数：
  - location: tuple(x, y) - 位置坐标
- 返回：str - 城镇名称

##### get_town_residents
- 功能：获取城镇所有居民
- 参数：
  - town_name: str - 城镇名称
- 返回：dict - 居民字典

##### get_town_job_market
- 功能：获取城镇就业市场
- 参数：
  - town_name: str - 城镇名称
- 返回：JobMarket - 就业市场对象

### 依赖关系
- Map：地图系统
- ResidentGroup：居民群组管理
- JobMarket：就业市场系统
- Resident：居民系统