# Government 模块 API 文档

## 类概述

### Government (主类)

政府主体类，负责管理整个政府系统的运作。

#### 初始化参数
- map: Map - 地图对象
- towns: Towns - 城镇管理对象
- military_strength: int - 初始军事力量
- initial_budget: float - 初始预算
- time: int - 当前时间
- transport_economy: TransportEconomy - 运输经济模型
- government_prompt_path: str - 政府提示词配置文件路径

#### 核心属性
- budget: float - 当前预算
- military_strength: int - 军事力量
- tax_rate: float - 税率(0-0.5)
- residents: dict - 居民引用字典
- transport_economy: TransportEconomy - 运输经济系统引用

#### 主要方法

##### handle_public_budget
- 功能：处理公共预算分配
- 参数：
  - budget_allocation: float - 预算分配额度
  - salary: float - 基础工资标准
  - job_total_count: int - 当前总工作岗位数
  - residents: dict - 居民字典
- 返回：无
- 依赖：Towns系统

##### maintain_canal
- 功能：维护运河系统
- 参数：
  - maintenance_investment: float - 维护投资金额
- 返回：bool - 维护是否成功
- 依赖：Map系统

##### handle_transport_decision
- 功能：处理运输决策
- 参数：
  - transport_ratio: float - 河运投入比例(0-1)
- 返回：bool - 决策是否成功
- 依赖：TransportEconomy系统

##### support_military
- 功能：进行军事投入
- 参数：
  - budget_allocation: float - 军事预算分配
- 返回：无
- 依赖：Towns系统

### OrdinaryGovernmentAgent (普通政府官员)

负责政府日常事务和政策讨论的普通官员。

#### 初始化参数
- agent_id: str - 官员ID
- government: Government - 政府对象引用
- shared_pool: government_SharedInformationPool - 共享信息池

#### 核心属性
- function: str - 职能
- faction: str - 派系
- personality: str - 性格特征

#### 主要方法

##### generate_opinion
- 功能：生成政策意见
- 参数：
  - salary: float - 当前工资标准
- 返回：str - 生成的意见
- 依赖：LLM系统

##### generate_and_share_opinion
- 功能：基于已有讨论生成和分享意见
- 参数：
  - salary: float - 当前工资标准
- 返回：无
- 依赖：SharedInformationPool

### HighRankingGovernmentAgent (高级政府官员)

负责最终决策的高级官员。

#### 初始化参数
- agent_id: str - 官员ID
- government: Government - 政府对象引用
- shared_pool: government_SharedInformationPool - 共享信息池

#### 主要方法

##### make_decision
- 功能：基于讨论做出最终决策
- 参数：
  - summary: str - 讨论总结
  - salary: float - 当前工资标准
- 返回：str - 决策内容
- 依赖：
  - SharedInformationPool
  - LLM系统

### government_SharedInformationPool (政府共享信息池)

管理政府内部讨论的信息共享系统。

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

##### get_all_discussions
- 功能：获取所有讨论
- 参数：无
- 返回：list[str] - 所有讨论内容
- 特点：异步操作

### InformationOfficer (信息官员)

负责整理和总结政府内部讨论的专门官员。

#### 初始化参数
- agent_id: str - 官员ID
- government: Government - 政府对象引用
- shared_pool: government_SharedInformationPool - 共享信息池

#### 主要方法

##### summarize_discussions
- 功能：总结所有讨论内容
- 参数：无
- 返回：str - 总结报告
- 依赖：
  - SharedInformationPool
  - LLM系统

## 系统交互

### 预算管理
- 通过handle_public_budget管理公共支出
- 通过support_military管理军事支出
- 通过maintain_canal管理基建支出

### 决策流程
1. OrdinaryGovernmentAgent生成初始意见
2. 通过SharedInformationPool共享讨论
3. InformationOfficer总结讨论
4. HighRankingGovernmentAgent作出最终决策

### 税收系统
- adjust_tax_rate：调整税率(0-50%)
- get_tax_rate：获取当前税率

## 配置依赖
- government_prompts.yaml：政府对话提示词配置

## 外部依赖
- BaseAgent：基础智能体类
- Map：地图系统
- Towns：城镇管理系统
- TransportEconomy：运输经济系统
- MemoryManager：记忆管理系统
- LLM：大语言模型接口