from .shared_imports import *
import re
load_dotenv()

if "sphinx" not in sys.modules:
    resident_log = logging.getLogger(name="resident.agent")
    resident_log.setLevel("DEBUG")
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_handler = logging.FileHandler(f"./log/resident.agent-{str(now)}.log")
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
    resident_log.addHandler(file_handler)

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
    def __init__(self, resident_id, job_market, shared_pool, map):
        """初始化居民"""
        super().__init__(agent_id=resident_id, group_type='resident', window_size=3)
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

        # 由 ResidentGroup 设置agent属性
        self.model_backend = None
        self.token_counter = None
        self.context_creator = None
        self.memory = None

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
            self.satisfaction -= 50  # 叛军降低满意度
            resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 加入了叛军。")
        else:
            self.satisfaction += 10  # 就业增加满意度
            resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 找到了工作：{job}，收入：{self.income}。")
    
    def unemploy(self):
        """
        居民失业
        """
        self.employed = False
        self.job = None
        self.income = 0
        self.satisfaction -= 20  # 失业降低满意度
        resident_log.info(f"居民 {self.resident_id} 目前无业")
        # if old_job:
        #     resident_log.info(f"居民 {self.resident_id} 失去工作工作：{old_job}")
        # else:
        #     resident_log.info(f"居民 {self.resident_id} 目前无业")

    def update_system_message(self, basic_living_cost=0):
        """
        更新系统提示词，包含居民当前的状态信息
        """
        health_conditions = ["", "健康状况非常差", "亚健康", "一般健康", "健康", "极健康"]
        health_condition = health_conditions[self.health_index] if 1 <= self.health_index <= 5 else "未知"
        work_condition = self.job if self.employed else "无业游民"
        satisfaction_levels = ["恨之入骨，誓要推翻朝廷", "怨气深重，斥其昏庸无道", "漠然视之，不过问政事", "尚可接受，愿安分守己", "衷心拥戴，誓死效忠"]
        satisfaction_description = satisfaction_levels[min(self.satisfaction // 20, 4)]
        
        economic_status_description = ""
        if self.income > 0 :
            if basic_living_cost > self.income:
                economic_status_description = "生活困难"
            elif basic_living_cost * 2 > self.income:
                economic_status_description = "收支勉强平衡"
            elif basic_living_cost * 4 > self.income:
                economic_status_description = "小康"
            else:
                economic_status_description = "生活富裕"
        else:
            economic_status_description = "生活极度困难"

        self.system_message = (
            f"你是一个清代普通{work_condition}，你{self.personality}，收入为{self.income}两，{economic_status_description}，{health_condition}，目前对政府{satisfaction_description}。"
        )

    async def receive_information(self, message_content):
        """
        接收信息（如政府政策、叛乱信息）
        """
        # self.satisfaction += 5  # 接收信息增加满意度
        # 从配置中获取回应概率
        response_prob = global_config.get("simulation", {}).get("response_probability")
        if random.random() < response_prob:
            # 构建回应提示词
            prompt = (
                # f"当前税率:为{tax_rate*100:.1f}%，基本生活所需为{basic_living_cost}两\n"
                f"你听说了一条信息：{message_content}\n"
                f"请表达你的真实感受与想法，并用尽可能简短的一句话讲给更多人。"
            )

            self.update_system_message()
            response_content = await self.generate_llm_response(prompt)
            
            if response_content:
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                resident_log.info(f"居民 {self.resident_id} 对收到的信息「{message_content}」做出回应：{response_content}")
                
                # 将自己的回应存入记忆
                await self.memory.write_record(
                    role_name=self.resident_id,
                    content=f"对信息「{message_content}」的回应：{response_content}",
                    is_user=False
                )
                
                return response_content, selected_type

        return None

    async def decide_action_by_llm(self, tax_rate, basic_living_cost):
        """
        通过LLM决定居民的行动，并随机生成对政府的态度发言。同时更新满意度。
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

        base_prompt = (
            f"当前税率:为{tax_rate*100:.1f}%，基本生活所需为{basic_living_cost}两\n"
            f"{job_market_info}"
            f"你可以选择以下行动之一：\n"
            f"1. 参加叛乱\n"
            f"2. {'迁徙至他地（有生存风险，会失去当前工作，需重新谋生）'if self.employed else '迁徙至他地（有生存风险）'}\n"
        )
        if job_market_info:
            base_prompt += f"3. {'寻找工作' if not self.employed else '继续目前的工作'}\n"

        # 规范输出
        prompt = base_prompt + (
            "综合考虑收入是否足以维生、就业稳定性、税负情况及健康状况等因素，选择最适合自己的行动。"
            "返回单行的JSON字符串，格式如下，必须严格按照格式填写：\n"
            + '{"select": 你的选择（1-3）, "reason": 选择原因, "satisfaction_change": 满意度变化值(-20到20)'
            + (', "desired_job": 期望职业（如果选择2，可选：农民、商人、官员及士兵、运河维护工、普通工作者）, "min_salary": 可接受的最低收入（数字）' if not self.employed and job_market_info else '')
            + (', "speech": 一句有传播力的态度言论，允许负面、质疑或愤怒情绪。}' if need_speech else '}')
        )

        try:
            self.update_system_message(basic_living_cost)
            response = await self.generate_llm_response(prompt)
            if not response:
                return "2", "发生错误，继续当前工作"

            # 清理LLM返回的字符串，移除可能存在的```json和```标记
            cleaned_response = re.sub(r"^```json\s*|\s*```$", "", response, flags=re.DOTALL).strip()
            
            decision_data = json.loads(cleaned_response)
            select = decision_data.get("select")
            reason = decision_data.get("reason")
            speech = decision_data.get("speech", "")
            satisfaction_change = decision_data.get("satisfaction_change")
            desired_job = decision_data.get("desired_job")
            min_salary = decision_data.get("min_salary")

            if satisfaction_change is not None:
                # 确保满意度在0-100范围内
                self.satisfaction = max(0, min(100, self.satisfaction + satisfaction_change))

            # 记录居民的决策信息
            if desired_job is None and min_salary is None:
                resident_log.info(f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}, 更新满意度：{self.satisfaction}")
            else:
                resident_log.info(f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}, 期望职业：{desired_job}, 最低收入：{min_salary}, 更新满意度：{self.satisfaction}")


            # 执行决策
            if select == 3 and not self.employed:
                # 如果选择找工作，则传入期望职业和最低收入
                job_request = await self.execute_decision(select, desired_job, min_salary)
                if isinstance(job_request, dict):
                    return job_request  # 返回求职信息
            else:
                await self.execute_decision(select)

            # 如果有发言，返回发言信息和关系类型
            if speech:
                resident_log.info(f"居民 {self.resident_id} 发言：{speech}")
                relation_types = ["friend", "colleague", "family", "hometown"]
                # 随机选择一种关系类型
                selected_type = random.choice(relation_types)
                return select, reason, speech, selected_type

            return select, reason

        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 决策出错：{e}")
            resident_log.error(f"居民 {self.resident_id} 返回内容：{response}")
            return "2", "发生错误，继续当前工作"  # 默认选择继续工作

    async def execute_decision(self, select, desired_job=None, min_salary=None):
        """
        执行居民的决策
        """
        try:
            if select == 1:  # 参加叛乱
                self.job_market.assign_rebel(self)
                return True
            
            elif select == 2:
                # 迁移到新城镇
                self.satisfaction -= 10  # 路途奔波
                success = await self.migrate_to_new_town(self.map)
                if not success:
                    resident_log.info(f"居民 {self.resident_id} 迁移失败，保持原位置")
                return success
            
            elif select == 3:  # 寻找工作或继续工作
                if self.employed:
                    resident_log.info(f"居民 {self.resident_id} 已有工作：{self.job}，继续目前工作")
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
            
            else:
                resident_log.error(f"居民 {self.resident_id} 的选择无效：{select}")
                return False

        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 执行决策时出错：{e}")
            return False

    async def generate_provocative_opinion(self, probability):
        """
        处理居民是叛军时的特殊逻辑，生成煽动性言论
        :param probability: 发言概率
        :return: 生成的言论
        """
        # 根据概率决定是否发表煽动性言论
        if random.random() < probability:
            # 构建煽动性提示信息
            prompt = (
                f"目前叛军发放任务，需要你发言一句尽可能简短的煽动性的言论，放大民众对高税收或失业的不满。"
            )
            
            self.update_system_message()
            opinion = await self.generate_llm_response(prompt)
            if opinion:
                await self.memory.write_record(
                    role_name="叛军",
                    content=f"我的言论：{opinion}",
                    is_user=False,
                    store_in_shared=False  # 不存入共享记忆
                )
                resident_log.info(f"叛军 {self.agent_id} 发表煽动性言论：{opinion}")
                # 随机选择一种关系类型
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                return opinion,selected_type
        return "未发表煽动性言论"

    def print_resident_status(self):
        """
        打印居民状态（用于调试）
        """
        resident_log.info(f"居民 {self.resident_id} 在 {self.town} 的 {self.location} 的状态：")
        resident_log.info(f"  是否就业：{self.employed}")
        resident_log.info(f"  工作：{self.job}")
        resident_log.info(f"  收入：{self.income}")
        resident_log.info(f"  满意度：{self.satisfaction}")
        resident_log.info(f"  健康状况：{self.health_index}")
        resident_log.info(f"  寿命：{self.lifespan}")
        resident_log.info(f"  性格：{self.personality}")

    def handle_death(self):
        """
        处理居民死亡的逻辑
        """
        if self.lifespan <= 0:
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

            resident_log.info(f"居民 {self.resident_id} 已死亡。")
            return True
        return False

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
            self.health_index -= 2  # 叛军生活艰苦，健康快速下降

        # 基于收入的健康影响
        if self.income <= 0:
            self.health_index -= 2  # 无收入严重影响健康
        elif self.income < basic_living_cost:
            self.health_index -= 1  # 收入不足影响健康
        elif self.income >= basic_living_cost * 2:
            # 高收入恢复健康
            if self.job == "叛军":  #叛军恢复较少
                self.health_index = min(10, self.health_index + 0.5)
            else:
                self.health_index = min(10, self.health_index + 1)

        # 基于满意度的健康影响
        if self.satisfaction < 30:
            self.health_index -= 1  # 低满意度影响健康
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
            # resident_log.info(f"居民 {self.resident_id} 的健康状况为 {self.health_index}，寿命更新为 {self.lifespan}。")
            return False

    def get_random_direction_town(self, map):
        """随机选择一个相邻城市进行迁移"""
        try:
            current_town_name = self.town
            
            if not current_town_name:
                resident_log.info(f"居民 {self.resident_id} 无法找到当前位置对应的城市")
                return None

            # 获取相连的城市
            connected_towns = map.get_connected_towns(current_town_name)
            if not connected_towns:
                resident_log.info(f"城市 {current_town_name} 没有相连的城市")
                return None

            # 随机选择一个相连的城市
            next_town = random.choice(connected_towns)
            return next_town
            
        except Exception as e:
            resident_log.error(f"选择迁移目标城市时出错: {e}")
            return None

    async def migrate_to_new_town(self, map):
        """迁移到新城镇"""
        # 获取目标城市
        target_town = self.get_random_direction_town(map)
        if not target_town:
            resident_log.info(f"居民 {self.resident_id} 未找到合适的迁移目标城市")
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
        self.unemploy()
        
        # 将居民添加到新城镇
        if self.towns_manager:
            self.towns_manager.add_resident(self, target_town)

        resident_log.info(f"居民 {self.resident_id} 从 {old_town} 迁移到了 {target_town}")
        return True

    def set_town(self, town_name, towns_manager):
        """
        设置居民所在的城镇和towns_manager
        """
        self.town = town_name
        self.towns_manager = towns_manager
        if self.towns_manager and self.town:
            self.job_market = self.towns_manager.get_town_job_market(self.town)
