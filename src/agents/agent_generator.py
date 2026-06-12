from __future__ import annotations

import json
import asyncio
import random
import os
from typing import Dict, Optional, Any, List, TYPE_CHECKING
import yaml

from src.environment.map import Map
from src.generator.resident_generate import generate_resident_profile, save_resident_data
from src.agents.shared_imports import BaseAgent

if TYPE_CHECKING:
    from src.agents.resident import ResidentSharedInformationPool
    from src.influences import InfluenceRegistry

# =============================================================================
# 实体类型到类/模板的映射表
# =============================================================================

AGENT_CLASS_MAP = {
    "resident": {
        "class_path": "src.agents.resident.Resident",
        "default_prompts_dir": "config/template/entities/resident",
        "prompts_file": "prompts.yaml",
        "actions_file": "actions.yaml",
    },
    "government": {
        "class_path": "src.plugins.government.government_plugin.DefaultGovernmentPlugin",
        "default_prompts_dir": "config/template/entities/government",
        "prompts_file": "prompts.yaml",
        "actions_file": "actions.yaml",
    },
    "rebels": {
        "class_path": "src.plugins.rebellion.rebellion_plugin.DefaultRebellionPlugin",
        "default_prompts_dir": "config/template/entities/rebels",
        "prompts_file": "prompts.yaml",
        "actions_file": "actions.yaml",
    },
}


# 由插件系统管理的实体类型（不走 agent_generator 实例化 Agent）
PLUGIN_MANAGED_TYPES = {"government", "rebels"}

# 用于存储 generate_agents() 中为插件管理的实体类型生成的画像数据
_plugin_profiles: Dict[str, Dict[str, Any]] = {}

def _store_plugin_profile(entity_type: str, name: str, profile: dict) -> None:
	"""存储插件管理实体类型的画像数据，供插件初始化时读取。"""
	_plugin_profiles[entity_type] = {"name": name, "profile": profile}

def get_plugin_profile(entity_type: str) -> Optional[Dict[str, Any]]:
	"""获取插件管理实体类型的画像数据。"""
	return _plugin_profiles.get(entity_type)

def clear_plugin_profiles() -> None:
	"""清理缓存，用于测试/重置。"""
	_plugin_profiles.clear()

# =============================================================================
# 动态注册工具
# =============================================================================

def register_agent_class(
    entity_type: str,
    cls=None,
    class_path: Optional[str] = None,
    prompts_dir: str = "config/template/entities/{entity_type}",
    prompts_file: str = "prompts.yaml",
    actions_file: str = "actions.yaml",
):
    """注册新的实体类型到 AGENT_CLASS_MAP。

    Args:
        entity_type: 实体类型标识字符串
        cls: 实体类对象（直接传入）
        class_path: 实体类导入路径（如 "src.agents.enterprise.EnterpriseAgent"）
        prompts_dir: 提示词模板目录
        prompts_file: 提示词文件名
        actions_file: 行动配置文件名
    """
    cfg = {
        "prompts_file": prompts_file,
        "actions_file": actions_file,
    }
    if cls is not None:
        cfg["class"] = cls
    if class_path is not None:
        cfg["class_path"] = class_path
    cfg["default_prompts_dir"] = prompts_dir.format(entity_type=entity_type)
    AGENT_CLASS_MAP[entity_type] = cfg


def _resolve_agent_class(entity_type: str):
    """根据 entity_type 解析对应的 Agent 类。

    优先返回已缓存的 class 对象；若不存在，尝试通过 class_path 动态导入。
    若均失败，返回 BaseAgent 作为 fallback。
    """
    import importlib

    cfg = AGENT_CLASS_MAP.get(entity_type)
    if cfg is None:
        return BaseAgent

    if "class" in cfg:
        return cfg["class"]

    if "class_path" in cfg:
        try:
            module_path, class_name = cfg["class_path"].rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            cfg["class"] = cls  # 缓存
            return cls
        except Exception as e:
            print(f"[agent_generator] 无法导入类 {cfg['class_path']}: {e}， fallback 到 BaseAgent")
            return BaseAgent

    return BaseAgent


# =============================================================================
# 数量计算
# =============================================================================

