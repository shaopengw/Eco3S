# AgentWorld

## 配置环境
```bash
conda create --name AGENTWORLD python=3.10
conda activate AGENTWORLD

pip install numpy
pip install matplotlib
pip install camel-ai
pip install pyyaml
pip install pandas
pip install hypernetx
pip install fastjsonschema
```

## 配置环境变量
```bash
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_API_BASE_URL="your_api_base_url"
```

## 运行模拟
```bash
python main.py --config_path config/simulation_config.yaml
```