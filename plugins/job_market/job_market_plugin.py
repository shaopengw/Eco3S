"""
就业市场插件实现 - 包装器模式
"""
from typing import Dict, Any
from src.plugins import IJobMarketPlugin, PluginContext
from src.environment.job_market import JobMarket


class DefaultJobMarketPlugin(IJobMarketPlugin):
    """
    默认就业市场插件 - 包装现有 JobMarket 类
    """
    
    def __init__(self, town_type: str = "非沿河",
                 initial_jobs_count: int = 100,
                 config_path: str = None):
        """
        初始化就业市场插件
        
        Args:
            town_type: 城镇类型（"沿河"或"非沿河"）
            initial_jobs_count: 初始工作总数
            config_path: 职业配置文件路径
        """
        super().__init__()
        
        # 保存参数
        self._town_type_param = town_type
        self._initial_jobs_count_param = initial_jobs_count
        self._config_path_param = config_path
        self._job_market = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建原始 JobMarket 实例
        self._job_market = JobMarket(
            town_type=self._town_type_param,
            initial_jobs_count=self._initial_jobs_count_param,
            config_path=self._config_path_param
        )
        self._service = self._job_market
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultJobMarketPlugin 正在加载 (town_type={self._job_market.town_type})")
        
        # 订阅事件
        self.context.event_bus.subscribe('resident_groups_initialized', self._on_residents_initialized)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultJobMarketPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('resident_groups_initialized', self._on_residents_initialized)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultJobMarket",
            "version": "1.0.0",
            "description": "默认就业市场插件（包装 JobMarket 类）",
            "author": "AgentWorld Team",
            "dependencies": ["population", "towns"]
        }
    
    def hire(self, resident_id: str, job_type: str) -> bool:
        """雇佣居民"""
        result = self._job_market.hire(resident_id, job_type)
        
        if result:
            # 发布雇佣事件
            self.context.event_bus.publish('resident_hired', {
                'resident_id': resident_id,
                'job_type': job_type
            })
        
        return result
    
    def fire(self, resident_id: str) -> bool:
        """解雇居民"""
        result = self._job_market.fire(resident_id)
        
        if result:
            # 发布解雇事件
            self.context.event_bus.publish('resident_fired', {
                'resident_id': resident_id
            })
        
        return result
    
    # ===== 内部方法 =====
    
    def _on_residents_initialized(self, data: Dict[str, Any]) -> None:
        """居民初始化时的处理"""
        self.logger.info("收到 resident_groups_initialized 事件")
