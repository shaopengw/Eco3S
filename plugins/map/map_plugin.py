"""地图插件实现"""

from typing import Dict, Any, Optional
from src.influences import InfluenceRegistry
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.map import Map


class DefaultMapPlugin(Map, BasePlugin):
    """
    默认地图插件 - 直接继承 Map 业务类 + BasePlugin 生命周期
    """

    def __init__(
        self,
        width: int = 100,
        height: int = 100,
        data_file: str = 'config/default/towns_data.json',
        influence_registry: Optional[InfluenceRegistry] = None,
    ):
        BasePlugin.__init__(self)

        # 保存参数用于 init() 阶段根据配置覆盖
        self._width_param = width
        self._height_param = height
        self._data_file_param = data_file
        self._influence_registry_param = influence_registry
        self._initialized = False

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 允许从运行配置覆盖地图参数
        sim_cfg = (context.config or {}).get('simulation', {})
        if isinstance(sim_cfg, dict):
            if isinstance(sim_cfg.get('map_width'), int):
                self._width_param = int(sim_cfg['map_width'])
            if isinstance(sim_cfg.get('map_height'), int):
                self._height_param = int(sim_cfg['map_height'])

        data_cfg = (context.config or {}).get('data', {})
        if isinstance(data_cfg, dict):
            towns_path = data_cfg.get('towns_data_path')
            if isinstance(towns_path, str) and towns_path.strip():
                self._data_file_param = towns_path.strip()

        # 初始化 Map 业务状态
        Map.__init__(
            self,
            width=self._width_param,
            height=self._height_param,
            data_file=self._data_file_param,
            influence_registry=self._influence_registry_param,
        )
        self._initialized = True

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info(f"DefaultMapPlugin 正在加载 ({self.width}x{self.height})")

        # 订阅事件
        self.subscribe_event(PluginEvent.SIMULATION_START, self._on_simulation_start)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultMapPlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.SIMULATION_START, self._on_simulation_start)

        self._initialized = False

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultMap",
            "version": "1.0.0",
            "description": "默认地图实现插件（直接实现 IMap）",
            "author": "AgentWorld Team",
            "dependencies": []
        }

    def initialize_map(self) -> None:
        """初始化地图（重写以发布事件）"""
        Map.initialize_map(self)

        if self.context is not None:
            self.publish_event(PluginEvent.MAP_INITIALIZED, {
                'width': self.width,
                'height': self.height
            })

    # ===== 内部方法 =====

    def _on_simulation_start(self, data: Dict[str, Any]) -> None:
        """模拟开始时的处理"""
        self.logger.info("收到 simulation_start 事件")
