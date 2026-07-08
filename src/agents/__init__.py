# src/agents/__init__.py
# Agent 系统入口：导出通用生成器及动态注册表
# 注意：为避免循环导入，BaseAgent 请直接从 src.agents.base_agent 导入

from .code_fixer import CodeFixerAgent
from .agent_generator import (
    generate_agents,
    generate_new_agents,
    AGENT_CLASS_MAP,
    register_agent_class,
    assign_agent_location,
    get_plugin_profile,
    clear_plugin_profiles,
    find_group_agent_def,
    generate_group_profiles,
    PLUGIN_MANAGED_TYPES,
)

__all__ = [
    "CodeFixerAgent",
    "generate_agents",
    "generate_new_agents",
    "AGENT_CLASS_MAP",
    "register_agent_class",
    "assign_agent_location",
    "get_plugin_profile",
    "clear_plugin_profiles",
    "find_group_agent_def",
    "generate_group_profiles",
    "PLUGIN_MANAGED_TYPES",
]
