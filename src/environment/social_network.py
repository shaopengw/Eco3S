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
            
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
            plt.rcParams['axes.unicode_minus'] = False    # 解决负号显示问题
            
            # 创建更大的画布
            fig, axes = plt.subplots(1, 2, figsize=(24, 12), gridspec_kw={'wspace': 0.3})
            
            # 计算节点大小
            num_nodes = len(self.hetero_graph.graph.nodes)
            node_size = max(50, 1000 / (1 + np.log(num_nodes)))  # 使用对数缩放防止节点过小
            
            # 可视化异质图
            ax1 = axes[0]
            plt.sca(ax1)  # 设置当前坐标轴
            pos = nx.spring_layout(self.hetero_graph.graph, k=1.5)  # 增加节点间距
            
            # 绘制节点
            node_colors = [self.hetero_graph.graph.nodes[node]["type"] == "person" and "lightblue" or "lightgreen" 
                         for node in self.hetero_graph.graph.nodes]
            nx.draw_networkx_nodes(self.hetero_graph.graph, pos, node_color=node_colors, 
                                 node_size=node_size, alpha=0.7)
            
            # 根据节点数量调整标签字体大小
            font_size = max(6, 16 / (1 + np.log(num_nodes)))
            nx.draw_networkx_labels(self.hetero_graph.graph, pos, font_size=font_size)
            
            # 绘制不同类型的边
            edge_colors = {
                "friend": "red",
                "colleague": "blue",
                "family": "green",
                "hometown": "purple"
            }
            
            for edge_type, color in edge_colors.items():
                edge_list = [(u, v) for (u, v, d) in self.hetero_graph.graph.edges(data=True) 
                            if d["type"] == edge_type]
                if edge_list:
                    nx.draw_networkx_edges(self.hetero_graph.graph, pos, edgelist=edge_list, 
                                         edge_color=color, width=0.8, alpha=0.6)
            
            ax1.set_title("异质图", pad=20, fontsize=16, fontfamily='SimHei')
            
            # 可视化超图
            ax2 = axes[1]
            plt.sca(ax2)
            hnx.draw(self.hyper_graph.hypergraph, 
                    with_node_labels=True,
                    node_labels_kwargs={'fontsize': font_size})
            ax2.set_title("超图", pad=20, fontsize=16, fontfamily='SimHei')
            
            # 保存高清图片
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(save_dir, f"social_network_{current_time}.png")
            plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
            print(f"社交网络图已保存至：{save_path}")
            
            plt.close(fig)
            
        except Exception as e:
            print(f"社交网络可视化失败：{e}")
        

    def initialize_network(self, residents: dict) -> None:
        """
        初始化社交网络，建立居民之间的关系
        :param residents: 居民字典
        """
        # 存储居民字典
        self.residents = residents
        # threshold = 0.5     #随机关系阈值
        
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
        threshold = np.percentile(friend_matrix[np.triu_indices(n, 1)], 100 * (1 - 3/n))
        friend_matrix = (friend_matrix > threshold).astype(int)

        # 生成同事关系矩阵
        colleague_matrix = np.random.random((n, n))
        colleague_matrix = (colleague_matrix + colleague_matrix.T) / 2
        np.fill_diagonal(colleague_matrix, 0)
        threshold = np.percentile(colleague_matrix[np.triu_indices(n, 1)], 100 * (1 - 3/n))
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

        # # 建立家族关系
        # families = []
        # remaining_residents = set(resident_ids)
        # family_id = 0
        
        # while remaining_residents:
        #     if len(remaining_residents) < 5:
        #         family_members = remaining_residents
        #         remaining_residents = set()
        #     else:
        #         family_size = random.randint(5, min(15, len(remaining_residents)))
        #         family_members = set(random.sample(list(remaining_residents), family_size))
        #         remaining_residents -= family_members
            
        #     families.append((f"family_{family_id}", list(family_members)))
        #     family_id += 1
            
        #     self.add_group(f"family_{family_id}", list(family_members))
        #     member_list = list(family_members)


        # 先建立同乡关系
        location_groups = {}
        for resident_id, resident in residents.items():
            x, y = resident.location
            area_key = (x // 20, y // 20)
            location_groups.setdefault(area_key, set()).add(resident_id)

        # 在每个地理区域内建立同乡和家庭关系
        family_id = 0
        for area_key, members in location_groups.items():
            if len(members) > 1:
                # 建立同乡群组
                hometown_group_id = f"hometown_{area_key[0]}_{area_key[1]}"
                member_list = list(members)
                self.add_group(hometown_group_id, member_list)
                
                # 在同乡群组内基于距离建立家庭关系
                area_remaining = set(member_list)
                
                while len(area_remaining) >= 3:  # 确保每个家族至少有3个成员
                    # 从剩余居民中选择一个作为家庭中心点
                    center = random.choice(list(area_remaining))
                    center_x, center_y = residents[center].location
                    
                    # 计算其他居民到中心点的距离
                    distances = []
                    for resident in area_remaining:
                        if resident != center:
                            x, y = residents[resident].location
                            dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                            distances.append((resident, dist))
                    
                    # 按距离排序
                    distances.sort(key=lambda x: x[1])
                    
                    # 选择3-8个最近的居民组成家庭
                    family_size = random.randint(3, min(8, len(area_remaining)))
                    family_members = {center}  # 包含中心点
                    for resident, _ in distances[:family_size-1]:  # -1是因为已经包含了中心点
                        family_members.add(resident)
                    
                    # 创建家庭群组
                    family_group_id = f"family_{family_id}"
                    self.add_group(family_group_id, list(family_members))
                    
                    # 更新剩余居民集合
                    area_remaining -= family_members
                    family_id += 1
                
                # 将剩余的每个居民单独作为一个家庭
                for resident in area_remaining:
                    # 创建单人家庭群组
                    family_group_id = f"family_{family_id}"
                    self.add_group(family_group_id, [resident])
                    family_id += 1
                

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
            
            # 建立同乡关系
            x, y = new_residents[resident_id].location
            area_key = (x // 20, y // 20)
            hometown_group_id = f"hometown_{area_key[0]}_{area_key[1]}"
            # 添加到对应的同乡群组
            self.add_group(hometown_group_id, [resident_id])

            # 在同乡中寻找现有的家族
            area_families = []
            for edge in self.hyper_graph.get_node_hyperedges(resident_id):
                if edge.startswith("family_"):
                    area_families.append(edge)
            
            # 如果同乡中有家族，随机选择一个加入（80%概率）
            if area_families and random.random() < 0.8:
                chosen_family = random.choice(list(set(area_families)))
                # 将新居民添加到选中的家族中
                members = self.hyper_graph.get_hyperedge_nodes(chosen_family)
                members = list(members) + [resident_id]
                self.add_group(chosen_family, members)
                # 添加家族关系
                for member in members:
                    if member != resident_id:
                        self.add_relation(resident_id, member, "family")
