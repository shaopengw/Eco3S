# 模块接口文档

本文档记录了政府（Government）和叛军（Rebellion）模块中定义的类及其对外提供的公共方法接口，以及这些方法的调用关系。

## 目录

- [1. 政府模块 (Government)](#1-政府模块-government)
  - [1.1 Government 类](#11-government-类)
  - [1.2 OrdinaryGovernmentAgent 类](#12-ordinarygovernmentagent-类)
  - [1.3 HighRankingGovernmentAgent 类](#13-highrankinggovernmentagent-类)
  - [1.4 InformationOfficer 类](#14-informationofficer-类)
  - [1.5 government_SharedInformationPool 类](#15-government_sharedinformationpool-类)
- [2. 叛军模块 (Rebellion)](#2-叛军模块-rebellion)
  - [2.1 Rebellion 类](#21-rebellion-类)
  - [2.2 OrdinaryRebel 类](#22-ordinaryrebel-类)
  - [2.3 RebelLeader 类](#23-rebelleader-类)
  - [2.4 InformationOfficer 类](#24-informationofficer-类-1)
  - [2.5 RebelsSharedInformationPool 类](#25-rebelssharedinformationpool-类)

---

## 1. 政府模块 (Government)

**模块位置**: `src/agents/government.py`

### 1.1 Government 类

政府核心类，管理预算、军事力量、税率和各项政策决策的执行。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(map, towns, military_strength, initial_budget, time, transport_economy, government_prompt_path)` | 初始化政府对象 | entrypoints/main*.py | None |
| `get_budget()` | 获取当前政府预算 | `OrdinaryGovernmentAgent`, `HighRankingGovernmentAgent`, `Simulator` | float |
| `get_military_strength()` | 获取当前军事力量 | `OrdinaryGovernmentAgent`, `HighRankingGovernmentAgent`, `Simulator` | int |
| `get_tax_rate()` | 获取当前税率(范围0-0.5) | `OrdinaryGovernmentAgent`, `HighRankingGovernmentAgent`, `Simulator` | float |
| `adjust_tax_rate(adjustment)` | 调整税率 | `Simulator` | float |
| `handle_public_budget(budget_allocation, salary, job_total_count, residents)` | 处理公共预算决策，调整就业岗位 | `Simulator` | None |
| `maintain_canal(maintenance_investment)` | 维护运河基础设施 | `Simulator` | bool |
| `handle_transport_decision(transport_ratio)` | 处理运输决策(河运vs海运比例) | `Simulator` | bool |
| `support_military(budget_allocation)` | 军需拨款，增加军事力量 | `Simulator` | None |
| `print_government_status()` | 打印政府状态(调试用) | 调试代码 | None |

#### 依赖关系

**依赖的外部模块**:
- `src.environment.map.Map` - 地图对象，用于获取运河通航状态
- `src.environment.towns.Towns` - 城镇对象，用于调整就业岗位
- `src.environment.transport_economy.TransportEconomy` - 运输经济模型（可选）

**被依赖的模块**:
- 所有 Simulator 变体
- Government Agent 类

---

### 1.2 OrdinaryGovernmentAgent 类

普通政府官员，参与讨论和决策。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(agent_id, government, shared_pool)` | 初始化普通政府官员 | `src.agents.government_agent_generator.generate_government_agents` | None |
| `update_system_message()` | 更新Agent的系统提示词 | 内部调用 | None |
| `get_current_situation_prompt(maintain_employment_cost)` | 获取当前政府状态描述 | 内部调用 | str |
| `async generate_opinion(salary)` | 生成关于政策的意见 | `Simulator` (在讨论初始阶段) | str |
| `async generate_and_share_opinion(salary)` | 基于他人讨论生成并分享意见 | `Simulator` (在讨论轮次中) | None |
| `async make_decision(summary, salary)` | 根据讨论总结作出决策(非独裁模式) | `Simulator` (非独裁模式下投票) | str |

#### 依赖关系

**依赖的外部模块**:
- `src.agents.base_agent.BaseAgent` - 继承自基础Agent类
- `Government` - 获取政府状态信息
- `government_SharedInformationPool` - 共享讨论信息池

**被依赖的模块**:
- `Simulator` (所有变体)
- `government_agent_generator`

---

### 1.3 HighRankingGovernmentAgent 类

高级政府官员（决策者），在独裁模式下做最终决策，在民主模式下总结讨论。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(agent_id, government, shared_pool)` | 初始化高级政府官员 | `src.agents.government_agent_generator.generate_government_agents` | None |
| `update_system_message()` | 更新Agent的系统提示词 | 内部调用 | None |
| `async summarize_discussion_for_voting(summary, salary)` | 总结讨论，为投票提供参考(非独裁模式) | `Simulator` (非独裁模式) | str |
| `async make_decision(summary, salary)` | 根据讨论作出最终决策 | `Simulator` (独裁模式) | str |
| `print_agent_status()` | 打印Agent状态(调试用) | 调试代码 | None |

#### 依赖关系

**依赖的外部模块**:
- `src.agents.base_agent.BaseAgent` - 继承自基础Agent类
- `Government` - 获取政府状态信息
- `government_SharedInformationPool` - 共享讨论信息池

**被依赖的模块**:
- `Simulator` (所有变体)
- `government_agent_generator`

---

### 1.4 InformationOfficer 类

信息整理官，负责总结所有讨论内容。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(agent_id, government, shared_pool)` | 初始化信息整理官 | `src.agents.government_agent_generator.generate_government_agents` | None |
| `async summarize_discussions()` | 整理和总结所有讨论内容 | `Simulator` (在决策前) | str |

#### 依赖关系

**依赖的外部模块**:
- `src.agents.base_agent.BaseAgent` - 继承自基础Agent类
- `government_SharedInformationPool` - 获取所有讨论内容

**被依赖的模块**:
- `Simulator` (所有变体)

---

### 1.5 government_SharedInformationPool 类

政府官员的共享信息池，用于存储和管理讨论内容。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(max_discussions: int = 5)` | 初始化共享信息池 | `src.agents.government_agent_generator.generate_government_agents` | None |
| `async add_discussion(discussion)` | 添加讨论内容 | `OrdinaryGovernmentAgent` | bool |
| `async get_latest_discussion()` | 获取最新的讨论内容 | Government Agents | str/None |
| `async get_all_discussions()` | 获取所有讨论内容 | `OrdinaryGovernmentAgent`, `InformationOfficer` | list[str] |
| `async clear_discussions()` | 清空所有讨论内容 | `HighRankingGovernmentAgent` | None |

#### 依赖关系

**依赖的外部模块**:
- `asyncio` - 异步锁机制

**被依赖的模块**:
- `OrdinaryGovernmentAgent`
- `HighRankingGovernmentAgent`
- `InformationOfficer`

---

## 2. 叛军模块 (Rebellion)

**模块位置**: `src/agents/rebels.py`

### 2.1 Rebellion 类

叛军核心类，管理叛军力量和资源。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(initial_strength, initial_resources, towns, rebels_prompt_path)` | 初始化叛军对象 | entrypoints/main*.py | None |
| `maintain_status()` | 维持现状，获取基本收入 | 未被调用(保留方法) | None |
| `get_strength()` | 获取当前叛军力量 | `OrdinaryRebel`, `RebelLeader`, `Simulator` | int |
| `get_resources()` | 获取当前叛军资源 | `OrdinaryRebel`, `RebelLeader`, `Simulator` | int |
| `print_rebellion_status()` | 打印叛军状态(调试用) | 调试代码 | None |

#### 依赖关系

**依赖的外部模块**:
- `src.environment.towns.Towns` - 城镇对象

**被依赖的模块**:
- 所有 Simulator 变体
- Rebel Agent 类

---

### 2.2 OrdinaryRebel 类

普通叛军头目，参与讨论和提供意见。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(agent_id, rebellion, shared_pool)` | 初始化普通叛军 | `src.agents.rebels_agent_generator.generate_rebel_agents` | None |
| `update_system_message()` | 更新Agent的系统提示词 | 内部调用 | None |
| `async generate_opinion(towns_stats)` | 生成关于叛军行动的意见 | `Simulator` (在讨论初始阶段) | str |
| `async generate_and_share_opinion(salary)` | 基于他人讨论生成并分享意见 | `Simulator` (在讨论轮次中) | None |
| `analysis_towns_stats(towns_stats)` | 分析各城镇的力量对比 | 内部调用 | list[str] |

#### 依赖关系

**依赖的外部模块**:
- `src.agents.base_agent.BaseAgent` - 继承自基础Agent类
- `Rebellion` - 获取叛军状态信息
- `RebelsSharedInformationPool` - 共享讨论信息池

**被依赖的模块**:
- `Simulator` (所有变体)
- `rebels_agent_generator`

---

### 2.3 RebelLeader 类

叛军头目（最高决策者），根据讨论作出最终决策。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(agent_id, rebellion, shared_pool)` | 初始化叛军头目 | `src.agents.rebels_agent_generator.generate_rebel_agents` | None |
| `update_system_message()` | 更新Agent的系统提示词 | 内部调用 | None |
| `async make_decision(summary, towns_stats)` | 根据讨论作出最终决策 | `Simulator` | str |
| `analysis_towns_stats(towns_stats)` | 分析各城镇的力量对比 | 内部调用 | list[str] |
| `print_leader_status()` | 打印叛军头目状态(调试用) | 调试代码 | None |

#### 依赖关系

**依赖的外部模块**:
- `src.agents.base_agent.BaseAgent` - 继承自基础Agent类
- `Rebellion` - 获取叛军状态信息
- `RebelsSharedInformationPool` - 共享讨论信息池

**被依赖的模块**:
- `Simulator` (所有变体)
- `rebels_agent_generator`

---

### 2.4 InformationOfficer 类

叛军信息整理官，负责总结所有讨论内容。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(agent_id, rebellion, shared_pool)` | 初始化信息整理官 | `src.agents.rebels_agent_generator.generate_rebel_agents` | None |
| `async summarize_discussions()` | 整理和总结所有讨论内容 | `Simulator` (在决策前) | str |

#### 依赖关系

**依赖的外部模块**:
- `src.agents.base_agent.BaseAgent` - 继承自基础Agent类
- `RebelsSharedInformationPool` - 获取所有讨论内容

**被依赖的模块**:
- `Simulator` (所有变体)

---

### 2.5 RebelsSharedInformationPool 类

叛军的共享信息池，用于存储和管理讨论内容。

#### 公共方法接口

| 方法签名 | 功能描述 | 调用方 | 返回类型 |
|---------|---------|--------|---------|
| `__init__(max_discussions: int = 5)` | 初始化共享信息池 | `src.agents.rebels_agent_generator.generate_rebel_agents` | None |
| `async add_discussion(discussion)` | 添加讨论内容 | `OrdinaryRebel` | bool |
| `async get_latest_discussion()` | 获取最新的讨论内容 | Rebel Agents | str/None |
| `async get_all_discussions()` | 获取所有讨论内容 | `OrdinaryRebel`, `InformationOfficer` | list[str] |
| `async clear_discussions()` | 清空所有讨论内容 | `RebelLeader` | None |

#### 依赖关系

**依赖的外部模块**:
- `asyncio` - 异步锁机制

**被依赖的模块**:
- `OrdinaryRebel`
- `RebelLeader`
- `InformationOfficer`

---

## 3. 模块间调用关系图

```
Simulator (主控制器)
├─> Government (政府状态管理)
│   ├─> get_budget()
│   ├─> get_military_strength()
│   ├─> get_tax_rate()
│   ├─> adjust_tax_rate()
│   ├─> handle_public_budget()
│   ├─> maintain_canal()
│   ├─> handle_transport_decision()
│   └─> support_military()
│
├─> HighRankingGovernmentAgent (高级官员)
│   ├─> make_decision()
│   └─> summarize_discussion_for_voting()
│       └─> Government.get_*() [状态查询]
│
├─> OrdinaryGovernmentAgent (普通官员)
│   ├─> generate_opinion()
│   ├─> generate_and_share_opinion()
│   └─> make_decision() [非独裁模式]
│       ├─> Government.get_*() [状态查询]
│       └─> government_SharedInformationPool.add_discussion()
│
├─> InformationOfficer (政府信息官)
│   └─> summarize_discussions()
│       └─> government_SharedInformationPool.get_all_discussions()
│
├─> Rebellion (叛军状态管理)
│   ├─> get_strength()
│   └─> get_resources()
│
├─> RebelLeader (叛军头目)
│   └─> make_decision()
│       ├─> Rebellion.get_*() [状态查询]
│       └─> RebelsSharedInformationPool.clear_discussions()
│
├─> OrdinaryRebel (普通叛军)
│   ├─> generate_opinion()
│   └─> generate_and_share_opinion()
│       ├─> Rebellion.get_*() [状态查询]
│       └─> RebelsSharedInformationPool.add_discussion()
│
└─> InformationOfficer (叛军信息官)
    └─> summarize_discussions()
        └─> RebelsSharedInformationPool.get_all_discussions()
```

---

## 4. 需要抽象的接口建议

基于以上分析，建议创建以下抽象接口：

### 4.1 IFactionState (阵营状态接口)

适用于 `Government` 和 `Rebellion` 类：

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class IFactionState(ABC):
    """阵营状态管理接口"""
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取当前阵营状态的字典表示"""
        pass
    
    @abstractmethod
    def update_resources(self, amount: float) -> None:
        """更新资源/预算"""
        pass
    
    @abstractmethod
    def get_strength(self) -> int:
        """获取力量（军事力量/叛军力量）"""
        pass
```

### 4.2 IDecisionMaker (决策者接口)

适用于 `HighRankingGovernmentAgent` 和 `RebelLeader` 类：

```python
from abc import ABC, abstractmethod

class IDecisionMaker(ABC):
    """决策者接口"""
    
    @abstractmethod
    async def make_decision(self, summary: str, context: Any) -> str:
        """根据讨论总结和上下文作出决策"""
        pass
```

### 4.3 IDiscussionParticipant (讨论参与者接口)

适用于 `OrdinaryGovernmentAgent` 和 `OrdinaryRebel` 类：

```python
from abc import ABC, abstractmethod

class IDiscussionParticipant(ABC):
    """讨论参与者接口"""
    
    @abstractmethod
    async def generate_opinion(self, context: Any) -> str:
        """生成意见"""
        pass
    
    @abstractmethod
    async def generate_and_share_opinion(self, context: Any) -> None:
        """基于他人讨论生成并分享意见"""
        pass
```

### 4.4 IInformationPool (信息池接口)

适用于 `government_SharedInformationPool` 和 `RebelsSharedInformationPool` 类：

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class IInformationPool(ABC):
    """共享信息池接口"""
    
    @abstractmethod
    async def add_discussion(self, discussion: str) -> bool:
        """添加讨论内容"""
        pass
    
    @abstractmethod
    async def get_all_discussions(self) -> List[str]:
        """获取所有讨论内容"""
        pass
    
    @abstractmethod
    async def clear_discussions(self) -> None:
        """清空讨论内容"""
        pass
```

---

## 5. 下一步工作

1. **定义抽象接口**：创建 `src/interfaces/` 目录，定义上述接口
2. **实现接口**：让现有类实现相应接口
3. **依赖注入配置**：在 `simulation_config.yaml` 中添加模块实现类的配置
4. **修改 Simulator**：使用接口类型而非具体类型
5. **添加工厂模式**：创建模块工厂，根据配置动态创建实例

---

*文档更新时间: 2026-03-10*
*分析人员: GitHub Copilot*
