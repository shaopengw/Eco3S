"""
测试插件系统集成到main文件
"""
import sys
import os
import yaml
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins import PluginRegistry, PluginContext
from src.plugins.plugin_context import EventBus
from src.utils.logger import LogManager

def initialize_plugin_system(
    config: dict, 
    modules_config_path: str = None,
    logger: logging.Logger = None
):
    """简化版插件系统初始化（用于测试）"""
    if logger is None:
        logger = LogManager.get_logger('plugin_system', console_output=True)
    
    # 创建插件注册表
    registry = PluginRegistry(logger=logger)
    
    # 发现插件
    count = registry.discover(['plugins/'])
    logger.info(f"发现了 {count} 个插件")
    
    # 加载的插件实例字典
    loaded_plugins = {}
    
    # 如果提供了 modules_config_path，读取并加载 active_plugins
    if modules_config_path and os.path.exists(modules_config_path):
        try:
            with open(modules_config_path, 'r', encoding='utf-8') as f:
                modules_config = yaml.safe_load(f)
            
            active_plugins = modules_config.get('active_plugins', [])
            
            if active_plugins:
                logger.info(f"开始加载 {len(active_plugins)} 个激活插件...")
                
                # 创建事件总线（所有插件共享）
                event_bus = EventBus()
                
                # 加载每个激活的插件
                for plugin_config in active_plugins:
                    plugin_name = plugin_config.get('plugin_name')
                    plugin_specific_config = plugin_config.get('config', {})
                    
                    if not plugin_name:
                        logger.warning(f"跳过无效的插件配置: {plugin_config}")
                        continue
                    
                    try:
                        # 创建 PluginContext
                        context = PluginContext(
                            config={**config, **plugin_specific_config},
                            logger=logger,
                            event_bus=event_bus,
                            registry=registry
                        )
                        
                        # 加载插件
                        plugin_instance = registry.load_plugin(plugin_name, context)
                        loaded_plugins[plugin_name] = plugin_instance
                        
                        logger.info(f"✓ 已加载插件: {plugin_name}")
                        
                    except Exception as e:
                        logger.error(f"✗ 加载插件 {plugin_name} 失败: {e}")
                        import traceback
                        traceback.print_exc()
                
                logger.info(f"插件加载完成: {len(loaded_plugins)}/{len(active_plugins)} 成功")
            else:
                logger.info("未配置 active_plugins，跳过插件加载")
                
        except Exception as e:
            logger.error(f"读取 modules_config.yaml 失败: {e}")
            import traceback
            traceback.print_exc()
    
    return registry, loaded_plugins

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
        registry, loaded_plugins = initialize_plugin_system(
            config=test_config,
            modules_config_path=modules_config_path,
            logger=logger
        )
        
        print(f"\n   [OK] 插件加载完成")
        print(f"   已加载插件数量: {len(loaded_plugins)}")
        print(f"   插件列表:")
        for name, plugin in loaded_plugins.items():
            print(f"     - {name}: {plugin.__class__.__name__}")
        
        # 测试插件功能
        if 'default_map' in loaded_plugins:
            map_plugin = loaded_plugins['default_map']
            print(f"\n   测试 Map 插件:")
            print(f"     - width: {map_plugin.width}")
            print(f"     - height: {map_plugin.height}")
        
        if 'default_time' in loaded_plugins:
            time_plugin = loaded_plugins['default_time']
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
