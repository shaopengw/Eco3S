from .simulator_imports import *

class PriceDiscoverySimulationSimulator:
    
    def __init__(self, **kwargs):

    
        self.logger = LogManager.get_logger('simulator', console_output=True)


    
        self.map = kwargs.get('map')

    
        self.time = kwargs.get('time')

    
        self.population = kwargs.get('population')

    
        self.social_network = kwargs.get('social_network')

    
        self.residents = kwargs.get('residents')

    
        self.towns = kwargs.get('towns')

    
        self.config = kwargs.get('config')


    
        self.initial_stock_price = self.config['simulation'].get('initial_stock_price', 100)

    
        self.trade_frequency = self.config['simulation'].get('trade_frequency', 1)

    
        self.price_update_interval = self.config['simulation'].get('price_update_interval', 1)


    
        self.exchanges = self.initialize_exchanges()

    
        self.stock_holders = list(self.residents.values())


    
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

    
                "exchange_A_price": [],

    
                "exchange_B_price": [],

    
                "common_efficient_price": [],

    
                "exchange_A_volume": [],

    
                "exchange_B_volume": [],

    
                "exchange_A_contribution": [],

    
                "exchange_B_contribution": [],

    
                "price_discovery_efficiency": [],

    
                "price_stability": [],

    
                "price_convergence_rate": [],

    
                "price_variance": [],

    
                "average_price_deviation": [],

    
                "cumulative_efficiency": [],

    
                "population": [],

    
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


            # 模拟结束后进行价格趋势分析


            self.logger.info("模拟结束，开始进行价格趋势分析...")


            analysis_results = self.analyze_price_trends()


            # 保存分析结果


            if analysis_results:


                analysis_file = self.result_file.replace('.csv', '_analysis.json')


                import json


                with open(analysis_file, 'w') as f:


                    json.dump(analysis_results, f, indent=2)


                self.logger.info(f"价格趋势分析结果已保存至 {analysis_file}")


            self.end_time = datetime.now()


            self.display_total_simulation_time()

    def print_time_step(self):


        print(Back.GREEN + f"年份:{self.time.current_time}" + Back.RESET)


        self.logger.info(f"年份:{self.time.current_time}")

    async def update_state(self):


        if self.time.current_time % self.price_update_interval == 0:


            self.update_exchange_prices()


        common_price = self.calculate_common_efficient_price()


        self.calculate_exchange_contributions(common_price)


        self.logger.info(f"交易所A价格: {self.exchanges['exchange_A']['current_price']:.2f}, 交易所B价格: {self.exchanges['exchange_B']['current_price']:.2f}")


        self.logger.info(f"共同有效价格: {common_price:.2f}")

    async def execute_actions(self):
            # 计算平均满意度并更新出生率
            average_satisfaction = self.calculate_average_satisfaction()
            self.population.update_birth_rate(average_satisfaction)
            
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


            self.logger.info(f"新加入{new_count}名股票持有者，当前出生率: {self.population.birth_rate:.4f}")

            # 收集居民决策任务
            tasks = []
            speech_tasks = []
            # 构建市场信息供居民决策参考
            market_info = f"交易所A当前价格: {self.exchanges['exchange_A']['current_price']:.2f}, " \
                          f"交易所B当前价格: {self.exchanges['exchange_B']['current_price']:.2f}"

            for resident in list(self.residents.values()):

                # 基于LLM的决策
                task = resident.decide_action_by_llm(
                    market_info=market_info,
                    exchange_A_price=self.exchanges['exchange_A']['current_price'],
                    exchange_B_price=self.exchanges['exchange_B']['current_price']
                )
                tasks.append(task)


            if tasks:


                results = await asyncio.gather(*tasks)
                # 处理返回的结果
                residents_list = list(self.residents.values())
                for i, result in enumerate(results):
                    if i >= len(residents_list):  # 安全检查
                        break
                    resident = residents_list[i]
                    
                    # 记录交易行为
                    select = None
                    
                    if isinstance(result, tuple) and len(result) == 4:
                        # 处理带有发言的决策结果
                        select, reason, speech, relation_type = result
                        # 执行决策
                        await resident.execute_decision(select)
                        # 收集发言传播任务
                        speech_tasks.append(asyncio.create_task(
                            self.social_network.spread_speech_in_network(resident.resident_id, speech, relation_type)
                        ))
                    elif isinstance(result, tuple) and len(result) == 2:
                        # 处理普通决策结果
                        select, reason = result
                        # 执行决策
                        await resident.execute_decision(select)
                    
                    # 根据决策更新交易量统计
                    if select:
                        select_int = int(select) if isinstance(select, str) and select.isdigit() else select
                        if select_int == 1:  # 在交易所A卖出
                            self.exchanges['exchange_A']['trade_volume'] += 1
                        elif select_int == 2:  # 在交易所B卖出
                            self.exchanges['exchange_B']['trade_volume'] += 1
                        elif select_int == 3:  # 在交易所A买入
                            self.exchanges['exchange_A']['trade_volume'] += 1
                        elif select_int == 4:  # 在交易所B买入
                            self.exchanges['exchange_B']['trade_volume'] += 1
                        # select_int == 5 是观察市场，不增加交易量
                
                # 并发执行所有发言传播任务
                if speech_tasks:
                    await asyncio.gather(*speech_tasks)
            
            # 检查居民寿命并处理死亡（每年）
            for resident_id in list(self.residents.keys()):
                resident = self.residents.get(resident_id)
                if resident and resident.update_resident_status(0):
                    # 居民死亡，从字典中移除
                    del self.residents[resident_id]
                    self.population.death()


            current_year = self.time.current_time


            if current_year % random.randint(3, 5) == 0:


                self.social_network.update_network_edges()

    def collect_results(self):


            common_price = self.calculate_common_efficient_price()


            # 计算价格方差


            price_variance = sum(


                (ex['current_price'] - common_price) ** 2 


                for ex in self.exchanges.values()


            ) / len(self.exchanges)


            # 计算价格稳定性


            price_stability = 1 / (1 + price_variance)


            # 计算价格发现效率（基于贡献分数）


            price_discovery_efficiency = sum(


                ex['contribution_score'] for ex in self.exchanges.values()


            ) / len(self.exchanges)


            # 计算价格收敛率（当前时间步与上一时间步的价格差异变化）


            price_convergence_rate = 0.0


            if len(self.results["years"]) > 0:


                prev_variance = self.results["price_variance"][-1] if self.results["price_variance"] else price_variance


                if prev_variance > 0:


                    price_convergence_rate = (prev_variance - price_variance) / prev_variance


            # 计算平均价格偏差（各交易所价格与共同有效价格的平均偏差）


            average_price_deviation = sum(


                abs(ex['current_price'] - common_price)


                for ex in self.exchanges.values()


            ) / len(self.exchanges)


            # 计算累积效率（历史平均价格发现效率）


            if len(self.results["price_discovery_efficiency"]) > 0:


                cumulative_efficiency = (sum(self.results["price_discovery_efficiency"]) + price_discovery_efficiency) / (len(self.results["price_discovery_efficiency"]) + 1)


            else:


                cumulative_efficiency = price_discovery_efficiency


            # 记录所有结果


            self.results["years"].append(self.time.current_time)


            self.results["exchange_A_price"].append(self.exchanges['exchange_A']['current_price'])


            self.results["exchange_B_price"].append(self.exchanges['exchange_B']['current_price'])


            self.results["common_efficient_price"].append(common_price)


            self.results["exchange_A_volume"].append(self.exchanges['exchange_A']['trade_volume'])


            self.results["exchange_B_volume"].append(self.exchanges['exchange_B']['trade_volume'])


            self.results["exchange_A_contribution"].append(self.exchanges['exchange_A']['contribution_score'])


            self.results["exchange_B_contribution"].append(self.exchanges['exchange_B']['contribution_score'])


            self.results["price_discovery_efficiency"].append(price_discovery_efficiency)


            self.results["price_stability"].append(price_stability)


            self.results["price_convergence_rate"].append(price_convergence_rate)


            self.results["price_variance"].append(price_variance)


            self.results["average_price_deviation"].append(average_price_deviation)


            self.results["cumulative_efficiency"].append(cumulative_efficiency)


            self.results["population"].append(self.population.get_population())


            # 增强日志输出，包含更多统计指标


            self.logger.info(f"年份: {self.time.current_time}, "


                  f"共同有效价格: {common_price:.2f}, "


                  f"价格发现效率: {price_discovery_efficiency:.4f}, "


                  f"价格稳定性: {price_stability:.4f}, "


                  f"价格方差: {price_variance:.4f}, "


                  f"价格收敛率: {price_convergence_rate:.4f}, "


                  f"平均价格偏差: {average_price_deviation:.4f}, "


                  f"累积效率: {cumulative_efficiency:.4f}, "


                  f"人口: {self.population.get_population()}")


            # 重置交易量


            for exchange_id in self.exchanges:


                self.exchanges[exchange_id]['trade_volume'] = 0

    def save_results(self, filename=None, append=False):


            data_dir = SimulationContext.get_data_dir()


            SimulationContext.ensure_directories()


            if filename is None:


                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


                pid = os.getpid()


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


            if self.start_time and self.end_time:


                total_time = self.end_time - self.start_time


                self.logger.info(f"总模拟时间: {total_time}")
    
    async def integrate_new_residents(self, new_residents):

    
            if not new_residents:

    
                return

    
            self.residents.update(new_residents)

    
            self.logger.info(f"{len(new_residents)} 名新股票持有者已加入，目前出生率: {self.population.birth_rate:.4f}")

    
            self.towns.initialize_resident_groups(new_residents)

    
            self.logger.info("新股票持有者已加入各自城镇")

    
            if new_residents:

    
                self.social_network.add_new_residents(new_residents)

    
                self.logger.info(f"{len(new_residents)} 名新股票持有者已加入社交网络")

    def initialize_exchanges(self):


            """初始化两个交易所"""


            exchanges = {


                'exchange_A': {


                    'name': '交易所A',


                    'current_price': self.initial_stock_price,


                    'quote_history': [],


                    'trade_volume': 0,


                    'contribution_score': 0


                },


                'exchange_B': {


                    'name': '交易所B',


                    'current_price': self.initial_stock_price,


                    'quote_history': [],


                    'trade_volume': 0,


                    'contribution_score': 0


                }


            }


            return exchanges


    def update_exchange_prices(self):


            """更新交易所价格"""


            for exchange_id, exchange in self.exchanges.items():


                volatility = random.uniform(-0.02, 0.02)


                new_price = exchange['current_price'] * (1 + volatility)


                exchange['current_price'] = max(1, new_price)


                exchange['quote_history'].append(new_price)


    def calculate_common_efficient_price(self):


            """计算共同有效价格"""


            total_volume = sum(ex['trade_volume'] for ex in self.exchanges.values())


            if total_volume == 0:


                return sum(ex['current_price'] for ex in self.exchanges.values()) / len(self.exchanges)


            weighted_price = sum(


                ex['current_price'] * ex['trade_volume'] / total_volume 


                for ex in self.exchanges.values()


            )


            return weighted_price


    def calculate_exchange_contributions(self, common_price):


            """计算各交易所对共同有效价格的贡献度"""


            for exchange_id, exchange in self.exchanges.items():


                price_diff = abs(exchange['current_price'] - common_price)


                contribution = 1 / (1 + price_diff) if price_diff > 0 else 1


                exchange['contribution_score'] = contribution


    async def execute_trade(self, resident, exchange_id):


            """执行股票交易并处理居民状态"""


            exchange = self.exchanges[exchange_id]


            action = random.choice(['buy', 'sell', 'hold'])


            if action == 'buy':


                exchange['trade_volume'] += 1


                self.logger.debug(f"居民 {resident.resident_id} 在{exchange['name']}买入股票")


            elif action == 'sell':


                exchange['trade_volume'] += 1


                self.logger.debug(f"居民 {resident.resident_id} 在{exchange['name']}卖出股票")


            # 检查居民寿命并处理死亡


            if resident.update_resident_status(0):
                # 从residents字典中移除
                if resident.resident_id in self.residents:
                    del self.residents[resident.resident_id]
                # 更新人口统计
                self.population.death()


    def is_end(self):


            """检查模拟是否结束"""


            return self.time.is_end()

    def calculate_average_satisfaction(self):
        """
        计算所有居民的平均满意度
        """
        if not self.residents:
            return 50  # 默认满意度
        
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())
        return total_satisfaction / len(self.residents)


    def analyze_price_trends(self):


            """


            分析价格趋势和统计指标，验证预期结果


            """


            import numpy as np


            if len(self.results["years"]) < 2:


                self.logger.warning("数据不足，无法进行价格趋势分析")


                return


            # 分析价格发现效率趋势


            efficiency_trend = np.array(self.results["price_discovery_efficiency"])


            efficiency_mean = np.mean(efficiency_trend)


            efficiency_std = np.std(efficiency_trend)


            # 分析价格稳定性趋势


            stability_trend = np.array(self.results["price_stability"])


            stability_mean = np.mean(stability_trend)


            stability_std = np.std(stability_trend)


            # 分析价格收敛趋势


            convergence_trend = np.array(self.results["price_convergence_rate"])


            convergence_mean = np.mean(convergence_trend)


            # 分析价格偏差趋势


            deviation_trend = np.array(self.results["average_price_deviation"])


            deviation_mean = np.mean(deviation_trend)


            deviation_trend_direction = "下降" if deviation_trend[-1] < deviation_trend[0] else "上升"


            # 分析交易所贡献度差异


            contrib_A = np.array(self.results["exchange_A_contribution"])


            contrib_B = np.array(self.results["exchange_B_contribution"])


            contrib_diff = np.mean(np.abs(contrib_A - contrib_B))


            # 输出分析报告


            self.logger.info("="*60)


            self.logger.info("价格发现模拟 - 统计分析报告")


            self.logger.info("="*60)


            self.logger.info(f"价格发现效率: 均值={efficiency_mean:.4f}, 标准差={efficiency_std:.4f}")


            self.logger.info(f"价格稳定性: 均值={stability_mean:.4f}, 标准差={stability_std:.4f}")


            self.logger.info(f"价格收敛率: 均值={convergence_mean:.4f}")


            self.logger.info(f"平均价格偏差: 均值={deviation_mean:.4f}, 趋势={deviation_trend_direction}")


            self.logger.info(f"交易所贡献度差异: {contrib_diff:.4f}")


            # 验证预期结果


            if stability_mean > 0.5:


                self.logger.info("✓ 价格稳定性良好，符合预期")


            else:


                self.logger.warning("✗ 价格稳定性较低，建议调整模拟参数")


            if deviation_trend_direction == "下降":


                self.logger.info("✓ 价格偏差呈下降趋势，市场趋于收敛")


            else:


                self.logger.warning("✗ 价格偏差未呈现收敛趋势，需要关注")


            if contrib_diff < 0.2:


                self.logger.info("✓ 两个交易所对价格发现的贡献较为均衡")


            else:


                self.logger.info(f"! 交易所贡献度存在差异，可能存在主导市场")


            self.logger.info("="*60)


            return {


                "efficiency_mean": efficiency_mean,


                "efficiency_std": efficiency_std,


                "stability_mean": stability_mean,


                "stability_std": stability_std,


                "convergence_mean": convergence_mean,


                "deviation_mean": deviation_mean,


                "contrib_diff": contrib_diff


            }
