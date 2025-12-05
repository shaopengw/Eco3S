from .shared_imports import *
from ..utils.simulation_context import SimulationContext

class BaseAgent:
    """基础Agent类，封装共同的大模型调用逻辑"""
    def __init__(self, agent_id, group_type, window_size=3, model_api_name=None, model_type_name=None):
        """
        初始化BaseAgent
        
        Args:
            agent_id: Agent ID
            group_type: 组类型
            window_size: 记忆窗口大小
            model_api_name: 指定的API名称（如 "CLAUDE", "OPENAI"），None表示随机选择
            model_type_name: 指定的模型类型（如 "claude-sonnet-4-5-20250929"），None表示使用API的默认模型
        """
        self.agent_id = agent_id
        self.model_manager = ModelManager()
        
        # 根据参数选择模型配置
        if model_api_name:
            model_config = self.model_manager.get_specific_model_config(model_api_name, model_type_name)
        else:
            model_config = self.model_manager.get_random_model_config()
        
        # 对于 OPENAI_COMPATIBLE_MODEL，直接使用字符串作为 model_type
        if model_config["model_platform"] == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
            self.model_type = model_config["model_type"]
        else:
            self.model_type = ModelType(model_config["model_type"])
            
        self.model_config = ChatGPTConfig(**model_config["model_config"])
        
        # 构建 ModelFactory.create 的参数
        create_params = {
            "model_platform": model_config["model_platform"],
            "model_type": self.model_type,
            "model_config_dict": self.model_config.as_dict(),
        }
        
        # 如果是 OPENAI_COMPATIBLE_MODEL，添加 url 和 api_key
        if model_config["model_platform"] == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
            create_params["url"] = model_config["url"]
            create_params["api_key"] = model_config["api_key"]
        
        self.model_backend = ModelFactory.create(**create_params)
        
        # 对于 token counter，如果是自定义模型，使用一个通用的模型类型
        if isinstance(self.model_type, str):
            # 使用 GPT-4 的 token counter 作为通用计数器
            self.token_counter = OpenAITokenCounter(ModelType.GPT_4O_MINI)
            memory_model_type = ModelType.GPT_4O_MINI  # 用于 MemoryManager
        else:
            self.token_counter = OpenAITokenCounter(self.model_type)
            memory_model_type = self.model_type
            
        self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
        self.memory = MemoryManager(
            agent_id=self.agent_id,
            model_type=memory_model_type,
            group_type=group_type,
            window_size=window_size
        )
        self.memory.set_agent(self)  # 设置agent引用
        self.system_message = None
        
        # 初始化默认值
        self.max_retry_attempts = 3
        self.retry_delay = 1.0
        
        # 从配置文件读取参数（如果存在）
        try:
            import yaml
            with open(f'config/{SimulationContext.get_simulation_type()}/simulation_config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.max_retry_attempts = config['simulation'].get('max_retry_attempts', 3)
                self.retry_delay = config['simulation'].get('retry_delay', 1.0)
        except Exception as e:
            logging.warning(f"读取重试配置失败，使用默认值：{e}")

    async def generate_llm_response(self, prompt):
        """生成大模型回应的通用方法"""
        prompt_messages = []

        if self.memory:
            prompt_messages = await self.memory.get_context_messages()

        # 添加当前提示词
        user_message = {
            "role": "user",
            "content": prompt
        }
        prompt_messages.append(user_message)

        messages = []
        if self.system_message:
            messages.append({
                "role": "system",
                "content": self.system_message
            })
        messages.extend(prompt_messages)

        # print("-------总提示信息-----------",messages)

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