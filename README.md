# AgentWorld

## 配置环境
```bash
conda create --name AGENTWORLD python=3.10
conda activate AGENTWORLD

pip install -r requirements.txt
```

## 运行模拟1
```bash
python main.py --config_path config/simulation_config.yaml
```
## 运行模拟2
```bash
python main_TEOG.py --config_path config_TEOG/simulation_config.yaml
```


注意，运行时确保以下语句未被注释掉：
```python
government_decision, government_summary = await self.collect_group_decision('government', government_config)
rebellion_decision, rebellion_summary = await self.collect_group_decision('rebellion', rebellion_config)
tasks.append(resident.decide_action_by_llm(tax_rate=self.tax_rate, basic_living_cost=self.basic_living_cost))
```