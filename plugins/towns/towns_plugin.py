"""城镇插件实现"""
from typing import Dict, Any, Optional
from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.towns import Towns


class DefaultTownsPlugin(Towns, BasePlugin):
    """
    默认城镇插件 - 直接继承 Towns 业务类 + BasePlugin 生命周期
    """

    def __init__(self, map=None,
                 initial_population: int = 10,
                 job_market_config_path: Optional[str] = None):
        BasePlugin.__init__(self)

        # 保存参数
        self._map_param = map
        self._initial_population_param = initial_population
        self._job_market_config_path_param = job_market_config_path

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 允许从运行配置覆盖就业市场配置路径
        if self._job_market_config_path_param is None:
            data_cfg = (context.config or {}).get('data', {})
            if isinstance(data_cfg, dict):
                cfg_path = data_cfg.get('jobs_config_path')
                if isinstance(cfg_path, str) and cfg_path.strip():
                    self._job_market_config_path_param = cfg_path.strip()

        # 从插件上下文获取 map 实例（依赖项）
        if self._map_param is None and context.registry:
            map_plugin = context.registry.get_plugin('map')
            if map_plugin:
                self._map_param = map_plugin
                self.logger.info("从插件系统获取 map 依赖")
            else:
                self.logger.warning("无法获取 map 插件，将在 on_load 时重试")

        # 初始化 Towns 业务状态
        if self._map_param is not None:
            Towns.__init__(
                self,
                map=self._map_param,
                initial_population=self._initial_population_param,
                job_market_config_path=self._job_market_config_path_param
            )
        else:
            # 延迟初始化，等待依赖加载
            self.logger.info("Towns 插件延迟初始化，等待 map 依赖")

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        # 如果 Towns 实例还未创建，现在创建它
        if not hasattr(self, '_towns') or self._towns is None:
            if self.context.registry:
                map_plugin = self.context.registry.get_plugin('map')
                if map_plugin:
                    Towns.__init__(
                        self,
                        map=map_plugin,
                        initial_population=self._initial_population_param,
                        job_market_config_path=self._job_market_config_path_param
                    )
                    self.logger.info("Towns 实例在 on_load 阶段创建")
                else:
                    raise RuntimeError("无法加载 Towns 插件：依赖的 map 插件未找到")
            else:
                raise RuntimeError("无法加载 Towns 插件：PluginContext 缺少 registry")

        self.logger.info(f"DefaultTownsPlugin 正在加载 (towns_count={len(self.towns)})")

        # 订阅事件
        self.subscribe_event(PluginEvent.MAP_INITIALIZED, self._on_map_initialized)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultTownsPlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.MAP_INITIALIZED, self._on_map_initialized)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultTowns",
            "version": "1.0.0",
            "description": "默认城镇系统插件（直接实现 ITowns）",
            "author": "AgentWorld Team",
            "dependencies": ["map"]
        }

    def initialize_resident_groups(self, residents):
        """初始化居民组（重写以发布事件）"""
        Towns.initialize_resident_groups(self, residents)

        # 发布事件
        self.publish_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, {
            'towns_count': len(self.towns),
            'resident_count': len(residents) if residents is not None else 0,
        })

    # ===== 内部方法 =====

    def _on_map_initialized(self, data: Dict[str, Any]) -> None:
        """地图初始化时的处理"""
        self.logger.info("收到 map_initialized 事件")
