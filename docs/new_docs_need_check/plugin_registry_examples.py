"""
插件注册表使用示例

展示如何使用 PluginRegistry 进行插件的注册、发现、加载和管理。
"""

from src.plugins.plugin_registry import PluginRegistry, PluginMetadata
from src.plugins import IMapPlugin, PluginContext
from src.utils.log_manager import LogManager
from typing import Dict, Any


# ========================================
# 示例 1: 基本使用 - 手动注册插件
# ========================================

def example_manual_registration():
    """手动注册插件示例"""
    print("\n" + "="*60)
    print("示例 1: 手动注册插件")
    print("="*60 + "\n")
    
    # 创建注册表
    logger = LogManager.get_logger('plugin_registry')
    registry = PluginRegistry(logger=logger)
    
    # 定义一个简单的插件
    class SimpleMapPlugin(IMapPlugin):
        def __init__(self, width: int, height: int):
            super().__init__()
            self._width = width
            self._height = height
        
        def init(self, context: PluginContext):
            self._context = context
        
        def on_load(self):
            self._mark_loaded()
        
        def on_unload(self):
            self._mark_unloaded()
        
        def get_metadata(self):
            return {
                "name": "SimpleMap",
                "version": "1.0.0",
                "description": "A simple map plugin",
                "author": "Example",
                "dependencies": []
            }
        
        @property
        def width(self): return self._width
        
        @property
        def height(self): return self._height
        
        @property
        def grid(self): return None
        
        def initialize_map(self): pass
    
    # 注册插件
    registry.register(
        plugin_class=SimpleMapPlugin,
        name="simple_map",
        metadata={
            "name": "SimpleMap",
            "version": "1.0.0",
            "description": "A simple map plugin",
            "author": "Example",
            "dependencies": []
        }
    )
    
    print(f"✓ 已注册插件数量: {len(registry)}")
    print(f"✓ 注册表信息: {registry}")
    
    # 查看插件列表
    plugins = registry.get_plugin_list()
    for plugin in plugins:
        print(f"  - {plugin['name']} v{plugin['version']}: {plugin['description']}")


# ========================================
# 示例 2: 从配置文件发现插件
# ========================================

def example_discover_from_config():
    """从配置文件发现插件示例"""
    print("\n" + "="*60)
    print("示例 2: 从配置文件发现插件")
    print("="*60 + "\n")
    
    registry = PluginRegistry(logger=LogManager.get_logger('registry'))
    
    # 从配置文件发现
    count = registry._discover_from_config('config/plugins.yaml')
    
    print(f"✓ 从配置文件发现了 {count} 个插件")
    
    # 显示所有已注册的插件
    print("\n已注册的插件:")
    for plugin_info in registry.get_plugin_list():
        status = "✓ 已启用" if plugin_info['loaded'] else "○ 未加载"
        print(f"  {status} {plugin_info['name']} v{plugin_info['version']}")
        print(f"      描述: {plugin_info['description']}")
        print(f"      来源: {plugin_info['source']}")
        if plugin_info['dependencies']:
            print(f"      依赖: {', '.join(plugin_info['dependencies'])}")


# ========================================
# 示例 3: 从目录扫描发现插件
# ========================================

def example_discover_from_directory():
    """从目录扫描发现插件示例"""
    print("\n" + "="*60)
    print("示例 3: 从目录扫描发现插件")
    print("="*60 + "\n")
    
    registry = PluginRegistry(logger=LogManager.get_logger('registry'))
    
    # 扫描目录
    paths = [
        'plugins/',
        'plugins/custom/',
        'plugins/community/'
    ]
    
    for path in paths:
        count = registry._discover_from_directory(path)
        print(f"✓ 从目录 '{path}' 发现了 {count} 个插件")
    
    print(f"\n总计: {len(registry)} 个插件已注册")


# ========================================
# 示例 4: 统一发现（配置 + 目录）
# ========================================

def example_unified_discover():
    """统一发现示例"""
    print("\n" + "="*60)
    print("示例 4: 统一发现插件")
    print("="*60 + "\n")
    
    registry = PluginRegistry(logger=LogManager.get_logger('registry'))
    
    # 使用 discover 方法（会同时使用配置文件和目录扫描）
    count = registry.discover(['plugins/', 'src/plugins/'])
    
    print(f"✓ 总共发现 {count} 个插件")
    print(f"✓ 注册表状态: {registry}")


# ========================================
# 示例 5: 加载和使用插件
# ========================================

def example_load_and_use():
    """加载和使用插件示例"""
    print("\n" + "="*60)
    print("示例 5: 加载和使用插件")
    print("="*60 + "\n")
    
    registry = PluginRegistry(logger=LogManager.get_logger('registry'))
    
    # 先注册一个测试插件
    class TestMapPlugin(IMapPlugin):
        def __init__(self, width: int, height: int):
            super().__init__()
            self._width = width
            self._height = height
            self._initialized = False
        
        def init(self, context: PluginContext):
            self._context = context
            context.log_info("TestMapPlugin initialized")
        
        def on_load(self):
            self._context.log_info("TestMapPlugin loading...")
            self._mark_loaded()
        
        def on_unload(self):
            self._context.log_info("TestMapPlugin unloading...")
            self._mark_unloaded()
        
        def get_metadata(self):
            return {
                "name": "TestMap",
                "version": "1.0.0",
                "description": "Test map plugin",
                "author": "Test",
                "dependencies": []
            }
        
        @property
        def width(self): return self._width
        
        @property
        def height(self): return self._height
        
        @property
        def grid(self): return None
        
        def initialize_map(self):
            self._initialized = True
            print(f"  地图已初始化: {self._width}x{self._height}")
    
    # 注册插件
    registry.register(TestMapPlugin, name="test_map")
    print("✓ 插件已注册")
    
    # 创建上下文
    context = PluginContext(
        config={},
        logger=LogManager.get_logger('plugin')
    )
    
    # 加载插件
    plugin = registry.load_plugin('test_map', context, width=200, height=150)
    print(f"✓ 插件已加载: {plugin.get_metadata()['name']}")
    
    # 使用插件
    plugin.initialize_map()
    print(f"✓ 地图尺寸: {plugin.width} x {plugin.height}")
    
    # 检查加载状态
    print(f"✓ 是否已加载: {registry.is_loaded('test_map')}")
    
    # 卸载插件
    registry.unload_plugin('test_map')
    print("✓ 插件已卸载")
    print(f"✓ 是否已加载: {registry.is_loaded('test_map')}")


