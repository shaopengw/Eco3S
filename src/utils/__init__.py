"""
工具模块

提供日志、缓存、依赖注入等通用工具类。
"""

from .di_container import (
    DIContainer, 
    Lifecycle, 
    get_global_container, 
    reset_global_container,
)
from .di_helpers import (
    setup_container_for_simulation,
)
from .simulation_cache import SimulationCache
from .simulation_context import SimulationContext

__all__ = [
    # DI Container 核心类
    'DIContainer',
    'Lifecycle',
    'get_global_container',
    'reset_global_container',
    # DI 辅助函数
    'setup_container_for_simulation',
    # 其他工具
    'SimulationCache',
    'SimulationContext',
]
