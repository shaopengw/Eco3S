"""
插件系统示例

展示如何创建和使用插件。
"""

from typing import Dict, Any
from src.plugins import (
    IMapPlugin,
    PluginContext,
    PluginManager,
    PluginLoader
)
from src.utils.log_manager import LogManager


# ========================================
# 示例 1: 创建一个简单的地图插件
# ========================================

class CustomMapPlugin(IMapPlugin):
    """
    自定义地图插件示例
    
    展示如何实现一个完整的插件，包括生命周期管理和业务逻辑。
    """
    
    def __init__(self, width: int, height: int, data_file: str):
        """初始化插件（业务参数）"""
        # 初始化 BasePlugin
        super().__init__()
        
        # 业务属性
        self._width = width
        self._height = height
        self._data_file = data_file
        self._grid = None
        self._initialized = False
    
    # ----------------------------------------
    # BasePlugin 生命周期方法
    # ----------------------------------------
    
    def init(self, context: PluginContext) -> None:
        """插件初始化（接收上下文）"""
        self._context = context
        self._context.log_info(f"CustomMapPlugin initializing with size {self._width}x{self._height}")
        
        # 从上下文获取配置
        debug_mode = context.get_config('debug_mode', False)
        if debug_mode:
            self._context.log_debug("Debug mode enabled")
    
    def on_load(self) -> None:
        """插件加载时的钩子"""
        self._context.log_info("CustomMapPlugin loading...")
        
        # 订阅事件
        self._context.event_bus.subscribe('simulation_start', self._on_simulation_start)
        
        # 标记为已加载
        self._mark_loaded()
        self._context.log_info("CustomMapPlugin loaded successfully")
    
    def on_unload(self) -> None:
        """插件卸载时的钩子"""
        self._context.log_info("CustomMapPlugin unloading...")
        
        # 取消订阅事件
        self._context.event_bus.unsubscribe('simulation_start', self._on_simulation_start)
        
        # 清理资源
        self._grid = None
        self._initialized = False
        
        # 标记为未加载
        self._mark_unloaded()
        self._context.log_info("CustomMapPlugin unloaded")
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取插件元数据"""
        return {
            "name": "CustomMap",
            "version": "1.0.0",
            "description": "A custom map plugin with enhanced features",
            "author": "AgentWorld Team",
            "dependencies": []
        }
    
    # ----------------------------------------
    # 事件处理器
    # ----------------------------------------
    
    def _on_simulation_start(self, data: Any) -> None:
        """处理模拟开始事件"""
        self._context.log_info(f"Simulation started! Data: {data}")
    
    # ----------------------------------------
    # IMap 业务方法实现
    # ----------------------------------------
    
    @property
    def width(self) -> int:
        """获取地图宽度"""
        return self._width
    
    @property
    def height(self) -> int:
        """获取地图高度"""
        return self._height
    
    @property
    def grid(self):
        """获取网格"""
        return self._grid
    
    def initialize_map(self) -> None:
        """初始化地图"""
        self._context.log_info("Initializing map grid...")
        self._grid = [[0 for _ in range(self._width)] for _ in range(self._height)]
        self._initialized = True
        
        # 发布自定义事件
        self._context.event_bus.publish('map_initialized', {
            'width': self._width,
            'height': self._height
        })
    
    # ... 实现其他 IMap 方法（此处省略以保持示例简洁）
    # 在实际实现中，需要实现所有 IMap 接口定义的抽象方法


# ========================================
# 示例 2: 使用插件管理器
# ========================================

def example_basic_usage():
    """基本使用示例"""
    print("\n=== 示例 2: 基本使用 ===\n")
    
    # 1. 创建插件管理器
    manager = PluginManager(
        config={
            'debug_mode': True,
            'simulation': {'population': 1000}
        },
        logger=LogManager.get_logger('plugin_system')
    )
    
    # 2. 创建并加载插件
    custom_map = CustomMapPlugin(width=100, height=100, data_file='towns.json')
    manager.load_plugin('custom_map', custom_map)
    
    # 3. 获取加载的插件
    loaded_map = manager.get_plugin('custom_map')
    print(f"Plugin loaded: {loaded_map.get_metadata()['name']}")
    
    # 4. 使用插件的业务方法
    loaded_map.initialize_map()
    print(f"Map size: {loaded_map.width}x{loaded_map.height}")
    
    # 5. 通过事件总线进行通信
    manager.event_bus.publish('simulation_start', {'time': 0})
    
    # 6. 卸载插件
    manager.unload_plugin('custom_map')
    print("Plugin unloaded")


# ========================================
# 示例 3: 使用插件加载器
# ========================================

def example_plugin_loader():
    """插件加载器示例"""
    print("\n=== 示例 3: 插件加载器 ===\n")
    
    # 1. 创建管理器
    manager = PluginManager(
        config={'debug_mode': False},
        logger=LogManager.get_logger('plugin_system')
    )
    
    # 2. 创建加载器
    loader = PluginLoader(manager)
    
    # 3. 从类加载插件
    loader.load_from_class(
        'custom_map',
        CustomMapPlugin,
        width=200,
        height=150,
        data_file='towns.json'
    )
    
    print(f"Loaded plugins: {list(manager.get_all_plugins().keys())}")
    
    # 4. 卸载所有插件
    manager.unload_all()


# ========================================
# 示例 4: 插件间通信（事件总线）
# ========================================

def example_event_communication():
    """插件间通信示例"""
    print("\n=== 示例 4: 插件间通信 ===\n")
    
    manager = PluginManager(logger=LogManager.get_logger('plugin_system'))
    
    # 加载两个插件
    map_plugin = CustomMapPlugin(100, 100, 'towns.json')
    manager.load_plugin('map', map_plugin)
    
    # 设置事件监听器
    def on_map_ready(data):
        print(f"✓ 收到地图就绪事件: {data}")
    
    manager.event_bus.subscribe('map_initialized', on_map_ready)
    
    # 触发地图初始化（会发布事件）
    map_plugin.initialize_map()
    
    # 清理
    manager.unload_all()


# ========================================
# 示例 5: 插件依赖管理
# ========================================

class DependentPlugin(IMapPlugin):
    """依赖其他插件的插件示例"""
    
    def __init__(self):
        super().__init__()
    
    def init(self, context: PluginContext) -> None:
        self._context = context
    
    def on_load(self) -> None:
        self._mark_loaded()
        # 可以通过 registry 访问其他插件
        map_plugin = self._context.registry.get('map')
        if map_plugin:
            print(f"Found map plugin: {map_plugin.get_metadata()['name']}")
    
    def on_unload(self) -> None:
        self._mark_unloaded()
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DependentPlugin",
            "version": "1.0.0",
            "description": "A plugin that depends on map plugin",
            "author": "AgentWorld Team",
            "dependencies": ["map"]  # 声明依赖
        }
    
    # 实现其他必需的抽象方法...
    @property
    def width(self) -> int:
        return 0
    
    @property
    def height(self) -> int:
        return 0
    
    @property
    def grid(self):
        return None
    
    def initialize_map(self) -> None:
        pass


def example_plugin_dependencies():
    """插件依赖示例"""
    print("\n=== 示例 5: 插件依赖 ===\n")
    
    manager = PluginManager(logger=LogManager.get_logger('plugin_system'))
    
    # 1. 先加载被依赖的插件
    map_plugin = CustomMapPlugin(100, 100, 'towns.json')
    manager.load_plugin('map', map_plugin)
    
    # 2. 加载依赖插件（会自动检查依赖）
    dependent = DependentPlugin()
    manager.load_plugin('dependent', dependent)
    
    print(f"Load order: {manager.get_load_order()}")
    
    # 3. 卸载（按逆序）
    manager.unload_all()


# ========================================
# 运行所有示例
# ========================================

if __name__ == '__main__':
    print("=" * 60)
    print("插件系统示例")
    print("=" * 60)
    
    example_basic_usage()
    example_plugin_loader()
    example_event_communication()
    example_plugin_dependencies()
    
    print("\n" + "=" * 60)
    print("所有示例执行完毕")
    print("=" * 60)
