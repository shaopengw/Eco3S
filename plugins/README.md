# 插件包结构说明

本目录包含 AgentWorld 系统的所有插件包。每个插件包对应系统的一个模块（如地图、时间、城镇等）。

## 目录结构

```
plugins/
├── map/                      # 地图插件
│   ├── plugin.yaml          # 插件元数据
│   ├── map_plugin.py        # 插件实现
│   └── __init__.py
├── time/                     # 时间插件
│   ├── plugin.yaml
│   └── ...
├── towns/                    # 城镇插件
│   ├── plugin.yaml
│   └── ...
├── population/               # 人口插件
│   ├── plugin.yaml
│   └── ...
├── social_network/           # 社交网络插件
│   ├── plugin.yaml
│   └── ...
├── transport_economy/        # 交通经济插件
│   ├── plugin.yaml
│   └── ...
├── climate/                  # 气候插件
│   ├── plugin.yaml
│   └── ...
└── job_market/               # 就业市场插件
    ├── plugin.yaml
    └── ...
```

## plugin.yaml 格式

每个插件目录必须包含 `plugin.yaml` 元数据文件：

```yaml
# 插件基本信息
name: plugin_name              # 插件名称（必需）
version: 1.0.0                # 版本号（推荐）
description: 插件描述          # 描述信息（推荐）
author: 作者名                # 作者信息（可选）
enabled: true                 # 是否启用（默认 true）

# 插件类信息
plugin_class: PluginClassName  # 插件类名（必需）
module: plugin_module_file     # 模块文件名（不含.py，必需）

# 实现的接口
interfaces:                    # 插件实现的接口列表（可选）
  - IMapPlugin
  - IMap

# 依赖项
dependencies:                  # 依赖的其他插件（可选）
  - other_plugin_name

# 初始化参数
init_params:                   # 传递给插件构造函数的参数（可选）
  width: 100
  height: 100

# 配置项
config:                        # 插件特定的配置（可选）
  enable_cache: true
```

## 插件发现机制

PluginRegistry 支持两种插件发现方式：

### 1. plugin.yaml 发现（推荐）

- 自动扫描 `plugins/` 目录下的所有子目录
- 查找每个子目录中的 `plugin.yaml` 文件
- 根据元数据自动加载插件类
- 支持启用/禁用控制
- 支持依赖声明

**优点：**
- 元数据集中管理
- 配置清晰明确
- 支持依赖管理
- 易于启用/禁用

### 2. Python 文件扫描（回退方式）

- 扫描所有 `.py` 文件
- 查找 `BasePlugin` 的子类
- 自动注册找到的插件类

**优点：**
- 无需配置文件
- 适合快速开发测试

**注意：** 如果目录中存在 `plugin.yaml`，将优先使用方式1，忽略方式2。

## 创建新插件

### 步骤 1: 创建插件目录

```bash
mkdir plugins/my_plugin
```

### 步骤 2: 创建 plugin.yaml

```yaml
name: my_plugin
version: 1.0.0
description: 我的自定义插件
author: Your Name
enabled: true

plugin_class: MyPlugin
module: my_plugin_impl

interfaces:
  - IMyInterface

dependencies: []

init_params:
  param1: value1
```

### 步骤 3: 创建插件实现

`plugins/my_plugin/my_plugin_impl.py`:

```python
from src.plugins import BasePlugin, PluginContext
from typing import Dict, Any

class MyPlugin(BasePlugin):
    def __init__(self, context: PluginContext, param1=None):
        super().__init__(context)
        self.param1 = param1
    
    def on_load(self) -> None:
        self.logger.info(f"MyPlugin 正在加载, param1={self.param1}")
    
    def on_unload(self) -> None:
        self.logger.info("MyPlugin 正在卸载")
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "MyPlugin",
            "version": "1.0.0",
            "description": "我的自定义插件"
        }
    
    # 实现业务方法
    def do_something(self):
        pass
```

### 步骤 4: 创建 __init__.py

`plugins/my_plugin/__init__.py`:

