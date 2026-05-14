# 🌍 Eco3S: Complex Economic Social System Simulation

<div align="center">

**基于大语言模型（LLM）的多智能体复杂经济社会系统因果仿真框架**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- [![Paper](https://img.shields.io/badge/📄-Read_Paper-red)](#) -->
[![Web UI](https://img.shields.io/badge/🖥️-Vite%20%2B%20Vue-42b883)](#)

[English](README.md) · **简体中文**

</div>

---

![Eco3S Framework Architecture](assets/framework.png)
> *Eco3S 架构概览：配置 (Configuration) -> 仿真 (Simulation) -> 自动分析 (Auto-analysis)*

## 💡 框架简介 (What is Eco3S?)

随着大语言模型（LLMs）的爆发，基于智能体的建模（ABM）焕发了新的生机。然而，现有的 LLM-ABM 框架普遍面临三大科学挑战：**缺乏物理与社会的协同演化环境**、**难以进行支持因果推断的反事实推理**、以及**无法将高层研究问题自动转化为可运行的代码**。

**Eco3S** (Economic Social System Simulation) 正是为解决这些痛点而生。它不仅是一个多智能体沙盒，更是一个**研究级的可复现社会科学实验平台**。无论你是想复现顶刊论文中的宏观经济现象，还是想用自然语言从零生成一条完整的实验流水线，Eco3S 都能为你提供强大的自动化支持。

---

## 🚀 核心学术贡献 (Core Innovations)

根据本框架的底层研究，Eco3S 在以下三个维度实现了突破：

*   🌪️ **共演化环境设计 (Co-evolving Environment Design)**
    打破传统静态环境的局限，构建了**物理环境（如气候、地理）**与**社会结构（异构信息网络 HIN）**的双层动态系统。智能体的集体行为会重塑环境（如基础设施老化），而环境变迁又会反向驱动智能体的涌现行为（如移民、叛乱）。
*   ⏪ **结构化因果仿真 (Structural Causal Simulation, SCS)**
    受结构因果模型（SCM）启发，Eco3S 内置了强大的**反事实机制（Counterfactual Mechanism）**。支持在任意模拟步长保存快照、施加干预（相当于 $do$-operator，如修改政策、改变气候），并重新运行以进行严格的因果效应评估。
*   🤖 **SAR 自动化演进范式 (Simulate-Analyze-Refine)**
    告别繁琐的调参和代码编写。Eco3S 引入了由四大特化 AI Agent 组成的委员会，将高维度的自然语言研究目标，通过闭环反馈（需求分析 -> 代码/配置生成 -> 运行纠错 -> 结果优化），全自动转化为稳健的仿真模型。

---

## 🛠️ 快速开始 (Quick Start)

### 1. 配置 API 与大模型引擎
Eco3S 支持多款主流 LLM（如 GPT-4o, DeepSeek, Qwen 等）。请在项目中配置你的 API 凭证：
*   复制或创建 `.env` 文件，填入你的 API 密钥（如 `OPENAI_API_BASE_URL`, `OPENAI_API_KEY` 等）。
*   在 `config/api_models_config.yaml` 中选择并激活你想要驱动智能体的模型。

### 2. 初始化 Python 环境
我们推荐使用 Conda 隔离环境：
```bash
conda create --name Eco3S python=3.10
conda activate Eco3S
pip install -r requirements.txt
```

### 3. 启动 Web 可视化工作台
Eco3S 提供了一个现代化的前端面板，用于实时追踪仿真轨迹和数据图表。

```bash
# 终端 1: 启动 Python 后端
cd src
python app.py

# 终端 2: 启动 Vue 前端 (首次需 npm install)
cd frontend
npm install
npm run dev
```
打开浏览器访问：👉 **http://localhost:5173**

---

## 🎮 使用指南 (Usage Modes)

Eco3S 提供两种截然不同的工作模式，满足从理论验证到自由探索的全部需求。

### 模式一：传统模拟（复现顶刊基准）
系统内置了对齐高影响力经济学论文的基准场景，验证了框架在复杂决策、空间计量和认知演化上的稳健性。

| 仿真场景 | 对应文献与核心机制 | 运行入口 |
| :--- | :--- | :--- |
| 🔥 **运河衰败与叛乱**<br>*(Canal Decay & Rebellion)* | Cao & Chen (2022) <br> *基础设施退化、失业与社会动荡的空间异质性* | `python entrypoints/main.py --config_path config/default/simulation_config.yaml` |
| 🏛️ **治理的起源**<br>*(Origins of Governance)* | Allen et al. (2023) <br> *气候/水文驱动的公共品需求与集体治理的涌现* | `python entrypoints/main_TEOG.py --config_path config/TEOG/simulation_config.yaml` |
| 📢 **信息传播与废钞令**<br>*(Information Propagation)* | Banerjee et al. (2024) <br> *印度“废钞令”下的网络传播、播种策略与社会学习* | `python entrypoints/main_info_propagation.py --config_path config/info_propagation/simulation_config.yaml` |

---

### 模式二：AI 辅助模拟（SAR 自动化演进）
**“把你的 Idea 告诉 AI，剩下的交给 Eco3S。”**

通过 `run_ai_system.py`，你只需输入一段自然语言描述，系统的 AI 委员会（ProjectMaster, SimArchitect, CodeArchitect, ResearchAnalyst）将自动完成**代码生成、运行查错、结果比对与配置迭代**。

```bash
python run_ai_system.py
```

📝 **典型 Prompt 示例：**
> *"研究极端气候下，政府如何通过调整税收和基建投资来平衡财政并抑制叛乱。系统需包含政府、居民和叛军三种角色，并设定极端气候会随机发生，加速运河设施的破坏..."*

⚙️ **工作流概览：**
1. **需求解析 (Analyzing Demand)**
2. **架构设计与配置生成 (Generating Configuration)**
3. **仿真运行与异常修复 (Running & Debugging)**
4. **结果诊断与闭环优化 (Auto-analyzing & Optimizing)** *(默认最多优化 10 轮迭代)*

> **💡 提示：** 框架在泛化实验中已成功全自动合成了包括**金融市场羊群效应 (Herding Effect)**、**资产泡沫形成 (Asset Bubble)** 以及 **Schelling 种族隔离模型**等经典场景。

---

## 📊 多维数据分析 (Auto-analysis)

仿真结束后，系统支持一键生成轨迹解析、统计图表与可读的因果叙事报告。

```bash
# 基础分析 (基于 default 场景)
python src/analyzer/simulation_analyzer.py --type default

# 高阶分析：指定人口规模、模拟步长与自定义输出路径
python src/analyzer/simulation_analyzer.py --type default --p 2000 --y 10 --output_dir ./my_research_reports

# 自定义分析：显式指定要对比的历史快照文件
python src/analyzer/simulation_analyzer.py --type default --input_files history/default/data1.json history/default/data2.csv
```
生成的图表与分析报告默认保存在 `history/<type>/analysis_results/` 目录下。

---

## 📂 核心代码结构 (Project Structure)

```text
Eco3S/
├── config/                  # 运行配置中心 (YAML参数, LLM Prompts)
│   ├── default/             # 运河衰败实验配置
│   ├── TEOG/                # 治理起源实验配置
│   └── template/            # SAR 自动生成的模板库
├── entrypoints/             # 仿真执行入口点
├── src/
│   ├── agents/              # 智能体定义 (认知, 记忆, 决策机制)
│   ├── environment/         # 共演化环境设计 (气候, 空间网络, 就业市场)
│   ├── simulation/          # 核心调度器与结构化因果仿真(SCS)逻辑
│   ├── analyzer/            # 自动化数据分析模块
│   └── app.py               # Web 可视化后端
├── frontend/                # 现代化的 Vite + Vue 前端大屏
├── history/                 # 运行时输出数据、快照与分析报告
└── run_ai_system.py         # AI 自动演进模拟的主入口
```

---

## 📖 延伸阅读 (Appendix & Papers)

如果你对 Eco3S 的底层算法、AI 编排架构、时间/空间复杂度分析，以及与其他基线模型（如 System Dynamics / YuLan-OneSim / GenSim）的 Head-to-Head 对比感兴趣，请务必查阅项目根目录下的 **[Appendix.pdf](./Appendix.pdf)**。

---

## ❓ 常见问题 (FAQ)

<details>
<summary><b>1. 我应该选择传统模式还是 AI 辅助模式？</b></summary>
如果你需要严格复现论文中的 Benchmark，或进行快速的机制测试 (Sanity Check)，请使用<b>传统模式</b>；如果你有一套全新的世界观或经济学猜想，希望系统替你打工写底层代码，请果断使用 <b>AI 辅助模式</b>。
</details>

<details>
<summary><b>2. AI 生成的代码靠谱吗？我可以手动修改吗？</b></summary>
非常靠谱。Eco3S 的 CodeArchitect 生成的是标准、模块化的 Python 代码以及结构化的 YAML 配置文件。这避免了“黑盒”问题，你完全可以在生成的 `src/simulation/simulator_xxx.py` 或配置中进行二次修改和深度调优。
</details>

<details>
<summary><b>3. 模拟速度和可扩展性如何？</b></summary>
借助异步并发架构，Eco3S 在模拟数千个智能体时表现出次线性的时间复杂度。主要瓶颈通常在于你所使用的 LLM API 的并发请求速率限制（Rate Limits）。详细的吞吐量测试请参考论文的 Scalability Analysis 部分。
</details>

