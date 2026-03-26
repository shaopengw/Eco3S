from .simulator_imports import *

class YourSimulator:
    
    def __init__(
        self,
        plugin_registry: Any,
        residents: Dict[int, IResident],
        config: Dict,
        government_officials: List[IOrdinaryGovernmentAgent] = None,
        rebels_agents: List[IOrdinaryRebel] = None,
        influence_manager: Any = None,
    ):
                
        # 初始化日志记录器
        self.logger = LogManager.get_logger('simulator', console_output=True)

        self.plugin_registry = plugin_registry
        # 影响函数编排器：默认启用
        self.influence_manager = influence_manager or InfluenceManager(logger=self.logger)

        # === 从插件注册中心获取核心对象 ===
        self.map = require_module(self.plugin_registry, 'map')
        self.time = require_module(self.plugin_registry, 'time')
        self.population = require_module(self.plugin_registry, 'population')
        self.social_network = require_module(self.plugin_registry, 'social_network')
        self.towns = require_module(self.plugin_registry, 'towns')
        self.government = require_module(self.plugin_registry, 'government')
        self.rebellion = require_module(self.plugin_registry, 'rebellion')
        self.transport_economy = require_module(self.plugin_registry, 'transport_economy')
        self.climate = require_module(self.plugin_registry, 'climate')
        
        # === 接受作为参数传入的对象 ===
        self.residents = residents
        self.config = config
        self.government_officials = government_officials
        self.rebels_agents = rebels_agents
        
        # === 经济参数 ===
        self.basic_living_cost = 8  # 年基本生活成本（单位：两）
        self.gdp = 0  # GDP
        
        # === 社会指标 ===
        self.average_satisfaction = None  # 平均满意度
        
        # === 叛军相关（不需要可删除） ===
        self.propaganda_prob = 0.1  # 宣传概率
        self.propaganda_speech = ""  # 宣传内容
        self.rebellion_records = 0  # 叛乱次数
        self.rebellion_history = []  # 叛乱历史
        
        # === 结果数据结构 ===
        self.results = self.init_results()
        self.start_time = None
        self.end_time = None

        # 保存初始数据（先算基础指标再落盘）
        self.gdp = self.calculate_gdp()
        self.average_satisfaction = self.calculate_average_satisfaction()
        self.results["years"].append("初始")
        self.results["rebellions"].append(self.rebellion_records)
        self.results["unemployment_rate"].append(0)
        self.results["population"].append(self.population.get_population())
        self.results["government_budget"].append(self.government.get_budget() if self.government else 0)
        self.results["rebellion_strength"].append(self.rebellion.get_strength() if self.rebellion else 0)
        self.results["rebellion_resources"].append(self.rebellion.get_resources() if self.rebellion else 0)
        self.results["average_satisfaction"].append(self.average_satisfaction)
        self.results["tax_rate"].append(self.government.get_tax_rate() if self.government else 0)
        self.results["river_navigability"].append(self.map.get_navigability() if self.map else 0)
        self.results["gdp"].append(self.gdp)
        
        # === 结果文件路径 ===
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
        # 如果保存为 JSON，使用: f"running_data_{timestamp}_pid{pid}.json"
    
    def init_results(self):
        """初始化结果数据结构"""
        return {
            "years": [],
            "rebellions": [],
            "unemployment_rate": [],
            "population": [],
            "government_budget": [],
            "rebellion_strength": [],
            "rebellion_resources": [],
            "average_satisfaction": [],
            "tax_rate": [],
            "river_navigability": [],
            "gdp": [],
        }

    async def run(self):
        """主运行流程：初始化→主循环→结束"""
        self.start_time = datetime.now()
        
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
            
            # 5. 保存结果（始终覆盖写入完整结果）
            self.save_results(self.result_file)
            
            # 6. 推进时间
            self.time.step()
        
        self.end_time = datetime.now()
        self.display_total_simulation_time()
        
        # 可选：绘制网络分析图
        # self.social_network.plot_degree_distribution()
        # self.social_network.visualize()

    def print_time_step(self):
        """打印当前时间步信息"""
        print(Back.GREEN + f"年份:{self.time.current_time}" + Back.RESET)
        self.logger.info(f"年份:{self.time.current_time}")
        if self.climate:
            current_year = self.time.current_time
            start_year = self.time.start_time
            self.logger.info(f"气候影响因子：{self.climate.get_current_impact(current_year, start_year)}")

    async def update_state(self):
        """更新系统状态（经济、气候、人口等）"""
        # ==================== 计算基础状态（用于构建 context） ====================
        current_year = getattr(self.time, 'current_time', None)
        start_year = getattr(self.time, 'start_time', None)

        self.gdp = self.calculate_gdp()
        self.average_satisfaction = self.calculate_average_satisfaction()
        climate_impact_factor = None
        if self.climate is not None and hasattr(self.climate, 'get_current_impact'):
            climate_impact_factor = self.climate.get_current_impact(current_year, start_year)

        # ==================== 应用影响函数（按 influences.yaml 编排） ====================
        # 说明：这里不再硬编码“税收/预算/军力/叛军资源/运河维护”等互影响公式。
        simulator_state = {
            'time': self.time,
            'map': self.map,
            'population': self.population,
            'transport_economy': self.transport_economy,
            'climate': self.climate,
            'towns': self.towns,
            'social_network': self.social_network,
            'government': self.government,
            'rebellion': self.rebellion,
            'residents': self.residents,
            'gdp': self.gdp,
            'average_satisfaction': self.average_satisfaction,
            'basic_living_cost': self.basic_living_cost,
            # 常用补充字段（影响函数可选读取）
            'gdp_growth_rate': self._calculate_gdp_growth_rate() if hasattr(self, '_calculate_gdp_growth_rate') else 0.0,
            'rebellion_records': self.rebellion_records,
            'climate_impact_factor': climate_impact_factor,
            'current_navigability': self.map.get_navigability() if self.map else 0.0,
            'navigability': self.map.get_navigability() if self.map else 0.0,
            'transport_cost': getattr(self.transport_economy, 'transport_cost', 0.0),
            'maintenance_cost_base': getattr(self.transport_economy, 'maintenance_cost_base', 0.0),
            'tax_rate': self.government.get_tax_rate() if self.government else 0.0,
        }

        global_context = self.influence_manager.apply_all_influences(simulator_state)

        # 影响函数通常会写回模块内部状态；这里仅做读取与日志。
        tax_income = global_context.get('tax_income', 0.0)
        rebellion_income = global_context.get('rebellion_income', 0.0)
        maintenance_cost = (global_context.get('result') or {}).get('maintenance_cost')

        if self.government:
            self.logger.info(f"GDP：{self.gdp}，税收收入：{tax_income}，政府预算：{self.government.get_budget()}")
        if self.rebellion:
            self.logger.info(f"叛军收入：{rebellion_income}，叛军资源：{self.rebellion.get_resources()}")
        if self.transport_economy:
            self.logger.info(f"河运价格：{getattr(self.transport_economy, 'river_price', None)}，维护成本：{maintenance_cost}")

    async def execute_actions(self):
        """执行所有智能体的决策和行为"""
        # 1. 居民出生
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
        
        # 2. 收集政府和叛军决策（每年）
        government_decision = None
        rebellion_decision = None
        
        if self.government and self.government_officials:
            government_config = {
                'agents': self.government_officials,
                'ordinary_type': OrdinaryGovernmentAgent,
                'leader_type': HighRankingGovernmentAgent,
            }
            government_decision = await self.collect_group_decision('government', government_config)
        
        if self.rebellion and self.rebels_agents:
            rebellion_config = {
                'agents': self.rebels_agents,
                'ordinary_type': OrdinaryRebel,
                'leader_type': RebelLeader,
            }
            rebellion_decision = await self.collect_group_decision('rebellion', rebellion_config)
        
        # 3. 执行决策
        if government_decision:
            self.execute_government_decision(government_decision)
        if rebellion_decision:
            self.execute_rebellion_decision(rebellion_decision)

        # 重置社交网络的对话计数器（如实现了该方法）
        if self.social_network and hasattr(self.social_network, 'reset_dialogue_count'):
            self.social_network.reset_dialogue_count()

        # 4. 居民行为（并发执行）
        tasks = []
        speech_tasks = []
        town_job_requests = defaultdict(list)

        # 清空上一轮的求职信息
        for resident_name in list(self.residents.keys()):
            resident = self.residents[resident_name]
            tax_rate = self.government.get_tax_rate() if self.government else 0
            
            # TODO: 以下两种情况二选一使用，不使用的直接删除
            # 1.基于LLM的决策(需要叛军情况，叛军发布激进言论)
            if resident.job == "叛军":
                tasks.append(resident.generate_provocative_opinion(self.propaganda_prob, self.propaganda_speech))
            else:
                task = resident.decide_action_by_llm(tax_rate=tax_rate, basic_living_cost=self.basic_living_cost)
            # 2.基于LLM的决策(无叛军情况)
            task = resident.decide_action_by_llm(tax_rate=tax_rate, basic_living_cost=self.basic_living_cost)
            
            # 重要提示：如需传递额外信息给LLM，请通过kwargs传递完整文本，而非在提示词模板中使用占位符
            # 示例：
            # market_info = f"当前价格：{price}元，库存：{stock}件"
            # task = resident.decide_action_by_llm(tax_rate=tax_rate, market_info=market_info)

            tasks.append(task)

        
        # 并发执行所有居民行为
        if tasks:
            results = await asyncio.gather(*tasks)

            # 处理返回的结果
            residents_list = list(self.residents.values())  # 获取当前的居民列表
            job_request_count = 0
            for i, result in enumerate(results):
                if i >= len(residents_list):
                    break
                resident = residents_list[i]
                if isinstance(result, dict) and "town" in result:
                    # 处理求职请求
                    town_job_requests[result["town"]].append(result)
                    job_request_count += 1
                elif isinstance(result, tuple) and len(result) == 4:
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

            if job_request_count > 0:
                self.logger.info(f"\n收集到 {job_request_count} 个求职请求")

            # 并发执行所有发言传播任务
            if speech_tasks:
                await asyncio.gather(*speech_tasks)
        
        # 5. 处理求职信息
        if town_job_requests:
            self.logger.info(f"\n开始处理 {len(town_job_requests)} 个城镇的求职请求")
            hiring_results = self.towns.process_town_job_requests(town_job_requests)
        else:
            self.logger.info("\n本轮无求职请求")
        
    def collect_results(self):
        """收集本轮结果数据"""
        # 更新就业市场（default 模拟会根据通航能力变化调整岗位结构）
        if self.towns and hasattr(self.towns, 'adjust_job_market'):
            old_navigability = self.results["river_navigability"][-1] if self.results["river_navigability"] else self.map.get_navigability()
            current_navigability = self.map.get_navigability()
            change_rate = (current_navigability - old_navigability) / old_navigability if old_navigability else 0
            self.towns.adjust_job_market(change_rate, self.residents)

        # 每3-5年更新社交网络
        current_year = self.time.current_time
        if self.social_network and hasattr(self.social_network, 'update_network_edges'):
            if current_year % random.randint(3, 5) == 0:
                self.social_network.update_network_edges()

        self.propaganda_prob = 0

        total_unemployment_rate = self.calculate_total_unemployment_rate()

        # 更新政府军力/叛军人数：由 influences.yaml 驱动（基于已更新的就业市场）
        if self.influence_manager and hasattr(self.influence_manager, 'build_global_context'):
            simulator_state = {
                'time': self.time,
                'map': self.map,
                'population': self.population,
                'transport_economy': self.transport_economy,
                'climate': self.climate,
                'towns': self.towns,
                'government': self.government,
                'rebellion': self.rebellion,
                'gdp': self.gdp,
                'average_satisfaction': self.average_satisfaction,
                'basic_living_cost': self.basic_living_cost,
                'gdp_growth_rate': self._calculate_gdp_growth_rate() if hasattr(self, '_calculate_gdp_growth_rate') else 0.0,
                'rebellion_records': self.rebellion_records,
            }
            context = self.influence_manager.build_global_context(simulator_state)
            if self.government and hasattr(self.government, 'apply_influences'):
                self.government.apply_influences('military_strength', context)
            if self.rebellion and hasattr(self.rebellion, 'apply_influences'):
                self.rebellion.apply_influences('strength', context)
        
        self.results["years"].append(self.time.current_time)
        self.results["rebellions"].append(self.rebellion_records)
        self.results["unemployment_rate"].append(total_unemployment_rate)
        self.results["population"].append(self.population.get_population())
        self.results["government_budget"].append(self.government.get_budget() if self.government else 0)
        self.results["rebellion_strength"].append(self.rebellion.get_strength() if self.rebellion else 0)
        self.results["rebellion_resources"].append(self.rebellion.get_resources() if self.rebellion else 0)
        self.results["average_satisfaction"].append(self.average_satisfaction)
        self.results["tax_rate"].append(self.government.get_tax_rate() if self.government else 0)
        self.results["river_navigability"].append(self.map.get_navigability())
        self.results["gdp"].append(self.gdp)
        
        self.logger.info(f"年份: {self.time.current_time}, "
              f"叛乱次数: {self.rebellion_records}, "
              f"人口数量: {self.population.get_population()}, "
              f"失业率: {self.results['unemployment_rate'][-1]:.2f}%, "
              f"平均满意度: {self.results['average_satisfaction'][-1]:.2f}, "
              f"税率: {self.results['tax_rate'][-1]:.2f}, "
              f"GDP: {self.results['gdp'][-1]:.2f}, "
              f"叛军强度: {self.results['rebellion_strength'][-1]}, "
              f"运河通航能力: {self.map.get_navigability():.2f}"
        )
        
        self.rebellion_records = 0

    def save_results(self, filename=None, append=False):
        """保存结果到CSV文件"""
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突
            filename = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
        
        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False)
        self.logger.info(f"模拟结果已完整保存至 {filename}")

    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            self.logger.info(f"总模拟时间: {total_time}")
    
    # ==================== 群体决策方法 ====================
    
    async def collect_group_decision(self, group_type, config, max_rounds=2):
        """收集群体决策（政府或叛军）"""
        self.logger.info(f"开始收集 {group_type} 的决策")

        # 计算决策参数
        _, government_salary = self.calculate_total_salaries()
        if group_type == 'rebellion':
            group_param = self.get_rebels_statistics()
        else:
            group_param = government_salary

        group_obj = self.rebellion if group_type == 'rebellion' else self.government
        if not hasattr(group_obj, 'orchestrate_group_decision'):
            return None

        return await group_obj.orchestrate_group_decision(
            agents=config['agents'],
            group_param=group_param,
            group_type=group_type,
            ordinary_type=config['ordinary_type'],
            leader_type=config['leader_type'],
            info_officer_types=(InformationOfficer, RebelsInformationOfficer),
            max_rounds=max_rounds,
        )
    
    def execute_government_decision(self, decision):
        """执行政府决策"""
        return self.execute_decision(decision, 'government')
    
    def execute_rebellion_decision(self, decision):
        """执行叛军决策"""
        return self.execute_decision(decision, 'rebellion')
    
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
    
    def execute_decision(self, decision, group_type):
        """通用决策执行函数"""
        _, salary = self.calculate_total_salaries()
        
        try:
            decision_data = self.parse_decision(decision)
            if not decision_data:
                return False
            
            success = True
            
            # 政府决策处理
            if group_type == "government":
                decision_keys = list(decision_data.keys())
                random.shuffle(decision_keys)
                
                for key in decision_keys:
                    # 示例：税率调整
                    if key == "tax_adjustment" and decision_data[key] is not None:
                        # 根据实际 government 对象的方法来调整
                        # 例如: self.government.adjust_tax_rate(decision_data[key])
                        pass
                    
                    # 示例：运河维护投资
                    elif key == "maintenance_investment" and decision_data[key] is not None:
                        # 根据实际 government 对象的方法来处理
                        # 例如: self.government.maintain_canal(maintenance_investment=decision_data[key])
                        pass
                    
                    # 示例：军事支持
                    elif key == "military_support" and decision_data[key] is not None:
                        # 根据实际 government 对象的方法来处理
                        # 例如: self.government.support_military(budget_allocation=decision_data[key])
                        pass
                    
                    # 添加其他决策类型...
            
            # 叛军决策处理
            elif group_type == "rebellion":
                if decision_data.get("propaganda_budget", 0) > 0:
                    speech_count = decision_data["propaganda_budget"] / 10  # 每10两多一名叛军发言
                    self.propaganda_speech = decision_data.get("provocative_speech", "")
                    self.calculate_propaganda_prob(speech_count)
                
                # 处理多个目标城镇
                if "target_towns" in decision_data:
                    for town in decision_data["target_towns"]:
                        strength = town.get("stage_rebellion", 0)
                        target = town.get('town_name', None)
                        if target and strength > 0:
                            self.handle_rebellion(strength_investment=strength, target_town=target)
                else:
                    # 如果没有多个目标城镇，处理单个目标城镇
                    if decision_data.get("stage_rebellion", 0) > 0:
                        strength = decision_data["stage_rebellion"]
                        target = decision_data.get('target_town', None)
                        if target:
                            self.handle_rebellion(strength_investment=strength, target_town=target)
            
            return success
        
        except Exception as e:
            self.logger.error(f"执行决策时出错：{e}")
            return False
    
    # ==================== 叛乱处理方法 ====================
    
    def handle_rebellion(self, strength_investment, target_town=None):
        """处理叛军叛乱事件（基于非线性优势损耗模型）"""
        BASE_LOSS_RATE = 0.1
        DECAY_FACTOR = 0.7
        MAX_RATIO = 5
        MIN_LOSS_RATE = 0.01
        RANDOM_RANGE = 0.03
        
        if target_town and target_town not in self.towns.towns:
            self.logger.warning(f"目标城镇 {target_town} 不存在")
            return False
        if strength_investment <= 0:
            return False
        
        town_data = self.towns.towns[target_town]
        town_defense = len(town_data['job_market'].jobs_info["官员及士兵"]["employed"])
        town_rebels = len(town_data['job_market'].jobs_info["叛军"]["employed"])
        rebel_strength = strength_investment
        
        if town_rebels < strength_investment:
            self.logger.warning(f"目标城镇 {target_town} 叛军数量不足，未能成功发起叛乱")
            return False
        
        # 无防守情况
        if town_defense == 0:
            success = True
            loot_ratio = 0 if self.government.military_strength <= 0 else strength_investment / self.government.military_strength
            gov_loss_budget = int(self.government.budget * loot_ratio)
            self.rebellion.resources += gov_loss_budget
            
            self.rebellion_records += 1
            self.logger.info(f"\n第 {self.rebellion_records} 次叛乱")
            self.logger.info(f"叛乱成功")
            self.logger.info(f"战场：{target_town}")
            self.logger.info(f"兵力对比：政府军 {town_defense} vs 叛军 {rebel_strength}")
            self.logger.info(f"叛军获得资源{gov_loss_budget}")
            
            rebellion_info = {
                "id": self.rebellion_records,
                "time": self.time.current_time,
                "target_town": target_town,
                "success": True,
                "rebel_strength": rebel_strength,
                "town_defense": town_defense,
                "rebel_loss": 0,
                "gov_loss": 0,
                "resource_change": gov_loss_budget
            }
            self.rebellion_history.append(rebellion_info)
        else:
            # 战斗损耗计算
            strength_ratio = town_defense / rebel_strength
            success = strength_ratio < 1
            
            if strength_ratio > MAX_RATIO:
                gov_loss_rate = MIN_LOSS_RATE
                rebel_loss_rate = BASE_LOSS_RATE * (MAX_RATIO ** DECAY_FACTOR)
            else:
                gov_loss_rate = BASE_LOSS_RATE / (strength_ratio ** DECAY_FACTOR)
                rebel_loss_rate = BASE_LOSS_RATE * (strength_ratio ** DECAY_FACTOR)
            
            random_factor = random.uniform(-RANDOM_RANGE, RANDOM_RANGE)
            gov_loss_rate += random_factor
            rebel_loss_rate += random_factor
            
            gov_loss = int(gov_loss_rate * town_defense)
            rebel_loss = int(rebel_loss_rate * rebel_strength)
            self.handle_army_loss("官员及士兵", gov_loss, target_town)
            self.handle_army_loss("叛军", rebel_loss, target_town)
            
            if success:
                loot_ratio = gov_loss / self.government.military_strength
                gov_loss_budget = int(self.government.budget * loot_ratio)
                self.rebellion.resources += gov_loss_budget
                self.government.budget -= gov_loss_budget
            else:
                rebel_loss_resources = int(rebel_loss * 6)
                self.rebellion.resources -= rebel_loss_resources
            
            self.rebellion_records += 1
            self.logger.info(f"\n第 {self.rebellion_records} 次叛乱")
            self.logger.info(f"叛乱成功" if success else f"叛乱失败")
            self.logger.info(f"战场：{target_town}")
            self.logger.info(f"兵力对比：政府军 {town_defense} vs 叛军 {rebel_strength}")
            self.logger.info(f"损耗率：政府军 {gov_loss_rate*100:.1f}% | 叛军 {rebel_loss_rate*100:.1f}%")
            self.logger.info(f"实际损耗：政府军 -{gov_loss} | 叛军 -{rebel_loss}")
            if success:
                self.logger.info(f"叛军获得资源{gov_loss_budget}")
            else:
                self.logger.info(f"叛军失去资源{rebel_loss_resources}")
        
        return True
    
    def handle_army_loss(self, army_type, actual_loss, target_town):
        """处理军队损耗"""
        all_army_residents = []
        if target_town:
            town_data = self.towns.towns[target_town]
            if town_data.get('job_market'):
                employed_list = town_data['job_market'].jobs_info.get(army_type, {}).get("employed", [])
                all_army_residents.extend(employed_list)
        
        if all_army_residents:
            selected_army = random.sample(all_army_residents, min(actual_loss, len(all_army_residents)))
            for army_id in selected_army:
                if army_id in self.residents:
                    resident = self.residents[army_id]
                    resident.deregister()
                    self.population.death()
    
    # ==================== 计算统计方法 ====================
    
    def calculate_gdp(self):
        """计算GDP（所有非叛军居民的收入总和）"""
        if not self.residents:
            return 0.0
        total_income = sum(resident.income for resident in self.residents.values() if resident.job != "叛军")
        return total_income
    
    def calculate_average_satisfaction(self):
        """计算所有居民的平均满意度"""
        if not self.residents:
            self.logger.warning("没有居民，平均满意度为 0.0")
            return 0.0
        
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())
        average_satisfaction = total_satisfaction / self.population.population
        self.logger.info(f"平均满意度: {average_satisfaction} = {total_satisfaction / self.population.population:.2f}")
        return average_satisfaction
    
    def calculate_total_unemployment_rate(self):
        """计算所有城镇的平均失业率"""
        total_employed = 0
        total_residents = 0
        
        for town_name, town_data in self.towns.towns.items():
            job_market = town_data['job_market']
            if job_market:
                town_employed = sum(len(info["employed"]) for job, info in job_market.jobs_info.items() if job != "叛军")
                total_employed += town_employed
                total_residents += len(town_data['residents'])
        
        if total_residents == 0:
            return 0.0
        self.logger.info(f"总体就业率: {total_employed} / {total_residents} = {total_employed / total_residents:.2f}")
        unemployment_rate = (1.0 - (total_employed / total_residents)) * 100
        return unemployment_rate
    
    def calculate_total_salaries(self):
        """计算所有城镇的叛军和其他职业总收入"""
        total_rebel_salary = 0
        total_other_salary = 0
        
        for town_name, town_data in self.towns.towns.items():
            if town_data.get('job_market'):
                for job, info in town_data['job_market'].jobs_info.items():
                    salary = info.get("salary", 0) * len(info.get("employed", []))
                    if job == "叛军":
                        total_rebel_salary += salary
                    else:
                        total_other_salary += salary
        
        return total_rebel_salary, total_other_salary
    
    def get_rebels_statistics(self):
        """返回每个城市的叛军和官员数量统计"""
        stats = []
        for town_name, town_data in self.towns.towns.items():
            town_job_market = town_data.get('job_market')
            if town_job_market:
                rebels_count = len(town_job_market.jobs_info.get("叛军", {}).get("employed", []))
                officials_count = len(town_job_market.jobs_info.get("官员及士兵", {}).get("employed", []))
                stats.append({
                    "town_name": town_name,
                    "rebel_count": rebels_count,
                    "official_count": officials_count
                })
        return stats
    
    def get_job_total_count(self):
        """获取除了叛军外的所有职业的岗位总数"""
        total_count = 0
        for town_name, town_data in self.towns.towns.items():
            job_market = town_data['job_market']
            if job_market:
                for job, info in job_market.jobs_info.items():
                    if job != "叛军":
                        total_count += info.get("quota", 0)
        return total_count
    
    def calculate_propaganda_prob(self, speech_count):
        """计算普通叛军发表煽动言论的概率"""
        total_rebels = self.rebellion.get_strength()
        if total_rebels == 0:
            self.propaganda_prob = 0.0
        else:
            self.propaganda_prob = round(speech_count / total_rebels, 2)
            self.propaganda_prob = max(0.0, min(1.0, self.propaganda_prob))
    
    # ==================== 辅助方法 ====================
    
    def get_basic_living_cost(self):
        """获取当前基本生活所需值"""
        return self.basic_living_cost
    
    def adjust_basic_living_cost(self, adjustment):
        """调整基本生活所需值"""
        self.basic_living_cost = max(500, self.basic_living_cost + adjustment)
        self.logger.info(f"基本生活所需值调整为: {self.basic_living_cost}")
        return self.basic_living_cost
    
    async def integrate_new_residents(self, new_residents):
        """整合新居民到系统"""
        if not new_residents:
            return
        
        self.residents.update(new_residents)
        self.logger.info(f"{len(new_residents)} 名新居民已出生")
        
        self.towns.initialize_resident_groups(new_residents)
        self.logger.info("新居民已加入各自城镇")
        
        if new_residents:
            self.social_network.add_new_residents(new_residents)
            self.logger.info(f"{len(new_residents)} 名新居民已加入社交网络")
    
    def summarize_time_step_results(self):
        """总结当前时间步的各项指标变化"""
        current_idx = len(self.results["years"]) - 1
        if current_idx <= 0:
            return {}
        
        changes = {
            "人口变化率": self.calculate_change_rate("population", current_idx),
            "GDP变化率": self.calculate_change_rate("gdp", current_idx),
            "政府预算变化率": self.calculate_change_rate("government_budget", current_idx),
            "叛军力量变化率": self.calculate_change_rate("rebellion_strength", current_idx),
            "平均满意度变化": self.calculate_change_rate("average_satisfaction", current_idx),
            "失业率变化": self.calculate_change_rate("unemployment_rate", current_idx),
            "叛乱次数": self.results["rebellions"][current_idx],
            "叛军资源变化": self.calculate_change_rate("rebellion_resources", current_idx),
        }
        return changes
    
    def calculate_change_rate(self, metric, current_idx):
        """计算指定指标的变化率"""
        current = self.results[metric][current_idx]
        previous = self.results[metric][current_idx-1]
        if previous == 0:
            return 0 if current == 0 else 1
        return (current - previous) / previous
    
    async def store_decision_memory(self, group_type, decision, changes_summary):
        """存储决策记忆到智能体"""
        if group_type == 'government':
            memory_content = (
                f"时间: {self.time.current_time}"
                f"决策内容: {decision}"
                f"执行结果:"
                f"- GDP变化率: {'+' if changes_summary.get('GDP变化率', 0) > 0 else ''}{changes_summary.get('GDP变化率', 0):.2%}"
                f"- 政府预算变化率: {'+' if changes_summary.get('政府预算变化率', 0) > 0 else ''}{changes_summary.get('政府预算变化率', 0):.2%}"
                f"- 叛军力量变化率: {'+' if changes_summary.get('叛军力量变化率', 0) > 0 else ''}{changes_summary.get('叛军力量变化率', 0):.2%}"
                f"- 平均满意度变化: {'+' if changes_summary.get('平均满意度变化', 0) > 0 else ''}{changes_summary.get('平均满意度变化', 0):.2%}"
                f"- 失业率变化: {'+' if changes_summary.get('失业率变化', 0) > 0 else ''}{changes_summary.get('失业率变化', 0):.2%}"
                f"- 叛乱次数: {changes_summary.get('叛乱次数', 0)}"
            )
            for official in self.government_officials.values():
                await official.store_memory(memory_content)
        
        elif group_type == 'rebellion':
            memory_content = (
                f"时间: {self.time.current_time}"
                f"决策内容: {decision}"
                f"执行结果:"
                f"- 叛军力量变化率: {'+' if changes_summary.get('叛军力量变化率', 0) > 0 else ''}{changes_summary.get('叛军力量变化率', 0):.2%}"
                f"- 叛军资源变化: {'+' if changes_summary.get('叛军资源变化', 0) > 0 else ''}{changes_summary.get('叛军资源变化', 0):.2%}"
            )
            for rebel in self.rebels_agents.values():
                await rebel.store_memory(memory_content)