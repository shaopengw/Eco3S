from camel.configs import ChatGPTConfig
from camel.memories import ChatHistoryMemory, MemoryRecord, ScoreBasedContextCreator
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter
from datetime import datetime
from typing import List
from .model_manager import ModelManager
from .memory_manager import MemoryManager 
import sys
import logging
import os
from dotenv import load_dotenv
import json
import asyncio
import random