# Skill S2：`influences.yaml` 执行与语义契约

## 何时使用

在确认以下**证据**后使用本 skill：

1. `InfluenceManager` 执行日志或预检报告显示 `module_missing` / `silent_skip`。
2. 或者你手动在 `src/influences/influence_manager.py:_apply_module_influence` 处加日志后，观察到某条 `execution_order` 记录被执行但对应的 `module` 在 `simulator_state` 中不存在。
3. 预检报告显示错写对象、重复调度、死输出或尺度坍缩。
4. **不要**仅因为“指标恒定”就直接改公式；先检查 producer → owner → consumer。

## 根因

`InfluenceManager._apply_module_influence()` 按 `execution_order` 在 `simulator_state` 中查找模块键：

```python
module = simulator_state.get(module_name)
if module is None:
    return   # 整条影响函数被静默跳过，不抛异常、不打 ERROR 日志
```

这段逻辑真实存在于 `src/influences/influence_manager.py:149-151`。只要 `module_name` 不在 `simulator_state`，对应的影响函数就不会执行。

更隐蔽的是“执行成功但语义无效”：source 模块被误当成写入对象；同一 target 的多条 influence 因旧式调度被重复执行；target/target_attr/CSV 名称不一致；输出没有消费者；或 0–100 与 0–1 尺度混用。

## 精确调度与状态所有者

新生成配置必须让每条 influence 在 `execution_order` 中携带唯一名称：

```yaml
execution_order:
  - module: __simulator__
    target: navigability
    influence: climate_to_navigability
```

逐条确认：name 全局唯一且恰好调度一次；`source.module` 只表示输入来源；`target == target_attr == simulator 状态属性`；输出至少有一个真实消费者。旧式二元顺序仍兼容，但同一 target 有多条 influence 时必须升级。

## 当前观察

- 截至本次检查，仓库内 4 个真实项目（`federal_housing_policy_impact`、`asset_market_bubble_sim`、`price_discovery_simulation`、`social_unrest_impact_sim`）的 `influences.yaml` 与 `simulator_state` 键**均匹配**，未观察到本 bug。
- 阶段 3.4 的 `InfluencePreflight` 把它作为**防御性检查**：如果未来 LLM 生成的 `module` 写成业务概念名（如 `housing_policy_simulation`）而非真实键，预检会立即捕获。

## 必查步骤（先确认，再修复）

### 步骤 1：确认影响函数真的被跳过

不要凭症状猜测，必须拿到直接证据：

- 方法 A（推荐）：运行阶段 3.4 预检
  ```bash
  python -m src.utils.influence_test_runner --project <项目名> --preflight
  ```
  若输出 `[静默跳过] module=...`，则确认命中本 bug。

- 方法 B：手动加临时日志
  在 `src/influences/influence_manager.py:149` 处加：
  ```python
  if module is None:
      self.logger.warning(f"INFLUENCE_SKIP module={module_name} target={target_name}")
      return
  ```
  运行模拟，若日志出现 `INFLUENCE_SKIP`，则确认命中。

- 方法 C：静态核对
  1. 读 `influences.yaml` 的 `execution_order`，列出所有 `module`。
  2. 读 `simulator.py` 的 `update_state()` / 主循环，列出 `simulator_state` 的所有顶层键（包括 `build_simulator_state_from_registry` 注入的 `modules_config.selected_modules`、以及 `extra_state` 注入的键）。
  3. 若存在某个 `module` 既不等于 `__simulator__`、也不在键集合中，则确认会跳过。

### 步骤 2：确认不是其他根因

指标恒定 / 全 0 的常见根因还有：

| 根因 | 如何区分 | 对应 skill |
|---|---|---|
|`simulator.py` 覆写了 `step()` 但基类调用的是 `update_state()`|`grep "def step" simulator.py`| [skill_metrics_constant_zero.md](skill_metrics_constant_zero.md) |
|`simulator.py` 调用插件不存在的方法，被 `hasattr` + `try/except` 静默 fallback|`grep -n "hasattr(self\.\w*plugin" simulator.py` 并去 `plugins/generated/<plugin>/*.py` 核对|[skill_metrics_constant_zero.md](skill_metrics_constant_zero.md) |
|`influences.yaml` 的 `module` 名缺失|本 skill |
|`target_attr` 写了嵌套字典路径但对象不支持|写入后嵌套 dict 无变化|[skill_nested_dict_proxy.md](skill_nested_dict_proxy.md) |

**在没确认是 module 名缺失之前，不要把指标恒定归因于本 skill。**

## 修复方法（仅在确认后使用）

二选一：

### 方案 A：把 `module` 改成 `__simulator__`（最常用）

如果你希望影响函数直接写回到 simulator 实例的属性：

```yaml
# 修改前
execution_order:
  - module: housing_policy_simulation
    target: gse_purchases

# 修改后
execution_order:
  - module: __simulator__
    target: gse_purchases
```

同时检查 `source.module`：
```yaml
source:
  module: __simulator__
```

### 方案 B：让 `update_state()` 把该模块注入 `simulator_state`

如果你确实需要一个独立的模块对象：

```python
simulator_state = {
    ...
    "housing_policy_simulation": self.housing_policy_sim,
}
self.influence_manager.apply_all_influences(simulator_state, target_root=self)
```

## 禁止

- 不要只改 `target` 不改 `module`。
- 不要看到指标恒定就直接改 `influences.yaml`，要先按“步骤 2”排除其他根因。
- 不要用 `hasattr`、默认值或动态新增属性掩盖写错状态所有者。
- 不要让同一业务效果同时由 LLM action handler 和 influence 自动执行。

## 验证

1. 重新运行阶段 3.4 预检：`python -m src.utils.influence_test_runner --project <项目名> --preflight`，不得再报告静默跳过或语义契约错误。
2. 或重新跑最小规模模拟，检查 CSV 中对应指标是否从恒定变为变化。
3. 若仍恒定，回到“步骤 2”排查其他根因。
