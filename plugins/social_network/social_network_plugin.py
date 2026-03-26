"""
社交网络插件实现 - 包装器模式
"""
from typing import Any, Dict

from src.plugins import ISocialNetworkPlugin, PluginContext
from src.environment.social_network import SocialNetwork


class DefaultSocialNetworkPlugin(ISocialNetworkPlugin):
    """
    默认社交网络插件 - 包装现有 SocialNetwork 类
    """
    
    def __init__(self):
        """
        初始化社交网络插件
        """
        super().__init__()
        # 业务能力由 service 提供
        self._service = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建业务实现（service）
        self._service = SocialNetwork()
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        self.logger.info("DefaultSocialNetworkPlugin 正在加载")
        
        # 订阅事件
        self.context.event_bus.subscribe('resident_groups_initialized', self._on_residents_initialized)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultSocialNetworkPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('resident_groups_initialized', self._on_residents_initialized)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultSocialNetwork",
            "version": "1.0.0",
            "description": "默认社交网络插件（包装 SocialNetwork 类）",
            "author": "AgentWorld Team",
            "dependencies": ["population"]
        }

    def initialize_network(self, residents, towns):
        """初始化社交网络

        该方法在插件层保留，以便发布系统事件；其余业务方法由 ServicePlugin 自动转发。
        """
        self.service.initialize_network(residents, towns)

        if self.context is not None:
            self.context.event_bus.publish('social_network_initialized', {
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
