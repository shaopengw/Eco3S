"""时间插件实现"""
from typing import Dict, Any
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.time import Time


class DefaultTimePlugin(Time, BasePlugin):
    """
    默认时间插件 - 直接继承 Time 业务类 + BasePlugin 生命周期
    """

    def __init__(self, start_time: int = 1650,
                 total_steps: int = 10):
        """
        初始化时间插件

        Args:
            start_time: 起始时间
            total_steps: 总时间步数
        """
        BasePlugin.__init__(self)
        Time.__init__(self, start_time, total_steps)

        # 保存参数用于 init() 阶段根据配置覆盖
        self._start_time_param = start_time
        self._total_steps_param = total_steps

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 从配置中读取时间参数，如果没有则使用构造函数的默认值
        start_time = self.config.get('simulation', {}).get('start_year', self._start_time_param)
        total_steps = self.config.get('simulation', {}).get('total_years', self._total_steps_param)

        # 重新初始化 Time 业务状态
        Time.__init__(self, start_time=start_time, total_steps=total_steps)

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultTimePlugin 正在加载 (start={self.start_time}, steps={self.total_steps})")

        # 订阅事件
        self.subscribe_event(PluginEvent.SIMULATION_START, self._on_simulation_start)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultTimePlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.SIMULATION_START, self._on_simulation_start)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultTime",
            "version": "1.0.0",
            "description": "默认时间系统插件（直接实现 ITime）",
            "author": "AgentWorld Team",
            "dependencies": []
        }

    def step(self) -> None:
        """推进一个时间步（重写以发布事件）"""
        old_time = self.current_time
        Time.step(self)

        # 发布时间推进事件
        self.publish_event(PluginEvent.TIME_ADVANCED, {
            'old_time': old_time,
            'new_time': self.current_time
        })

    # ===== 内部方法 =====

    def _on_simulation_start(self, data: Dict[str, Any]) -> None:
        """模拟开始时的处理"""
        self.logger.info("收到 simulation_start 事件")
