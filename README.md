# 🌍 Eco3S: Complex Economic Social System Simulation

<div align="center">

**A multi-agent causal simulation framework for complex economic and social systems, powered by large language models (LLMs)**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- [![Paper](https://img.shields.io/badge/📄-Read_Paper-red)](#) -->
[![Web UI](https://img.shields.io/badge/🖥️-Vite%20%2B%20Vue-42b883)](#)

**English** · [简体中文](README_zh.md)

</div>

---

![Eco3S Framework Architecture](assets/framework.png)
> *Eco3S architecture overview: Configuration → Simulation → Auto-analysis*

## 💡 Framework overview (What is Eco3S?)

As large language models (LLMs) have taken off, agent-based modeling (ABM) has gained new momentum. Yet existing LLM-ABM frameworks face three major scientific challenges: **lack of a co-evolving physical–social environment**, **difficulty supporting counterfactual reasoning for causal inference**, and **inability to turn high-level research questions into runnable code automatically**.

**Eco3S** (Economic Social System Simulation) was built to address these gaps. It is not only a multi-agent sandbox but also a **research-grade, reproducible platform for social-science experiments**. Whether you want to reproduce macro phenomena from top-journal papers or generate a full experimental pipeline from natural language alone, Eco3S provides strong automation support.

---

## 🚀 Core academic contributions (Core innovations)

Grounded in the framework’s underlying research, Eco3S advances along three dimensions:

*   🌪️ **Co-evolving environment design**
    Moving beyond static environments, Eco3S builds a **two-layer dynamic system** of **physical settings (e.g., climate, geography)** and **social structure (heterogeneous information networks, HIN)**. Collective agent behavior reshapes the environment (e.g., infrastructure aging), and environmental change in turn drives emergent agent behavior (e.g., migration, rebellion).
*   ⏪ **Structural causal simulation (SCS)**
    Inspired by structural causal models (SCM), Eco3S includes a powerful **counterfactual mechanism**: save snapshots at any simulation step, apply interventions (analogous to the $do$-operator, e.g., policy or climate changes), and re-run for rigorous causal effect estimation.
*   🤖 **SAR automation paradigm (Simulate–Analyze–Refine)**
    Leave tedious tuning and hand-written code behind. Eco3S uses a committee of four specialized AI agents to turn high-dimensional natural-language research goals into robust simulation models through closed-loop feedback (requirements analysis → code/config generation → run-and-fix → result refinement).

---

## 🛠️ Quick start

### 1. Configure APIs and LLM engines
Eco3S supports mainstream LLMs (e.g., GPT-4o, DeepSeek, Qwen). Configure your API credentials in the project:
*   Copy or create a `.env` file and fill in your API keys (e.g., `OPENAI_API_BASE_URL`, `OPENAI_API_KEY`, etc.).
*   In `config/api_models_config.yaml`, select and activate the model you want to drive the agents.

### 2. Initialize the Python environment
We recommend an isolated Conda environment:
```bash
conda create --name Eco3S python=3.10
conda activate Eco3S
pip install -r requirements.txt
```

### 3. Launch the Web visualization workbench
Eco3S provides a modern front-end panel for live simulation traces and charts.

```bash
# Terminal 1: start the Python backend
cd src
python app.py

# Terminal 2: start the Vue front end (run npm install on first use)
cd frontend
npm install
npm run dev
```
Open your browser at: 👉 **http://localhost:5173**

---

## 🎮 Usage modes

Eco3S offers two distinct modes, from theory validation to open exploration.

### Mode 1: Traditional simulation (reproducing top-journal benchmarks)
The system ships with benchmark scenarios aligned to high-impact economics papers, validating robustness on complex decisions, spatial econometrics, and cognitive evolution.

| Simulation scenario | Reference and core mechanism | Entry command |
| :--- | :--- | :--- |
| 🔥 **Canal decay & rebellion**<br>*(Canal Decay & Rebellion)* | Cao & Chen (2022) <br> *Spatial heterogeneity of infrastructure decay, unemployment, and social unrest* | `python entrypoints/main.py --config_path config/default/simulation_config.yaml` |
| 🏛️ **Origins of governance**<br>*(Origins of Governance)* | Allen et al. (2023) <br> *Climate/hydrology-driven demand for public goods and emergence of collective governance* | `python entrypoints/main_TEOG.py --config_path config/TEOG/simulation_config.yaml` |
| 📢 **Information propagation & demonetization**<br>*(Information Propagation)* | Banerjee et al. (2024) <br> *Network propagation, seeding strategies, and social learning under India’s demonetization* | `python entrypoints/main_info_propagation.py --config_path config/info_propagation/simulation_config.yaml` |

---

### Mode 2: AI-assisted simulation (SAR automation)
**“Tell the AI your idea—Eco3S handles the rest.”**

With `run_ai_system.py`, you only need a natural-language description. The AI committee (ProjectMaster, SimArchitect, CodeArchitect, ResearchAnalyst) automatically performs **code generation, run-and-debug, result comparison, and configuration iteration**.

```bash
python run_ai_system.py
```

📝 **Example prompt:**
> *“Study how, under extreme climate, a government balances the budget and curbs rebellion by adjusting taxes and infrastructure investment. The system should include government, residents, and rebels, with extreme weather occurring at random and accelerating damage to canal facilities…”*

⚙️ **Workflow overview:**
1. **Analyzing demand**
2. **Architecture design and configuration generation**
3. **Simulation run and error repair**
4. **Result diagnosis and closed-loop optimization** *(up to 10 optimization rounds by default)*

> **💡 Tip:** In generalized experiments, the framework has fully automated synthesis of classic setups including **financial-market herding**, **asset-bubble formation**, and the **Schelling segregation model**.

---

## 📊 Multi-dimensional data analysis (Auto-analysis)

After a simulation, the system can one-click generate trajectory parsing, statistical charts, and readable causal narratives.

```bash
# Basic analysis (default scenario)
python src/analyzer/simulation_analyzer.py --type default

# Advanced analysis: set population size, simulation horizon, and custom output path
python src/analyzer/simulation_analyzer.py --type default --p 2000 --y 10 --output_dir ./my_research_reports

# Custom analysis: explicitly list historical snapshot files to compare
python src/analyzer/simulation_analyzer.py --type default --input_files history/default/data1.json history/default/data2.csv
```
Charts and analysis reports are saved by default under `history/<type>/analysis_results/`.

---

## 📂 Core project structure

```text
Eco3S/
├── config/                  # Run configuration hub (YAML parameters, LLM prompts)
│   ├── default/             # Canal decay experiment
│   ├── TEOG/                # Origins of governance experiment
│   └── template/            # Templates for SAR auto-generation
├── entrypoints/             # Simulation entry points
├── src/
│   ├── agents/              # Agent definitions (cognition, memory, decision rules)
│   ├── environment/         # Co-evolving environment (climate, spatial networks, labor market)
│   ├── simulation/          # Core scheduler and structural causal simulation (SCS)
│   ├── analyzer/            # Automated data analysis
│   └── app.py               # Web visualization backend
├── frontend/                # Modern Vite + Vue dashboard
├── history/                 # Runtime outputs, snapshots, and analysis reports
└── run_ai_system.py         # Main entry for AI-driven simulation
```

---

## 📖 Further reading (Appendix & papers)

For underlying algorithms, AI orchestration, time/space complexity, and head-to-head comparisons with baselines (e.g., System Dynamics / YuLan-OneSim / GenSim), see **[Appendix.pdf](./Appendix.pdf)** in the project root.

---

## ❓ FAQ

<details>
<summary><b>1. Should I use traditional mode or AI-assisted mode?</b></summary>
Use <b>traditional mode</b> when you need strict paper-aligned benchmarks or quick mechanism checks (sanity tests); use <b>AI-assisted mode</b> when you have a new world model or economic hypothesis and want the system to draft the underlying code for you.
</details>

<details>
<summary><b>2. How reliable is AI-generated code? Can I edit it by hand?</b></summary>
Very reliable. Eco3S’s CodeArchitect emits standard, modular Python and structured YAML configs—avoiding a “black box.” You can freely edit generated files such as `src/simulation/simulator_xxx.py` or configs for fine-tuning.
</details>

<details>
<summary><b>3. How fast and scalable is simulation?</b></summary>
With an async concurrent architecture, Eco3S shows sublinear time complexity for thousands of agents. The usual bottleneck is your LLM API’s rate limits. See the paper’s scalability analysis for throughput details.
</details>

