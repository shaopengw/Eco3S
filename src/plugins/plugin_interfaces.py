"""
插件接口 (Plugin Interfaces)

为每个业务模块定义插件接口，继承 BasePlugin 和对应的业务接口。
这样可以确保插件既满足插件生命周期要求，又满足业务接口要求。
"""

from abc import ABC
from .base_plugin import BasePlugin
from src.interfaces import (
    IMap,
    ITime,
    IPopulation,
    ITowns,
    ISocialNetwork,
    ITransportEconomy,
    IClimateSystem,
    IJobMarket,
    IGovernment,
    IRebellion,
)


class IMapPlugin(BasePlugin, IMap, ABC):
    """
    地图模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法（init, on_load, on_unload, get_metadata）
    - IMap 的业务方法（initialize_map, get_width, get_height 等）
    
    Example:
        ```python
        class CustomMapPlugin(IMapPlugin):
            def __init__(self, width: int, height: int, data_file: str):
                BasePlugin.__init__(self)
                self._width = width
                self._height = height
                self._data_file = data_file
            
            def init(self, context: PluginContext) -> None:
                self._context = context
                context.log_info("CustomMap plugin initializing...")
            
            def on_load(self) -> None:
                self._context.log_info("CustomMap plugin loaded")
                self._mark_loaded()
            
            def on_unload(self) -> None:
                self._context.log_info("CustomMap plugin unloaded")
                self._mark_unloaded()
            
            def get_metadata(self) -> Dict[str, Any]:
                return {
                    "name": "CustomMap",
                    "version": "1.0.0",
                    "description": "Custom map with enhanced features",
                    "author": "AgentWorld Team",
                    "dependencies": []
                }
            
            # 实现 IMap 的业务方法
            @property
            def width(self) -> int:
                return self._width
            
            # ... 其他 IMap 方法
        ```
    """
    pass


class ITimePlugin(BasePlugin, ITime, ABC):
    """
    时间模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ITime 的业务方法（step, is_end, get_current_time 等）
    """
    pass


class IPopulationPlugin(BasePlugin, IPopulation, ABC):
    """
    人口模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IPopulation 的业务方法（birth, death, get_population 等）
    """
    pass


class ITownsPlugin(BasePlugin, ITowns, ABC):
    """
    城镇模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ITowns 的业务方法（initialize_towns, initialize_resident_groups 等）
    """
    pass


class ISocialNetworkPlugin(BasePlugin, ISocialNetwork, ABC):
    """
    社交网络模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ISocialNetwork 的业务方法（initialize_network, add_new_residents 等）
    """
    pass


class ITransportEconomyPlugin(BasePlugin, ITransportEconomy, ABC):
    """
    交通经济模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ITransportEconomy 的业务方法（calculate_river_price, calculate_maintenance_cost 等）
    """
    pass


class IClimatePlugin(BasePlugin, IClimateSystem, ABC):
    """
    气候系统模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IClimateSystem 的业务方法（get_current_impact, _load_climate_data 等）
    """
    pass


class IJobMarketPlugin(BasePlugin, IJobMarket, ABC):
    """
    就业市场模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IJobMarket 的业务方法（hire, fire, adjust_jobs_count 等）
    """
    pass


class IGovernmentPlugin(BasePlugin, IGovernment, ABC):
    """
    政府模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IGovernment 的业务方法（handle_public_budget, maintain_canal, adjust_tax_rate 等）
    """
    pass


class IRebellionPlugin(BasePlugin, IRebellion, ABC):
    """
    叛军模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IRebellion 的业务方法（maintain_status, get_strength, get_resources 等）
    """
    pass


# 插件接口映射（方便查询）
PLUGIN_INTERFACE_MAP = {
    'IMap': IMapPlugin,
    'ITime': ITimePlugin,
    'IPopulation': IPopulationPlugin,
    'ITowns': ITownsPlugin,
    'ISocialNetwork': ISocialNetworkPlugin,
    'ITransportEconomy': ITransportEconomyPlugin,
    'IClimateSystem': IClimatePlugin,
    'IJobMarket': IJobMarketPlugin,
    'IGovernment': IGovernmentPlugin,
    'IRebellion': IRebellionPlugin,
}
