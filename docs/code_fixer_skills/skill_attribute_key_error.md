# Skill S5：`AttributeError` / `KeyError`

## 何时使用

- 运行时报错 `AttributeError: 'Simulator' object has no attribute 'xxx'`
- 或 `KeyError: 'xxx'`
- 或代码里引用 `self.xxx` 但 `__init__` 里找不到

## 必查步骤

1. **定位报错行**
   - 从 Traceback 找到出错的文件、方法、行号。

2. **检查 `__init__` 初始化**
   - 读 `simulator.py` 的 `__init__`。
   - 确认 `self.xxx` 是否在 `__init__` 中赋值。
   - 如果指标存在嵌套 dict，确认外层 dict 已初始化。

3. **检查父类初始化**
   - 读 `src/simulation/base_simulator.py` 的 `__init__`。
   - 确认子类 `super().__init__()` 被正确调用。

4. **检查方法名是否真实存在**
   - 用 `search_project` 搜索报错的方法名。
   - 确认调用处的方法名没有拼写错误。

## 常见修复

- 在 `__init__` 中补初始化：`self.xxx = default_value`。
- 拼写错误：统一调用处与定义处的方法名/键名。
- 缺少 `super().__init__()`：补上父类初始化。
- `influence_manager` 调用了不存在的方法（如 `.update()` / `.apply()` / `.step()`）：
  `InfluenceManager` 唯一入口是 `apply_all_influences(simulator_state, target_root=self)`；
  改用该方法，并把返回的 `global_context` 写回状态（已有 `_refresh_*` 桥则调用它）。
  `target_root=self` 必传，漏传不报错但结果写不回、指标恒定。
  若该错误调用被 `try/except` 包住，则不崩溃而表现为“指标恒定”，见 [skill_metrics_constant_zero.md](skill_metrics_constant_zero.md)。

## 禁止

- 用裸 `except Exception` 掩盖 `AttributeError` / `KeyError`。
- 不读 `__init__` 就盲目在调用处加 `hasattr` 防御。

## 验证

- 同样输入下不再报该错误。
- `py_compile` 通过。
