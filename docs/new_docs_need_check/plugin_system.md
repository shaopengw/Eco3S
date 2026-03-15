# 插件系统文档

## 概述

AgentWorld 插件系统提供了一套完整的插件基础设施，允许开发者以插件形式扩展和替换系统的各个模块。插件系统支持生命周期管理、事件驱动通信和依赖解析。

## 架构设计

### 核心组件

```
src/plugins/
├── __init__.py              # 模块导出
├── base_plugin.py           # BasePlugin 抽象类
├── plugin_context.py        # PluginContext、EventBus、PluginRegistry
├── plugin_manager.py        # PluginManager、PluginLoader
└── plugin_interfaces.py     # 各模块的插件接口
```

### 类图

```
┌─────────────────┐
│   BasePlugin    │ (抽象类)
│  (生命周期管理)  │
└────────┬────────┘
         │
         │ 继承
         │
         ├──────────────┬──────────────┬─────────────┬───────...
         │              │              │             │
    ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌───▼────┐
    │ IMapPlugin│  │ITimePlugin│  │ITownsPlugin│  │  ...   │
    │(插件接口) │  │(插件接口)│  │(插件接口) │  │        │
    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┘
         │              │              │
         │ 同时继承      │              │
         │              │              │
    ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐
    │   IMap    │  │   ITime   │  │  ITowns  │
    │(业务接口) │  │(业务接口)│  │(业务接口)│
    └──────────┘  └──────────┘  └──────────┘
```

### 工作流程

```
1. 创建 PluginManager
   │
   ├─> 初始化 EventBus
   ├─> 初始化 PluginRegistry
   └─> 创建 PluginContext
   
2. 加载插件 (load_plugin)
   │
   ├─> 调用 plugin.init(context)       # 传递上下文
   ├─> 调用 plugin.get_metadata()      # 获取元数据
   ├─> 检查依赖 (check_dependencies)   # 验证依赖是否满足
   ├─> 注册到 PluginRegistry           # 注册插件
   ├─> 调用 plugin.on_load()           # 加载钩子
   └─> 发布 'plugin_loaded' 事件       # 通知其他插件
   
3. 使用插件
   │
   ├─> 通过 manager.get_plugin() 获取
   ├─> 调用插件的业务方法
   └─> 通过 EventBus 进行插件间通信
   
4. 卸载插件 (unload_plugin)
   │
   ├─> 调用 plugin.on_unload()         # 卸载钩子
   ├─> 从 PluginRegistry 移除          # 注销插件
   └─> 发布 'plugin_unloaded' 事件     # 通知其他插件
```

## 核心类说明

### 1. BasePlugin

所有插件的抽象基类，定义插件生命周期。

**生命周期方法：**

- `__init__()` - 插件实例化
- `init(context: PluginContext)` - 接收上下文，进行初始化
- `on_load()` - 插件加载时的钩子
- `on_unload()` - 插件卸载时的钩子
- `get_metadata() -> dict` - 返回插件元数据

**元数据格式：**

```python
{
    "name": "PluginName",           # 插件名称
    "version": "1.0.0",             # 版本号（语义化版本）
    "description": "...",           # 描述
    "author": "Author Name",        # 作者
    "dependencies": ["other_plugin"] # 依赖的其他插件
}
```

### 2. PluginContext

插件运行时上下文，提供插件所需的所有资源。

**属性：**

- `config: Dict[str, Any]` - 配置字典
- `logger: logging.Logger` - 日志记录器
- `event_bus: EventBus` - 事件总线
- `registry: PluginRegistry` - 插件注册表
- `metadata: Dict[str, Any]` - 自定义元数据

**方法：**

```python
# 配置访问（支持点号分隔的嵌套键）
context.get_config('simulation.population', default=1000)
context.set_config('debug_mode', True)

# 便捷日志方法
context.log_info("Info message")
context.log_warning("Warning message")
context.log_error("Error message")
context.log_debug("Debug message")
```

### 3. EventBus

事件总线，用于插件间的事件驱动通信。

**使用示例：**

```python
# 订阅事件
def on_event(data):
    print(f"Received: {data}")

event_bus.subscribe('my_event', on_event)

# 发布事件
event_bus.publish('my_event', {'key': 'value'})

# 取消订阅
event_bus.unsubscribe('my_event', on_event)
```

### 4. PluginRegistry (增强版)

增强版插件注册表，提供完整的插件发现、注册和管理功能。

**双重发现机制：**

1. **配置文件清单** (`config/plugins.yaml`):
   - 明确的插件列表
   - 可禁用特定插件
   - 提供元数据和初始化参数

2. **目录扫描** (`plugins/` 目录):
   - 自动发现新插件
   - 支持插件热添加
   - 适合开发环境

**核心方法：**

