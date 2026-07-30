# CodeFixerAgent 诊断导航

> 本文件只负责根据症状定位 skill；真正的修复步骤在 skill 文件里。

## 使用方法

1. 根据 `primary_issue_category`（来自评估报告）或当前最突出的症状，在下表找到匹配的 skill。
2. 用 `read_file` 读取对应 skill 文件。
3. 严格按 skill 中的步骤执行，不要跳过。
4. 若命中多条，按表中顺序优先读靠前的 skill。

## 症状 → Skill 映射

| 编号 | 触发条件（症状 / primary_issue_category） | Skill 文件 |
|---|---|---|
| S0 | 阶段 3.4 的 influence 虚拟数据预检失败；`primary_issue_category` 以 `influences.yaml` 开头 | 见下表 "预检子类别" |
| S1 | 指标全 0 / 恒定 / 无变化；`observed_anomalies` 中多个指标为 `constant` / `zero` | [skill_metrics_constant_zero.md](skill_metrics_constant_zero.md) |
| S2 | 已确认 `influences.yaml` 的 `execution_order.module` / `source.module` 不在 `simulator_state` 键中（预检报告 `[静默跳过]` 或手动日志 `INFLUENCE_SKIP`） | [skill_influences_silent_skip.md](skill_influences_silent_skip.md) |
| S3 | 嵌套字典指标（如 `self.mortgage_market["mortgage_rate"]`）被影响函数写入后没变化；`target_attr` 含点号 | [skill_nested_dict_proxy.md](skill_nested_dict_proxy.md) |
| S4 | Agent 行为异常、决策不输出、actions/prompts 看起来没触发 | [skill_agent_behavior_abnormal.md](skill_agent_behavior_abnormal.md) |
| S5 | 运行时报 `AttributeError` / `KeyError`；代码引用 `self.xxx` 但 `__init__` 里找不到 | [skill_attribute_key_error.md](skill_attribute_key_error.md) |
| S6 | 同一补丁反复出现；修复后问题依旧；诊断只 echo 没读修改后文件 | [skill_repeated_patches.md](skill_repeated_patches.md) |
| S7 | 指标数值爆炸（单轮变化过大、溢出、出现天文数字） | [skill_numerical_explosion.md](skill_numerical_explosion.md) |
| S8 | 上一轮改动被审计 Agent 驳回，需读审计日志后重新生成 | [skill_audit_feedback.md](skill_audit_feedback.md) |
| S9 | `agent_profile.yaml` 声明了 `government` / `rebels`，但群体不行动、`group_agents` 为空、政府决策未影响业务状态 | [skill_group_agent_missing.md](skill_group_agent_missing.md) |
| S10 | `ProjectContractPreflight` 报跨配置职业/城镇/枚举/路径不一致 | [skill_cross_config_contract.md](skill_cross_config_contract.md) |

## 阶段 3.4 influence 预检子类别

由 `InfluencePreflight` 自动注入评估报告，CodeFixer 解析后按以下子类别定位 skill：

`influences.yaml semantic contract violation` 表示 influence 虽可运行，但存在错写对象、重复执行、无消费者或数值尺度混用；使用 [skill_influences_silent_skip.md](code_fixer_skills/skill_influences_silent_skip.md) 检查精确调度与状态所有者。

| primary_issue_category | 含义 | Skill 文件 |
|---|---|---|
| `influences.yaml functions silently skipped` | 预检确认：`execution_order.module` / `source.module` 不是 `__simulator__` 也不是真实模块键，会被 `InfluenceManager` 静默跳过 | [skill_influences_silent_skip.md](skill_influences_silent_skip.md) |
| `AttributeError/KeyError in influence apply` | 预检确认：`expr` / `code` 引用未定义变量、或 `target_attr` 不存在，apply 抛异常 | [skill_attribute_key_error.md](skill_attribute_key_error.md) |
| `numerical explosion in influences` | 预检确认：虚拟数据单轮出现 `NaN` / `inf` | [skill_numerical_explosion.md](skill_numerical_explosion.md) |

> 注：
> - `placeholder: true` 的影响函数被预检忽略，不视为问题。
> - 预检子类别只覆盖 influence 机制本身的问题。**指标恒定还有多种非 influence 根因**（如 `simulator.py` 不调用影响系统、插件方法缺失等），见 S1 的 skill。

## 兜底与通用规范（极简）

- 若无法归类，先读 [skill_metrics_constant_zero.md](skill_metrics_constant_zero.md)。
- 禁止未验证假设就批量改代码；每次诊断必须引用具体文件/数据作为证据。
- 禁止新增 `step()` / 不会被 `BaseSimulator.run()` 调用的方法。
- 禁止用裸 `except Exception` 掩盖错误。
- 验证：最小配置冒烟 → CSV 中原 `constant`/`zero` 列变 `varying`。
