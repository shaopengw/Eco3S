# AgentWorld

## 安装依赖

在运行项目之前，请确保已安装所有必要的依赖项。建议使用 `conda` 创建一个虚拟环境。

```bash
conda create --name AGENTWORLD python=3.10
conda activate AGENTWORLD

pip install -r requirements.txt
```

## 功能

- **多智能体模拟**：模拟政府、居民和叛军等多种智能体之间的互动。
- **可视化界面**：通过前端界面实时展示模拟过程和结果。
- **多种模拟场景**：支持不同的配置文件和提示词，以运行多种模拟场景，包括信息传播模拟。
- **可配置性**：通过 YAML 和 JSON 文件灵活配置模拟参数、智能体提示词和环境数据。

## 项目结构
- `config/`: 存放不同模拟场景的配置文件和提示词。
- `frontend/`: 包含可视化界面的前端代码。
- `src/`: 核心源代码目录，包括智能体（agents）、环境（environment）、模拟器（simulation）和可视化（visualization）模块。
- `main.py`: 运行模拟1的主入口文件。
- `main_TEOG.py`: 运行模拟2的主入口文件。
- `main_info_propagation.py`: 运行模拟3（信息传播）的主入口文件。
- `requirements.txt`: 项目的Python依赖列表。

## 运行可视化页面
运行可视化页面需要 Node.js 环境。

### 安装 Node.js
请确保您的系统已安装 Node.js。如果未安装，请访问 [Node.js 官方网站](https://nodejs.org/) 下载并安装。

### 启动可视化界面

首先，在项目根目录下启动后端服务：

```bash
cd src
python app.py
```

然后，在一个新的终端中启动前端开发服务器：

```bash
cd frontend
npm install
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

