# AgentWorld

## 简介

AgentWorld 是一个多智能体模拟系统，支持政府、居民和叛军等多种智能体之间的互动模拟，并提供可视化界面实时展示模拟过程。

## 快速开始

### 环境配置

```bash
# 创建虚拟环境
conda create --name AGENTWORLD python=3.10
conda activate AGENTWORLD

# 安装依赖
pip install -r requirements.txt
```


### 启动可视化界面

1. **启动后端服务**
```bash
cd src
python app.py
```

2. **启动前端服务**（新终端）
```bash
cd frontend
npm install
npm install chart.js vue-chartjs
npm run dev
```

# Windows用户
```bash
start_web.bat
```


访问 http://localhost:5173 查看 Web 界面。

---

## 传统模拟场景

### 模拟1：基础多智能体交互
```bash
python entrypoints/main.py --config_path config/default/simulation_config.yaml
```

### 模拟2：TEOG 场景
```bash
python entrypoints/main_TEOG.py --config_path config/TEOG/simulation_config.yaml
```

### 模拟3：信息传播
```bash
python entrypoints/main_info_propagation.py --config_path config/info_propagation/simulation_config.yaml
```

## 数据分析

使用内置分析工具生成统计报告和可视化图表：

```bash
# 分析默认模拟结果
python src/analyzer/simulation_analyzer.py --type default

# 分析特定参数的结果
python src/analyzer/simulation_analyzer.py --type default --p 5 --y 2
```

**参数说明:**
*   `--type`: **必填**。指定模拟类型，可选值包括 `default`, `TEOG`, `info_propagation`。
*   `--p`: **可选**。用于过滤模拟结果文件夹的 `p` 初始化人口数量。
*   `--y`: **可选**。用于过滤模拟结果文件夹的 `y` 总模拟步长。

分析结果保存在 `history/<simulation_type>/analysis_results/` 目录。

## 项目结构

```
├── config/           # 所有配置文件
│   ├── default/      # 模拟1配置文件
│   ├── TEOG/         # 模拟2配置文件  
│   ├── info_propagation/  # 模拟3配置文件
│   └── template/     # 配置模板
├── frontend/         # 前端代码
├── src/              # 核心源代码
│   ├── agents/       # 智能体模块
│   ├── environment/  # 环境模块
│   ├── simulation/   # 模拟器模块
│   └── visualization/# 可视化模块
├─ entrypoints/
│    ├─ main.py       # 模拟1入口
│    ├─ main_TEOG.py  # 模拟2入口
│    └─ main_info_propagation.py  # 模拟3入口
│    └─ ```
```

## 核心功能

- 🎯 多智能体模拟与交互
- 📊 实时可视化展示
- 🎮 多种模拟场景支持
- ⚙️ 灵活的参数配置
- 📈 数据分析和报告生成

---

*确保已安装 Node.js 以运行可视化界面。*
