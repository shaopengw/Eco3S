"""
依赖注入容器使用示例

演示如何使用 DIContainer 进行依赖注入和自动装配。
"""

from src.utils.di_container import DIContainer, Lifecycle

# 导入接口
from src.interfaces import (
    IMap, ITime, IPopulation, ITowns, ISocialNetwork, 
    ITransportEconomy, IClimateSystem, IGovernment, IRebellion
)

# 导入实现类
from src.environment.map import Map
from src.environment.time import Time
from src.environment.population import Population
from src.environment.towns import Towns
from src.environment.social_network import SocialNetwork
from src.environment.transport_economy import TransportEconomy
from src.environment.climate import ClimateSystem
from src.agents.government import Government
from src.agents.rebels import Rebellion


def setup_container_basic() -> DIContainer:
    """
    基础示例：手动注册所有依赖
    
    Returns:
        配置好的 DIContainer 实例
    """
    container = DIContainer()
    
    # 注册环境模块（单例模式）
    container.register(IMap, Map, lifecycle=Lifecycle.SINGLETON)
    container.register(ITime, Time, lifecycle=Lifecycle.SINGLETON)
    container.register(IPopulation, Population, lifecycle=Lifecycle.SINGLETON)
    container.register(ITowns, Towns, lifecycle=Lifecycle.SINGLETON)
    container.register(ISocialNetwork, SocialNetwork, lifecycle=Lifecycle.SINGLETON)
    container.register(ITransportEconomy, TransportEconomy, lifecycle=Lifecycle.SINGLETON)
    container.register(IClimateSystem, ClimateSystem, lifecycle=Lifecycle.SINGLETON)
    
    # 注册 Agent 模块（单例模式）
    container.register(IGovernment, Government, lifecycle=Lifecycle.SINGLETON)
    container.register(IRebellion, Rebellion, lifecycle=Lifecycle.SINGLETON)
    
    return container


def setup_container_with_factory(config: dict) -> DIContainer:
    """
    工厂函数示例：使用工厂函数注册需要配置参数的对象
    
    Args:
        config: 配置字典
        
    Returns:
        配置好的 DIContainer 实例
    """
    container = DIContainer()
    
    # 使用工厂函数注册需要配置参数的对象
    container.register_factory(
        IMap,
        lambda: Map(
            width=config["simulation"]["map_width"],
            height=config["simulation"]["map_height"],
            data_file=config["data"]["towns_data_path"]
        )
    )
    
    container.register_factory(
        ITime,
        lambda: Time(
            start_time=config["simulation"]["start_year"],
            total_steps=config["simulation"]["total_years"]
        )
    )
    
    container.register_factory(
        IPopulation,
        lambda: Population(
            initial_population=config["simulation"]["initial_population"],
            birth_rate=config["simulation"]["birth_rate"]
        )
    )
    
    # 其他依赖使用自动装配
    container.register(ITowns, Towns)
    container.register(ISocialNetwork, SocialNetwork)
    
    return container


def setup_container_with_instances(map_instance, time_instance) -> DIContainer:
    """
    实例注册示例：直接注册已创建的实例
    
    Args:
        map_instance: 已创建的 Map 实例
        time_instance: 已创建的 Time 实例
        
    Returns:
        配置好的 DIContainer 实例
    """
    container = DIContainer()
    
    # 直接注册已创建的实例
    container.register_instance(IMap, map_instance)
    container.register_instance(ITime, time_instance)
    
    # 其他依赖使用自动装配
    container.register(IPopulation, Population)
    container.register(ITowns, Towns)
    
    return container


