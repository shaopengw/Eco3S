# 依赖注入容器 (DI Container) 使用指南

## 概述

依赖注入容器（DIContainer）是一个用于管理对象依赖关系的工具类，支持：

- **接口与实现类的注册映射**
- **自动依赖解析**（基于类型注解）
- **生命周期管理**（单例模式和瞬态模式）
- **工厂函数注册**
- **实例直接注册**
- **循环依赖检测**

## 文件位置

- 实现文件：`src/utils/di_container.py`
- 使用示例：`docs/di_container_examples.py`

## 核心概念

### 1. 生命周期 (Lifecycle)

容器支持两种生命周期模式：

- **SINGLETON（单例）**：容器生命周期内只创建一次实例，后续请求返回同一实例（默认）
- **TRANSIENT（瞬态）**：每次请求都创建新实例

### 2. 注册方式

#### 2.1 类注册（register）

```python
container = DIContainer()

# 注册为单例（默认）
container.register(IMap, Map)

# 注册为瞬态
container.register(ITime, Time, lifecycle=Lifecycle.TRANSIENT)
```

#### 2.2 工厂函数注册（register_factory）

适用于需要配置参数的对象：

```python
container.register_factory(
    IMap,
    lambda: Map(width=100, height=100, data_file="config/towns_data.json")
)
```

#### 2.3 实例注册（register_instance）

直接注册已创建的实例：

```python
map_instance = Map(width=100, height=100)
container.register_instance(IMap, map_instance)
```

### 3. 依赖解析（resolve）

```python
# 解析接口获取实例（自动注入依赖）
map_instance = container.resolve(IMap)
```

## 使用示例

### 示例1：从配置文件自动加载（推荐）

**最简单的方式**：直接从 `modules_config.yaml` 加载所有模块映射：

```python
from src.utils import create_container_from_yaml
from src.interfaces import IMap, ITime, IGovernment

# 一行代码创建并配置容器
container = create_container_from_yaml("config/template/modules_config.yaml")

# 解析实例（自动根据配置文件中的映射创建）
map_instance = container.resolve(IMap)
time_instance = container.resolve(ITime)
government_instance = container.resolve(IGovernment)
```

**配置文件格式** (`modules_config.yaml`)：

```yaml
# 模块实现映射（用于依赖注入容器）
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

**向已有容器注册**：

```python
from src.utils import DIContainer, register_from_yaml

container = DIContainer()
register_from_yaml(container, "config/template/modules_config.yaml")

# 查看已注册的模块
bindings = container.get_all_bindings()
print(f"已注册 {len(bindings)} 个模块")
```

### 示例2：结合配置文件和工厂函数

```python
import yaml
from src.utils import create_container_from_yaml
from src.interfaces import IMap, ITime, IPopulation
from src.environment.map import Map
from src.environment.time import Time
from src.environment.population import Population

# 1. 加载模拟配置
with open("config/template/simulation_config.yaml", 'r', encoding='utf-8') as f:
    sim_config = yaml.safe_load(f)

# 2. 从 modules_config.yaml 创建基础容器
container = create_container_from_yaml("config/template/modules_config.yaml")

# 3. 为需要配置参数的模块注册工厂函数（覆盖默认注册）
container.register_factory(
    IMap,
    lambda: Map(
        width=sim_config['simulation']['map_width'],
        height=sim_config['simulation']['map_height'],
        data_file=sim_config['data']['towns_data_path']
    )
)

container.register_factory(
    ITime,
    lambda: Time(
        start_time=sim_config['simulation']['start_year'],
        total_steps=sim_config['simulation']['total_years']
    )
)

container.register_factory(
    IPopulation,
    lambda: Population(
        initial_population=sim_config['simulation']['initial_population'],
        birth_rate=sim_config['simulation']['birth_rate']
    )
)

# 4. 解析实例（会使用工厂函数创建）
map_instance = container.resolve(IMap)
```

### 示例3：基础使用

```python
from src.utils import DIContainer, Lifecycle
from src.interfaces import IMap, ITime
from src.environment.map import Map
from src.environment.time import Time

# 创建容器
container = DIContainer()