```python
# 创建注册表
registry = PluginRegistry(logger=logger)

# 发现插件（统一方法）
count = registry.discover([
    'plugins/',           # 官方插件
    'plugins/custom/',    # 自定义插件
    'plugins/community/'  # 社区插件
])

# 手动注册插件
registry.register(
    plugin_class=MyPlugin,
    name="my_plugin",
    metadata={
        "version": "1.0.0",
        "description": "My custom plugin"
    }
)

# 加载插件实例
plugin = registry.load_plugin(
    'my_plugin',
    context,
    width=100,  # 传递构造参数
    height=100
)

# 按接口查询
map_plugins = registry.get_plugins_by_interface('IMapPlugin')

# 获取插件实例
plugin = registry.get_plugin('my_plugin')

# 检查状态
if registry.has_plugin('my_plugin'):
    if registry.is_loaded('my_plugin'):
        pass

# 卸载插件
registry.unload_plugin('my_plugin')

# 获取所有插件信息
plugins = registry.get_plugin_list()
```

**PluginMetadata 类：**

```python
class PluginMetadata:
    name: str                         # 插件名称
    plugin_class: Type[BasePlugin]    # 插件类
    metadata: Dict[str, Any]          # 元数据
    source: str                       # 来源（config/scan/manual）
    instance: Optional[BasePlugin]    # 插件实例
    loaded: bool                      # 加载状态
```

**详细文档：** 参见 [PluginRegistry 详细文档](plugin_registry.md)

### 4.5. SimplePluginRegistry

简化版插件注册表（在 `PluginContext` 中使用）。

**方法：**

```python
# 注册插件
registry.register('plugin_name', plugin_instance)

# 获取插件
plugin = registry.get('plugin_name')

# 检查插件是否存在
if registry.has('plugin_name'):
    pass

# 获取所有插件
all_plugins = registry.get_all()
```

### 5. PluginManager

插件管理器，提供插件的完整生命周期管理。

**核心方法：**

```python
# 创建管理器
manager = PluginManager(
    config={'debug': True},
    logger=LogManager.get_logger('plugins')
)

# 加载插件
plugin = MyPlugin()
manager.load_plugin('my_plugin', plugin)

# 获取插件
loaded = manager.get_plugin('my_plugin')

# 检查插件
if manager.has_plugin('my_plugin'):
    pass

# 卸载插件
manager.unload_plugin('my_plugin')

# 卸载所有插件（逆序）
manager.unload_all()

# 获取加载顺序
order = manager.get_load_order()
```

### 6. 插件接口

为每个模块定义的插件接口，继承 `BasePlugin` 和对应的业务接口。

**可用插件接口：**

- `IMapPlugin` - 地图模块插件接口
- `ITimePlugin` - 时间模块插件接口
- `IPopulationPlugin` - 人口模块插件接口
- `ITownsPlugin` - 城镇模块插件接口
- `ISocialNetworkPlugin` - 社交网络模块插件接口
- `ITransportEconomyPlugin` - 交通经济模块插件接口
- `IClimatePlugin` - 气候系统模块插件接口
- `IJobMarketPlugin` - 就业市场模块插件接口
- `IGovernmentPlugin` - 政府模块插件接口
- `IRebellionPlugin` - 叛军模块插件接口

## 使用指南

### 创建自定义插件

**步骤 1: 选择插件接口**

根据要扩展的模块选择对应的插件接口。例如，创建地图插件时使用 `IMapPlugin`。

**步骤 2: 实现插件类**

```python
from src.plugins import IMapPlugin, PluginContext
from typing import Dict, Any

class CustomMapPlugin(IMapPlugin):
    """自定义地图插件"""
    
    def __init__(self, width: int, height: int, data_file: str):
        """初始化插件（业务参数）"""
        super().__init__()
        self._width = width
        self._height = height
        self._data_file = data_file
    
    # ========================================
    # BasePlugin 生命周期方法（必须实现）
    # ========================================
    
    def init(self, context: PluginContext) -> None:
        """接收上下文并初始化"""
        self._context = context
        self._context.log_info("CustomMap initializing...")
    
    def on_load(self) -> None:
        """加载时的钩子"""
        self._context.log_info("CustomMap loading...")
        # 订阅事件
        self._context.event_bus.subscribe('event_name', self._handler)
        self._mark_loaded()
    
    def on_unload(self) -> None:
        """卸载时的钩子"""
        self._context.log_info("CustomMap unloading...")
        # 取消订阅
        self._context.event_bus.unsubscribe('event_name', self._handler)
        self._mark_unloaded()
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回元数据"""
        return {
            "name": "CustomMap",
            "version": "1.0.0",
            "description": "Custom map with advanced features",
            "author": "Your Name",
            "dependencies": []
        }
    
    # ========================================
    # IMap 业务方法（必须实现）
    # ========================================
    
    @property
    def width(self) -> int:
        return self._width
    
    @property
    def height(self) -> int:
        return self._height
    
    def initialize_map(self) -> None:
        self._context.log_info("Initializing map...")
        # 实现地图初始化逻辑
    
    # ... 实现其他 IMap 接口定义的方法
```

**步骤 3: 使用插件**

```python
from src.plugins import PluginManager
from src.utils.log_manager import LogManager

# 1. 创建管理器
manager = PluginManager(
    config={'simulation': {'population': 1000}},
    logger=LogManager.get_logger('plugin_system')
)

# 2. 创建并加载插件
custom_map = CustomMapPlugin(width=100, height=100, data_file='towns.json')
manager.load_plugin('custom_map', custom_map)

# 3. 使用插件
map_plugin = manager.get_plugin('custom_map')
map_plugin.initialize_map()

# 4. 卸载插件
manager.unload_plugin('custom_map')
```

