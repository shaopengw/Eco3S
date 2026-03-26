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
from typing import Any, Dict, List, Optional, Set

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
from src.agents.resident import ResidentGroup

# 群体通用能力/生成器（入口共用）
from src.agents.agent_group import AgentGroup
import src.agents.government as government_agents
import src.agents.rebels as rebels_agents_module

# 可视化模块
from src.visualization.plot_results import plot_all_results, plot_rebellions_over_time, plot_unemployment_rate_over_time, plot_population_over_time, plot_government_budget_over_time, plot_rebellion_strength_over_time, plot_satisfaction_over_time, plot_tax_rate_over_time, plot_river_navigability_over_time, plot_gdp_over_time, plot_urban_scale_over_time
# 生成器模块
from src.generator.resident_generate import generate_resident_data, save_resident_data

# 工具模块
from src.utils.simulation_context import SimulationContext
from src.utils.simulation_cache import SimulationCache
from src.utils.di_container import DIContainer
from src.utils.di_helpers import setup_container_for_simulation, register_loaded_plugins
from src.utils.logger import LogManager
from src.utils.entrypoint_runner import (
    load_influence_registry_from_dir,
    run_with_cache,
    orchestrate_basic_runtime_init,
    build_default_simulator_via_di,
    build_teog_simulator_via_di,
    build_info_propagation_simulator_via_di,
)

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

# 固定运行：插件系统启动逻辑（统一实现）
from src.plugins.bootstrap import initialize_plugin_system

