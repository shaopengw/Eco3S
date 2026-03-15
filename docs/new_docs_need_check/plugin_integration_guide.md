# 插件系统集成指南

本指南说明如何将 PluginRegistry 与 AgentWorld 现有系统集成。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│              AgentWorld Application                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐         ┌────────────────┐        │
│  │   DIContainer   │◄────────┤ PluginRegistry │        │
│  │  (依赖注入容器)  │         │  (插件注册表)   │        │
│  └────────┬────────┘         └───────┬────────┘        │
│           │                          │                  │
│           │ 注册                     │ 加载             │
│           │                          │                  │
│  ┌────────▼──────────────────────────▼────────┐        │
│  │          PluginManager                      │        │
│  │     (统一管理插件生命周期)                   │        │
│  └─────────────────┬───────────────────────────┘        │
│                    │                                     │
│     ┌──────────────┼──────────────┐                     │
│     │              │              │                     │
│  ┌──▼───┐     ┌───▼────┐    ┌───▼────┐                │
│  │ Map  │     │  Time  │    │  Towns │  ...            │
│  │Plugin│     │ Plugin │    │ Plugin │                 │
│  └──────┘     └────────┘    └────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## 集成步骤

### 步骤 1: 初始化插件系统

在应用启动时初始化插件注册表和管理器。

**推荐位置**: `entrypoints/main.py` 或 `src/app.py`

```python
from src.plugins import PluginRegistry, PluginManager, PluginContext
from src.utils.log_manager import LogManager

def initialize_plugin_system(config: Dict[str, Any]) -> Tuple[PluginRegistry, PluginManager]:
    """
    初始化插件系统
    
    Returns:
        (registry, manager): 插件注册表和管理器
    """
    # 创建日志记录器
    logger = LogManager.get_logger('plugin_system', console_output=True)
    
    # 创建注册表
    registry = PluginRegistry(logger=logger)
    
    # 发现插件
    plugin_paths = config.get('plugin_paths', ['plugins/', 'plugins/custom/'])
    count = registry.discover(plugin_paths)
    logger.info(f"发现了 {count} 个插件")
    
    # 创建管理器
    manager = PluginManager(
        config=config.get('plugins', {}),
        logger=logger
    )
    
    return registry, manager
```

### 步骤 2: 配置插件路径

在配置文件中指定插件路径。

**推荐位置**: `config/*/simulation_config.yaml`

```yaml
# 插件系统配置
plugins:
  # 基础配置
  enabled: true
  debug_mode: false
  
  # 插件路径
  plugin_paths:
    - plugins/              # 官方插件
    - plugins/custom/       # 自定义插件
    - plugins/community/    # 社区插件
  
  # 发现机制
  discovery:
    use_config_file: true   # 使用 config/plugins.yaml
    use_directory_scan: true # 扫描目录
  
  # 加载选项
  loading:
    lazy_load: true         # 延迟加载
    hot_reload: false       # 热重载（开发模式）
    load_timeout: 30        # 加载超时（秒）
```

### 步骤 3: 创建插件配置清单

创建插件清单文件。

**文件路径**: `config/plugins.yaml`

```yaml
plugins:
  # 自定义地图插件
  - name: custom_map
    module: plugins.custom_map.CustomMapPlugin
    enabled: true
    metadata:
      version: "1.0.0"
      description: "自定义地图插件，支持多层次地图"
      author: "Eco3S"
      dependencies: []
    init_params:
      width: 100
      height: 100
      data_file: "towns_data.json"
  
  # 高级时间插件
  - name: advanced_time
    module: plugins.time.AdvancedTimePlugin
    enabled: true
    metadata:
      version: "2.0.0"
      description: "支持时区和季节的高级时间系统"
  
  # 社交网络增强插件
  - name: enhanced_social
    module: plugins.social.EnhancedSocialNetworkPlugin
    enabled: false  # 暂时禁用
    metadata:
      version: "1.5.0"
      description: "增强的社交网络，支持社区检测"
      dependencies: ["custom_map"]  # 依赖自定义地图插件

# 扫描目录
plugin_paths:
  - plugins/
  - plugins/custom/
  - plugins/community/

# 全局设置
settings:
  hot_reload: false         # 生产环境关闭
  verbose_loading: true     # 显示加载详情
  load_timeout: 30          # 加载超时
  validate_dependencies: true  # 验证依赖
```

