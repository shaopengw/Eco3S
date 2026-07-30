# Skill S1：指标全 0 / 恒定 / 无变化

## 何时使用

- 评估报告 `observed_anomalies` 显示多个指标为 `constant` / `zero`
- `get_csv_status()` 返回某列 `constant` 或 `zero`
- 模拟跑了多步但输出 CSV 几乎没变化

## 目标

找到“数据在哪里产生 → 在哪里提交 → 在哪里收集”的断裂点。

## 必查步骤（按顺序）

1. **读基类生命周期**
   - 读 `src/simulation/base_simulator.py` 的 `run()` 方法。
   - 确认 `BaseSimulator.run()` 调用的是 `update_state()` → `execute_actions()` → `collect_results()` → `save_results()`，**不是** `step()`。
   - 如果你的 `simulator.py` 覆写的是 `step()`，那它永远不会被调用。

2. **读 `simulator.py` 的三个方法**
   - `__init__`：确认指标在 `self.results` 或状态 dict 中初始化。
   - `update_state()`：确认业务逻辑/影响函数在这里被调用，并把结果写回状态。
   - `collect_results()`：确认它读取的是 `update_state()` 写回的状态，而不是未初始化的局部变量。

3. **检查 `influences.yaml` 是否真正生效**
   - 读 [skill_influences_silent_skip.md](skill_influences_silent_skip.md)。
   - “预检通过”不能只代表没抛异常；必须检查精确调度、状态所有者、消费者和数值尺度。

4. **为每个异常指标画最短数据链，不要按文件逐个猜**
   - producer：哪个 action / plugin / influence 产生它？
   - owner：权威值存放在 simulator、plugin 还是 agent profile？只能有一个稳定所有者。
   - commit：哪个生命周期方法把变化提交到 owner？
   - consumer：哪个公式、prompt 或 `collect_results()` 使用它？
   - 找不到 producer 或 consumer就是死字段；producer 和 consumer 读取不同对象就是“执行成功但数据无效”。

5. **确认 Agent 主观变量没有被公式替代**
   - 如果指标是 `placeholder: true` 或描述中明确说由 Agent 决策产生，禁止用公式代码实现。
   - 应改 `residents` 的 `actions/*.yaml` 和 `prompts/*.yaml`，并让 `simulator.py` 在 `collect_results()` 中聚合 Agent 输出。

6. **排查 `hasattr` 守卫下对"不存在的插件方法"的静默调用**（高频根因）
   - 症状：某组指标恒等于 `__init__` 初始值，日志里没有对应插件的任何输出。
   - 成因：simulator 与插件分两次生成，simulator 臆想的方法名（如 `predict_next_quarter`）
     插件并未实现；调用被 `if hasattr(plugin, 'xxx')` 包住，错配时静默跳过而非报错。
   - 发现：`grep -n "hasattr(self\.\w*plugin" simulator.py`，逐个去
     `plugins/generated/<plugin>/*.py` 核对方法是否真存在。
   - 修复：按插件真实接口改 simulator，或给插件补方法；二选一，并删掉永远为假的守卫。

   **特别注意 `get_current_metrics()` / `record_*()` 类方法**：
   - 如果 simulator 依赖插件提供当季聚合指标（如 `get_current_metrics()`），而插件没实现，
     `hasattr` 失败后 simulator 常回退到全 0 默认值。
   - 修复时给插件补的方法应满足两点：
     1. 返回 simulator 期望的所有键，且类型为数值；
     2. 若方法依赖 `current_quarter` 等状态，必须同时提供被 simulator 调用的写入/推进入口
        （如 `record_quarter_data(quarter, **kwargs)`），否则状态永远不会前进，指标会恒定不变。

7. **影响系统的"写入路径"与 `collect_results` 的"读取路径"脱节**（本仓库已实际发生）
   - 症状：`influences.yaml` 配置正确、影响函数也执行了，CSV 却仍恒定。
   - 成因：影响函数把结果写到 `self.<target>`（以 `influences.yaml` 的 `target` 命名），
     而 `collect_results()` 走 `get_xxx()` getter 读插件 / 回退初值，二者并非同一属性；
     或 influence 的 `target` 名与 CSV/结果字段名不一致，名称匹配落空。
   - 发现：核对三处命名是否指向同一个名字 —— `influences.yaml` 的 `target`/`target_attr`、
     simulator 写回的属性、`collect_results()` 读取的来源。
   - 修复：让 `collect_results()` 直接读影响函数写回的实例属性（必要时建 `target→字段` 映射），
     删除会回退初值的 getter。

8. **公式只引用 `baseline_*` 常量，缺跨回合反馈**
   - 症状：打通后指标仅第一步偏移一次，之后恒定。
   - 成因：`expr` 只用 `baseline_*`（每轮不变）加一个从不变化的驱动量，结果每轮相同。
   - 修复：把上一回合实际值注入 context 让公式递推；并确保驱动量真会随事件变化。

9. **配置驱动的事件/政策被读到空或字段错配**（症状："换了政策结果不变"）
   - 症状：调整政策/事件配置后 CSV 完全不变；不同实验结果雷同。
   - 成因：simulator 读取路径与 config 实际结构不一致 —— 键层级错位（如事件在 config 顶层，
     代码却从 `config["simulation"]` 读到空 list），或字段名错配（代码找 `type`/`magnitude`，
     config 实际是 `agency_purchase_shock`/`year`）。
   - 发现：把 simulator 里每个 `config.get(...)` / `event.get(...)` 与 config 文件逐一对照。
   - 修复：对齐读取路径与字段名；修复后事件应在日志中触发并改变对应状态量。

10. **检查初值、单位和尺度**
   - 初值为 0 且公式只有 `current * factor` 时，结果永远为 0。
   - 读取外生 CSV 的首尾、最小最大值，明确比例、百分数、指数或绝对量。
   - 检查 `min(1)` 等边界是否与 owner 的尺度一致。
   - 禁止随意加常数制造变化；应补真实基准 producer 或删除无业务来源的指标。

11. **确认是"无用指标"后，从结果收集里删除**（前述步骤打不通时的出口）
   - 前提：数据确实无变化，且对照代码与设计文件（`description.md` 等）确认该指标
     无业务含义、无下游消费者（`grep -rn "<指标名>" config/ src/` 仅产生处出现）。
   - 只从 `collect_results()` / CSV schema 里去掉该列即可；
     保留 simulator 内部的初始化与计算，以备其它逻辑仍需引用。
   - 不确定是否有消费者就不要删，回到第 1–8 步。

## 修复优先级

1. 让 `update_state()` 真正被调用并产生数据。
2. 让 `collect_results()` 读取正确的状态来源。
3. 让 `influences.yaml` 的 `module` / `target_attr` 命中。
4. 最后才调参数。

## 验证

- `py_compile` 通过。
- 小配置（pop=5、steps=2）跑完不崩溃。
- CSV 中原来 `constant` / `zero` 的列出现数值变化。
- 若走第 9 步删除：CSV 不再含该列，`py_compile` 通过，小配置跑完不崩溃。
