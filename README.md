# AgentWorld

## 配置环境
```bash
conda create --name AGENTWORLD python=3.10
conda activate AGENTWORLD

pip install -r requirements.txt
```

## 运行可视化页面
```bash
cd src
python app.py
```
在一个新的终端：
```bash
cd frontend
npm run dev
```
通过 http://localhost:5173 访问 Web 界面

## 命令行运行
### 运行模拟1
配置文件及提示词位于config文件夹下，具体如下：
 - 总配置：config/simulation_config.yaml
 - 居民提示词：config/residents_prompts.yaml
 - 政府提示词：config/government_prompts.yaml
 - 叛军提示词：config/rebels_prompts.yaml
 - 职业分布及配置：config/jobs_config.yaml
 - 城市配置：config/towns_data.json

运行命令如下：
```bash
python main.py --config_path config/simulation_config.yaml
```

注意，运行时确保以下语句未被注释掉：
```python
government_decision, government_summary = await self.collect_group_decision('government', government_config)
rebellion_decision, rebellion_summary = await self.collect_group_decision('rebellion', rebellion_config)
tasks.append(resident.decide_action_by_llm(tax_rate=self.tax_rate, basic_living_cost=self.basic_living_cost))
```

### 运行模拟2
配置文件及提示词位于config_TEOG文件夹下，具体如下：
 - 总配置：config_TEOG/simulation_config.yaml
 - 居民提示词：config_TEOG/residents_prompts.yaml
 - 政府提示词：config_TEOG/government_prompts.yaml
 - 职业分布及配置：config_TEOG/jobs_config.yaml
 - 城市配置：config_TEOG/towns_data.json

运行命令如下：
```bash
python main_TEOG.py --config_path config_TEOG/simulation_config.yaml
```

### 运行模拟3-信息传播
配置文件及提示词位于config_info_propagation文件夹下，具体如下：
 - 总配置：config_info_propagation/simulation_config.yaml
 - 居民提示词：config_info_propagation/residents_prompts.yaml
 - 原传播信息：config_info_propagation/message_config.yaml
 - 调查问卷：config_info_propagation/questionnaire.yaml
 - 职业分布及配置：config_info_propagation/jobs_config.yaml
 - 城市配置：config_info_propagation/towns_data.json

运行命令如下：
```bash
python main_info_propagation.py --config_path config_info_propagation/simulation_config.yaml
```

