# 依赖注入容器 - 配置文件使用说明

## 快速开始

### 1. 配置文件已就绪

所有项目的 `modules_config.yaml` 文件已添加模块实现映射：

- ✅ `config/template/modules_config.yaml`
- ✅ `config/financial_herd_behavior_sim/modules_config.yaml`
- ✅ `config/asset_market_bubble_sim/modules_config.yaml`
- ✅ `config/schelling_segregation_model/modules_config.yaml`
- ✅ `config/customer_satisfaction_sim/modules_config.yaml`

### 2. 最简单的使用方式

```python
from src.utils import setup_container_from_config_dir
from src.interfaces import IMap, ITime, IPopulation

# 一行代码设置容器（自动加载 modules_config.yaml 和 simulation_config.yaml）
container = setup_container_from_config_dir("config/template")

# 解析依赖
map = container.resolve(IMap)
time = container.resolve(ITime)
population = container.resolve(IPopulation)
```

### 3. 更多控制的方式

```python
import yaml
from src.utils import setup_container_for_simulation

# 加载配置
with open("config/template/simulation_config.yaml", 'r') as f:
    config = yaml.safe_load(f)

# 设置容器
container = setup_container_for_simulation(
    "config/template/modules_config.yaml",
    config
)

# 解析依赖
map = container.resolve(IMap)
```

### 4. 一次性解析所有依赖

```python
from src.utils import setup_container_from_config_dir, resolve_all_dependencies

container = setup_container_from_config_dir("config/template")
deps = resolve_all_dependencies(container)

# deps 包含: map, time, population, towns, social_network, 
#           transport_economy, climate, government, rebellion

simulator = Simulator(**deps, config=config)
```

## 配置文件格式

`modules_config.yaml` 中的新增部分：

```yaml
# ========================================
# 模块实现映射（用于依赖注入容器）
# ========================================
module_implementations:
  # 环境模块
  IMap: "src.environment.map.Map"
  ITime: "src.environment.time.Time"
  IPopulation: "src.environment.population.Population"
  ITowns: "src.environment.towns.Towns"
  ISocialNetwork: "src.environment.social_network.SocialNetwork"
  ITransportEconomy: "src.environment.transport_economy.TransportEconomy"
  IClimateSystem: "src.environment.climate.ClimateSystem"
  IJobMarket: "src.environment.job_market.JobMarket"
  
  # Agent 模块
  IGovernment: "src.agents.government.Government"
  IRebellion: "src.agents.rebels.Rebellion"
```

## 工作原理

1. **配置文件定义映射**：`modules_config.yaml` 定义接口到实现类的映射
2. **容器动态加载**：`DIContainer` 读取配置，使用 `importlib` 动态导入类
3. **自动依赖注入**：解析时根据构造函数类型注解自动注入依赖
4. **单例管理**：默认所有模块为单例，容器生命周期内只创建一次

## 核心 API

### 容器设置函数

| 函数 | 说明 | 使用场景 |
|------|------|---------|
| `create_container_from_yaml(yaml_path)` | 从 modules_config.yaml 创建容器 | 只需要模块映射 |
| `setup_container_from_config_dir(config_dir)` | 从配置目录自动加载 | 推荐用于 entrypoint |
| `setup_container_for_simulation(modules_path, config)` | 手动指定两个配置文件 | 需要更多控制 |
| `create_manual_container(config)` | 不使用配置文件 | 完全手动配置 |

### 解析函数

| 函数 | 说明 |
|------|------|
| `container.resolve(IInterface)` | 解析单个接口 |
| `resolve_all_dependencies(container)` | 一次性解析所有标准依赖 |

## 在 main.py 中使用示例

```python
async def run_simulation(config):
    # 1. 设置容器
    container = setup_container_from_config_dir("config/template")
    
    # 2. 解析环境模块
    map = container.resolve(IMap)
    time = container.resolve(ITime)
    population = container.resolve(IPopulation)
    
    # 3. 初始化需要特殊处理的对象
    residents = await generate_canal_agents(...)
    
    # 4. 继续解析其他模块
    towns = container.resolve(ITowns)
    towns.initialize_resident_groups(residents)
    
    social_network = container.resolve(ISocialNetwork)
    social_network.initialize_network(residents, towns)
    
    # 5. 创建 Simulator
    simulator = Simulator(
        map=map,
        time=time,
        population=population,
        towns=towns,
        social_network=social_network,
        transport_economy=container.resolve(ITransportEconomy),
        climate=container.resolve(IClimateSystem),
        government=container.resolve(IGovernment),
        rebellion=container.resolve(IRebellion),
        config=config,
    )
    
    await simulator.run()
```

## 优势

✅ **配置驱动**：模块映射在配置文件中，无需修改代码  
✅ **动态加载**：支持运行时替换实现类  
✅ **自动装配**：自动解析和注入依赖  
✅ **类型安全**：基于接口类型注解  
✅ **单例管理**：避免重复创建实例  
✅ **易于测试**：可轻松替换测试用实现  

## 文档和示例

- 📖 完整指南：`docs/di_container_guide.md`
- 💡 基础示例：`docs/di_container_examples.py`
- 💡 配置示例：`docs/di_container_config_examples.py`
- 🛠️ 辅助工具：`src/utils/di_helpers.py`
- 🔧 核心实现：`src/utils/di_container.py`

## 下一步

1. 在 entrypoint 文件中使用容器（推荐从 `main_template.py` 开始）
2. 测试配置文件加载功能
3. 根据需要自定义模块实现映射
