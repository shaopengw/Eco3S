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

class SharedVectorDB:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedVectorDB, cls).__new__(cls)
            cls._instance.vector_db = VectorDBBlock()
        return cls._instance

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
        
        # 使用共享的向量数据库
        shared_vector_db = SharedVectorDB()
        
        # 初始化长期记忆系统
        self.memory = LongtermAgentMemory(
            context_creator=self.context_creator,
            chat_history_block=ChatHistoryBlock(),
            vector_db_block=shared_vector_db.vector_db,
            retrieve_limit=3  # 检索历史记录的数量限制
        )
        
        self.window_size = window_size

    async def write_record(self, role_name, content, is_user=True, round_num=None):
        """
        写入新的对话记录
        :param role_name: 角色名称
        :param content: 对话内容
        :param is_user: 是否为用户消息
        :param round_num: 当前轮次
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

        # 如果是信息官的总结或高级官员的决策，添加轮次信息
        if round_num is not None and (
            role_name == "高级政府官员" and not is_user
        ):
            content = f"Round {round_num}: {content}"
            message.content = content

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
        # 获取最近的历史记录
        try:
            recent_context = self.memory.chat_history_block.retrieve(3)
        except:
            recent_context = []
            
        # 从向量数据库检索相似记录
        try:
            similar_context = self.memory.vector_db_block.retrieve(current_prompt)
        except:
            similar_context = []
        
        def clean_message(msg):
            if isinstance(msg, dict):
                return {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                }
            # 如果是 ContextRecord 对象
            if hasattr(msg, "memory_record"):
                message = msg.memory_record.message
                return {
                    "role": "assistant" if message.role_type == "assistant" else "user",
                    "content": message.content
                }
            return None
        
        # 合并两种上下文和提示词
        context = []
        if recent_context:
            context.extend(filter(None, [clean_message(msg) for msg in recent_context]))
        if similar_context:
            context.extend(filter(None, [clean_message(msg) for msg in similar_context]))
        
        # 添加当前提示词
        user_message = {
            "role": "user",
            "content": current_prompt
        }
        context.append(user_message)
            
        return context

    async def clear(self):
        """清空记忆"""
        self.memory.clear()