# simulator_template.py
"""
Simulator 代码格式参考模板
此文件仅作为代码结构参考，供代码生成Agent使用

【重要说明】
- 使用 **kwargs 灵活接收参数，适应不同实验需求
- 所有 simulator 必须统一导入：from .simulator_imports import *
- 结果保存必须使用 SimulationContext 管理路径
- 主循环必须是 async 函数，支持并发操作
"""

from .simulator_imports import *

class YourSimulator:
    """
    模拟器模板类
    
    必须实现的核心方法：
    1. __init__: 初始化所有组件
    2. init_results: 定义结果数据结构
    3. run: 主运行循环
    4. prepare_experiment: 实验准备（可选）
    5. update_state: 更新系统状态
    6. execute_actions: 执行智能体行为
    7. collect_results: 收集数据
    8. save_results: 保存结果
    """
    
    def __init__(self, **kwargs):
        """
        初始化模拟器，参数通过kwargs灵活传递
        
        【核心对象】必须接收的参数：
        - map: 地图对象
        - time: 时间对象
        - population: 人口对象
        - social_network: 社交网络对象
        - residents: 居民字典
        - towns: 城镇对象
        - config: 配置字典
        
        【可选对象】根据实验需求选择：
        - government: 政府对象
        - government_officials: 政府官员字典
        - rebellion: 叛军对象
        - rebels_agents: 叛军字典
        - transport_economy: 运输经济对象
        - climate: 气候对象
        """
        # === 核心对象（必需） ===
        self.map = kwargs.get('map')
        self.time = kwargs.get('time')
        self.population = kwargs.get('population')
        self.social_network = kwargs.get('social_network')
        self.residents = kwargs.get('residents')
        self.towns = kwargs.get('towns')
        self.config = kwargs.get('config')
        
        # === 可选对象（根据实验需求） ===
        self.government = kwargs.get('government')
        self.government_officials = kwargs.get('government_officials')
        self.rebellion = kwargs.get('rebellion')
        self.rebels_agents = kwargs.get('rebels_agents')
        self.transport_economy = kwargs.get('transport_economy')
        self.climate = kwargs.get('climate')
        
        # === 实验特定参数（可选） ===
        # 例如：self.propaganda_prob = kwargs.get('propaganda_prob', 0.1)
        
        # === 状态变量 ===
        self.results = self.init_results()
        self.start_time = None
        self.end_time = None
        
        # === 结果文件路径（推荐在 __init__ 中创建） ===
        # 使用 SimulationContext 确保路径正确
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}.csv")
        # 如果保存为 JSON，使用: f"running_data_{timestamp}.json"

    def init_results(self):
        """
        初始化结果数据结构
        
        【返回格式】
        - CSV 格式：字典，键为列名，值为列表
          例如: {'years': [], 'population': [], 'gdp': []}
        - JSON 格式：任意可序列化的数据结构
        
        【示例】
        return {
            'years': [],
            'population': [],
            'gdp': [],
            'average_satisfaction': [],
            'unemployment_rate': []
        }
        """
        return {}

    async def run(self):
        """
        主运行流程：初始化→主循环→结束
        
        【标准流程】
        1. 记录开始时间
        2. 准备实验（可选）
        3. 主循环：
           - 打印当前时间步
           - 更新系统状态
           - 执行智能体行为
           - 收集结果
           - 保存结果（增量保存）
           - 推进时间
        4. 记录结束时间并显示
        """
        self.start_time = datetime.now()
        
        # 可选：实验准备工作
        self.prepare_experiment()
        
        # 主循环
        while not self.time.is_end():
            # 1. 打印时间步信息
            self.print_time_step()
            
            # 2. 更新系统状态（经济、气候、人口等）
            await self.update_state()
            
            # 3. 执行智能体行为（政府、叛军、居民等）
            await self.execute_actions()
            
            # 4. 收集本轮结果
            self.collect_results()
            
            # 5. 保存结果（增量追加模式）
            self.save_results(self.result_file, append=True)
            
            # 6. 推进时间
            self.time.step()
        
        # 结束统计
        self.end_time = datetime.now()
        self.display_total_simulation_time()

    def prepare_experiment(self):
        """
        实验准备工作（可选）
        
        【适用场景】
        - 需要打印实验信息
        - 初始化特定变量
        - 保存初始状态到结果中
        
        【示例】
        print(f"实验名称：{self.config.get('simulation_name')}")
        print(f"实验目标：{self.config.get('objectives')}")
        
        # 保存初始数据
        self.results['years'].append('初始')
        self.results['population'].append(self.population.get_population())
        """
        pass

    def print_time_step(self):
        """
        打印当前时间步信息
        
        【标准格式】
        使用 colorama 的 Back.GREEN 高亮显示当前时间
        """
        print(Back.GREEN + f"年份:{self.time.get_current_time()}" + Back.RESET)

    async def update_state(self):
        """
        更新系统状态（异步方法）
        
        【常见操作】
        1. 更新气候影响因子
        2. 更新经济指标（GDP、税收等）
        3. 更新环境状态（运河、资源等）
        4. 更新人口统计（出生率、满意度等）
        
        【示例】
        # 更新气候
        if self.climate:
            climate_impact = self.climate.get_current_impact(
                self.time.get_current_year(), 
                self.time.get_start_time()
            )
            print(f"气候影响因子: {climate_impact}")
        
        # 更新经济
        if self.government:
            self.gdp = self.calculate_gdp()
            tax_income = self.gdp * self.government.get_tax_rate()
            self.government.budget += tax_income
        
        # 更新人口
        self.average_satisfaction = self.calculate_average_satisfaction()
        self.population.update_birth_rate(self.average_satisfaction)
        """
        pass

    async def execute_actions(self):
        """
        执行所有智能体的决策和行为（异步方法）
        
        【常见操作】
        1. 政府决策（如果启用）
        2. 叛军决策（如果启用）
        3. 居民行为（并发执行）
        
        【并发执行示例】
        # 并发执行所有居民行为
        tasks = []
        for resident in self.residents.values():
            task = resident.decide_action_by_llm(
                tax_rate=self.government.get_tax_rate(),
                living_cost=self.basic_living_cost
            )
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks)
            # 处理结果...
        
        【群体决策示例】
        if self.government:
            government_config = {
                'agents': self.government_officials,
                'ordinary_type': OrdinaryGovernmentAgent,
                'leader_type': HighRankingGovernmentAgent
            }
            decision = await self.collect_group_decision('government', government_config)
            if decision:
                self.execute_government_decision(decision)
        """
        pass

    def collect_results(self):
        """
        收集本轮结果数据
        
        【标准操作】
        将当前时间步的所有关键指标添加到 self.results 中
        
        【示例】
        self.results['years'].append(self.time.get_current_time())
        self.results['population'].append(self.population.get_population())
        self.results['gdp'].append(self.gdp)
        self.results['average_satisfaction'].append(self.average_satisfaction)
        
        if self.government:
            self.results['government_budget'].append(self.government.get_budget())
            self.results['tax_rate'].append(self.government.get_tax_rate())
        
        if self.rebellion:
            self.results['rebellion_strength'].append(self.rebellion.get_strength())
        """
        pass

    def save_results(self, filename=None, append=False):
        """
        保存结果到文件
        
        【必须使用 SimulationContext】
        确保文件保存到正确的目录
        
        【参数说明】
        - filename: 文件路径（None 则自动生成）
        - append: 是否追加模式（增量保存推荐 True）
        
        【CSV 保存示例】
        # 使用 SimulationContext 获取数据目录
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(data_dir, f"running_data_{timestamp}.csv")
        
        # 转换为 DataFrame
        df = pd.DataFrame(self.results)
        
        # 追加或覆盖写入
        if append and os.path.exists(filename):
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            df.to_csv(filename, index=False)
        
        【JSON 保存示例】
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(data_dir, f"running_data_{timestamp}.json")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        """
        pass

    def display_total_simulation_time(self):
        """
        显示总模拟时间
        
        【标准格式】
        计算并打印从 start_time 到 end_time 的时间差
        """
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")
    
    # ==================== 辅助方法示例 ====================
    
    async def collect_group_decision(self, group_type, config, max_rounds=2):
        """
        收集群体决策（可选方法）
        
        【适用场景】
        启用政府或叛军的群体决策机制
        
        【参数】
        - group_type: 'government' 或 'rebellion'
        - config: 包含 agents, ordinary_type, leader_type 的字典
        - max_rounds: 最大讨论轮数
        
        【返回】
        决策结果（字符串或字典）
        """
        pass
    
    def execute_government_decision(self, decision):
        """执行政府决策（可选方法）"""
        pass
    
    def execute_rebellion_decision(self, decision):
        """执行叛军决策（可选方法）"""
        pass
    
    def calculate_gdp(self):
        """计算 GDP（可选方法）"""
        if not self.residents:
            return 0
        total_income = sum(
            resident.income for resident in self.residents.values()
        )
        return total_income
    
    def calculate_average_satisfaction(self):
        """计算平均满意度（可选方法）"""
        if not self.residents:
            return 0
        total_satisfaction = sum(
            resident.satisfaction for resident in self.residents.values()
        )
        return total_satisfaction / len(self.residents)
    
    async def integrate_new_residents(self, new_residents):
        """整合新居民到系统（可选方法）"""
        if not new_residents:
            return
        
        # 更新全局居民列表
        self.residents.update(new_residents)
        print(f"{len(new_residents)} 名新居民已出生")
        
        # 添加到城镇
        self.towns.initialize_resident_groups(new_residents)
        
        # 添加到社交网络
        if new_residents:
            self.social_network.add_new_residents(list(new_residents.values()))