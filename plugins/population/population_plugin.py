"""人口插件实现"""

from typing import Dict, Any, Optional
from src.influences import InfluenceRegistry
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.population import Population


class DefaultPopulationPlugin(Population, BasePlugin):
    """
    默认人口插件 - 直接继承 Population 业务类 + BasePlugin 生命周期
    """

    def __init__(
        self,
        initial_population: int = 1000,
        birth_rate: float = 0.01,
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        BasePlugin.__init__(self)
        self._initial_population_param = initial_population
        self._birth_rate_param = birth_rate
        self._influence_registry_param = influence_registry

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

        Population.__init__(
            self,
            initial_population=self._initial_population_param,
            birth_rate=self._birth_rate_param,
            influence_registry=self._influence_registry_param,
        )

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultPopulationPlugin 正在加载 (initial_population={self.population})")

        # 订阅事件
        self.subscribe_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, self._on_residents_initialized)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultPopulationPlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, self._on_residents_initialized)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultPopulation",
            "version": "1.0.0",
            "description": "默认人口系统插件（直接实现 IPopulation）",
            "author": "AgentWorld Team",
            "dependencies": ["towns"]
        }

    def birth(self, num: int) -> int:
        """人口出生（重写以发布事件）"""
        old_population = self.population
        new_population = Population.birth(self, num)

        # 发布人口变化事件
        self.publish_event(PluginEvent.POPULATION_CHANGED, {
            'old': old_population,
            'new': new_population,
            'change': num
        })

        return new_population

    def death(self) -> None:
        """人口死亡（重写以发布事件）"""
        old_population = self.population
        Population.death(self)

        # 发布人口变化事件
        self.publish_event(PluginEvent.POPULATION_CHANGED, {
            'old': old_population,
            'new': self.population,
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
            old = self.population
            self.population = resident_count
            self.logger.info(f"Population 同步为居民数量: {old} -> {resident_count}")
