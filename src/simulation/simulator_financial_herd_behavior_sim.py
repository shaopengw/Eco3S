from .simulator_imports import *

class FinancialHerdBehaviorSimSimulator:
    
    def __init__(self, **kwargs):
        self.map = kwargs.get('map')
        self.time = kwargs.get('time')
        self.population = kwargs.get('population')
        self.social_network = kwargs.get('social_network')
        self.residents = kwargs.get('residents')
        self.towns = kwargs.get('towns')
        self.config = kwargs.get('config')
        self.climate = kwargs.get('climate')
        self.government = kwargs.get('government')

        # 市场状态
        self.asset_price = 100.0
        self.asset_price_history = [100.0]
        self.trading_volume = 0
        self.buy_volume = 0
        self.sell_volume = 0
        self.market_volatility = 0.0
        self.average_satisfaction = None
        
        # 初始化居民资产
        self.initialize_resident_assets()

        # 结果记录
        self.results = self.init_results()
        self.start_time = None
        self.end_time = None

        # 数据文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
    
    def initialize_resident_assets(self):
        """初始化居民的资产和现金"""
        import random
        for resident in self.residents.values():
            # 给每个居民初始现金（1000-5000元）
            resident.cash = random.uniform(1000, 5000)
            # 初始持仓（0-10单位）
            resident.asset_holdings = random.randint(0, 10)
            # 记录投资决策
            resident.last_action = None

    def init_results(self):
        return {
            "years": [],
            "asset_price": [],
            "asset_price_volatility": [],
            "trading_volume": [],
            "buy_volume": [],
            "sell_volume": [],
            "buy_sell_ratio": [],
            "portfolio_concentration": [],
            "behavior_concentration": [],
            "total_market_value": [],
            "average_holdings": [],
            "average_cash": [],
            "population": [],
            "average_satisfaction": [],
        }

    async def run(self):


        self.start_time = datetime.now()


        while not self.time.is_end():


            self.print_time_step()


            await self.update_state()


            await self.execute_actions()


            self.collect_results()


            self.save_results(self.result_file, append=True)
            
            ResidentStateExporter.save_resident_data(self)

            self.time.step()


        self.end_time = datetime.now()


        self.display_total_simulation_time()

    def print_time_step(self):


        print(Back.GREEN + f"交易日:{self.time.current_time}" + Back.RESET)


        print(f"当前资产价格：{self.asset_price:.2f}")

    async def update_state(self):
        self.average_satisfaction = self.calculate_average_satisfaction()
        self.population.update_birth_rate(self.average_satisfaction)
        self.market_volatility = self.calculate_market_volatility()
        
        # 重置交易统计
        self.buy_volume = 0
        self.sell_volume = 0
        self.trading_volume = 0
        
        print(f"资产价格：{self.asset_price:.2f}，市场波动率：{self.market_volatility:.4f}")

    async def execute_actions(self):
        # 新居民出生
        new_count = int(self.population.birth_rate * self.population.get_population())
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
        print(f"新加入{new_count}名居民")

        # 收集居民决策
        tasks = []
        speech_tasks = []
        
        for resident_name in list(self.residents.keys()):
            resident = self.residents[resident_name]
            
            # 准备市场信息（通过kwargs传递，会被添加到additional_context）
            holdings = getattr(resident, 'asset_holdings', 0)
            cash = getattr(resident, 'cash', 0)
            
            market_info_text = (
                f"当前资产价格：{self.asset_price:.2f}元\n"
                f"市场波动率：{self.market_volatility:.4f}\n"
                f"你的持仓数量：{holdings}单位\n"
                f"你的现金：{cash:.2f}元\n"
                f"最近20交易日价格趋势：{self.get_price_trend_description()}"
            )
            
            # 更新居民寿命（每年）
            if resident.update_resident_status(0):
                del self.residents[resident_name]
                self.population.death()
                continue
            print(f"居民 {resident.resident_id} (正在决策...")
            task = resident.decide_action_by_llm(
                tax_rate=0.0,
                basic_living_cost=0.0,
                climate_impact=0.0,
                市场信息=market_info_text,
                current_year=self.time.current_time
            )
            tasks.append(task)

        # 执行决策
        if tasks:
            results = await asyncio.gather(*tasks)
            residents_list = list(self.residents.values())
            
            for i, result in enumerate(results):
                if i >= len(residents_list):
                    break
                    
                resident = residents_list[i]
                
                if isinstance(result, dict):
                    select = result.get('select', '3')
                    reason = result.get('reason', '')
                    speech = result.get('speech', '')
                    relation_type = result.get('relation_type', 'weak')
                    
                    # 执行交易决策
                    self.execute_trade(resident, select)
                    
                    if speech:
                        speech_tasks.append(asyncio.create_task(
                            self.social_network.spread_information(resident.resident_id, speech, relation_type)
                        ))
                        
                elif isinstance(result, tuple) and len(result) >= 2:
                    select = result[0]
                    reason = result[1]
                    
                    # 执行交易决策
                    self.execute_trade(resident, select)
                    
                    if len(result) >= 3:
                        speech = result[2]
                        relation_type = result[3] if len(result) >= 4 else 'weak'
                        if speech:
                            speech_tasks.append(asyncio.create_task(
                                self.social_network.spread_information(resident.resident_id, speech, relation_type)
                            ))
            
            if speech_tasks:
                await asyncio.gather(*speech_tasks)
        
        # 根据交易情况更新资产价格
        self.update_asset_price()
        
        # 定期更新社交网络
        current_year = self.time.current_time
        if current_year % random.randint(3, 5) == 0:
            self.social_network.update_network_edges()
    
    def execute_trade(self, resident, action):
        """执行交易操作"""
        action = str(action)
        
        if action == "1":  # 买入
            if resident.cash >= self.asset_price:
                resident.cash -= self.asset_price
                resident.asset_holdings += 1
                resident.last_action = "buy"
                self.buy_volume += 1
                self.trading_volume += 1
                # 买入提升少量满意度
                resident.satisfaction = min(100, resident.satisfaction + 2)
                
        elif action == "2":  # 卖出
            if resident.asset_holdings > 0:
                resident.cash += self.asset_price
                resident.asset_holdings -= 1
                resident.last_action = "sell"
                self.sell_volume += 1
                self.trading_volume += 1
                # 卖出提升少量满意度
                resident.satisfaction = min(100, resident.satisfaction + 2)
                
        elif action == "3":  # 持有
            resident.last_action = "hold"
            # 持有时满意度略微下降
            resident.satisfaction = max(0, resident.satisfaction - 1)

    def collect_results(self):


            """收集模拟结果数据"""


            # 计算买卖比率


            buy_sell_ratio = self.buy_volume / self.sell_volume if self.sell_volume > 0 else (


                float('inf') if self.buy_volume > 0 else 1.0


            )


            # 计算持仓集中度


            portfolio_concentration = self.calculate_portfolio_concentration()

            # 计算行为集中度（当期买/卖/持有中占比最大的一类）
            # 行为集中度 = max(buy_count, sell_count, hold_count) / 总行为数
            total_actions = 0
            buy_count = 0
            sell_count = 0
            hold_count = 0
            for r in self.residents.values():
                action = getattr(r, 'last_action', None)
                if action in ("buy", "sell", "hold"):
                    total_actions += 1
                    if action == "buy":
                        buy_count += 1
                    elif action == "sell":
                        sell_count += 1
                    elif action == "hold":
                        hold_count += 1
            if total_actions > 0:
                behavior_concentration = max(buy_count, sell_count, hold_count) / total_actions
            else:
                behavior_concentration = 0.0


            # 计算市场总市值


            total_market_value = sum(


                getattr(r, 'asset_holdings', 0) * self.asset_price + getattr(r, 'cash', 0)


                for r in self.residents.values()


            )


            # 计算平均持仓和现金


            if self.residents:


                average_holdings = sum(


                    getattr(r, 'asset_holdings', 0) for r in self.residents.values()


                ) / len(self.residents)


                average_cash = sum(


                    getattr(r, 'cash', 0) for r in self.residents.values()


                ) / len(self.residents)


            else:


                average_holdings = 0.0


                average_cash = 0.0


            # 记录结果


            self.results["years"].append(self.time.current_time)


            self.results["asset_price"].append(self.asset_price)


            self.results["asset_price_volatility"].append(self.market_volatility)


            self.results["trading_volume"].append(self.trading_volume)


            self.results["buy_volume"].append(self.buy_volume)


            self.results["sell_volume"].append(self.sell_volume)


            self.results["buy_sell_ratio"].append(buy_sell_ratio)


            self.results["portfolio_concentration"].append(portfolio_concentration)
            self.results["behavior_concentration"].append(behavior_concentration)


            self.results["total_market_value"].append(total_market_value)


            self.results["average_holdings"].append(average_holdings)


            self.results["average_cash"].append(average_cash)


            self.results["population"].append(self.population.get_population())


            self.results["average_satisfaction"].append(


                self.average_satisfaction if self.average_satisfaction is not None else 0.0


            )


            # 打印关键指标


            # 避免无卖出时出现 inf，便于阅读
            buy_sell_display = "only_buy(no_sell)" if buy_sell_ratio == float('inf') else f"{buy_sell_ratio:.2f}"
            print(f"持仓集中度：{portfolio_concentration:.4f}，交易量：{self.trading_volume}，买卖比：{buy_sell_display}")

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
            print(f"模拟结果已保存至 {filename}")

    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            print(f"总模拟时间: {total_time}")
    
    # ==================== 群体决策方法 ====================


    def calculate_average_satisfaction(self):
        if not self.residents:
            return 0.0
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values() if hasattr(resident, 'satisfaction'))
        return total_satisfaction / len(self.residents) if self.residents else 0.0

    def update_asset_price(self):
        """根据买卖压力更新资产价格"""
        if not self.residents:
            return
        
        net_demand = self.buy_volume - self.sell_volume
        
        # 价格变化模型：净需求影响价格
        # 价格变化 = 净需求比例 * 价格敏感度 * 当前价格
        total_population = len(self.residents)
        if total_population > 0:
            demand_ratio = net_demand / total_population
            price_sensitivity = 0.05  # 价格敏感度系数
            price_change = demand_ratio * price_sensitivity * self.asset_price
            
            # 添加随机波动（市场噪音）
            import random
            noise = random.uniform(-0.5, 0.5)
            
            self.asset_price = max(1.0, self.asset_price + price_change + noise)
            self.asset_price_history.append(self.asset_price)

    def calculate_market_volatility(self):
        """计算市场波动率"""
        if len(self.asset_price_history) < 2:
            return 0.0
        recent_prices = self.asset_price_history[-20:] if len(self.asset_price_history) >= 20 else self.asset_price_history
        if len(recent_prices) < 2:
            return 0.0
        returns = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] for i in range(1, len(recent_prices))]
        if not returns:
            return 0.0
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    def calculate_portfolio_concentration(self):
            """计算投资者持仓集中度
            持仓集中度使用赫芬达尔-赫希曼指数(HHI)的变体来衡量：
            - 计算每个投资者的资产配置比例（资产价值 / 总资产）
            - 对所有投资者的持仓集中度取平均值
            - 返回值范围0-1，值越大表示持仓越集中
            Returns:
                float: 平均持仓集中度
            """
            if not self.residents:
                return 0.0

            concentration_sum = 0.0
            valid_count = 0

            for resident in self.residents.values():
                # 获取居民的资产和现金
                holdings = getattr(resident, 'asset_holdings', 0)
                cash = getattr(resident, 'cash', 0)

                # 计算资产价值
                asset_value = holdings * self.asset_price
                total_value = asset_value + cash

                # 只统计有资产的投资者
                if total_value > 0:
                    # 计算资产占比和现金占比
                    asset_ratio = asset_value / total_value
                    cash_ratio = cash / total_value

                    # 使用HHI公式：集中度 = sum(比例^2)
                    # 两种资产的情况：HHI = asset_ratio^2 + cash_ratio^2
                    concentration = asset_ratio ** 2 + cash_ratio ** 2
                    concentration_sum += concentration
                    valid_count += 1

            if valid_count == 0:
                return 0.0

            # 返回平均集中度
            avg_concentration = concentration_sum / valid_count
            return avg_concentration
    
    def calculate_total_market_value(self):
        """计算市场总市值"""
        if not self.residents:
            return 0.0
        total_holdings = sum(getattr(resident, 'asset_holdings', 0) for resident in self.residents.values())
        return total_holdings * self.asset_price
    
    def calculate_average_holdings(self):
        """计算平均持仓数量"""
        if not self.residents:
            return 0.0
        total_holdings = sum(getattr(resident, 'asset_holdings', 0) for resident in self.residents.values())
        return total_holdings / len(self.residents)
    
    def calculate_average_cash(self):
        """计算平均现金持有量"""
        if not self.residents:
            return 0.0
        total_cash = sum(getattr(resident, 'cash', 0) for resident in self.residents.values())
        return total_cash / len(self.residents)
    
    def get_price_trend_description(self):
        """获取价格趋势描述"""
        if len(self.asset_price_history) < 2:
            return "价格稳定"
        
        recent_prices = self.asset_price_history[-20:] if len(self.asset_price_history) >= 20 else self.asset_price_history
        
        if len(recent_prices) < 2:
            return "价格稳定"
        
        # 计算趋势
        start_price = recent_prices[0]
        end_price = recent_prices[-1]
        change_percent = ((end_price - start_price) / start_price) * 100
        
        if change_percent > 10:
            return f"大幅上涨({change_percent:.1f}%)"
        elif change_percent > 3:
            return f"上涨({change_percent:.1f}%)"
        elif change_percent > -3:
            return f"震荡({change_percent:.1f}%)"
        elif change_percent > -10:
            return f"下跌({change_percent:.1f}%)"
        else:
            return f"大幅下跌({change_percent:.1f}%)"

    async def integrate_new_residents(self, new_residents):
        """整合新居民并初始化其资产"""
        if not new_residents:
            return
        
        import random
        # new_residents是字典，需要遍历其值
        for resident in new_residents.values():
            # 初始化新居民的资产
            resident.cash = random.uniform(1000, 5000)
            resident.asset_holdings = random.randint(0, 10)
            resident.last_action = None
        
        # 更新全局居民列表
        self.residents.update(new_residents)
        print(f"{len(new_residents)} 名新居民已出生")
        
        # 添加到城镇（如果towns有这个方法）
        if hasattr(self.towns, 'initialize_resident_groups'):
            self.towns.initialize_resident_groups(new_residents)
            print("新居民已加入各自城镇")
        
        # 添加到社交网络
        if new_residents:
            self.social_network.add_new_residents(new_residents)
            print(f"{len(new_residents)} 名新居民已加入社交网络")
