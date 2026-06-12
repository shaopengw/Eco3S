"""就业市场插件实现"""
from typing import Dict, Any
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.job_market import JobMarket


class DefaultJobMarketPlugin(JobMarket, BasePlugin):
    """
    默认就业市场插件 - 直接继承 JobMarket 业务类 + BasePlugin 生命周期
    """

    def __init__(self, town_type: str = "非沿河",
                 initial_jobs_count: int = 100,
                 config_path: str = None):
        BasePlugin.__init__(self)
        self._town_type_param = town_type
        self._initial_jobs_count_param = initial_jobs_count
        self._config_path_param = config_path

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 初始化 JobMarket 业务状态
        JobMarket.__init__(
            self,
            town_type=self._town_type_param,
            initial_jobs_count=self._initial_jobs_count_param,
            config_path=self._config_path_param
        )

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultJobMarketPlugin 正在加载 (town_type={self.town_type})")

        # 订阅事件
        self.subscribe_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, self._on_residents_initialized)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultJobMarketPlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, self._on_residents_initialized)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultJobMarket",
            "version": "1.0.0",
            "description": "默认就业市场插件（直接实现 IJobMarket）",
            "author": "AgentWorld Team",
            "dependencies": ["population", "towns"]
        }

    def hire(self, resident_id: str, job_type: str) -> bool:
        """雇佣居民（重写以发布事件）"""
        result = JobMarket.hire(self, resident_id, job_type)

        if result:
            # 发布雇佣事件
            self.publish_event(PluginEvent.RESIDENT_HIRED, {
                'resident_id': resident_id,
                'job_type': job_type
            })

        return result

    def fire(self, resident_id: str) -> bool:
        """解雇居民（重写以发布事件）"""
        result = JobMarket.fire(self, resident_id)

        if result:
            # 发布解雇事件
            self.publish_event(PluginEvent.RESIDENT_FIRED, {
                'resident_id': resident_id
            })

        return result

    # ===== 内部方法 =====

    def _on_residents_initialized(self, data: Dict[str, Any]) -> None:
        """居民初始化时的处理"""
        self.logger.info("收到 resident_groups_initialized 事件")