### 步骤 4: 与 DIContainer 集成

将插件实例注册到依赖注入容器。

**推荐位置**: `src/app.py` 或 `entrypoints/main.py`

```python
from src.utils.di_container import DIContainer
from src.plugins import PluginRegistry, PluginContext

def integrate_plugins_with_di(
    di_container: DIContainer,
    registry: PluginRegistry,
    config: Dict[str, Any]
) -> None:
    """
    将插件系统与依赖注入容器集成
    
    Args:
        di_container: 依赖注入容器
        registry: 插件注册表
        config: 应用配置
    """
    logger = LogManager.get_logger('plugin_integration')
    
    # 创建插件上下文
    context = PluginContext(
        config=config.get('plugins', {}),
        logger=logger
    )
    
    # 加载核心插件
    core_plugins = [
        ('map', 'custom_map'),
        ('time', 'advanced_time'),
        ('towns', 'custom_towns'),
        ('population', 'custom_population'),
    ]
    
    for interface_name, plugin_name in core_plugins:
        try:
            # 检查插件是否注册
            if not registry.has_plugin(plugin_name):
                logger.warning(f"插件 '{plugin_name}' 未注册，跳过")
                continue
            
            # 加载插件
            plugin = registry.load_plugin(
                plugin_name,
                context,
                **config.get(f'{interface_name}_init_params', {})
            )
            
            # 注册到 DI 容器（使用接口名）
            di_container.register_instance(interface_name, plugin)
            
            logger.info(f"✓ 插件 '{plugin_name}' 已加载并注册到 DI 容器")
            
        except Exception as e:
            logger.error(f"✗ 加载插件 '{plugin_name}' 失败: {e}")
            raise
    
    # 将注册表本身也注册到 DI 容器
    di_container.register_instance('plugin_registry', registry)
```

### 步骤 5: 在 Simulation 中使用插件

修改 Simulation 类以支持插件系统。

**修改文件**: `src/simulation/simulation.py`

```python
class Simulation:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.di_container = DIContainer()
        
        # 初始化插件系统
        self.plugin_registry, self.plugin_manager = initialize_plugin_system(config)
        
        # 集成插件与 DI 容器
        integrate_plugins_with_di(
            self.di_container,
            self.plugin_registry,
            config
        )
        
        # 从 DI 容器获取模块（现在可能是插件）
        self.map = self.di_container.resolve('map')
        self.time = self.di_container.resolve('time')
        self.towns = self.di_container.resolve('towns')
        # ... 其他模块
    
    def run(self):
        """运行模拟"""
        # 使用插件提供的功能（与使用原生模块相同）
        self.map.initialize_map()
        self.time.advance_time()
        # ... 使用其他模块
```

### 步骤 6: 创建自定义插件

创建符合接口的自定义插件。

**示例**: 自定义地图插件

**文件路径**: `plugins/custom_map/custom_map_plugin.py`

```python
from src.plugins import IMapPlugin, PluginContext
from src.environment.interfaces import IMap
from typing import Dict, Any, Optional

class CustomMapPlugin(IMapPlugin):
    """
    自定义地图插件
    
    同时实现 IMapPlugin（插件接口）和 IMap（业务接口）
    """
    
    def __init__(self, context: PluginContext, 
                 width: int = 100, 
                 height: int = 100,
                 data_file: Optional[str] = None):
        """
        初始化插件
        
        Args:
            context: 插件上下文
            width: 地图宽度
            height: 地图高度
            data_file: 数据文件路径
        """
        super().__init__(context)
        self.width = width
        self.height = height
        self.data_file = data_file
        self._initialized = False
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"CustomMapPlugin 正在加载 ({self.width}x{self.height})")
        
        # 订阅相关事件
        self.context.event_bus.subscribe('simulation_start', self._on_simulation_start)
        self.context.event_bus.subscribe('time_advanced', self._on_time_advanced)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("CustomMapPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('simulation_start', self._on_simulation_start)
        self.context.event_bus.unsubscribe('time_advanced', self._on_time_advanced)
        
        # 清理资源
        self._initialized = False
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "CustomMap",
            "version": "1.0.0",
            "description": "自定义地图插件，支持多层次地图",
            "author": "Your Name",
            "dependencies": []
        }
    
    # ===== IMap 业务接口方法 =====
    
    @property
    def width(self) -> int:
        """地图宽度"""
        return self._width
    
    @width.setter
    def width(self, value: int):
        self._width = value
    
    @property
    def height(self) -> int:
        """地图高度"""
        return self._height
    
    @height.setter
    def height(self, value: int):
        self._height = value
    
    def initialize_map(self) -> None:
        """初始化地图"""
        if self._initialized:
            self.logger.warning("地图已经初始化")
            return
        
        self.logger.info(f"正在初始化 {self.width}x{self.height} 地图")
        
        # 加载数据文件
        if self.data_file:
            self._load_data(self.data_file)
        
        self._initialized = True
        
        # 发布事件
        self.context.event_bus.publish('map_initialized', {
            'width': self.width,
            'height': self.height
        })
    
    def get_distance(self, pos1: tuple, pos2: tuple) -> float:
        """计算两点距离"""
        x1, y1 = pos1
        x2, y2 = pos2
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    
    # ===== 内部方法 =====
    
    def _load_data(self, file_path: str) -> None:
        """加载地图数据"""
        self.logger.info(f"正在从 {file_path} 加载地图数据")
        # 实现数据加载逻辑
        pass
    
    def _on_simulation_start(self, data: Dict[str, Any]) -> None:
        """模拟开始时的处理"""
        self.logger.info("收到simulation_start事件")
        
    def _on_time_advanced(self, data: Dict[str, Any]) -> None:
        """时间推进时的处理"""
        # 根据时间更新地图状态
        pass
```

