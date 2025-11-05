from .shared_imports import *
import random
import os
from dotenv import load_dotenv

load_dotenv()

class ModelManager:
    """统一的模型管理器，用于管理不同的模型 API"""
    def __init__(self):
        """初始化模型管理器"""
        # 可用模型配置
        self.available_models = {
            # "OPENAI": {
            #     "model_types": ["gpt-3.5-turbo"],
            #     "model_platform": ModelPlatformType.OPENAI,
            #     "url":os.getenv('OPENAI_API_BASE_URL'),
            #     "api_key":os.getenv('OPENAI_API_KEY')
            # },
            "CLAUDE": {
                "model_types": ["claude-sonnet-4-5-20250929"],
                "model_platform": ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
                "url":os.getenv('ANTHROPIC_API_BASE_URL'),
                "api_key":os.getenv('ANTHROPIC_API_KEY')
            },
            # "OPENAI": {
            #     "model_types": ["gpt-4o"],
            #     "model_platform": ModelPlatformType.OPENAI,
            #     "url":os.getenv('OPENAI_API_BASE_URL'),
            #     "api_key":os.getenv('OPENAI_API_KEY')
            # },
            # "deepseek": {
            #     "model_types": ["deepseek-chat"],
            #     "model_platform": ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
            #     "url":os.getenv('DEEPSEEK_API_BASE_URL'),
            #     "api_key":os.getenv('DEEPSEEK_API_KEY')
            # },
            
        }
        # 统一模型配置
        self.model_config = {
            "temperature": 1,
            "max_tokens": 2048,
            "top_p": 0.9,
        }

    def get_random_model_config(self):
        """随机获取一个模型配置"""
        api_name = random.choice(list(self.available_models.keys()))
        api_info = self.available_models[api_name]
        model_type = random.choice(api_info["model_types"])
        
        # 基础配置
        config = {
            "model_platform": api_info["model_platform"],
            "model_type": model_type,
            "model_config": self.model_config.copy()
        }
        
        # 如果是 OPENAI_COMPATIBLE_MODEL，需要单独保存 url 和 api_key
        if api_info["model_platform"] == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
            config["url"] = api_info["url"]
            config["api_key"] = api_info["api_key"]
        
        return config
