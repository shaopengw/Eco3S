import hypernetx as hnx
import matplotlib.pyplot as plt

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

    def add_hyperedge(self, incidences):
        """
        向超图中添加关联关系。

        :param hyperedge_id: 超边的唯一标识符。
        :param nodes: 包含在超边中的节点列表。
        """
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

# 示例用法
if __name__ == "__main__":
    hg = Hypergraph()

    # 添加超边
    hg.add_hyperedge([('e1','1',{"color": "red"}),('e1', '2',{"color": "red"}),('e2', '3',{"color": "red"})])
    hg.add_hyperedge([('e1','4',{"color": "blue"})])
    hg.add_hyperedge([('e3','1'), ('e3','2')])


    # 打印超图信息
    print("Nodes:", hg.get_nodes())
    print("Hyperedges:", hg.get_hyperedges())
    print("超边'e1'的节点:", hg.get_hyperedge_nodes('e1'))
    print("节点2的超边:", hg.get_node_hyperedges('2'))

    print("节点1的邻居：",hg.get_neighbors('1'))
    hg.visualize()

    # 移除节点和超边
    hg.remove_node('3')
    hg.remove_hyperedge('e3')

    # 打印更新后的超图信息
    print("Updated Nodes:", hg.get_nodes())
    print("Updated Hyperedges:", hg.get_hyperedges())