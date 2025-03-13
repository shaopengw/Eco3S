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
import asyncio

if "sphinx" not in sys.modules:
    rebellion_log = logging.getLogger(name="rebels.agent")
    rebellion_log.setLevel("DEBUG")
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_handler = logging.FileHandler(f"./log/rebels.agent-{str(now)}.log")
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
    rebellion_log.addHandler(file_handler)

class OrdinaryRebel:
    def __init__(self, rebel_id, rebellion, model_type="gpt-3.5-turbo"):
        """
        初始化普通叛军类
        :param rebel_id: 叛军的唯一标识符
        :param rebellion: 叛军对象，用于获取叛军状态
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.rebel_id = rebel_id
        self.rebellion = rebellion
        self.opinions = []  # 收集意见
        self.time = 0  # 当前时间（年）

        # 初始化叛军属性
        self.role = None  # 角色
        self.mbti = None  # 人物性格

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
        self.memory = ChatHistoryMemory(self.context_creator, window_size=3)
        # 系统消息
        self.system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content="你是一位普通叛军，负责根据个人属性和叛军状态提出意见。"
        )

    def set_attributes(self, role, mbti):
        """
        设置叛军的属性
        :param role: 角色
        :param mbti: 人物性格
        """
        self.role = role
        self.mbti = mbti

    async def generate_opinion(self):
        """
        利用 AI 生成一句关于叛军行动的意见
        :return: 生成的意见内容
        """
        # 获取当前叛军状态
        rebellion_status = (
            f"当前叛军状态：\n"
            f"力量: {self.rebellion.get_strength()}\n"
            f"资源: {self.rebellion.get_resources()}\n"
            f"支持度: {self.rebellion.get_support()}\n"
        )

        # 构建提示信息
        prompt = (
            f"你是一位普通叛军，以下是你的个人属性：\n"
            f"角色: {self.role}\n"
            f"人物性格: {self.mbti}\n"
            f"{rebellion_status}\n"
            f"请根据你的个人属性和当前叛军状态，提出一句关于叛军行动的意见。"
        )

        # 使用 CAMEL 框架生成意见
        user_message = BaseMessage.make_user_message(
            role_name="普通叛军",
            content=prompt,
        )
        self.memory.write_record(
            MemoryRecord(
                message=user_message,
                role_at_backend=OpenAIBackendRole.USER,
            )
        )
        
        # 获取历史信息
        openai_messages, _ = self.memory.get_context()
        if not openai_messages:
            openai_messages = [{
                "role": self.system_message.role_name,
                "content": self.system_message.content,
            }] + [user_message.to_openai_user_message()]

        rebellion_log.info(f"普通叛军 {self.rebel_id} 正在生成意见，提示信息：{openai_messages}")

        try:
            # 调用模型生成意见
            # response = self.model_backend.run(openai_messages)
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)  # 异步运行模型
            opinion = response.choices[0].message.content
            rebellion_log.info(f"普通叛军 {self.rebel_id} 生成的意见：{opinion}")
            return opinion
        except Exception as e:
            rebellion_log.error(f"普通叛军 {self.rebel_id} 在生成意见时出错：{e}")
            return "无法生成意见"

    def express_opinion(self, message_content):
        """
        表达意见
        :param message_content: 意见内容
        """
        self.opinions.append(message_content)

        # 使用 CAMEL 框架处理信息
        user_message = BaseMessage.make_user_message(
            role_name="普通叛军",
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
        获取当前叛军的所有意见
        :return: 叛军的意见列表
        """
        return self.opinions

    def discuss_with_other_rebels(self, other_rebels):
        """
        与其他普通叛军讨论
        :param other_rebels: 其他叛军列表
        """
        opinions = []
        for rebel in other_rebels:
            opinions += rebel.get_opinions()
        
        # 讨论意见并生成报告
        discussion_report = "\n".join(opinions)
        user_msg = BaseMessage.make_user_message(
            role_name="普通叛军",
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
    
class RebelLeader:
    def __init__(self, leader_id, rebellion, model_type="gpt-3.5-turbo"):
        """
        初始化叛军头子类（决策者）
        :param leader_id: 叛军头子的唯一标识符
        :param rebellion: 叛军对象，用于获取叛军状态
        :param model_type: 使用的模型类型（默认使用 GPT-3.5-turbo）
        """
        self.leader_id = leader_id
        self.rebellion = rebellion
        self.time = 0  # 当前时间（年）
        
        # 初始化叛军头子属性
        self.role = None  # 角色
        self.mbti = None  # 人物性格

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

    def set_attributes(self, role, mbti):
        """
        设置叛军头子的属性
        :param role: 角色
        :param mbti: 人物性格
        """
        self.role = role
        self.mbti = mbti

    def make_decision(self, discussion_report):
        """
        根据普通叛军的讨论作出决策
        :param discussion_report: 普通叛军的讨论报告
        :return: 决策结果
        """
        # 使用 CAMEL 框架来做决策
        decision_message = BaseMessage.make_user_message(
            role_name="叛军头子",
            content=(
                f"你是一个叛军头子，负责根据下属叛军的讨论和当前叛军状态做出最终决策。\n"
                f"请从以下动作中选择一个，并提供一个参数：\n"
                f"- 袭击政府设施: 参数为 `力量投入`（整数）\n"
                f"- 招募新成员: 参数为 `资源投入`（整数）\n"
                f"- 争取民众支持: 参数为 `资源投入`（整数）\n"
                f"- 撤退: 参数为 `无`\n"
                f"\n"
                f"当前叛军状态：\n"
                f"力量: {self.rebellion.get_strength()}\n"
                f"资源: {self.rebellion.get_resources()}\n"
                f"支持度: {self.rebellion.get_support()}\n"
                f"\n"
                f"普通叛军们的讨论报告：\n{discussion_report}\n"
                f"\n"
                f"请根据以上信息和状态作出最终决策，输出格式为 JSON，例如：\n"
                f'{{"action": "袭击政府设施", "params": 1000}}'
            )
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
                "content": "你是一个叛军头子，负责根据下属叛军的讨论和当前叛军状态做出最终决策。"
            }] + [decision_message.to_openai_user_message()]

        rebellion_log.info(f"叛军头子 {self.leader_id} 正在处理决策，提示信息：{openai_messages}")
        
        try:
            # 调用模型做出最终决策
            response = self.model_backend.run(openai_messages)
            decision = response.choices[0].message.content
            rebellion_log.info(f"叛军头子 {self.leader_id} 的决策：{decision}")
            return decision
        except Exception as e:
            rebellion_log.error(f"叛军头子 {self.leader_id} 在做出决策时出错：{e}")
            return "无法做出决策"

    def print_leader_status(self):
        """
        打印叛军头子的状态
        """
        rebellion_log.info(f"叛军头子 {self.leader_id} 的状态：")
        rebellion_log.info(f"  当前时间：{self.time}年")
        rebellion_log.info(f"  角色：{self.role}")
        rebellion_log.info(f"  人物性格：{self.mbti}")

