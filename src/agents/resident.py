from .shared_imports import *
from ..utils.logger import LogManager
import inspect
import importlib
load_dotenv()

class ResidentSharedInformationPool:
    def __init__(self):
        self.shared_info = {
            'economic_status': {},
            'social_network': {},
            'environment_awareness': {}
        }

    def add_shared_info(self, key, value, category):
        if category not in self.shared_info:
            self.shared_info[category] = {}
        self.shared_info[category][key] = value

    def get_shared_info(self, category=None):
        if category:
            return self.shared_info.get(category, {})
        return self.shared_info

class ResidentGroup(BaseAgent, IResidentGroup):
    """居民群组，用于管理同一城镇的居民"""
    def __init__(self, town_name):
        super().__init__(agent_id=f"group_{town_name}", group_type='resident_group', window_size=3)
        self._town_name = town_name
        self._residents = {}
        self._social_network = None

    @property
    def town_name(self):
        return self._town_name
    
    @property
    def residents(self):
        return self._residents
    
    @property
    def social_network(self):
        return self._social_network
    
    @social_network.setter
    def social_network(self, value):
        self._social_network = value

    def add_resident(self, resident):
        """添加居民到群组"""
        self._residents[resident.resident_id] = resident
        # 设置共享的 LLM 资源（如果群组有的话）
        if self.model_backend is not None:
            resident.model_backend = self.model_backend
        if self.token_counter is not None:
            resident.token_counter = self.token_counter
        if self.context_creator is not None:
            resident.context_creator = self.context_creator
        if self.model_type is not None:
            resident.model_type = self.model_type
        
        # 为每个居民创建独立的memory（但共享其他资源）
        if resident.memory is None and self.model_type is not None:
            resident.memory = MemoryManager(
                agent_id=resident.resident_id,
                model_type=self.model_type,
                group_type='resident',
                window_size=5
            )
            resident.memory.set_agent(resident)
        
        # 设置居民所属的群组
        resident.set_group(self)

    def set_social_network(self, social_network):
        """设置群组的社交网络"""
        self._social_network = social_network

    def remove_resident(self, resident_id):
        """从群组中移除居民"""
        if resident_id in self._residents:
            resident = self._residents[resident_id]
            resident.set_group(None)  # 清除居民的群组引用
            del self._residents[resident_id]

