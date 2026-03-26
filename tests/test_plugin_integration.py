"""
测试插件系统集成到main文件
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins.bootstrap import initialize_plugin_system
from src.utils.logger import LogManager

def test_plugin_loading_with_config():
    """测试从配置文件加载插件"""
    print("=" * 60)
    print("测试插件系统集成")
    print("=" * 60)
    
    # 创建日志记录器
    logger = LogManager.get_logger('test_integration', console_output=True)
    
    # 测试配置
    test_config = {
        'simulation': {
            'map_width': 100,
            'map_height': 100,
            'start_year': '1400-01-01',
            'total_years': 10,
            'initial_population': 1000
        },
        'data': {
            'towns_data_path': 'config/default/towns_data.json'
        }
    }
    
    # 测试从 default 配置加载
    print("\n1. 测试加载 default 配置的插件...")
    modules_config_path = "config/default/modules_config.yaml"
    
    try:
        registry = initialize_plugin_system(
            config=test_config,
            modules_config_path=modules_config_path,
            logger=logger
        )

        loaded_plugins = registry.get_all_loaded()
        
        print(f"\n   [OK] 插件加载完成")
        print(f"   已加载插件数量: {len(loaded_plugins)}")
        print(f"   插件列表:")
        for name, plugin in loaded_plugins.items():
            print(f"     - {name}: {plugin.__class__.__name__}")
        
        # 测试插件功能
        if 'map' in loaded_plugins:
            map_plugin = loaded_plugins['map']
            print(f"\n   测试 Map 插件:")
            print(f"     - width: {map_plugin.width}")
            print(f"     - height: {map_plugin.height}")
        
        if 'time' in loaded_plugins:
            time_plugin = loaded_plugins['time']
            print(f"\n   测试 Time 插件:")
            print(f"     - start_time: {time_plugin.start_time}")
            print(f"     - total_steps: {time_plugin.total_steps}")
        
        print("\n   [OK] 插件功能正常")
        
    except Exception as e:
        print(f"\n   [FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_plugin_loading_with_config()
    sys.exit(0 if success else 1)
