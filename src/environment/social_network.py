import random
import os
import hypernetx as hnx
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
os.environ["OMP_NUM_THREADS"] = "1"
from sklearn.cluster import KMeans
import asyncio
from src.interfaces import IHeterogeneousGraph, IHypergraph, ISocialNetwork

class HeterogeneousGraph(IHeterogeneousGraph):
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
    
    def remove_node(self, node_id):
        """
        从异质图中移除节点。
        """
        if node_id in self.graph.nodes:
            self.graph.remove_node(node_id)

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

class Hypergraph(IHypergraph):
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
    
    def remove_hyperedge_node(self, group_id, member):
        """
        从超图中移除一个关联关系。
        """
        self.hypergraph.remove_incidences(group_id, member)

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


class SocialNetwork(ISocialNetwork):
    """
    结合异质图和超图，构建社交网络。
    """ 
    def __init__(self):
        self._hetero_graph = HeterogeneousGraph()
        self._hyper_graph = Hypergraph()
        self._residents = {}  # 添加residents字典
        self._dialogue_count = 0  # 当前时间步的对话计数
        self._max_dialogues_per_step = 20000  # 每个时间步最大对话量

    @property
    def hetero_graph(self) -> IHeterogeneousGraph:
        return self._hetero_graph

    @property
    def hyper_graph(self) -> IHypergraph:
        return self._hyper_graph

    @property
    def residents(self) -> dict:
        return self._residents

    @residents.setter
    def residents(self, value: dict) -> None:
        self._residents = value

    @property
    def dialogue_count(self) -> int:
        return self._dialogue_count

    @dialogue_count.setter
    def dialogue_count(self, value: int) -> None:
        self._dialogue_count = value

    @property
    def MAX_DIALOGUES_PER_STEP(self) -> int:
        return self._max_dialogues_per_step

    @MAX_DIALOGUES_PER_STEP.setter
    def MAX_DIALOGUES_PER_STEP(self, value: int) -> None:
        self._max_dialogues_per_step = value

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

    async def communicate_resident_to_resident(
        self,
        sender_id: int,
        receiver_id: int,
        message: str,
    ) -> Optional[Any]:
        """指定居民与指定居民一对一沟通。

        约定：底层复用 resident.receive_information(message) 的返回值。
        """
        if self.dialogue_count >= self.MAX_DIALOGUES_PER_STEP:
            return None

        receiver = self.residents.get(receiver_id)
        if receiver is None:
            return None

        self.dialogue_count += 1
        responses = await asyncio.gather(receiver.receive_information(message), return_exceptions=True)
        response = responses[0]
        if isinstance(response, Exception):
            return None
        return response

    async def communicate_resident_to_residents(
        self,
        sender_id: int,
        receiver_ids: List[int],
        message: str,
    ) -> Dict[int, Optional[Any]]:
        """指定居民一对多沟通。"""
        results: Dict[int, Optional[Any]] = {rid: None for rid in receiver_ids}
        if not receiver_ids:
            return results

        remaining = self.MAX_DIALOGUES_PER_STEP - self.dialogue_count
        if remaining <= 0:
            return results

        tasks = []
        task_receiver_ids: List[int] = []
        for rid in receiver_ids:
            if len(tasks) >= remaining:
                break
            receiver = self.residents.get(rid)
            if receiver is None:
                continue
            tasks.append(receiver.receive_information(message))
            task_receiver_ids.append(rid)

        if not tasks:
            return results

        self.dialogue_count += len(tasks)
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for rid, resp in zip(task_receiver_ids, responses):
            results[rid] = None if isinstance(resp, Exception) else resp
        return results

    async def communicate_user_to_resident(
        self,
        user_id: str,
        resident_id: int,
        message: str,
    ) -> Optional[Any]:
        """用户与指定居民沟通。"""
        # sender_id 对 resident.receive_information 来说通常不重要，保留参数用于上层扩展。
        return await self.communicate_resident_to_resident(sender_id=-1, receiver_id=resident_id, message=message)

    async def communicate_user_to_residents(
        self,
        user_id: str,
        resident_ids: List[int],
        message: str,
    ) -> Dict[int, Optional[Any]]:
        """用户与指定居民列表沟通。"""
        return await self.communicate_resident_to_residents(sender_id=-1, receiver_ids=resident_ids, message=message)

    async def spread_information(self, resident_id: int, message: str, relation_type: str, current_depth: int = 1, max_depth: int = 3):
        """
        在异质图中传播信息，支持并发执行
        :param resident_id: 发送信息的居民ID
        :param message: 信息内容
        :param relation_type: 关系类型
        :param current_depth: 当前传播层数
        :param max_depth: 最大传播层数
        """
        # 检查对话量限制
        if self.dialogue_count >= self.MAX_DIALOGUES_PER_STEP:
            return
        
        if current_depth > max_depth:
            return
            
        neighbors = self.hetero_graph.get_neighbors(resident_id, relation_type)
        # 随机选择30%-50%的邻居节点
        selected_count = random.randint(max(1, int(len(neighbors) * 0.3)), max(1, int(len(neighbors) * 0.5)))
        selected_neighbors = random.sample(neighbors, min(selected_count, len(neighbors)))
        
        # 并发执行所有接收任务
        tasks = []
        for neighbor in selected_neighbors:
            if neighbor in self.residents:
                tasks.append(self.residents[neighbor].receive_information(message))
        
        if tasks:
            self.dialogue_count += len(tasks)  # 更新对话计数
            responses = await asyncio.gather(*tasks)
            # 收集所有有效回应
            next_layer_tasks = []
            for neighbor, response in zip(selected_neighbors, responses):
                if response:
                    response_content, response_type = response
                    next_neighbors = self.hetero_graph.get_neighbors(neighbor, response_type)
                    next_selected_count = random.randint(max(1, int(len(next_neighbors) * 0.3)), max(1, int(len(next_neighbors) * 0.5)))
                    next_selected_neighbors = random.sample(next_neighbors, min(next_selected_count, len(next_neighbors)))
                    for next_neighbor in next_selected_neighbors:
                        if next_neighbor in self.residents:
                            next_layer_tasks.append((next_neighbor, response_content, response_type))
            
            # 并发执行下一层的所有传播任务
            if next_layer_tasks and current_depth < max_depth:
                spread_tasks = [self.residents[next_neighbor].receive_information(content) 
                               for next_neighbor, content, _ in next_layer_tasks]
                await asyncio.gather(*spread_tasks)

    async def spread_information_in_group(self, group_id: str, message: str, current_depth: int = 1, max_depth: int = 3):
        """
        在超图的群组中并发传播信息
        :param group_id: 群组ID
        :param message: 信息内容
        :param current_depth: 当前传播层数
        :param max_depth: 最大传播层数
        """
        # 检查对话量限制
        if self.dialogue_count >= self.MAX_DIALOGUES_PER_STEP:
            return
        
        if current_depth > max_depth:
            return
            
        members = self.hyper_graph.get_hyperedge_nodes(group_id)
        # 随机选择30%-50%的群组成员
        selected_count = random.randint(max(1, int(len(members) * 0.3)), max(1, int(len(members) * 0.5)))
        selected_members = random.sample(members, min(selected_count, len(members)))
        
        # 并发执行所有接收任务
        tasks = []
        for member in selected_members:
            if member in self.residents:
                tasks.append(self.residents[member].receive_information(message))
        
        if tasks:
            self.dialogue_count += len(tasks)  # 更新对话计数
            responses = await asyncio.gather(*tasks)
            # 收集所有有效回应
            next_layer_tasks = []
            for member, response in zip(selected_members, responses):
                if response:
                    response_content, response_type = response
                    if response_type in ["friend", "colleague"]:
                        next_neighbors = self.hetero_graph.get_neighbors(member, response_type)
                        next_selected_count = random.randint(max(1, int(len(next_neighbors) * 0.3)), max(1, int(len(next_neighbors) * 0.5)))
                        next_selected_neighbors = random.sample(next_neighbors, min(next_selected_count, len(next_neighbors)))
                        for next_neighbor in next_selected_neighbors:
                            if next_neighbor in self.residents:
                                next_layer_tasks.append((next_neighbor, response_content, response_type))
                    elif response_type in ["family", "hometown"]:
                        groups = self.get_resident_groups(member, response_type)
                        if groups:
                            selected_group = random.choice(groups)
                            next_layer_tasks.append((selected_group, response_content, response_type, True))
            
            # 并发执行下一层的所有传播任务
            if next_layer_tasks and current_depth < max_depth:
                spread_tasks = []
                for task in next_layer_tasks:
                    if len(task) == 4:  # 群组传播
                        group_id, content, _, _ = task
                        spread_tasks.append(self.spread_information_in_group(group_id, content, current_depth + 1, max_depth))
                    else:  # 个人传播
                        next_neighbor, content, _ = task
                        spread_tasks.append(self.residents[next_neighbor].receive_information(content))
                await asyncio.gather(*spread_tasks)

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

            tasks = []
            if relation_type in ["friend", "colleague"]:
                # 在异质图中并发传播
                tasks.append(self.spread_information(resident_id, speech, relation_type, current_depth, max_depth))
                
            elif relation_type in ["family", "hometown"]:
                # 在超图中并发传播
                groups = self.get_resident_groups(resident_id, relation_type)
                if groups:
                    selected_group = random.choice(groups)
                    tasks.append(self.spread_information_in_group(selected_group, speech, current_depth, max_depth))
            
            if tasks:
                await asyncio.gather(*tasks)
                    
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
        保存图片到指定目录。针对大规模网络进行优化。
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
            
            # 计算节点数量
            num_nodes = len(self.hetero_graph.graph.nodes)
            print(f"[可视化] 社交网络包含 {num_nodes} 个节点")
            
            # 可视化异质图
            ax1 = axes[0]
            plt.sca(ax1)
            
            # 根据节点数量选择不同的可视化策略
            if num_nodes > 1000:
                # 大规模网络：使用采样和优化的布局
                print(f"[可视化] 检测到大规模网络({num_nodes}个节点)，使用优化策略...")
                
                # 策略1：只显示核心节点（度数较高的节点）
                degrees = dict(self.hetero_graph.graph.degree())
                # 按度数排序，取前30%的节点
                sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
                sample_size = min(1000, max(500, int(num_nodes * 0.3)))  # 显示500-1000个核心节点
                core_nodes = [node for node, _ in sorted_nodes[:sample_size]]
                
                # 创建子图
                subgraph = self.hetero_graph.graph.subgraph(core_nodes)
                print(f"[可视化] 显示核心节点子图：{len(core_nodes)} 个节点")
                
                # 使用更快的布局算法
                pos = nx.kamada_kawai_layout(subgraph, scale=2)
                
                # 节点大小根据度数调整，但更小一些
                node_sizes = [max(10, min(100, degrees[node] * 3)) for node in core_nodes]
                
                # 不显示标签（太多会很乱）
                node_colors = ['lightblue' if subgraph.nodes[node]["type"] == "person" else "lightgreen" 
                             for node in core_nodes]
                nx.draw_networkx_nodes(subgraph, pos, node_color=node_colors, 
                                     node_size=node_sizes, alpha=0.6)
                
                # 绘制边（降低透明度）
                edge_colors = {
                    "friend": (1, 0, 0, 0.4),      # 红色，40%透明度
                    "colleague": (0, 0, 1, 0.4),   # 蓝色，40%透明度
                }
                
                for edge_type, color in edge_colors.items():
                    edge_list = [(u, v) for (u, v, d) in subgraph.edges(data=True) 
                                if d["type"] == edge_type]
                    if edge_list:
                        nx.draw_networkx_edges(subgraph, pos, edgelist=edge_list, 
                                             edge_color=color, width=0.5, alpha=0.4)
                
                ax1.set_title(f"异质图（核心节点子图：{len(core_nodes)}/{num_nodes}）", 
                            pad=20, fontsize=16, fontweight='bold', fontfamily='SimHei')
            
            else:
                # 中小规模网络：正常显示
                node_size = max(30, 800 / (1 + np.log(num_nodes)))
                
                # 使用spring_layout，增加迭代次数提高质量
                pos = nx.spring_layout(self.hetero_graph.graph, k=2/np.sqrt(num_nodes), 
                                      iterations=50, seed=42)
                
                # 绘制节点
                node_colors = [self.hetero_graph.graph.nodes[node]["type"] == "person" and "lightblue" or "lightgreen" 
                             for node in self.hetero_graph.graph.nodes]
                nx.draw_networkx_nodes(self.hetero_graph.graph, pos, node_color=node_colors, 
                                     node_size=node_size, alpha=0.7)
                
                # 根据节点数量决定是否显示标签
                if num_nodes <= 500:
                    font_size = max(6, 16 / (1 + np.log(num_nodes)))
                    nx.draw_networkx_labels(self.hetero_graph.graph, pos, font_size=font_size)
                
                # 绘制不同类型的边
                edge_colors = {
                    "friend": "red",
                    "colleague": "blue"
                }
                
                for edge_type, color in edge_colors.items():
                    edge_list = [(u, v) for (u, v, d) in self.hetero_graph.graph.edges(data=True) 
                                if d["type"] == edge_type]
                    if edge_list:
                        nx.draw_networkx_edges(self.hetero_graph.graph, pos, edgelist=edge_list, 
                                             edge_color=color, width=0.8, alpha=0.5)
                
                ax1.set_title("异质图", pad=20, fontsize=16, fontweight='bold', fontfamily='SimHei')
            
            # 添加图例
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor='red', 
                      markersize=8, label='朋友关系', alpha=0.6),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', 
                      markersize=8, label='同事关系', alpha=0.6)
            ]
            ax1.legend(handles=legend_elements, loc='upper right', fontsize=10)
            
            # 可视化超图（采样显示部分城镇）
            ax2 = axes[1]
            plt.sca(ax2)
            
            if num_nodes > 1000:
                # 大规模网络：只显示统计信息
                ax2.text(0.5, 0.5, f'超图统计\n\n节点数: {len(self.hyper_graph.get_nodes())}\n'
                        f'超边数: {len(self.hyper_graph.get_hyperedges())}\n\n'
                        f'(节点过多，跳过详细可视化)',
                        ha='center', va='center', fontsize=14, 
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                ax2.set_xlim(0, 1)
                ax2.set_ylim(0, 1)
                ax2.axis('off')
            else:
                # 中小规模网络：正常显示超图
                font_size = max(6, 16 / (1 + np.log(num_nodes)))
                hnx.draw(self.hyper_graph.hypergraph, 
                        with_node_labels=(num_nodes <= 500),
                        node_labels_kwargs={'fontsize': font_size})
            
            ax2.set_title("超图", pad=20, fontsize=16, fontweight='bold', fontfamily='SimHei')
            
            # 保存高清图片
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(save_dir, f"social_network_{current_time}.png")
            plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
            print(f"社交网络图已保存至：{save_path}")
            
            plt.close(fig)
            
        except Exception as e:
            print(f"社交网络可视化失败：{e}")
            import traceback
            traceback.print_exc()

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
        gamma = 1.5
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
                    # 提取所有居民的位置坐标并添加微小噪声
                    resident_locations = np.array([residents[r].location for r in area_remaining], dtype=np.float64)
                    resident_locations += np.random.normal(0, 0.0001, resident_locations.shape)
                    
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

    def calculate_speech_probability(self, node_id) -> float:
        """
        计算节点的发言概率
        :param node_id: 节点ID
        :return: 发言概率值(0-1)
        """

        try:
            degree = self.get_node_degree(node_id)
            max_degree = self.get_max_degree()
            normalized_degree = degree / max_degree
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
        degrees = [self.hetero_graph.graph.degree(n) for n in self.hetero_graph.graph.nodes]
        degree_count = {}
        for d in degrees:
            degree_count[d] = degree_count.get(d, 0) + 1
        x = sorted(degree_count.keys())
        y = [degree_count[k] for k in x]
        
        plt.figure(figsize=(10, 6))
        plt.bar(x, y, color='skyblue', edgecolor='navy', alpha=0.7)
        plt.xlabel('度数', fontsize=12)
        plt.ylabel('人数', fontsize=12)
        plt.title('社交网络节点度分布', fontsize=14, fontweight='bold')
        plt.xticks(x)
        
        # 动态计算纵坐标刻度，确保有10-15个标识
        max_count = max(y)
        if max_count <= 15:
            # 如果最大值小于等于15，每个整数一个刻度
            yticks = list(range(0, max_count + 1))
        else:
            # 计算合适的间隔，使刻度数在10-15之间
            target_ticks = 12  # 目标刻度数
            interval = max(1, int(np.ceil(max_count / target_ticks)))
            # 将间隔调整为5、10、20、50、100等整数
            if interval <= 5:
                interval = 5
            elif interval <= 10:
                interval = 10
            elif interval <= 20:
                interval = 20
            elif interval <= 50:
                interval = 50
            else:
                interval = int(np.ceil(interval / 100) * 100)
            
            yticks = list(range(0, max_count + interval, interval))
        
        plt.yticks(yticks)
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        # 保存高清图片
        save_dir = "experiment_dataset/social_network_data"
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(save_dir, f"degree_distribution_{current_time}.png")
        plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
        print(f"社交网络节点度分布表已保存至：{save_path}")
        plt.close()

    def reset_dialogue_count(self):
        """
        重置当前时间步的对话计数器
        """
        self.dialogue_count = 0

    def update_network_edges(self, update_ratio=0.2):
        """
        随机更新社交网络中的部分边，默认每次更新20%。
        :param update_ratio: 每次更新的边的比例（0-1之间）
        """
        G = self.hetero_graph.graph
        
        # 获取所有边
        edges = list(G.edges(data=True))
        m = len(edges)
        if m == 0:
            print(f"警告：没有找到任何边可更新")
            return
        
        #计算需要更新的边数（确保至少更新1条边）
        num_update = max(1, int(round(m * update_ratio)))
        
        #随机选择要删除的边并批量删除
        edges_to_remove_data = random.sample(edges, num_update)
        edges_to_remove = [(u, v) for u, v, d in edges_to_remove_data]
        G.remove_edges_from(edges_to_remove)
        
        #准备节点列表用于随机采样
        nodes = list(G.nodes())
        n = len(nodes)
        max_possible_edges = n * (n - 1) // 2
        current_edges = G.number_of_edges()
        
        #检查是否还能添加新边
        if current_edges >= max_possible_edges:
            print("警告：图已达到最大边数，无法添加新边")
            return
        
        # 生成新边
        new_edges_list = []
        existing_edges_set = set(G.edges())
        max_attempts = min(1000, 10 * num_update)  # 合理限制尝试次数
        attempts = 0
        
        while len(new_edges_list) < num_update and attempts < max_attempts:
            u, v = random.sample(nodes, 2)
            # 检查边是否已存在，集合查找更快
            if (u, v) not in existing_edges_set and (v, u) not in existing_edges_set:
                # 随机选择一种现有边类型，或者默认'friend'，如果图中没有边类型
                if edges_to_remove_data:
                    edge_type = random.choice(edges_to_remove_data)[2].get("type", "friend")
                else:
                    edge_type = "friend"
                new_edges_list.append((u, v, {"type": edge_type}))
                existing_edges_set.add((u, v))
            attempts += 1
        
        # 批量添加新边
        G.add_edges_from(new_edges_list)
        
        #结果统计
        actual_ratio = len(new_edges_list) / m if m > 0 else 0
        print(f"社交网络更新完成: 更新了{len(edges_to_remove)}条边，实际更新比例{actual_ratio:.1%}，")

    def to_dict(self):
        """将社交网络状态转换为可序列化的字典"""
        return {
            'hetero_graph': nx.node_link_data(self.hetero_graph.graph, edges="edges"),
            'hyper_graph': {
                'nodes': list(self.hyper_graph.hypergraph.nodes),
                'edges': {e: list(self.hyper_graph.hypergraph.edges[e]) 
                        for e in self.hyper_graph.hypergraph.edges}
        }}

    @classmethod
    def from_dict(cls, data, residents):
        """从字典恢复社交网络"""
        sn = cls()
        sn.residents = residents

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 恢复异质图
        if 'hetero_graph' in data:
            try:
                sn.hetero_graph.graph = nx.node_link_graph(data['hetero_graph'], edges="edges")
            except KeyError:
                # 兼容旧版本的缓存数据
                sn.hetero_graph.graph = nx.node_link_graph(data['hetero_graph'], edges="links")
        
        # 恢复超图
        if 'hyper_graph' in data:
            hyper_data = data['hyper_graph']
            sn.hyper_graph = Hypergraph()
            for node in hyper_data.get('nodes', []):
                sn.hyper_graph.add_node(node)
            for edge_id, members in hyper_data.get('edges', {}).items():
                sn.hyper_graph.add_hyperedge(edge_id, members)
        
        return sn