def example_usage_basic():
    """基础使用示例"""
    print("=== 基础使用示例 ===")
    
    # 1. 创建容器
    container = DIContainer()
    
    # 2. 注册接口与实现类
    container.register(IMap, Map, lifecycle=Lifecycle.SINGLETON)
    container.register(ITime, Time, lifecycle=Lifecycle.SINGLETON)
    
    # 3. 解析实例（自动创建并注入依赖）
    map_instance = container.resolve(IMap)
    time_instance = container.resolve(ITime)
    
    print(f"Map 实例: {map_instance}")
    print(f"Time 实例: {time_instance}")
    
    # 4. 验证单例模式
    map_instance2 = container.resolve(IMap)
    print(f"单例验证: {map_instance is map_instance2}")  # 应该输出 True


def example_usage_with_dependencies():
    """依赖自动注入示例"""
    print("\n=== 依赖自动注入示例 ===")
    
    container = DIContainer()
    
    # 注册所有依赖
    container.register(IMap, Map)
    container.register(ITime, Time)
    container.register(ITransportEconomy, TransportEconomy)
    container.register(ITowns, Towns)
    
    # Government 的构造函数需要 map, towns, time, transport_economy
    # 容器会自动解析并注入这些依赖
    container.register(IGovernment, Government)
    
    # 解析 Government（会自动创建并注入所有依赖）
    government = container.resolve(IGovernment)
    print(f"Government 实例: {government}")
    print(f"Government.map: {government.map}")
    print(f"Government.towns: {government.towns}")


def example_usage_with_factory():
    """工厂函数示例"""
    print("\n=== 工厂函数示例 ===")
    
    container = DIContainer()
    
    # 使用工厂函数创建配置复杂的对象
    container.register_factory(
        IMap,
        lambda: Map(width=100, height=100, data_file="config/towns_data.json")
    )
    
    map_instance = container.resolve(IMap)
    print(f"通过工厂函数创建的 Map: {map_instance}")


def example_usage_transient():
    """瞬态模式示例（每次创建新实例）"""
    print("\n=== 瞬态模式示例 ===")
    
    container = DIContainer()
    
    # 使用瞬态模式注册
    container.register(ITime, Time, lifecycle=Lifecycle.TRANSIENT)
    
    # 每次调用 resolve 都会创建新实例
    time1 = container.resolve(ITime)
    time2 = container.resolve(ITime)
    
    print(f"Time 实例1: {time1}")
    print(f"Time 实例2: {time2}")
    print(f"是否为同一实例: {time1 is time2}")  # 应该输出 False


def example_check_bindings():
    """检查绑定信息示例"""
    print("\n=== 检查绑定信息示例 ===")
    
    container = DIContainer()
    
    container.register(IMap, Map)
    container.register(ITime, Time, lifecycle=Lifecycle.TRANSIENT)
    container.register_factory(IPopulation, lambda: Population(initial_population=1000))
    
    # 检查单个绑定
    map_info = container.get_binding_info(IMap)
    print(f"IMap 绑定信息: {map_info}")
    
    # 获取所有绑定
    all_bindings = container.get_all_bindings()
    print(f"\n所有绑定信息:")
    for name, info in all_bindings.items():
        print(f"  {name}: {info}")


def example_error_handling():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    container = DIContainer()
    
    # 1. 尝试解析未注册的接口
    try:
        container.resolve(IMap)
    except ValueError as e:
        print(f"错误1 - 未注册的接口: {e}")
    
    # 2. 循环依赖检测（需要构造循环依赖场景）
    # 注：实际使用中，容器会自动检测并抛出异常
    
    print("错误处理测试完成")


if __name__ == "__main__":
    """运行所有示例"""
    # 注意：这些示例需要实际的实现类支持
    # 在真实环境中运行前，确保所有依赖都已正确配置
    
    print("依赖注入容器使用示例")
    print("=" * 50)
    
    try:
        example_usage_basic()
        example_usage_with_dependencies()
        example_usage_with_factory()
        example_usage_transient()
        example_check_bindings()
        example_error_handling()
    except Exception as e:
        print(f"\n示例运行出错: {e}")
        print("请确保所有依赖模块已正确导入和配置")
