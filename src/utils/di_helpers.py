"""
DIContainer 辅助工具函数

为 entrypoint 文件提供快速设置和配置容器的工具函数
"""

import yaml
from typing import Dict, Any
from src.utils import DIContainer, create_container_from_yaml
from src.interfaces import (
    IMap, ITime, IPopulation, ITowns, ISocialNetwork,
    ITransportEconomy, IClimateSystem, IGovernment, IRebellion
)
from src.environment.map import Map
from src.environment.time import Time
from src.environment.population import Population


def setup_container_for_simulation(
    modules_config_path: str,
    simulation_config: Dict[str, Any],
    influence_registry: Any = None
) -> DIContainer:
    """
    为模拟设置依赖注入容器（推荐使用）
    
    此函数会：
    1. 从 modules_config.yaml 加载所有模块映射
    2. 为需要配置参数的核心模块注册工厂函数
    3. 将 InfluenceRegistry 传递给支持的模块
    4. 返回配置好的容器
    
    Args:
        modules_config_path: modules_config.yaml 的路径
        simulation_config: 模拟配置字典（从 simulation_config.yaml 加载）
        influence_registry: 影响函数注册中心实例（可选）
        
    Returns:
        配置好的 DIContainer 实例
        
    Example:
        import yaml
        from src.influences import InfluenceRegistry
        
        # 加载模拟配置
        with open("config/template/simulation_config.yaml", 'r') as f:
            sim_config = yaml.safe_load(f)
        
        # 初始化影响函数注册中心（可选）
        registry = InfluenceRegistry()
        registry.load_from_config(influences_config)
        
        # 设置容器
        container = setup_container_for_simulation(
            "config/template/modules_config.yaml",
            sim_config,
            influence_registry=registry
        )
        
        # 解析依赖
        map = container.resolve(IMap)
        time = container.resolve(ITime)
    """
    # 1. 从配置文件创建基础容器
    container = create_container_from_yaml(modules_config_path)
    
    # 2. 为核心模块注册工厂函数（使用配置参数，覆盖 YAML 中的默认注册）
    # Map 模块
    container.register_factory(
        IMap,
        lambda: Map(
            width=simulation_config.get('simulation', {}).get('map_width', 100),
            height=simulation_config.get('simulation', {}).get('map_height', 100),
            data_file=simulation_config.get('data', {}).get('towns_data_path', ''),
            influence_registry=influence_registry
        ),
        override=True
    )
    
    # Time 模块
    container.register_factory(
        ITime,
        lambda: Time(
            start_time=simulation_config.get('simulation', {}).get('start_year', 0),
            total_steps=simulation_config.get('simulation', {}).get('total_years', 10)
        ),
        override=True
    )
    
    # Population 模块
    container.register_factory(
        IPopulation,
        lambda: Population(
            initial_population=simulation_config.get('simulation', {}).get('initial_population', 1000),
            birth_rate=simulation_config.get('simulation', {}).get('birth_rate', 0.01),
            influence_registry=influence_registry
        ),
        override=True
    )
    
    # TransportEconomy 模块（使用配置中的值，或默认值）
    from src.environment.transport_economy import TransportEconomy
    transport_config = simulation_config.get('transport_economy', {})
    container.register_factory(
        ITransportEconomy,
        lambda: TransportEconomy(
            transport_cost=transport_config.get('transport_cost', 1.0),
            transport_task=transport_config.get('transport_task', 1000.0),
            maintenance_cost_base=transport_config.get('maintenance_cost_base', 100.0),
            influence_registry=influence_registry
        ),
        override=True
    )
    
    # ClimateSystem 模块（使用配置中的 climate_info_path）
    from src.environment.climate import ClimateSystem
    climate_data_path = simulation_config.get('data', {}).get('climate_info_path', 'experiment_dataset/climate_data/climate.csv')
    container.register_factory(
        IClimateSystem,
        lambda: ClimateSystem(
            climate_data_path=climate_data_path,
            influence_registry=influence_registry
        ),
        override=True
    )
    
    return container


def setup_container_from_config_dir(config_dir: str) -> DIContainer:
    """
    从配置目录设置容器（便捷方法）
    
    自动加载配置目录下的 modules_config.yaml 和 simulation_config.yaml
    
    Args:
        config_dir: 配置目录路径，如 "config/template"
        
    Returns:
        配置好的 DIContainer 实例
        
    Example:
        container = setup_container_from_config_dir("config/template")
        map = container.resolve(IMap)
    """
    import os
    
    modules_config_path = os.path.join(config_dir, "modules_config.yaml")
    simulation_config_path = os.path.join(config_dir, "simulation_config.yaml")
    
    # 加载模拟配置
    with open(simulation_config_path, 'r', encoding='utf-8') as f:
        simulation_config = yaml.safe_load(f)
    
    return setup_container_for_simulation(modules_config_path, simulation_config)