def _compute_agent_counts(agents_def: List[dict], total_population: int) -> Dict[str, int]:
    """根据 agent_profile 中各 agent 的定义和总人数，计算每种 agent 的生成数量。

    策略：
    1. 若 agent 定义中有 'count'（绝对数量），优先采用
    2. 若有 'population_ratio'（0-1 之间），采用 ratio * total
    3. 剩余未分配的数量平均分给无显式数量定义的 agent
    """
    counts = {}
    assigned = 0
    unspecified_indices = []

    for i, agent_def in enumerate(agents_def):
        name = agent_def.get("name", f"agent_{i}")
        explicit_count = agent_def.get("count")
        ratio = agent_def.get("population_ratio")

        if isinstance(explicit_count, int):
            counts[name] = explicit_count
            assigned += explicit_count
        elif isinstance(ratio, (int, float)) and ratio > 0:
            cnt = max(1, int(round(total_population * ratio)))
            counts[name] = cnt
            assigned += cnt
        else:
            unspecified_indices.append(i)
            counts[name] = 0

    remaining = max(0, total_population - assigned)
    if unspecified_indices and remaining > 0:
        per_agent = max(1, remaining // len(unspecified_indices))
        for idx in unspecified_indices:
            name = agents_def[idx].get("name", f"agent_{idx}")
            counts[name] = per_agent
            remaining -= per_agent
        # 将余数分配给第一个未指定的 agent
        if remaining > 0 and unspecified_indices:
            first_name = agents_def[unspecified_indices[0]].get("name", f"agent_{unspecified_indices[0]}")
            counts[first_name] += remaining

    # 如果所有都指定了且总数不足 total，补齐到第一个
    if sum(counts.values()) < total_population and counts:
        first_name = next(iter(counts))
        counts[first_name] += total_population - sum(counts.values())

    return counts


# =============================================================================
# 位置分配（完全通用）
# =============================================================================

def assign_agent_location(agent_data: dict, map: Map) -> tuple:
    """分配 Agent 的位置和所属城镇。

    分配策略（按优先级）：
    1. 若 agent_data 中有 'town' 字段，直接使用该城镇
    2. 若 agent_data 中有 'residence' 字段，按旧逻辑解析（沿河/非沿河）
    3. 否则从所有城镇中随机分配

    Returns:
        ((x, y), town_name)
    """
    canal_towns = [name for name, info in map.town_dict.items() if info.get('type') == 'canal']
    non_canal_towns = [name for name, info in map.town_dict.items() if info.get('type') == 'non_canal']
    all_towns = list(map.town_dict.keys())

    town_name = None

    # 优先级1：直接指定 town
    town = agent_data.get("town")
    if town and town in all_towns:
        town_name = town

    # 优先级2：residence 字段
    if town_name is None:
        residence = agent_data.get("residence")
        if residence is not None:
            if residence == "沿河":
                if canal_towns:
                    town_name = random.choice(canal_towns)
            else:
                if non_canal_towns:
                    town_name = random.choice(non_canal_towns)

    # 优先级3：随机分配
    if town_name is None:
        if all_towns:
            town_name = random.choice(all_towns)

    if town_name:
        location = map.generate_random_location(town_name)
    else:
        location = (0, 0)
        town_name = "UnknownTown"

    return location, town_name


# =============================================================================
# 通用 Agent 生成主入口
# =============================================================================

async def generate_agents(
    map: Map,
    initial_population: int = 10,
    agent_profile: Optional[Dict] = None,
    agent_graph: Optional[Dict[int, Any]] = None,
    shared_pool: Optional[Any] = None,
    prompts_path: Optional[str] = None,
    actions_path: Optional[str] = None,
    window_size: int = 3,
    influence_registry: Optional['InfluenceRegistry'] = None,
    config_dir: Optional[str] = None,
    **kwargs
) -> Dict[int, Any]:
    """根据 agent_profile.yaml 动态生成任意类型的 Agent。

    Args:
        map: 地图对象
        initial_population: 总初始人口/实体数量
        agent_profile: 解析后的 agent_profile.yaml 字典（含 agents 列表）
        agent_graph: 已有的 Agent 图（用于增量生成）
        shared_pool: 共享资源池
        prompts_path: 默认提示词文件路径（若 agent_profile 中未指定）
        actions_path: 默认行动配置文件路径（若 agent_profile 中未指定）
        window_size: 记忆窗口大小
        influence_registry: 影响函数注册表
        config_dir: 配置目录，用于自动查找 prompts/actions 文件
        **kwargs: 额外参数，透传给 Agent 构造函数

    Returns:
        Dict[int, Any]: Agent ID 到 Agent 实例的映射
    """
    import time as time_module
    start_time = time_module.time()

    if agent_graph is None:
        agent_graph = {}

    if initial_population <= 0:
        return agent_graph

    # 兼容旧版：若 agent_profile 为 None，降级到单一 resident 生成
    if agent_profile is None:
        print("[agent_generator] agent_profile 为空，降级到单一 resident 生成")
        from src.agents.resident import Resident, ResidentSharedInformationPool
        if shared_pool is None:
            shared_pool = ResidentSharedInformationPool()
        return await _legacy_generate_residents(
            map=map,
            initial_population=initial_population,
            agent_graph=agent_graph,
            shared_pool=shared_pool,
            prompts_path=prompts_path,
            actions_path=actions_path,
            window_size=window_size,
            influence_registry=influence_registry,
            **kwargs
        )

    # 支持两种格式：
    #   - 标准格式：agent_profile['agents'] 为列表
    #   - 简写格式：agent_profile 直接包含 entity_type + attributes（单实体类型）
    agents_def = agent_profile.get("agents", [])
    if not agents_def and "entity_type" in agent_profile and "attributes" in agent_profile:
        agents_def = [dict(agent_profile)]
    if not agents_def:
        print("[agent_generator] agent_profile['agents'] 为空，无法生成 Agent")
        return agent_graph

    # 提取全局 computed_descriptions（如 health_conditions、satisfaction_levels 等）
    computed_descriptions = agent_profile.get("computed_descriptions", {})

    counts = _compute_agent_counts(agents_def, initial_population)
    print(f"[agent_generator] 生成计划: {counts}")

    # 预加载共享 pool（若未提供）
    if shared_pool is None:
        try:
            from src.agents.resident import ResidentSharedInformationPool
            shared_pool = ResidentSharedInformationPool()
        except Exception:
            shared_pool = None

    # 遍历每种 agent 定义，批量生成
    next_id = max(agent_graph.keys()) + 1 if agent_graph else 1
    for i, agent_def in enumerate(agents_def):
        name = agent_def.get("name", f"agent_{i}")
        entity_type = agent_def.get("entity_type", "resident")
        population = counts.get(name, 0)
        if population <= 0:
            continue

        # ---- 插件管理的实体类型（government / rebels）：生成画像，不实例化 Agent ----
        if entity_type in PLUGIN_MANAGED_TYPES:
            profile_cfg = {
                "attributes": agent_def.get("attributes", {}),
                "constraints": agent_def.get("constraints", []),
                "extra": agent_def.get("extra", {}),
            }
            if entity_type == "government":
                from src.generator.government_generate import generate_official_data
                profiles = generate_official_data(population, profile_config=profile_cfg)
            else:  # rebels
                from src.generator.rebels_generate import generate_rebel_data
                profiles = generate_rebel_data(population, profile_config=profile_cfg)
            _store_plugin_profile(entity_type, name, {"profiles": profiles, "population": population})
            print(f"[agent_generator] ✓ {entity_type}「{name}」{len(profiles)} 个画像已生成（由插件系统管理）")
            continue

        agent_class = _resolve_agent_class(entity_type)

        # 确定 prompts/actions 路径
        entity_prompts_path, entity_actions_path = _resolve_prompts_actions_paths(
            agent_def, entity_type, config_dir, prompts_path, actions_path
        )

        # 加载 prompts/actions
        prompts_data = {}
        actions_data = {}
        if entity_prompts_path and os.path.exists(entity_prompts_path):
            with open(entity_prompts_path, 'r', encoding='utf-8') as f:
                prompts_data = yaml.safe_load(f) or {}
        if entity_actions_path and os.path.exists(entity_actions_path):
            with open(entity_actions_path, 'r', encoding='utf-8') as f:
                actions_data = yaml.safe_load(f) or {}

        # 将 agent_profile 中的 computed_descriptions 合并进 prompts
        # 使 Resident 在渲染系统消息时能读取 health_conditions / satisfaction_levels / economic_status_rules
        if computed_descriptions:
            prompts_data = {**computed_descriptions, **prompts_data}

        # 生成画像数据
        profile_cfg = {
            "attributes": agent_def.get("attributes", {}),
            "constraints": agent_def.get("constraints", []),
            "extra": agent_def.get("extra", {}),
        }
        agent_data_list = []
        for _ in range(population):
            profile = generate_resident_profile(profile_cfg)
            agent_data_list.append(profile)

        # 批量创建 Agent
        for agent_data in agent_data_list:
            location, town_name = assign_agent_location(agent_data, map)

            # 统一构造：BaseAgent 子类通过 **kwargs 自行取用所需参数
            agent = agent_class(
                agent_id=next_id,
                group_type=entity_type,
                profile_config=agent_data,
                prompts=prompts_data,
                actions_config=actions_data,
                window_size=window_size,
                job_market=None,
                shared_pool=shared_pool,
                map=map,
                lightweight=True,
                influence_registry=influence_registry,
            )

            # 通用位置和城镇属性（如果类支持）
            if hasattr(agent, 'town'):
                agent.town = town_name
            if hasattr(agent, 'location'):
                agent.location = location

            agent_graph[next_id] = agent
            next_id += 1

    total_time = time_module.time() - start_time
    print(f"[agent_generator] 全部 Agent 创建完成，总耗时: {total_time:.2f}秒，共 {len(agent_graph)} 个")
    return agent_graph


# =============================================================================
# 内部工具函数
# =============================================================================

def _resolve_prompts_actions_paths(
    agent_def: dict,
    entity_type: str,
    config_dir: Optional[str],
    default_prompts_path: Optional[str],
    default_actions_path: Optional[str],
) -> tuple:
    """解析 prompts 和 actions 的文件路径。

    优先级（从高到低）：
    1. agent_profile 中该 agent 定义显式指定的 prompts_path / actions_path
    2. generate_agents 调用方传入的 default_prompts_path / default_actions_path
    3. AGENT_CLASS_MAP 中注册的 fallback 默认路径
    4. config_dir 下按 role 自动探测（prompts/{role}.yaml, actions/{role}.yaml）
    5. config_dir 下同名文件自动探测
    """
    # 1. agent_def 中显式指定
    prompts_path = agent_def.get("prompts_path")
    actions_path = agent_def.get("actions_path")

    # 2. generate_agents 调用方传入的全局默认路径（项目级配置）
    if prompts_path is None:
        prompts_path = default_prompts_path
    if actions_path is None:
        actions_path = default_actions_path

    # 3. AGENT_CLASS_MAP 中注册的 fallback 路径（通用模板）
    if prompts_path is None or actions_path is None:
        cfg = AGENT_CLASS_MAP.get(entity_type, {})
        if prompts_path is None and cfg:
            default_dir = cfg.get("default_prompts_dir", f"config/template/entities/{entity_type}")
            prompts_path = os.path.join(default_dir, cfg.get("prompts_file", "prompts.yaml"))
            if not os.path.isabs(prompts_path):
                prompts_path = os.path.join(os.getcwd(), prompts_path)
        if actions_path is None and cfg:
            default_dir = cfg.get("default_prompts_dir", f"config/template/entities/{entity_type}")
            actions_path = os.path.join(default_dir, cfg.get("actions_file", "actions.yaml"))
            if not os.path.isabs(actions_path):
                actions_path = os.path.join(os.getcwd(), actions_path)

    # 4. 按 role 自动探测分角色配置（最高优先级覆盖）
    # 若 config_dir 缺失，尝试从 default_prompts_path 推导
    if not config_dir and default_prompts_path:
        config_dir = os.path.dirname(default_prompts_path)

    role = (agent_def.get("extra") or {}).get("role") if agent_def else None
    if role and config_dir:
        role_prompts = os.path.join(config_dir, "prompts", f"{role}.yaml")
        role_actions = os.path.join(config_dir, "actions", f"{role}.yaml")
        if os.path.exists(role_prompts):
            prompts_path = role_prompts
        if os.path.exists(role_actions):
            actions_path = role_actions

    # 5. 若提供了 config_dir，尝试在该目录下查找同名文件（兜底）
    if config_dir:
        if prompts_path and not os.path.exists(prompts_path):
            alt = os.path.join(config_dir, os.path.basename(prompts_path) if prompts_path else "prompts.yaml")
            if os.path.exists(alt):
                prompts_path = alt
        if actions_path and not os.path.exists(actions_path):
            alt = os.path.join(config_dir, os.path.basename(actions_path) if actions_path else "actions.yaml")
            if os.path.exists(alt):
                actions_path = alt

    return prompts_path, actions_path


async def _legacy_generate_residents(
    map,
    initial_population,
    agent_graph,
    shared_pool,
    prompts_path,
    actions_path,
    window_size,
    influence_registry,
    **kwargs
):
    """降级方案：当 agent_profile 为空时，直接生成 resident 数据并实例化。
    1. 生成 resident 画像数据；2. 加载 prompts/actions；3. 并发创建 Resident 实例。
    """
    import time as time_module
    import yaml
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.agents.resident import Resident, ResidentSharedInformationPool
    from src.generator.resident_generate import generate_resident_data

    start_time = time_module.time()

    if agent_graph is None:
        agent_graph = {}
    if shared_pool is None:
        shared_pool = ResidentSharedInformationPool()

    _prompts_path = prompts_path or "config/template/residents_prompts.yaml"
    _actions_path = actions_path or "config/template/resident_actions.yaml"

    prompts_data = {}
    actions_data = {}
    if _prompts_path and os.path.exists(_prompts_path):
        with open(_prompts_path, 'r', encoding='utf-8') as f:
            prompts_data = yaml.safe_load(f) or {}
    if _actions_path and os.path.exists(_actions_path):
        with open(_actions_path, 'r', encoding='utf-8') as f:
            actions_data = yaml.safe_load(f) or {}

    # 生成画像数据（无 profile_config 时使用默认随机生成）
    resident_info = generate_resident_data(initial_population)

    def create_single_agent(i, agent_data):
        agent_id = i + 1
        location, town_name = assign_agent_location(agent_data, map)

        agent = Resident(
            agent_id=agent_id,
            job_market=None,
            shared_pool=shared_pool,
            map=map,
            prompts=prompts_data,
            actions_config=actions_data,
            window_size=window_size,
            lightweight=True,
            influence_registry=influence_registry,
            profile_config=agent_data,
        )
        agent.town = town_name
        agent.location = location
        return agent_id, agent

    if initial_population == 0:
        return agent_graph

    max_workers = min(os.cpu_count() * 2, initial_population, 32)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(create_single_agent, i, data): i
            for i, data in enumerate(resident_info)
        }
        for future in as_completed(future_to_index):
            try:
                agent_id, agent = future.result()
                agent_graph[agent_id] = agent
            except Exception as e:
                print(f"[resident生成] 创建 Agent 失败: {e}")
                import traceback
                traceback.print_exc()

    total_time = time_module.time() - start_time
    print(f"[resident生成] 全部 resident 创建完成，总耗时: {total_time:.2f}秒")
    return agent_graph