# 注册映射
container.register(IMap, Map, lifecycle=Lifecycle.SINGLETON)
container.register(ITime, Time, lifecycle=Lifecycle.SINGLETON)

# 解析实例
map_instance = container.resolve(IMap)
time_instance = container.resolve(ITime)

# 验证单例
map_instance2 = container.resolve(IMap)
assert map_instance is map_instance2  # True
```

### 示例2：自动依赖注入

假设 `Government` 类的构造函数签名如下：

```python
class Government(BaseAgent, IGovernment):
    def __init__(
        self,
        map: IMap,
        towns: ITowns,
        time: ITime,
        transport_economy: ITransportEconomy,
        ...
    ):
        ...
```

使用容器时，依赖会自动注入：

```python
# 注册所有依赖
container.register(IMap, Map)
container.register(ITowns, Towns)
container.register(ITime, Time)
container.register(ITransportEconomy, TransportEconomy)
container.register(IGovernment, Government)

# 解析 Government（会自动创建并注入 map, towns, time, transport_economy）
government = container.resolve(IGovernment)
```

**关键点**：
- 构造函数参数必须有**类型注解**
- 参数类型必须是已注册的接口
- 容器会递归解析所有依赖

### 示例3：配置项目容器

```python
def setup_simulation_container(config: dict) -> DIContainer:
    """
    配置模拟系统的依赖注入容器
    
    Args:
        config: 配置字典
        
    Returns:
        配置好的容器
    """
    container = DIContainer()
    
    # 使用工厂函数注册需要配置的对象
    container.register_factory(
        IMap,
        lambda: Map(
            width=config["simulation"]["map_width"],
            height=config["simulation"]["map_height"],
            data_file=config["data"]["towns_data_path"]
        )
    )
    
    container.register_factory(
        ITime,
        lambda: Time(
            start_time=config["simulation"]["start_year"],
            total_steps=config["simulation"]["total_years"]
        )
    )
    
    container.register_factory(
        IPopulation,
        lambda: Population(
            initial_population=config["simulation"]["initial_population"],
            birth_rate=config["simulation"]["birth_rate"]
        )
    )
    
    # 自动装配的对象
    container.register(ITowns, Towns)
    container.register(ISocialNetwork, SocialNetwork)
    container.register(ITransportEconomy, TransportEconomy)
    container.register(IClimateSystem, ClimateSystem)
    container.register(IGovernment, Government)
    container.register(IRebellion, Rebellion)
    
    return container

# 使用
config = load_config("config.yaml")
container = setup_simulation_container(config)

# 解析 Simulator 所需的所有依赖
map = container.resolve(IMap)
time = container.resolve(ITime)
government = container.resolve(IGovernment)
# ...
```

### 示例4：在 entrypoint 中使用

修改后的 `main.py`：

```python
from src.utils import DIContainer
from src.interfaces import *
from src.environment.map import Map
# ... 其他导入

async def run_simulation(config):
    # 设置容器
    container = setup_simulation_container(config)
    
    # 注册特殊依赖（如 residents）
    residents = await generate_canal_agents(...)
    container.register_instance(IResidents, residents)  # 如果有 IResidents 接口
    
    # 初始化其他对象
    towns = container.resolve(ITowns)
    towns.initialize_resident_groups(residents)
    
    # 解析所有依赖
    simulator = Simulator(
        map=container.resolve(IMap),
        time=container.resolve(ITime),
        government=container.resolve(IGovernment),
        population=container.resolve(IPopulation),
        social_network=container.resolve(ISocialNetwork),
        towns=towns,
        transport_economy=container.resolve(ITransportEconomy),
        climate=container.resolve(IClimateSystem),
        config=config,
    )
    
    await simulator.run()
```

## 高级功能

### 从配置文件加载（推荐）

#### 函数列表

**`create_container_from_yaml(yaml_path, lifecycle=Lifecycle.SINGLETON)`**

最便捷的方式，一行代码创建并配置容器：

```python
from src.utils import create_container_from_yaml