class Rebellion:
    def __init__(self, initial_strength, initial_resources, initial_support):
        """
        初始化叛军类
        :param initial_strength: 初始力量
        :param initial_resources: 初始资源
        :param initial_support: 初始支持度
        """
        self.strength = initial_strength
        self.resources = initial_resources
        self.support = initial_support

    def attack_government_facility(self, strength_investment):
        """
        袭击政府设施
        :param strength_investment: 投入的力量
        """
        if self.strength >= strength_investment:
            self.strength -= strength_investment * 0.1  # 力量消耗
            print(f"叛军成功袭击了政府设施，消耗了 {strength_investment * 0.1} 力量。")
        else:
            print("叛军力量不足以袭击政府设施。")

    def recruit_new_members(self, resource_investment):
        """
        招募新成员
        :param resource_investment: 投入的资源
        """
        if self.resources >= resource_investment:
            self.strength += resource_investment * 0.1  # 假设每投入1单位资源，力量增加0.1
            self.resources -= resource_investment
            print(f"叛军成功招募了新成员，力量增加了 {resource_investment * 0.1}。")
        else:
            print("叛军资源不足以招募新成员。")

    def gain_public_support(self, resource_investment):
        """
        争取民众支持
        :param resource_investment: 投入的资源
        """
        if self.resources >= resource_investment:
            self.support += resource_investment * 0.1  # 假设每投入1单位资源，支持度增加0.1
            self.resources -= resource_investment
            print(f"叛军成功争取了民众支持，支持度增加了 {resource_investment * 0.1}。")
        else:
            print("叛军资源不足以争取民众支持。")

    def retreat(self):
        """
        撤退
        """
        print("叛军决定撤退。")

    def get_strength(self):
        """
        获取当前力量
        :return: 当前力量
        """
        return self.strength

    def get_resources(self):
        """
        获取当前资源
        :return: 当前资源
        """
        return self.resources

    def get_support(self):
        """
        获取当前支持度
        :return: 当前支持度
        """
        return self.support

    def print_rebellion_status(self):
        """
        打印叛军状态（用于调试）
        """
        print(f"叛军力量: {self.strength}")
        print(f"叛军资源: {self.resources}")
        print(f"叛军支持度: {self.support}")