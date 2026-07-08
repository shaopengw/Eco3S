from .shared_imports import *
from ..utils.simulation_context import SimulationContext
import importlib
import inspect
import os
import yaml

class BaseAgent:
    """通用模拟实体基类。

    提供 LLM 调用、Memory、Profile 容器，以及通用决策/执行/消息/信息接收骨架。
    子类通过重写抽象钩子注入场景特有逻辑。
    """
    def __init__(self, agent_id, group_type, window_size=3, model_api_name=None, model_type_name=None,
                 profile_config=None, prompts=None, actions_config=None, memory_token_limit=4096, **kwargs):
        """
        初始化BaseAgent

        Args:
            agent_id: Agent ID
            group_type: 组类型
            window_size: 记忆窗口大小
            model_api_name: 指定的API名称（如 "CLAUDE", "OPENAI"），None表示随机选择
            model_type_name: 指定的模型类型（如 "claude-sonnet-4-5-20250929"），None表示使用API的默认模型
            profile_config: 动态画像配置（字典或None）。若为字典，会作为初始profile数据；
                            若为None，则初始化空字典，供子类动态写入。
            memory_token_limit: MemoryManager 的 token 预算（默认 4096）
            **kwargs: 额外参数，供子类扩展使用，BaseAgent 本身不做处理
        """
        self.agent_id = agent_id
        # 动态画像容器：所有场景-specific 属性统一放这里
        self.profile = profile_config if isinstance(profile_config, dict) else {}
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

        # 保留 reasoning 配置和接口信息，供 generate_llm_response 按需使用
        self._extra_kwargs = model_config.get("reasoning_config")
        self._api_url = model_config.get("url")
        self._api_key = model_config.get("api_key")

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
            window_size=window_size,
            token_limit=memory_token_limit
        )
        self.memory.set_agent(self)  # 设置agent引用
        self.system_message = None

        # 提示词与行为配置（子类或外部注入）
        self.prompts = prompts if isinstance(prompts, dict) else {}
        self.actions_config = actions_config if isinstance(actions_config, dict) else {}

        # 初始化默认值
        self.max_retry_attempts = 3
        self.retry_delay = 1.0
        
        # 从 kwargs 中提取影响函数注册表（用于 effects 的 influence.xxx 触发）
        self.influence_registry = kwargs.get('influence_registry')
        # 储存 LLM 决策的额外参数字段（action-specific，如 target_market、supplier_choices）
        self._last_decision_meta = {}
        # 供 influence.xxx 效果路由到插件（由 simulator 在执行决策前注入）
        self._plugin = None

        # 从配置文件读取参数（如果存在）
        # 兼容新项目（projects/<name>/config/）与旧项目（config/<name>/）两种布局
        simulation_type = SimulationContext.get_simulation_type()
        candidate_paths = [
            f'projects/{simulation_type}/config/simulation_config.yaml',
            f'config/{simulation_type}/simulation_config.yaml',
        ]
        config_loaded = False
        for cfg_path in candidate_paths:
            try:
                if not os.path.exists(cfg_path):
                    continue
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if isinstance(config, dict) and isinstance(config.get('simulation'), dict):
                    self.max_retry_attempts = config['simulation'].get('max_retry_attempts', 3)
                    self.retry_delay = config['simulation'].get('retry_delay', 1.0)
                    config_loaded = True
                    break
            except Exception:
                continue
        if not config_loaded:
            logging.warning(f"读取重试配置失败，使用默认值：未找到 {candidate_paths}")

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
                extra_kwargs = getattr(self, '_extra_kwargs', None)
                if extra_kwargs:
                    from openai import OpenAI
                    client = OpenAI(base_url=self._api_url, api_key=self._api_key)
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=self.model_type,
                        messages=messages,
                        **extra_kwargs
                    )
                else:
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

    # ---------- 动态画像/属性系统 ----------
    def attr(self, key: str, default=None):
        """安全读取 profile 中的属性。子类可把任意场景-specific 字段放这里。"""
        return self.profile.get(key, default)

    def set_attr(self, key: str, value) -> None:
        """写入 profile 属性。"""
        self.profile[key] = value

    def _build_profile_vars_doc(self, **kwargs) -> str:
        """根据 self.profile 动态构建画像变量说明文本。

        将当前 Agent 的所有 profile 属性及动态计算描述格式化为一段结构化文本，
        直接注入系统消息，使模板无需硬编码任何具体属性名。

        Args:
            **kwargs: 可传入 tax_rate、basic_living_cost 等上下文参数，
                      用于动态计算经济状况等衍生描述。

        Returns:
            str: 画像变量说明文本；若 profile 为空则返回空字符串。
        """
        if not isinstance(self.profile, dict) or not self.profile:
            return ""

        lines = []

        # 子类可覆盖的元数据键集合（这些键不应出现在画像文档中）
        skip_keys = getattr(self, '_META_PROFILE_KEYS', set())

        # 基础属性（按字母序，保证稳定输出）
        for key, value in sorted(self.profile.items()):
            if key.startswith("_") or key in skip_keys:
                continue
            if isinstance(value, (int, float)):
                lines.append(f"  - {key} = {value}")
            elif isinstance(value, str):
                preview = value[:40] + "..." if len(value) > 40 else value
                lines.append(f'  - {key} = "{preview}"')
            elif isinstance(value, bool):
                lines.append(f"  - {key} = {'是' if value else '否'}")
            else:
                lines.append(f"  - {key} = {value}")

        # 动态计算描述（仅当对应属性存在且有上下文参数时才生成）
        basic_living_cost = kwargs.get('basic_living_cost', 0)
        tax_rate = kwargs.get('tax_rate', 0)

        if 'income' in self.profile and basic_living_cost > 0:
            income_val = self.profile['income'] * (1 - tax_rate)
            if income_val > 0:
                if basic_living_cost * 0.8 > income_val:
                    lines.append("  - 经济状况 = 终日辛劳不得温饱")
                elif basic_living_cost * 1 > income_val:
                    lines.append("  - 经济状况 = 勉强糊口")
                elif basic_living_cost * 1.6 > income_val:
                    lines.append("  - 经济状况 = 生活尚算安稳")
                else:
                    lines.append("  - 经济状况 = 生活富裕丰衣足食")
            else:
                lines.append("  - 经济状况 = 家破人亡难以为继")

        if 'health_index' in self.profile:
            prompts = getattr(self, 'prompts_resident', getattr(self, 'prompts', {}))
            health_conditions = prompts.get('health_conditions', []) if prompts else []
            idx = self.profile['health_index']
            if 0 <= idx < len(health_conditions) and health_conditions[idx]:
                lines.append(f"  - 健康状况 = {health_conditions[idx]}")

        if 'satisfaction' in self.profile:
            prompts = getattr(self, 'prompts_resident', getattr(self, 'prompts', {}))
            satisfaction_levels = prompts.get('satisfaction_levels', []) if prompts else []
            sat = self.profile['satisfaction']
            sat_idx = min(int(sat // 20), len(satisfaction_levels) - 1) if satisfaction_levels else 0
            if satisfaction_levels:
                lines.append(f"  - 满意度 = {satisfaction_levels[sat_idx]}（{sat}/100）")

        if not lines:
            return ""
        return "你的画像属性：\n" + "\n".join(lines)

    # ==================== 通用决策框架 ====================

    async def decide_action(self, context=None, **kwargs):
        """通用决策入口。

        流程：
        1. 调用 _build_decision_prompt() 构建提示词（子类重写）
        2. 调用 generate_llm_response() 获取 LLM 响应
        3. 调用 _parse_decision_response() 解析结果（子类重写）

        Returns:
            解析后的决策结果，格式由子类决定。
        """
        # 防御：model_backend 未初始化时自动初始化（兼容无 town 的轻量级实体）
        if self.model_backend is None:
            if not hasattr(self, 'model_manager') or self.model_manager is None:
                self.model_manager = ModelManager()
            model_config = self.model_manager.get_random_model_config()

            model_platform = model_config["model_platform"]
            model_type_raw = model_config["model_type"]
            if model_platform == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
                self.model_type = model_type_raw
            else:
                self.model_type = ModelType(model_type_raw)

            self.model_config = ChatGPTConfig(**model_config["model_config"])
            create_params = {
                "model_platform": model_platform,
                "model_type": self.model_type,
                "model_config_dict": self.model_config.as_dict(),
            }
            if model_platform == ModelPlatformType.OPENAI_COMPATIBLE_MODEL:
                create_params["url"] = model_config["url"]
                create_params["api_key"] = model_config["api_key"]

            self.model_backend = ModelFactory.create(**create_params)

            if isinstance(self.model_type, str):
                self.token_counter = OpenAITokenCounter(ModelType.GPT_4O_MINI)
            else:
                self.token_counter = OpenAITokenCounter(self.model_type)
            self.context_creator = ScoreBasedContextCreator(self.token_counter, 4096)
            if not hasattr(self, 'memory') or self.memory is None:
                self.memory = MemoryManager(
                    agent_id=self.agent_id,
                    model_type=self.model_type if not isinstance(self.model_type, str) else ModelType.GPT_4O_MINI,
                    group_type=getattr(self, 'group_type', 'baseagent'),
                )
                self.memory.set_agent(self)

            logging.warning(
                f"{self.__class__.__name__} {self.agent_id} 的 model_backend 缺失，已自动初始化"
            )

        # 确保重试参数存在（轻量级实体可能未设置）
        if not hasattr(self, 'max_retry_attempts'):
            self.max_retry_attempts = 3
        if not hasattr(self, 'retry_delay'):
            self.retry_delay = 1.0
        if not hasattr(self, 'system_message'):
            self.system_message = None

        prompt = await self._build_decision_prompt(context, **kwargs)
        if not prompt:
            return None

        # 子类可在 _build_decision_prompt 前/后通过钩子更新系统消息
        # 这里提供一个通用回调入口
        await self._pre_llm_call_hook(context, **kwargs)

        response = await self.generate_llm_response(prompt)
        if not response:
            return None

        return await self._parse_decision_response(response, context, **kwargs)

    # ---------- simulator 兼容适配层 ----------
    # 通用 simulator（simulator_template / 各项目 simulator）按 Resident 方言调用
    # decide_action_by_llm / execute_decision。这里提供薄适配，使任何裸 BaseAgent 实体
    # （entity_type=baseagent）都能被通用 simulator 直接驱动，无需继承 Resident。
    # 注意：标识统一使用 agent_id，不再引入 resident_id 别名。

    async def decide_action_by_llm(self, **kwargs):
        """decide_action 的兼容包装：把 kwargs 作为决策上下文透传。"""
        return await self.decide_action(context=kwargs, **kwargs)

    async def execute_decision(self, select, *args, **kwargs):
        """execute_action 的兼容包装，自动注入决策参数模板。"""
        meta = getattr(self, '_last_decision_meta', {})
        if meta and not kwargs:
            kwargs = dict(meta)
        return await self.execute_action(select, *args, **kwargs)

    async def _build_decision_prompt(self, context, **kwargs):
        """抽象钩子：构建决策提示词。子类可重写。

        默认实现支持标准 key ``decision_prompt``，并兼容旧版 ``decide_action_prompt``。
        若存在 ``decision_json`` / ``decide_action_json``，会追加到 prompt 末尾。

        Args:
            context: 决策上下文（字典或自定义对象）
            **kwargs: 额外参数

        Returns:
            str: 构建好的提示词字符串；若无法构建则返回 None。
        """
        if not self.prompts:
            return None

        # 优先使用新版标准 key，回退旧版 key
        decision_template = (
            self.prompts.get('decision_prompt')
            or self.prompts.get('decide_action_prompt')
        )
        if not decision_template:
            return None

        try:
            vars_ = self._get_system_message_vars(**kwargs)
            if inspect.isawaitable(vars_):
                vars_ = await vars_
            if isinstance(context, dict):
                vars_.update(context)
            prompt = decision_template.format(**vars_)

            # 若模板未显式引用 {available_actions_section} 且存在 action 列表，
            # 则在 prompt 末尾自动追加，确保 LLM 知晓当前可用的 action 选项
            actions_section = vars_.get('available_actions_section', '')
            if actions_section and '{available_actions_section}' not in decision_template:
                # 防御：检查 prompt 中是否已出现至少一个 action 名称
                actions = self.actions_config.get('actions', {}) if self.actions_config else {}
                action_names = [a.get('name', '') for a in actions.values() if isinstance(a, dict)]
                if not any(name and name in prompt for name in action_names):
                    prompt += "\n\n" + actions_section

            json_template = (
                self.prompts.get('decision_json')
                or self.prompts.get('decide_action_json')
            )
            if json_template:
                prompt += "\n" + json_template.format(**vars_)

            return prompt
        except Exception as e:
            logging.warning(f"{self.__class__.__name__} 默认决策模板渲染失败：{e}")
        return None

    async def _parse_decision_response(self, response, context, **kwargs):
        """抽象钩子：解析 LLM 的决策响应。子类可重写。

        通用实现：
        1. 清洗并解析 JSON（容忍 ```json 包裹与多段 JSON）；
        2. 通用地把所有 ``*_change`` 数值字段累加写回 profile；
        3. 归一为 simulator 认识的返回形状：
           - 含 speech：``(select, reason, speech, relation_type)``
           - 一般决策：``(select, reason)``
           - 无 select（如结构化分配输出）：返回解析后的 dict，供上层自行消费。

        Returns:
            tuple 或 dict 或 None
        """
        if not response:
            return None

        cleaned = re.sub(r"^```json\s*|\s*```$", "", response, flags=re.DOTALL).strip()

        def _merge_json(text):
            matches = re.findall(r'\{[^{}]*\}', text)
            result = {}
            for m in matches:
                try:
                    result.update(json.loads(m))
                except Exception:
                    continue
            return result or None

        decision_data = None
        try:
            decision_data = json.loads(cleaned)
        except Exception:
            decision_data = _merge_json(cleaned)

        if not isinstance(decision_data, dict):
            return {"raw_response": response}

        # 通用化：自动把所有 *_change 数值字段累加到对应 profile 属性
        for key, value in decision_data.items():
            if not key.endswith('_change') or not isinstance(value, (int, float)):
                continue
            attr_name = key[:-7]  # 去掉 _change
            self.set_attr(attr_name, self.attr(attr_name, 0) + value)

        # 保留除 select/reason/speech 外的全部决策参数（如 target_market, supplier_choices）
        # 这些字段将作为 kwargs 自动注入 execute_action -> _apply_effects 用于模板渲染
        self._last_decision_meta = {
            k: v for k, v in decision_data.items()
            if k not in ('select', 'reason', 'speech')
        }

        select = decision_data.get("select")
        reason = decision_data.get("reason", "")
        speech = decision_data.get("speech", "")

        logging.getLogger(f"{self.__class__.__name__}").info(
            f"{self.__class__.__name__} {self.agent_id} "
            f"决策结果 → select={select}, reason=\"{reason[:80]}\""
        )

        if select is None:
            # 无 select 的结构化输出（如预算分配），原样返回供上层消费
            return decision_data

        if speech:
            relation_type = random.choice(["friend", "colleague", "family", "hometown"])
            return select, reason, speech, relation_type
        return select, reason

    async def _pre_llm_call_hook(self, context, **kwargs):
        """决策前钩子，默认更新系统消息。子类可重写。"""
        # 如果 prompts 中有系统消息模板（支持多种 key），则尝试更新
        if self.prompts:
            for key in ('system_message_template', 'system_message',
                        'entity_system_message', 'system_message'):
                if key in self.prompts:
                    self.update_system_message(**kwargs)
                    break

    # ==================== 通用行为执行 ====================

    async def execute_action(self, select, *args, **kwargs):
        """通用行为执行入口。

        执行策略（优先级）：
        1. effects 声明式定义（零代码：profile 属性修改 / influence 触发）
        2. function 命令式调用（指向 Python 可调用对象）

        Args:
            select: action ID（在 actions_config['actions'] 中查找）
            *args, **kwargs: 传递给目标函数的额外参数

        Returns:
            函数执行结果；失败时返回 False 或包含错误信息的字典。
        """
        try:
            actions = self.actions_config.get('actions', {}) if self.actions_config else {}
            action = actions.get(select) or actions.get(str(select)) or (
                actions.get(int(select)) if str(select).isdigit() else None
            )
            if not action:
                logging.error(f"{self.__class__.__name__} {self.agent_id} 未找到动作配置：{select}")
                return False

            # 优先使用 effects 声明式定义（零代码行为定义）
            effects = action.get('effects')
            if effects:
                return await self._apply_effects(
                    effects,
                    action_name=action.get('name', str(select)),
                    **kwargs
                )

            # 回退到 function 调用
            func_path = action.get('function')
            if not func_path:
                logging.error(f"{self.__class__.__name__} {self.agent_id} 未找到有效的动作配置：{select}（无 effects 也无 function）")
                return False

            callable_obj = self._resolve_callable(func_path)
            if not callable_obj:
                return {
                    'unresolved_function': func_path,
                    'action': action,
                    'agent': self,
                    'kwargs': kwargs
                }

            bound_kwargs = self._bind_action_params(callable_obj, action, kwargs)
            is_async = action.get('is_async', False) or inspect.iscoroutinefunction(callable_obj)

            try:
                return await callable_obj(**bound_kwargs) if is_async else callable_obj(**bound_kwargs)
            except TypeError:
                # 参数绑定失败时的降级处理：直接传 kwargs
                return await callable_obj(**kwargs) if is_async else callable_obj(**kwargs)

        except Exception as e:
            logging.error(f"{self.__class__.__name__} {self.agent_id} 执行行为时出错：{e}")
            return False

    async def _apply_effects(self, effects, action_name="", **kwargs):
        """应用 effects 声明式配置到 profile 属性或触发影响函数。

        支持两种 target 类型：
        - ``profile.xxx`` — 直接修改 self.profile 中的属性
        - ``influence.xxx`` — 通过 influence_registry 触发影响函数

        支持三种 mode：
        - ``set`` — 直接设置值
        - ``add`` — 在原有值上增加
        - ``mul`` — 在原有值上乘以系数
        - ``trigger`` — 触发影响函数（仅 influence.xxx 目标）

        Args:
            effects: effects 配置列表
            action_name: 行为名称（用于日志）
            **kwargs: 额外上下文变量，用于渲染 effects 中的模板字符串（如 {calculated_utilization}）

        Returns:
            bool: 是否成功执行所有 effects
        """
        if not effects:
            return True

        # 构建模板渲染上下文：profile + kwargs
        render_vars = {**self.profile, **kwargs}

        def _resolve_value(raw_value):
            """解析 effects 中的 value，支持模板字符串和字面量。"""
            if raw_value is None:
                return None
            if isinstance(raw_value, str):
                # 尝试用 render_vars 渲染模板字符串
                template_vars = re.findall(r'\{(\w+)\}', raw_value)
                if template_vars:
                    # 仅当所有模板变量都可解析时才渲染
                    try:
                        rendered = raw_value.format(**render_vars)
                        # 尝试转为数值
                        try:
                            return float(rendered) if '.' in rendered else int(rendered)
                        except (ValueError, TypeError):
                            return rendered
                    except KeyError:
                        # 模板变量缺失 → 尝试把原始字符串当数值解析
                        try:
                            return float(raw_value) if '.' in raw_value else int(raw_value)
                        except (ValueError, TypeError):
                            return raw_value
                else:
                    # 无模板变量，尝试转为数值
                    try:
                        return float(raw_value) if '.' in raw_value else int(raw_value)
                    except (ValueError, TypeError):
                        return raw_value
            return raw_value

        for effect in effects:
            if not isinstance(effect, dict):
                continue

            target = effect.get('target', '')
            mode = effect.get('mode', 'set')
            value = _resolve_value(effect.get('value'))
            params = effect.get('params', {})

            # ---- profile.xxx：修改 Agent 自有属性 ----
            if target.startswith('profile.'):
                attr_name = target[8:]
                if not attr_name:
                    continue

                current = self.attr(attr_name, 0)

                try:
                    num_value = float(value) if value is not None else 0
                except (ValueError, TypeError):
                    continue

                if mode == 'set':
                    new_val = num_value
                elif mode == 'add':
                    new_val = current + num_value
                elif mode == 'mul':
                    new_val = current * num_value
                else:
                    continue

                self.set_attr(attr_name, new_val)
                logging.getLogger(self.__class__.__name__).info(
                    f"{self.__class__.__name__} {self.agent_id} "
                    f"执行 {action_name}: {attr_name} = {current:.4g} → {new_val:.4g}（{mode} {num_value:.4g}）"
                )

            # ---- influence.xxx：触发影响函数 ----
            elif target.startswith('influence.'):
                func_name = target[10:]
                if not func_name:
                    continue

                # 渲染 params 模板（同原有模板渲染逻辑）
                try:
                    resolved_params = {}
                    for pk, pv in params.items():
                        if isinstance(pv, str):
                            pv = pv.format(**render_vars)
                        resolved_params[pk] = pv
                except KeyError:
                    resolved_params = params

                # 主路径：通过 _plugin.handle_influence 路由
                plugin = getattr(self, '_plugin', None)
                if plugin is not None and hasattr(plugin, 'handle_influence'):
                    try:
                        # 合并决策参数：将 LLM 输出的字段（_last_decision_meta）
                        # 也传给 handler，使 handler 能读取 target_market 等参数
                        meta = getattr(self, '_last_decision_meta', {})
                        for mk, mv in meta.items():
                            if mk not in resolved_params:
                                resolved_params[mk] = mv
                        plugin.handle_influence(func_name, **resolved_params)
                    except Exception as e:
                        logging.warning(
                            f"{self.__class__.__name__} {self.agent_id} "
                            f"handle_influence({func_name}) 失败: {e}"
                        )
                    continue

                # 回退路径：从 influence_registry 查找注册的影响函数
                if not self.influence_registry:
                    continue
                influence_func = None
                if hasattr(self.influence_registry, 'get'):
                    influence_func = self.influence_registry.get(func_name)
                elif hasattr(self.influence_registry, 'registry'):
                    influence_func = self.influence_registry.registry.get(func_name)

                if influence_func is None:
                    if hasattr(self.influence_registry, 'trigger'):
                        try:
                            await self.influence_registry.trigger(func_name, params)
                        except Exception:
                            pass
                    continue

                try:
                    if asyncio.iscoroutinefunction(influence_func):
                        await influence_func(**resolved_params)
                    else:
                        influence_func(**resolved_params)
                except Exception as e:
                    logging.warning(
                        f"{self.__class__.__name__} {self.agent_id} "
                        f"触发影响函数 {func_name} 失败: {e}"
                    )

        return True

    def _resolve_callable(self, func_path):
        """解析函数路径，返回可调用的函数/方法对象。

        解析优先级：
        1. 在 self 对象上逐层 getattr 解析（如 "handle_work"、"job_market.assign_job"）
        2. 作为模块路径 importlib 导入（如 "src.utils.foo.bar"）

        Args:
            func_path: 函数路径字符串

        Returns:
            callable 或 None
        """
        if not isinstance(func_path, str):
            return None
        parts = func_path.split('.')

        # 尝试在 self 上解析
        try:
            obj = self
            for p in parts:
                obj = getattr(obj, p)
            return obj
        except AttributeError:
            pass

        # 尝试作为模块路径导入
        try:
            if len(parts) > 1:
                module = importlib.import_module('.'.join(parts[:-1]))
                return getattr(module, parts[-1])
        except (ImportError, AttributeError):
            pass

        return None

    def _bind_action_params(self, callable_obj, action, kwargs):
        """根据 action 配置和 kwargs 绑定函数参数。

        绑定策略：
        1. 优先从 kwargs 和 self.__dict__ 中匹配参数名
        2. 使用 action['parameters'] 中定义的默认值
        3. 如果参数仍无值且没有默认值，传入 self

        Args:
            callable_obj: 目标可调用对象
            action: action 配置字典
            kwargs: 调用方传入的参数字典

        Returns:
            dict: 绑定好的参数字典
        """
        available = {**{k: v for k, v in self.__dict__.items()}, **kwargs}
        default_values = {
            param['name']: param.get('default')
            for param in action.get('parameters', [])
            if 'default' in param
        }

        bound_kwargs = {}
        try:
            sig = inspect.signature(callable_obj, follow_wrapped=True)
            for pname, param in sig.parameters.items():
                if pname in available:
                    bound_kwargs[pname] = available[pname]
                elif pname in default_values and default_values[pname] is not None:
                    bound_kwargs[pname] = default_values[pname]
                elif param.default is inspect.Parameter.empty:
                    bound_kwargs[pname] = self
        except Exception:
            bound_kwargs = available

        return bound_kwargs

    # ==================== 通用系统消息框架 ====================

    def update_system_message(self, **kwargs):
        """更新系统消息。

        读取 self.prompts['system_message_template'] 并渲染，
        模板变量由 _get_system_message_vars() 提供。

        Args:
            **kwargs: 额外模板变量，会覆盖 _get_system_message_vars() 中的默认值。
        """
        # 支持多种模板 key，便于不同实体类型复用
        template = None
        template_key = None
        if self.prompts:
            for key in ('system_message_template', 'system_message',
                        'entity_system_message', 'system_message'):
                if key in self.prompts:
                    template = self.prompts[key]
                    template_key = key
                    break
        if not template:
            return

        try:
            vars_ = self._get_system_message_vars(**kwargs)
            self.system_message = template.format(**vars_)
        except Exception as e:
            logging.warning(f"{self.__class__.__name__} {self.agent_id} 系统消息模板渲染失败：{e}")

    def _get_system_message_vars(self, **kwargs):
        """抽象钩子：提供系统消息模板变量。

        默认实现返回 {**self.profile, **kwargs}，并自动从 self.actions_config 注入
        action 变量（action_{key}_name / action_{key}_desc）和 available_actions_section。
        子类可重写以注入场景特有变量。

        Returns:
            dict: 模板变量字典
        """
        vars_ = {**self.profile, **kwargs}

        # —— 自动注入 actions_config 中的 action 变量 ——
        actions = self.actions_config.get('actions', {}) if self.actions_config else {}
        if actions:
            vars_['available_actions_section'] = self._build_available_actions_section(actions)
            for key, act in actions.items():
                if isinstance(act, dict):
                    vars_[f'action_{key}_name'] = act.get('name', '')
                    vars_[f'action_{key}_desc'] = act.get('description', '')
                    # 参数摘要：提取 parameters 列表中的 name 字段
                    params = act.get('parameters', [])
                    if isinstance(params, list) and params:
                        param_names = [p.get('name', '?') if isinstance(p, dict) else str(p) for p in params[:3]]
                        suffix = '...' if len(params) > 3 else ''
                        vars_[f'action_{key}_params_str'] = ', '.join(param_names) + suffix
                    else:
                        vars_[f'action_{key}_params_str'] = ''

        return vars_

    def _build_available_actions_section(self, actions: dict) -> str:
        """根据 actions_config['actions'] 构建"可用行动列表"文本块。

        对每个 action 生成一行摘要，包含 ID、名称、描述、参数。
        子类可重写以自定义格式。

        Args:
            actions: self.actions_config['actions'] 字典，key 为 action ID

        Returns:
            str: 格式化后的行动列表文本；若 actions 为空则返回空字符串
        """
        if not actions:
            return ""

        lines = ["当前可选行动："]
        # 按 key 排序确保稳定输出（key 可能是 int 或 str）
        try:
            sorted_keys = sorted(actions.keys(), key=lambda k: (isinstance(k, (int, float)), k))
        except TypeError:
            sorted_keys = list(actions.keys())

        for key in sorted_keys:
            act = actions[key]
            if not isinstance(act, dict):
                continue
            name = act.get('name', '')
            desc = act.get('description', '')
            # 参数摘要
            params = act.get('parameters', [])
            if isinstance(params, list) and params:
                param_names = [p.get('name', '?') if isinstance(p, dict) else str(p) for p in params[:3]]
                suffix = '...' if len(params) > 3 else ''
                params_str = f"（参数：{', '.join(param_names)}{suffix}）"
            else:
                params_str = ""
            lines.append(f"  [{key}] {name} - {desc}{params_str}")

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================== 通用信息接收 ====================

    async def receive_information(self, message_content):
        """通用信息接收骨架。

        从配置中读取 response_probability，决定是否回应。
        若回应，构建提示词并调用 LLM，将结果存入记忆。

        Args:
            message_content: 接收到的信息内容

        Returns:
            回应内容（如果有），否则返回 None。
        """
        response_prob = global_config.get("simulation", {}).get("response_probability", 0.5)
        if random.random() >= response_prob:
            return None

        # 构建提示词：子类通过 prompts['receive_information_prompt'] 提供模板
        template = self.prompts.get('receive_information_prompt') if self.prompts else None
        if template:
            try:
                prompt = template.format(message_content=message_content)
            except Exception:
                prompt = f"你收到了以下信息：{message_content}\n请给出你的回应。"
        else:
            prompt = f"你收到了以下信息：{message_content}\n请给出你的回应。"

        # 决策前钩子（更新系统消息等）
        await self._pre_llm_call_hook(message_content)

        response_content = await self.generate_llm_response(prompt)
        if not response_content or "None" in response_content:
            return None

        # 将回应存入记忆
        if self.memory:
            await self.memory.write_record(
                role_name=str(self.agent_id),
                content=f"对信息「{message_content}」的回应：{response_content}",
                is_user=False
            )

        return response_content

    # ==================== 通用知识记忆更新 ====================

    async def update_knowledge_memory(self, prompt_key: str = None, prompt: str = None):
        """通用知识记忆更新。

        根据提示词 key 读取模板，生成知识总结，并更新长期记忆。

        Args:
            prompt_key: prompts 字典中的模板 key
            prompt: prompt_key 的别名（向后兼容）
        """
        key = prompt_key or prompt
        if not key:
            return

        if not self.memory or not hasattr(self.memory, 'personal_memory'):
            return

        template = self.prompts.get(key) if self.prompts else None
        if not template:
            return

        try:
            prompt = template.format()
        except Exception as e:
            logging.warning(f"{self.__class__.__name__} {self.agent_id} 知识记忆模板渲染失败：{e}")
            return

        await self._pre_llm_call_hook(prompt_key=prompt_key)
        knowledge_summary = await self.generate_llm_response(prompt)

        if knowledge_summary:
            await self.memory.clear()
            self.memory.personal_memory.longterm_memory.append(knowledge_summary)
            self.memory.personal_memory.record_count = 0
            logging.info(f"{self.__class__.__name__} {self.agent_id} 更新了记忆：{knowledge_summary}")

    # ==================== 实体死亡处理钩子 ====================

    def _handle_entity_death(self):
        """抽象钩子：实体死亡处理。子类重写。"""
        logging.info(f"{self.__class__.__name__} {self.agent_id} 已死亡/移除。")
        return True