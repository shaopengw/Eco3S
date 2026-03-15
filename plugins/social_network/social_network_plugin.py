"""
社交网络插件实现 - 包装器模式
"""
from typing import Dict, Any, List
from src.plugins import ISocialNetworkPlugin, PluginContext
from src.interfaces import ISocialNetwork
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
        self._social_network = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 创建原始 SocialNetwork 实例
        self._social_network = SocialNetwork()
    
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
            "dependencies": ["default_population"]
        }
    
    # ===== ISocialNetwork 接口属性 - 代理到内部 SocialNetwork 实例 =====
    
    @property
    def hetero_graph(self):
        """获取异构图"""
        return self._social_network.hetero_graph
    
    @property
    def hyper_graph(self):
        """获取超图"""
        return self._social_network.hyper_graph
    
    @property
    def residents(self):
        """获取居民字典"""
        return self._social_network.residents
    
    @residents.setter
    def residents(self, value):
        """设置居民字典"""
        self._social_network.residents = value
    
    @property
    def dialogue_count(self):
        """获取对话计数"""
        return self._social_network.dialogue_count
    
    @dialogue_count.setter
    def dialogue_count(self, value):
        """设置对话计数"""
        self._social_network.dialogue_count = value
    
    @property
    def MAX_DIALOGUES_PER_STEP(self):
        """获取每步最大对话数"""
        return self._social_network.MAX_DIALOGUES_PER_STEP
    
    # ===== ISocialNetwork 接口方法 - 代理到内部 SocialNetwork 实例 =====
    
    def initialize_network(self, residents, towns):
        """初始化社交网络"""
        self._social_network.initialize_network(residents, towns)
        
        # 发布事件
        self.context.event_bus.publish('social_network_initialized', {
            'network_type': 'small_world'
        })
    
    def add_node(self, node_id, node_type):
        """添加节点"""
        self._social_network.add_node(node_id, node_type)
    
    def add_edge(self, node1_id, node2_id, edge_type):
        """添加边"""
        self._social_network.add_edge(node1_id, node2_id, edge_type)
    
    def get_neighbors(self, node_id, edge_type=None):
        """获取邻居节点"""
        return self._social_network.get_neighbors(node_id, edge_type)
    
    def remove_node(self, node_id):
        """移除节点"""
        self._social_network.remove_node(node_id)
    
    def visualize(self):
        """可视化社交网络"""
        self._social_network.visualize()
    
    def plot_degree_distribution(self):
        """绘制度分布"""
        self._social_network.plot_degree_distribution()
    
    def get_graph(self):
        """获取图对象"""
        return self._social_network.get_graph()
    
    def get_community_structure(self):
        """获取社区结构"""
        return self._social_network.get_community_structure()
    
    def add_resident(self, resident_id, node_type):
        """添加居民"""
        return self._social_network.add_resident(resident_id, node_type)
    
    def add_relation(self, resident1_id, resident2_id, relation_type):
        """添加关系"""
        return self._social_network.add_relation(resident1_id, resident2_id, relation_type)
    
    def add_group(self, group_id, members):
        """添加组"""
        return self._social_network.add_group(group_id, members)
    
    async def spread_information(self, resident_id: int, message: str, relation_type: str, current_depth: int = 1, max_depth: int = 3):
        """传播信息"""
        return await self._social_network.spread_information(resident_id, message, relation_type, current_depth, max_depth)
    
    async def spread_information_in_group(self, resident_id: int, message: str, group_type: str):
        """在组内传播信息"""
        return await self._social_network.spread_information_in_group(resident_id, message, group_type)
    
    async def spread_speech_in_network(self, resident_id: int, speech: str, relation_type: str, current_depth: int = 1, max_depth: int = 3):
        """在网络中传播言论"""
        return await self._social_network.spread_speech_in_network(resident_id, speech, relation_type, current_depth, max_depth)
    
    def get_resident_groups(self, resident_id: int, group_type: str):
        """获取居民的组"""
        return self._social_network.get_resident_groups(resident_id, group_type)
    
    def add_new_residents(self, new_residents: dict):
        """添加新居民"""
        return self._social_network.add_new_residents(new_residents)
    
    def calculate_speech_probability(self, node_id):
        """计算言论概率"""
        return self._social_network.calculate_speech_probability(node_id)
    
    def get_node_degree(self, node_id: int):
        """获取节点度"""
        return self._social_network.get_node_degree(node_id)
    
    def get_max_degree(self):
        """获取最大度"""
        return self._social_network.get_max_degree()
    
    def reset_dialogue_count(self):
        """重置对话计数"""
        return self._social_network.reset_dialogue_count()
    
    def update_network_edges(self, update_ratio=0.2):
        """更新网络边"""
        return self._social_network.update_network_edges(update_ratio)
    
    def to_dict(self):
        """转换为字典"""
        return self._social_network.to_dict()
    
    @classmethod
    def from_dict(cls, data, residents):
        """从字典创建"""
        return SocialNetwork.from_dict(data, residents)
    
    # ===== 内部方法 =====
    
    def _on_residents_initialized(self, data: Dict[str, Any]) -> None:
        """居民初始化时的处理"""
        self.logger.info("收到 resident_groups_initialized 事件")
