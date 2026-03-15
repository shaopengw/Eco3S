# PluginRegistry 详细文档

## 概述

`PluginRegistry` 是 AgentWorld 插件系统的核心组件，提供插件的注册、发现、加载和管理功能。

## 主要特性

### ✨ 核心功能

1. **插件注册** - 手动注册插件类和元数据
2. **自动发现** - 支持两种发现机制：
   - 基于配置文件清单（`config/plugins.yaml`）
   - 基于目录扫描（`plugins/` 下的子目录）
3. **插件加载** - 创建插件实例并初始化
4. **接口查询** - 按接口类型查找插件
5. **生命周期管理** - 加载和卸载插件

### 🎯 设计目标

- **灵活性**: 支持多种插件发现和加载方式
- **可扩展性**: 易于添加新的插件类型和发现机制
- **易用性**: 简洁的 API 设计
- **安全性**: 插件隔离和错误处理

## 类结构

### PluginMetadata

插件元数据类，存储插件的详细信息。

**属性:**

```python
class PluginMetadata:
    name: str                    # 插件名称
    plugin_class: Type[BasePlugin]  # 插件类
    metadata: Dict[str, Any]     # 元数据字典
    source: str                  # 插件来源（config/scan/manual）
    instance: Optional[BasePlugin]  # 插件实例
    loaded: bool                 # 是否已加载
```

### PluginRegistry

增强版插件注册表，提供完整的插件管理功能。

**核心方法:**

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `register(plugin_class, metadata, name, source)` | 注册插件类 | str (插件名称) |
| `discover(paths)` | 发现插件 | int (发现数量) |
| `load_plugin(name, context, **kwargs)` | 加载插件实例 | BasePlugin |
| `unload_plugin(name)` | 卸载插件 | None |
| `get_plugin(name)` | 获取已加载的插件 | Optional[BasePlugin] |
| `get_plugins_by_interface(interface_name)` | 按接口查询 | List[str] |
| `get_all()` | 获取所有插件元数据 | Dict[str, PluginMetadata] |
| `get_all_loaded()` | 获取所有已加载插件 | Dict[str, BasePlugin] |

## 使用指南

### 1. 创建注册表

```python
from src.plugins.plugin_registry import PluginRegistry
from src.utils.log_manager import LogManager

# 创建注册表
registry = PluginRegistry(
    logger=LogManager.get_logger('plugin_registry')
)
```

### 2. 手动注册插件

```python
from src.plugins import IMapPlugin

class MyMapPlugin(IMapPlugin):
    # ... 实现插件
    pass

# 注册插件
registry.register(
    plugin_class=MyMapPlugin,
    name="my_map",
    metadata={
        "name": "MyMap",
        "version": "1.0.0",
        "description": "Custom map plugin",
        "author": "Your Name",
        "dependencies": []
    }
)
```

### 3. 从配置文件发现插件

**配置文件示例** (`config/plugins.yaml`):

```yaml
plugins:
  - name: custom_map
    module: plugins.custom_map.CustomMapPlugin
    enabled: true
    metadata:
      version: "1.0.0"
      description: "自定义地图插件"
      author: "AgentWorld Team"
      dependencies: []
  
  - name: advanced_time
    module: plugins.time.AdvancedTimePlugin
    enabled: false  # 禁用
    metadata:
      version: "2.0.0"
      description: "高级时间管理系统"
```

**加载插件:**

```python
# 从配置文件发现
count = registry._discover_from_config('config/plugins.yaml')
print(f"发现了 {count} 个插件")
```

### 4. 从目录扫描发现插件

**目录结构:**

```
plugins/
├── custom_map/
│   ├── __init__.py
│   └── custom_map_plugin.py  # 包含 CustomMapPlugin 类
├── advanced_time/
│   └── plugin.py              # 包含 AdvancedTimePlugin 类
└── community/
    └── social/
        └── enhanced.py        # 包含 EnhancedSocialNetworkPlugin 类
```

**扫描目录:**

```python
# 扫描指定目录
count = registry._discover_from_directory('plugins/')
print(f"从目录发现了 {count} 个插件")
```

### 5. 统一发现（推荐）

```python
# 同时使用配置文件和目录扫描
count = registry.discover([
    'plugins/',
    'plugins/custom/',
    'plugins/community/'
])

print(f"总共发现 {count} 个插件")
```

### 6. 加载和使用插件

