import random
import hypernetx as hnx
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, List, Set, Tuple

class HeterogeneousGraph:
    """
    使用 networkx 构建异质图，支持多类型节点和边。
    """
    def __init__(self):
        self.graph = nx.Graph()

    def add_node(self, node_id, node_type):
        """
        添加节点，并指定节点类型。
        """
        if node_id in self.graph.nodes:
            raise ValueError(f"节点 {node_id} 已存在！")
        self.graph.add_node(node_id, type=node_type)

    def add_edge(self, node1_id, node2_id, edge_type):
        """
        添加边，并指定边类型。
        """
        if node1_id not in self.graph.nodes or node2_id not in self.graph.nodes:
            raise ValueError("节点不存在！")
        self.graph.add_edge(node1_id, node2_id, type=edge_type)

    def get_neighbors(self, node_id, edge_type=None):
        """
        获取某个节点的邻居，可以过滤边类型。
        """
        if node_id not in self.graph.nodes:
            raise ValueError(f"节点 {node_id} 不存在！")
        neighbors = []
        for neighbor in self.graph.neighbors(node_id):
            if edge_type is None or self.graph[node_id][neighbor]["type"] == edge_type:
                neighbors.append(neighbor)
        return neighbors

    def spread_information(self, node_id, message, edge_type=None):
        """
        模拟信息在某种边类型下的传播。
        """
        neighbors = self.get_neighbors(node_id, edge_type)
        for neighbor in neighbors:
            print(f"节点 {neighbor} 收到了来自节点 {node_id} 的信息：{message}")

    def visualize(self):
        """
        可视化异质图。
        """
        pos = nx.spring_layout(self.graph)
        node_colors = [self.graph.nodes[node]["type"] == "person" and "lightblue" or "lightgreen" for node in self.graph.nodes]
        nx.draw(self.graph, pos, with_labels=True, node_color=node_colors, node_size=500, font_size=10)
        plt.show()

class Hypergraph:
    def __init__(self):
        """
        初始化一个空的超图。
        """
        self.hypergraph = hnx.Hypergraph()
        
    def add_node(self, node):
        """
        向超图中添加一个节点。

        :param node: 要添加的节点。
        """
        self.hypergraph.add_node(node)

    def add_edge(self, edge):
        """
        向超图中添加一条边。

        :param edge: 要添加的边。
        """
        self.hypergraph.add_edge(edge)

    def add_hyperedge(self, group_id, members):
        """
        向超图中添加关联关系。

        :param hyperedge_id: 超边的唯一标识符。
        :param nodes: 包含在超边中的节点列表。
        """
        incidences = [(group_id, member) for member in members] # 格式转换
        self.hypergraph.add_incidences_from(incidences)

    def get_nodes(self):
        """
        获取超图中的所有节点。

        :return: 超图中的所有节点。
        """
        return list(self.hypergraph.nodes)

    def get_hyperedges(self):
        """
        获取超图中的所有超边。

        :return: 超图中的所有超边。
        """
        return list(self.hypergraph.edges)

    def get_neighbors(self, node):
        """
        获取某个节点的邻居。
        """
        return list(self.hypergraph.neighbors(node))

    def get_hyperedge_nodes(self, hyperedge_id):
        """
        获取指定超边中包含的节点。

        :param hyperedge_id: 超边的唯一标识符。
        :return: 包含在超边中的节点列表。
        """
        return list(self.hypergraph.edges[hyperedge_id])

    def get_node_hyperedges(self, node):
        """
        获取包含指定节点的所有超边。

        :param node: 节点。
        :return: 包含该节点的所有超边的列表。
        """
        return list(self.hypergraph.nodes[node])

    def remove_node(self, node):
        """
        从超图中移除一个节点。

        :param node: 要移除的节点。
        """
        self.hypergraph.remove_nodes(node)

    def remove_hyperedge(self, hyperedge_id):
        """
        从超图中移除一个超边。

        :param hyperedge_id: 要移除的超边的唯一标识符。
        """
        self.hypergraph.remove_edges(hyperedge_id)
    
    def spread_information_in_group(self, edge_id, message):
        """
        模拟信息在某个超边中的传播。
        """
        members = self.get_hyperedge_nodes(edge_id)
        for member in members:
            # 这里需要补充信息传播的逻辑
            print(f"节点 {member} 在超边 {edge_id} 中收到了信息：{message}")

    def visualize(self):
        """
        可视化超图。
        """
        hnx.draw(self.hypergraph)
        plt.title("Hypergraph Visualization")
        plt.show()


class SocialNetwork:
    """
    结合异质图和超图，构建社交网络。
    """
    def __init__(self):
        self.hetero_graph = HeterogeneousGraph()
        self.hyper_graph = Hypergraph()

    def add_resident(self, resident_id, node_type):
        """
        添加居民到异质图中。
        """
        self.hetero_graph.add_node(resident_id, node_type)

    def add_relation(self, resident1_id, resident2_id, relation_type):
        """
        添加居民之间的关系到异质图中。
        """
        self.hetero_graph.add_edge(resident1_id, resident2_id, relation_type)

    def add_group(self, group_id, members):
        """
        添加居民群体到超图中。
        """
        self.hyper_graph.add_hyperedge(group_id, members)

    def spread_information(self, resident_id, message, relation_type=None):
        """
        模拟信息在某种关系下的传播。
        """
        self.hetero_graph.spread_information(resident_id, message, relation_type)

    def spread_information_in_group(self, group_id, message):
        """
        模拟信息在某个群体中的传播。
        """
        self.hyper_graph.spread_information_in_group(group_id, message)

    def visualize(self):
        """
        可视化社交网络，同时显示异质图和超图的可视化图片，并添加边框和间距。
        """
        # 创建一个包含两个子图的画布，并调整间距
        fig, axes = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw={'wspace': 0.3})

        # 可视化异质图
        ax1 = axes[0]
        pos = nx.spring_layout(self.hetero_graph.graph)
        node_colors = [self.hetero_graph.graph.nodes[node]["type"] == "person" and "lightblue" or "lightgreen" for node in self.hetero_graph.graph.nodes]
        nx.draw(self.hetero_graph.graph, pos, with_labels=True, node_color=node_colors, node_size=500, font_size=10, ax=ax1)
        ax1.set_title("Heterogeneous Graph", pad=20)  # 增加标题与图的间距

        # 可视化超图
        ax2 = axes[1]
        hnx.draw(self.hyper_graph.hypergraph, ax=ax2)
        ax2.set_title("Hypergraph", pad=20)  # 增加标题与图的间距

        plt.show()