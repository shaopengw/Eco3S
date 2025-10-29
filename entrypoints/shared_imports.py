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

# 环境模块
from src.environment.map import Map
from src.environment.time import Time
from src.environment.population import Population
from src.environment.social_network import SocialNetwork
from src.environment.climate import ClimateSystem
from src.environment.towns import Towns
from src.environment.transport_economy import TransportEconomy
from src.environment.job_market import JobMarket

# Agent模块
from src.agents.government import Government
from src.agents.rebels import Rebellion
from src.agents.resident_agent_generator import generate_canal_agents
from src.agents.government_agent_generator import generate_government_agents
from src.agents.rebels_agent_generator import generate_rebels_agents
from src.agents.resident import ResidentGroup

# 可视化模块
from src.visualization.plot_results import plot_all_results

# 生成器模块
from src.generator.resident_generate import generate_resident_data, save_resident_data

# 工具模块
from src.utils.simulation_context import SimulationContext
from src.utils.simulation_cache import SimulationCache
