"""
插件系统事件常量

集中定义所有插件间通信的事件名称，避免魔法字符串拼写错误。
新增事件时请先在此注册，然后在插件代码中使用。

Usage:
    from src.plugins import PluginEvent
    event_bus.subscribe(PluginEvent.TIME_ADVANCED, self._on_time_advanced)
    event_bus.publish(PluginEvent.MAP_INITIALIZED, {'width': 100})
"""


class PluginEvent:
    """插件系统标准事件名"""

    # 模拟生命周期
    SIMULATION_START = "simulation_start"

    # 地图相关
    MAP_INITIALIZED = "map_initialized"

    # 时间推进
    TIME_ADVANCED = "time_advanced"

    # 居民群体
    RESIDENT_GROUPS_INITIALIZED = "resident_groups_initialized"

    # 人口变化
    POPULATION_CHANGED = "population_changed"

    # 社交网络
    SOCIAL_NETWORK_INITIALIZED = "social_network_initialized"

    # 气候
    EXTREME_CLIMATE_EVENT = "extreme_climate_event"
    CLIMATE_DISASTER = "climate_disaster"

    # 就业市场
    RESIDENT_HIRED = "resident_hired"
    RESIDENT_FIRED = "resident_fired"
