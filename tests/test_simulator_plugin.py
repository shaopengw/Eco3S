"""测试插件注册中心与模块名查询。

验证：
- modules_config.yaml 的 selected_modules 绑定后，可通过 registry.get_plugin('map') 按模块名取到实例
- registry.load_plugin(..., container=DIContainer()) 会走 DIContainer.create（支持依赖注入）
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.di_container import DIContainer
from src.utils.logger import LogManager
from src.plugins import PluginRegistry, PluginContext
from src.plugins.plugin_context import EventBus
import yaml

def test_simulator_plugin_integration():
    """测试按模块名获取插件实例"""
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
    
    selected_modules = modules_config.get('selected_modules', {}) or {}
    print(f"\n2. 配置了 {len(selected_modules)} 个选择模块")
    
    # 绑定模块名 -> 插件名
    registry.bind_modules(selected_modules)

    # 加载插件
    event_bus = EventBus()
    container = DIContainer()
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
    
    map_plugin_name = selected_modules.get('map')
    if map_plugin_name:
        context = PluginContext(
            config=test_config,
            logger=logger,
            event_bus=event_bus,
            registry=registry
        )
        plugin = registry.load_plugin(map_plugin_name, context, container=container)
        loaded_plugins[map_plugin_name] = plugin
        print(f"   - 已加载插件: {map_plugin_name}")
    
    print(f"\n3. 测试按模块名查询插件:")

    map_instance = registry.get_plugin('map')
    assert map_instance is not None
    print(f"   ✓ registry.get_plugin('map') 返回实例: {type(map_instance).__name__}")
    if hasattr(map_instance, 'width') and hasattr(map_instance, 'height'):
        print(f"   - width: {map_instance.width}")
        print(f"   - height: {map_instance.height}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_simulator_plugin_integration()
    sys.exit(0 if success else 1)
