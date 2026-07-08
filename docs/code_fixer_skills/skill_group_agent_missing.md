# Skill S9：政府/叛军等插件群体未激活

## 何时使用

- `agent_profile.yaml` 声明了 `entity_type: government` / `rebels`，但模拟中官员/叛军不行动
- `simulator.group_agents` 为空或缺少对应群体
- 日志中无政府/叛军 LLM 决策输出
- 政府决策未影响 simulator 业务状态（如 `agency_purchase_shock` 不变）

## 必查步骤

1. **查 `modules_config.yaml`**
   - `selected_modules` 必须包含 `government`（或 `rebellion`）。
   - 若缺省，添加并重新运行。

2. **查 `simulator.py` 是否继承 `BaseSimulator` 并透传 `group_agents`**
   - `__init__` 必须显式接收 `group_agents=None`。
   - 必须 `super().__init__(..., group_agents=group_agents)`，不能用 `**_unused` 吞掉。

3. **查 `agent_profile.yaml`**
   - 群体定义必须有 `entity_type: government` 或 `entity_type: rebels`。
   - 可选：配 `count` / `ranks`，否则依赖下一步的 `group_counts`。

4. **查 `simulation_config.yaml`**
   - `simulation.group_counts.<name>` 或 `simulation.group_counts.<entity_type>` 必须指定数量。
   - 例如：`group_counts: {federal_housing_agency: 2}` 或 `group_counts: {government: 2}`。

5. **查决策是否落地（政府已生成但不生效）**
   - 读 `simulator.py __init__` 是否注册 `decision_handler`。
   - 政府插件对象必须有 `register_decision_handler`。
   - 决策 JSON 字段名（如 `purchase_volume`）必须与 handler 注册键一致。

6. **查提示词文件键名**
   - 政府 prompt yaml 必须包含：
     `ordinary_government_agent_system_message`、`high_ranking_government_agent_system_message`、
     `generate_opinion_prompt`、`generate_and_share_opinion_prompt`、
     `make_decision_prompt`、`summarize_discussions_prompt`
   - 叛军 prompt yaml 必须包含：
     `ordinary_rebel_system_message`、`rebel_leader_system_message`、
     `generate_opinion_prompt`、`generate_and_share_opinion_prompt`、
     `make_decision_prompt`、`summarize_discussions_prompt`
   - 自定义项目 prompt 不能只写 `system_message` / `policy_discussion_prompt` 等通用角色模板键，必须与运行时框架键名一致。

## 常见修复

- 缺模块 → 加 `government` / `rebellion` 到 `selected_modules`。
- `group_agents` 为空 → 修复 simulator `__init__` 透传。
- 群体数量为 0 → 加 `group_counts` 或 `count` / `ranks`。
- 决策不落地 → 在项目 simulator 中 `register_decision_handler(key, handler)`。
- 提示词报 `KeyError: 'generate_opinion_prompt'` 等 → 按步骤 6 补齐 prompt yaml 键名，或改用 `config/template/entities/government/prompts.yaml` / `config/template/entities/rebels/prompts.yaml` 作为模板。

## 决策处理器示例

```python
from src.simulation.plugin_access import require_module

try:
    gov_obj = getattr(require_module(self.plugin_registry, "government"), "service", None)
    if gov_obj is None:
        gov_obj = require_module(self.plugin_registry, "government")

    def _handle_purchase_volume(value, _decision_data, simulator_context=None):
        if simulator_context is None:
            return
        baseline = getattr(simulator_context, "baseline_agency_purchases", 100000.0)
        purchase_amount = float(value) * 1e9
        shock = (purchase_amount - baseline) / max(baseline, 1.0)
        simulator_context.agency_purchase_shock += shock

    if hasattr(gov_obj, "register_decision_handler"):
        gov_obj.register_decision_handler("purchase_volume", _handle_purchase_volume)
except Exception as e:
    self.logger.warning(f"注册政府决策处理器失败: {e}")
```

## 禁止

- 禁止把项目专有决策逻辑写进通用 `src/agents/government.py` / `src/agents/rebels.py`。
- 禁止在政府/叛军未启用时静默吞掉异常，必须记录 warning。
- 禁止让旧 `Simulator`（不继承 `BaseSimulator`）接收 `group_agents`；构建器会自动兼容。

## 验证

- `len(simulator.group_agents.get("government", {}).get("agents", []))` 等于配置数量。
- 运行一回合后，日志出现政府/叛军决策输出。
- 注册 handler 的字段被正确更新；未注册时仅记录日志不抛异常。