class Resident(BaseAgent, IResident):
    def __init__(self, agent_id, job_market=None, shared_pool=None, map=None, prompts=None, actions_config=None,
                 window_size=3, lightweight=False, influence_registry=None, profile_config=None, **kwargs):
        """初始化居民

        Args:
            agent_id: 居民 ID（与 BaseAgent 的 agent_id 对齐）
            job_market: 就业市场对象（可选）
            shared_pool: 共享信息池（可选）
            map: 地图对象（可选）
            prompts: 提示词配置字典（可选，与 BaseAgent 的 prompts 对齐）
            actions_config: 行动配置字典（可选）
            window_size: 记忆窗口大小
            lightweight: 如果为True，跳过BaseAgent的重量级初始化，稍后由ResidentGroup设置共享资源
            influence_registry: 影响函数注册表（可选）
            profile_config: 初始画像数据字典（可选，与 BaseAgent 的 profile_config 对齐）。
                            若提供，会直接写入 self.profile；
                            后续可通过 resident.income / resident.satisfaction 等 property 透明读写。
            **kwargs: 额外参数，兼容未来扩展
        """
        # 统一 prompts/actions_config 格式
        _prompts = prompts if isinstance(prompts, dict) else {}
        _actions = actions_config if isinstance(actions_config, dict) else {}

        if not lightweight:
            super().__init__(agent_id=agent_id, group_type='resident', window_size=window_size,
                             profile_config=profile_config, prompts=_prompts, actions_config=_actions)
        else:
            # 轻量级初始化：只设置agent_id，跳过重量级对象创建
            self.agent_id = agent_id
            self.system_message = None
            self.max_retry_attempts = 3
            self.retry_delay = 1.0
            # 这些将由ResidentGroup统一设置
            self.model_backend = None
            self.token_counter = None
            self.context_creator = None
            self.memory = None
            self.model_type = None
            # 轻量级路径也要初始化 profile 容器
            self.profile = profile_config if isinstance(profile_config, dict) else {}
            # 轻量级路径也要保留 prompts/actions_config
            self.prompts = _prompts
            self.actions_config = _actions

        self._resident_id = agent_id
        self.job_market = job_market
        self.shared_pool = shared_pool
        self.map = map
        self._location = None
        self._town = None  # 城镇属性
        self._employed = False  # 是否就业
        self._job = None  # 当前工作
        self.towns_manager = None  # Towns实例的引用
        self._group = None  # 所属群组的引用
        self._influence_registry = influence_registry

        # 向后兼容：prompts_resident 作为 prompts 的别名
        self.prompts_resident = self.prompts

        # 向后兼容：确保旧版代码依赖的常用属性存在于 profile 中
        # 否则 __getattr__ / __setattr__ 会抛 AttributeError
        _compat_defaults = {
            'satisfaction': 50,
            'income': 0,
            'health_index': 0,
            'lifespan': 0,
            'personality': '',
        }
        for key, default in _compat_defaults.items():
            if key not in self.profile:
                self.profile[key] = default

        self.resident_log = LogManager.get_logger("resident")

    @property
    def resident_id(self):
        return self._resident_id
    
    @resident_id.setter
    def resident_id(self, value):
        self._resident_id = value
    
    @property
    def location(self):
        return self._location
    
    @location.setter
    def location(self, value):
        self._location = value
    
    @property
    def town(self):
        return self._town
    
    @town.setter
    def town(self, value):
        self._town = value
    
    @property
    def employed(self):
        return self._employed
    
    @employed.setter
    def employed(self, value):
        self._employed = value
    
    @property
    def job(self):
        return self._job
    
    @job.setter
    def job(self, value):
        self._job = value
    
    @property
    def group(self):
        return self._group

    @group.setter
    def group(self, value):
        self._group = value

    def set_group(self, group):
        """设置居民所属的群组"""
        self._group = group

    def __setattr__(self, name: str, value):
        """当赋值的目标属性已存在于 profile 中时，自动写入 profile 而非创建新实例属性。"""
        if not name.startswith("_") and "profile" in self.__dict__:
            profile = self.__dict__["profile"]
            if isinstance(profile, dict) and name in profile:
                profile[name] = value
                return
        super().__setattr__(name, value)

    def __getattr__(self, name: str):
        """
        当访问的属性在类上不存在时，尝试从 profile 中读取。
        这使得新场景可以透明地通过 resident.cross_border_experience 访问动态画像字段。
        """
        # 避免递归和访问内部属性
        if name.startswith("_") or name in ("profile", "attr", "set_attr"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        # 如果 profile 已初始化且包含该字段，返回之
        profile = object.__getattribute__(self, "profile")
        if isinstance(profile, dict) and name in profile:
            return profile[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get_social_network(self):
        """通过群组获取社交网络"""
        return self.group.social_network if self.group else None

    def employ(self, job, salary=None):
        """
        居民就业
        :param job: 工作名称
        :param salary: 工作收入，如果未指定则使用职业默认收入
        """
        self.employed = True
        self.job = job
        
        # 如果指定了收入，使用指定的收入；否则从就业市场获取该职业的标准收入
        if salary is not None:
            self.income = salary
        elif self.job_market and job in self.job_market.jobs_info:
            self.income = self.job_market.jobs_info[job]["salary"]
        else:
            self.income = 0
        if self.job == "叛军":
            # self.satisfaction = max(0, self.satisfaction - 50)  # 叛军降低满意度
            self.resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 加入了叛军。")
        else:
            self.resident_log.info(f"居民 {self.resident_id} 在城镇 {self.town} 找到了工作：{job}，收入：{self.income}。")
    
    def unemploy(self):
        """
        居民失业
        """
        self.employed = False
        self.job = None
        self.income = 0
        self.resident_log.info(f"居民 {self.resident_id} 目前无业")

    # 从 profile 中排除的元数据键（不应出现在画像文档中）
    _META_PROFILE_KEYS = {"role", "description", "expansion"}

    def _get_system_message_vars(self, **kwargs):
        """重写钩子：提供居民系统消息模板变量。

        同时提供：
        1. 按 role 动态生成的身份描述（identity）
        2. 旧版模板直接使用的独立计算变量（economic_status_description 等）
        3. 动态画像变量文档（profile_vars_doc）供新版模板使用
        4. 原始属性值向后兼容
        """
        work_condition = self.job if self.employed else "无业游民"
        prompts = getattr(self, 'prompts_resident', getattr(self, 'prompts', {}))

        # ---- 按 role 动态生成身份描述 ----
        role = self.profile.get('role', 'consumer')
        if role == 'enterprise':
            identity = "代表性企业，覆盖制造业和服务业"
        elif role == 'government':
            identity = "中央政府决策者"
        else:
            identity = "代表性消费者和家庭成员"

        # ---- 健康状况 ----
        health_idx = self.profile.get('health_index', 0)
        health_conditions = prompts.get('health_conditions', []) if prompts else []
        health_condition = ""
        if isinstance(health_idx, int) and 0 <= health_idx < len(health_conditions) and health_conditions[health_idx]:
            health_condition = health_conditions[health_idx]

        # ---- 满意度描述 ----
        satisfaction = self.profile.get('satisfaction', 0)
        satisfaction_levels = prompts.get('satisfaction_levels', []) if prompts else []
        sat_idx = min(int(satisfaction // 20), len(satisfaction_levels) - 1) if satisfaction_levels else 0
        satisfaction_description = satisfaction_levels[sat_idx] if satisfaction_levels else ""

        # ---- 经济状况描述 ----
        economic_status_description = self._eval_economic_status_rules(
            prompts, kwargs
        )

        # 动态画像变量文档（供新版模板使用）
        profile_vars_doc = self._build_profile_vars_doc(**kwargs)

        # 向后兼容：继续提供旧版模板变量（若属性缺失则给默认值）
        # 过滤掉元数据字段，避免旧模板意外引用
        income = self.profile.get('income', 0)
        legacy_vars = {
            'personality': self.profile.get('personality', ''),
            'income': income,
            'satisfaction': satisfaction,
            'health_index': health_idx,
            'lifespan': self.profile.get('lifespan', 0),
        }

        return {
            **legacy_vars,
            **self.profile,
            'identity': identity,
            'work_condition': work_condition,
            'economic_status_description': economic_status_description,
            'health_condition': health_condition,
            'satisfaction_description': satisfaction_description,
            'profile_vars_doc': profile_vars_doc,
            **kwargs
        }

    def _eval_economic_status_rules(self, prompts: dict, kwargs: dict) -> str:
        """根据 prompts 中的 economic_status_rules 计算经济状况描述。

        规则格式（来自 agent_profile.yaml 的 computed_descriptions）：
        economic_status_rules:
          - condition: "income <= 0"
            description: "家破人亡难以为继"
          - condition: "income < basic_living_cost"
            description: "勉强糊口"
          - fallback: "生活富裕丰衣足食"
        """
        rules = prompts.get("economic_status_rules", []) if prompts else []
        if not rules:
            # 无配置时兜底：沿用旧版绝对值逻辑
            income = self.profile.get('income', 0)
            if income <= 0:
                return "家破人亡难以为继"
            elif income < 8:
                return "勉强糊口"
            elif income < 15:
                return "生活尚算安稳"
            else:
                return "生活富裕丰衣足食"

        basic_living_cost = kwargs.get('basic_living_cost', 0)
        tax_rate = kwargs.get('tax_rate', 0)
        income = self.profile.get('income', 0)

        # 构建安全求值上下文
        safe_ctx = {"__builtins__": {}}
        safe_ctx.update(self.profile)
        safe_ctx["income"] = income
        safe_ctx["basic_living_cost"] = basic_living_cost
        safe_ctx["tax_rate"] = tax_rate

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            condition = rule.get("condition")
            if condition is None:
                continue
            try:
                if eval(str(condition), safe_ctx, {}):
                    return str(rule.get("description", ""))
            except Exception:
                continue

        # 无匹配条件时，检查 fallback
        for rule in rules:
            if isinstance(rule, dict) and "fallback" in rule:
                return str(rule["fallback"])

        return ""

    async def receive_information(self, message_content):
        """
        接收信息（如政府政策、叛乱信息）
        """
        # 从配置中获取回应概率
        response_prob = global_config.get("simulation", {}).get("response_probability")
        if random.random() < response_prob:
            # 构建回应提示词
            prompt = self.prompts_resident['receive_information_prompt'].format(message_content=message_content)

            self.update_system_message()
            response_content = await self.generate_llm_response(prompt)
            
            if response_content and "None" not in response_content:
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                self.resident_log.info(f"居民 {self.resident_id} 对收到的信息「{message_content}」做出回应：{response_content}")
                
                # 将自己的回应存入记忆
                await self.memory.write_record(
                    role_name=self.resident_id,
                    content=f"对信息「{message_content}」的回应：{response_content}",
                    is_user=False
                )
                
                return response_content, selected_type

        return None

    # ==================== 决策框架钩子实现 ====================

    async def _build_decision_prompt(self, context, **kwargs):
        """重写钩子：构建居民决策提示词。"""
        # 从 context/kwargs 中提取参数
        if isinstance(context, dict):
            tax_rate = context.get('tax_rate', 0)
            basic_living_cost = context.get('basic_living_cost', 0)
            climate_impact = context.get('climate_impact', 0)
            additional_context_dict = context.get('additional_context', {})
        else:
            tax_rate = kwargs.get('tax_rate', 0)
            basic_living_cost = kwargs.get('basic_living_cost', 0)
            climate_impact = kwargs.get('climate_impact', 0)
            additional_context_dict = kwargs.get('additional_context', {})
        if not isinstance(additional_context_dict, dict):
            additional_context_dict = {}

        # 发言概率基于节点在社交网络中的度值
        speech_prob = 0.0
        social_network = self.get_social_network()
        if social_network:
            speech_prob = social_network.calculate_speech_probability(self.resident_id)
        need_speech = random.random() < speech_prob

        # 如果是未就业居民，获取当前城镇的空缺岗位信息
        job_market_info = ""
        if not self.employed and self.town and self.job_market:
            vacant_jobs = self.job_market.get_vacant_jobs()
            if vacant_jobs:
                job_market_info = "以下是当前可用工作岗位：\n" + "\n".join(
                    f"- {job}: {count}个空缺, 基础收入：{self.job_market.jobs_info[job]['base_salary']}"
                    for job, count in vacant_jobs.items()
                )

        # 构建税率和天气状况信息
        tax_rate_message = ""
        if tax_rate < 0.05:
            tax_rate_message = "当前税率极低，几乎无税负担。\n"
        elif tax_rate < 0.2:
            tax_rate_message = "当前税率适中，负担一般。\n"
        elif tax_rate < 0.3:
            tax_rate_message = "当前税率较高，负担较重。\n"
        else:
            tax_rate_message = "当前税率极高，负担极重。\n"

        weather_condition = ""
        if climate_impact <= 0.2:
            weather_condition = "天气良好，适宜农耕。"
        elif climate_impact <= 0.4:
            weather_condition = "天气一般，对农耕有轻微影响。"
        elif climate_impact <= 0.6:
            weather_condition = "天气较差，农耕受到明显影响。"
        elif climate_impact <= 0.8:
            weather_condition = "天气恶劣，农耕困难。"
        else:
            weather_condition = "天气极端恶劣，农耕几乎无法进行。"

        # 构建用于 prompt 模板 format 的参数
        format_kwargs = {
            'tax_rate_message': tax_rate_message,
            'job_market_info': job_market_info,
            'weather_condition': weather_condition,
        }
        format_kwargs.update(additional_context_dict)
        format_kwargs.update({k: v for k, v in kwargs.items() if k not in ('tax_rate', 'basic_living_cost', 'climate_impact', 'additional_context')})

        # ★ 硬性注入：把 profile 中所有字段自动暴露给 prompt 模板
        # 这样模板可以直接用 {expected_demand}、{inventory_level} 等任意画像属性
        if isinstance(self.profile, dict):
            for key, value in self.profile.items():
                if key not in format_kwargs:
                    format_kwargs[key] = value

        # 从 BaseAgent 继承 action 变量注入（action_N_name/desc/params_str + available_actions_section）
        base_vars = super()._get_system_message_vars(**kwargs)
        format_kwargs.update(base_vars)

        employed = self.employed

        # 安全 format：缺键时不抛 KeyError，而是填充占位提示，便于排查
        class _SafeDict(dict):
            def __missing__(self, key):
                return f"[未提供:{key}]"

        safe_kwargs = _SafeDict(format_kwargs)

        # ★ 统一模板 key：优先使用 decision_prompt，回退到旧版 key
        prompts = self.prompts_resident
        decision_template = prompts.get('decision_prompt')
        if not decision_template:
            # 回退到旧版模板（向后兼容）
            if self.job == "城市居民":
                decision_template = prompts.get('decide_action_prompt_city_resident', '')
            elif employed:
                decision_template = prompts.get('decide_action_prompt_employed', '')
            else:
                decision_template = prompts.get('decide_action_prompt_unemployed', '')
        prompt = decision_template.format_map(safe_kwargs)

        # 追加 JSON 格式模板（统一 key decision_json，回退旧版 decide_action_json）
        json_template = prompts.get('decision_json') or prompts.get('decide_action_json', '')
        if json_template:
            json_safe = _SafeDict({
                'speech': ', "speech": 一句有传播力的态度言论，允许负面、质疑或愤怒情绪。}' if need_speech else '}',
                'desired_job_and_min_salary': ', "desired_job": 期望职业（如果选择2，可选：农民、商人、官员及士兵、运河维护工、普通工作者）, "min_salary": 可接受的最低收入（数字）' if not self.employed and job_market_info else '',
            })
            prompt += "\n" + json_template.format_map(json_safe)

        # 将 need_speech 和 job_market_info 存入内部状态，供 _parse_decision_response 使用
        self._last_decision_meta = {
            'need_speech': need_speech,
            'job_market_info': job_market_info,
        }

        return prompt

    async def _parse_decision_response(self, response, context, **kwargs):
        """重写钩子：解析 LLM 决策响应。"""
        if not response:
            return "3", "发生错误，继续当前工作"

        cleaned_response = re.sub(r"^```json\s*|\s*```$", "", response, flags=re.DOTALL).strip()
        cleaned_response = re.sub(r'\s+', '', cleaned_response, flags=re.DOTALL)
        cleaned_response = re.sub(r'}(?=.*})', '', cleaned_response, flags=re.DOTALL)

        def merge_json(text):
            matches = re.findall(r'\{[^{}]*\}', text)
            if not matches:
                return None
            result = {}
            for m in matches:
                try:
                    obj = json.loads(m)
                    result.update(obj)
                except Exception:
                    continue
            return result if result else None

        decision_data = None
        try:
            decision_data = json.loads(cleaned_response)
        except Exception:
            decision_data = merge_json(cleaned_response)

        if not decision_data:
            return "3", "发生错误，继续当前工作"

        select = decision_data.get("select")
        reason = decision_data.get("reason", "")
        speech = decision_data.get("speech", "")
        desired_job = decision_data.get("desired_job")
        min_salary = decision_data.get("min_salary")
        quantity = decision_data.get("quantity", 0)
        price = decision_data.get("price", 0)

        # 将交易细节等附加决策字段存入 meta，供 simulator/execute_action 读取
        meta = getattr(self, '_last_decision_meta', {})
        meta['quantity'] = quantity
        meta['price'] = price
        self._last_decision_meta = meta

        # ★ 通用化：自动应用所有 *_change 字段到对应 profile 属性
        for key, value in decision_data.items():
            if not key.endswith('_change'):
                continue
            if not isinstance(value, (int, float)):
                continue
            attr_name = key[:-7]  # 去掉 _change
            current = self.attr(attr_name, 0)
            new_val = current + value
            # 通用边界（可扩展为从 actions.yaml 读取边界）
            if attr_name in ('consumer_confidence_index', 'policy_space_fiscal',
                             'policy_space_monetary', 'satisfaction'):
                new_val = max(0, min(100, new_val))
            elif attr_name == 'employment':
                new_val = max(0, new_val)
            self.set_attr(attr_name, new_val)

        # 日志：记录主要变化
        changes = [f"{k}: {v}" for k, v in decision_data.items() if k.endswith('_change')]
        self.resident_log.info(
            f"居民 {self.resident_id} 的思考：{reason}, 选择：{select}"
            + (f", 变化：{'; '.join(changes)}" if changes else "")
        )

        # 保留求职逻辑（向后兼容）
        meta = getattr(self, '_last_decision_meta', {})
        if desired_job is not None or min_salary is not None:
            print(f"[求职] 居民 {self.resident_id} 期望职业：{desired_job}, 最低收入：{min_salary}, 所在城镇：{self.town}")
            return {
                "town": self.town,
                "desired_job": desired_job,
                "min_salary": min_salary,
                "resident_id": self.resident_id,
                "resident": self
            }
        elif speech and meta.get('need_speech'):
            relation_types = ["friend", "colleague", "family", "hometown"]
            selected_type = random.choice(relation_types)
            return select, reason, speech, selected_type
        else:
            return select, reason

    async def decide_action_by_llm(self, tax_rate=0, basic_living_cost=0, climate_impact=0, **kwargs):
        """
        通过LLM决定居民的行动（向后兼容包装器）。
        内部调用通用决策入口 decide_action()。
        """
        context = {
            'tax_rate': tax_rate,
            'basic_living_cost': basic_living_cost,
            'climate_impact': climate_impact,
        }
        # 将 additional_context 和其余 kwargs 也并入 context
        if 'additional_context' in kwargs:
            context['additional_context'] = kwargs.pop('additional_context')
        context.update(kwargs)

        # decide_action 会自动调用 _build_decision_prompt、generate_llm_response、_parse_decision_response
        # _pre_llm_call_hook 会自动调用 update_system_message
        return await self.decide_action(context=context, **kwargs)

    async def execute_decision(self, select, *args, **kwargs):
        """
        根据配置动态执行居民的决策（向后兼容包装器）。
        内部调用通用行为执行入口 execute_action()。
        """
        return await self.execute_action(select, *args, **kwargs)

    async def execute_action(self, select, *args, **kwargs):
        """配置驱动的行为执行。

        优先读取 actions.yaml 中的 effects 配置自动执行，
        如果没有 effects 则回退到父类的 function 调用逻辑。
        新项目只需要写 YAML，不需要写 Python handle_xxx 方法。
        """
        actions = self.actions_config.get('actions', {}) if self.actions_config else {}
        action = actions.get(select) or actions.get(str(select)) or (
            actions.get(int(select)) if str(select).isdigit() else None
        )
        if not action:
            self.resident_log.warning(f"未找到行动配置: select={select}")
            return False

        # ★ 优先使用配置化的 effects（新机制：零代码行为定义）
        effects = action.get('effects')
        if effects:
            return self._apply_effects(effects, action_name=action.get('name', select))

        # 回退到旧机制：通过 function 字段调用方法（向后兼容）
        return await super().execute_action(select, *args, **kwargs)

    def _apply_effects(self, effects, action_name=""):
        """应用 effects 配置到 profile 属性。"""
        import random
        applied = []
        for effect in effects:
            attr = effect.get('target_attr')
            if not attr:
                continue

            current = self.attr(attr, 0)
            new_val = current

            # 效果计算
            if 'multiplier' in effect:
                new_val = current * effect['multiplier']
            elif 'multiplier_range' in effect:
                lo, hi = effect['multiplier_range']
                new_val = current * random.uniform(lo, hi)
            elif 'add' in effect:
                new_val = current + effect['add']
            elif 'add_range' in effect:
                lo, hi = effect['add_range']
                new_val = current + random.uniform(lo, hi)
            elif 'set' in effect:
                new_val = effect['set']

            # 边界约束
            if 'min' in effect:
                new_val = max(new_val, effect['min'])
            if 'max' in effect:
                new_val = min(new_val, effect['max'])

            self.set_attr(attr, new_val)
            applied.append(f"{attr}: {current:.2f} → {new_val:.2f}")

        if applied:
            self.resident_log.info(
                f"居民 {self.resident_id} 执行 {action_name}: " + "; ".join(applied)
            )
        return True

    def handle_work(self, desired_job=None, min_salary=None):
        """
        处理居民寻找工作或继续工作的逻辑
        """
        if self.job_market and self.employed:
            self.resident_log.info(f"居民 {self.resident_id} 已有工作：{self.job}，继续目前工作")
            return True
        elif desired_job and min_salary:
            # 返回求职信息
            return {
                "town": self.town, 
                "desired_job": desired_job, 
                "min_salary": min_salary,
                "resident_id": self.resident_id 
            }
        return True

    async def generate_provocative_opinion(self, probability, speech):
        """
        处理居民是叛军时的特殊逻辑，生成煽动性言论
        :param probability: 发言概率
        :return: 生成的言论
        """
        # 根据概率决定是否发表煽动性言论
        if random.random() < probability:
            if speech:
                opinion = speech
            else:
                # 构建煽动性提示信息
                prompt = self.prompts_resident['generate_provocative_opinion_prompt']
                
                self.update_system_message()
                opinion = await self.generate_llm_response(prompt)

            if opinion:
                self.resident_log.info(f"叛军 {self.agent_id} 发表煽动性言论：{opinion}")
                # 随机选择一种关系类型
                relation_types = ["friend", "colleague", "family", "hometown"]
                selected_type = random.choice(relation_types)
                return opinion,selected_type
        return "未发表煽动性言论"

    async def receive_and_decide_response(self, message: dict, year):
        """
        接收公共知识通知，由LLM决定是否发言
        """
        content = message.get("content")
        public_notice = message.get("public_notice")
        if content:
            message_content = f"你收到了政府发布的详细信息：[{content}]" 
        else:
            message_content = "你没有收到政府信息。" 
        
        # 构建提示词
        if year == 0:
            # await self.memory.write_record(
            #         role_name="居民",
            #         content=message_content,
            #         is_user=False,
            #         store_in_shared=False,
            #         )
            prompt = self.prompts_resident['receive_and_decide_response_prompt'].format(
                public_notice=public_notice,
                message_content=message_content
            )
        else:
            prompt = self.prompts_resident['receive_and_decide_response_prompt'].format(
                public_notice="",
                message_content=""
            )
        try:
            self.update_system_message()
            response = await self.generate_llm_response(prompt)
            import json
            if response:
                try:
                    response_json = json.loads(response)
                    select_choice = response_json.get("select")
                    select_reason = response_json.get("reason")
                    speech_content = response_json.get("speech", "")
                    self.resident_log.info(f"居民 {self.resident_id} 选择：{select_choice}, 原因：{select_reason}")
                    if year == 0:
                        await self.memory.write_record(
                            role_name="居民",
                            content=message_content + public_notice,
                            is_user=False,
                            store_in_shared=False,
                        )
                    if select_choice == 2 and speech_content:
                        await self.memory.write_record(
                            role_name="居民",
                            content=f"我发表言论：{speech_content}",
                            is_user=False,
                            store_in_shared=False
                        )
                        self.resident_log.info(f"居民 {self.resident_id}发起讨论: {speech_content}")
                        # 返回带有发言的决策结果
                        relation_types = ["friend", "colleague", "family", "hometown"]
                        # 随机选择一种关系类型
                        selected_type = random.choice(relation_types)
                        return speech_content, selected_type
                    else:
                        await self.memory.write_record(
                            role_name="居民",
                            content=f"我保持沉默",
                            is_user=False,
                            store_in_shared=False
                        )
                        self.resident_log.info(f"居民 {self.resident_id} 选择沉默")
                        return None
                except json.JSONDecodeError:
                    self.resident_log.error(f"居民 {self.resident_id} 解析LLM响应失败: {response}")
                    return None
            else:
                await self.memory.write_record(
                    role_name="居民",
                    content=f"我保持沉默",
                    is_user=False,
                    store_in_shared=False
                )
                self.resident_log.info(f"居民 {self.resident_id} 选择沉默")
                return None
            
        except Exception as e:
            self.resident_log.error(f"居民 {self.resident_id} 处理公共知识出错: {e}")
            return None

    async def make_survey_request(self, prompt: str):
        """通用方法：构建提示词，获取LLM响应并进行初步清理"""
        try:
            # 更新系统消息以确保最新状态
            self.update_system_message()
            
            # 获取LLM响应
            response = await self.generate_llm_response(prompt)
            if not response:
                return None
                
            # 清理LLM返回的字符串
            cleaned_response = response.strip()
            
            # 记录问卷结果
            self.resident_log.info(f"居民 {self.resident_id} 回应: {cleaned_response}")
            
            # 返回选择结果
            return cleaned_response
            
        except Exception as e:
            self.resident_log.error(f"居民 {self.resident_id} 进行信息请求出错: {e}")
            return None

    def print_resident_status(self):
        """
        打印居民状态（用于调试）。
        仅打印 profile 中实际存在的属性，不再强制输出固定字段。
        """
        self.resident_log.info(f"居民 {self.resident_id} 在 {self.town} 的 {self.location} 的状态：")
        self.resident_log.info(f"  是否就业：{self.employed}")
        self.resident_log.info(f"  工作：{self.job}")

        # 动态打印 profile 中存在的属性，避免强制访问可能不存在的字段
        if isinstance(self.profile, dict):
            for key in sorted(self.profile.keys()):
                if key.startswith("_"):
                    continue
                value = self.profile[key]
                self.resident_log.info(f"  {key}：{value}")
        else:
            self.resident_log.info("  （无画像数据）")

    def handle_death(self):
        """
        处理居民死亡的逻辑
        """
        # 从就业市场和城镇中移除
        if self.town and self.towns_manager:
            self.towns_manager.remove_resident_in_town(self.resident_id, self.town, self.job)
            self.employed = False
            self.job = None

        # 从社交网络中移除（如果存在）
        social_network = self.get_social_network()
        if social_network:
            # 从异质图中移除
            social_network.hetero_graph.remove_node(self.resident_id)
            # 从超图中移除
            social_network.hyper_graph.remove_node(self.resident_id)

        self.resident_log.info(f"居民 {self.resident_id} 已死亡。")
        return True

    def get_random_direction_town(self, map):
        """随机选择一个相邻城市进行迁移"""
        try:
            current_town_name = self.town
            
            if not current_town_name:
                self.resident_log.info(f"居民 {self.resident_id} 无法找到当前位置对应的城市")
                return None

            # 获取相连的城市
            connected_towns = map.get_connected_towns(current_town_name)
            if not connected_towns:
                self.resident_log.info(f"城市 {current_town_name} 没有相连的城市")
                return None

            # 随机选择一个相连的城市
            next_town = random.choice(connected_towns)
            return next_town
            
        except Exception as e:
            self.resident_log.error(f"选择迁移目标城市时出错: {e}")
            return None

    async def migrate_to_new_town(self, map, update_job=True):
        """
        迁移到新城镇
        
        Args:
            map: 地图对象
            update_job: 是否更新职业，如果为False则保留原职业
        """
        # 获取目标城市
        target_town = self.get_random_direction_town(map)
        if not target_town:
            self.resident_log.info(f"居民 {self.resident_id} 未找到合适的迁移目标城市")
            return False

        # 生成新位置
        new_location = map.generate_random_location(target_town)

        # 保存旧城镇信息
        old_town = self.town
        old_job = self.job

        # 从原城镇中移除居民
        if self.towns_manager and old_town:
            self.towns_manager.remove_resident_in_town(self.resident_id, old_town, old_job)

        # 更新居民信息
        self.location = new_location
        self.town = target_town
        
        # 根据update_job参数决定是否清除职业信息
        if update_job:
            self.unemploy()
        
        # 将居民添加到新城镇
        if self.towns_manager:
            self.towns_manager.add_resident(self, target_town)
            # 如果不更新职业，则重新分配原来的工作
            if not update_job and old_job:
                self.job_market.assign_specific_job_withoutcheck(self, old_job)

        # 更新超图
        social_network = self.get_social_network()
        if social_network:
            if old_town:
                old_group_id = f"hometown_{old_town}"
                social_network.hyper_graph.remove_hyperedge_node(old_group_id, self.resident_id)
            if target_town:
                new_group_id = f"hometown_{target_town}"
                social_network.hyper_graph.add_hyperedge(new_group_id, [self.resident_id])

        self.resident_log.info(f"居民 {self.resident_id} 从 {old_town} 迁移到了 {target_town}")
        return True

    def set_town(self, town_name, towns_manager):
        """
        设置居民所在的城镇和towns_manager
        """
        self.town = town_name
        self.towns_manager = towns_manager
        if self.towns_manager and self.town:
            self.job_market = self.towns_manager.get_town_job_market(self.town)

    async def reset_experimental_state(self):
        """
        重置居民实验状态，主要用于删除记忆
        """
        if self.memory:
            await self.memory.clear()  # 清除所有记忆

    def apply_influences(self, target_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        应用所有注册的影响函数到指定目标
        
        :param target_name: 目标名称（如 'health_index', 'satisfaction'）
        :param context: 上下文字典，包含影响函数所需的所有数据
        """
        if self._influence_registry is None:
            return
        
        # 如果没有提供上下文，创建默认上下文
        if context is None:
            context = {}
        
        # 确保上下文中包含 resident 对象本身
        context['resident'] = self
        
        # 获取所有影响该目标的影响函数
        influences = self._influence_registry.get_influences(target_name)
        
        # 应用每个影响函数
        for influence in influences:
            try:
                impact = influence.apply(self, context)
                if impact is not None:
                    # 可以记录影响或采取其他行动
                    pass
            except Exception as e:
                self.resident_log.error(f"应用影响函数失败 ({influence.source}->{target_name}:{influence.name}): {e}")
