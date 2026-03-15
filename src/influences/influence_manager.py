"""
影响函数管理器 (Influence Manager)

负责协调各模块影响函数的执行，包括：
- 构建全局 context
- 按依赖顺序执行影响函数
- 更新 context 中的状态值
"""

from typing import Dict, Any, Optional, List
import logging


class InfluenceManager:
    """
    影响函数执行管理器
    
    负责在模拟的每个时间步协调各模块间的影响函数执行。
    按照依赖关系顺序调用各模块的影响函数，确保数据流正确。
    
    执行顺序：
        1. ClimateSystem: 计算增强后的气候影响度
        2. Map: 应用气候对运河的破坏
        3. TransportEconomy: 应用通航能力对价格和成本的影响
        4. Population: 应用气候和满意度对出生率的影响
        5. Resident: 在居民行为阶段单独处理健康影响
    
    依赖关系图：
        Climate -> Map -> TransportEconomy
        Climate -> Population
        Satisfaction -> Population
        Job/Income/Satisfaction -> Resident
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化影响函数管理器
        
        Args:
            logger: 日志记录器（可选）
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # 定义模块执行顺序（可通过配置文件覆盖）
        self.execution_order = [
            ('climate', 'climate_impact'),
            ('map', 'canal_condition'),
            ('transport_economy', 'river_price'),
            ('transport_economy', 'maintenance_cost'),
            ('population', 'birth_rate'),
        ]
    
    def build_global_context(self, simulator_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建全局 context 字典
        
        从 simulator 的当前状态中提取所有影响函数可能需要的变量。
        
        Args:
            simulator_state: 包含 simulator 当前状态的字典，必须包含：
                - time, map, population, transport_economy, climate, government, rebellion
                - gdp, average_satisfaction, basic_living_cost 等
        
        Returns:
            包含所有全局变量的 context 字典
        """
        # 从 simulator_state 提取必要的对象和变量
        time = simulator_state['time']
        map_obj = simulator_state['map']
        population = simulator_state['population']
        transport_economy = simulator_state['transport_economy']
        climate = simulator_state['climate']
        government = simulator_state.get('government')
        rebellion = simulator_state.get('rebellion')
        
        # 计算当前状态
        current_year = time.current_time
        start_year = time.start_time
        climate_impact = climate.get_current_impact(current_year, start_year)
        
        # 构建全局 context
        context = {
            # 时间相关
            'current_year': current_year,
            'start_year': start_year,
            
            # 核心对象
            'population': population,
            'map': map_obj,
            'transport_economy': transport_economy,
            'climate': climate,
            'government': government,
            'rebellion': rebellion,
            
            # 经济指标
            'gdp': simulator_state.get('gdp', 0.0),
            'gdp_growth_rate': simulator_state.get('gdp_growth_rate', 0.0),
            'tax_rate': government.get_tax_rate() if government else 0.15,
            'government_budget': government.get_budget() if government else 0.0,
            
            # 人口与社会
            'population_size': population.get_population(),
            'satisfaction': simulator_state.get('average_satisfaction', 50.0),
            'average_satisfaction': simulator_state.get('average_satisfaction', 50.0),
            'current_birth_rate': population.birth_rate,
            
            # 环境与资源
            'climate_impact': climate_impact,
            'raw_impact': climate_impact,  # 用于气候放大器
            'navigability': map_obj.get_navigability(),
            'river_price': transport_economy.river_price,
            
            # 运输经济
            'transport_cost': transport_economy.transport_cost,
            'maintenance_cost_base': transport_economy.maintenance_cost_base,
            
            # 其他
            'basic_living_cost': simulator_state.get('basic_living_cost', 8.0),
            'at_war': simulator_state.get('rebellion_records', 0) > 0,
            
            # 历史数据（如果需要）
            'climate_data': climate.climate_data if hasattr(climate, 'climate_data') else None,
        }
        
        return context
    
    def apply_all_influences(self, simulator_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行所有模块的影响函数
        
        按照预定义的顺序依次调用各模块的影响函数，并在每次调用后
        更新 context 中的相关值，确保后续模块能访问到最新状态。
        
        Args:
            simulator_state: simulator 当前状态字典
        
        Returns:
            更新后的 context 字典，包含所有影响函数执行后的最新值
        """
        # 构建初始 context
        context = self.build_global_context(simulator_state)
        
        self.logger.debug("开始应用影响函数...")
        
        # 按顺序执行各模块的影响函数
        for module_name, target_name in self.execution_order:
            self._apply_module_influence(module_name, target_name, context, simulator_state)
        
        self.logger.debug("所有影响函数执行完成")
        
        return context
    
    def _apply_module_influence(
        self, 
        module_name: str, 
        target_name: str, 
        context: Dict[str, Any],
        simulator_state: Dict[str, Any]
    ) -> None:
        """
        应用单个模块的影响函数
        
        Args:
            module_name: 模块名称（'climate', 'map', 'transport_economy', 'population'）
            target_name: 目标名称（如 'climate_impact', 'canal_condition'）
            context: 全局 context 字典
            simulator_state: simulator 状态字典
        """
        # 获取模块对象
        module = simulator_state.get(module_name)
        if not module:
            self.logger.warning(f"模块 {module_name} 不存在，跳过")
            return
        
        # 检查模块是否有影响函数注册表
        if not hasattr(module, '_influence_registry') or not module._influence_registry:
            self.logger.debug(f"模块 {module_name} 没有影响函数，跳过")
            return
        
        # 应用影响函数
        try:
            module.apply_influences(target_name, context)
            
            # 更新 context 中的相关值（确保后续模块能访问最新状态）
            self._update_context_after_influence(module_name, target_name, context, module)
            
        except Exception as e:
            self.logger.error(f"应用 {module_name}.{target_name} 影响函数时出错: {e}", exc_info=True)
    
    def _update_context_after_influence(
        self,
        module_name: str,
        target_name: str,
        context: Dict[str, Any],
        module: Any
    ) -> None:
        """
        在影响函数执行后更新 context 中的值
        
        Args:
            module_name: 模块名称
            target_name: 目标名称
            context: 全局 context 字典
            module: 模块对象
        """
        # 根据不同的目标更新对应的 context 值
        if target_name == 'climate_impact' and module_name == 'climate':
            # 更新气候影响度
            current_year = context['current_year']
            start_year = context['start_year']
            context['climate_impact'] = module.get_current_impact(current_year, start_year)
            self.logger.debug(f"气候影响度（增强后）: {context['climate_impact']:.3f}")
            
        elif target_name == 'canal_condition' and module_name == 'map':
            # 更新通航能力
            context['navigability'] = module.get_navigability()
            self.logger.debug(f"通航能力（受气候影响后）: {context['navigability']:.3f}")
            
        elif target_name == 'river_price' and module_name == 'transport_economy':
            # 更新河运价格
            context['river_price'] = module.river_price
            self.logger.debug(f"河运价格（受通航能力影响后）: {context['river_price']:.2f}")
            
        elif target_name == 'maintenance_cost' and module_name == 'transport_economy':
            # 维护成本在 context['result'] 中，不需要更新到顶层
            self.logger.debug(f"维护成本已计算")
            
        elif target_name == 'birth_rate' and module_name == 'population':
            # 更新出生率
            context['current_birth_rate'] = module.birth_rate
            self.logger.debug(f"出生率（受影响后）: {module.birth_rate:.4f}")
    
    def apply_resident_health_influences(
        self,
        resident: Any,
        global_context: Dict[str, Any],
        basic_living_cost: float
    ) -> None:
        """
        应用单个居民的健康影响函数
        
        为每个居民构建个性化的 context，并应用健康相关的影响函数。
        应在居民状态更新前调用。
        
        Args:
            resident: 居民对象
            global_context: 全局 context 字典
            basic_living_cost: 基本生活成本
        """
        # 检查居民是否有影响函数注册表
        if not hasattr(resident, '_influence_registry') or not resident._influence_registry:
            return
        
        # 构建居民专属 context（继承全局 context）
        resident_context = {
            **global_context,  # 继承全局 context
            'resident': resident,
            'job': resident.job,
            'income': resident.income,
            'satisfaction': resident.satisfaction,
            'health_index': resident.health_index,
            'basic_living_cost': basic_living_cost,
        }
        
        try:
            # 应用健康影响函数
            resident.apply_influences('health_index', resident_context)
        except Exception as e:
            self.logger.error(
                f"应用居民 {resident.resident_id} 健康影响函数时出错: {e}",
                exc_info=True
            )
    
    def set_execution_order(self, order: List[tuple]) -> None:
        """
        设置模块影响函数的执行顺序
        
        Args:
            order: 执行顺序列表，每个元素为 (module_name, target_name) 元组
        
        Example:
            manager.set_execution_order([
                ('climate', 'climate_impact'),
                ('map', 'canal_condition'),
                ('population', 'birth_rate'),
            ])
        """
        self.execution_order = order
        self.logger.info(f"影响函数执行顺序已更新: {len(order)} 个步骤")
