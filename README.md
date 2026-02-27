# Eco3S

**Languages:** [English](README.md) | [中文](README_zh.md)

---

## Introduction

**Eco3S** (Complex **Eco**nomic **S**ocial **S**ystem **S**imulation) is a multi-agent simulation framework designed for economic research and policy analysis. It leverages Large Language Models (LLMs) to endow agents with sophisticated perception, reasoning, and decision-making capabilities, bridging gaps in traditional simulation methods regarding environmental interaction, counterfactual inference, and scenario generalization.

### Key Highlights
1.  **Delicate Environment Design**: Simulates dynamically evolving physical environments (climate, geography), heterogeneous information networks (HIN), and dual "individual-collective" decision-making modes.
2.  **Counterfactual Mechanism**: Supports snapshot saving at any simulation step, rollback, and intervention modification (policies, environmental parameters) for rigorous causal effect evaluation.
3.  **Auto-Simulation with Human Feedback**: Automatically transforms natural language requirements into experimental scenarios through a LLM agent-based orchestration framework(ProjectMasterAgent, SimArchitectAgent, CodeArchitectAgent, and ResearchAnalystAgent).
4.  **Auto-Analysis**: Automatically parses simulation trajectories to generate statistical charts and causal interpretation reports.

## Quick Start

### Environment Setup

```bash
# Create virtual environment
conda create --name Eco3S python=3.10
conda activate Eco3S

# Install dependencies
pip install -r requirements.txt
```

### Launch Visualization Interface

**Option 1: One-Click Start for Windows Users**
```bash
start_web.bat
```

**Option 2: Manual Start**
1. Start backend service
```bash
cd src
python app.py
```

2. Start frontend service (new terminal)
```bash
cd frontend
npm install  # First run only
npm install chart.js vue-chartjs  # First run only
npm run dev
```

Visit http://localhost:5173 to view the web interface.

---

## Usage

### I. Traditional Simulation Mode

Eco3S includes multiple benchmark scenarios based on replications of top-tier economic/historical research:
1.  **Canal Decay and Rebellion**: Replicates Cao & Chen (2022) research, exploring the impact of transportation infrastructure evolution (Grand Canal) on social stability.
2.  **Origins of Governance (TEOG)**: Based on Allen (2023) findings, simulates collective action and government emergence from climate/river changes.
3.  **Information Propagation**: Replicates Banerjee et al. (2016) research on India's demonetization policy, testing different propagation strategies (seed nodes vs. broadcast).

#### Available Scenarios

**1. Canal Decay**
```bash
python entrypoints/main.py --config_path config/default/simulation_config.yaml
```

**2. TEOG Scenario**
```bash
python entrypoints/main_TEOG.py --config_path config/TEOG/simulation_config.yaml
```

**3. Information Propagation**
```bash
python entrypoints/main_info_propagation.py --config_path config/info_propagation/simulation_config.yaml
```

### II. AI-Assisted Simulation Mode

Describe requirements in natural language, and the system automatically completes experimental design, code generation, simulation execution, and result optimization.

#### Start System

```bash
python run_ai_system.py
```

#### Running Modes

**Automatic Mode** (Recommended)
- Fully automated from requirement input to final results
- Auto-iterates optimization until meeting expected goals
- Suitable for clear requirements

**Interactive Mode**
- Pauses after each key stage for user confirmation
- Allows review of intermediate results (design documents, generated code, etc.)
- Suitable for requirement exploration and gradual adjustments

#### Workflow

The system automatically completes simulation experiments through 6 stages:

1. **Requirement Input**: Captures natural language descriptions from users
2. **Requirement Analysis**: Parses and formalizes simulation objectives and constraints
3. **System Design**: Generates design documents and module configurations
4. **Code Generation**: Automatically generates simulator code, configuration files, and prompts
5. **Run Simulation**: Executes simulation and automatically fixes runtime errors
6. **Result Evaluation**: Analyzes results and auto-optimizes configurations until expectations are met

#### Usage Example

```
Please enter your simulation experiment requirements:
Research how governments balance finances and suppress rebellion through taxation and investment under extreme climate conditions.
The simulation includes three roles: government, residents, and rebels, with extreme weather randomly occurring and damaging canals.
```