**文件路径**: `plugins/custom_map/__init__.py`

```python
from .custom_map_plugin import CustomMapPlugin

__all__ = ['CustomMapPlugin']
```

### 步骤 7: 测试插件集成

创建测试脚本验证插件系统。

**文件路径**: `tests/test_plugin_integration.py`

```python
import unittest
from src.plugins import PluginRegistry, PluginContext
from src.utils.log_manager import LogManager
from src.utils.di_container import DIContainer

class TestPluginIntegration(unittest.TestCase):
    """测试插件系统集成"""
    
    def setUp(self):
        """测试前设置"""
        self.logger = LogManager.get_logger('test_plugins')
        self.registry = PluginRegistry(logger=self.logger)
        self.di_container = DIContainer()
    
    def test_discover_plugins(self):
        """测试插件发现"""
        count = self.registry.discover(['plugins/'])
        self.assertGreater(count, 0, "应该发现至少一个插件")
    
    def test_load_plugin(self):
        """测试插件加载"""
        # 发现插件
        self.registry.discover(['plugins/'])
        
        # 创建上下文
        context = PluginContext(
            config={'debug': True},
            logger=self.logger
        )
        
        # 加载插件
        if self.registry.has_plugin('custom_map'):
            plugin = self.registry.load_plugin(
                'custom_map',
                context,
                width=100,
                height=100
            )
            self.assertIsNotNone(plugin)
            self.assertTrue(self.registry.is_loaded('custom_map'))
    
    def test_di_container_integration(self):
        """测试与 DI 容器集成"""
        # 发现并加载插件
        self.registry.discover(['plugins/'])
        context = PluginContext(config={}, logger=self.logger)
        
        if self.registry.has_plugin('custom_map'):
            plugin = self.registry.load_plugin('custom_map', context)
            
            # 注册到 DI 容器
            self.di_container.register_instance('map', plugin)
            
            # 从 DI 容器解析
            map_instance = self.di_container.resolve('map')
            self.assertEqual(map_instance, plugin)
    
    def test_plugin_by_interface(self):
        """测试按接口查询插件"""
        self.registry.discover(['plugins/'])
        
        # 查询地图插件
        map_plugins = self.registry.get_plugins_by_interface('IMapPlugin')
        self.assertIsInstance(map_plugins, list)
        
        if len(map_plugins) > 0:
            self.logger.info(f"找到 {len(map_plugins)} 个地图插件: {map_plugins}")

if __name__ == '__main__':
    unittest.main()
```

## 完整工作流程

### 应用启动流程

