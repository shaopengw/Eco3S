# Resident 模块 API 文档

## 类概述

### ResidentSharedInformationPool

居民共享信息池，用于管理和共享居民之间的信息。

#### 方法

##### add_shared_info
- 功能：添加共享信息到指定类别
- 参数：
  - key: Any - 信息的键
  - value: Any - 信息的值
  - category: str - 信息类别
- 返回：无

##### get_shared_info
- 功能：获取特定类别或所有共享信息
- 参数：
  - category: str (可选) - 信息类别
- 返回：dict - 共享信息字典

### ResidentGroup

管理同一城镇的居民群组。

#### 方法

##### add_resident
- 功能：将居民添加到群组
- 参数：
  - resident: Resident - 要添加的居民对象
- 返回：无

##### set_social_network
- 功能：设置群组的社交网络
- 参数：
  - social_network: SocialNetwork - 社交网络对象
- 返回：无

##### remove_resident
- 功能：从群组中移除居民
- 参数：
  - resident_id: str - 要移除的居民ID
- 返回：无

### Resident

居民个体类，继承自BaseAgent。

#### 初始化参数
- resident_id: str - 居民唯一标识
- job_market: JobMarket - 就业市场对象
- shared_pool: ResidentSharedInformationPool - 共享信息池
- map: Map - 地图对象
- resident_prompt_path: str - 居民提示词配置文件路径
- resident_actions_path: str - 居民行为配置文件路径
- window_size: int - 记忆窗口大小（默认为3）

#### 核心属性
- employed: bool - 就业状态
- job: str - 当前工作
- income: float - 收入
- satisfaction: int - 满意度（0-100）
- health_index: int - 健康状况（1-5）
- lifespan: int - 寿命
- personality: str - 性格特征

#### 主要方法

##### employ
- 功能：为居民分配工作
- 参数：
  - job: str - 工作名称
  - salary: float (可选) - 工资金额
- 返回：无

##### unemploy
- 功能：将居民置为失业状态
- 参数：无
- 返回：无

##### receive_information
- 功能：接收并处理信息
- 参数：
  - message_content: str - 信息内容
- 返回：tuple (str, str) - (回应内容, 关系类型)

##### decide_action_by_llm
- 功能：通过LLM决定居民行动
- 参数：
  - tax_rate: float - 当前税率
  - basic_living_cost: float - 基本生活成本
  - climate_impact: float - 气候影响因子（0-1）
- 返回：
  - dict 或 tuple - 决策结果（包含行动选择、原因等）

##### execute_decision
- 功能：执行居民决策
- 参数：
  - select: str - 决策选择
  - *args, **kwargs - 附加参数
- 返回：bool - 执行是否成功

##### receive_and_decide_response
- 功能：接收公共知识通知并决定回应
- 参数：
  - message: dict - 消息内容
  - year: int - 当前年份
- 返回：tuple (str, str) - (发言内容, 关系类型)

##### update_resident_status
- 功能：更新居民状态
- 参数：
  - basic_living_cost: float - 基本生活成本
- 返回：bool - 居民是否死亡

##### migrate_to_new_town
- 功能：居民迁移到新城镇
- 参数：
  - map: Map - 地图对象
  - update_job: bool - 是否更新工作状态
- 返回：bool - 迁移是否成功

## 事件和回调

### 生命周期事件
- 出生：通过初始化触发
- 寿命更新：通过update_lifespan处理（已包含死亡判定和处理）
- 迁移：通过migrate_to_new_town处理

### 社交互动
- 信息传播：通过receive_information和generate_provocative_opinion处理
- 社群关系：通过social_network维护

## 配置依赖
- resident_prompts.yaml：居民对话提示词配置
- resident_actions.yaml：居民行为动作配置