```python
from .my_plugin_impl import MyPlugin

__all__ = ['MyPlugin']
```

### 步骤 5: 使用插件

插件会在系统启动时自动发现和注册（如果 `enabled: true`）。

## 插件使用示例

```python
from src.plugins import PluginRegistry, PluginContext
from src.utils.log_manager import LogManager

# 创建注册表
registry = PluginRegistry(logger=LogManager.get_logger('plugins'))

# 发现所有插件
count = registry.discover(['plugins/'])
print(f"发现了 {count} 个插件")

# 创建插件上下文
context = PluginContext(
    config={'debug': True},
    logger=LogManager.get_logger('plugin')
)

# 加载特定插件
plugin = registry.load_plugin('my_plugin', context)

# 使用插件
plugin.do_something()

# 卸载插件
registry.unload_plugin('my_plugin')
```

## 已有插件

目前系统包含以下默认插件：

| 插件名称 | 说明 | 接口 |
|---------|------|------|
| default_map | 默认地图实现 | IMapPlugin, IMap |
| default_time | 默认时间系统 | ITimePlugin, ITime |
| default_towns | 默认城镇系统 | ITownsPlugin, ITowns |
| default_population | 默认人口系统 | IPopulationPlugin, IPopulation |
| default_social_network | 默认社交网络 | ISocialNetworkPlugin, ISocialNetwork |
| default_transport_economy | 默认交通经济 | ITransportEconomyPlugin, ITransportEconomy |
| default_climate | 默认气候系统 | IClimatePlugin, IClimate |
| default_job_market | 默认就业市场 | IJobMarketPlugin, IJobMarket |

## 启用/禁用插件

在 `plugin.yaml` 中设置 `enabled` 字段：

```yaml
enabled: true   # 启用插件
enabled: false  # 禁用插件
```

禁用的插件不会被发现和加载。

## 插件依赖

在 `plugin.yaml` 中声明依赖：

```yaml
dependencies:
  - default_map    # 依赖地图插件
  - default_time   # 依赖时间插件
```

**注意：** 当前版本需要手动确保依赖插件先加载。未来版本将支持自动依赖解析。

## 调试插件

启用详细日志：

```python
from src.utils.log_manager import LogManager

logger = LogManager.get_logger('plugin_system', console_output=True)
registry = PluginRegistry(logger=logger)
```

查看插件列表：

```python
plugins = registry.get_plugin_list()
for plugin_info in plugins:
    print(f"{plugin_info['name']} v{plugin_info['version']}")
    print(f"  描述: {plugin_info['description']}")
    print(f"  已加载: {plugin_info['loaded']}")
    print(f"  来源: {plugin_info['source']}")
```

## 相关文档

- [插件系统概述](../docs/plugin_system.md)
- [PluginRegistry 详细文档](../docs/plugin_registry.md)
- [插件集成指南](../docs/plugin_integration_guide.md)
- [快速上手指南](../docs/plugin_quickstart.md)

## 常见问题

### Q: 为什么我的插件没有被发现？

A: 检查以下几点：
1. `plugin.yaml` 文件名是否正确
2. `enabled` 字段是否为 `true`
3. `plugin_class` 和 `module` 字段是否正确
4. 插件类是否继承自 `BasePlugin`

### Q: 如何临时禁用某个插件？

A: 将 `plugin.yaml` 中的 `enabled` 设置为 `false`。

### Q: 插件之间如何通信？

A: 使用 `EventBus`：

```python
# 在插件A中发布事件
self.context.event_bus.publish('my_event', {'data': 'value'})

# 在插件B中订阅事件
def on_my_event(data):
    print(f"收到事件: {data}")

self.context.event_bus.subscribe('my_event', on_my_event)
```

### Q: 如何在插件间共享数据？

A: 使用 `PluginContext.registry`：

```python
# 在插件A中存储数据
self.context.registry.register('shared_data', my_data)

# 在插件B中访问数据
shared_data = self.context.registry.get('shared_data')
```
