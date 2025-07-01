from .shared_imports import *

class BaseAgent:
    """基础Agent类，封装共同的大模型调用逻辑"""
    def __init__(self, agent_id, group_type, window_size):
        self.agent_id = agent_id
        self.model_manager = ModelManager()
        model_config = self.model_manager.get_random_model_config()
        self.model_type = ModelType(model_config["model_type"])
        self.model_config = ChatGPTConfig(**model_config["model_config"])
        # self.model_config = ChatGPTConfig(model_config["model_config"])
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
        self.memory.set_agent(self)  # 设置agent引用
        self.system_message = None
        
        # 从配置文件读取参数
        try:
            import yaml
            with open('config/simulation_config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.max_retry_attempts = config['simulation'].get('max_retry_attempts', 3)
                self.retry_delay = config['simulation'].get('retry_delay', 1.0)
        except Exception as e:
            logging.warning(f"读取重试配置失败，使用默认值：{e}")

    async def generate_llm_response(self, prompt, system_message=None):
        """生成大模型回应的通用方法"""
        user_message = BaseMessage.make_user_message(
            role_name=self.__class__.__name__,
            content=prompt,
        )

        prompt_messages = await self.memory.get_context_messages(prompt)
        if not prompt_messages:
            messages = []
            if system_message or self.system_message:
                messages.append({
                    "role": "system",
                    "content": system_message or self.system_message
                })
            messages.append(user_message.to_openai_user_message())
            prompt_messages = messages
        print("-------总提示信息-----------",prompt_messages)
        attempts = 0
        while attempts < self.max_retry_attempts:
            try:
                response = await asyncio.to_thread(self.model_backend.run, prompt_messages)
                content = response.choices[0].message.content
                if content is not None:
                    return content
                
                # 如果返回None，记录日志并重试
                logging.warning(f"{self.__class__.__name__} {self.agent_id} 第{attempts + 1}次尝试返回None，准备重试")
                
            except Exception as e:
                logging.error(f"{self.__class__.__name__} {self.agent_id} 第{attempts + 1}次尝试出错：{e}")
            
            attempts += 1
            if attempts < self.max_retry_attempts:
                await asyncio.sleep(self.retry_delay)  # 延迟一段时间后重试
        
        logging.error(f"{self.__class__.__name__} {self.agent_id} 在{self.max_retry_attempts}次尝试后仍然失败")
        return None