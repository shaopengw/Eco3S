"""
测试插件系统发现和加载功能
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins import PluginRegistry, PluginContext
from src.plugins.plugin_context import EventBus
from src.utils.logger import LogManager

def test_plugin_discovery():
    """测试插件发现功能"""
    print("=" * 60)
    print("测试插件系统")
    print("=" * 60)
    
    # 创建日志记录器
    logger = LogManager.get_logger('test_plugins', console_output=True)
    
    # 创建插件注册表
    print("\n1. 创建 PluginRegistry...")
    registry = PluginRegistry(logger=logger)
    print("   [OK] PluginRegistry 创建成功")
    
    # 发现插件
    print("\n2. 发现插件...")
    try:
        count = registry.discover(['plugins/'])
        print(f"   [OK] 发现了 {count} 个插件")
    except Exception as e:
        print(f"   [FAIL] 插件发现失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 列出所有插件
    print("\n3. 已注册的插件列表:")
    plugins = registry.get_plugin_list()
    if not plugins:
        print("   (无插件)")
    else:
        for plugin_info in plugins:
            print(f"   - {plugin_info['name']} v{plugin_info['version']}")
            print(f"     描述: {plugin_info['description']}")
            print(f"     来源: {plugin_info['source']}")
            print(f"     已加载: {plugin_info['loaded']}")
            print()
    
    # 测试按接口查询
    print("\n4. 按接口查询插件:")
    interfaces = ['IMapPlugin', 'ITimePlugin', 'ITownsPlugin', 'IPopulationPlugin']
    for interface_name in interfaces:
        matched = registry.get_plugins_by_interface(interface_name)
        if matched:
            print(f"   {interface_name}: {matched}")
    
    # 测试加载插件
    print("\n5. 测试加载插件:")
    if 'map' in registry._plugins:
        try:
            # 创建 EventBus
            event_bus = EventBus()
            
            context = PluginContext(
                config={'debug': True},
                logger=logger,
                event_bus=event_bus,
                registry=registry
            )
            plugin = registry.load_plugin('map', context, width=100, height=100)
            print(f"   [OK] 成功加载插件: {plugin.__class__.__name__}")
            print(f"   [OK] 插件已初始化: width={plugin.width}, height={plugin.height}")
            
            # 卸载插件
            registry.unload_plugin('map')
            print(f"   [OK] 插件已卸载")
        except Exception as e:
            print(f"   [FAIL] 加载插件失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   [WARN] map 插件未注册，跳过加载测试")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == '__main__':
    test_plugin_discovery()
