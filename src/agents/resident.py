from camel.configs import ChatGPTConfig
from camel.memories import ChatHistoryMemory, MemoryRecord, ScoreBasedContextCreator
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter
from datetime import datetime
import sys
import logging
import json

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

class Resident:
    def __init__(self, resident_id, location, job_market, model_type="gpt-3.5-turbo"):
        """
        初始化居民类
        :param resident_id: 居民的唯一标识符
        :param location: 居民的初始位置 (x, y)
        :param job_market: 就业市场对象，用于获取工作机会
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.resident_id = resident_id
        self.location = location
        self.job_market = job_market
        self.employed = False  # 是否就业
        self.job = None  # 当前工作
        self.income = 0  # 收入
        self.satisfaction = 100  # 对政府的满意度（0到100）
        self.rebellion_risk = 0  # 参与叛乱的风险（0到100）
        self.health_index = 10  # 居民的健康状况（0到10）
        self.lifespan = 100  # 居民的寿命

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

        # # 初始化日志
        # self.logger = logging.getLogger(name=f"resident_{resident_id}")
        # self.logger.setLevel(logging.DEBUG)
        # handler = logging.StreamHandler()
        # handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        # self.logger.addHandler(handler)

    def employ(self, job):
        """
        居民就业
        :param job: 工作名称
        """
        self.employed = True
        self.job = job
        self.income = 10  # 假设每份工作的收入为10
        self.satisfaction += 10  # 就业增加满意度
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 找到了工作：{job}。")

    def unemploy(self):
        """
        居民失业
        """
        self.employed = False
        self.job = None
        self.income = 0
        self.satisfaction -= 20  # 失业降低满意度
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 失业了。")

    def migrate(self, new_location):
        """
        居民迁徙
        :param new_location: 新位置的坐标 (x, y)
        """
        self.location = new_location
        resident_log.info(f"居民 {self.resident_id} 迁徙到了 {new_location}。")

    def evaluate_rebellion_risk(self):
        """
        评估参与叛乱的风险
        """
        if not self.employed:
            self.rebellion_risk += 30  # 失业增加叛乱风险
        if self.income < 50:
            self.rebellion_risk += 20  # 低收入增加叛乱风险
        if self.satisfaction < 50:
            self.rebellion_risk += 50  # 低满意度增加叛乱风险
        resident_log.info(f"居民 {self.resident_id} 的叛乱风险更新为 {self.rebellion_risk}。")

    def decide_rebellion(self):
        """
        决定是否参与叛乱
        :return: 是否参与叛乱（布尔值）
        """
        self.evaluate_rebellion_risk()
        if self.rebellion_risk > 70:  # 叛乱风险超过70时参与叛乱
            resident_log.warning(f"居民 {self.resident_id} 在 {self.location} 决定参与叛乱。")
            return True
        return False

    def receive_information(self, message_content):
        """
        接收信息（如政府政策、叛乱信息）
        :param message_content: 信息内容
        """
        self.satisfaction += 5  # 接收信息增加满意度
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 收到了信息：{message_content}。")

        # 使用 CAMEL 框架处理信息
        user_message = BaseMessage.make_user_message(
            role_name="政府",
            content=message_content,
        )
        self.memory.write_record(
            MemoryRecord(
                message=user_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )

    async def process_information(self):
        """
        处理接收到的信息并生成响应
        """
        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一个清代中国大运河附近的居民。请根据收到的信息做出回应。",
            }]

        response = await self.model_backend.run(openai_messages)
        resident_log.info(f"居民 {self.resident_id} 的回应：{response.choices[0].message.content}")

        # 将响应记录到记忆中
        assistant_message = BaseMessage.make_assistant_message(
            role_name="居民",
            content=response.choices[0].message.content,
        )
        self.memory.write_record(
            MemoryRecord(
                message=assistant_message,
                role_at_backend=OpenAIBackendRole.ASSISTANT,
            )
        )

    async def decide_action_by_llm(self):
        """
        通过LLM决定居民的行动（参加叛乱、继续工作、迁徙等）。
        """
        # 获取当前居民状态的提示信息
        status_prompt = self.get_status_prompt()
        user_msg = BaseMessage.make_user_message(
            role_name="居民",  # 居民角色
            content=(
                f"请根据当前状态决定下一步行动。"
                f"以下是你的当前状态：{status_prompt}\n"
                f"你可以选择以下行动之一：\n"
                f"1. 参加叛乱\n"
                f"2. 继续目前的工作\n"
                f"3. 迁徙到其他位置\n"
                f"请返回选择的数字（1、2 或 3），并解释原因，输出格式为 JSON，例如：\n"
                f'{{"select": "1", "reason": "叛乱风险已达210，环境极其危险。农民收入微薄（10），高风险工作不明智。健康极差（1），寿命仅剩22年，生存优先。迁徙是最紧急合理的选择，可逃离危险，改善生活与健康。"}}'
            ),
        )
        # 将用户消息写入记忆系统
        self.memory.write_record(
            MemoryRecord(
                message=user_msg,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        # 获取当前的上下文
        openai_messages, _ = self.memory.get_context()
        # 如果上下文为空，加入系统消息
        if not openai_messages:
            openai_messages = [{
                "role": "system",
                "content": "你是一个模拟中的居民。请根据当前状态决定下一步行动。",
            }] + [user_msg.to_openai_user_message()]

        resident_log.info(f"居民 {self.resident_id} 正在决定行动，提示信息：{openai_messages}")

        # 调用模型进行推理
        try:
            response = self.model_backend.run(openai_messages)  # 运行模型
            content = response.choices[0].message.content  # 获取响应内容
            
            decision_data = json.loads(content)  # 将 JSON 字符串解析为字典
            select = decision_data.get("select")
            reason = decision_data.get("reason")
            resident_log.info(f"居民 {self.resident_id} 的思考：{reason},选择：{select}")

            # 解析响应内容并执行相应的行动
            if select =="1":
                resident_log.warning(f"居民 {self.resident_id} 决定参加叛乱。")
                self.decide_rebellion()
            elif select =="2":
                resident_log.info(f"居民 {self.resident_id} 决定继续目前的工作。")
                # 继续工作，无需额外操作
            elif select =="3":
                # 假设迁徙到随机位置
                new_location = (self.location[0] + 1, self.location[1] + 1)  # 示例：简单的位置更新
                self.migrate(new_location)
            else:
                resident_log.info(f"居民 {self.resident_id} 未做出明确行动决定。")

            # 将响应记录到记忆中
            assistant_message = BaseMessage.make_assistant_message(
                role_name="居民",
                content=content,
            )
            self.memory.write_record(
                MemoryRecord(
                    message=assistant_message,
                    role_at_backend=OpenAIBackendRole.ASSISTANT,
                )
            )

        except Exception as e:
            resident_log.error(f"居民 {self.resident_id} 在决定行动时出错：{e}")
            content = "无法决定行动。"

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
            f"叛乱风险: {self.rebellion_risk}\n"
            f"健康状况: {self.health_index}\n"
            f"寿命: {self.lifespan}"
        )
        return status_prompt
    
    def print_resident_status(self):
        """
        打印居民状态（用于调试）
        """
        resident_log.info(f"居民 {self.resident_id} 在 {self.location} 的状态：")
        resident_log.info(f"  是否就业：{self.employed}")
        resident_log.info(f"  工作：{self.job}")
        resident_log.info(f"  收入：{self.income}")
        resident_log.info(f"  满意度：{self.satisfaction}")
        resident_log.info(f"  叛乱风险：{self.rebellion_risk}")
        resident_log.info(f"  健康状况：{self.health_index}")
        resident_log.info(f"  寿命：{self.lifespan}")

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
            resident_log.info(f"居民 {self.resident_id} 的健康状况为 {self.health_index}，寿命更新为 {self.lifespan}，该居民已死亡。")
            return False
        else:
            resident_log.info(f"居民 {self.resident_id} 的健康状况为 {self.health_index}，寿命更新为 {self.lifespan}。")

