# Rebels 模块 API 文档

## 类概述

### Rebellion (主类)

叛军组织的主体类，负责管理整个叛军系统的运作。

#### 初始化参数
- initial_strength: int - 初始力量值
- initial_resources: float - 初始资源量
- towns: Towns - 城镇管理对象
- rebels_prompt_path: str - 叛军提示词配置文件路径

#### 核心属性
- strength: int - 当前力量值
- resources: float - 当前资源量
- towns: Towns - 城镇系统引用

#### 主要方法

##### maintain_status
- 功能：维持叛军基本运作
- 参数：无
- 返回：无
- 特点：根据当前力量自动产生基本收入（1%）

##### get_strength/get_resources
- 功能：获取当前力量/资源值
- 参数：无
- 返回：int/float - 当前力量/资源值

### OrdinaryRebel (普通叛军)

负责叛军日常行动和战略讨论的普通成员。

#### 初始化参数
- agent_id: str - 叛军ID
- rebellion: Rebellion - 叛军组织对象
- shared_pool: RebelsSharedInformationPool - 共享信息池

#### 核心属性
- role: str - 在组织中的角色
- personality: str - 性格特征
- system_message: str - 系统提示词

#### 主要方法

##### generate_opinion
- 功能：生成关于叛军行动的意见
- 参数：
  - towns_stats: list[dict] - 各城镇状态统计
- 返回：str - 生成的意见
- 依赖：
  - LLM系统
  - SharedInformationPool

##### generate_and_share_opinion
- 功能：基于已有讨论生成和分享意见
- 参数：
  - salary: float - 当前工资标准
- 返回：无
- 依赖：SharedInformationPool

##### analysis_towns_stats
- 功能：分析各城镇的力量对比
- 参数：
  - towns_stats: list[dict] - 城镇状态数据
- 返回：list[str] - 分析结果列表

### RebelLeader (叛军首领)

负责叛军最终决策的领导者。

#### 初始化参数
- agent_id: str - 首领ID
- rebellion: Rebellion - 叛军组织对象
- shared_pool: RebelsSharedInformationPool - 共享信息池

#### 核心属性
- role: str - 领导角色
- personality: str - 性格特征

#### 主要方法

##### make_decision
- 功能：基于讨论和形势做出最终决策
- 参数：
  - summary: str - 讨论总结
  - towns_stats: list[dict] - 城镇状态数据
- 返回：str - 决策内容
- 依赖：
  - SharedInformationPool
  - LLM系统

### InformationOfficer (信息官)

负责整理叛军内部讨论的专门人员。

#### 初始化参数
- agent_id: str - 信息官ID
- rebellion: Rebellion - 叛军组织对象
- shared_pool: RebelsSharedInformationPool - 共享信息池

#### 主要方法

##### summarize_discussions
- 功能：总结所有讨论内容
- 参数：无
- 返回：str - 总结报告
- 依赖：
  - SharedInformationPool
  - LLM系统

### RebelsSharedInformationPool (叛军共享信息池)

管理叛军内部讨论的信息共享系统。

#### 初始化参数
- max_discussions: int - 最大讨论数量（默认5）

#### 主要方法

##### add_discussion
- 功能：添加讨论内容
- 参数：
  - discussion: str - 讨论内容
- 返回：bool - 是否成功添加
- 特点：异步操作，线程安全

##### get_latest_discussion
- 功能：获取最新讨论
- 参数：无
- 返回：str - 最新讨论内容
- 特点：异步操作

##### get_all_discussions/clear_discussions
- 功能：获取/清空所有讨论
- 参数：无
- 返回：list[str]/无
- 特点：异步操作

## 系统交互

### 力量和资源管理
- 通过maintain_status维持基本运作
- 自动根据力量计算资源收入
- 实时跟踪各城镇叛军分布

### 决策流程
1. OrdinaryRebel分析形势并生成意见
2. 通过SharedInformationPool共享讨论
3. InformationOfficer总结讨论
4. RebelLeader根据形势作出最终决策

### 城镇分析
- 持续监控各城镇叛军和官兵数量
- 分析力量对比，为决策提供依据
- 跟踪叛军分布变化

## 配置依赖
- rebels_prompts.yaml：叛军对话提示词配置

## 外部依赖
- BaseAgent：基础智能体类
- Towns：城镇管理系统
- MemoryManager：记忆管理系统
- LLM：大语言模型接口

## 注意事项
- TODO：所有决策的后果需要存储到记忆中，供叛军学习
- 需要实现决策结果的反馈机制
- 考虑添加更复杂的资源管理系统