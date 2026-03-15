"""
从配置文件加载模块的示例

演示如何使用 modules_config.yaml 配置 DIContainer
"""

from src.utils import (
    DIContainer,
    create_container_from_yaml,
    register_from_yaml,
    load_implementations_from_yaml
)

# 示例1：使用便捷方法创建容器
def example_create_from_yaml():
    """最简单的方式：直接从配置文件创建容器"""
    print("=== 示例1: 从 YAML 创建容器 ===")
    
    # 一行代码创建并配置容器
    container = create_container_from_yaml("config/template/modules_config.yaml")
    
    # 从接口导入（用于类型注解）
    from src.interfaces import IMap, ITime, IPopulation
    
    # 解析实例（自动根据配置文件中的映射创建）
    map_instance = container.resolve(IMap)
    time_instance = container.resolve(ITime)
    population_instance = container.resolve(IPopulation)
    
    print(f"Map 实例: {map_instance}")
    print(f"Time 实例: {time_instance}")
    print(f"Population 实例: {population_instance}")
    print()


def example_register_to_existing_container():
    """向已有容器注册配置文件中的模块"""
    print("=== 示例2: 向已有容器注册模块 ===")
    
    # 创建空容器
    container = DIContainer()
    
    # 从配置文件注册模块
    register_from_yaml(container, "config/template/modules_config.yaml")
    
    # 查看所有绑定
    bindings = container.get_all_bindings()
    print(f"已注册 {len(bindings)} 个模块:")
    for name, info in bindings.items():
        print(f"  - {name}: {info['implementation']} ({info['lifecycle']})")
    print()


def example_load_and_inspect():
    """加载配置但不立即注册（用于检查）"""
    print("=== 示例3: 加载并检查实现映射 ===")
    
    # 只加载映射，不注册
    implementations = load_implementations_from_yaml("config/template/modules_config.yaml")
    
    print(f"从配置文件加载了 {len(implementations)} 个映射:")
    for interface, implementation in implementations.items():
        print(f"  - {interface.__name__} -> {implementation.__name__}")
    print()


def example_with_factory_functions():
    """结合工厂函数使用"""
    print("=== 示例4: 结合工厂函数 ===")
    
    import yaml
    
    # 加载模拟配置
    with open("config/template/simulation_config.yaml", 'r', encoding='utf-8') as f:
        sim_config = yaml.safe_load(f)
    
    # 从 modules_config.yaml 创建基础容器
    container = create_container_from_yaml("config/template/modules_config.yaml")
    
    # 为需要配置参数的模块注册工厂函数
    from src.interfaces import IMap, ITime, IPopulation
    from src.environment.map import Map
    from src.environment.time import Time
    from src.environment.population import Population
    
    # 覆盖默认注册，使用工厂函数
    container.register_factory(
        IMap,
        lambda: Map(
            width=sim_config['simulation']['map_width'],
            height=sim_config['simulation']['map_height'],
            data_file=sim_config['data']['towns_data_path']
        )
    )
    
    container.register_factory(
        ITime,
        lambda: Time(
            start_time=sim_config['simulation']['start_year'],
            total_steps=sim_config['simulation']['total_years']
        )
    )
    
    container.register_factory(
        IPopulation,
        lambda: Population(
            initial_population=sim_config['simulation']['initial_population'],
            birth_rate=sim_config['simulation']['birth_rate']
        )
    )
    
    # 解析实例（会使用工厂函数创建）
    map_instance = container.resolve(IMap)
    print(f"Map 实例 (使用工厂): {map_instance}")
    print(f"  - 宽度: {map_instance.width}")
    print(f"  - 高度: {map_instance.height}")
    print()


def example_real_world_usage():
    """真实场景：在 main.py 中使用"""
    print("=== 示例5: 真实场景用法 ===")
    
    import yaml
    
    # 1. 从配置文件创建容器
    config_path = "config/template/simulation_config.yaml"
    modules_config_path = "config/template/modules_config.yaml"
    
    # 加载模拟配置
    with open(config_path, 'r', encoding='utf-8') as f:
        sim_config = yaml.safe_load(f)
    
    # 创建并配置容器
    container = create_container_from_yaml(modules_config_path)
    
    # 2. 为需要配置的模块注册工厂函数
    from src.interfaces import IMap, ITime, IPopulation, ITowns, ISocialNetwork
    from src.environment.map import Map
    from src.environment.time import Time
    from src.environment.population import Population
    
    # 注册带配置的工厂函数
    container.register_factory(
        IMap,
        lambda: Map(
            width=sim_config['simulation']['map_width'],
            height=sim_config['simulation']['map_height'],
            data_file=sim_config['data']['towns_data_path']
        )
    )
    
    container.register_factory(
        ITime,
        lambda: Time(
            start_time=sim_config['simulation']['start_year'],
            total_steps=sim_config['simulation']['total_years']
        )
    )
    
    container.register_factory(
        IPopulation,
        lambda: Population(
            initial_population=sim_config['simulation']['initial_population'],
            birth_rate=sim_config['simulation']['birth_rate']
        )
    )
    
    # 3. 解析所有依赖
    print("解析模拟系统所需的所有模块...")
    map_inst = container.resolve(IMap)
    time_inst = container.resolve(ITime)
    population_inst = container.resolve(IPopulation)
    towns_inst = container.resolve(ITowns)
    social_network_inst = container.resolve(ISocialNetwork)
    
    print(f"✓ Map: {type(map_inst).__name__}")
    print(f"✓ Time: {type(time_inst).__name__}")
    print(f"✓ Population: {type(population_inst).__name__}")
    print(f"✓ Towns: {type(towns_inst).__name__}")
    print(f"✓ SocialNetwork: {type(social_network_inst).__name__}")
    
    # 4. 这些实例现在可以传递给 Simulator
    # simulator = Simulator(
    #     map=map_inst,
    #     time=time_inst,
    #     population=population_inst,
    #     ...
    # )
    
    print("\n所有模块已成功解析并准备好使用！")


def example_error_handling():
    """错误处理示例"""
    print("=== 示例6: 错误处理 ===")
    
    container = DIContainer()
    
    # 1. 配置文件不存在
    try:
        register_from_yaml(container, "config/nonexistent.yaml")
    except FileNotFoundError as e:
        print(f"✓ 正确捕获错误: {e}")
    
    # 2. 模块导入失败
    from src.utils.di_container import load_module_from_path
    try:
        load_module_from_path("src.nonexistent.Module")
    except ImportError as e:
        print(f"✓ 正确捕获错误: {type(e).__name__}")
    
    print()


if __name__ == "__main__":
    """运行所有示例"""
    print("DI Container 配置文件加载示例")
    print("=" * 60)
    print()
    
    try:
        example_create_from_yaml()
        example_register_to_existing_container()
        example_load_and_inspect()
        # example_with_factory_functions()  # 需要完整配置文件
        # example_real_world_usage()  # 需要完整配置文件
        example_error_handling()
        
        print("=" * 60)
        print("所有示例运行完成！")
        
    except Exception as e:
        print(f"\n示例运行出错: {e}")
        import traceback
        traceback.print_exc()