# ========================================
# 示例 6: 按接口查询插件
# ========================================

def example_query_by_interface():
    """按接口查询插件示例"""
    print("\n" + "="*60)
    print("示例 6: 按接口查询插件")
    print("="*60 + "\n")
    
    registry = PluginRegistry(logger=LogManager.get_logger('registry'))
    
    # 注册几个不同类型的插件
    from src.plugins import ITimePlugin, IPopulationPlugin
    
    class TestMapPlugin(IMapPlugin):
        def __init__(self): super().__init__()
        def init(self, context): self._context = context
        def on_load(self): self._mark_loaded()
        def on_unload(self): self._mark_unloaded()
        def get_metadata(self): return {"name": "TestMap", "version": "1.0", "description": "", "author": "", "dependencies": []}
        @property
        def width(self): return 0
        @property
        def height(self): return 0
        @property
        def grid(self): return None
        def initialize_map(self): pass
    
    class TestTimePlugin(ITimePlugin):
        def __init__(self): super().__init__()
        def init(self, context): self._context = context
        def on_load(self): self._mark_loaded()
        def on_unload(self): self._mark_unloaded()
        def get_metadata(self): return {"name": "TestTime", "version": "1.0", "description": "", "author": "", "dependencies": []}
        def step(self): pass
        def is_end(self): return False
        @property
        def start_time(self): return 0
        @property
        def total_steps(self): return 0
        @property
        def end_time(self): return 0
        @property
        def current_time(self): return 0
    
    # 注册插件
    registry.register(TestMapPlugin, name="map1")
    registry.register(TestMapPlugin, name="map2")
    registry.register(TestTimePlugin, name="time1")
    
    # 按接口查询
    map_plugins = registry.get_plugins_by_interface('IMapPlugin')
    time_plugins = registry.get_plugins_by_interface('ITimePlugin')
    
    print(f"✓ 找到 {len(map_plugins)} 个 IMapPlugin: {map_plugins}")
    print(f"✓ 找到 {len(time_plugins)} 个 ITimePlugin: {time_plugins}")


# ========================================
# 示例 7: 完整的插件管理流程
# ========================================

def example_complete_workflow():
    """完整的插件管理流程示例"""
    print("\n" + "="*60)
    print("示例 7: 完整的插件管理流程")
    print("="*60 + "\n")
    
    # 1. 创建注册表
    registry = PluginRegistry(logger=LogManager.get_logger('registry'))
    print("1. ✓ 创建注册表")
    
    # 2. 发现插件
    count = registry.discover()
    print(f"2. ✓ 发现 {count} 个插件")
    
    # 3. 查看插件列表
    print("\n3. 已注册的插件:")
    for info in registry.get_plugin_list():
        print(f"   - {info['name']} (v{info['version']})")
    
    # 4. 检查插件是否存在
    if 'simple_map' in registry:
        print("\n4. ✓ 'simple_map' 插件已注册")
    
    # 5. 获取元数据
    metadata = registry.get_plugin_metadata('simple_map')
    if metadata:
        print(f"5. ✓ 元数据: {metadata}")
    
    # 6. 加载特定插件
    # context = PluginContext(config={}, logger=LogManager.get_logger('plugin'))
    # plugin = registry.load_plugin('simple_map', context, width=100, height=100)
    # print(f"6. ✓ 已加载插件: {plugin.get_metadata()['name']}")
    
    # 7. 获取所有已加载的插件
    loaded = registry.get_all_loaded()
    print(f"\n7. 已加载的插件数量: {len(loaded)}")
    
    # 8. 清理
    registry.clear()
    print(f"8. ✓ 注册表已清空: {registry}")


# ========================================
# 运行所有示例
# ========================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("PluginRegistry 使用示例")
    print("="*60)
    
    try:
        example_manual_registration()
    except Exception as e:
        print(f"示例 1 失败: {e}")
    
    try:
        example_discover_from_config()
    except Exception as e:
        print(f"示例 2 失败: {e}")
    
    try:
        example_discover_from_directory()
    except Exception as e:
        print(f"示例 3 失败: {e}")
    
    try:
        example_unified_discover()
    except Exception as e:
        print(f"示例 4 失败: {e}")
    
    try:
        example_load_and_use()
    except Exception as e:
        print(f"示例 5 失败: {e}")
    
    try:
        example_query_by_interface()
    except Exception as e:
        print(f"示例 6 失败: {e}")
    
    try:
        example_complete_workflow()
    except Exception as e:
        print(f"示例 7 失败: {e}")
    
    print("\n" + "="*60)
    print("所有示例执行完毕")
    print("="*60 + "\n")
