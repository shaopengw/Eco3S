"""
测试修改后的Simulator插件集成
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.simulator import Simulator
from src.utils.di_container import DIContainer
from src.utils.logger import LogManager
from src.plugins import PluginRegistry, PluginContext
from src.plugins.plugin_context import EventBus
import yaml

def test_simulator_plugin_integration():
    """测试Simulator使用插件系统"""
    print("=" * 60)
    print("测试Simulator插件集成")
    print("=" * 60)
    
    logger = LogManager.get_logger('test_simulator', console_output=True)
    
    # 创建插件系统
    registry = PluginRegistry(logger=logger)
    count = registry.discover(['plugins/'])
    print(f"\n1. 发现了 {count} 个插件")
    
    # 读取配置
    modules_config_path = "config/default/modules_config.yaml"
    with open(modules_config_path, 'r', encoding='utf-8') as f:
        modules_config = yaml.safe_load(f)
    
    active_plugins = modules_config.get('active_plugins', [])
    print(f"\n2. 配置了 {len(active_plugins)} 个激活插件")
    
    # 加载插件
    event_bus = EventBus()
    loaded_plugins = {}
    
    test_config = {
        'simulation': {
            'map_width': 100,
            'map_height': 100,
            'start_year': '1400-01-01',
            'total_years': 10
        },
        'data': {
            'towns_data_path': 'config/default/towns_data.json'
        }
    }
    
    for plugin_config in active_plugins:
        plugin_name = plugin_config.get('plugin_name')
        if plugin_name == 'default_map':  # 只测试map插件
            context = PluginContext(
                config=test_config,
                logger=logger,
                event_bus=event_bus,
                registry=registry
            )
            plugin = registry.load_plugin(plugin_name, context)
            loaded_plugins[plugin_name] = plugin
            print(f"   - 已加载插件: {plugin_name}")
    
    print(f"\n3. 测试Simulator._resolve_instance方法:")
    
    # 创建一个模拟的DIContainer
    container = DIContainer()
    
    # 测试从loaded_plugins获取
    from src.interfaces import IMap
    map_instance = Simulator._resolve_instance('default_map', IMap, container, loaded_plugins)
    
    if map_instance:
        print(f"   ✓ 成功从loaded_plugins获取map实例")
        print(f"   - 类型: {type(map_instance).__name__}")
        print(f"   - width: {map_instance.width if hasattr(map_instance, 'width') else 'N/A'}")
        print(f"   - height: {map_instance.height if hasattr(map_instance, 'height') else 'N/A'}")
    else:
        print(f"   ✗ 获取map实例失败")
        return False
    
    # 测试从容器获取（应该回退到容器，但container为空会失败）
    try:
        time_instance = Simulator._resolve_instance('default_time', None, container, loaded_plugins)
        print(f"   ⚠ 从空容器获取了time实例（不应该发生）")
    except Exception as e:
        print(f"   ✓ 正确处理了容器中不存在的实例")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_simulator_plugin_integration()
    sys.exit(0 if success else 1)
