import random
import os
import hypernetx as hnx
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from typing import List
from datetime import datetime
from sklearn.cluster import KMeans
import asyncio
import math

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

    async def spread_information(self, resident_id: int, message: str, relation_type: str, current_depth: int = 1, max_depth: int = 3):
        """
        在异质图中传播信息，支持并发执行
        :param resident_id: 发送信息的居民ID
        :param message: 信息内容
        :param relation_type: 关系类型
        :param current_depth: 当前传播层数
        :param max_depth: 最大传播层数
        """
        if current_depth > max_depth:
            return
            
        neighbors = self.hetero_graph.get_neighbors(resident_id, relation_type)
        # 随机选择30%-70%的邻居节点
        selected_count = random.randint(max(1, int(len(neighbors) * 0.3)), max(1, int(len(neighbors) * 0.7)))
        selected_neighbors = random.sample(neighbors, min(selected_count, len(neighbors)))
        
        tasks = []
        for neighbor in selected_neighbors:
            if neighbor in self.residents:
                tasks.append(self.residents[neighbor].receive_information(message))
        
        # 并发执行所有接收任务
        if tasks:
            responses = await asyncio.gather(*tasks)
            # 并发处理所有有效的回应
            response_tasks = []
            for neighbor, response in zip(neighbors, responses):
                if response:
                    response_content, response_type = response
                    response_tasks.append(
                        self.spread_speech_in_network(neighbor, response_content, response_type, current_depth + 1)
                    )
            if response_tasks:
                await asyncio.gather(*response_tasks)

    async def spread_information_in_group(self, group_id: str, message: str, current_depth: int = 1, max_depth: int = 3):
        """
        在超图的群组中并发传播信息
        :param group_id: 群组ID
        :param message: 信息内容
        :param current_depth: 当前传播层数
        :param max_depth: 最大传播层数
        """
        if current_depth > max_depth:
            return
            
        members = self.hyper_graph.get_hyperedge_nodes(group_id)
        # 随机选择30%-70%的群组成员
        selected_count = random.randint(max(1, int(len(members) * 0.3)), max(1, int(len(members) * 0.7)))
        selected_members = random.sample(members, min(selected_count, len(members)))
        
        tasks = []
        for member in selected_members:
            if member in self.residents:
                tasks.append(self.residents[member].receive_information(message))
        
        # 并发执行所有接收任务
        if tasks:
            responses = await asyncio.gather(*tasks)
            # 并发处理所有有效的回应
            response_tasks = []
            for member, response in zip(members, responses):
                if response:
                    response_content, response_type = response
                    response_tasks.append(
                        self.spread_speech_in_network(member, response_content, response_type, current_depth + 1)
                    )
            if response_tasks:
                await asyncio.gather(*response_tasks)

    async def spread_speech_in_network(self, resident_id: int, speech: str, relation_type: str, current_depth: int = 1, max_depth: int = 3):
        """在社交网络中递归传播发言
        :param resident_id: 发送信息的居民ID
        :param speech: 发言内容
        :param relation_type: 关系类型
        :param current_depth: 当前传播层数
        :param max_depth: 最大传播层数
        """
        try:
            if current_depth > max_depth:
                return
                
            resident = self.residents.get(resident_id)
            if not resident:
                return

            if relation_type in ["friend", "colleague"]:
                # 在异质图中并发传播
                await self.spread_information(resident_id, speech, relation_type, current_depth, max_depth)
                
            elif relation_type in ["family", "hometown"]:
                # 在超图中并发传播
                groups = self.get_resident_groups(resident_id, relation_type)
                if groups:
                    selected_group = random.choice(groups)
                    await self.spread_information_in_group(selected_group, speech, current_depth, max_depth)
                    
        except Exception as e:
            print(f"在社交网络中传播发言时出错：{e}")

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

    def visualize(self):
        """
        可视化社交网络，同时显示异质图和超图的可视化图片，并添加边框和间距。
        保存图片到指定目录。
        """
        # 确保保存目录存在
        save_dir = "experiment_dataset/social_network_data"
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

    def initialize_network(self, residents: dict, towns) -> None:
        """
        初始化社交网络，建立居民之间的关系
        :param residents: 居民字典
        :param towns: 城镇
        """
        # 存储居民字典
        self.residents = residents
        # 初始化 family_id 计数器
        family_id = 0
        
        # 将居民添加到社交网络
        resident_ids = list(residents.keys())
        for resident_id in resident_ids:
            self.add_resident(resident_id, "resident")

        # 使用矩阵方式建立朋友和同事关系
        n = len(resident_ids)
        
        # 生成朋友关系矩阵（幂律分布）
        # friend_matrix = np.random.random((n, n))
        gamma = 2.5 
        friend_matrix = np.random.power(a=gamma, size=(n, n))
        friend_matrix = (friend_matrix + friend_matrix.T) / 2  # 确保对称
        np.fill_diagonal(friend_matrix, 0)  # 对角线置0
        threshold = np.percentile(friend_matrix[np.triu_indices(n, 1)], 100 * (1 - 3/n))
        friend_matrix = (friend_matrix > threshold).astype(int)

        # 生成同事关系矩阵（幂律分布）
        # colleague_matrix = np.random.random((n, n))
        colleague_matrix = np.random.power(a=gamma, size=(n, n))
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
        # 为每个城镇创建同乡关系超边
        for town_name, town_data in towns.towns.items():
            town_residents = town_data['residents'].keys()
            if town_residents:
                # 创建同乡关系超边
                hometown_group_id = f"hometown_{town_name}"
                self.add_group(hometown_group_id, list(town_residents))
                # 将超边ID存储到城镇数据中
                town_data['hometown_group'] = hometown_group_id
                
                # 在同乡群组内基于距离建立家庭关系
                area_remaining = list(town_residents)
                
                # 使用KMeans聚类
                if len(area_remaining) >= 6:
                    # 提取所有居民的位置坐标
                    resident_locations = np.array([residents[r].location for r in area_remaining])
                    
                    # 估计家庭数量 (平均每个家庭3人)
                    num_families = max(1, len(area_remaining) // 3)
                    
                    # 使用KMeans聚类算法将居民分组为多个家庭
                    
                    try:
                        kmeans = KMeans(n_clusters=num_families, random_state=0)
                        clusters = kmeans.fit_predict(resident_locations)
                        
                        # 根据聚类结果创建家庭
                        families = [[] for _ in range(num_families)]
                        for i, cluster_id in enumerate(clusters):
                            families[cluster_id].append(area_remaining[i])
                        
                        # 批量创建家庭群组
                        for family_members in families:
                            if len(family_members) >= 3:  # 确保每个家庭至少有3个成员
                                family_group_id = f"family_{family_id}"
                                self.add_group(family_group_id, family_members)
                                family_id += 1
                        
                        # 清空剩余居民集合
                        area_remaining = []
                        
                    except Exception as e:
                        # 如果KMeans失败，回退到原始算法
                        print(f"KMeans聚类失败: {e}")

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
            joined_family = False
            if area_families and random.random() < 0.8:
                chosen_family = random.choice(list(set(area_families)))
                # 将新居民添加到选中的家族中
                self.add_group(chosen_family, [resident_id])
                joined_family = True
            
            # # 如果没有加入任何家族，创建单人家族
            # if not joined_family:
            #     family_id = len([edge for edge in self.hyper_graph.get_hyperedges() if edge.startswith("family_")])
            #     family_group_id = f"family_{family_id}"
            #     self.add_group(family_group_id, [resident_id])

    def calculate_speech_probability(self, node_id: int, population: int) -> float:
        """
        计算节点的发言概率
        :param node_id: 节点ID
        :return: 发言概率值(0-1)
        """

        try:
            degree = self.get_node_degree(node_id)
            max_degree = self.get_max_degree()
            normalized_degree = degree / max_degree
            print(f"节点 {node_id} 的度发言概率为{degree}/{max_degree}={normalized_degree}")
            
            # speech_probability = 1 / (1 + math.exp(-10 * (normalized_degree - 0.5)))
            # print(f"节点 {node_id} 的度发言概率为{degree}/{max_degree}={normalized_degree}，经过归一化后为 {speech_probability}")
            return normalized_degree
        except ValueError:
            return 0.0

    def get_node_degree(self, node_id: int) -> float:
        """获取指定节点的度数
        :param node_id: 节点ID
        :return: 节点的度数
        :raises ValueError: 如果节点不存在
        """
        if node_id not in self.hetero_graph.graph.nodes:
            raise ValueError(f"节点 {node_id} 不存在")
        
        # 获取节点的所有边
        degree = self.hetero_graph.graph.degree(node_id)
        return degree

    def get_max_degree(self) -> float:
        """获取图中的最大度数
        :return: 最大度数
        :raises ValueError: 如果图为空
        """
        if not self.hetero_graph.graph.nodes:
            raise ValueError("图为空")
        
        # 获取所有节点的度数
        degrees = dict(self.hetero_graph.graph.degree())
        max_degree = max(degrees.values())
        return max_degree

    def plot_degree_distribution(self):
        """
        绘制异质图中节点度分布的可视化表格，横坐标为度数，纵坐标为人数。
        """
        print("正在绘制社交网络节点度分布...")
        degrees = [self.hetero_graph.graph.degree(n) for n in self.hetero_graph.graph.nodes]
        degree_count = {}
        for d in degrees:
            degree_count[d] = degree_count.get(d, 0) + 1
        x = sorted(degree_count.keys())
        y = [degree_count[k] for k in x]
        plt.figure(figsize=(8, 5))
        plt.bar(x, y, color='skyblue')
        plt.xlabel('度数')
        plt.ylabel('人数')
        plt.title('社交网络节点度分布')
        plt.xticks(x)
        plt.tight_layout()
        plt.show()
        # 保存高清图片
        save_dir = "experiment_dataset/social_network_data"
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(save_dir, f"degree_distribution_{current_time}.png")
        plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
        print(f"社交网络图已保存至：{save_path}")