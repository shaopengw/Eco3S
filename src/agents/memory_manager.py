from camel.memories import (
    ChatHistoryBlock,
    LongtermAgentMemory,
    MemoryRecord,
    ScoreBasedContextCreator,
    VectorDBBlock,
)
from camel.messages import BaseMessage
from camel.types import ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter

class MemoryManager:
    def __init__(self, agent_id, model_type, window_size=5):
        """
        初始化代理记忆管理器
        :param agent_id: 代理ID
        :param model_type: 模型类型
        :param window_size: 最近对话窗口大小
        """
        self.agent_id = agent_id
        self.token_counter = OpenAITokenCounter(model_type)
        self.context_creator = ScoreBasedContextCreator(
            token_counter=self.token_counter,
            token_limit=4096
        )
        
        # 初始化长期记忆系统
        self.memory = LongtermAgentMemory(
            context_creator=self.context_creator,
            chat_history_block=ChatHistoryBlock(),
            vector_db_block=VectorDBBlock(),
            retrieve_limit=3  # 检索历史记录的数量限制
        )
        
        self.window_size = window_size

    async def write_record(self, role_name, content, is_user=True):
        """
        写入新的对话记录
        :param role_name: 角色名称
        :param content: 对话内容
        :param is_user: 是否为用户消息
        """
        if is_user:
            message = BaseMessage.make_user_message(
                role_name=role_name,
                content=content
            )
            role = OpenAIBackendRole.USER
        else:
            message = BaseMessage.make_assistant_message(
                role_name=role_name,
                content=content
            )
            role = OpenAIBackendRole.ASSISTANT

        record = MemoryRecord(
            message=message,
            role_at_backend=role
        )
        
        self.memory.write_record(record)

    async def get_context_messages(self, current_prompt):
        """
        获取上下文消息，包括最近对话和相关历史记录
        :param current_prompt: 当前提示词
        :return: OpenAI消息列表和系统消息
        """
        # 写入当前提示词以便检索相关历史
        await self.write_record(f"Agent_{self.agent_id}", current_prompt)
        
        # 获取完整上下文
        context, token_count = self.memory.get_context()
        
        # 如果上下文为空，添加默认系统消息
        if not context:
            system_message = {
                "role": "system",
                "content": f"你是Agent_{self.agent_id}，负责根据历史记录和当前状态做出决策。"
            }
            context = [system_message]
            
        return context

    async def clear(self):
        """清空记忆"""
        self.memory.clear()