"""
机制解释与调整Agent
作为用户和系统之间的中介，帮助非技术用户理解和调整模拟机制
"""
from src.utils.custom_logger import CustomLogger
from .shared_imports import *


class MechanismInterpreterAgent(BaseAgent):
    """
    机制解释与调整Agent
    
    功能:
    1. 读取并解释当前的模拟机制（配置文件、代码逻辑）
    2. 用通俗易懂的语言向用户解释机制
    3. 以对话方式回答用户的各种问题
    4. 接收用户的自然语言调整指令
    5. 将用户指令转换为系统配置修改
    """
    
    def __init__(self, agent_id, config_dir, simulator_path=None, main_path=None):
        """
        初始化机制解释Agent
        
        Args:
            agent_id: Agent唯一标识
            config_dir: 配置文件目录
            simulator_path: simulator文件路径（可选）
            main_path: main文件路径（可选）
        """
        super().__init__(agent_id, group_type='mechanism_interpreter', window_size=10)
        self.config_dir = config_dir
        self.simulator_path = simulator_path
        self.main_path = main_path
        self.logger = CustomLogger('mechanism_interpreter').logger
        
        # 加载提示词配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'mechanism_interpreter_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']
        
        # 缓存已读取的文件内容
        self.cached_configs = {}
        
        # 加载文件目录描述（字符串格式）
        self.file_catalog = self._load_file_catalog()
    
    def _load_file_catalog(self):
        """加载文件目录描述"""
        catalog_path = os.path.join(os.path.dirname(self.config_dir), 'template', 'file_descriptions.yaml')
        self.logger.info(f"加载文件目录: {catalog_path}")
        
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                # 构建格式化的字符串
                catalog_text = "=== 可用的文件资源 ===\n\n"
                
                if 'config_files_description' in data:
                    catalog_text += "**配置文件**\n"
                    for filename, desc in data['config_files_description'].items():
                        catalog_text += f"- {filename}: {desc}\n"
                    catalog_text += "\n"
                
                if 'prompt_files_description' in data:
                    catalog_text += "**提示词文件**\n"
                    for filename, desc in data['prompt_files_description'].items():
                        catalog_text += f"- {filename}: {desc}\n"
                    catalog_text += "\n"
                
                if 'documentation_files_description' in data:
                    catalog_text += "**说明文档**\n"
                    for filename, desc in data['documentation_files_description'].items():
                        catalog_text += f"- {filename}: {desc}\n"
                    catalog_text += "\n"
                
                if 'api_docs_description' in data:
                    catalog_text += "**API文档 (模块功能说明)**\n"
                    for filename, desc in data['api_docs_description'].items():
                        catalog_text += f"- {filename}: {desc}\n"
                    catalog_text += "\n"
                
                return catalog_text
                
            except Exception as e:
                self.logger.error(f"加载文件目录失败: {e}")
        
        return "=== 可用的文件资源 ===\n\n(未找到文件目录配置)"
    
    def _read_all_configs(self):
        """读取配置目录下的所有配置文件"""
        configs = {}
        
        if not os.path.exists(self.config_dir):
            self.logger.warning(f"配置目录不存在: {self.config_dir}")
            return configs
        
        # 支持的配置文件类型
        config_files = [
            'description.md',
            'simulation_config.yaml',
            'jobs_config.yaml',
            'resident_actions.yaml',
            'towns_data.json',
            'government_prompts.yaml',
            'rebels_prompts.yaml',
            'residents_prompts.yaml',
            'message_config.yaml',
            'questionnaire.yaml',
            'modules_config.yaml'
        ]
        
        for filename in config_files:
            filepath = os.path.join(self.config_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        configs[filename] = content
                        self.logger.info(f"读取配置文件: {filename}")
                except Exception as e:
                    self.logger.error(f"读取文件失败 {filename}: {e}")
        
        self.cached_configs = configs
        return configs
    
    def _read_code_logic(self):
        """读取代码逻辑（simulator和main文件的完整内容）"""
        code_info = {}
        
        # 读取完整的simulator文件
        if self.simulator_path and os.path.exists(self.simulator_path):
            try:
                with open(self.simulator_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    code_info['simulator'] = content
                    code_info['simulator_path'] = self.simulator_path
                    self.logger.info(f"读取完整simulator代码: {self.simulator_path}")
            except Exception as e:
                self.logger.error(f"读取simulator失败: {e}")
        
        # 读取完整的main文件
        if self.main_path and os.path.exists(self.main_path):
            try:
                with open(self.main_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    code_info['main'] = content
                    code_info['main_path'] = self.main_path
                    self.logger.info(f"读取完整main代码: {self.main_path}")
            except Exception as e:
                self.logger.error(f"读取main失败: {e}")
        
        return code_info
    
    def _extract_key_functions(self, code_content):
        """提取代码中的关键函数信息（简化版）"""
        import re
        
        # 提取类定义和主要方法
        class_pattern = r'class\s+(\w+).*?:'
        method_pattern = r'def\s+(\w+)\s*\([^)]*\):'
        docstring_pattern = r'"""(.*?)"""'
        
        classes = re.findall(class_pattern, code_content)
        methods = re.findall(method_pattern, code_content)
        docstrings = re.findall(docstring_pattern, code_content, re.DOTALL)
        
        return {
            'classes': classes,
            'methods': methods[:10],  # 只保留前10个方法
            'docstrings': [d.strip()[:200] for d in docstrings[:5]]  # 只保留前5个文档字符串的前200字符
        }
    
    def _read_specific_files(self, file_list):
        """
        按需读取特定的配置文件
        
        Args:
            file_list: 需要读取的文件名列表
        
        Returns:
            dict: 文件名 -> 文件内容的字典
        """
        configs = {}
        
        for filename in file_list:
            # 先检查缓存
            if filename in self.cached_configs:
                configs[filename] = self.cached_configs[filename]
                continue
            
            # 在配置目录中查找
            filepath = os.path.join(self.config_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        configs[filename] = content
                        self.cached_configs[filename] = content
                        self.logger.info(f"读取文件: {filename}")
                except Exception as e:
                    self.logger.error(f"读取文件失败 {filename}: {e}")
            else:
                # 尝试在docs/api目录中查找API文档
                api_path = os.path.join(os.path.dirname(self.config_dir), 'docs', 'api', filename)
                if os.path.exists(api_path):
                    try:
                        with open(api_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            configs[filename] = content
                            self.cached_configs[filename] = content
                            self.logger.info(f"读取API文档: {filename}")
                    except Exception as e:
                        self.logger.error(f"读取API文档失败 {filename}: {e}")
        
        return configs
    
    def _build_context(self, configs, code_info):
        """
        构建上下文信息，用于LLM理解系统
        
        Args:
            configs: 配置文件字典
            code_info: 代码信息字典
        
        Returns:
            str: 格式化的上下文信息
        """
        context = "=== 当前模拟的配置文件 ===\n\n"
        
        # 优先展示description.md
        if 'description.md' in configs:
            desc_content = configs['description.md']
            context += f"【模拟说明】\n{desc_content[:2000]}\n\n"
        
        # 展示主要配置的摘要
        key_configs = ['simulation_config.yaml', 'modules_config.yaml']
        for config_name in key_configs:
            if config_name in configs:
                context += f"【{config_name}】\n{configs[config_name][:1000]}\n\n"
        
        # 如果有代码信息，提取关键部分展示
        if code_info:
            context += "=== 代码逻辑概览 ===\n"
            if 'simulator' in code_info:
                simulator_content = code_info['simulator']
                # 只展示前2000字符作为概览
                context += f"【Simulator代码片段】\n{simulator_content[:2000]}...\n\n"
            if 'main' in code_info:
                main_content = code_info['main']
                # 只展示前1000字符作为概览
                context += f"【Main代码片段】\n{main_content[:1000]}...\n\n"
        
        return context
    
    async def explain_mechanism(self):
        """
        解释当前的模拟机制
        
        Returns:
            str: 通俗易懂的机制解释
        """
        self.logger.info("开始解释模拟机制")
        
        # 读取所有配置文件
        configs = self._read_all_configs()
        
        if not configs:
            return "未找到任何配置文件，无法解释机制。"
        
        # 读取代码逻辑（如果有）
        code_info = self._read_code_logic()
        
        # 构建上下文
        context = self._build_context(configs, code_info)
        
        # 构建提示词
        prompt = self.prompts['explain_mechanism_prompt'].format(
            context=context
        )
        
        # 调用LLM生成解释
        self.logger.info("调用LLM生成机制解释")
        explanation = await self.generate_llm_response(prompt)
        await self.memory.write_record(
            role_name="机制解释对话agent",
            content=f"机制解释：{explanation}",
            is_user=False,
            store_in_shared=False  # 不存入共享记忆
            )
        return explanation
    
    async def recognize_intent(self, user_input):
        """
        识别用户意图并确定需要的文件
        
        Args:
            user_input: 用户输入的内容
        
        Returns:
            dict: 包含意图类型的字典
                - intent='adjustment': 包含description字段(转换后的需求描述)
                - intent='question': 包含required_files字段(需要的文件列表)
                - 其他intent: 只包含intent字段
        """

        self.logger.info(f"识别用户意图: {user_input}")
        
        # 构建提示词（直接使用字符串格式的file_catalog）
        prompt = self.prompts['intent_recognition_prompt'].format(
            user_input=user_input,
            file_catalog=self.file_catalog
        )
        
        # 调用LLM识别意图
        self.logger.info("调用LLM识别用户意图")
        response = await self.generate_llm_response(prompt)
        
        # 解析JSON响应
        try:
            # 移除可能的Markdown代码块标记
            response = response.strip()
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
                if response.startswith('json'):
                    response = response[4:].strip()
            
            intent_result = json.loads(response)
            
            # 验证必需字段
            if 'intent' not in intent_result:
                self.logger.error("意图识别结果缺少intent字段")
                return None
            
            return intent_result
            
        except Exception as e:
            self.logger.error(f"解析意图识别结果JSON失败: {e}, 响应: {response[:200]}")
            return None
    
    async def answer_question(self, user_question, required_files=None):
        """
        回答用户关于模拟机制的问题
        
        Args:
            user_question: 用户的问题
            required_files: 需要读取的文件列表（可选）
        
        Returns:
            str: 问题的答案
        """
        self.logger.info(f"回答用户问题: {user_question}")
        
        # 按需读取文件
        if required_files:
            configs = self._read_specific_files(required_files)
            self.logger.info(f"按需加载文件: {required_files}")
        else:
            # 如果没有指定，加载常用文件
            default_files = ['description.md', 'simulation_config.yaml', 'modules_config.yaml']
            configs = self._read_specific_files(default_files)
            self.logger.info("加载默认文件")
        
        if not configs:
            return "未找到任何配置文件，无法回答问题。"
        
        # 读取代码逻辑（如果有）
        code_info = self._read_code_logic()
        
        # 构建上下文
        context = "=== 相关配置文件 ===\n\n"
        
        # 展示所加载的文件
        for filename, content in configs.items():
            context += f"【{filename}】\n{content}\n\n"
        
        # 添加代码信息
        if code_info:
            context += "=== 代码逻辑 ===\n"
            if 'simulator' in code_info:
                context += f"【Simulator完整代码】\n{code_info['simulator']}\n\n"
            if 'main' in code_info:
                context += f"【Main完整代码】\n{code_info['main']}\n\n"
        
        # 构建提示词
        prompt = self.prompts['answer_question_prompt'].format(
            user_question=user_question,
            context=context
        )
        
        # 调用LLM生成回答
        self.logger.info("调用LLM生成回答")
        answer = await self.generate_llm_response(prompt)
        await self.memory.write_record(
            role_name="机制解释对话agent",
            content=f"用户问题：{user_question}。回答：{answer}",
            is_user=False,
            store_in_shared=False  # 不存入共享记忆
            )
        return answer
    
    async def interactive_adjustment_session(self):
        """
        交互式调整会话
        引导用户了解和调整机制
        
        Returns:
            str: 格式化的需求字符串 ("1. 需求1\n2. 需求2") 或 None
        """
        self.logger.info("开始交互式调整会话")
        
        adjustments = []
        
        # 1. 首先解释当前机制
        print("\n" + "=" * 80)
        print("机制解释与调整助手")
        print("=" * 80)
        print("\n我将帮助您理解和调整当前的模拟机制。")
        print("您无需了解编程知识，只需用自然语言描述您的需求。")
        
        # 生成机制概览
        print("\n正在分析当前机制...")
        overview = await self.explain_mechanism()
        
        print("\n" + "-" * 80)
        print("【当前机制概览】")
        print("-" * 80)
        print(overview)
        print("-" * 80)
        
        # 2. 交互式对话循环
        print("\n" + "=" * 80)
        print("您可以:")
        print("  - 提问关于模拟的任何问题")
        print("  - 提出您的调整建议或意见")
        print("  - 输入 'done' 结束对话")
        print("=" * 80)
        
        while True:
            user_input = input("\n您: ").strip()
            
            if not user_input:
                continue
            if user_input.lower() == 'done':
                self.logger.info("用户完成对话")
                break
            # 识别用户意图
            print("\n正在理解您的意图...")
            intent_result = await self.recognize_intent(user_input)
            
            if not intent_result:
                print("\n✗ 抱歉，我没有理解您的意思。请尝试换个方式表达。")
                continue
            
            intent = intent_result.get('intent')
            
            # 根据意图处理
            if intent == 'done':
                print("\n✓ 调整会话结束")
                break
            
            elif intent == 'question':
                # 用户在提问
                print(f"\n正在思考您的问题...")
                answer = await self.answer_question(user_input, intent_result.get('required_files', []))
                print("\n" + "-" * 80)
                print(answer)
                print("-" * 80)
            
            elif intent == 'adjustment':
                # 用户想调整配置,显示转换后的描述
                description = intent_result.get('description', user_input)
                print(f"\n✓ 我理解您的意思是: {description}")
                
                # 询问是否确认
                confirm = input("\n是否是这个意思？(yes/no): ").strip().lower()
                if confirm in ['yes', 'y', '是', '']:
                    adjustments.append(description)
                    print(f"✓ 已添加到需求列表（当前共{len(adjustments)}项）")
                else:
                    print("已取消此需求，请重新描述")
            
            elif intent == 'view_adjustments':
                # 用户想查看需求列表
                if adjustments:
                    print("\n" + "-" * 80)
                    print("【当前需求列表】:")
                    print("-" * 80)
                    for i, req in enumerate(adjustments, 1):
                        print(f"{i}. {req}")
                    print("-" * 80)
                else:
                    print("\n暂无需求")
            
            else:
                print("\n✗ 抱歉，我没有理解您的意图。请尝试换个方式表达。")
        
        # 返回格式化的需求字符串
        if adjustments:
            requirements_text = "\n".join([f"{i}. {req}" for i, req in enumerate(adjustments, 1)])
            self.logger.info(f"收集到 {len(adjustments)} 项需求")
            return requirements_text
        else:
            self.logger.info("未收集到任何需求")
            return None
