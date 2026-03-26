"""人口插件实现 - 包装器模式"""

from typing import Dict, Any, Optional
from src.plugins import IPopulationPlugin, PluginContext
from src.influences import InfluenceRegistry
from src.environment.population import Population


class DefaultPopulationPlugin(IPopulationPlugin):
    """
    默认人口插件 - 包装现有 Population 类
    """
    
    def __init__(
        self,
        initial_population: int = 1000,
        birth_rate: float = 0.01,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        """
        初始化人口插件
        
        Args:
            initial_population: 初始人口数量
            birth_rate: 出生率
        """
        super().__init__()
        
        # 保存参数
        self._initial_population_param = initial_population
        self._birth_rate_param = birth_rate
        self._influence_registry_param = influence_registry
        self._population = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 从 simulation_config.yaml 覆盖默认参数（若存在）
        sim_cfg = (context.config or {}).get('simulation', {})
        if isinstance(sim_cfg, dict):
            if isinstance(sim_cfg.get('initial_population'), int):
                self._initial_population_param = sim_cfg['initial_population']
            if isinstance(sim_cfg.get('birth_rate'), (int, float)):
                self._birth_rate_param = float(sim_cfg['birth_rate'])
        
        # 创建原始 Population 实例
        self._population = Population(
            initial_population=self._initial_population_param,
            birth_rate=self._birth_rate_param,
            influence_registry=self._influence_registry_param,
        )
        self._service = self._population

        # 让 InfluenceManager 能识别该模块可应用影响函数
        self._influence_registry = getattr(self._population, "_influence_registry", None) or self._influence_registry_param
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultPopulationPlugin 正在加载 (initial_population={self._population.population})")
        
        # 订阅事件
        self.context.event_bus.subscribe('resident_groups_initialized', self._on_residents_initialized)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultPopulationPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('resident_groups_initialized', self._on_residents_initialized)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultPopulation",
            "version": "1.0.0",
            "description": "默认人口系统插件（包装 Population 类）",
            "author": "AgentWorld Team",
            "dependencies": ["towns"]
        }
    
    def birth(self, num: int) -> int:
        """人口出生"""
        old_population = self._population.population
        new_population = self._population.birth(num)
        
        # 发布人口变化事件
        self.context.event_bus.publish('population_changed', {
            'old': old_population,
            'new': new_population,
            'change': num
        })
        
        return new_population
    
    def death(self) -> None:
        """人口死亡"""
        old_population = self._population.population
        self._population.death()
        
        # 发布人口变化事件
        self.context.event_bus.publish('population_changed', {
            'old': old_population,
            'new': self._population.population,
            'change': -1
        })
    
    # ===== 内部方法 =====
    
    def _on_residents_initialized(self, data: Dict[str, Any]) -> None:
        """居民初始化时的处理"""
        self.logger.info("收到 resident_groups_initialized 事件")

        resident_count = None
        if isinstance(data, dict):
            resident_count = data.get('resident_count')

        if isinstance(resident_count, int) and resident_count >= 0:
            old = self._population.population
            self._population.population = resident_count
            self.logger.info(f"Population 同步为居民数量: {old} -> {resident_count}")
