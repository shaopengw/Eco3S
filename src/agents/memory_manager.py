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
    def __init__(self, window_size=3, summary_interval=3):
        """
        个人记忆系统
        :param window_size: 短期记忆窗口大小
        :param summary_interval: 多少条记录后进行一次总结
        """
        self.chat_history = ChatHistoryBlock()  # 短期记忆
        self.longterm_memory = []  # 长期记忆，存储总结
        self.window_size = window_size
        self.summary_interval = summary_interval
        self.record_count = 0
        self.summary_prompt_template = (
            "你是一个{role}。请总结以下{count}条记忆，生成一个简洁的总结：\n"
            "{memories}\n"
            "如果有更早的记忆总结，请一并考虑：\n"
            "{previous_summary}\n"
            "请用一段话总结这些记忆的要点。"
        )
    
    def write_record(self, record):
        """写入记录到个人历史"""
        self.chat_history.write_record(record)
        self.record_count += 1
    
    def retrieve(self, limit=3):
        """获取最近的个人历史记录（短期记忆）"""
        return self.chat_history.retrieve(limit)
    
    def get_longterm_memory(self):
        """获取长期记忆"""
        return self.longterm_memory

    async def maybe_create_summary(self, role_name, llm_generator):
        """
        检查是否需要创建总结，如果需要则创建
        :param role_name: 角色名称
        :param llm_generator: 用于生成总结的LLM函数
        """
        if self.record_count >= self.summary_interval:
            # 获取最近的记录
            recent_records = self.chat_history.retrieve(self.summary_interval)
            memories_text = "\n".join([
                record.memory_record.message.content 
                for record in recent_records if hasattr(record, 'memory_record')
            ])
            
            # 获取之前的总结
            previous_summary = self.longterm_memory[-1] if self.longterm_memory else ""
            
            # 构建提示词
            prompt = self.summary_prompt_template.format(
                role=role_name,
                count=self.summary_interval,
                memories=memories_text,
                previous_summary=previous_summary
            )
            
            # 生成总结
            summary = await llm_generator(prompt)
            if summary:
                self.longterm_memory.append(summary)
                self.record_count = 0  # 重置计数器

class MemoryManager:
    def __init__(self, agent_id, model_type, group_type='default', window_size=5, summary_interval=5):
        """
        初始化代理记忆管理器
        :param agent_id: 代理ID
        :param model_type: 模型类型
        :param group_type: 群体类型，'government' 或 'rebellion'
        :param window_size: 最近对话窗口大小
        :param summary_interval: 多少条记录后进行一次总结
        """
        self.agent_id = agent_id
        self.token_counter = OpenAITokenCounter(model_type)
        self.context_creator = ScoreBasedContextCreator(
            token_counter=self.token_counter,
            token_limit=4096
        )
        
        # 使用群体特定的共享向量数据库（暂时保留但不使用）
        self.shared_memory = SharedVectorDB(group_type)
        # 初始化个人记忆系统
        self.personal_memory = PersonalMemory(window_size, summary_interval)
        
        self.window_size = window_size
        self.agent = None  # 存储对应的agent引用
    
    def set_agent(self, agent):
        """设置对应的agent引用"""
        self.agent = agent

    async def write_record(self, role_name, content, is_user=True, round_num=None, store_in_shared=False):
        """
        写入新的对话记录
        :param store_in_shared: 是否存入共享记忆，默认为False（暂时不使用）
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
        # 检查是否需要创建总结，使用agent的generate_llm_response方法
        if self.agent:
            await self.personal_memory.maybe_create_summary(role_name, self.agent.generate_llm_response)
        
        # 暂时不使用共享记忆
        if store_in_shared:
            pass

    async def get_context_messages(self, current_prompt):
        """获取上下文消息"""
        # 获取短期记忆（最近的记录）
        try:
            recent_context = self.personal_memory.retrieve(limit=3)
        except:
            recent_context = []
            
        # 获取长期记忆（总结）
        longterm_memory = self.personal_memory.get_longterm_memory()
        
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
        
        # 添加长期记忆（如果有）
        if longterm_memory:
            context.append({
                "role": "system",
                "content": "历史记忆总结：" + "\n".join(longterm_memory[-2:])  # 只使用最近的2条总结
            })
        
        # 处理短期记忆
        for msg in recent_context:
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
        self.personal_memory.longterm_memory.clear()