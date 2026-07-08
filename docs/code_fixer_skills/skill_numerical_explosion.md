# Skill S7：数值爆炸 / 指标溢出

## 何时使用

- 指标单轮变化倍数 >2 或绝对值超过 1e6
- 房价指数、投资额等出现天文数字
- 失业率、利率等应被约束的指标跳到 0 或负数

## 根因

`influences.yaml` 中的公式没有按 `LinearInfluence` / `ExprInfluence` 的实际语义书写，或缺少边界保护。

常见模式：

1. `LinearInfluence` 误用 `mode: multiply`。
   - 实际计算：`current * (coefficient * variable + constant)`
   - 错误示例：`coefficient: 0.18`, `variable: origination_volume`, `mode: multiply`
     - 结果：`residential_investment *= 0.18 * 101 = 18.2`（爆炸）
   - 正确做法：改为 `mode: add`，或 `expr: baseline * (1 + 0.18 * (x - baseline) / baseline)`

2. `ExprInfluence` 使用绝对差而非相对变化。
   - 错误示例：`current_price_index + (current_investment - baseline) * 0.45`
   - 正确做法：使用对数/百分比变化，或加 `min/max` 边界。

3. 指标缺少硬边界。
   - 即使公式合理，长期累积也可能溢出。
   - 必须在 simulator.py 或 expr 中加 `min/max` 裁剪。

## 必查步骤

1. 跑隔离测试：
   ```bash
   python src/utils/influence_test_runner.py --project <项目名>
   ```
   查看输出中的 `[ANOMALY]` 行。

2. 读 `src/influences/builtin.py`，确认 `LinearInfluence.apply` 和 `ExprInfluence.apply` 的公式语义。

3. 检查异常影响函数：
   - 是否 `mode: multiply` 但 coefficient 与变量量级不匹配？
   - 是否 `expr` 中使用绝对差？
   - 是否缺少 `min/max` 边界？

4. 检查 simulator.py 是否在 `update_state()` 中对关键指标做边界裁剪。

## 修复优先级

1. 先改 influences.yaml 公式（最常见根因）。
2. 再在 simulator.py 加硬边界作为兜底。
3. 最后调整初始值/配置。

## 验证

- 隔离测试无 `[ANOMALY]`。
- 关键指标单轮变化率在 `[-0.5, 2.0]` 内（除非是刻意的外生冲击）。
- 最小配置冒烟通过。
- CSV 中相关指标从爆炸/恒定变为合理波动。

## 禁止

- 不要给所有指标无脑乘衰减系数；先定位具体影响函数。
- 不要在 influences.yaml 里把 `placeholder: true` 的 Agent 主观变量改成公式。