```python
from src.plugins import PluginContext

# 创建上下文
context = PluginContext(
    config={'debug_mode': True},
    logger=LogManager.get_logger('plugin')
)

# 加载插件（传递构造函数参数）
plugin = registry.load_plugin(
    'custom_map',
    context,
    width=100,
    height=100,
    data_file='towns.json'
)

# 使用插件
plugin.initialize_map()
print(f"Map size: {plugin.width} x {plugin.height}")

# 卸载插件
registry.unload_plugin('custom_map')
```

### 7. 查询插件

```python
# 检查插件是否注册
if 'custom_map' in registry:
    print("插件已注册")

# 检查插件是否加载
if registry.is_loaded('custom_map'):
    print("插件已加载")

# 获取插件实例
plugin = registry.get_plugin('custom_map')

# 按接口查询
map_plugins = registry.get_plugins_by_interface('IMapPlugin')
print(f"找到 {len(map_plugins)} 个地图插件: {map_plugins}")

# 获取所有插件列表
plugins = registry.get_plugin_list()
for info in plugins:
    print(f"{info['name']} v{info['version']} - {info['description']}")
```

## 配置文件格式

### 基本格式

```yaml
plugins:
  - name: plugin_name           # 必需：插件名称
    module: module.path.Class   # 必需：完整的模块路径
    enabled: true               # 可选：是否启用（默认 true）
    metadata:                   # 可选：元数据
      version: "1.0.0"
      description: "插件描述"
      author: "作者名"
      dependencies: []          # 依赖的其他插件
    init_params:                # 可选：构造函数参数
      width: 100
      height: 100
```

### 完整示例

查看 `config/plugins.yaml` 获取完整的配置文件示例。

## 插件发现机制

### 机制 1: 配置文件清单

**优点:**
- 明确的插件列表
- 可以禁用特定插件
- 提供元数据信息
- 支持初始化参数

**适用场景:**
- 生产环境
- 需要精确控制的场景
- 插件数量较少

**工作流程:**
1. 读取 `config/plugins.yaml`
2. 解析插件配置项
3. 检查 `enabled` 标志
4. 动态导入插件类
5. 注册到注册表

### 机制 2: 目录扫描

**优点:**
- 自动发现新插件
- 无需手动配置
- 支持插件热添加

**适用场景:**
- 开发环境
- 插件市场/社区插件
- 快速测试

**工作流程:**
1. 递归扫描指定目录
2. 查找所有 `.py` 文件
3. 动态导入模块
4. 查找 `BasePlugin` 的子类
5. 自动注册找到的插件

### 混合使用（推荐）

```python
# 同时使用两种机制
count = registry.discover([
    'plugins/',           # 扫描官方插件
    'plugins/custom/',    # 扫描自定义插件
    'plugins/community/'  # 扫描社区插件
])
```

## 高级用法

### 1. 获取详细的插件信息

```python
# 获取插件元数据对象
metadata = registry.get_plugin_metadata('custom_map')

if metadata:
    print(f"名称: {metadata.name}")
    print(f"类: {metadata.plugin_class.__name__}")
    print(f"来源: {metadata.source}")
    print(f"已加载: {metadata.loaded}")
    print(f"元数据: {metadata.metadata}")
```

### 2. 批量加载插件

```python
# 加载所有地图插件
map_plugins = registry.get_plugins_by_interface('IMapPlugin')

context = PluginContext(config={}, logger=logger)

for plugin_name in map_plugins:
    try:
        plugin = registry.load_plugin(
            plugin_name,
            context,
            width=100,
            height=100
        )
        print(f"✓ 已加载: {plugin_name}")
    except Exception as e:
        print(f"✗ 加载失败 {plugin_name}: {e}")
```

### 3. 插件依赖检查

```python
def check_dependencies(registry: PluginRegistry, plugin_name: str) -> bool:
    """检查插件依赖是否满足"""
    metadata = registry.get_plugin_metadata(plugin_name)
    if not metadata:
        return False
    
    dependencies = metadata.metadata.get('dependencies', [])
    
    for dep in dependencies:
        if not registry.has_plugin(dep):
            print(f"缺少依赖: {dep}")
            return False
        if not registry.is_loaded(dep):
            print(f"依赖未加载: {dep}")
            return False
    
    return True
```

### 4. 插件热重载

