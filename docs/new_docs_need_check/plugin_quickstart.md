# 插件系统快速上手指南

## 5 分钟快速开始

### 第 1 步：导入必要的类

```python
from src.plugins import (
    IMapPlugin,           # 选择您要扩展的模块接口
    PluginContext,
    PluginManager
)
from src.utils.log_manager import LogManager
from typing import Dict, Any
```

### 第 2 步：创建您的插件

```python
class MyMapPlugin(IMapPlugin):
    """我的自定义地图插件"""
    
    def __init__(self, width: int, height: int, data_file: str):
        super().__init__()
        self._width = width
        self._height = height
        self._data_file = data_file
    
    # 生命周期方法
    def init(self, context: PluginContext) -> None:
        self._context = context
        context.log_info("MyMapPlugin initializing...")
    
    def on_load(self) -> None:
        self._context.log_info("MyMapPlugin loaded!")
        self._mark_loaded()
    
    def on_unload(self) -> None:
        self._context.log_info("MyMapPlugin unloaded!")
        self._mark_unloaded()
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "MyMap",
            "version": "1.0.0",
            "description": "My custom map plugin",
            "author": "Your Name",
            "dependencies": []
        }
    
    # 实现 IMap 业务方法
    @property
    def width(self) -> int:
        return self._width
    
    @property
    def height(self) -> int:
        return self._height
    
    @property
    def grid(self):
        return self._grid
    
    def initialize_map(self) -> None:
        self._context.log_info("Initializing map...")
        self._grid = [[0] * self._width for _ in range(self._height)]
    
    # ... 实现其他必需的 IMap 方法
```

### 第 3 步：使用插件

```python
# 1. 创建插件管理器
manager = PluginManager(
    config={'debug_mode': True},
    logger=LogManager.get_logger('plugin_system')
)

# 2. 创建并加载插件
my_plugin = MyMapPlugin(width=100, height=100, data_file='towns.json')
manager.load_plugin('my_map', my_plugin)

# 3. 使用插件
plugin = manager.get_plugin('my_map')
plugin.initialize_map()
print(f"Map size: {plugin.width} x {plugin.height}")

# 4. 卸载插件
manager.unload_plugin('my_map')
```

## 常用模式

### 模式 1: 事件驱动通信

```python
class ProducerPlugin(IMapPlugin):
    def some_action(self):
        # 发布事件
        self._context.event_bus.publish('data_ready', {'value': 42})

class ConsumerPlugin(ITimePlugin):
    def on_load(self):
        # 订阅事件
        self._context.event_bus.subscribe('data_ready', self._handle_data)
        self._mark_loaded()
    
    def _handle_data(self, data):
        print(f"Received: {data}")
    
    def on_unload(self):
        self._context.event_bus.unsubscribe('data_ready', self._handle_data)
        self._mark_unloaded()
```

### 模式 2: 访问其他插件

```python
class DependentPlugin(ITownsPlugin):
    def on_load(self):
        # 获取其他插件
        map_plugin = self._context.registry.get('map_plugin')
        if map_plugin:
            width = map_plugin.width
            print(f"Map width: {width}")
        self._mark_loaded()
```

### 模式 3: 使用配置

```python
class ConfigurablePlugin(IPopulationPlugin):
    def init(self, context: PluginContext):
        self._context = context
        
        # 读取配置
        self._debug = context.get_config('plugins.my_plugin.debug', False)
        self._max_size = context.get_config('plugins.my_plugin.max_size', 1000)
        
        if self._debug:
            context.log_debug("Debug mode enabled")
```

## 可用的插件接口

| 插件接口 | 对应业务接口 | 用途 |
|---------|-------------|------|
| `IMapPlugin` | `IMap` | 地图系统 |
| `ITimePlugin` | `ITime` | 时间管理 |
| `IPopulationPlugin` | `IPopulation` | 人口系统 |
| `ITownsPlugin` | `ITowns` | 城镇管理 |
| `ISocialNetworkPlugin` | `ISocialNetwork` | 社交网络 |
| `ITransportEconomyPlugin` | `ITransportEconomy` | 交通经济 |
| `IClimatePlugin` | `IClimateSystem` | 气候系统 |
| `IJobMarketPlugin` | `IJobMarket` | 就业市场 |
| `IGovernmentPlugin` | `IGovernment` | 政府系统 |
| `IRebellionPlugin` | `IRebellion` | 叛军系统 |

## 必须实现的方法

### 所有插件都必须实现（来自 BasePlugin）：

1. `init(context: PluginContext)` - 接收上下文
2. `on_load()` - 加载钩子
3. `on_unload()` - 卸载钩子
4. `get_metadata() -> dict` - 返回元数据

### 还需要实现对应业务接口的所有抽象方法

例如 `IMapPlugin` 需要实现 `IMap` 接口的所有方法。

## 检查清单

创建插件时，确保：

- [ ] 继承了正确的插件接口（如 `IMapPlugin`）
- [ ] 调用了 `super().__init__()` 在构造函数中
- [ ] 在 `init()` 中保存了上下文: `self._context = context`
- [ ] 在 `on_load()` 中调用了 `self._mark_loaded()`
- [ ] 在 `on_unload()` 中调用了 `self._mark_unloaded()`
- [ ] `get_metadata()` 返回了完整的元数据
- [ ] 实现了所有业务接口的抽象方法
- [ ] 在 `on_unload()` 中清理了所有资源（事件订阅、文件句柄等）

## 调试技巧

### 技巧 1: 启用调试日志

```python
manager = PluginManager(
    config={'debug_mode': True},
    logger=LogManager.get_logger('plugin_system', console_output=True)
)
```

### 技巧 2: 检查插件状态

```python
plugin = manager.get_plugin('my_plugin')
print(f"Is loaded: {plugin.is_loaded}")
print(f"Metadata: {plugin.get_metadata()}")
```

### 技巧 3: 查看加载顺序

```python
print(f"Load order: {manager.get_load_order()}")
print(f"All plugins: {list(manager.get_all_plugins().keys())}")
```

### 技巧 4: 捕获异常

```python
try:
    manager.load_plugin('my_plugin', plugin)
except ValueError as e:
    print(f"Plugin already loaded: {e}")
except RuntimeError as e:
    print(f"Plugin load failed: {e}")
```

## 下一步

- 查看 [完整文档](plugin_system.md) 了解更多细节
- 查看 [示例代码](plugin_system_examples.py) 学习更多用法
- 查看 `src/plugins/` 目录了解源代码实现

## 常见问题

**Q: 如何在现有系统中集成插件？**

A: 可以将插件实例注册到 DIContainer：

```python
# 加载插件
manager = PluginManager()
map_plugin = MyMapPlugin(100, 100, 'data.json')
manager.load_plugin('map', map_plugin)

# 注册到 DI 容器
from src.utils import DIContainer
from src.interfaces import IMap

container = DIContainer()
container.register_instance(IMap, map_plugin)
```

**Q: 插件可以依赖其他插件吗？**

A: 可以，在 `get_metadata()` 中声明依赖：

```python
def get_metadata(self) -> Dict[str, Any]:
    return {
        "name": "MyPlugin",
        "version": "1.0.0",
        "description": "...",
        "author": "...",
        "dependencies": ["other_plugin_name"]  # 声明依赖
    }
```

**Q: 如何在插件间传递数据？**

A: 使用 EventBus 进行事件驱动通信，或通过 PluginRegistry 直接访问其他插件。

## 支持

如有问题，请查看：
- 完整文档: `docs/plugin_system.md`
- 示例代码: `docs/plugin_system_examples.py`
- 源代码: `src/plugins/`
