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
    _instances = {}
    
    def __new__(cls, group_type='default'):
        """
        创建或获取指定群体的向量数据库实例
        :param group_type: 群体类型，如 'government' 或 'rebellion'
        """
        if group_type not in cls._instances:
            instance = super(SharedVectorDB, cls).__new__(cls)
            instance.vector_db = VectorDBBlock()
            cls._instances[group_type] = instance
        return cls._instances[group_type]
    
    def write_record(self, record):
        """写入记录到共享向量数据库"""
        self.vector_db.write_record(record)
        
    def retrieve(self, query, limit=2):
        """从共享向量数据库检索记录"""
        return self.vector_db.retrieve(query, limit=limit)

class PersonalMemory:
    def __init__(self, window_size=5):
        """个人记忆系统"""
        self.chat_history = ChatHistoryBlock()
        self.window_size = window_size
    
    def write_record(self, record):
        """写入记录到个人历史"""
        self.chat_history.write_record(record)
    
    def retrieve(self, limit=3):
        """获取最近的个人历史记录"""
        return self.chat_history.retrieve(limit)

class MemoryManager:
    def __init__(self, agent_id, model_type, group_type='default', window_size=5):
        """
        初始化代理记忆管理器
        :param agent_id: 代理ID
        :param model_type: 模型类型
        :param group_type: 群体类型，'government' 或 'rebellion'
        :param window_size: 最近对话窗口大小
        """
        self.agent_id = agent_id
        self.token_counter = OpenAITokenCounter(model_type)
        self.context_creator = ScoreBasedContextCreator(
            token_counter=self.token_counter,
            token_limit=4096
        )
        
        # 使用群体特定的共享向量数据库
        self.shared_memory = SharedVectorDB(group_type)
        # 初始化个人记忆系统
        self.personal_memory = PersonalMemory(window_size)
        
        self.window_size = window_size

    async def write_record(self, role_name, content, is_user=True, round_num=None, store_in_shared=True):
        """
        写入新的对话记录
        :param store_in_shared: 是否存入共享记忆，默认为True
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

        if round_num is not None and (
            role_name == "高级政府官员" and not is_user
        ):
            content = f"Round {round_num}: {content}"
            message.content = content

        record = MemoryRecord(
            message=message,
            role_at_backend=role
        )
        
        # 写入个人记忆
        self.personal_memory.write_record(record)
        # 根据参数决定是否写入共享记忆
        if store_in_shared:
            self.shared_memory.write_record(record)

    async def get_context_messages(self, current_prompt):
        """获取上下文消息"""
        # 从个人历史获取最近3条记录
        try:
            personal_context = self.personal_memory.retrieve(limit=3)
        except:
            personal_context = []
            
        # 从共享向量数据库检索2条相关记录
        try:
            shared_context = self.shared_memory.retrieve(current_prompt, limit=2)
        except:
            shared_context = []
        
        def clean_message(msg):
            if isinstance(msg, dict):
                return {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                }
            if hasattr(msg, "memory_record"):
                message = msg.memory_record.message
                return {
                    "role": "assistant" if message.role_type == "assistant" else "user",
                    "content": message.content
                }
            return None
        
        # 使用集合去重
        seen_contents = set()
        context = []
        
        # 处理个人历史记录
        for msg in personal_context:
            cleaned_msg = clean_message(msg)
            if cleaned_msg and cleaned_msg["content"] not in seen_contents:
                context.append(cleaned_msg)
                seen_contents.add(cleaned_msg["content"])
        
        # 处理共享记录
        for msg in shared_context:
            cleaned_msg = clean_message(msg)
            if cleaned_msg and cleaned_msg["content"] not in seen_contents:
                context.append(cleaned_msg)
                seen_contents.add(cleaned_msg["content"])
        
        # 添加当前提示词
        user_message = {
            "role": "user",
            "content": current_prompt
        }
        context.append(user_message)
            
        return context

    async def clear(self):
        """清空记忆"""
        self.personal_memory.chat_history.clear()