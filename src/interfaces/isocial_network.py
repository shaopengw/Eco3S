"""
社交网络抽象接口
定义社交网络系统的核心功能接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional


class IHeterogeneousGraph(ABC):
    """
    异质图抽象基类
    使用 networkx 构建异质图，支持多类型节点和边
    """

    @abstractmethod
    def __init__(self):
        """初始化异质图"""
        pass

    @abstractmethod
    def add_node(self, node_id: int, node_type: str) -> None:
        """
        添加节点，并指定节点类型
        
        Args:
            node_id: 节点ID
            node_type: 节点类型
            
        Raises:
            ValueError: 如果节点已存在
        """
        pass

    @abstractmethod
    def add_edge(self, node1_id: int, node2_id: int, edge_type: str) -> None:
        """
        添加边，并指定边类型
        
        Args:
            node1_id: 节点1的ID
            node2_id: 节点2的ID
            edge_type: 边类型
            
        Raises:
            ValueError: 如果节点不存在
        """
        pass

    @abstractmethod
    def get_neighbors(self, node_id: int, edge_type: Optional[str] = None) -> List[int]:
        """
        获取某个节点的邻居，可以过滤边类型
        
        Args:
            node_id: 节点ID
            edge_type: 边类型，如果为None则返回所有邻居
            
        Returns:
            List[int]: 邻居节点ID列表
            
        Raises:
            ValueError: 如果节点不存在
        """
        pass

    @abstractmethod
    def remove_node(self, node_id: int) -> None:
        """
        从异质图中移除节点
        
        Args:
            node_id: 节点ID
        """
        pass

    @abstractmethod
    def visualize(self) -> None:
        """
        可视化异质图，使用不同颜色显示不同类型的边
        """
        pass


class IHypergraph(ABC):
    """
    超图抽象基类
    支持多节点关系的超图结构
    """

    @abstractmethod
    def __init__(self):
        """初始化一个空的超图"""
        pass

    @abstractmethod
    def add_node(self, node: Any) -> None:
        """
        向超图中添加一个节点
        
        Args:
            node: 要添加的节点
        """
        pass

    @abstractmethod
    def add_edge(self, edge: Any) -> None:
        """
        向超图中添加一条边
        
        Args:
            edge: 要添加的边
        """
        pass

    @abstractmethod
    def add_hyperedge(self, group_id: str, members: List[Any]) -> None:
        """
        向超图中添加关联关系
        
        Args:
            group_id: 组/超边的唯一标识符
            members: 包含在超边中的成员列表
        """
        pass

    @abstractmethod
    def remove_hyperedge_node(self, group_id: str, member: Any) -> None:
        """
        从超图中移除一个关联关系
        
        Args:
            group_id: 组ID
            member: 成员
        """
        pass

    @abstractmethod
    def get_nodes(self) -> List[Any]:
        """
        获取超图中的所有节点
        
        Returns:
            List[Any]: 超图中的所有节点
        """
        pass

    @abstractmethod
    def get_hyperedges(self) -> List[Any]:
        """
        获取超图中的所有超边
        
        Returns:
            List[Any]: 超图中的所有超边
        """
        pass

    @abstractmethod
    def get_neighbors(self, node: Any) -> List[Any]:
        """
        获取某个节点的邻居
        
        Args:
            node: 节点
            
        Returns:
            List[Any]: 邻居节点列表
        """
        pass

    @abstractmethod
    def get_hyperedge_nodes(self, hyperedge_id: str) -> List[Any]:
        """
        获取指定超边中包含的节点
        
        Args:
            hyperedge_id: 超边的唯一标识符
            
        Returns:
            List[Any]: 包含在超边中的节点列表
        """
        pass

    @abstractmethod
    def get_node_hyperedges(self, node: Any) -> List[Any]:
        """
        获取包含指定节点的所有超边
        
        Args:
            node: 节点
            
        Returns:
            List[Any]: 包含该节点的所有超边的列表
        """
        pass

    @abstractmethod
    def remove_node(self, node: Any) -> None:
        """
        从超图中移除一个节点
        
        Args:
            node: 要移除的节点
        """
        pass

    @abstractmethod
    def remove_hyperedge(self, hyperedge_id: str) -> None:
        """
        从超图中移除一个超边
        
        Args:
            hyperedge_id: 要移除的超边的唯一标识符
        """
        pass

    @abstractmethod
    def visualize(self) -> None:
        """可视化超图"""
        pass


class ISocialNetwork(ABC):
    """
    社交网络抽象基类
    结合异质图和超图，构建社交网络
    """

    @abstractmethod
    def __init__(self):
        """初始化社交网络"""
        pass

    @abstractmethod
    def add_resident(self, resident_id: int, node_type: str) -> None:
        """
        添加居民到异质图中
        
        Args:
            resident_id: 居民ID
            node_type: 节点类型
        """
        pass

    @abstractmethod
    def add_relation(self, resident1_id: int, resident2_id: int, relation_type: str) -> None:
        """
        添加居民之间的关系到异质图中
        
        Args:
            resident1_id: 居民1的ID
            resident2_id: 居民2的ID
            relation_type: 关系类型
        """
        pass

    @abstractmethod
    def add_group(self, group_id: str, members: List[int]) -> None:
        """
        添加居民群体到超图中
        
        Args:
            group_id: 群组ID
            members: 成员ID列表
        """
        pass

    @abstractmethod
    async def spread_information(
        self, 
        resident_id: int, 
        message: str, 
        relation_type: str, 
        current_depth: int = 1, 
        max_depth: int = 3
    ) -> None:
        """
        在异质图中传播信息，支持并发执行
        
        Args:
            resident_id: 发送信息的居民ID
            message: 信息内容
            relation_type: 关系类型
            current_depth: 当前传播层数
            max_depth: 最大传播层数
            
        Note:
            - 检查对话量限制
            - 随机选择30%-50%的邻居节点进行传播
        """
        pass

    @abstractmethod
    async def spread_information_in_group(
        self, 
        group_id: str, 
        message: str, 
        current_depth: int = 1, 
        max_depth: int = 3
    ) -> None:
        """
        在超图的群组中并发传播信息
        
        Args:
            group_id: 群组ID
            message: 信息内容
            current_depth: 当前传播层数
            max_depth: 最大传播层数
            
        Note:
            - 检查对话量限制
            - 随机选择30%-50%的群组成员进行传播
        """
        pass

    @abstractmethod
    async def spread_speech_in_network(
        self, 
        resident_id: int, 
        speech: str, 
        relation_type: str, 
        current_depth: int = 1, 
        max_depth: int = 3
    ) -> None:
        """
        在社交网络中递归传播发言
        
        Args:
            resident_id: 发送信息的居民ID
            speech: 发言内容
            relation_type: 关系类型
            current_depth: 当前传播层数
            max_depth: 最大传播层数
        """
        pass

    @abstractmethod
    async def communicate_resident_to_resident(
        self,
        sender_id: int,
        receiver_id: int,
        message: str,
    ) -> Optional[Any]:
        """指定居民与指定居民一对一沟通。

        Args:
            sender_id: 发送方居民ID
            receiver_id: 接收方居民ID
            message: 消息内容

        Returns:
            Optional[Any]: 接收方可选的回应（实现通常沿用 Resident.receive_information 返回结构）

        Note:
            - 需要遵守 dialogue_count/MAX_DIALOGUES_PER_STEP 的对话量限制
            - 若接收方不存在或已达对话上限，返回 None
        """
        pass

    @abstractmethod
    async def communicate_resident_to_residents(
        self,
        sender_id: int,
        receiver_ids: List[int],
        message: str,
    ) -> Dict[int, Optional[Any]]:
        """指定居民一对多沟通。

        Returns:
            Dict[int, Optional[Any]]: 每个接收方对应的可选回应；不可达/不存在/被限流的为 None
        """
        pass

    @abstractmethod
    async def communicate_user_to_resident(
        self,
        user_id: str,
        resident_id: int,
        message: str,
    ) -> Optional[Any]:
        """用户与指定居民沟通。"""
        pass

    @abstractmethod
    async def communicate_user_to_residents(
        self,
        user_id: str,
        resident_ids: List[int],
        message: str,
    ) -> Dict[int, Optional[Any]]:
        """用户与指定居民列表沟通。"""
        pass

    @abstractmethod
    def get_resident_groups(self, resident_id: int, group_type: str) -> List[str]:
        """
        获取居民所属的特定类型群组
        
        Args:
            resident_id: 居民ID
            group_type: 群组类型（family或hometown）
            
        Returns:
            List[str]: 群组ID列表
        """
        pass

    @abstractmethod
    def visualize(self) -> None:
        """
        可视化社交网络，同时显示异质图和超图的可视化图片
        
        Note:
            - 保存图片到指定目录
            - 针对大规模网络进行优化
        """
        pass

    @abstractmethod
    def initialize_network(self, residents: Dict[int, Any], towns: Any) -> None:
        """
        初始化社交网络，建立居民之间的关系
        
        Args:
            residents: 居民字典
            towns: 城镇
            
        Note:
            - 使用幂律分布建立朋友和同事关系
            - 为每个城镇创建同乡关系超边
        """
        pass

    @abstractmethod
    def add_new_residents(self, new_residents: Dict[int, Any]) -> None:
        """
        将新生成的居民添加到现有的社交网络中
        
        Args:
            new_residents: 新居民字典 {resident_id: resident}
        """
        pass

    @abstractmethod
    def calculate_speech_probability(self, node_id: int) -> float:
        """
        计算节点的发言概率
        
        Args:
            node_id: 节点ID
            
        Returns:
            float: 发言概率值(0-1)
        """
        pass

    @abstractmethod
    def get_node_degree(self, node_id: int) -> float:
        """
        获取指定节点的度数
        
        Args:
            node_id: 节点ID
            
        Returns:
            float: 节点的度数
            
        Raises:
            ValueError: 如果节点不存在
        """
        pass

    @abstractmethod
    def get_max_degree(self) -> float:
        """
        获取图中的最大度数
        
        Returns:
            float: 最大度数
            
        Raises:
            ValueError: 如果图为空
        """
        pass

    @abstractmethod
    def plot_degree_distribution(self) -> None:
        """
        绘制异质图中节点度分布的可视化表格
        
        Note:
            横坐标为度数，纵坐标为人数
            保存高清图片到指定目录
        """
        pass

    @abstractmethod
    def reset_dialogue_count(self) -> None:
        """重置当前时间步的对话计数器"""
        pass

    @abstractmethod
    def update_network_edges(self, update_ratio: float = 0.2) -> None:
        """
        随机更新社交网络中的部分边
        
        Args:
            update_ratio: 每次更新的边的比例（0-1之间），默认0.2
            
        Note:
            - 随机删除指定比例的边
            - 生成相同数量的新边
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        将社交网络状态转换为可序列化的字典
        
        Returns:
            Dict[str, Any]: 包含异质图和超图数据的字典
        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any], residents: Dict[int, Any]) -> 'ISocialNetwork':
        """
        从字典数据恢复社交网络
        
        Args:
            data: 包含网络数据的字典
            residents: 居民字典
            
        Returns:
            ISocialNetwork: 恢复的社交网络实例
        """
        pass

    # 属性定义（供实现类参考）
    @property
    @abstractmethod
    def hetero_graph(self) -> IHeterogeneousGraph:
        """异质图对象"""
        pass

    @property
    @abstractmethod
    def hyper_graph(self) -> IHypergraph:
        """超图对象"""
        pass

    @property
    @abstractmethod
    def residents(self) -> Dict[int, Any]:
        """居民字典"""
        pass

    @property
    @abstractmethod
    def dialogue_count(self) -> int:
        """当前时间步的对话计数"""
        pass

    @property
    @abstractmethod
    def MAX_DIALOGUES_PER_STEP(self) -> int:
        """每个时间步最大对话量"""
        pass
