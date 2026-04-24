from .simulator_imports import *

class AssetMarketBubbleSimSimulator:
    
    def __init__(self, **kwargs):
            self.logger = LogManager.get_logger('simulator', console_output=True)
            self.map = kwargs.get('map')
            self.time = kwargs.get('time')
            self.population = kwargs.get('population')
            self.social_network = kwargs.get('social_network')
            self.residents = kwargs.get('residents')
            self.towns = kwargs.get('towns')
            self.config = kwargs.get('config')
            self.government = kwargs.get('government')
            self.government_officials = kwargs.get('government_officials')
            self.basic_living_cost = 0
            self.gdp = 0
            self.tax_income = 0
            self.average_satisfaction = None
            self.initial_cash = self.config['asset_market']['initial_cash']
            self.dividend_amount = self.config['asset_market']['dividend_amount']
            self.trading_periods = self.config['asset_market']['trading_periods']


    
            self.asset_fundamental_value = self.dividend_amount * self.trading_periods


    
            self.order_book = {'bids': [], 'asks': []}


    
            self.transaction_history = []


    
            self.asset_prices = []


    
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

    
            "periods": [],

    
            "asset_price": [],

    
            "trading_volume": [],

    
            "average_cash": [],

    
            "average_assets": [],

    
            "price_deviation": [],

    
            "bid_ask_spread": [],

    
            "population": [],

    
        }

    async def run(self):


        self.start_time = datetime.now()


        await self.initialize_assets()


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


            print(Back.GREEN + f"交易期:{self.time.current_time}" + Back.RESET)


            self.logger.info(f"交易期:{self.time.current_time}")


            remaining_periods = self.trading_periods - self.time.get_elapsed_time_steps()


            remaining_value = self.dividend_amount * remaining_periods


            self.logger.info(f"资产基础价值:{remaining_value:.2f}")

    async def update_state(self):


            self.pay_dividend()


            self.gdp = self.calculate_gdp()


            if self.government:


                self.tax_income = self.gdp * self.government.get_tax_rate()


                self.government.budget = round(self.government.budget + self.tax_income, 2)


            self.average_satisfaction = self.calculate_average_satisfaction()


            self.population.update_birth_rate(self.average_satisfaction)


            if self.government:


                self.logger.info(f"GDP:{self.gdp},税收收入:{self.tax_income},政府预算:{self.government.budget}")

    async def execute_actions(self):


        self.migration_count = 0


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


        self.logger.info(f"新加入{new_count}名居民")


        government_decision = None


        if self.government and self.government_officials:


            government_config = {


                'agents': self.government_officials,


                'ordinary_type': OrdinaryGovernmentAgent,


                'leader_type': HighRankingGovernmentAgent,


            }


            government_decision = await self.collect_group_decision('government', government_config)


        if government_decision:


            self.execute_government_decision(government_decision)


        await self.conduct_trading_session()


        for resident_name in list(self.residents.keys()):


            resident = self.residents[resident_name]


            if resident.update_resident_status(self.basic_living_cost):


                self.population.death()


        current_year = self.time.current_time


        if current_year % random.randint(3, 5) == 0:


            self.social_network.update_network_edges()

    def collect_results(self):


                current_transactions = [t for t in self.transaction_history if t['period'] == self.time.current_time]


                trading_volume = sum(t['quantity'] for t in current_transactions)


                total_cash = sum(r.cash for r in self.residents.values())


                total_assets = sum(r.assets for r in self.residents.values())


                avg_cash = total_cash / len(self.residents) if self.residents else 0


                avg_assets = total_assets / len(self.residents) if self.residents else 0


                # 获取当前价格，如果没有交易则使用基础价值


                remaining_periods = self.trading_periods - self.time.get_elapsed_time_steps()


                fundamental_value = self.dividend_amount * remaining_periods

                if self.asset_prices:
                    current_price = self.asset_prices[-1]

                else:
                    # 如果还没有交易价格，使用基础价值
                    current_price = fundamental_value
                    self.asset_prices.append(current_price)  # 记录基础价值

                price_deviation = ((current_price - fundamental_value) / fundamental_value * 100) if fundamental_value > 0 else 0


                bids = [b['price'] for b in self.order_book['bids']]


                asks = [a['price'] for a in self.order_book['asks']]


                bid_ask_spread = (max(asks) - min(bids)) if bids and asks else 0


                self.results["periods"].append(self.time.current_time)


                self.results["asset_price"].append(current_price)


                self.results["trading_volume"].append(trading_volume)


                self.results["average_cash"].append(avg_cash)


                self.results["average_assets"].append(avg_assets)


                self.results["price_deviation"].append(price_deviation)


                self.results["bid_ask_spread"].append(bid_ask_spread)


                self.results["population"].append(self.population.get_population())


                self.logger.info(f"交易期: {self.time.current_time}, "


                      f"资产价格: {current_price:.2f}, "


                      f"交易量: {trading_volume}, "


                      f"价格偏离: {price_deviation:.2f}%, "


                      f"人口: {self.population.get_population()}")

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
    
    async def collect_group_decision(self, group_type, config, max_rounds=2):

    
        self.logger.info(f"开始收集 {group_type} 的决策")


    
        try:

    
            with open(f'config/{SimulationContext.get_simulation_type()}/simulation_config.yaml', 'r', encoding='utf-8') as f:

    
                sim_config = yaml.safe_load(f)

    
                group_decision_config = sim_config['simulation'].get('group_decision', {})

    
                group_config = group_decision_config.get(group_type, {})

    
                group_decision_enabled = group_config.get('enabled', True)

    
                configured_max_rounds = group_config.get('max_rounds', 2)

    
        except Exception as e:

    
            self.logger.warning(f"读取群体决策配置失败，使用默认值：{e}")

    
            group_decision_enabled = True

    
            configured_max_rounds = max_rounds


    
        leaders = [member for member in config['agents'].values()

    
                  if isinstance(member, config['leader_type'])]

    
        if not leaders:

    
            return None

        # 计算salary参数（总收入作为salary参数）
        salary = self.calculate_gdp()

        if not group_decision_enabled:

    
            leader = leaders[0]

    
            decision = await leader.make_decision(

    
                summary="直接决策模式，无群体讨论。",
                salary=salary

    
            )

    
            return decision


    
        ordinary_members = [

    
            member for member in config['agents'].values()

    
            if isinstance(member, config['ordinary_type'])

    
            and not isinstance(member, InformationOfficer)

    
        ]


    
        if not ordinary_members:

    
            return None


    
        shared_pool = list(config['agents'].values())[0].shared_pool

    
        await shared_pool.clear_discussions()


    
        first_round_tasks = [

    
            member.generate_opinion(salary)

    
            for member in random.sample(ordinary_members, len(ordinary_members))

    
        ]

    
        await asyncio.gather(*first_round_tasks)


    
        for round_num in range(2, configured_max_rounds + 1):

    
            self.logger.info(f"第{round_num}轮决策")

    
            round_tasks = [

    
                member.generate_and_share_opinion(salary)

    
                for member in random.sample(ordinary_members, len(ordinary_members))

    
            ]

    
            await asyncio.gather(*round_tasks)


    
        info_officers = [

    
            member for member in config['agents'].values()

    
            if isinstance(member, InformationOfficer)

    
        ]


    
        if info_officers and leaders:

    
            discussion_summary = await info_officers[0].summarize_discussions()

    
            if discussion_summary:

    
                decision = await leaders[0].make_decision(discussion_summary, salary)

    
                return decision


    
        return None
    
    def execute_government_decision(self, decision):

    
            """执行政府决策"""

    
            try:

    
                decision_data = self.parse_decision(decision)

    
                if not decision_data:

    
                    return False


    
                success = True


    
                # 处理税率调整

    
                if "tax_adjustment" in decision_data and decision_data["tax_adjustment"] is not None:

    
                    new_tax_rate = decision_data["tax_adjustment"]

    
                    if self.government:

    
                        self.government.adjust_tax_rate(new_tax_rate)

    
                        self.logger.info(f"政府调整税率至: {new_tax_rate}")


    
                return success


    
            except Exception as e:

    
                self.logger.error(f"执行政府决策时出错：{e}")

    
                return False
    
    def extract_json_from_text(self, text):
        """从文本中提取JSON内容"""
        json_pattern = r'\{[^{}]*\}'
        matches = re.findall(json_pattern, text)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        return None
    
    def parse_decision(self, decision_text, max_retries=3):
        """解析决策内容，支持重试"""
        decision_text = decision_text.strip().removeprefix('```json').removesuffix('```')
        for attempt in range(max_retries):
            try:
                return json.loads(decision_text)
            except json.JSONDecodeError:
                extracted = self.extract_json_from_text(decision_text)
                if extracted:
                    return extracted
        return None
    
    def calculate_gdp(self):

    
        if not self.residents:

    
            return 0.0

    
        total_income = sum(resident.income for resident in self.residents.values())

    
        return total_income
    
    def calculate_average_satisfaction(self):

    
        if not self.residents:

    
            self.logger.warning("没有居民，平均满意度为 0.0")

    
            return 0.0
    
        if self.population.population == 0:
            self.logger.warning("人口为0，平均满意度为 0.0")
            return 0.0
    
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())

    
        average_satisfaction = total_satisfaction / self.population.population

    
        self.logger.info(f"平均满意度: {average_satisfaction:.2f}")

    
        return average_satisfaction
    
    async def integrate_new_residents(self, new_residents):
        if not new_residents:
            return
        for resident in new_residents.values():
            resident.cash = self.initial_cash
            resident.income = self.initial_cash
            resident.assets = random.randint(0, 3)
            resident.asset_valuation = self.asset_fundamental_value * random.uniform(0.8, 1.2)
            resident.risk_preference = random.choice(['conservative', 'moderate', 'aggressive'])
            resident.trading_strategy = random.choice(['fundamental', 'technical', 'momentum'])
    
        self.residents.update(new_residents)
        self.logger.info(f"{len(new_residents)} 名新居民已出生")
        self.towns.initialize_resident_groups(new_residents)
        self.logger.info("新居民已加入各自城镇")

        if new_residents:
            self.social_network.add_new_residents(new_residents)
            self.logger.info(f"{len(new_residents)} 名新居民已加入社交网络")

    async def initialize_assets(self):


            self.logger.info(f"初始化资产市场：基础价值={self.asset_fundamental_value}，初始现金={self.initial_cash}")


            for resident in self.residents.values():


                resident.cash = self.initial_cash


                resident.income = self.initial_cash


                resident.assets = random.randint(0, 5)


                resident.asset_valuation = self.asset_fundamental_value * random.uniform(0.8, 1.2)


                resident.risk_preference = random.choice(['conservative', 'moderate', 'aggressive'])


                resident.trading_strategy = random.choice(['fundamental', 'technical', 'momentum'])


            self.logger.info(f"已为{len(self.residents)}名智能体初始化资产组合")


    def pay_dividend(self):


            if self.time.get_elapsed_time_steps() > 0:


                for resident in self.residents.values():


                    dividend = resident.assets * self.dividend_amount


                    resident.cash += dividend


                self.logger.info(f"本期分红:每份资产{self.dividend_amount}元")

    
    def parse_llm_trading_decision(self, select, resident, market_price):
        """
        解析LLM返回的决策结果，转换为交易决策
        
        Args:
            select: LLM返回的选择值
            resident: 居民对象
            market_price: 市场价格
            
        Returns:
            dict: 包含action, price, quantity的字典
        """
        try:
            # 将select转换为字符串并清理
            select_str = str(select).strip()
            
            # 根据配置文件中的动作映射（1-买入，2-卖出，3-观望）
            if select_str == '1':  # 买入
                # 计算买入数量
                quantity = 1 if resident.risk_preference == 'conservative' else (2 if resident.risk_preference == 'moderate' else 3)
                quantity = min(quantity, int(resident.cash / market_price) if market_price > 0 else 0, 10)
                if quantity > 0:
                    # 根据风险偏好调整价格波动范围
                    price_multiplier = random.uniform(1.0, 1.15) if resident.risk_preference == 'aggressive' else \
                                     random.uniform(1.0, 1.08) if resident.risk_preference == 'moderate' else \
                                     random.uniform(1.0, 1.05)
                    return {
                        'action': 'buy',
                        'price': market_price * price_multiplier,
                        'quantity': quantity
                    }
            elif select_str == '2':  # 卖出
                # 计算卖出数量
                quantity = 1 if resident.risk_preference == 'conservative' else (2 if resident.risk_preference == 'moderate' else 3)
                quantity = min(quantity, resident.assets, 10)
                if quantity > 0:
                    # 根据风险偏好调整价格波动范围
                    price_multiplier = random.uniform(0.85, 1.0) if resident.risk_preference == 'aggressive' else \
                                     random.uniform(0.92, 1.0) if resident.risk_preference == 'moderate' else \
                                     random.uniform(0.95, 1.0)
                    return {
                        'action': 'sell',
                        'price': market_price * price_multiplier,
                        'quantity': quantity
                    }
            # 默认为观望
            return {'action': 'hold'}
            
        except Exception as e:
            self.logger.warning(f"解析交易决策失败: {e}")
            return {'action': 'hold'}

    
    def make_trading_decision(self, resident, fundamental_value, market_price):
        """
        为居民生成交易决策（不依赖resident模块的方法）
        
        Args:
            resident: 居民对象
            fundamental_value: 资产基础价值
            market_price: 当前市场价格
            
        Returns:
            dict: 包含action, price, quantity的字典
        """
        try:
            cash = resident.cash
            assets = resident.assets
            strategy = resident.trading_strategy
            risk_preference = resident.risk_preference
            
            # 计算价格偏离度
            if fundamental_value > 0:
                deviation = (market_price - fundamental_value) / fundamental_value
            else:
                return {'action': 'hold'}
            
            # 根据风险偏好设置交易阈值
            thresholds = {
                'conservative': 0.2,
                'moderate': 0.15,
                'aggressive': 0.1
            }
            threshold = thresholds.get(risk_preference, 0.15)
            
            # 根据策略调整阈值
            if strategy == 'momentum':
                # 动量策略：跟随趋势
                threshold *= 0.8
            elif strategy == 'fundamental':
                # 基本面策略：更严格的阈值
                threshold *= 1.2
            
            # 如果价格低于基础价值较多，考虑买入
            if deviation < -threshold and cash > market_price:
                quantity = 1 if risk_preference == 'conservative' else (2 if risk_preference == 'moderate' else 3)
                quantity = min(quantity, int(cash / market_price), 10)
                if quantity > 0:
                    return {
                        'action': 'buy',
                        'price': market_price * 1.02,  # 略高于市价
                        'quantity': quantity
                    }
            
            # 如果价格高于基础价值较多，考虑卖出
            elif deviation > threshold and assets > 0:
                quantity = 1 if risk_preference == 'conservative' else (2 if risk_preference == 'moderate' else 3)
                quantity = min(quantity, assets, 10)
                if quantity > 0:
                    return {
                        'action': 'sell',
                        'price': market_price * 0.98,  # 略低于市价
                        'quantity': quantity
                    }
            
            return {'action': 'hold'}
            
        except Exception as e:
            self.logger.warning(f"居民 {resident.resident_id} 交易决策失败: {e}")
            return {'action': 'hold'}


    async def conduct_trading_session(self):
        self.order_book = {'bids': [], 'asks': []}

        tasks = []
        for resident in self.residents.values():
            tasks.append(self.resident_submit_order(resident))

        await asyncio.gather(*tasks)

        self.match_orders()

        current_price = self.calculate_current_price()
        if current_price:
            self.asset_prices.append(current_price)
            self.logger.info(f"当前资产价格：{current_price:.2f}")


    async def resident_submit_order(self, resident):


            remaining_periods = self.trading_periods - self.time.get_elapsed_time_steps()


            fundamental_value = self.dividend_amount * remaining_periods


            market_price = self.asset_prices[-1] if self.asset_prices else fundamental_value


            # 准备格式化的市场信息
            
            # 计算价格趋势
            if len(self.asset_prices) >= 2:
                price_change = self.asset_prices[-1] - self.asset_prices[-2]
                if price_change > 0:
                    price_trend = "上涨"
                elif price_change < 0:
                    price_trend = "下跌"
                else:
                    price_trend = "持平"
            else:
                price_trend = "初始价格"
            
            # 构建完整的市场信息文本（不使用占位符）
            market_info = f"""
当前市场价格：{market_price:.2f}元，资产基础价值：{fundamental_value:.2f}元
当前买单数量：{len(self.order_book.get('bids', []))}，卖单数量：{len(self.order_book.get('asks', []))}
每期固定分红{self.dividend_amount}元，剩余{remaining_periods}期
当前是第{self.time.current_time}个交易期（共{self.trading_periods}期），资产剩余分红期数为{remaining_periods}期，每期固定分红{self.dividend_amount}元。
基础价值为剩余分红总额：{fundamental_value}元。
当前市场价格为{market_price}元，价格{price_trend}。
你当前持有现金{resident.cash}元，持有资产{resident.assets}份。
你的交易策略：{resident.trading_strategy}，风险偏好：{resident.risk_preference}。
"""

            # 使用LLM进行交易决策
            try:
                decision_result = await resident.decide_action_by_llm(
                    tax_rate=0,
                    basic_living_cost=0,
                    climate_impact=0,
                    market_info=market_info,
                    current_year=self.time.current_time
                )
                # 解析LLM返回的决策结果
                if isinstance(decision_result, tuple):
                    select = decision_result[0] if len(decision_result) > 0 else None
                    # 根据select值决定动作
                    decision = self.parse_llm_trading_decision(select, resident, market_price)

                else:

                    decision = {'action': 'hold'}

            except Exception as e:
                self.logger.warning(f"居民 {resident.resident_id} LLM决策失败: {e}，使用默认策略")

                decision = self.make_trading_decision(
                    resident=resident,
                    fundamental_value=fundamental_value,
                    market_price=market_price
                )
            if decision and decision.get('action') in ['buy', 'sell']:
                order = {
                    'resident_id': resident.resident_id,
                    'action': decision['action'],
                    'price': decision.get('price', market_price),
                    'quantity': decision.get('quantity', 1)
                }


                if order['action'] == 'buy':
                    self.order_book['bids'].append(order)
                else:
                    self.order_book['asks'].append(order)

            if hasattr(resident, 'asset_valuation'):
                noise = random.uniform(-0.1, 0.1)
                resident.asset_valuation = market_price * (1 + noise)


    def match_orders(self):
        bids = sorted(self.order_book['bids'], key=lambda x: x['price'], reverse=True)
        asks = sorted(self.order_book['asks'], key=lambda x: x['price'])

        transactions = []

        i, j = 0, 0
        while i < len(bids) and j < len(asks):
            bid = bids[i]
            ask = asks[j]

            if bid['price'] >= ask['price']:
                transaction_price = (bid['price'] + ask['price']) / 2
                transaction_quantity = min(bid['quantity'], ask['quantity'])

                buyer = self.residents.get(bid['resident_id'])
                seller = self.residents.get(ask['resident_id'])

                if buyer and seller:
                    cost = transaction_price * transaction_quantity
                    if buyer.cash >= cost and seller.assets >= transaction_quantity:
                        buyer.cash -= cost
                        buyer.assets += transaction_quantity
                        buyer.income = buyer.cash  # 同步income和cash
                        seller.cash += cost
                        seller.assets -= transaction_quantity
                        seller.income = seller.cash  # 同步income和cash

                        transactions.append({
                            'period': self.time.current_time,
                            'price': transaction_price,
                            'quantity': transaction_quantity,
                            'buyer': bid['resident_id'],
                            'seller': ask['resident_id']
                        })

                bid['quantity'] -= transaction_quantity
                ask['quantity'] -= transaction_quantity

                if bid['quantity'] <= 0:
                    i += 1
                if ask['quantity'] <= 0:
                    j += 1
            else:
                break

        self.transaction_history.extend(transactions)
        self.logger.info(f"本期成交{len(transactions)}笔交易")


    def calculate_current_price(self):
        current_transactions = [t for t in self.transaction_history if t['period'] == self.time.current_time]

        if current_transactions:
            total_value = sum(t['price'] * t['quantity'] for t in current_transactions)
            total_quantity = sum(t['quantity'] for t in current_transactions)
            return total_value / total_quantity if total_quantity > 0 else None

        return None
