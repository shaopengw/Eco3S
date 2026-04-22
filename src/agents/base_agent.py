from .shared_imports import *
from collections import deque
from ..utils.simulation_context import SimulationContext
from .model_backend_factory import create_backend_from_model_config

class BaseAgent:
    """基础Agent类，封装共同的大模型调用逻辑"""

    # 通用限流容器：按 rate_limit_key 使用配置文件中的策略。
    _rate_limit_profiles = {}
    _rate_limit_semaphores = {}
    _rate_limit_timestamps = {}
    _rate_limit_locks = {}

    @classmethod
    def _configure_rate_limits(cls, profiles):
        if not isinstance(profiles, dict):
            return
        cls._rate_limit_profiles = {str(k): dict(v or {}) for k, v in profiles.items()}

    @classmethod
    def _get_rate_limit_profile(cls, key):
        if not key:
            return {}
        profile = cls._rate_limit_profiles.get(key) or cls._rate_limit_profiles.get("default") or {}
        return dict(profile)

    @classmethod
    def _get_rate_limit_semaphore(cls, key, max_concurrency):
        if not key or max_concurrency <= 0:
            return None
        semaphore = cls._rate_limit_semaphores.get(key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(max_concurrency)
            cls._rate_limit_semaphores[key] = semaphore
        return semaphore

    @classmethod
    async def _acquire_rate_slot(cls, key, rpm_limit, window_seconds):
        if not key or rpm_limit <= 0:
            return

        if key not in cls._rate_limit_timestamps:
            cls._rate_limit_timestamps[key] = deque()
        if key not in cls._rate_limit_locks:
            cls._rate_limit_locks[key] = asyncio.Lock()

        timestamps = cls._rate_limit_timestamps[key]
        lock = cls._rate_limit_locks[key]

        while True:
            async with lock:
                now = time.monotonic()
                window_start = now - window_seconds

                while timestamps and timestamps[0] <= window_start:
                    timestamps.popleft()

                if len(timestamps) < rpm_limit:
                    timestamps.append(now)
                    return

                oldest = timestamps[0]
                wait_seconds = max(
                    0.01,
                    window_seconds - (now - oldest) + 0.01,
                )

            await asyncio.sleep(wait_seconds)

    def __init__(self, agent_id, group_type, window_size=3, model_api_name=None, model_type_name=None):
        """
        初始化BaseAgent
        
        Args:
            agent_id: Agent ID
            group_type: 组类型
            window_size: 记忆窗口大小
            model_api_name: 指定的API名称（如 "CLAUDE", "OPENAI"），None表示按模型名或随机选择
            model_type_name: 指定的模型类型（如 "claude-sonnet-4-5-20250929"），可在不指定API时直接选模型
        """
        self.agent_id = agent_id
        self.model_manager = ModelManager()
        
        # 根据参数选择模型配置
        if model_api_name:
            model_config = self.model_manager.get_specific_model_config(model_api_name, model_type_name)
        elif model_type_name:
            model_config = self.model_manager.get_model_config_by_type(model_type_name)
        else:
            model_config = self.model_manager.get_random_model_config()

        BaseAgent._configure_rate_limits(self.model_manager.get_rate_limit_profiles())
        self.rate_limit_key = model_config.get("rate_limit_key")

        # 统一从配置创建 backend（支持本地 Ollama `/api/generate`）
        self.model_backend, self.model_type, self.token_counter, memory_model_type = (
            create_backend_from_model_config(model_config)
        )
            
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

        rate_limit_key = getattr(self.model_backend, "rate_limit_key", None) or getattr(self, "rate_limit_key", None)
        profile = BaseAgent._get_rate_limit_profile(rate_limit_key)
        max_concurrency = int(profile.get("max_concurrency", 0) or 0)
        rpm_limit = int(profile.get("rpm_limit", 0) or 0)
        window_seconds = float(profile.get("window_seconds", 60) or 60)
        semaphore = BaseAgent._get_rate_limit_semaphore(rate_limit_key, max_concurrency)

        attempts = 0
        while attempts < self.max_retry_attempts:
            try:
                await BaseAgent._acquire_rate_slot(rate_limit_key, rpm_limit, window_seconds)

                if semaphore is not None:
                    async with semaphore:
                        response = await asyncio.to_thread(self.model_backend.run, messages)
                else:
                    response = await asyncio.to_thread(self.model_backend.run, messages)
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