async def generate_new_agents(
    count: int,
    map: Map,
    existing_agents: Dict[int, Any],
    agent_profile: Optional[Dict] = None,
    prompts_path: Optional[str] = None,
    actions_path: Optional[str] = None,
    config_dir: Optional[str] = None,
    influence_registry: Optional['InfluenceRegistry'] = None,
    **kwargs
) -> Dict[int, Any]:
    """增量生成新 Agent 并分配新 ID。

    Args:
        count: 新增数量
        map: 地图对象
        existing_agents: 现有 Agent 字典
        agent_profile: Agent 画像配置
        prompts_path: 提示词路径
        actions_path: 行动配置路径
        influence_registry: 影响函数注册表

    Returns:
        Dict[int, Any]: 仅包含新生成 Agent 的字典
    """
    new_agents = await generate_agents(
        map=map,
        initial_population=count,
        agent_profile=agent_profile,
        agent_graph={},
        prompts_path=prompts_path,
        actions_path=actions_path,
        config_dir=config_dir,
        influence_registry=influence_registry,
        **kwargs
    )

    # 分配不重复的 ID
    used_ids = set(existing_agents.keys())
    new_id = max(used_ids) + 1 if used_ids else 1

    result = {}
    for agent in new_agents.values():
        while new_id in used_ids:
            new_id += 1
        agent.agent_id = new_id
        if hasattr(agent, 'resident_id'):
            agent.resident_id = new_id
        result[new_id] = agent
        used_ids.add(new_id)
        new_id += 1

    return result