The system will automatically generate:
- Configuration files: `config/<simulation_name>/`
- Simulator code: `src/simulation/simulator_<simulation_name>.py`
- Entry scripts: `entrypoints/main_<simulation_name>.py`
- Experimental data: `history/<simulation_name>/`

---

## Data Analysis

Use built-in analysis tools to generate statistical reports and visualization charts:

```bash
# Analyze results of specified type
python src/analyzer/simulation_analyzer.py --type default

# Analyze results with specific parameters
python src/analyzer/simulation_analyzer.py --type default --p 200 --y 15

# Directly specify files for analysis
python src/analyzer/simulation_analyzer.py --type default --input_files history/default/data1.json history/default/data2.csv

# Custom output directory
python src/analyzer/simulation_analyzer.py --type default --output_dir ./my_reports
```

**Parameter Description**
- `--type`: Simulation type, options: `default`, `TEOG`, `info_propagation`
- `--p`: Initial population size (optional)
- `--y`: Total simulation steps (optional)
- `--input_files`: Directly specify files to analyze (optional)
- `--output_dir`: Custom output directory (optional)

Analysis results are saved in `history/<type>/analysis_results/` directory.

---

## Project Structure

```
├── config/                  # Configuration files
│   ├── default/             # Canal Decay scenario
│   ├── TEOG/                # TEOG scenario
│   ├── info_propagation/    # Information Propagation scenario
│   ├── template/            # Configuration templates
│   └── ...                  # Other scenarios
├── entrypoints/             # Simulation entry scripts
│   ├── main.py              # Canal Decay scenario
│   ├── main_TEOG.py         # TEOG scenario
│   ├── main_info_propagation.py  # Information Propagation scenario
│   └── ...                  # Other scenarios
├── src/                     # Core source code
│   ├── agents/              # Agent modules
│   ├── environment/         # Environment modules
│   ├── simulation/          # Simulator modules
│   ├── analyzer/            # Data analysis modules
│   └── visualization/       # Visualization modules
├── frontend/                # Web visualization interface
├── history/                 # Simulation result data
├── run_ai_system.py         # AI-assisted system entry
└── start_web.bat            # Windows one-click start script
```

---

## Core Features

- 🤖 **AI-Assisted Experimental Design**: Natural language requirements automatically generate complete simulation experiments
- 🎯 **Multi-Agent Simulation**: Multi-role interactions including government, residents, rebels, etc.
- 🔄 **Auto-Optimization Loop**: Intelligent evaluation and automatic parameter adjustment
- 📊 **Real-time Visualization**: Web interface displays simulation process in real-time
- 📈 **Data Analysis**: Automatically generates statistical reports and visualization charts
- ⚙️ **Flexible Configuration**: Supports custom simulation scenarios and parameters

---

## Supplementary Material

For more in-depth technical details and extended experimental results, please refer to our **[Appendix.pdf](./Appendix.pdf)**.

The appendix (24 pages) provides:
- **Experimental Elaborations**: Comprehensive agent logic, environmental formulas, and full trajectories for all benchmark scenarios (Canal Decay, TEOG, Info Propagation).
- **Auto-Simulation Framework**: Internal architecture of the AI agent committee (Master, Architect, etc.) and the iterative error-recovery mechanisms.
- **Extended Case Studies**: Four additional AI-generated experiments, including Financial Herding, Asset Bubble, and Schelling Segregation models.
- **Robustness & Performance Analysis**: Consistency evaluations across different LLMs (GPT-4, DeepSeek, Qwen) and system scaling benchmarks (up to 10,000 agents).
- **Technical Validation**: Comparison with traditional System Dynamics (SD) models and alignment with empirical DID baselines.

---

## FAQ

**Q: How to choose between Traditional Mode and AI-Assisted Mode?**  
A: Use Traditional Mode for running existing scenarios or quick testing; use AI-Assisted Mode for creating new simulation experiments.

**Q: How many times will AI auto-optimization run?**  
A: Maximum 3 times by default. You can modify the `max_iterations` parameter in the `run_full_workflow` method of `project_master.py`.

**Q: Can Interactive Mode return to a previous stage?**  
A: Cross-stage returns are not supported in the current version, but you can provide feedback to regenerate within the current stage.

**Q: Can I manually modify the generated code?**  
A: Yes. The AI-generated files are standard Python code and YAML/JSON configuration files, supporting manual modification and extension.

---

*Note: Node.js installation is required to run the visualization interface.*