container = create_container_from_yaml("config/template/modules_config.yaml")
```

**`register_from_yaml(container, yaml_path, lifecycle=Lifecycle.SINGLETON)`**

向已有容器注册配置文件中的模块：

```python
from src.utils import DIContainer, register_from_yaml

container = DIContainer()
register_from_yaml(container, "config/template/modules_config.yaml")
```

**`load_implementations_from_yaml(yaml_path, lifecycle=Lifecycle.SINGLETON)`**

只加载映射，不注册（用于检查或自定义注册）：

```python
from src.utils import load_implementations_from_yaml

implementations = load_implementations_from_yaml("config/template/modules_config.yaml")
# 返回: {IMap: Map, ITime: Time, ...}
```

**`load_module_from_path(module_path)`**

从字符串路径动态导入类：

```python
from src.utils import load_module_from_path

Map = load_module_from_path("src.environment.map.Map")
```

#### 配置文件格式

在各个项目的 `modules_config.yaml` 中添加：

```yaml
# 模块实现映射（用于依赖注入容器）
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

### 全局容器

使用全局单例容器：

```python
from src.utils import get_global_container, reset_global_container

# 获取全局容器
container = get_global_container()
container.register(IMap, Map)

# 在其他模块中使用
from src.utils import get_global_container
container = get_global_container()
map = container.resolve(IMap)

# 重置全局容器
reset_global_container()
```

### 检查绑定信息

```python
# 检查是否已注册
if container.is_registered(IMap):
    print("IMap 已注册")

# 获取绑定信息
info = container.get_binding_info(IMap)
print(info)
# 输出: {'interface': 'IMap', 'implementation': 'Map', 'lifecycle': 'singleton', 'has_instance': False}

# 获取所有绑定
all_bindings = container.get_all_bindings()
for name, info in all_bindings.items():
    print(f"{name}: {info}")
```

### 重置容器

```python
# 清除所有注册和实例
container.clear()

# 只重置单例实例（保留注册映射）
container.reset_singletons()
```

## 错误处理

### 1. 未注册的接口

```python
try:
    instance = container.resolve(IMap)
except ValueError as e:
    print(f"错误: {e}")  # 接口 IMap 未注册
```

### 2. 循环依赖

如果 A 依赖 B，B 依赖 A，容器会检测到循环依赖并抛出异常：

```python
# 检测到循环依赖: ClassA -> ClassB -> ClassA
```

### 3. 缺少类型注解

构造函数参数必须有类型注解（除非有默认值）：

```python
# 错误示例
class MyClass:
    def __init__(self, param):  # 缺少类型注解
        pass

# 正确示例
class MyClass:
    def __init__(self, param: IMap):  # 有类型注解
        pass
    
# 或有默认值
class MyClass:
    def __init__(self, param=None):  # 有默认值
        pass
```

## 最佳实践

1. **使用接口类型注解**：构造函数参数始终使用接口类型（`IMap`）而非具体类（`Map`）
2. **合理选择生命周期**：
   - 无状态或共享状态的对象使用 SINGLETON
   - 需要独立状态的对象使用 TRANSIENT
3. **工厂函数用于配置**：需要配置参数的对象使用工厂函数注册
4. **提前注册**：在解析依赖前，确保所有接口都已注册
5. **避免循环依赖**：设计时避免类之间的循环依赖关系

## 与现有代码集成

### 迁移策略

1. **保持现有代码**：不需要立即修改所有代码
2. **逐步采用**：在新功能或重构时使用容器
3. **混合使用**：容器和手动创建可以共存

### 渐进式迁移示例

```python
# 阶段1：部分使用容器
container = DIContainer()
container.register(IMap, Map)
map = container.resolve(IMap)
time = Time(...)  # 仍然手动创建

# 阶段2：更多依赖使用容器
container.register(ITime, Time)
map = container.resolve(IMap)
time = container.resolve(ITime)

# 阶段3：完全使用容器
container.register(IGovernment, Government)
government = container.resolve(IGovernment)  # 自动注入所有依赖
```

## 参考资料

- 完整示例：`docs/di_container_examples.py`
- 实现代码：`src/utils/di_container.py`
- 接口定义：`src/interfaces/`