### 插件间通信

使用 EventBus 进行插件间的松耦合通信：

```python
# 插件 A - 发布事件
class PluginA(IMapPlugin):
    def some_method(self):
        self._context.event_bus.publish('map_ready', {
            'width': self._width,
            'height': self._height
        })

# 插件 B - 订阅事件
class PluginB(ITimePlugin):
    def on_load(self):
        self._context.event_bus.subscribe('map_ready', self._on_map_ready)
        self._mark_loaded()
    
    def _on_map_ready(self, data):
        print(f"Map is ready: {data}")
    
    def on_unload(self):
        self._context.event_bus.unsubscribe('map_ready', self._on_map_ready)
        self._mark_unloaded()
```

### 插件依赖管理

在 `get_metadata()` 中声明依赖：

```python
def get_metadata(self) -> Dict[str, Any]:
    return {
        "name": "DependentPlugin",
        "version": "1.0.0",
        "description": "Depends on other plugins",
        "author": "Your Name",
        "dependencies": ["map_plugin", "time_plugin"]  # 声明依赖
    }
```

PluginManager 会在加载时自动检查依赖是否满足。

### 访问其他插件

通过 `PluginRegistry` 访问其他已加载的插件：

```python
def on_load(self):
    # 获取其他插件
    map_plugin = self._context.registry.get('map_plugin')
    if map_plugin:
        # 使用其他插件的方法
        width = map_plugin.width
```

## 最佳实践

### 1. 资源清理

在 `on_unload()` 中确保清理所有资源：

```python
def on_unload(self):
    # 取消所有事件订阅
    self._context.event_bus.unsubscribe('event1', self._handler1)
    self._context.event_bus.unsubscribe('event2', self._handler2)
    
    # 关闭文件、连接等
    if hasattr(self, '_file'):
        self._file.close()
    
    # 清空缓存
    self._cache.clear()
    
    self._mark_unloaded()
```

### 2. 错误处理

在关键方法中添加错误处理：

```python
def on_load(self):
    try:
        self._context.log_info("Loading plugin...")
        # 加载逻辑
        self._mark_loaded()
    except Exception as e:
        self._context.log_error(f"Failed to load: {e}")
        raise
```

### 3. 配置管理

利用 PluginContext 的配置功能：

```python
def init(self, context: PluginContext):
    self._context = context
    
    # 获取插件特定配置
    self._debug = context.get_config('plugins.custom_map.debug', False)
    self._cache_size = context.get_config('plugins.custom_map.cache_size', 100)
```

### 4. 日志记录

使用统一的日志接口：

```python
def some_method(self):
    self._context.log_debug("Debug information")
    self._context.log_info("Normal operation")
    self._context.log_warning("Warning message")
    self._context.log_error("Error occurred")
```

### 5. 版本管理

使用语义化版本号：

```python
def get_metadata(self):
    return {
        "name": "MyPlugin",
        "version": "1.2.3",  # MAJOR.MINOR.PATCH
        # ...
    }
```

## 常见问题

### Q: 如何在 DIContainer 中使用插件？

A: 可以将插件实例注册到 DIContainer：

```python
# 创建并加载插件
manager = PluginManager()
plugin = CustomMapPlugin(100, 100, 'data.json')
manager.load_plugin('map', plugin)

# 注册到 DI 容器
container = DIContainer()
container.register_instance(IMap, plugin)
```

### Q: 插件可以热重载吗？

A: 当前实现不支持热重载。如需更新插件，必须先卸载再重新加载：

```python
manager.unload_plugin('my_plugin')
new_plugin = MyPlugin(updated_params)
manager.load_plugin('my_plugin', new_plugin)
```

### Q: 如何测试插件？

A: 可以创建模拟的 PluginContext 进行单元测试：

```python
import unittest
from src.plugins import PluginContext

class TestMyPlugin(unittest.TestCase):
    def setUp(self):
        self.context = PluginContext(
            config={},
            logger=None
        )
        self.plugin = MyPlugin()
        self.plugin.init(self.context)
    
    def test_metadata(self):
        metadata = self.plugin.get_metadata()
        self.assertEqual(metadata['name'], 'MyPlugin')
```

## 完整示例

查看 `docs/plugin_system_examples.py` 获取完整的使用示例。

## 技术细节

- **Python 版本**: 3.8+
- **依赖**: 仅依赖标准库和项目现有接口
- **性能**: 事件发布采用同步调用，如需异步可扩展 EventBus
- **线程安全**: 当前实现非线程安全，多线程环境需加锁

## 未来扩展

可能的扩展方向：

1. **异步支持**: 支持 async/await 的插件生命周期
2. **热重载**: 支持插件热更新
3. **插件市场**: 提供插件分发和版本管理
4. **配置验证**: 基于 JSON Schema 的配置验证
5. **性能监控**: 插件性能指标收集
