import asyncio
import logging
from .shared_imports import *

class BaseAgent:
    """基础Agent类，封装共同的大模型调用逻辑"""
    def __init__(self, agent_id, group_type, window_size=3):
        self.agent_id = agent_id
        self.model_manager = ModelManager()
        model_config = self.model_manager.get_random_model_config()
        self.model_type = ModelType(model_config["model_type"])
        self.model_config = ChatGPTConfig(temperature=0.7)
        self.model_backend = ModelFactory.create(
            model_platform=model_config["model_platform"],
            model_type=self.model_type,
            model_config_dict=self.model_config.as_dict(),
        )
        self.token_counter = OpenAITokenCounter(self.model_type)
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = MemoryManager(
            agent_id=self.agent_id,
            model_type=self.model_type,
            group_type=group_type,
            window_size=window_size
        )
        self.system_message = None

    async def generate_llm_response(self, prompt, system_message=None):
        """生成大模型回应的通用方法"""
        user_message = BaseMessage.make_user_message(
            role_name=self.__class__.__name__,
            content=prompt,
        )

        openai_messages = await self.memory.get_context_messages(prompt)
        if not openai_messages:
            messages = []
            if system_message or self.system_message:
                messages.append({
                    "role": "system",
                    "content": system_message or self.system_message
                })
            messages.append(user_message.to_openai_user_message())
            openai_messages = messages

        try:
            response = await asyncio.to_thread(self.model_backend.run, openai_messages)
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"{self.__class__.__name__} {self.agent_id} 在生成回应时出错：{e}")
            return None