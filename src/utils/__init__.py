"""
工具模块

提供日志、缓存、依赖注入等通用工具类。
"""

from .di_container import (
    DIContainer, 
    Lifecycle, 
    get_global_container, 
    reset_global_container,
    load_module_from_path,
    load_implementations_from_config,
    load_implementations_from_yaml,
    register_from_config,
    register_from_yaml,
    create_container_from_yaml
)
from .di_helpers import (
    setup_container_for_simulation,
    setup_container_from_config_dir,
    create_manual_container,
    resolve_all_dependencies
)
from .simulation_cache import SimulationCache
from .simulation_context import SimulationContext

__all__ = [
    # DI Container 核心类
    'DIContainer',
    'Lifecycle',
    'get_global_container',
    'reset_global_container',
    # 配置加载功能
    'load_module_from_path',
    'load_implementations_from_config',
    'load_implementations_from_yaml',
    'register_from_config',
    'register_from_yaml',
    'create_container_from_yaml',
    # DI 辅助函数
    'setup_container_for_simulation',
    'setup_container_from_config_dir',
    'create_manual_container',
    'resolve_all_dependencies',
    # 其他工具
    'SimulationCache',
    'SimulationContext',
]
