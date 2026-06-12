from __future__ import annotations

import json
import asyncio
import random
from typing import Dict, Optional, Any, TYPE_CHECKING
import yaml
from src.agents.resident import Resident, ResidentSharedInformationPool
from src.environment.map import Map
from src.generator.resident_generate import generate_resident_data, save_resident_data

if TYPE_CHECKING:
    from src.influences import InfluenceRegistry

# 实体类型到类/模板的映射表
AGENT_CLASS_MAP = {
    "resident": {
        "class": Resident,
        # 新版模板目录结构：config/template/entities/resident/
        "default_prompts_dir": "config/template/entities/resident",
        "prompts_file": "prompts.yaml",
        "actions_file": "actions.yaml",
    },
    # 未来可在此扩展 enterprise、consumer 等实体类型
    # "enterprise": {
    #     "class": EnterpriseAgent,
    #     "default_prompts_dir": "config/template/entities/enterprise",
    #     "prompts_file": "prompts.yaml",
    #     "actions_file": "actions.yaml",
    # },
}

def _resolve_entity_type(profile_config: Optional[Dict]) -> str:
    """从 profile 配置中解析实体类型，默认返回 'resident'。"""
    if not isinstance(profile_config, dict):
        return "resident"
    return profile_config.get("entity_type", "resident")

def assign_resident_location(resident_data, map):
    """
    分配居民的位置和所属城镇。
    兼容配置驱动生成：若 resident_data 中不存在 "residence" 字段，
    则直接从所有城镇中随机分配，不强制要求该属性。
    :param resident_data: 居民数据字典，可选包含"residence"字段
    :param map: Map类实例
    :return: ((x, y), town_name) 坐标元组和城市名称
    """
    canal_towns = [name for name, info in map.town_dict.items() if info['type'] == 'canal']
    non_canal_towns = [name for name, info in map.town_dict.items() if info['type'] == 'non_canal']

    town_name = None
    location = None

    # 若存在 residence 字段，按旧逻辑分配；否则视为缺失，直接随机选城镇
    residence = resident_data.get("residence")
    if residence is not None:
        if residence == "沿河":
            if canal_towns:
                town_name = random.choice(canal_towns)
        else:
            if non_canal_towns:
                town_name = random.choice(non_canal_towns)

    if town_name is None:
        all_towns = list(map.town_dict.keys())
        if all_towns:
            town_name = random.choice(all_towns)

    if town_name:
        location = map.generate_random_location(town_name)
    else:
        return (0, 0), "UnknownTown"

    return location, town_name
