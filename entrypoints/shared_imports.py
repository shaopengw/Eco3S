"""
entrypoints 共享导入模块
统一管理所有入口文件的依赖
"""

# 标准库
import argparse
import asyncio
import logging
import os
import sys
import yaml
from datetime import datetime
from typing import Any

# 第三方库
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入接口（用于类型注解）
from src.interfaces import (
    IMap, ITime, IPopulation, ISocialNetwork, IClimateSystem,
    ITowns, ITransportEconomy, IJobMarket,
    IGovernment, IRebellion, IResident, IResidentGroup
)

# 环境模块（具体实现）
from src.environment.map import Map
from src.environment.time import Time
from src.environment.population import Population
from src.environment.social_network import SocialNetwork
from src.environment.climate import ClimateSystem
from src.environment.towns import Towns
from src.environment.transport_economy import TransportEconomy
from src.environment.job_market import JobMarket

# Agent模块（具体实现）
from src.agents.government import Government
from src.agents.rebels import Rebellion
from src.agents.resident_agent_generator import generate_canal_agents
from src.agents.government_agent_generator import generate_government_agents
from src.agents.rebels_agent_generator import generate_rebels_agents
from src.agents.resident import ResidentGroup

# 可视化模块
from src.visualization.plot_results import plot_all_results, plot_rebellions_over_time, plot_unemployment_rate_over_time, plot_population_over_time, plot_government_budget_over_time, plot_rebellion_strength_over_time, plot_satisfaction_over_time, plot_tax_rate_over_time, plot_river_navigability_over_time, plot_gdp_over_time, plot_urban_scale_over_time
# 生成器模块
from src.generator.resident_generate import generate_resident_data, save_resident_data

# 工具模块
from src.utils.simulation_context import SimulationContext
from src.utils.simulation_cache import SimulationCache
from src.utils.di_container import DIContainer
from src.utils.di_helpers import setup_container_for_simulation
from src.utils.logger import LogManager

# 影响函数系统
from src.influences import InfluenceRegistry, InfluenceManager

# 插件系统
from src.plugins import (
    PluginRegistry, 
    PluginManager, 
    PluginContext,
    BasePlugin
)
from src.plugins.plugin_context import EventBus


def initialize_plugin_system(
    config: dict, 
    modules_config_path: str = None,
    logger: logging.Logger = None
) -> tuple:
    """
    初始化插件系统并加载配置的插件
    
    Args:
        config: 主配置字典
        modules_config_path: modules_config.yaml 文件路径（可选）
        logger: 日志记录器（可选）
    
    Returns:
        tuple: (registry, loaded_plugins) 插件注册表和已加载的插件字典
        
    Example:
        registry, plugins = initialize_plugin_system(
            config=config,
            modules_config_path="config/default/modules_config.yaml",
            logger=logger
        )
        # 使用插件
        map_plugin = plugins.get('default_map')
        if map_plugin:
            map_plugin.initialize_map()
    """
    if logger is None:
        logger = LogManager.get_logger('plugin_system', console_output=True)
    
    # 创建插件注册表
    registry = PluginRegistry(logger=logger)
    
    # 发现插件（从配置和目录）
    plugin_paths = config.get('plugin_paths', ['plugins/'])
    count = registry.discover(plugin_paths)
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
