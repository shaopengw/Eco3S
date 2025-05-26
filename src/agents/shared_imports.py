from camel.configs import ChatGPTConfig
from camel.memories import ChatHistoryMemory, MemoryRecord, ScoreBasedContextCreator
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter
from datetime import datetime
from typing import List
import sys
import logging
import os
from dotenv import load_dotenv
import json
import asyncio
import random

from .model_manager import ModelManager
from .memory_manager import MemoryManager
from .base_agent import BaseAgent

import yaml
import os

# 全局配置对象
global_config = {}

def load_global_config(config_path="config/simulation_config.yaml"):
    """加载全局配置"""
    global global_config
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            global_config = yaml.safe_load(f)
    else:
        raise FileNotFoundError(f"Config file not found: {config_path}")

# 初始化时加载配置
try:
    load_global_config()
except Exception as e:
    print(f"Warning: Failed to load global config: {e}")
    global_config = {"simulation": {"speech_probability": 0.2}}  # 默认配置