```python
def hot_reload_plugin(registry: PluginRegistry, name: str, context: PluginContext):
    """热重载插件"""
    # 卸载旧版本
    if registry.is_loaded(name):
        registry.unload_plugin(name)
    
    # 重新导入模块（刷新代码）
    import importlib
    metadata = registry.get_plugin_metadata(name)
    module_name = metadata.plugin_class.__module__
    module = importlib.reload(importlib.import_module(module_name))
    
    # 重新加载
    plugin = registry.load_plugin(name, context)
    print(f"✓ 插件 '{name}' 已热重载")
```

## API 参考

### PluginRegistry 构造函数

```python
def __init__(self, logger: Optional[logging.Logger] = None)
```

**参数:**
- `logger`: 日志记录器（可选）

### register()

```python
def register(
    self,
    plugin_class: Type[BasePlugin],
    metadata: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
    source: str = "manual"
) -> str
```

**参数:**
- `plugin_class`: 插件类（必须继承 BasePlugin）
- `metadata`: 插件元数据（可选）
- `name`: 插件名称（可选，默认使用类名）
- `source`: 插件来源标识（可选）

**返回:** 插件名称

**异常:**
- `ValueError`: 插件类无效或名称冲突

### discover()

```python
def discover(self, paths: Optional[List[str]] = None) -> int
```

**参数:**
- `paths`: 要扫描的目录路径列表（可选）

**返回:** 发现的插件数量

### load_plugin()

```python
def load_plugin(
    self,
    name: str,
    context: PluginContext,
    **init_kwargs
) -> BasePlugin
```

**参数:**
- `name`: 插件名称
- `context`: 插件上下文
- `**init_kwargs`: 传递给插件构造函数的参数

**返回:** 插件实例

**异常:**
- `KeyError`: 插件未注册
- `RuntimeError`: 插件加载失败

### get_plugins_by_interface()

```python
def get_plugins_by_interface(self, interface_name: str) -> List[str]
```

**参数:**
- `interface_name`: 接口名称（如 "IMapPlugin"）

**返回:** 匹配的插件名称列表

### get_plugin_list()

```python
def get_plugin_list(self) -> List[Dict[str, Any]]
```

**返回:** 插件信息列表，每个元素包含：
- `name`: 插件名称
- `version`: 版本号
- `description`: 描述
- `author`: 作者
- `loaded`: 是否已加载
- `source`: 来源
- `class`: 类名
- `dependencies`: 依赖列表

## 最佳实践

### 1. 使用统一的发现机制

```python
# 推荐：使用 discover() 方法
registry = PluginRegistry(logger=logger)
registry.discover(['plugins/', 'plugins/custom/'])
```

### 2. 错误处理

```python
try:
    plugin = registry.load_plugin('my_plugin', context)
except KeyError:
    print("插件未注册")
except RuntimeError as e:
    print(f"插件加载失败: {e}")
```

### 3. 延迟加载

```python
# 只在需要时才加载插件
if 'custom_map' in registry:
    if not registry.is_loaded('custom_map'):
        plugin = registry.load_plugin('custom_map', context)
```

### 4. 资源清理

```python
# 程序退出前清理
try:
    registry.clear()
finally:
    print("插件系统已关闭")
```

### 5. 日志记录

```python
# 使用日志追踪插件状态
logger = LogManager.get_logger('plugin_registry', console_output=True)
registry = PluginRegistry(logger=logger)
```

## 性能考虑

- **目录扫描**: 仅在启动时扫描一次，避免性能开销
- **延迟加载**: 插件实例仅在需要时创建
- **缓存**: 已加载的插件实例会被缓存
- **元数据**: 轻量级元数据对象，占用内存小

## 常见问题

### Q: 为什么插件没有被发现？

A: 检查以下几点：
1. 配置文件路径是否正确
2. 目录路径是否存在
3. 插件类是否继承自 `BasePlugin`
4. 配置文件中 `enabled` 是否为 `true`

### Q: 如何禁用某个插件？

A: 在配置文件中设置 `enabled: false`

### Q: 如何查看所有可用的插件？

A: 使用 `registry.get_plugin_list()` 查看详细信息

### Q: 插件加载顺序重要吗？

A: 如果插件之间有依赖关系，需要先加载被依赖的插件

## 相关文档

- [插件系统概述](plugin_system.md)
- [快速上手指南](plugin_quickstart.md)
- [使用示例](plugin_registry_examples.py)
- [配置文件示例](../config/plugins.yaml)
