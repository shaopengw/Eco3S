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
            "OPENAI": {
                "model_types": ["gpt-3.5-turbo"],
                "model_platform": ModelPlatformType.OPENAI,
                "url":os.getenv('OPENAI_API_BASE_URL'),
                "api_key":os.getenv('OPENAI_API_KEY'),
                "allow_random": True  # 允许随机选择
            },
            "CLAUDE": {
                "model_types": ["claude-sonnet-4-5-20250929"],
                "model_platform": ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
                "url":os.getenv('ANTHROPIC_API_BASE_URL'),
                "api_key":os.getenv('ANTHROPIC_API_KEY'),
                "allow_random": False  # 仅供指定使用，不参与随机选择
            },
            # "OPENAI": {
            #     "model_types": ["gpt-4o"],
            #     "model_platform": ModelPlatformType.OPENAI,
            #     "url":os.getenv('OPENAI_API_BASE_URL'),
            #     "api_key":os.getenv('OPENAI_API_KEY'),
            #     "allow_random": True
            # },
            # "deepseek": {
            #     "model_types": ["deepseek-v3.2"],
            #     "model_platform": ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
            #     "url":os.getenv('DEEPSEEK_API_BASE_URL'),
            #     "api_key":os.getenv('DEEPSEEK_API_KEY'),
            #     "allow_random": True
            # },
            # "qwen": {
            #     "model_types": ["qwen3-235b-a22b"],
            #     "model_platform": ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
            #     "url":os.getenv('DEEPSEEK_API_BASE_URL'),
            #     "api_key":os.getenv('DEEPSEEK_API_KEY'),
            #     "allow_random": True
            # },
        }
        # 统一模型配置
        self.model_config = {
            "temperature": 1,
            # "top_p": 0.9,
        }

    def get_random_model_config(self):
        """随机获取一个模型配置（仅从允许随机选择的模型中选择）"""
        # 过滤出允许随机选择的模型
        random_allowed_models = {
            name: info for name, info in self.available_models.items() 
            if info.get("allow_random", True)  # 默认允许随机选择
        }
        
        if not random_allowed_models:
            raise ValueError("没有可供随机选择的模型")
        
        api_name = random.choice(list(random_allowed_models.keys()))
        api_info = random_allowed_models[api_name]
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
    
    def get_specific_model_config(self, api_name, model_type=None):
        """获取指定的模型配置
        
        Args:
            api_name: API名称（如 "CLAUDE", "OPENAI"）
            model_type: 模型类型（可选，如果不指定则使用该API的第一个模型）
        """
        if api_name not in self.available_models:
            raise ValueError(f"未找到API: {api_name}，可用的API: {list(self.available_models.keys())}")
        
        api_info = self.available_models[api_name]
        
        # 如果没有指定model_type，使用第一个可用的
        if model_type is None:
            model_type = api_info["model_types"][0]
        elif model_type not in api_info["model_types"]:
            raise ValueError(f"模型 {model_type} 不在 {api_name} 的可用模型列表中: {api_info['model_types']}")
        
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
