"""
影响函数注册中心 (Influence Registry)

该模块实现了影响函数的注册、查询和管理功能。
支持从配置文件动态加载影响函数，并提供工厂方法创建不同类型的影响函数。

主要功能：
- 注册和管理影响函数
- 按目标模块查询相关的影响函数
- 从配置文件加载影响函数
- 提供内置的影响函数类型

使用示例：
    from src.influences import InfluenceRegistry
    
    # 创建注册中心
    registry = InfluenceRegistry()
    
    # 注册影响函数
    registry.register(my_influence)
    
    # 获取针对特定目标的所有影响函数
    influences = registry.get_influences('population')
    
    # 从配置加载
    registry.load_from_config(config_dict)
"""

from typing import List, Dict, Optional, Type, Callable, Any
import logging
from collections import defaultdict

from .iinfluence import IInfluenceFunction


class InfluenceRegistry:
    """
    影响函数注册中心
    
    管理所有影响函数的注册、查询和生命周期。
    支持按源模块、目标模块或名称查询影响函数。
    
    Attributes:
        influences: 所有已注册的影响函数列表
        by_target: 按目标模块索引的影响函数字典
        by_source: 按源模块索引的影响函数字典
        by_name: 按名称索引的影响函数字典
        factories: 影响函数工厂方法字典
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化影响函数注册中心
        
        Args:
            logger: 日志记录器（可选）
        """
        self._influences: List[IInfluenceFunction] = []
        self._by_target: Dict[str, List[IInfluenceFunction]] = defaultdict(list)
        self._by_source: Dict[str, List[IInfluenceFunction]] = defaultdict(list)
        self._by_name: Dict[str, IInfluenceFunction] = {}
        self._factories: Dict[str, Callable] = {}
        
        self.logger = logger or logging.getLogger(__name__)
        
        # 注册内置的影响函数工厂
        self._register_builtin_factories()
    
    def register(self, influence: IInfluenceFunction) -> None:
        """
        注册一个影响函数
        
        Args:
            influence: 要注册的影响函数实例
        
        Raises:
            ValueError: 如果影响函数名称已存在
        
        Example:
            registry = InfluenceRegistry()
            registry.register(ClimateToPopulationInfluence())
        """
        # 检查名称是否已存在
        full_name = f"{influence.source}->{influence.target}:{influence.name}"
        if full_name in self._by_name:
            raise ValueError(
                f"Influence with name '{full_name}' already registered. "
                f"Use a unique name for each influence."
            )
        
        # 注册影响函数
        self._influences.append(influence)
        self._by_target[influence.target].append(influence)
        self._by_source[influence.source].append(influence)
        self._by_name[full_name] = influence
        
        self.logger.info(
            f"Registered influence: {influence.source} -> {influence.target} "
            f"[{influence.name}]"
        )
    
    def get_influences(self, target: str) -> List[IInfluenceFunction]:
        """
        获取所有影响指定目标模块的影响函数
        
        Args:
            target: 目标模块名称（如 "population", "towns"）
        
        Returns:
            影响函数列表，如果没有则返回空列表
        
        Example:
            influences = registry.get_influences('population')
            for influence in influences:
                result = influence.apply(target_obj, context)
        """
        return self._by_target.get(target, [])
    
    def get_influences_by_source(self, source: str) -> List[IInfluenceFunction]:
        """
        获取所有来自指定源模块的影响函数
        
        Args:
            source: 源模块名称（如 "climate", "transport_economy"）
        
        Returns:
            影响函数列表
        """
        return self._by_source.get(source, [])
    
    def get_influence_by_name(self, source: str, target: str, name: str) -> Optional[IInfluenceFunction]:
        """
        根据完整名称获取影响函数
        
        Args:
            source: 源模块名称
            target: 目标模块名称
            name: 影响函数名称
        
        Returns:
            影响函数实例，如果不存在则返回 None
        """
        full_name = f"{source}->{target}:{name}"
        return self._by_name.get(full_name)
    
    def get_all_influences(self) -> List[IInfluenceFunction]:
        """获取所有已注册的影响函数"""
        return self._influences.copy()
    
    def unregister(self, source: str, target: str, name: str) -> bool:
        """
        取消注册一个影响函数
        
        Args:
            source: 源模块名称
            target: 目标模块名称
            name: 影响函数名称
        
        Returns:
            如果成功取消注册返回 True，否则返回 False
        """
        full_name = f"{source}->{target}:{name}"
        influence = self._by_name.get(full_name)
        
        if not influence:
            return False
        
        # 从所有索引中移除
        self._influences.remove(influence)
        self._by_target[target].remove(influence)
        self._by_source[source].remove(influence)
        del self._by_name[full_name]
        
        self.logger.info(f"Unregistered influence: {full_name}")
        return True
    
    def clear(self) -> None:
        """清空所有已注册的影响函数"""
        count = len(self._influences)
        self._influences.clear()
        self._by_target.clear()
        self._by_source.clear()
        self._by_name.clear()
        
        self.logger.info(f"Cleared {count} influences from registry")
    
    def register_factory(self, type_name: str, factory: Callable) -> None:
        """
        注册一个影响函数工厂方法
        
        Args:
            type_name: 影响函数类型名称
            factory: 工厂函数，接收配置字典，返回影响函数实例
        
        Example:
            def create_climate_influence(config):
                return ClimateToPopulationInfluence(**config)
            
            registry.register_factory('climate_death', create_climate_influence)
        """
        self._factories[type_name] = factory
        self.logger.info(f"Registered factory for influence type: {type_name}")
    
    def load_from_config(self, config: dict) -> int:
        """
        从配置字典加载影响函数
        
        Args:
            config: 配置字典，格式：
                {
                    'influences': [
                        {
                            'type': 'climate_death',
                            'source': 'climate',
                            'target': 'population',
                            'name': 'extreme_weather_death',
                            'params': {...}  # 可选的额外参数
                        },
                        ...
                    ]
                }
        
        Returns:
            成功加载的影响函数数量
        
        Raises:
            ValueError: 如果配置格式错误或影响函数类型不存在
        
        Example:
            config = {
                'influences': [
                    {
                        'type': 'linear_multiplier',
                        'source': 'climate',
                        'target': 'population',
                        'name': 'temperature_death',
                        'params': {
                            'multiplier': 0.01,
                            'threshold': 35
                        }
                    }
                ]
            }
            registry.load_from_config(config)
        """
        if 'influences' not in config:
            self.logger.warning("Config does not contain 'influences' key")
            return 0
        
        influences_config = config['influences']
        if not isinstance(influences_config, list):
            raise ValueError("Config 'influences' must be a list")
        
        loaded_count = 0
        
        for idx, inf_config in enumerate(influences_config):
            try:
                self._load_single_influence(inf_config)
                loaded_count += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to load influence #{idx}: {e}",
                    exc_info=True
                )
        
        self.logger.info(
            f"Loaded {loaded_count}/{len(influences_config)} influences from config"
        )
        return loaded_count
    
    def _load_single_influence(self, config: dict) -> None:
        """
        从配置加载单个影响函数
        
        Args:
            config: 单个影响函数的配置字典
        
        Raises:
            ValueError: 如果配置缺少必需字段或类型不支持
        """
        # 验证必需字段
        required_fields = ['type', 'source', 'target', 'name']
        missing_fields = [f for f in required_fields if f not in config]
        
        if missing_fields:
            raise ValueError(
                f"Influence config missing required fields: {missing_fields}"
            )
        
        influence_type = config['type']
        
        # 查找工厂方法
        if influence_type not in self._factories:
            raise ValueError(
                f"Unknown influence type: '{influence_type}'. "
                f"Available types: {list(self._factories.keys())}"
            )
        
        # 使用工厂方法创建影响函数
        factory = self._factories[influence_type]
        influence = factory(config)
        
        # 注册影响函数
        self.register(influence)
    
    def _register_builtin_factories(self) -> None:
        """注册内置的影响函数工厂方法"""
        from .builtin_influences import (
            create_linear_multiplier_influence,
            create_threshold_influence,
            create_conditional_influence,
            create_lambda_influence
        )
        from .builtin import (
            create_constant_influence,
            create_linear_influence,
            create_code_influence
        )
        
        # 注册 builtin_influences 中的工厂
        self.register_factory('linear_multiplier', create_linear_multiplier_influence)
        self.register_factory('threshold', create_threshold_influence)
        self.register_factory('conditional', create_conditional_influence)
        self.register_factory('lambda', create_lambda_influence)
        
        # 注册 builtin 中的工厂
        self.register_factory('constant', create_constant_influence)
        self.register_factory('linear', create_linear_influence)
        self.register_factory('code', create_code_influence)
    
    def list_targets(self) -> List[str]:
        """获取所有有影响函数的目标模块列表"""
        return list(self._by_target.keys())
    
    def list_sources(self) -> List[str]:
        """获取所有有影响函数的源模块列表"""
        return list(self._by_source.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取注册中心的统计信息
        
        Returns:
            包含统计信息的字典
        """
        return {
            'total_influences': len(self._influences),
            'targets': {
                target: len(influences)
                for target, influences in self._by_target.items()
            },
            'sources': {
                source: len(influences)
                for source, influences in self._by_source.items()
            },
            'registered_types': list(self._factories.keys())
        }
    
    def __repr__(self) -> str:
        """返回注册中心的字符串表示"""
        return (
            f"<InfluenceRegistry: "
            f"{len(self._influences)} influences, "
            f"{len(self._by_target)} targets, "
            f"{len(self._by_source)} sources>"
        )
