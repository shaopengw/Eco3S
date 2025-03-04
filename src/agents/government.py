from camel.configs import ChatGPTConfig
from camel.memories import ChatHistoryMemory, MemoryRecord, ScoreBasedContextCreator
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter
import logging

class OrdinaryGovernmentAgent:
    def __init__(self, agent_id, government, model_type="gpt-3.5-turbo"):
        """
        初始化普通政府官员类
        :param agent_id: 政府官员的唯一标识符
        :param government: 政府对象，用于获取政府状态
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.agent_id = agent_id
        self.government = government
        self.opinions = []  # 收集意见
        self.time = 0  # 当前时间（年）

        # 初始化官员属性
        self.age = None  # 年龄
        self.political_style = None  # 政治风格
        self.preferences_and_views = None  # 偏好与观点
        self.background = None  # 背景
        self.persona = None  # 人物性格

        # 初始化 CAMEL 框架组件
        self.model_type = ModelType(model_type)
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = ChatHistoryMemory(self.context_creator, window_size=5)

        # 初始化日志
        self.logger = logging.getLogger(name=f"ordinary_government_agent_{agent_id}")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.logger.addHandler(handler)

    def set_attributes(self, age, political_style, preferences_and_views, background, persona):
        """
        设置官员的属性
        :param age: 年龄
        :param political_style: 政治风格
        :param preferences_and_views: 偏好与观点
        :param background: 背景
        :param persona: 人物性格
        """
        self.age = age
        self.political_style = political_style
        self.preferences_and_views = preferences_and_views
        self.background = background
        self.persona = persona

    def generate_opinion(self):
        """
        利用 AI 生成一句关于政治决策的意见
        :return: 生成的意见内容
        """
        # 获取当前政府状态
        government_status = (
            f"当前政府状态：\n"
            f"预算: {self.government.get_budget()}\n"
            f"军事力量: {self.government.get_military_strength()}\n"
            f"运河维护政策支持: {self.government.policy_support_canal}\n"
        )

        # 构建提示信息
        prompt = (
            f"你是一位普通政府官员，以下是你的个人属性：\n"
            f"年龄: {self.age}\n"
            f"政治风格: {self.political_style}\n"
            f"偏好与观点: {self.preferences_and_views}\n"
            f"{government_status}\n"
            f"请根据你的个人属性和当前政府状态，提出一句关于大运河运营的政治决策的意见。"
        )
        # prompt = (
        #     f"你是一位普通政府官员，以下是你的个人属性：\n"
        #     f"年龄: {self.age}\n"
        #     f"政治风格: {self.political_style}\n"
        #     f"偏好与观点: {self.preferences_and_views}\n"
        #     f"背景: {self.background}\n"
        #     f"人物性格: {self.persona}\n"
        #     f"{government_status}\n"
        #     f"请根据你的个人属性和当前政府状态，提出一句关于政治决策的意见。"
        # )
        # 使用 CAMEL 框架生成意见
        user_message = BaseMessage.make_user_message(
            role_name="普通政府官员",
            content=prompt,
        )
        self.memory.write_record(
            MemoryRecord(
                message=user_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )

        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一位普通政府官员，负责根据个人属性和政府状态提出意见。"
            }] + [user_message.to_openai_user_message()]

        self.logger.info(f"普通政府官员 {self.agent_id} 正在生成意见，提示信息：{openai_messages}")

        try:
            # 调用模型生成意见
            response = self.model_backend.run(openai_messages)
            opinion = response.choices[0].message.content
            self.logger.info(f"普通政府官员 {self.agent_id} 生成的意见：{opinion}")
            return opinion
        except Exception as e:
            self.logger.error(f"普通政府官员 {self.agent_id} 在生成意见时出错：{e}")
            return "无法生成意见"

    def express_opinion(self, message_content):
        """
        表达意见
        :param message_content: 意见内容
        """
        self.opinions.append(message_content)
        self.logger.info(f"普通政府官员 {self.agent_id} 表达了意见：{message_content}")

        # 使用 CAMEL 框架处理信息
        user_message = BaseMessage.make_user_message(
            role_name="普通政府官员",
            content=message_content,
        )
        self.memory.write_record(
            MemoryRecord(
                message=user_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )

    def get_opinions(self):
        """
        获取当前官员的所有意见
        :return: 官员的意见列表
        """
        return self.opinions

    async def discuss_with_other_officials(self, other_agents):
        """
        与其他普通政府官员讨论
        :param other_agents: 其他政府官员列表
        """
        opinions = []
        for agent in other_agents:
            opinions += agent.get_opinions()
        
        # 讨论意见并生成报告
        discussion_report = "\n".join(opinions)
        user_msg = BaseMessage.make_user_message(
            role_name="普通政府官员",
            content=f"我们讨论了以下意见：\n{discussion_report}\n请提出您的看法。",
        )

        # 将讨论内容写入记忆系统
        self.memory.write_record(
            MemoryRecord(
                message=user_msg,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        
        # 更新并返回讨论报告
        return discussion_report
    
class HighRankingGovernmentAgent:
    def __init__(self, agent_id, government, model_type="gpt-3.5-turbo"):
        """
        初始化高级政府官员类（决策者）
        :param agent_id: 政府官员的唯一标识符
        :param government: 政府对象，用于获取政府状态
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.agent_id = agent_id
        self.government = government
        self.time = 0  # 当前时间（年）
        
        # 初始化官员属性
        self.age = None  # 年龄
        self.political_style = None  # 政治风格
        self.preferences_and_views = None  # 偏好与观点
        self.background = None  # 背景
        self.persona = None  # 人物性格

        # 初始化 CAMEL 框架组件
        self.model_type = ModelType(model_type)
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = ChatHistoryMemory(self.context_creator, window_size=5)

        # 初始化日志
        self.logger = logging.getLogger(name=f"high_ranking_government_agent_{agent_id}")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.logger.addHandler(handler)

    def set_attributes(self, age, political_style, preferences_and_views, background, persona):
        """
        设置官员的属性
        :param age: 年龄
        :param political_style: 政治风格
        :param preferences_and_views: 偏好与观点
        :param background: 背景
        :param persona: 人物性格
        """
        self.age = age
        self.political_style = political_style
        self.preferences_and_views = preferences_and_views
        self.background = background
        self.persona = persona

    def make_decision(self, discussion_report):
        """
        根据普通政府官员的讨论作出决策
        :param discussion_report: 普通政府官员的讨论报告
        :return: 决策结果
        """
        # 使用 CAMEL 框架来做决策
        decision_message = BaseMessage.make_user_message(
            role_name="高级政府官员",
            content=(f"普通政府官员们的讨论报告：\n{discussion_report}\n"
                     f"当前政府状态：\n"
                     f"预算: {self.government.get_budget()}\n"
                     f"军事力量: {self.government.get_military_strength()}\n"
                     f"运河维护政策支持: {self.government.policy_support_canal}\n"
                     f"请根据这些意见和状态作出最终决策。")
        )
        
        # 将讨论内容写入记忆系统
        self.memory.write_record(
            MemoryRecord(
                message=decision_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        
        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一个高级政府官员，负责根据下属官员的讨论和当前政府状态做出最终决策。"
            }] + [decision_message.to_openai_user_message()]

        self.logger.info(f"高级政府官员 {self.agent_id} 正在处理决策，提示信息：{openai_messages}")
        
        try:
            # 调用模型做出最终决策
            response = self.model_backend.run(openai_messages)
            decision = response.choices[0].message.content
            self.logger.info(f"高级政府官员 {self.agent_id} 的决策：{decision}")
            return decision
        except Exception as e:
            self.logger.error(f"高级政府官员 {self.agent_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def print_agent_status(self):
        """
        打印高级政府官员的状态
        """
        self.logger.info(f"高级政府官员 {self.agent_id} 的状态：")
        self.logger.info(f"  当前时间：{self.time}年")
        self.logger.info(f"  年龄：{self.age}")
        self.logger.info(f"  政治风格：{self.political_style}")
        self.logger.info(f"  偏好与观点：{self.preferences_and_views}")
        self.logger.info(f"  背景：{self.background}")
        self.logger.info(f"  人物性格：{self.persona}")

class Government:
    def __init__(self, map, job_market, initial_budget, time):
        """
        初始化政府类
        :param map: 地图对象，用于获取地理信息
        :param job_market: 就业市场对象，用于提供就业机会
        :param initial_budget: 初始预算
        """
        self.map = map
        self.job_market = job_market
        self.budget = initial_budget
        self.military_strength = 100  # 初始军事力量
        self.policy_support_canal = True  # 是否支持运河维护
        self.time = time

    def provide_jobs(self):
        """
        提供就业机会
        """
        if self.budget >= 1000:
            self.job_market.add_job("Canal Maintenance")
            self.budget -= 1000
            print("政府提供运河维护工作。")
        else:
            print("政府预算不足以提供工作。")

    def maintain_canal(self):
        """
        维护运河
        """
        if self.policy_support_canal and self.budget >= 500:
            self.map.update_river_condition(year=self.time.get_current_year())
            self.budget -= 500
            print("政府维护运河。")
        else:
            print("政府因政策或预算限制未维护运河。")

    def suppress_rebellion(self, rebellion_strength):
        """
        镇压叛乱
        :param rebellion_strength: 叛乱的强度
        :return: 是否成功镇压叛乱（布尔值）
        """
        if self.military_strength >= rebellion_strength:
            self.military_strength -= rebellion_strength * 0.1  # 军事力量消耗
            print(f"政府成功压制了强度为 {rebellion_strength} 的叛乱。")
            return True
        else:
            print(f"政府未能压制强度为 {rebellion_strength} 的叛乱。")
            return False

    def provide_public_services(self):
        """
        提供公共服务（如粮食救济）
        """
        if self.budget >= 300:
            self.budget -= 300
            print("政府提供公共服务（如粮食救济）。")
        else:
            print("政府预算不足以提供公共服务。")

    def set_policy_support_canal(self, support):
        """
        设置是否支持运河维护的政策
        :param support: 是否支持运河维护（布尔值）
        """
        self.policy_support_canal = support
        print(f"政府关于运河维护政策的支持已设置为 {support}。")

    def get_budget(self):
        """
        获取当前预算
        :return: 当前预算
        """
        return self.budget

    def get_military_strength(self):
        """
        获取当前军事力量
        :return: 当前军事力量
        """
        return self.military_strength

    def print_government_status(self):
        """
        打印政府状态（用于调试）
        """
        print(f"政府预算: {self.budget}")
        print(f"军事力量: {self.military_strength}")
        print(f"运河维护政策支持: {self.policy_support_canal}")