```python
# entrypoints/main.py

from src.plugins import PluginRegistry, PluginManager, PluginContext
from src.utils.di_container import DIContainer
from src.simulation.simulation import Simulation
import yaml

def main():
    # 1. 加载配置
    with open('config/default/simulation_config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 2. 初始化日志
    logger = LogManager.get_logger('main', console_output=True)
    
    # 3. 创建插件注册表
    registry = PluginRegistry(logger=logger)
    
    # 4. 发现插件
    plugin_paths = config.get('plugin_paths', ['plugins/'])
    count = registry.discover(plugin_paths)
    logger.info(f"✓ 发现了 {count} 个插件")
    
    # 5. 创建 DI 容器
    di_container = DIContainer()
    
    # 6. 创建插件上下文
    context = PluginContext(
        config=config.get('plugins', {}),
        logger=logger
    )
    
    # 7. 加载并注册核心插件
    core_plugins = ['custom_map', 'advanced_time', 'custom_towns']
    for plugin_name in core_plugins:
        if registry.has_plugin(plugin_name):
            try:
                plugin = registry.load_plugin(plugin_name, context)
                interface_name = plugin_name.replace('custom_', '').replace('advanced_', '')
                di_container.register_instance(interface_name, plugin)
                logger.info(f"✓ '{plugin_name}' 已加载")
            except Exception as e:
                logger.error(f"✗ 加载 '{plugin_name}' 失败: {e}")
    
    # 8. 创建并运行模拟
    simulation = Simulation(config, di_container)
    simulation.run()
    
    # 9. 清理（程序退出时）
    registry.clear()
    logger.info("✓ 插件系统已关闭")

if __name__ == '__main__':
    main()
```

## 最佳实践

### 1. 插件命名约定

- **插件类**: `{Feature}Plugin` (如 `CustomMapPlugin`)
- **插件名称**: `{feature}_{type}` (如 `custom_map`)
- **模块路径**: `plugins.{category}.{PluginClass}`

### 2. 插件目录结构

```
plugins/
├── custom_map/              # 自定义地图插件
│   ├── __init__.py
│   ├── custom_map_plugin.py
│   └── data/
│       └── map_data.json
├── advanced_time/           # 高级时间插件
│   ├── __init__.py
│   └── advanced_time_plugin.py
└── community/               # 社区插件
    └── social/
        ├── __init__.py
        └── enhanced_social_plugin.py
```

### 3. 错误处理

```python
# 始终使用 try-except 处理插件加载
try:
    plugin = registry.load_plugin('my_plugin', context)
except KeyError:
    logger.error("插件未注册")
except RuntimeError as e:
    logger.error(f"插件加载失败: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
```

### 4. 依赖管理

在插件元数据中声明依赖：

```python
def get_metadata(self) -> Dict[str, Any]:
    return {
        "name": "EnhancedSocial",
        "version": "1.5.0",
        "dependencies": ["custom_map", "advanced_time"]  # 依赖其他插件
    }
```

### 5. 资源清理

始终实现 `on_unload()` 方法：

```python
def on_unload(self) -> None:
    """清理插件资源"""
    # 取消事件订阅
    self.context.event_bus.unsubscribe('event_name', self.handler)
    
    # 关闭文件句柄
    if hasattr(self, 'file'):
        self.file.close()
    
    # 释放其他资源
    self.cleanup_resources()
```

## 常见问题

### Q1: 如何在不修改核心代码的情况下使用插件？

A: 使用依赖注入容器。将插件注册为接口的实现，核心代码通过接口访问：

```python
# 而不是直接实例化
# map = Map(width=100, height=100)

# 从 DI 容器获取（可能是插件也可能是原生实现）
map = di_container.resolve('map')
```

### Q2: 插件与原生模块有什么区别？

A: 插件实现了相同的业务接口（如 `IMap`），因此可以无缝替换。区别在于：

- 插件继承 `BasePlugin`，有生命周期管理
- 插件可以通过 `EventBus` 与其他插件通信
- 插件可以动态加载和卸载

### Q3: 如何调试插件？

A: 启用详细日志：

```python
registry = PluginRegistry(
    logger=LogManager.get_logger('plugin', console_output=True)
)
```

设置断点在 `on_load()` 和业务方法中。

### Q4: 多个插件实现同一接口怎么办？

A: 使用不同的注册名称：

```python
# 两个地图插件
di_container.register_instance('map_simple', simple_map_plugin)
di_container.register_instance('map_advanced', advanced_map_plugin)

# 根据需要选择
map = di_container.resolve('map_advanced')
```

## 相关文档

- [插件系统概述](plugin_system.md)
- [PluginRegistry 详细文档](plugin_registry.md)
- [快速上手指南](plugin_quickstart.md)
- [插件示例](plugin_registry_examples.py)
