from .shared_imports import *
from ..utils.logger import LogManager
import inspect
import importlib
load_dotenv()

class ResidentSharedInformationPool:
    def __init__(self):
        self.shared_info = {
            'economic_status': {},
            'social_network': {},
            'environment_awareness': {}
        }

    def add_shared_info(self, key, value, category):
        if category not in self.shared_info:
            self.shared_info[category] = {}
        self.shared_info[category][key] = value

    def get_shared_info(self, category=None):
        if category:
            return self.shared_info.get(category, {})
        return self.shared_info

class ResidentGroup(BaseAgent):
    """居民群组，用于管理同一城镇的居民"""
    def __init__(self, town_name):
        super().__init__(agent_id=f"group_{town_name}", group_type='resident_group', window_size=3)
        self.town_name = town_name
        self.residents = {}
        self.social_network = None

    def add_resident(self, resident):
        """添加居民到群组"""
        self.residents[resident.resident_id] = resident
        # 设置共享的 LLM 资源
        resident.model_backend = self.model_backend
        resident.token_counter = self.token_counter
        resident.context_creator = self.context_creator
        resident.memory = MemoryManager(
            agent_id=resident.resident_id,
            model_type=self.model_type,
            group_type='resident',
            window_size=5
        )
        # resident.memory.set_agent(resident)
        # 设置居民所属的群组
        resident.set_group(self)

    def set_social_network(self, social_network):
        """设置群组的社交网络"""
        self.social_network = social_network

    def remove_resident(self, resident_id):
        """从群组中移除居民"""
        if resident_id in self.residents:
            resident = self.residents[resident_id]
            resident.set_group(None)  # 清除居民的群组引用
            del self.residents[resident_id]

