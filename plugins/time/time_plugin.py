"""
时间插件实现 - 包装器模式
"""
from typing import Dict, Any
from src.plugins import ITimePlugin, PluginContext
from src.environment.time import Time


class DefaultTimePlugin(ITimePlugin):
    """
    默认时间插件 - 包装现有 Time 类
    """
    
    def __init__(self, start_time: int = 1650,
                 total_steps: int = 10):
        """
        初始化时间插件
        
        Args:
            start_time: 起始时间
            total_steps: 总时间步数
        """
        super().__init__()
        
        # 保存参数
        self._start_time_param = start_time
        self._total_steps_param = total_steps
        self._time = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 从配置中读取时间参数，如果没有则使用构造函数的默认值
        start_time = self.config.get('simulation', {}).get('start_year', self._start_time_param)
        total_steps = self.config.get('simulation', {}).get('total_years', self._total_steps_param)
        
        # 创建原始 Time 实例
        self._time = Time(start_time=start_time, total_steps=total_steps)
        self._service = self._time
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultTimePlugin 正在加载 (start={self._time.start_time}, steps={self._time.total_steps})")
        
        # 订阅事件
        self.context.event_bus.subscribe('simulation_start', self._on_simulation_start)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultTimePlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('simulation_start', self._on_simulation_start)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultTime",
            "version": "1.0.0",
            "description": "默认时间系统插件（包装 Time 类）",
            "author": "AgentWorld Team",
            "dependencies": []
        }
    
    def step(self) -> None:
        """推进一个时间步"""
        old_time = self._time.current_time
        self._time.step()
        
        # 发布时间推进事件
        self.context.event_bus.publish('time_advanced', {
            'old_time': old_time,
            'new_time': self._time.current_time
        })
    
    # ===== 内部方法 =====
    
    def _on_simulation_start(self, data: Dict[str, Any]) -> None:
        """模拟开始时的处理"""
        self.logger.info("收到 simulation_start 事件")
