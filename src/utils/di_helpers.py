"""DIContainer 辅助函数

当前架构下：
- 模块选择/实例化由插件系统负责（modules_config.yaml 的 selected_modules）。
- DIContainer 仅用于插件构造期的自动注入，以及在插件加载后把实例注册进容器，
    以便其他插件通过类型注入（例如 Government/Rebellion 构造函数注入 IMap/ITowns）。
"""

from typing import Any, Dict, Optional

from src.utils.di_container import DIContainer
from src.interfaces import (
        IMap, ITime, IPopulation, ITowns, ISocialNetwork,
        ITransportEconomy, IClimateSystem, IJobMarket, IGovernment, IRebellion
)
from src.influences import InfluenceRegistry


def register_loaded_plugins(container: DIContainer, loaded_plugins: Optional[Dict[str, Any]]) -> None:
    """将已加载的插件实例注入 DIContainer。

    目标：让后续代码只需通过 `container.get(IMap)` 等接口获取即可拿到插件实现，
    避免在业务代码里硬编码插件名（如 map）。
    """
    if not loaded_plugins:
        return

    interface_types = (
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

    # 依赖先加载、目标后加载：后加载的同接口插件会覆盖先前注册
    for plugin in loaded_plugins.values():
        # 只对“service 模式”的模块插件做注入绑定；例如 residents 这类非模块插件不参与。
        if not hasattr(plugin, "service"):
            continue

        service = plugin.service  # type: ignore[attr-defined]

        for interface_type in interface_types:
            try:
                if isinstance(service, interface_type):
                    # 注入绑定注册插件本体：保留插件层的事件发布/包装逻辑。
                    container.register_instance(interface_type, plugin)
            except TypeError:
                # 某些 typing/动态类型在 isinstance 下可能抛 TypeError
                continue


def setup_container_for_simulation(
    influence_registry: Optional[InfluenceRegistry] = None,
) -> DIContainer:
    """
    为模拟设置依赖注入容器（推荐使用）
    此函数会：
    1. 创建 DIContainer
    2. （可选）注册 InfluenceRegistry 供插件构造期注入
    3. 返回容器
    """
    container = DIContainer()

    if influence_registry is not None:
        container.register_instance(InfluenceRegistry, influence_registry)

    return container