def create_manual_container(config: Dict[str, Any]) -> DIContainer:
    """
    手动创建容器（不使用配置文件）
    
    适用于需要完全控制容器配置的场景
    
    Args:
        config: 模拟配置字典
        
    Returns:
        配置好的 DIContainer 实例
        
    Example:
        container = create_manual_container(config)
        # 然后手动注册其他模块
        container.register(ICustomModule, CustomModule)
    """
    from src.environment.towns import Towns
    from src.environment.social_network import SocialNetwork
    from src.environment.transport_economy import TransportEconomy
    from src.environment.climate import ClimateSystem
    from src.agents.government import Government
    from src.agents.rebels import Rebellion
    
    container = DIContainer()
    
    # 注册基础环境模块（使用工厂函数）
    container.register_factory(
        IMap,
        lambda: Map(
            width=config['simulation']['map_width'],
            height=config['simulation']['map_height'],
            data_file=config['data'].get('towns_data_path', '')
        )
    )
    
    container.register_factory(
        ITime,
        lambda: Time(
            start_time=config['simulation']['start_year'],
            total_steps=config['simulation']['total_years']
        )
    )
    
    container.register_factory(
        IPopulation,
        lambda: Population(
            initial_population=config['simulation']['initial_population'],
            birth_rate=config['simulation']['birth_rate']
        )
    )
    
    # 注册其他模块（自动装配）
    container.register(ITowns, Towns)
    container.register(ISocialNetwork, SocialNetwork)
    container.register(ITransportEconomy, TransportEconomy)
    container.register(IClimateSystem, ClimateSystem)
    container.register(IGovernment, Government)
    container.register(IRebellion, Rebellion)
    
    return container


def resolve_all_dependencies(container: DIContainer) -> Dict[str, Any]:
    """
    解析所有标准模拟依赖
    
    Args:
        container: 配置好的 DIContainer 实例
        
    Returns:
        包含所有依赖实例的字典
        
    Example:
        container = setup_container_from_config_dir("config/template")
        deps = resolve_all_dependencies(container)
        
        # 传递给 Simulator
        simulator = Simulator(
            map=deps['map'],
            time=deps['time'],
            population=deps['population'],
            ...
        )
    """
    return {
        'map': container.resolve(IMap),
        'time': container.resolve(ITime),
        'population': container.resolve(IPopulation),
        'towns': container.resolve(ITowns),
        'social_network': container.resolve(ISocialNetwork),
        'transport_economy': container.resolve(ITransportEconomy),
        'climate': container.resolve(IClimateSystem),
        'government': container.resolve(IGovernment),
        'rebellion': container.resolve(IRebellion),
    }


# ========================================
# Main.py 示例用法
# ========================================

def example_usage_in_main():
    """
    在 main.py 中使用的示例
    
    这展示了如何在实际的 entrypoint 文件中使用 DIContainer
    """
    import yaml
    
    print("=== Entrypoint 中使用 DIContainer 示例 ===\n")
    
    # 1. 加载配置
    config_path = "config/template/simulation_config.yaml"
    modules_config_path = "config/template/modules_config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 2. 设置容器（方式1：推荐）
    container = setup_container_for_simulation(modules_config_path, config)
    
    # 或者方式2：更简单
    # container = setup_container_from_config_dir("config/template")
    
    # 3. 解析依赖（逐个获取）
    map = container.resolve(IMap)
    time = container.resolve(ITime)
    population = container.resolve(IPopulation)
    
    print(f"✓ Map: {type(map).__name__}")
    print(f"✓ Time: {type(time).__name__}")
    print(f"✓ Population: {type(population).__name__}")
    
    # 或者方式3：一次性解析所有依赖
    # deps = resolve_all_dependencies(container)
    # map = deps['map']
    # time = deps['time']
    # ...
    
    # 4. 初始化需要特殊处理的对象（如 residents）
    # residents = await generate_canal_agents(...)
    # container.register_instance(IResidents, residents)
    
    # 5. 创建 Simulator
    # simulator = Simulator(
    #     map=map,
    #     time=time,
    #     population=population,
    #     towns=container.resolve(ITowns),
    #     social_network=container.resolve(ISocialNetwork),
    #     transport_economy=container.resolve(ITransportEconomy),
    #     climate=container.resolve(IClimateSystem),
    #     government=container.resolve(IGovernment),
    #     rebellion=container.resolve(IRebellion),
    #     config=config,
    # )
    
    print("\n所有依赖已解析，可以创建 Simulator！")


if __name__ == "__main__":
    try:
        example_usage_in_main()
    except Exception as e:
        print(f"示例运行出错: {e}")
        import traceback
        traceback.print_exc()
