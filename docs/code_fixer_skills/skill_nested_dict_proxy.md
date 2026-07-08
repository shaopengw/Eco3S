# Skill S3：嵌套字典指标无 `@property` 代理

## 何时使用

- `influences.yaml` 的 `target_attr` 写了点号路径，如 `mortgage_market.debt_stock`
- 指标实际存在 `self.mortgage_market["debt_stock"]`，但影响函数写入后没变化
- 或影响函数要写入 `self.xxx`，但代码里 `self.xxx` 其实是个嵌套 dict 的键

## 根因

`LinearInfluence` / `ExprInfluence` 写结果用的是：

```python
setattr(target_obj, target_attr, result)
```

如果 `target_attr = "mortgage_market.debt_stock"`，Python 会创建一个**字面属性名** `mortgage_market.debt_stock`，而不是更新 `self.mortgage_market["debt_stock"]`。

## 必查步骤

1. **读 `influences.yaml`**
   - 找到所有 `target_attr`。
   - 把含点号的列出来，例如 `mortgage_market.debt_stock`、`macro_state.personal_income`。

2. **读 `simulator.py` 的 `__init__`**
   - 确认这些指标实际存在哪里：`self.mortgage_market["mortgage_rate"]`、`self.macro_state["personal_income"]` 等。

3. **二选一修复**
   - **方案 A（推荐）**：把 `target_attr` 改成扁平名（如 `debt_stock`），然后在 `simulator.py` 里给该指标加 `@property` 代理：
     ```python
     @property
     def debt_stock(self):
         return self.mortgage_market["debt_stock"]
     @debt_stock.setter
     def debt_stock(self, v):
         self.mortgage_market["debt_stock"] = v
     ```
   - **方案 B**：把指标从嵌套 dict 提升到 `self.debt_stock` 顶层属性，并同步改 `collect_results()` 的读取来源。

## 常见修复

```python
@property
def mortgage_rate(self) -> float:
    return self.mortgage_market.get("mortgage_rate", 8.0)

@mortgage_rate.setter
def mortgage_rate(self, value: float) -> None:
    self.mortgage_market["mortgage_rate"] = float(value)
```

## 禁止

- `target_attr: mortgage_market.debt_stock`（会被当成字面属性）。
- 在 `influences.yaml` 里写 `target_attr: macro_state.personal_income`。

## 验证

- 影响函数执行后，嵌套 dict 里的值真的变化。
- CSV 中对应列从 `constant` 变为 `varying`。
