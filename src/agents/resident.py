from .shared_imports import *
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
        super().__init__(agent_id=f"group_{town_name}", group_type='resident_group', window_size=5)
        self.town_name = town_name
        self.residents = {}  # resident_id -> Resident
        # 共享的 LLM 资源
        # self.model_manager = ModelManager()
        # self.model_config = self.model_manager.get_random_model_config()
        # self.model_type = ModelType(self.model_config["model_type"])
        # self.model_backend = ModelFactory.create(
        #     model_platform=self.model_config["model_platform"],
        #     model_type=self.model_type,
        #     model_config_dict=ChatGPTConfig(temperature=0.7).as_dict(),
        # )
        # # 共享的 token 计数器和上下文创建器
        # self.token_counter = OpenAITokenCounter(self.model_type)
        # self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)

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

    def remove_resident(self, resident_id):
        """从群组中移除居民"""
        if resident_id in self.residents:
            del self.residents[resident_id]

class Resident(BaseAgent):
    def __init__(self, resident_id, job_market, shared_pool, map):
        """初始化居民"""
        self.resident_id = resident_id
        self.job_market = job_market
        self.shared_pool = shared_pool
        self.map = map
        self.location = None
        self.town = None  # 添加城镇属性
        self.employed = False  # 是否就业
        self.job = None  # 当前工作
        self.income = 0  # 收入
        self.satisfaction = 100  # 对政府的满意度（0到100）
        self.health_index = 10  # 居民的健康状况（0到10）
        self.lifespan = 100  # 居民的寿命
        self.towns_manager = None  # 添加Towns实例的引用

        # 由 ResidentGroup 设置agent属性
        self.model_backend = None
        self.token_counter = None
        self.context_creator = None
        self.memory = None

    def employ(self, job):
        """
        居民就业
        :param job: 工作名称
        """
        self.employed = True
        self.job = job
        self.income = 10  # 假设每份工作的收入为10
        self.satisfaction += 10  # 就业增加满意度
        resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 找到了工作：{job}。")
    
    def unemploy(self):
        """
        居民失业
        """
        self.employed = False
        self.job = None
        self.income = 0
        self.satisfaction -= 20  # 失业降低满意度
        resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 失业了。")

    async def receive_information(self, message_content):
        """
        接收信息（如政府政策、叛乱信息）
        """
        # TODO: 确认基于同质图和异质图的信息传递细节是否达到预期，邻居agent信息影响目标agent的决策（观念+市场中的就业信息）
        # print("触发receive_information--------------------------------")
        self.satisfaction += 5  # 接收信息增加满意度
        resident_log.info(f"居民 {self.resident_id} 收到了信息：{message_content}。")

        if random.random() < 0.8:
            system_message = "你是一个清代中国大运河沿线地区的居民。请根据你了解的信息做出回应。回应要简短，不超过20个字。"
            response_content = await self.generate_llm_response(message_content)
            
            if response_content:
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)

                # 使用 asyncio.create_task 来避免阻塞
                await asyncio.create_task(
                    self.spread_speech_in_network(response_content, selected_type)
                )
                resident_log.info(f"居民 {self.resident_id} 对收到的信息做出回应：{response_content}")

    async def process_information(self):
        """
        处理接收到的信息并生成响应
        """
        prompt = "请根据收到的信息做出回应。"
        response = await self.generate_llm_response(prompt)
        if response:
            resident_log.info(f"居民 {self.resident_id} 的回应：{response}")
            return response
        return None

    async def decide_action_by_llm(self, tax_rate, basic_living_cost):
        """
        通过LLM决定居民的行动，并随机生成对政府的态度发言。同时更新满意度。
        """
        # 随机决定是否需要发言（20%的概率）
        need_speech = random.random() < 0.2
        
        # 获取当前居民状态的提示信息
        status_prompt = self.get_status_prompt()

        # 获取社会状态信息
        social_status = (
            f"税率: {tax_rate*100:.1f}%\n"
            f"基本生活所需值: {basic_living_cost}\n"
        )

        # 如果是未就业居民，获取当前城镇的空缺岗位信息
        job_market_info = ""
        if not self.employed and self.town and self.job_market:
            vacant_jobs = self.job_market.get_vacant_jobs()
            if vacant_jobs:
                job_market_info = "以下是当前可用工作岗位：\n" + "\n".join(
                    f"- {job}: {count}个空缺" for job, count in vacant_jobs.items()
                )
            else:
                job_market_info = "当前没有可用的工作岗位。\n"

        # 基础提示信息
        base_prompt = (
            f"请根据当前状态决定下一步行动。"
            f"以下是你的当前状态：{status_prompt}\n"
            f"以下是目前的社会环境：{social_status}\n"
            f"{job_market_info}"
            f"你可以选择以下行动之一：\n"
            f"1. 参加叛乱\n"
            f"2. {'寻找工作' if not self.employed else '继续目前的工作'}\n"
            f"3. 迁徙到其他位置\n"
            f"请分析当前状况，并返回：\n"
            f"1. 你的选择（1-3）\n"
            f"2. 选择原因\n"
            f"3. 满意度变化值（-20到20之间的数字），需要考虑：\n"
            f"   - 当前收入与基本生活所需的比值\n"
            f"   - 就业情况\n"
            f"   - 社会环境（税率等）\n"
            f"   - 个人健康状况\n"
        )

        prompt = base_prompt + (
            f"4. 一段对政府的态度发言\n"
            f"注意：必须返回单行的JSON字符串，格式如下：\n"
            f'{{"select": 你的选择, "reason": 选择原因, "satisfaction_change": 满意度变化值, "speech": 你的发言}}'
            if need_speech else
            f"注意：必须返回单行的JSON字符串，格式如下：\n"
            f'{{"select": 你的选择, "reason": 选择原因, "satisfaction_change": 满意度变化值}}'
        )

        try:
            response = await self.generate_llm_response(prompt)
            if not response:
                return "2", "发生错误，继续当前工作"

            decision_data = json.loads(response)
            select = decision_data.get("select")
            reason = decision_data.get("reason")
            speech = decision_data.get("speech", "")
            satisfaction_change = decision_data.get("satisfaction_change")

            if satisfaction_change is not None:
                # 确保满意度在0-100范围内
                self.satisfaction = max(0, min(100, self.satisfaction + satisfaction_change))

            resident_log.info(f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}, 更新满意度：{self.satisfaction}")

            # 执行决策
            await self.execute_decision(select)

            # 如果有发言，在社交网络中传播
            if speech:
                print(f"居民 {self.resident_id} 发言：{speech}")
                relation_types = ["friend", "colleague", "family", "hometown"]
                # 随机选择一种关系类型
                selected_type = random.choice(relation_types)
                # 在社交网络中传播信息
                await self.spread_speech_in_network(speech, selected_type)

            return select, reason

        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 决策出错：{e}")
            return "2", "发生错误，继续当前工作"  # 默认选择继续工作

    async def execute_decision(self, select):
        """
        执行居民的决策
        """
        try:
            if select == 1:
                resident_log.info(f"居民 {self.resident_id} 决定参加叛乱")
                self.job_market.assign_specific_job(self, "叛军")
                return True
            
            elif select == 2:
                if not self.employed and self.town and self.job_market:
                    # 80%的概率能够成功就业
                    if random.random() < 0.8 :
                        self.job_market.assign_job(self)
                        return True
                    resident_log.info(f"居民 {self.resident_id} 求职失败")
                    return False
                resident_log.info(f"居民 {self.resident_id} 继续当前工作：{self.job}")
                return True
            
            elif select == 3:
                # 迁移到新城镇
                success = await self.migrate_to_new_town(self.map)
                if not success:
                    resident_log.info(f"居民 {self.resident_id} 迁移失败，保持原位置")
                return success
            
            else:
                resident_log.error(f"居民 {self.resident_id} 的选择无效：{select}")
                return False

        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 执行决策时出错：{e}")
            return False

    async def spread_speech_in_network(self, speech: str, relation_type: str):
        """
        在社交网络中传播发言
        """
        try:
            if hasattr(self, 'social_network'):
                if relation_type in ["friend", "colleague"]:
                    # 在异质图中传播
                    neighbors = self.social_network.hetero_graph.get_neighbors(self.resident_id)
                    for neighbor_id in neighbors:
                        if self.social_network.hetero_graph.graph[self.resident_id][neighbor_id]["type"] == relation_type:
                            resident_log.info(f"居民 {self.resident_id} 向邻居 {neighbor_id} 传播信息：{speech}")
                            # 获取邻居居民对象并调用其receive_information方法
                            neighbor = self.social_network.residents.get(neighbor_id)
                            if neighbor:
                                await neighbor.receive_information(speech)

                elif relation_type in ["family", "hometown"]:
                    # 在超图中传播
                    groups = [edge_id for edge_id in self.social_network.hyper_graph.get_node_hyperedges(self.resident_id)
                            if edge_id.startswith(relation_type)]
                    if groups:
                        selected_group = random.choice(groups)
                        resident_log.info(f"居民 {self.resident_id} 在群组 {selected_group} 中传播信息：{speech}")
                        members = self.social_network.hyper_graph.get_hyperedge_nodes(selected_group)
                        for member_id in members:
                            if member_id != self.resident_id:
                                # 获取群组成员对象并调用其receive_information方法
                                member = self.social_network.residents.get(member_id)
                                if member:
                                    await member.receive_information(speech)

        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 传播信息时出错：{e}")

    def get_status_prompt(self):
        """
        生成当前居民状态的提示信息。
        :return: 居民状态的字符串描述
        """
        status_prompt = (
            f"居民 ID: {self.resident_id}\n"
            f"位置: {self.location}\n"
            f"是否就业: {self.employed}\n"
            f"工作: {self.job}\n"
            f"收入: {self.income}\n"
            f"满意度: {self.satisfaction}\n"
            f"健康状况: {self.health_index}\n"
            f"寿命: {self.lifespan}"
        )
        return status_prompt

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

    def handle_death(self):
        """
        处理居民死亡的逻辑
        """
        if self.lifespan <= 0:
            # 从就业市场中移除
            if self.employed and self.job and self.town:
                # 获取城镇的就业市场
                if self.towns_manager and self.town in self.towns_manager.towns:
                    town_job_market = self.towns_manager.get_town_job_market(self.town)
                    if town_job_market:
                        town_job_market.remove_resident(self.resident_id, self.job)
                self.employed = False
                self.job = None
            
            # 从城镇居民列表中移除
            if self.town and self.towns_manager:
                town_data = self.towns_manager.towns[self.town]
                if self.resident_id in town_data['residents']:
                    del town_data['residents'][self.resident_id]
                if town_data['resident_group']:
                    town_data['resident_group'].remove_resident(self.resident_id)

            # 从社交网络中移除（如果存在）
            if hasattr(self, 'social_network'):
                # 从异质图中移除
                if hasattr(self.social_network, 'hetero_graph'):
                    self.social_network.hetero_graph.remove_node(self.resident_id)
                # 从超图中移除
                if hasattr(self.social_network, 'hyper_graph'):
                    self.social_network.hyper_graph.remove_node(self.resident_id)

            resident_log.info(f"居民 {self.resident_id} 已死亡。")
            return True
        return False

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
        new_location, new_town_name = map.generate_random_location(target_town)

        # 更新居民信息
        old_town = self.town
        self.location = new_location
        self.town = new_town_name

        resident_log.info(f"居民 {self.resident_id} 从 {old_town} 迁移到了 {new_town_name}")
        return True

    def set_town(self, town_name, towns_manager):
        """
        设置居民所在的城镇和towns_manager
        """
        self.town = town_name
        self.towns_manager = towns_manager
        if self.towns_manager and self.town:
            self.job_market = self.towns_manager.get_town_job_market(self.town)
