"""社交网络插件实现"""
from typing import Any, Dict

from src.plugins import BasePlugin, PluginContext, PluginEvent
from src.environment.social_network import SocialNetwork


class DefaultSocialNetworkPlugin(SocialNetwork, BasePlugin):
    """
    默认社交网络插件 - 直接继承 SocialNetwork 业务类 + BasePlugin 生命周期
    """

    def __init__(self):
        BasePlugin.__init__(self)
        # 不在这里调用 SocialNetwork.__init__，等 init() 中初始化

    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config

        # 初始化 SocialNetwork 业务状态
        SocialNetwork.__init__(self)

    # ===== BasePlugin 生命周期方法 =====

    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info("DefaultSocialNetworkPlugin 正在加载")

        # 订阅事件
        self.subscribe_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, self._on_residents_initialized)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultSocialNetworkPlugin 正在卸载")

        # 取消订阅
        self.unsubscribe_event(PluginEvent.RESIDENT_GROUPS_INITIALIZED, self._on_residents_initialized)

    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultSocialNetwork",
            "version": "1.0.0",
            "description": "默认社交网络插件（直接实现 ISocialNetwork）",
            "author": "AgentWorld Team",
            "dependencies": ["population"]
        }

    def initialize_network(self, residents, towns):
        """初始化社交网络（重写以发布事件）"""
        SocialNetwork.initialize_network(self, residents, towns)

        if self.context is not None:
            self.publish_event(PluginEvent.SOCIAL_NETWORK_INITIALIZED, {
                'network_type': 'small_world'
            })

    @classmethod
    def from_dict(cls, data, residents):
        """从字典创建业务实现"""
        return SocialNetwork.from_dict(data, residents)

    # ===== 内部方法 =====

    def _on_residents_initialized(self, data: Dict[str, Any]) -> None:
        """居民初始化时的处理"""
        self.logger.info("收到 resident_groups_initialized 事件")
