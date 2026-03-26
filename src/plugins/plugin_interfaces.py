"""插件接口 (Plugin Interfaces)

插件接口用于定义“插件生命周期 + service 暴露”约定。

插件包装业务实现对象（service），通过 ServicePlugin 自动转发，
从而避免为每个新增业务方法重复写插件代理。
"""

from abc import ABC
from typing import Any, Dict, TYPE_CHECKING

from .base_plugin import BasePlugin
from .service_plugin import ServicePlugin

if TYPE_CHECKING:
    from src.interfaces import (
        IAgentGroup,
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


class IMapPlugin(ServicePlugin, ABC):
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
    @property
    def service(self) -> "IMap":  # type: ignore[name-defined]
        return super().service


class ITimePlugin(ServicePlugin, ABC):
    """
    时间模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ITime 的业务方法（step, is_end, get_current_time 等）
    """
    @property
    def service(self) -> "ITime":  # type: ignore[name-defined]
        return super().service


class IPopulationPlugin(ServicePlugin, ABC):
    """
    人口模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IPopulation 的业务方法（birth, death, get_population 等）
    """
    @property
    def service(self) -> "IPopulation":  # type: ignore[name-defined]
        return super().service


class ITownsPlugin(ServicePlugin, ABC):
    """
    城镇模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ITowns 的业务方法（initialize_towns, initialize_resident_groups 等）
    """
    @property
    def service(self) -> "ITowns":  # type: ignore[name-defined]
        return super().service


class ISocialNetworkPlugin(ServicePlugin, ABC):
    """
    社交网络模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ISocialNetwork 的业务方法（initialize_network, add_new_residents 等）
    """
    @property
    def service(self) -> "ISocialNetwork":  # type: ignore[name-defined]
        return super().service


class ITransportEconomyPlugin(ServicePlugin, ABC):
    """
    交通经济模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - ITransportEconomy 的业务方法（calculate_river_price, calculate_maintenance_cost 等）
    """
    @property
    def service(self) -> "ITransportEconomy":  # type: ignore[name-defined]
        return super().service


class IClimatePlugin(ServicePlugin, ABC):
    """
    气候系统模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IClimateSystem 的业务方法（get_current_impact, _load_climate_data 等）
    """
    @property
    def service(self) -> "IClimateSystem":  # type: ignore[name-defined]
        return super().service


class IJobMarketPlugin(ServicePlugin, ABC):
    """
    就业市场模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IJobMarket 的业务方法（hire, fire, adjust_jobs_count 等）
    """
    @property
    def service(self) -> "IJobMarket":  # type: ignore[name-defined]
        return super().service


class IAgentGroupPlugin(ServicePlugin, ABC):
    """群体系统插件接口。

    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IAgentGroup 的群体级能力（如 orchestrate_group_decision）
    """

    @property
    def service(self) -> "IAgentGroup":  # type: ignore[name-defined]
        return super().service


class IGovernmentPlugin(IAgentGroupPlugin, ABC):
    """
    政府模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IGovernment 的业务方法（handle_public_budget, maintain_canal, adjust_tax_rate 等）
    """
    @property
    def service(self) -> "IGovernment":  # type: ignore[name-defined]
        return super().service


class IRebellionPlugin(IAgentGroupPlugin, ABC):
    """
    叛军模块插件接口
    
    插件必须同时实现：
    - BasePlugin 的生命周期方法
    - IRebellion 的业务方法（maintain_status, get_strength, get_resources 等）
    """
    @property
    def service(self) -> "IRebellion":  # type: ignore[name-defined]
        return super().service


class IResidentAgentsPlugin(BasePlugin, ABC):
    """居民 agent 生成器插件接口。

    约定：实现方提供异步 `generate(...)` 方法，返回居民字典。
    """

    async def generate(self, **kwargs) -> Dict[int, Any]:
        raise NotImplementedError


class IResidentsPlugin(BasePlugin, ABC):
    """居民系统插件接口。

    约定：
    - 插件实例可通过 `plugin_registry.get_plugin('residents')` 获取。
    - 插件内部缓存生成结果，提供一次性异步初始化方法 ensure_initialized()/init_residents()。
    """

    @property
    def residents(self) -> Dict[int, Any]:
        raise NotImplementedError

    async def ensure_initialized(self, **kwargs) -> Dict[int, Any]:
        raise NotImplementedError

    async def init_residents(self, **kwargs) -> Dict[int, Any]:
        return await self.ensure_initialized(**kwargs)


class IGovernmentOfficialsPlugin(BasePlugin, ABC):
    """政府官员 agent 生成器插件接口。"""

    async def generate(self, **kwargs) -> Dict[int, Any]:
        raise NotImplementedError


class IRebelsAgentsPlugin(BasePlugin, ABC):
    """叛军成员 agent 生成器插件接口。"""

    async def generate(self, **kwargs) -> Dict[int, Any]:
        raise NotImplementedError


# 插件接口映射（方便查询）
PLUGIN_INTERFACE_MAP = {
    'IAgentGroup': IAgentGroupPlugin,
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
    'IResidentAgentsPlugin': IResidentAgentsPlugin,
    'IResidentsPlugin': IResidentsPlugin,
    'IGovernmentOfficialsPlugin': IGovernmentOfficialsPlugin,
    'IRebelsAgentsPlugin': IRebelsAgentsPlugin,
}
