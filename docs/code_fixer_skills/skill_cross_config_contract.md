# Skill S10：跨配置事实契约不一致

## 何时使用

- `ProjectContractPreflight` 报告 `cross-config semantic inconsistency`。
- Agent 的职业、城镇、枚举值在 `agent_profile.yaml`、`jobs_config.yaml`、`towns_data.json`、prompts/actions 中名称不一致。
- `simulation_config.yaml` 的 data 路径不存在。

## 核心原则

不要新增另一份人工维护的 schema。把已经生成的结构化配置当作事实来源：

- 职业事实词表：`jobs_config.yaml.jobs_info`。
- 城镇事实词表：`towns_data.json`。
- 角色属性、choice 与约束：`agent_profile.yaml`。
- 运行时属性键：每个 attribute 的 `runtime_key`，必须是稳定 Python 标识符；`name` 只负责显示和本地化。
- 文件路径：实际文件系统。

LLM 可以创造新概念，但一旦某个结构化文件先定义了名称，后续文件必须精确复用。

## 修复步骤

1. 读取预检报告中的 `kind`、`value` 和 `canonical_values`。
2. 回到最早定义该概念的结构化文件，确认事实来源是否符合设计文档。
3. 若事实来源正确，统一修改所有下游引用；不要只改 CSV 统计或添加别名掩盖冲突。
4. 若事实来源本身错误，先修正它，再重新生成依赖它的配置。
5. 对 `missing_config_path`，使用项目实际存在文件修正路径，不创建空文件充数。
6. 对 `missing_runtime_key`，从实体接口/源码选择真实运行时属性；约束和 effects 使用 runtime_key，prompt 可继续使用显示名。

## 禁止

- 不要用模糊匹配在运行时猜测职业或城镇。
- 不要同时保留两个近义名称并在统计阶段相加。
- 不要把中文/展示属性和英文/运行时属性保存为两套独立状态；必须通过 runtime_key 别名同步。
- 不要要求岗位总数严格等于职业种类数；本 skill 只检查名称引用，不规定数量分配策略。
- 不要把模板示例当成事实来源。

## 验证

```bash
python -m pytest tests/test_project_contract_preflight.py -q
```

重新运行 `ProjectContractPreflight`，`errors` 必须为空；允许保留明确说明为有意设计的 warning。
