import random
import os
import hypernetx as hnx
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Set, Tuple
from datetime import datetime

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
        可视化异质图，使用不同颜色显示不同类型的边。
        """
        pos = nx.spring_layout(self.graph)
        
        # 绘制节点
        node_colors = [self.graph.nodes[node]["type"] == "person" and "lightblue" or "lightgreen" for node in self.graph.nodes]
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, node_size=300)
        nx.draw_networkx_labels(self.graph, pos, font_size=8)
        
        # 为不同类型的边使用不同颜色
        edge_colors = {
            "friend": "red",
            "colleague": "blue",
        }
        
        # 分别绘制不同类型的边
        for edge_type, color in edge_colors.items():
            edge_list = [(u, v) for (u, v, d) in self.graph.edges(data=True) if d["type"] == edge_type]
            if edge_list:  # 只有当存在这种类型的边时才绘制
                nx.draw_networkx_edges(self.graph, pos, edgelist=edge_list, edge_color=color, width=1.0)
        
        # 添加图例
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color=color, label=edge_type)
            for edge_type, color in edge_colors.items()
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        
        plt.axis('off')

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
        self.residents = {}  # 添加residents字典

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

    def spread_information(self, resident_id: int, message: str, relation_type: str):
        """
        在异质图中传播信息
        :param resident_id: 发送信息的居民ID
        :param message: 信息内容
        :param relation_type: 关系类型
        """
        neighbors = self.hetero_graph.get_neighbors(resident_id, relation_type)
        for neighbor in neighbors:
            # 这里可以调用每个邻居的receive_information方法
            if neighbor in self.residents:
                self.residents[neighbor].receive_information(message)

    def get_resident_groups(self, resident_id: int, group_type: str) -> List[str]:
        """
        获取居民所属的特定类型群组
        :param resident_id: 居民ID
        :param group_type: 群组类型（family或hometown）
        :return: 群组ID列表
        """
        groups = []
        for edge_id in self.hyper_graph.get_node_hyperedges(resident_id):
            if edge_id.startswith(group_type):
                groups.append(edge_id)
        return groups

    def spread_information_in_group(self, group_id: str, message: str):
        """
        在超图的群组中传播信息
        :param group_id: 群组ID
        :param message: 信息内容
        """
        members = self.hyper_graph.get_hyperedge_nodes(group_id)
        for member in members:
            if member in self.residents:
                self.residents[member].receive_information(message)
    def visualize(self):
        """
        可视化社交网络，同时显示异质图和超图的可视化图片，并添加边框和间距。
        保存图片到指定目录。
        """
        # 确保保存目录存在
        save_dir = "e:/cyf/多智能体/AgentWorld/experiment_dataset/social_network_data"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        try:
            # 使用 Agg 后端，避免使用 tkinter
            import matplotlib
            matplotlib.use('Agg')
            
            # 创建一个包含两个子图的画布，并调整间距
            fig, axes = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={'wspace': 0.3})
        
            # 可视化异质图
            ax1 = axes[0]
            plt.sca(ax1)  # 设置当前坐标轴
            self.hetero_graph.visualize()
            ax1.set_title("Heterogeneous Graph", pad=20)
        
            # 可视化超图
            ax2 = axes[1]
            plt.sca(ax2)  # 设置当前坐标轴
            hnx.draw(self.hyper_graph.hypergraph)
            ax2.set_title("Hypergraph", pad=20)
        
            # 生成当前时间作为文件名
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(save_dir, f"social_network_{current_time}.png")
            
            # 保存图片
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"社交网络图已保存至：{save_path}")
            
            # 关闭图形，释放内存
            plt.close(fig)
            
        except Exception as e:
            print(f"社交网络可视化失败：{e}")
        
        # 显示图片
        plt.show()

    def initialize_network(self, residents: dict) -> None:
        """
        初始化社交网络，建立居民之间的关系
        :param residents: 居民字典
        """
        # 存储居民字典
        self.residents = residents
        threshold = 0.5     #随机关系阈值
        
        # 将居民添加到社交网络
        resident_ids = list(residents.keys())
        for resident_id in resident_ids:
            self.add_resident(resident_id, "resident")

        # 使用矩阵方式建立朋友和同事关系
        n = len(resident_ids)
        
        # 生成朋友关系矩阵
        friend_matrix = np.random.random((n, n))
        friend_matrix = (friend_matrix + friend_matrix.T) / 2  # 确保对称
        np.fill_diagonal(friend_matrix, 0)  # 对角线置0
        friend_matrix = (friend_matrix > threshold).astype(int)

        # 生成同事关系矩阵
        colleague_matrix = np.random.random((n, n))
        colleague_matrix = (colleague_matrix + colleague_matrix.T) / 2
        np.fill_diagonal(colleague_matrix, 0)
        colleague_matrix = (colleague_matrix > threshold).astype(int)
        
        # 将矩阵转换为关系对
        friend_pairs = np.where(np.triu(friend_matrix) == 1)
        colleague_pairs = np.where(np.triu(colleague_matrix) == 1)

        # 建立朋友关系
        for i, j in zip(*friend_pairs):
            self.add_relation(resident_ids[i], resident_ids[j], "friend")
        
        # 建立同事关系
        for i, j in zip(*colleague_pairs):
            self.add_relation(resident_ids[i], resident_ids[j], "colleague")

        # 建立家族关系
        families = []
        remaining_residents = set(resident_ids)
        family_id = 0
        
        while remaining_residents:
            if len(remaining_residents) < 5:
                family_members = remaining_residents
                remaining_residents = set()
            else:
                family_size = random.randint(5, min(15, len(remaining_residents)))
                family_members = set(random.sample(list(remaining_residents), family_size))
                remaining_residents -= family_members
            
            families.append((f"family_{family_id}", list(family_members)))
            family_id += 1
            
            self.add_group(f"family_{family_id}", list(family_members))
            member_list = list(family_members)
            for i, member1 in enumerate(member_list):
                for member2 in member_list[i+1:]:
                    self.add_relation(member1, member2, "family")

        # 先建立同乡关系
        location_groups = {}
        for resident_id, resident in residents.items():
            x, y = resident.location
            area_key = (x // 20, y // 20)
            location_groups.setdefault(area_key, set()).add(resident_id)

        # 存储每个居民的同乡群组，用于后续建立家族关系
        resident_hometowns = {}
        
        for area_key, members in location_groups.items():
            if len(members) > 1:
                group_id = f"hometown_{area_key[0]}_{area_key[1]}"
                member_list = list(members)
                self.add_group(group_id, member_list)
                
                # 记录每个居民的同乡群组并建立关系
                for member in member_list:
                    resident_hometowns[member] = group_id
                    # 与同区域的所有其他居民建立关系
                    for other_member in member_list:
                        if other_member != member:
                            self.add_relation(member, other_member, "hometown")

        # 在同乡的基础上建立家族关系
        remaining_residents = set(resident_ids)
        family_id = 0
        
        # 按照同乡区域分组处理家族关系
        for area_members in location_groups.values():
            area_remaining = set(area_members)
            
            while len(area_remaining) >= 3:  # 确保每个家族至少有3个成员
                # 从当前区域随机选择3-8个居民组成家族
                family_size = random.randint(3, min(8, len(area_remaining)))
                family_members = set(random.sample(list(area_remaining), family_size))
                area_remaining -= family_members
                
                # 创建家族群组
                family_group_id = f"family_{family_id}"
                self.add_group(family_group_id, list(family_members))
                
                # 建立家族成员之间的关系
                member_list = list(family_members)
                for i, member1 in enumerate(member_list):
                    for member2 in member_list[i+1:]:
                        self.add_relation(member1, member2, "family")
                
                family_id += 1
                remaining_residents -= family_members
            
            # 将剩余的居民添加到现有家族中
            for resident in area_remaining:
                # 找到同一区域的现有家族
                area_families = [f"family_{i}" for i in range(family_id) 
                               if any(m in area_members for m in self.hyper_graph.get_hyperedge_nodes(f"family_{i}"))]
                
                if area_families:
                    # 随机选择一个家族加入
                    chosen_family = random.choice(area_families)
                    current_members = set(self.hyper_graph.get_hyperedge_nodes(chosen_family))
                    new_members = current_members | {resident}
                    
                    # 更新家族群组
                    self.hyper_graph.remove_hyperedge(chosen_family)
                    self.add_group(chosen_family, list(new_members))
                    
                    # 建立与家族成员的关系
                    for member in current_members:
                        self.add_relation(resident, member, "family")
                
                remaining_residents.remove(resident)

    def add_new_residents(self, new_residents: dict) -> None:
        """
        将新生成的居民添加到现有的社交网络中
        :param new_residents: 新居民字典 {resident_id: resident}
        """
        # 将新居民添加到residents字典
        self.residents.update(new_residents)
        
        # 获取所有现有居民ID（不包括新居民）
        existing_resident_ids = [rid for rid in self.residents.keys() if rid not in new_residents]
        new_resident_ids = list(new_residents.keys())
        
        # 为每个新居民添加节点和关系
        for resident_id in new_resident_ids:
            # 添加居民节点
            self.add_resident(resident_id, "resident")
            
            # 随机添加朋友关系（1-3个）
            if existing_resident_ids:  # 如果有现有居民
                num_friends = random.randint(1, 3)
                potential_friends = random.sample(existing_resident_ids, min(num_friends, len(existing_resident_ids)))
                for friend_id in potential_friends:
                    self.add_relation(resident_id, friend_id, "friend")
            
            # 随机添加同事关系（1-3个）
            if existing_resident_ids:
                num_colleagues = random.randint(1, 3)
                potential_colleagues = random.sample(existing_resident_ids, min(num_colleagues, len(existing_resident_ids)))
                for colleague_id in potential_colleagues:
                    self.add_relation(resident_id, colleague_id, "colleague")
            
            # 先建立同乡关系
            x, y = new_residents[resident_id].location
            area_key = (x // 20, y // 20)
            hometown_group_id = f"hometown_{area_key[0]}_{area_key[1]}"
            
            # 查找同一区域的现有居民
            same_area_residents = []
            for rid, resident in self.residents.items():
                if rid != resident_id:
                    rx, ry = resident.location
                    if (rx // 20, ry // 20) == area_key:
                        same_area_residents.append(rid)
            
            if same_area_residents:
                # 添加到同乡群组并直接与所有同乡建立关系
                self.add_group(hometown_group_id, [resident_id] + same_area_residents)
                # 与所有同乡建立关系
                for neighbor in same_area_residents:
                    self.add_relation(resident_id, neighbor, "hometown")
                
                # 在同乡中寻找现有的家族
                area_families = []
                for neighbor in same_area_residents:
                    # 获取邻居所属的家族
                    for edge in self.hyper_graph.get_node_hyperedges(neighbor):
                        if edge.startswith("family_"):
                            area_families.append(edge)
                
                # 如果同乡中有家族，随机选择一个加入（80%概率）
                if area_families and random.random() < 0.8:
                    chosen_family = random.choice(list(set(area_families)))  # 去重
                    # 将新居民添加到选中的家族中
                    members = self.hyper_graph.get_hyperedge_nodes(chosen_family)
                    members = list(members) + [resident_id]
                    self.add_group(chosen_family, members)
                    # 添加家族关系
                    for member in members:
                        if member != resident_id:
                            self.add_relation(resident_id, member, "family")
