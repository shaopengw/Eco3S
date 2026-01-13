from .simulator_imports import *

class PricingModelSimulationSimulator:
    
    def __init__(self, **kwargs):


    
            self.logger = LogManager.get_logger('simulator', console_output=True)


    
            self.map = kwargs.get('map')

    
            self.time = kwargs.get('time')

    
            self.population = kwargs.get('population')

    
            self.social_network = kwargs.get('social_network')

    
            self.residents = kwargs.get('residents')

    
            self.towns = kwargs.get('towns')

    
            self.config = kwargs.get('config')


    
            self.basic_living_cost = 10

    
            self.gdp = 0


    
            self.average_satisfaction = None


    
            self.initial_price = 50

    
            self.demand_elasticity = 0.5

    
            self.storage_cost_rate = 0.1

    
            self.storage_depreciation = 0.05

    
            self.price_adjustment_step = 0.1

    
            self.storage_capacity = 100


    
            self.results = self.init_results()

    
            self.start_time = None

    
            self.end_time = None


    
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    
            pid = os.getpid()

    
            data_dir = SimulationContext.get_data_dir()

    
            SimulationContext.ensure_directories()

    
            self.result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
    
    def init_results(self):

    
            return {

    
                "years": [],

    
                "equilibrium_price": [],

    
                "inventory_level": [],

    
                "stockout_probability": [],

    
                "average_satisfaction": [],

    
                "population": [],

    
                "gdp": [],

    
            }

    async def run(self):


            self.start_time = datetime.now()


            while not self.time.is_end():


                self.print_time_step()


                await self.update_state()


                await self.execute_actions()


                self.collect_results()


                self.save_results(self.result_file, append=True)


                self.time.step()


            self.end_time = datetime.now()


            self.display_total_simulation_time()

    def print_time_step(self):


            print(Back.GREEN + f"时段:{self.time.current_time}" + Back.RESET)


            self.logger.info(f"时段:{self.time.current_time}")

    async def update_state(self):


            self.gdp = self.calculate_gdp()


            self.average_satisfaction = self.calculate_average_satisfaction()


            self.population.update_birth_rate(self.average_satisfaction)


            self.logger.info(f"GDP：{self.gdp}")

    async def execute_actions(self):
        """执行居民的购买、存储和价格调整行为"""
        
        # 1. 居民出生
        new_count = int(self.population.birth_rate * self.population.get_population())
        if new_count > 0:
            from src.agents.resident_agent_generator import generate_new_residents
            new_residents = await generate_new_residents(
                count=new_count,
                map=self.map,
                residents=self.residents,
                social_network=self.social_network,
                resident_prompt_path=self.config["data"]["resident_prompt_path"],
                resident_actions_path=self.config["data"]["resident_actions_path"],
            )
            await self.integrate_new_residents(new_residents)
            self.population.birth(new_count)
            self.logger.info(f"新加入{new_count}名居民")
        
        # 2. 计算当前市场均衡价格
        current_price = self.calculate_equilibrium_price()
        self.logger.info(f"当前市场均衡价格: {current_price:.2f}")
        
        # 3. 居民通过LLM做决策（并发执行）
        tasks = []
        valid_residents = []  # 存储有效居民的引用
        
        for resident_name in list(self.residents.keys()):
            resident = self.residents[resident_name]
            
            # 更新居民寿命并处理死亡（在创建任务前检查）
            if resident.update_resident_status(self.basic_living_cost):
                del self.residents[resident_name]
                self.population.death()
                continue
            
            # 构建决策上下文
            wealth = getattr(resident, 'wealth', 100)
            inventory = getattr(resident, 'inventory', 0)
            price_sensitivity = getattr(resident, 'price_sensitivity', self.demand_elasticity)
            
            # 使用LLM决策，通过kwargs传递市场信息
            task = resident.decide_action_by_llm(
                tax_rate=0,  # 定价模型不涉及税率
                basic_living_cost=self.basic_living_cost,
                climate_impact=0,  # 定价模型不涉及气候
                当前市场价格=f"{current_price:.2f}单位",
                我的财富=f"{wealth:.2f}单位",
                我的库存=f"{inventory:.2f}单位",
                存储容量=f"{self.storage_capacity}单位",
                存储成本率=f"{self.storage_cost_rate * 100}%",
                存储折旧率=f"{self.storage_depreciation * 100}%",
                我的价格敏感度=f"{price_sensitivity:.2f}"
            )
            tasks.append(task)
            valid_residents.append(resident)
        
        # 并发执行所有居民决策
        if tasks:
            results = await asyncio.gather(*tasks)
            
            # 映射action编号到action名称
            action_map = {
                1: 'purchase',
                2: 'store',
                3: 'adjust_price',
                '1': 'purchase',
                '2': 'store',
                '3': 'adjust_price'
            }
            
            for i, result in enumerate(results):
                if i >= len(valid_residents):
                    break
                    
                resident = valid_residents[i]
                
                # result可能是元组(select, reason)或字典
                action = None
                purchase_amount = 10  # 默认值
                sell_amount = 0       # 默认值
                
                if isinstance(result, tuple) and len(result) >= 1:
                    select = result[0]
                    action = action_map.get(select)
                elif isinstance(result, dict):
                    select = result.get('select')
                    action = action_map.get(select)
                    purchase_amount = result.get('purchase_amount', 10)
                    sell_amount = result.get('sell_amount', 0)
                
                # 处理不同的行动
                if action == 'purchase':
                    result_dict = {'purchase_amount': purchase_amount} if isinstance(result, tuple) else result
                    self.handle_purchase(resident, result_dict, current_price)
                elif action == 'store':
                    result_dict = {'sell_amount': sell_amount} if isinstance(result, tuple) else result
                    self.handle_store(resident, result_dict, current_price)
                elif action == 'adjust_price':
                    self.handle_maintain(resident, result if isinstance(result, dict) else {})
        
        # 4. 自动扣除存储成本和应用折旧
        for resident in self.residents.values():
            inventory = getattr(resident, 'inventory', 0)
            if inventory > 0:
                # 扣除存储成本
                storage_cost = inventory * self.storage_cost_rate
                wealth = getattr(resident, 'wealth', 0)
                resident.wealth = max(0, wealth - storage_cost)
                
                # 应用库存折旧
                resident.inventory = inventory * (1 - self.storage_depreciation)
                resident.inventory = min(resident.inventory, self.storage_capacity)

    def collect_results(self):
            equilibrium_price = self.calculate_equilibrium_price()
            inventory_level = self.calculate_total_inventory()
            stockout_prob = self.calculate_stockout_probability()

            # 注意：居民出生已在execute_actions中处理，这里不再重复

            self.results["years"].append(self.time.current_time)
            self.results["equilibrium_price"].append(equilibrium_price)
            self.results["inventory_level"].append(inventory_level)
            self.results["stockout_probability"].append(stockout_prob)
            self.results["average_satisfaction"].append(self.average_satisfaction)
            self.results["population"].append(self.population.get_population())
            self.results["gdp"].append(self.gdp)


            self.logger.info(f"时段: {self.time.current_time}, "
                  f"人口数量: {self.population.get_population()}, "
                  f"均衡价格: {equilibrium_price:.2f}, "
                  f"库存水平: {inventory_level:.2f}, "
                  f"断档概率: {stockout_prob:.2%}, "
                  f"平均满意度: {self.average_satisfaction:.2f}, "
                  f"GDP: {self.gdp:.2f}"
            )

    def save_results(self, filename=None, append=False):
        """保存结果到CSV文件"""
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突
            filename = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
        
        if append:
            last_row_data = {key: [value[-1]] for key, value in self.results.items() if value}
            df = pd.DataFrame(last_row_data)
        else:
            df = pd.DataFrame(self.results)
        
        if append and os.path.exists(filename):
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            df.to_csv(filename, index=False)
        
        if not append:
            self.logger.info(f"模拟结果已完整保存至 {filename}")

    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            self.logger.info(f"总模拟时间: {total_time}")
    
    # ==================== 群体决策方法 ====================
    
    def calculate_gdp(self):

    
            if not self.residents:

    
                return 0.0

    
            total_income = sum(resident.income for resident in self.residents.values())

    
            return total_income
    
    def calculate_average_satisfaction(self):

    
            if not self.residents:

    
                self.logger.warning("没有居民，平均满意度为 0.0")

    
                return 0.0


    
            total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())

    
            average_satisfaction = total_satisfaction / self.population.population

    
            return average_satisfaction
    
    def get_basic_living_cost(self):
        """获取当前基本生活所需值"""
        return self.basic_living_cost
    
    async def integrate_new_residents(self, new_residents):
            """整合新居民到模拟系统"""
            if not new_residents:
                return

            # 为新居民初始化定价模型相关属性
            for resident in new_residents.values():
                if not hasattr(resident, 'inventory'):
                    resident.inventory = 0
                if not hasattr(resident, 'price_sensitivity'):
                    resident.price_sensitivity = self.demand_elasticity
                if not hasattr(resident, 'wealth'):
                    # 初始财富基于收入，给予一定的随机性
                    resident.wealth = resident.income * random.uniform(0.8, 1.5)

            self.residents.update(new_residents)
            self.logger.info(f"{len(new_residents)} 名新居民已加入市场")
            
            # 将新居民加入城镇
            self.towns.initialize_resident_groups(new_residents)
            self.logger.info("新居民已加入各自城镇")
            
            # 更新社交网络
            if new_residents:
                self.social_network.add_new_residents(new_residents)

    def calculate_equilibrium_price(self):
            total_demand = 0
            total_supply = 0
            for resident in self.residents.values():
                price_sensitivity = getattr(resident, 'price_sensitivity', self.demand_elasticity)
                wealth = getattr(resident, 'wealth', 100)  # 假设默认财富为100
                demand = max(0, 100 * (self.initial_price / max(1, wealth)) ** price_sensitivity)
                total_demand += demand
                inventory = getattr(resident, 'inventory', 0)
                total_supply += inventory

            if total_demand == 0:
                return self.initial_price

            supply_demand_ratio = total_supply / total_demand
            
            # 如果供应为0，价格应该很高（供不应求）
            if supply_demand_ratio == 0:
                return self.initial_price * 2  # 价格翻倍
            
            price = self.initial_price * (supply_demand_ratio ** (-self.demand_elasticity))

            return price


    def calculate_total_inventory(self):


            total_inventory = 0


            for resident in self.residents.values():


                inventory = getattr(resident, 'inventory', 0)


                total_inventory += inventory


            return total_inventory


    def calculate_stockout_probability(self):
            if not self.residents:
                return 0.0

            stockout_count = 0
            for resident in self.residents.values():
                inventory = getattr(resident, 'inventory', 0)
                if inventory <= 0:
                    stockout_count += 1

            return stockout_count / len(self.residents)
    
    # ==================== 行为处理方法 ====================
    
    def handle_purchase(self, resident, result, current_price):
        """处理居民购买行为"""
        purchase_amount = result.get('purchase_amount', 10)
        wealth = getattr(resident, 'wealth', 0)
        
        # 限制购买量不超过财富允许的范围
        max_affordable = wealth / max(1, current_price)
        actual_purchase = min(purchase_amount, max_affordable, 50)  # 最多购买50单位
        
        if actual_purchase > 0:
            cost = actual_purchase * current_price
            resident.wealth = wealth - cost
            resident.inventory = getattr(resident, 'inventory', 0) + actual_purchase
            self.logger.info(f"{resident.resident_id} 购买了 {actual_purchase:.2f} 单位商品，花费 {cost:.2f}，剩余财富 {resident.wealth:.2f}")
    
    def handle_store(self, resident, result, current_price):
        """处理居民出售库存"""
        sell_amount = result.get('sell_amount', 0)
        inventory = getattr(resident, 'inventory', 0)
        
        # 限制出售量不超过现有库存
        actual_sell = min(sell_amount, inventory)
        
        if actual_sell > 0:
            revenue = actual_sell * current_price
            resident.wealth = getattr(resident, 'wealth', 0) + revenue
            resident.inventory = inventory - actual_sell
            self.logger.info(f"{resident.resident_id} 出售了 {actual_sell:.2f} 单位商品，获得 {revenue:.2f}，当前财富 {resident.wealth:.2f}")
    
    def handle_maintain(self, resident, result):
        """处理居民维持策略"""
        # 可以根据当前库存水平微调价格敏感度
        inventory = getattr(resident, 'inventory', 0)
        price_sensitivity = getattr(resident, 'price_sensitivity', self.demand_elasticity)
        
        if inventory > 50:
            price_sensitivity += self.price_adjustment_step
        elif inventory < 20:
            price_sensitivity -= self.price_adjustment_step
        
        resident.price_sensitivity = max(0.1, min(1.0, price_sensitivity))
        self.logger.debug(f"{resident.resident_id} 维持当前策略，价格敏感度: {resident.price_sensitivity:.2f}")
