"""
消融实验专用模拟器
用于实验：LLM驱动的复杂行为消融 (Ablation of LLM-driven Behavior)

该模拟器继承自原始Simulator类，但使用规则决策替代LLM决策，
以评估基于LLM的智能体决策模型相较于传统规则模型的优势。
"""

from .simulator_imports import *
from .simulator import Simulator
import random


class SimulatorAblation(Simulator):
    """
    消融实验模拟器类
    继承自原始Simulator，使用规则决策替代LLM决策
    """
    
    def __init__(self, *args, **kwargs):
        """初始化消融实验模拟器"""
        super().__init__(*args, **kwargs)
        self.logger.info("=== 消融实验模拟器已启动 ===")
        self.logger.info("使用规则决策替代LLM决策")
        
    @staticmethod
    def decide_action_by_rule(resident, tax_rate=0, basic_living_cost=0, climate_impact=0, **kwargs):
        """
        基于简单规则决定居民的行动（用于消融实验）
        
        规则逻辑：
        - 税率影响：当 tax_rate > 0.2 时，降低满意度，税率越高下降越快（单次最多-10）
        - 如果 satisfaction < 30 且有一定储蓄，则有50%概率选择"加入叛军"
        - 否则，如果无工作，则选择"寻找工作"
        - 其他情况继续当前工作
        
        Args:
            resident: 居民对象
            tax_rate: 当前税率
            basic_living_cost: 基本生活成本
            climate_impact: 天气影响因子
            **kwargs: 其他可选参数
        
        Returns:
            决策结果，格式与decide_action_by_llm保持一致
        """
        # 处理税率对满意度的影响
        if tax_rate > 0.2:
            # 税率超过0.2时开始降低满意度
            # 使用非线性公式：下降幅度 = min(10, (tax_rate - 0.2) * 50)
            # 这样 tax_rate=0.3 时下降5，tax_rate=0.4 时下降10（达到上限）
            tax_penalty = min(10, (tax_rate - 0.2) * 50)
            old_satisfaction = resident.satisfaction
            resident.satisfaction = max(0, resident.satisfaction - tax_penalty)
            if tax_penalty > 0:
                resident.resident_log.info(
                    f"[规则决策] 居民 {resident.resident_id} 因高税率({tax_rate:.2%})满意度下降 "
                    f"{tax_penalty:.1f}：{old_satisfaction:.1f} -> {resident.satisfaction:.1f}"
                )
        
        # 计算储蓄（假设基于收入和基本生活成本的差值）
        savings = max(0, resident.income - basic_living_cost) if resident.income else 0
        
        # 规则1：低满意度且有储蓄时，有概率加入叛军
        if resident.satisfaction < 30 and savings > 10:
            if random.random() < 0.5:  # 50%概率
                # 从配置文件中查找对应的动作
                actions = resident.actions_config.get('actions', {}) if resident.actions_config else {}
                
                # 查找"加入叛军"相关的动作
                rebel_action = None
                for action_id, action_info in actions.items():
                    if "叛军" in str(action_info.get('description', '')):
                        rebel_action = action_id
                        break
                
                if rebel_action:
                    resident.resident_log.info(
                        f"[规则决策] 居民 {resident.resident_id} 决定加入叛军"
                        f"（满意度：{resident.satisfaction}, 储蓄：{savings}）"
                    )
                    # 更新满意度
                    resident.satisfaction = max(0, resident.satisfaction - 20)
                    return str(rebel_action), "规则决策：满意度低且有储蓄，选择加入叛军"
        
        # 规则2：无工作时寻找工作
        if not resident.employed:
            # 获取当前城镇的空缺岗位信息
            if resident.job_market:
                vacant_jobs = resident.job_market.get_vacant_jobs()
                if vacant_jobs:
                    # 选择第一个可用职业
                    desired_job = list(vacant_jobs.keys())[0]
                    min_salary = resident.job_market.jobs_info[desired_job]['base_salary']
                    
                    resident.resident_log.info(
                        f"[规则决策] 居民 {resident.resident_id} 决定寻找工作：{desired_job}"
                        f"（最低薪资：{min_salary}）"
                    )
                    # 更新满意度
                    resident.satisfaction = min(100, resident.satisfaction + 5)
                    
                    # 返回求职信息
                    return {
                        "town": resident.town,
                        "desired_job": desired_job,
                        "min_salary": min_salary,
                        "resident_id": resident.resident_id,
                        "resident": resident
                    }
        
        # 规则3：其他情况继续当前工作
        resident.resident_log.info(f"[规则决策] 居民 {resident.resident_id} 决定继续当前工作")
        # 轻微调整满意度
        if resident.income >= basic_living_cost:
            resident.satisfaction = min(100, resident.satisfaction + 1)
        else:
            resident.satisfaction = max(0, resident.satisfaction - 2)
        
        return "2", "规则决策：继续当前工作"

    @staticmethod
    def decide_government_by_rule(budget, military_strength, tax_rate, gdp, rebellion_strength, 
                                   avg_satisfaction, transport_economy=None, map_navigability=1.0):
        """
        基于规则的政府决策（用于消融实验）
        
        规则逻辑：
        1. 税率调整：根据预算和满意度调整
        2. 公共预算：根据预算情况调整就业
        3. 运河维护：根据预算和通航能力决定
        4. 军事拨款：根据叛军威胁程度决定
        5. 运输决策：根据成本效益决定河运比例
        
        Args:
            budget: 当前预算
            military_strength: 军事力量
            tax_rate: 当前税率
            gdp: 当前GDP
            rebellion_strength: 叛军力量
            avg_satisfaction: 平均满意度
            transport_economy: 运输经济对象
            map_navigability: 运河通航能力
        
        Returns:
            决策JSON字符串
        """
        decision = {
            "tax_adjustment": 0,
            "public_budget": 0,
            "canal_maintenance": 0,
            "military_support": 0,
            "river_transport_ratio": 0.5
        }
        
        # 规则1：税率调整
        # - 预算紧张(budget < gdp*0.1)且税率低：增税
        # - 预算充足(budget > gdp*0.3)且满意度低：减税
        # - 满意度很低(<40)：减税
        if budget < gdp * 0.1 and tax_rate < 0.3:
            decision["tax_adjustment"] = 0.02  # 增税2%
        elif budget > gdp * 0.3 and avg_satisfaction < 60:
            decision["tax_adjustment"] = -0.02  # 减税2%
        elif avg_satisfaction < 40:
            decision["tax_adjustment"] = -0.03  # 大幅减税3%
        
        # 规则2：公共预算分配
        # - 预算充足且满意度低：增加就业
        # - 预算紧张：减少就业
        if budget > gdp * 0.2 and avg_satisfaction < 70:
            decision["public_budget"] = round(budget * 0.15, 2)  # 分配15%预算增加就业
        elif budget < gdp * 0.05:
            decision["public_budget"] = round(budget * 0.02, 2)  # 只维持最低就业
        else:
            decision["public_budget"] = round(budget * 0.08, 2)  # 正常维持就业
        
        # 规则3：运河维护
        # - 通航能力低(<0.6)且有预算：维护
        # - 通航能力高(>0.8)：不维护或少维护
        if transport_economy and map_navigability < 0.6 and budget > gdp * 0.1:
            decision["canal_maintenance"] = round(transport_economy.maintenance_cost_base * 0.8, 2)
        elif transport_economy and map_navigability < 0.8 and budget > gdp * 0.15:
            decision["canal_maintenance"] = round(transport_economy.maintenance_cost_base * 0.5, 2)
        else:
            decision["canal_maintenance"] = 0
        
        # 规则4：军事拨款
        # - 叛军威胁大(rebellion_strength > military_strength)：增加军力
        # - 叛军威胁小：维持或减少
        if rebellion_strength > military_strength * 1.2 and budget > gdp * 0.15:
            decision["military_support"] = round(budget * 0.2, 2)  # 分配20%预算扩军
        elif rebellion_strength > military_strength and budget > gdp * 0.1:
            decision["military_support"] = round(budget * 0.1, 2)  # 分配10%预算扩军
        else:
            decision["military_support"] = 0
        
        # 规则5：运输决策
        # - 通航能力高：多用河运（便宜）
        # - 通航能力低：多用海运
        if transport_economy:
            if map_navigability > 0.7:
                decision["river_transport_ratio"] = 0.8
            elif map_navigability > 0.5:
                decision["river_transport_ratio"] = 0.6
            else:
                decision["river_transport_ratio"] = 0.3
        
        import json
        return json.dumps(decision, ensure_ascii=False)

    @staticmethod
    def decide_rebellion_by_rule(rebellion_strength, rebellion_resources, government_military, 
                                  towns_stats, avg_satisfaction):
        """
        基于规则的叛军决策（用于消融实验）
        
        规则逻辑：只要城镇叛军数 > 官员数，就有60%概率发动叛乱
        
        Args:
            rebellion_strength: 叛军总力量
            rebellion_resources: 叛军资源
            government_military: 政府军总力量
            towns_stats: 城镇统计信息列表 [{"town_name":, "rebel_count":, "official_count":}]
            avg_satisfaction: 平均满意度
        
        Returns:
            决策JSON字符串
        """
        decision = {
            "action": "maintain",
            "target_town": None,
            "stage_rebellion": 0 
        }
        
        # 找出所有叛军数量大于官员数量的城镇
        advantageous_towns = []
        for town in towns_stats:
            rebel_count = town['rebel_count']
            official_count = town['official_count']
            
            # 只要叛军数 > 官员数，就是有利城镇
            if rebel_count > official_count:
                advantage = rebel_count - official_count
                advantageous_towns.append({
                    'town': town,
                    'advantage': advantage,
                    'rebel_count': rebel_count
                })
        
        # 如果没有有利城镇，直接返回
        if not advantageous_towns:
            import json
            return json.dumps(decision, ensure_ascii=False)
        
        # 选择优势最大的城镇
        best_town = max(advantageous_towns, key=lambda x: x['advantage'])
        
        # 60%概率发动叛乱（简单随机）
        if random.random() < 0.6:
            decision["action"] = "rebellion"
            decision["target_town"] = best_town['town']['town_name']
            # 投入该城镇80%的叛军
            decision["stage_rebellion"] = max(1, int(best_town['rebel_count'] * 0.8))
            decision["provocative_speech"] = ""
        
        import json
        return json.dumps(decision, ensure_ascii=False)

    async def collect_group_decision(self, group_type, config, max_rounds=2):
        """
        收集群体决策（消融实验版本：使用规则决策替代LLM）
        
        覆盖父类方法，在消融实验中使用规则决策而非LLM决策
        """
        self.logger.info(f"[规则决策] 开始收集 {group_type} 的决策")
        
        # 计算决策参数
        _, government_salary = self.calculate_total_salaries()
        
        if group_type == 'rebellion':
            # 叛军规则决策
            towns_stats = self.get_rebels_statistics()
            decision = self.decide_rebellion_by_rule(
                rebellion_strength=self.rebellion.get_strength(),
                rebellion_resources=self.rebellion.get_resources(),
                government_military=self.government.military_strength,
                towns_stats=towns_stats,
                avg_satisfaction=self.average_satisfaction
            )
            self.logger.info(f"[规则决策] 叛军决策: {decision}")
            return decision
            
        elif group_type == 'government':
            # 政府规则决策
            decision = self.decide_government_by_rule(
                budget=self.government.get_budget(),
                military_strength=self.government.military_strength,
                tax_rate=self.government.get_tax_rate(),
                gdp=self.gdp,
                rebellion_strength=self.rebellion.get_strength(),
                avg_satisfaction=self.average_satisfaction,
                transport_economy=self.transport_economy,
                map_navigability=self.map.get_navigability()
            )
            self.logger.info(f"[规则决策] 政府决策: {decision}")
            return decision
        
        return None

    async def run(self):
        """
        运行模拟（消融实验版本，使用规则决策）
        """
        self.start_time = datetime.now()  # 记录模拟开始时间
        
        # 创建结果文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
        
        self.logger.info(f"消融实验结果将保存到: {result_file}")
        
        while not self.time.is_end():
            # 打印当前时间步信息
            print(Back.GREEN + f"年份:{self.time.current_time} [消融实验-规则决策]" + Back.RESET)
            self.logger.info(f"年份:{self.time.current_time} [消融实验-规则决策]")
            current_year = self.time.current_time
            start_year = self.time.start_time
            self.logger.info(f"天气影响因子：{self.climate.get_current_impact(current_year,start_year)}")
            
            # 更新属性变量
            self.gdp = self.calculate_gdp()
            self.tax_income = self.gdp * self.government.get_tax_rate()
            self.government.budget = round(self.government.budget + self.tax_income, 2) 
            self.government.military_strength = self.calculate_total_government_military()
            self.rebellion_income = self.rebellion.get_strength() * 6
            self.rebellion.resources = round(self.rebellion.resources + self.rebellion_income, 2)
            self.rebellion.strength = self.calculate_total_rebels()
        
            self.average_satisfaction = self.calculate_average_satisfaction()
            self.population.update_birth_rate(self.average_satisfaction)
            self.rebellion_records = 0
            self.logger.info(f"GDP：{self.gdp}，税收收入：{self.tax_income}，政府预算：{self.government.budget}")
            self.logger.info(f"河运价格：{self.transport_economy.river_price}，维护成本：{self.transport_economy.calculate_maintenance_cost(self.map.get_navigability())}")

            # 居民出生
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

            # 收集政府和叛军的决策
            government_decision = None
            rebellion_decision = None
            
            # 收集政府决策
            government_config = {
                'agents': self.government_officials,
                'ordinary_type': OrdinaryGovernmentAgent,
                'leader_type': HighRankingGovernmentAgent,
            }
            government_decision = await self.collect_group_decision('government', government_config)
            
            # 收集叛军决策
            rebellion_config = {
                'agents': self.rebels_agents,
                'ordinary_type': OrdinaryRebel,
                'leader_type': RebelLeader,
            }
            rebellion_decision = await self.collect_group_decision('rebellion', rebellion_config)
            
            # 统一执行决策
            if government_decision:
                self.execute_government_decision(government_decision)
            if rebellion_decision:
                self.execute_rebellion_decision(rebellion_decision)

            # 重置社交网络的对话计数器
            self.social_network.reset_dialogue_count()

            # === 居民行为（使用规则决策） ===
            tasks = []
            speech_tasks = []
            town_job_requests = defaultdict(list)
            
            tax_rate = self.government.get_tax_rate()
            climate_impact = self.climate.get_current_impact(self.time.current_time, self.time.start_time)
            
            for resident_name in list(self.residents.keys()):
                resident = self.residents[resident_name]
                
                # 使用规则决策替代LLM决策
                if resident.job == "叛军":
                    tasks.append(resident.generate_provocative_opinion(self.propaganda_prob, self.propaganda_speech))
                else:
                    # 调用静态方法进行规则决策
                    result = self.decide_action_by_rule(
                        resident=resident,
                        tax_rate=tax_rate, 
                        basic_living_cost=self.basic_living_cost,
                        climate_impact=climate_impact
                    )
                    # 将同步结果包装为已完成的Future
                    future = asyncio.Future()
                    future.set_result(result)
                    tasks.append(future)

                # 更新居民寿命
                if resident.update_resident_status(self.basic_living_cost):
                    del self.residents[resident_name]
                    self.population.death()
                    continue

            # 并发执行所有居民的行为并收集结果
            if tasks:
                results = await asyncio.gather(*tasks)
                
                # 处理返回的结果
                residents_list = list(self.residents.values())
                job_request_count = 0
                for i, result in enumerate(results):
                    if i >= len(residents_list):
                        break
                    resident = residents_list[i]
                    
                    if isinstance(result, dict) and "desired_job" in result:
                        town = result["town"]
                        town_job_requests[town].append(result)
                        job_request_count += 1
                    elif isinstance(result, tuple) and len(result) >= 2:
                        select, reason = result[0], result[1]
                        speech = result[2] if len(result) >= 3 else None
                        selected_type = result[3] if len(result) >= 4 else None
                        
                        decision_result = await resident.execute_decision(select, reason=reason)
                        
                        if speech and selected_type:
                            speech_task = self.social_network.propagate_speech(
                                resident.resident_id, 
                                speech, 
                                selected_type
                            )
                            speech_tasks.append(speech_task)
                
                if job_request_count > 0:
                    self.logger.info(f"共收到 {job_request_count} 个求职请求")
                
                # 并发执行所有发言传播任务
                if speech_tasks:
                    await asyncio.gather(*speech_tasks)
            
            # 处理所有城镇的求职信息
            if town_job_requests:
                self.logger.info(f"\n开始处理 {len(town_job_requests)} 个城镇的求职请求")
                hiring_results = self.towns.process_town_job_requests(town_job_requests)
            else:
                self.logger.info("\n本轮无求职请求")

            # 更新结果数据
            self.update_results()
            
            # 在每个时间步结束时保存结果
            self.save_results(result_file, append=True)

            # 保存居民微观状态（实时更新）
            ResidentStateExporter.save_resident_data(self)
            
            # 时间前进
            self.time.step()

        self.end_time = datetime.now()
        self.display_total_simulation_time()
        self.social_network.plot_degree_distribution()
        
        self.logger.info(f"=== 消融实验完成，结果已保存到 {result_file} ===")
