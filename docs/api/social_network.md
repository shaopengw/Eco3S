# Social Network 模块 API 文档

## 提示

**属性命名规范**：
- SocialNetwork 类的异质图属性名为 **`hetero_graph`**
- SocialNetwork 类的超图属性名为 **`hyper_graph`**

使用示例：
```python
# 正确 ✓
neighbors = social_network.hetero_graph.get_neighbors(node_id)
groups = social_network.hyper_graph.get_hyperedges()
```

## 核心类结构

### HeterogeneousGraph
异质图系统，管理节点间的直接关系。

#### 主要方法
- add_node(node_id, node_type) - 添加节点
- add_edge(node1_id, node2_id, edge_type) - 添加边
- get_neighbors(node_id, edge_type=None) - 获取邻居节点
- remove_node(node_id) - 移除节点
- visualize() - 可视化异质图

### Hypergraph
超图系统，管理群组关系。

#### 主要方法
- add_node(node) - 添加节点
- add_hyperedge(group_id, members) - 添加超边（群组）
- get_neighbors(node) - 获取邻居节点
- get_hyperedge_nodes(hyperedge_id) - 获取群组成员
- remove_node(node) - 移除节点
- visualize() - 可视化超图

### SocialNetwork
社交网络主类，整合异质图和超图功能。

#### 初始化参数
无需参数，自动创建异质图和超图实例。

#### 类属性
- **hetero_graph**: HeterogeneousGraph - 异质图实例
- **hyper_graph**: Hypergraph - 超图实例
- **residents**: dict - 居民字典 {resident_id: resident_object}

**重要提示**：访问异质图时使用 `social_network.hetero_graph`，访问超图时使用 `social_network.hyper_graph`。

#### 主要方法

##### initialize_network
- 功能：初始化社交网络
- 参数：
  - residents: dict - 居民字典
  - towns: Towns - 城镇系统
- 返回：无

##### spread_information
- 功能：在异质图中传播信息
- 参数：
  - resident_id: int - 发送者ID
  - message: str - 信息内容
  - relation_type: str - 关系类型
  - current_depth: int - 当前深度
  - max_depth: int - 最大深度
- 返回：无

##### spread_information_in_group
- 功能：在群组中传播信息
- 参数：
  - group_id: str - 群组ID
  - message: str - 信息内容
  - current_depth: int - 当前深度
  - max_depth: int - 最大深度
- 返回：无

##### add_new_residents
- 功能：添加新居民到网络
- 参数：
  - new_residents: dict - 新居民字典
- 返回：无

##### update_network_edges
- 功能：更新社交网络边
- 参数：
  - update_ratio: float - 更新比例(0-1)
- 返回：无

## 数据结构

### 边类型
- friend: 朋友关系
- colleague: 同事关系
- family: 家庭关系
- hometown: 同乡关系

### 群组ID格式
- family_[id]: 家庭群组
- hometown_[town]: 同乡群组

## 外部依赖
- networkx: 异质图实现
- hypernetx: 超图实现
- numpy: 数据处理
- sklearn.cluster: 群组划分
- matplotlib: 可视化