class Resident(BaseAgent):
    def __init__(self, resident_id, job_market, shared_pool, map, resident_prompt_path, resident_actions_path, window_size=3):
        """初始化居民"""
        super().__init__(agent_id=resident_id, group_type='resident', window_size=window_size)
        self.resident_id = resident_id
        self.job_market = job_market
        self.shared_pool = shared_pool
        self.map = map
        self.location = None
        self.town = None  # 城镇属性
        self.employed = False  # 是否就业
        self.job = None  # 当前工作
        self.income = 0  # 收入
        self.satisfaction = 0  # 对政府的满意度（0到100）
        self.health_index = 0 # 居民的健康状况（1到5）
        self.lifespan = 0  # 居民的寿命
        self.towns_manager = None  # Towns实例的引用
        self.group = None  # 所属群组的引用
        self.personality = None
        self.system_message = None  # 系统提示词
        with open(os.path.join(resident_prompt_path), 'r', encoding='utf-8') as file:
            self.prompts_resident = yaml.safe_load(file)
        # 加载行为配置
        with open(os.path.join(resident_actions_path), 'r', encoding='utf-8') as file:
            self.actions_config = yaml.safe_load(file)

        # 由 ResidentGroup 设置agent属性
        self.model_backend = None
        self.token_counter = None
        self.context_creator = None

        self.resident_log = LogManager.get_logger("resident")

    def set_group(self, group):
        """设置居民所属的群组"""
        self.group = group

    def get_social_network(self):
        """通过群组获取社交网络"""
        return self.group.social_network if self.group else None

    def employ(self, job, salary=None):
        """
        居民就业
        :param job: 工作名称
        :param salary: 工作收入，如果未指定则使用职业默认收入
        """
        self.employed = True
        self.job = job
        
        # 如果指定了收入，使用指定的收入；否则从就业市场获取该职业的标准收入
        if salary is not None:
            self.income = salary
        elif self.job_market and job in self.job_market.jobs_info:
            self.income = self.job_market.jobs_info[job]["salary"]
        else:
            self.income = 0
        if self.job == "叛军":
            # self.satisfaction = max(0, self.satisfaction - 50)  # 叛军降低满意度
            self.resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 加入了叛军。")
        else:
            self.resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 找到了工作：{job}，收入：{self.income}。")
    
    def unemploy(self):
        """
        居民失业
        """
        self.employed = False
        self.job = None
        self.income = 0
        self.resident_log.info(f"居民 {self.resident_id} 目前无业")

    def update_system_message(self, basic_living_cost=0, tax_rate=0):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        health_condition = self.prompts_resident['health_conditions'][self.health_index] if 0 <= self.health_index < len(self.prompts_resident['health_conditions']) else "未知"
        work_condition = self.job if self.employed else "无业游民"
        satisfaction_description = self.prompts_resident['satisfaction_levels'][min(self.satisfaction // 20, 4)]
        
        economic_status_description = ""
        if self.income > 0 :
            income = self.income * (1 - tax_rate)
            if basic_living_cost > income:
                economic_status_description = "终日辛劳不得温饱"
            elif basic_living_cost * 2 > income:
                economic_status_description = "勉强糊口"
            elif basic_living_cost * 4 > income:
                economic_status_description = "生活尚算安稳"
            else:
                economic_status_description = "生活富裕丰衣足食"
        else:
            economic_status_description = "家破人亡难以为继"

        self.system_message = self.prompts_resident['resident_system_message'].format(
            work_condition=work_condition,
            personality=self.personality,
            income=self.income,
            economic_status_description=economic_status_description,
            health_condition=health_condition,
            satisfaction_description=satisfaction_description,
            satisfaction=self.satisfaction
        )

    async def receive_information(self, message_content):
        """
        接收信息（如政府政策、叛乱信息）
        """
        # 从配置中获取回应概率
        response_prob = global_config.get("simulation", {}).get("response_probability")
        if random.random() < response_prob:
            # 构建回应提示词
            prompt = self.prompts_resident['receive_information_prompt'].format(message_content=message_content)

            self.update_system_message()
            response_content = await self.generate_llm_response(prompt)
            
            if response_content and "None" not in response_content:
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                self.resident_log.info(f"居民 {self.resident_id} 对收到的信息「{message_content}」做出回应：{response_content}")
                
                # 将自己的回应存入记忆
                await self.memory.write_record(
                    role_name=self.resident_id,
                    content=f"对信息「{message_content}」的回应：{response_content}",
                    is_user=False
                )
                
                return response_content, selected_type

        return None

    async def decide_action_by_llm(self, tax_rate, basic_living_cost, climate_impact=0):
        """
        通过LLM决定居民的行动，并随机生成对政府的态度发言。同时更新满意度。
        
        Args:
            tax_rate: 当前税率
            basic_living_cost: 基本生活成本
            climate_impact: 天气影响因子，默认为0
        """
        # 发言概率基于节点在社交网络中的度值
        speech_prob = 0.0
        social_network = self.get_social_network()
        if social_network:
            speech_prob = social_network.calculate_speech_probability(self.resident_id)
        need_speech = random.random() < speech_prob
    
        # 如果是未就业居民，获取当前城镇的空缺岗位信息
        job_market_info = ""
        if not self.employed and self.town and self.job_market:
            vacant_jobs = self.job_market.get_vacant_jobs()
            if vacant_jobs:
                job_market_info = "以下是当前可用工作岗位：\n" + "\n".join(
                    f"- {job}: {count}个空缺, 基础收入：{self.job_market.jobs_info[job]['base_salary']}"
                    for job, count in vacant_jobs.items()
                )
        rebel_salary = self.job_market.get_job_salary("叛军")
    
        # 构建税率和天气状况信息
        tax_rate_message = ""
        if tax_rate < 0.05:
            tax_rate_message = "当前税率极低，几乎无税负担。\n"
        elif tax_rate < 0.15:
            tax_rate_message = "当前税率适中，负担一般。\n"
        elif tax_rate < 0.3:
            tax_rate_message = "当前税率较高，负担较重。\n"
        else:
            tax_rate_message = "当前税率极高，负担极重。\n"
        
        # 添加天气状况信息
        weather_condition = ""
        if climate_impact <= 0.2:
            weather_condition = "天气良好，适宜农耕。"
        elif climate_impact <= 0.4:
            weather_condition = "天气一般，对农耕有轻微影响。"
        elif climate_impact <= 0.6:
            weather_condition = "天气较差，农耕受到明显影响。"
        elif climate_impact <= 0.8:
            weather_condition = "天气恶劣，农耕困难。"
        else:
            weather_condition = "天气极端恶劣，农耕几乎无法进行。"
        
        employed = self.employed
    
        # 根据是否就业选择不同的提示词模板
        if self.job == "城市居民":
            prompt = self.prompts_resident['decide_action_prompt_city_resident'].format(
                tax_rate_message=tax_rate_message, 
                job_market_info=job_market_info,
                weather_condition=weather_condition)
        elif employed:
            prompt = self.prompts_resident['decide_action_prompt_employed'].format(
                tax_rate_message=tax_rate_message, 
                job_market_info=job_market_info,
                weather_condition=weather_condition)
        else:
            prompt = self.prompts_resident['decide_action_prompt_unemployed'].format(
                tax_rate_message=tax_rate_message, 
                job_market_info=job_market_info,
                weather_condition=weather_condition)
    
        # 构建 desired_job_and_min_salary 和 speech
        desired_job_and_min_salary = self.prompts_resident['decide_action_json'].format(
            desired_job_and_min_salary=', "desired_job": 期望职业（如果选择2，可选：农民、商人、官员及士兵、运河维护工、普通工作者）, "min_salary": 可接受的最低收入（数字）' if not self.employed and job_market_info else '',
            speech=', "speech": 一句有传播力的态度言论，允许负面、质疑或愤怒情绪。}' if need_speech else '}')
    
        # 将 desired_job_and_min_salary 和 speech 插入到 prompt 中
        prompt += desired_job_and_min_salary
        try:
            self.update_system_message(basic_living_cost)
            response = await self.generate_llm_response(prompt)
            if not response:
                return "2", "发生错误，继续当前工作"
    
            # 清理LLM返回的字符串，移除可能存在的```json和```标记以及换行符
            cleaned_response = re.sub(r"^```json\s*|\s*```$", "", response, flags=re.DOTALL).strip()
            cleaned_response = re.sub(r'\s+', '', cleaned_response, flags=re.DOTALL)  # 删除所有空白字符，包括换行符
            cleaned_response = re.sub(r'}(?=.*})', '', cleaned_response, flags=re.DOTALL)

            decision_data = json.loads(cleaned_response)
            select = decision_data.get("select")
            reason = decision_data.get("reason")
            speech = decision_data.get("speech", "")
            satisfaction_change = decision_data.get("satisfaction_change")
            desired_job = decision_data.get("desired_job")
            min_salary = decision_data.get("min_salary")
    
            if satisfaction_change is not None:
                # 确保满意度在0-100范围内
                old_satisfaction = self.satisfaction
                self.satisfaction = max(0, min(100, self.satisfaction + satisfaction_change))
                # print(f"居民 {self.resident_id} 收到满意度变化{satisfaction_change}：{old_satisfaction} -> {self.satisfaction}")

            # 记录居民的决策信息
            if desired_job is None and min_salary is None:
                self.resident_log.info(f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}, 更新满意度：{self.satisfaction}")
            else:
                self.resident_log.info(f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}, 期望职业：{desired_job}, 最低收入：{min_salary}, 更新满意度：{self.satisfaction}")
    
            # 返回决策结果
            if select == "3" and not self.employed and desired_job and min_salary:
                # 返回求职信息
                return {
                    "town": self.town, 
                    "desired_job": desired_job, 
                    "min_salary": min_salary,
                    "resident_id": self.resident_id 
                }
            elif speech:
                # 返回带有发言的决策结果
                relation_types = ["friend", "colleague", "family", "hometown"]
                # 随机选择一种关系类型
                selected_type = random.choice(relation_types)
                return select, reason, speech, selected_type
            else:
                # 返回普通决策结果
                return select, reason
    
        except Exception as e:
            self.resident_log.error(f"居民 {self.resident_id} 决策出错：{e}")
            self.resident_log.error(f"居民 {self.resident_id} 返回内容：{response}")
            return "2", "发生错误，继续当前工作"  # 默认选择继续工作

    async def execute_decision(self, select, *args, **kwargs):
        """
        根据配置动态执行居民的决策。
        """
        try:
            actions = self.actions_config.get('actions', {}) if self.actions_config else {}
            
            # 统一转换select并查找动作
            action = actions.get(select) or actions.get(str(select)) or (
                actions.get(int(select)) if str(select).isdigit() else None
            )
            if not action or not (func_path := action.get('function')):
                self.resident_log.error(f"居民 {self.resident_id} 未找到有效的动作配置：{select}")
                return False

            # 解析函数路径
            parts = func_path.split('.') if isinstance(func_path, str) else []
            callable_obj = None

            # 尝试在self对象上解析
            try:
                obj = self
                for p in parts:
                    obj = getattr(obj, p)
                callable_obj = obj
            except AttributeError:
                # 尝试作为模块路径导入
                try:
                    if len(parts) > 1:
                        module = importlib.import_module('.'.join(parts[:-1]))
                        callable_obj = getattr(module, parts[-1])
                except (ImportError, AttributeError):
                    pass

            if not callable_obj:
                self.resident_log.error(f"居民 {self.resident_id} 无法解析函数：{func_path}")
                return False

            # 构建参数
            available = {**{k: v for k, v in self.__dict__.items()}, **kwargs}
            default_values = {
                param['name']: param.get('default') 
                for param in action.get('parameters', []) 
                if 'default' in param
            }

            bound_kwargs = {}
            if sig := inspect.signature(callable_obj, follow_wrapped=True):
                for pname, param in sig.parameters.items():
                    if pname in available:
                        bound_kwargs[pname] = available[pname]
                    elif pname in default_values and default_values[pname] is not None:
                        bound_kwargs[pname] = default_values[pname]
                    elif param.default is inspect.Parameter.empty:
                        bound_kwargs[pname] = self
            else:
                bound_kwargs = available

            # 执行函数
            is_async = action.get('is_async', False) or inspect.iscoroutinefunction(callable_obj)
            try:
                return await callable_obj(**bound_kwargs) if is_async else callable_obj(**bound_kwargs)
            except TypeError:
                # 参数绑定失败时的降级处理
                return await kwargs if is_async else callable_obj(**kwargs)

        except Exception as e:
            self.resident_log.error(f"居民 {self.resident_id} 执行决策时出错：{e}")
            return False

    def handle_work(self, desired_job=None, min_salary=None):
        """
        处理居民寻找工作或继续工作的逻辑
        """
        if self.job_market and self.employed:
            self.resident_log.info(f"居民 {self.resident_id} 已有工作：{self.job}，继续目前工作")
            return True
        elif desired_job and min_salary:
            # 返回求职信息
            return {
                "town": self.town, 
                "desired_job": desired_job, 
                "min_salary": min_salary,
                "resident_id": self.resident_id 
            }
        return True

    async def generate_provocative_opinion(self, probability, speech):
        """
        处理居民是叛军时的特殊逻辑，生成煽动性言论
        :param probability: 发言概率
        :return: 生成的言论
        """
        # 根据概率决定是否发表煽动性言论
        if random.random() < probability:
            if speech:
                opinion = speech
            else:
                # 构建煽动性提示信息
                prompt = self.prompts_resident['generate_provocative_opinion_prompt']
                
                self.update_system_message()
                opinion = await self.generate_llm_response(prompt)

            if opinion:
                self.resident_log.info(f"叛军 {self.agent_id} 发表煽动性言论：{opinion}")
                # 随机选择一种关系类型
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                return opinion,selected_type
        return "未发表煽动性言论"

    async def receive_and_decide_response(self, message: dict, year):
        """
        接收公共知识通知，由LLM决定是否发言
        """
        content = message.get("content")
        public_notice = message.get("public_notice")
        if content:
            message_content = f"你收到了政府发布的详细信息：[{content}]" 
        else:
            message_content = "你没有收到政府信息。" 
        
        # 构建提示词
        if year == 0:
            # await self.memory.write_record(
            #         role_name="居民",
            #         content=message_content,
            #         is_user=False,
            #         store_in_shared=False,
            #         )
            prompt = self.prompts_resident['receive_and_decide_response_prompt'].format(
                public_notice=public_notice,
                message_content=message_content
            )
        else:
            prompt = self.prompts_resident['receive_and_decide_response_prompt'].format(
                public_notice="",
                message_content=""
            )
        try:
            self.update_system_message()
            response = await self.generate_llm_response(prompt)
            import json
            if response:
                try:
                    response_json = json.loads(response)
                    select_choice = response_json.get("select")
                    select_reason = response_json.get("reason")
                    speech_content = response_json.get("speech", "")
                    self.resident_log.info(f"居民 {self.resident_id} 选择：{select_choice}, 原因：{select_reason}")
                    if year == 0:
                        await self.memory.write_record(
                            role_name="居民",
                            content=message_content + public_notice,
                            is_user=False,
                            store_in_shared=False,
                        )
                    if select_choice == 2 and speech_content:
                        await self.memory.write_record(
                            role_name="居民",
                            content=f"我发表言论：{speech_content}",
                            is_user=False,
                            store_in_shared=False
                        )
                        self.resident_log.info(f"居民 {self.resident_id}发起讨论: {speech_content}")
                        # 返回带有发言的决策结果
                        relation_types = ["friend", "colleague", "family", "hometown"]
                        # 随机选择一种关系类型
                        selected_type = random.choice(relation_types)
                        return speech_content, selected_type
                    else:
                        await self.memory.write_record(
                            role_name="居民",
                            content=f"我保持沉默",
                            is_user=False,
                            store_in_shared=False
                        )
                        self.resident_log.info(f"居民 {self.resident_id} 选择沉默")
                        return None
                except json.JSONDecodeError:
                    self.resident_log.error(f"居民 {self.resident_id} 解析LLM响应失败: {response}")
                    return None
            else:
                await self.memory.write_record(
                    role_name="居民",
                    content=f"我保持沉默",
                    is_user=False,
                    store_in_shared=False
                )
                self.resident_log.info(f"居民 {self.resident_id} 选择沉默")
                return None
            
        except Exception as e:
            self.resident_log.error(f"居民 {self.resident_id} 处理公共知识出错: {e}")
            return None

    async def make_survey_request(self, prompt: str):
        """通用方法：构建提示词，获取LLM响应并进行初步清理"""
        try:
            # 更新系统消息以确保最新状态
            self.update_system_message()
            
            # 获取LLM响应
            response = await self.generate_llm_response(prompt)
            if not response:
                return None
                
            # 清理LLM返回的字符串
            cleaned_response = response.strip()
            
            # 记录问卷结果
            self.resident_log.info(f"居民 {self.resident_id} 回应: {cleaned_response}")
            
            # 返回选择结果
            return cleaned_response
            
        except Exception as e:
            self.resident_log.error(f"居民 {self.resident_id} 进行信息请求出错: {e}")
            return None
    
    async def update_knowledge_memory(self,prompt:str):
        """
        定期更新居民的知识记忆,专注于居民个人的知识和经历总结
        """
        # 确保 self.memory 和 self.memory.personal_memory 都存在
        if self.memory and hasattr(self.memory, 'personal_memory'):
            # 构建提示词
            prompt = self.prompts_resident[prompt].format()
            
            # 生成知识总结
            self.update_system_message()  # 确保系统消息是最新的
            knowledge_summary = await self.generate_llm_response(prompt)
            
            if knowledge_summary:
                # 清空原有记忆
                await self.memory.clear()  # 清除所有记忆
                
                # 将新的知识总结添加到长期记忆中
                self.memory.personal_memory.longterm_memory.append(knowledge_summary)
                self.memory.personal_memory.record_count = 0  # 重置计数器
                
                # 记录日志
                self.resident_log.info(f"居民 {self.resident_id} 更新了记忆：{knowledge_summary}")

    def print_resident_status(self):
        """
        打印居民状态（用于调试）
        """
        self.resident_log.info(f"居民 {self.resident_id} 在 {self.town} 的 {self.location} 的状态：")
        self.resident_log.info(f"  是否就业：{self.employed}")
        self.resident_log.info(f"  工作：{self.job}")
        self.resident_log.info(f"  收入：{self.income}")
        self.resident_log.info(f"  满意度：{self.satisfaction}")
        self.resident_log.info(f"  健康状况：{self.health_index}")
        self.resident_log.info(f"  寿命：{self.lifespan}")
        self.resident_log.info(f"  性格：{self.personality}")

    def handle_death(self):
        """
        处理居民死亡的逻辑
        """
        # 从就业市场和城镇中移除
        if self.town and self.towns_manager:
            self.towns_manager.remove_resident_in_town(self.resident_id, self.town, self.job)
            self.employed = False
            self.job = None

        # 从社交网络中移除（如果存在）
        social_network = self.get_social_network()
        if social_network:
            # 从异质图中移除
            social_network.hetero_graph.remove_node(self.resident_id)
            # 从超图中移除
            social_network.hyper_graph.remove_node(self.resident_id)

        self.resident_log.info(f"居民 {self.resident_id} 已死亡。")
        return True

    def update_resident_status(self, basic_living_cost):
        """
        更新居民状况，包括健康状况和寿命
        如果居民死亡则返回True，否则返回False
        """
        # 先更新健康状况
        self.update_health_index(basic_living_cost)
        
        # 根据健康状况更新寿命
        return self.update_lifespan()

    def update_health_index(self, basic_living_cost):
        """根据收入和满意度等因素更新健康状况"""
        # 叛军职业的额外健康影响
        if self.job == "叛军":
            self.health_index = max(0, self.health_index - 2)  # 叛军生活艰苦，健康快速下降

        # 基于收入的健康影响
        if self.income <= 0:
            self.health_index = max(0, self.health_index - 2)  # 无收入严重影响健康
        elif self.income < basic_living_cost:
            self.health_index = max(0, self.health_index - 1)  # 收入不足影响健康
        elif self.income >= basic_living_cost * 2:
            # 高收入恢复健康
            if self.job == "叛军":  #叛军恢复较少
                self.health_index = min(10, self.health_index + 0.5)
            else:
                self.health_index = min(10, self.health_index + 1)

        # 基于满意度的健康影响
        if self.satisfaction < 30:
            self.health_index = max(0, self.health_index - 1)  # 低满意度影响健康
        elif self.satisfaction > 80:
            # 高满意度恢复健康
            if self.job == "叛军":  #叛军恢复较少
                self.health_index = min(10, self.health_index + 0.5)
            else:
                self.health_index = min(10, self.health_index + 1)
        
        # 确保健康指数在0-10范围内
        self.health_index = int(max(0, min(10, self.health_index)))

    def update_lifespan(self):
        """
        检查健康状况并更新寿命
        如果寿命更新后为0，认为该居民死亡，输出提示信息并从列表中删除该用户
        """
        if self.health_index <= 1:
            self.lifespan -= 5
        else:
            self.lifespan -= 1

        if self.lifespan <= 0:
            return self.handle_death()
        else:
            # self.resident_log.info(f"居民 {self.resident_id} 的健康状况为 {self.health_index}，寿命更新为 {self.lifespan}。")
            return False

    def get_random_direction_town(self, map):
        """随机选择一个相邻城市进行迁移"""
        try:
            current_town_name = self.town
            
            if not current_town_name:
                self.resident_log.info(f"居民 {self.resident_id} 无法找到当前位置对应的城市")
                return None

            # 获取相连的城市
            connected_towns = map.get_connected_towns(current_town_name)
            if not connected_towns:
                self.resident_log.info(f"城市 {current_town_name} 没有相连的城市")
                return None

            # 随机选择一个相连的城市
            next_town = random.choice(connected_towns)
            return next_town
            
        except Exception as e:
            self.resident_log.error(f"选择迁移目标城市时出错: {e}")
            return None

    async def migrate_to_new_town(self, map, update_job=True):
        """
        迁移到新城镇
        
        Args:
            map: 地图对象
            update_job: 是否更新职业，如果为False则保留原职业
        """
        # 获取目标城市
        target_town = self.get_random_direction_town(map)
        if not target_town:
            self.resident_log.info(f"居民 {self.resident_id} 未找到合适的迁移目标城市")
            return False

        # 生成新位置
        new_location = map.generate_random_location(target_town)

        # 保存旧城镇信息
        old_town = self.town
        old_job = self.job

        # 从原城镇中移除居民
        if self.towns_manager and old_town:
            self.towns_manager.remove_resident_in_town(self.resident_id, old_town, old_job)

        # 更新居民信息
        self.location = new_location
        self.town = target_town
        
        # 根据update_job参数决定是否清除职业信息
        if update_job:
            self.unemploy()
        
        # 将居民添加到新城镇
        if self.towns_manager:
            self.towns_manager.add_resident(self, target_town)
            # 如果不更新职业，则重新分配原来的工作
            if not update_job and old_job:
                self.job_market.assign_specific_job_withoutcheck(self, old_job)

        self.resident_log.info(f"居民 {self.resident_id} 从 {old_town} 迁移到了 {target_town}")
        return True

    def set_town(self, town_name, towns_manager):
        """
        设置居民所在的城镇和towns_manager
        """
        self.town = town_name
        self.towns_manager = towns_manager
        if self.towns_manager and self.town:
            self.job_market = self.towns_manager.get_town_job_market(self.town)

    async def reset_experimental_state(self):
        """
        重置居民实验状态，主要用于删除记忆
        """
        if self.memory:
            await self.memory.clear()  # 清除所有记忆
