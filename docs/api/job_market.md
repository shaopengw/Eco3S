# JobMarket 模块 API 文档

## JobMarket 类

### 功能概述
就业市场管理系统，负责管理工作岗位分配、薪资和就业状态。

### 初始化参数
- town_type: str - 城镇类型("沿河"或"非沿河")
- initial_jobs_count: int - 初始工作总数（默认100）
- config_path: str - 配置文件路径（可选）

### 数据结构
```python
jobs_info = {
    "职业名称": {
        "total": int,          # 总岗位数
        "employed": {          # 已雇佣人员
            resident_id: salary # 工资
        },
        "base_salary": float  # 基础工资
    }
}
```

### 核心方法

#### 岗位管理

##### add_job/remove_job
- 功能：添加/移除工作岗位
- 参数：
  - job: str - 工作名称
  - num: int - 数量（仅add_job）
- 返回：无

##### add_random_jobs
- 功能：随机增加工作岗位
- 参数：
  - num_jobs: int - 增加数量
  - specific_job: str - 指定职业（可选）
- 返回：无

##### remove_random_jobs
- 功能：随机减少工作岗位
- 参数：
  - num_jobs: int - 减少数量
  - residents: dict - 居民字典
- 返回：无

#### 就业管理

##### assign_job
- 功能：随机分配工作
- 参数：
  - resident: Resident - 居民对象
- 返回：无

##### assign_specific_job
- 功能：分配指定工作
- 参数：
  - resident: Resident - 居民对象
  - job_type: str - 工作类型
  - actual_salary: float - 实际工资（可选）
- 返回：bool - 是否成功

##### process_job_applications
- 功能：处理求职申请
- 参数：
  - job_requests: list - 求职申请列表
- 返回：tuple(hired_list, total_expense)

#### 查询方法

##### get_available_jobs
- 功能：获取可用工作
- 返回：dict - 工作空缺情况

##### get_job_salary
- 功能：获取职业工资
- 参数：
  - job_type: str - 职业类型
- 返回：float - 工资金额

##### get_job_statistics
- 功能：获取职业统计
- 参数：
  - job_type: str - 职业类型
- 返回：tuple(total, employed, salary)

#### 特殊功能

##### adjust_canal_maintenance_jobs
- 功能：调整运河维护工作
- 参数：
  - change_rate: float - 变化率(-1到1)
  - residents: dict - 居民字典
- 返回：无

### 配置文件结构
```yaml
jobs_info:
  职业名称:
    base_salary: float
professions_ratio:
  职业名称:
    沿河: [min, max]
    非沿河: [min, max]
```

### 依赖关系
- yaml: 配置文件解析
- Resident: 居民系统
- random: 随机分配
- collections.defaultdict: 数据结构