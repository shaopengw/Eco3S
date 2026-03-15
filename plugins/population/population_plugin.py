"""
人口插件实现 - 包装器模式
"""
from typing import Dict, Any
from src.plugins import IPopulationPlugin, PluginContext
from src.interfaces import IPopulation
from src.environment.population import Population


class DefaultPopulationPlugin(IPopulationPlugin):
    """
    默认人口插件 - 包装现有 Population 类
    """
    
    def __init__(self, initial_population: int = 1000,
                 birth_rate: float = 0.01):
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
        self._population = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建原始 Population 实例
        self._population = Population(
            initial_population=self._initial_population_param,
            birth_rate=self._birth_rate_param
        )
    
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
            "dependencies": ["default_towns"]
        }
    
    # ===== IPopulation 接口属性 - 代理到内部 Population 实例 =====
    
    @property
    def population(self) -> int:
        return self._population.population
    
    @population.setter
    def population(self, value: int):
        self._population.population = value
    
    @property
    def birth_rate(self) -> float:
        return self._population.birth_rate
    
    @birth_rate.setter
    def birth_rate(self, value: float):
        self._population.birth_rate = value
    
    # ===== IPopulation 接口方法 - 代理到内部 Population 实例 =====
    
    def update_birth_rate(self, satisfaction: float) -> None:
        """根据居民平均满意度更新出生率"""
        self._population.update_birth_rate(satisfaction)
    
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
    
    def get_population(self) -> int:
        """获取当前人口数量"""
        return self._population.get_population()
    
    def set_population(self, value: int) -> None:
        """设置人口数量"""
        self._population.population = value
    
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
    
    def print_population_status(self) -> None:
        """打印人口状态"""
        self._population.print_population_status()
    
    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """应用影响函数"""
        self._population.apply_influences(target_name, context)
    
    # ===== 内部方法 =====
    
    def _on_residents_initialized(self, data: Dict[str, Any]) -> None:
        """居民初始化时的处理"""
        self.logger.info("收到 resident_groups_initialized 事件")
