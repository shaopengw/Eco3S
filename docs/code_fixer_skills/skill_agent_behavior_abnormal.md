# Skill S4：Agent 行为异常

## 何时使用

- Agent 不行动、决策为空、actions/prompts 看起来没触发
- 评估报告 `primary_issue_category` 为 `prompt_logic`
- Agent 输出格式不符合 YAML schema，导致 simulator 无法解析
- 日志出现 `model_backend 未初始化，跳过决策` / 大量 `跳过决策`，但程序退出码为 0、不报错

## 必查步骤

1. **读 `actions/*.yaml`**
   - 确认每个 action 的 `name` 是否被 `simulator.py` 引用。
   - 确认 `parameters` schema 与 `simulator.py` 解析时一致。

2. **读 `prompts/*.yaml`**
   - 确认 prompt 中使用的变量名与 `simulator.py` 实际传入的一致。
   - 检查是否要求 LLM 输出特定格式（如 `decision:`、`action:`）。

3. **读 `simulator.py` 的 `execute_actions()`**
   - 确认它遍历了哪些 Agent/群体。
   - 确认它把 Agent 输出写回了哪个状态字段。

4. **确认 Action 触发链路**
   - Agent SDK 的 `act()` 是否被调用。
   - `action_decisions` 是否被正确收集。

5. **确认 Agent 已接入、拿到共享资源（静默跳过类）**
   - 轻量级（lightweight）Agent 的 `model_backend` 由所属 ResidentGroup 注入；若 Agent 没被加入 group，则 `model_backend` 恒为 `None`，决策被静默跳过。
   - 若 `simulator.py` **重写了 `integrate_new_residents`**，重点检查它：
     `new_residents` 是 **dict**（`{id: agent}`），必须 `for r in new_residents.values()`，写成 `for r in new_residents` 会遍历到 key（int）导致全员漏接入。
     优先**删除重写、回退基类实现**（基类已正确处理分组 + 社交网络接入）。
   - 旁证：社交网络节点数为 0、各城镇 `residents=0`，即说明居民未接入。

## 静默失明：为何不报错也不被自动修复

此类 bug 不抛异常、退出码 0、输出非空，且宏观变量仍在变化（由机制/影响函数驱动，与 Agent 决策无关），因此 returncode 检查、空输出检查、冒烟测试的非零/变化检查都会误判为"成功"；冒烟校验只匹配 `ERROR` 关键字，漏掉 `WARNING`。修复器是 traceback 驱动的，对"不报错但行为退化"无感知 —— 必须人工看决策日志 / Agent 活性，不能只看退出码。

## 常见修复

- prompt 变量名拼写错误 → 对齐 `simulator.py` 与 prompts/*.yaml。
- actions/*.yaml 中 `name` 与 simulator 期望的不一致 → 统一命名。
- Agent 输出没有 schema → 在 prompt 里强制要求 YAML/JSON 输出格式。
- `integrate_new_residents` 遍历 dict 的 key 而非 value → 删除重写回退基类，或改为 `.values()`。

## 禁止

- 禁止把 Agent 主观决策变量用公式硬编码到 simulator 或 influences.yaml 中。
- 禁止直接改 Agent 内部实现而不改 prompt/schema。

## 验证

- 小配置跑完后，Agent 决策日志不为空。
- simulator 能正确解析 Agent 输出并更新状态。
- 无 `model_backend 未初始化 / 跳过决策` 告警；社交网络节点数 > 0、城镇 `residents > 0`。
