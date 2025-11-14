
from .shared_imports import *
from .sim_architect import SimArchitectAgent
from .code_architect import CodeArchitectAgent
from .research_analyst import ResearchAnalystAgent

class ProjectMasterAgent(BaseAgent):
    """
    项目管理师Agent，继承BaseAgent，负责协调整个实验流程，调用其他agent并进行质量控制。
    """
    def __init__(self, agent_id, workspace_dir, docs_dir, config_template_dir):
        super().__init__(agent_id, group_type='project_master', window_size=5)
        self.workspace_dir = workspace_dir
        self.docs_dir = docs_dir
        self.config_template_dir = config_template_dir
        self.current_project_dir = None
        self.current_config_dir = None
        self.current_simulation_name = None
        self.max_regeneration_attempts = 3
        self.logger = LogManager.get_logger('project_master')
        
        # 子Agent实例（延迟初始化）
        self.code_architect = None
        
        # 加载提示词配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'project_master_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']
    
    def _check_step_completion(self, step_name, check_files):
        """检查步骤是否已完成（所有必需文件都存在）
        
        Args:
            step_name: 步骤名称
            check_files: 需要检查的文件列表
        
        Returns:
            bool: True表示需要执行步骤，False表示跳过
        """
        # 检查是否所有文件都存在
        all_exist = all(os.path.exists(f) for f in check_files)
        
        if not all_exist:
            return True  # 有文件不存在，需要执行
        
        # 所有文件都存在，询问是否跳过
        print(f"\n{'='*60}")
        print(f"检测到 {step_name} 的所有文件已存在:")
        for f in check_files:
            print(f"  ✓ {f}")
        print(f"{'='*60}")
        user_input = input("是否重新生成？(y/yes=重新生成, 其他=跳过使用现有文件): ").strip().lower()
        
        if user_input in ['y', 'yes']:
            self.logger.info(f"用户选择重新执行步骤: {step_name}")
            return True
        else:
            self.logger.info(f"用户选择跳过步骤: {step_name}")
            print(f"✓ 跳过步骤: {step_name}")
            return False

    def _read_modules_config(self):
        """读取模块配置文件内容
        
        Returns:
            str: 模块配置的YAML内容，如果文件不存在返回空字符串
        """
        modules_config_path = os.path.join(self.current_config_dir, 'modules_config.yaml')
        if os.path.exists(modules_config_path):
            with open(modules_config_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    async def parse_user_requirement(self, requirement_text):
        """
        解析用户需求，确定模拟名称和基本信息。
        """
        prompt = self.prompts['parse_user_requirement_prompt'].format(
            requirement_text=requirement_text
        )
        
        response = await self.generate_llm_response(prompt)
        try:
            parsed = json.loads(response)
        except Exception as e:
            self.logger.error(f"解析需求失败: {e}")
            parsed = {
                'simulation_name': f'sim_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'description': requirement_text[:100],
                'estimated_complexity': 'medium',
                'key_requirements': []
            }
        
        return parsed

    async def initialize_project(self, simulation_name):
        """
        创建项目文件夹结构。
        配置文件放在 config/[模拟名称] 文件夹下。
        """
        # 项目根目录（AgentWorld项目根目录）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 创建 config/[模拟名称] 文件夹
        config_dir = os.path.join(project_root, 'config', simulation_name)
        os.makedirs(config_dir, exist_ok=True)
        
        # 创建实验数据文件夹（在experiment_dataset下）
        experiment_dir = os.path.join(self.workspace_dir, simulation_name)
        os.makedirs(experiment_dir, exist_ok=True)
        
        # 在experiment_dataset下创建子文件夹
        subdirs = ['results', 'logs']
        for subdir in subdirs:
            os.makedirs(os.path.join(experiment_dir, subdir), exist_ok=True)
        
        self.current_project_dir = experiment_dir
        self.current_config_dir = config_dir
        self.current_simulation_name = simulation_name
        self.logger.info(f"配置文件夹已创建: {config_dir}")
        self.logger.info(f"实验文件夹已创建: {experiment_dir}")
        
        return experiment_dir

    async def validate_quality(self, content, content_type, criteria):
        """
        调用大模型验证生成内容的质量。
        
        Args:
            content: 要验证的内容
            content_type: 内容类型（如 "design_doc", "code", "config"）
            criteria: 验证标准
        
        Returns:
            (is_valid: bool, feedback: str, score: float)
        """
        prompt = self.prompts['validate_quality_prompt'].format(
            content_type=content_type,
            content=content,
            criteria=criteria
        )
        
        response = await self.generate_llm_response(prompt)
        try:
            result = json.loads(response)
            is_valid = result.get('is_valid', False) and result.get('score', 0) >= 70
            return is_valid, result.get('feedback', ''), result.get('score', 0)
        except Exception as e:
            self.logger.error(f"质量验证失败: {e}")
            return False, "验证过程出错", 0

    async def run_design_phase(self, requirement_dict, previous_version=None, user_feedback=None):
        """
        运行设计阶段，调用 SimArchitectAgent。
        
        Args:
            requirement_dict: 需求字典
            previous_version: 上一个版本的设计结果（如果是重新执行）
            user_feedback: 用户反馈意见
        """
        self.logger.info("=" * 50)
        self.logger.info("开始设计阶段")
        if user_feedback:
            self.logger.info(f"用户反馈: {user_feedback}")
        self.logger.info("=" * 50)
        
        # 使用项目根目录下的config_[模拟名称]文件夹
        designer = SimArchitectAgent(
            agent_id='sim_architect_001',
            output_dir=self.current_config_dir,
            docs_dir=self.docs_dir,
            config_dir=self.config_template_dir
        )
        
        # 解析需求
        self.logger.info("步骤 1: 解析需求")
        requirement_text = json.dumps(requirement_dict, ensure_ascii=False)
        
        # 如果有上一版本和反馈，添加到需求文本中
        if previous_version and user_feedback:
            requirement_text += f"\n\n上一版本结果:\n{json.dumps(previous_version.get('parsed_requirement', {}), ensure_ascii=False)}"
            requirement_text += f"\n\n用户反馈意见:\n{user_feedback}"
        
        parsed_req = await designer.parse_requirement(requirement_text)
        self.logger.info(f"需求解析结果: {parsed_req}")
        
        # 生成设计文档
        self.logger.info("步骤 2: 生成设计文档")
        
        # 检查是否已存在设计文档
        desc_path = os.path.join(self.current_config_dir, 'description.md')
        should_generate_desc = True
        
        if os.path.exists(desc_path) and not (previous_version and user_feedback):
            print(f"\n{'='*60}")
            print(f"发现已存在的设计文档")
            print(f"路径: {desc_path}")
            print(f"{'='*60}")
            user_input = input("是否重新生成？(y/yes=重新生成, 其他=跳过使用现有文件): ").strip().lower()
            
            if user_input not in ['y', 'yes']:
                self.logger.info("跳过生成，使用现有设计文档")
                print(f"✓ 跳过，使用现有设计文档")
                with open(desc_path, 'r', encoding='utf-8') as f:
                    description_md = f.read()
                should_generate_desc = False
        
        if should_generate_desc:
            # 构建带反馈的参数
            design_context = {
                'parsed_req': parsed_req
            }
            
            if previous_version and user_feedback:
                design_context['previous_description'] = previous_version.get('description_md', '')
                design_context['user_feedback'] = user_feedback
            
            description_md = await designer.generate_description_md(
                design_context.get('parsed_req'),
                design_context.get('previous_description'),
                design_context.get('user_feedback')
            )
            
            if description_md:
                with open(desc_path, 'w', encoding='utf-8') as f:
                    f.write(description_md)
                self.logger.info(f"设计文档已保存: {desc_path}")
        
        # 生成配置文件（modules_config.yaml）
        self.logger.info("步骤 3: 生成模块配置文件 (modules_config.yaml)")
        
        # 检查是否已存在模块配置文件
        modules_config_path = os.path.join(self.current_config_dir, 'modules_config.yaml')
        should_generate_modules_config = True
        
        if os.path.exists(modules_config_path) and not (previous_version and user_feedback):
            print(f"\n{'='*60}")
            print(f"发现已存在的模块配置文件")
            print(f"路径: {modules_config_path}")
            print(f"{'='*60}")
            user_input = input("是否重新生成？(y/yes=重新生成, 其他=跳过使用现有文件): ").strip().lower()
            
            if user_input not in ['y', 'yes']:
                self.logger.info("跳过生成，使用现有模块配置文件")
                print(f"✓ 跳过，使用现有模块配置文件")
                should_generate_modules_config = False
        
        if should_generate_modules_config:
            config_context = {
                'parsed_req': parsed_req,
                'description_md': description_md
            }
            
            if previous_version and user_feedback:
                config_context['previous_config'] = previous_version.get('config_files', [])
                config_context['user_feedback'] = user_feedback
            
            config_files = await designer.generate_config_files(
                config_context.get('parsed_req'),
                config_context.get('description_md'),
                config_context.get('previous_config'),
                config_context.get('user_feedback')
            )
            self.logger.info(f"配置文件已生成: {config_files}")
        else:
            config_files = [modules_config_path] if os.path.exists(modules_config_path) else []
        
        # 读取 modules_config.yaml 的内容，供编码阶段使用
        modules_config_yaml = ""
        if os.path.exists(modules_config_path):
            with open(modules_config_path, 'r', encoding='utf-8') as f:
                modules_config_yaml = f.read()
        
        return {
            'parsed_requirement': parsed_req,
            'description_md': description_md,
            'config_files': config_files,
            'modules_config_yaml': modules_config_yaml
        }

    async def run_coding_phase(self, design_results, previous_version=None, user_feedback=None):
        """
        运行编码阶段，调用 CodeArchitectAgent。
        采用细粒度步骤，每次只生成一个文件，避免上下文过大。
        
        Args:
            design_results: 设计阶段的结果
            previous_version: 上一个版本的代码结果（如果是重新执行）
            user_feedback: 用户反馈意见
        """
        self.logger.info("=" * 50)
        self.logger.info("开始编码阶段")
        if user_feedback:
            self.logger.info(f"用户反馈: {user_feedback}")
        self.logger.info("=" * 50)
        
        # 项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # simulator文件放在src/simulation文件夹下
        simulator_dir = os.path.join(project_root, 'src', 'simulation')
        os.makedirs(simulator_dir, exist_ok=True)
        
        # main文件放在entrypoints文件夹下
        entrypoints_dir = os.path.join(project_root, 'entrypoints')
        os.makedirs(entrypoints_dir, exist_ok=True)
        
        # 创建或复用 CodeArchitectAgent 实例
        if not self.code_architect:
            self.code_architect = CodeArchitectAgent(
                agent_id='code_architect_001',
                simulator_output_dir=simulator_dir,
                main_output_dir=entrypoints_dir,
                docs_dir=self.docs_dir,
                config_dir=self.current_config_dir,
                config_template_dir=self.config_template_dir,
                simulation_name=self.current_simulation_name
            )
        
        coder = self.code_architect
        
        # 检查编码阶段是否已完成（所有必需文件都存在）
        simulator_file_path = os.path.join(simulator_dir, f'simulator_{self.current_simulation_name}.py')
        main_file_path = os.path.join(entrypoints_dir, f'main_{self.current_simulation_name}.py')
        
        required_files = [
            simulator_file_path,
            main_file_path,
            os.path.join(self.current_config_dir, 'simulation_config.yaml'),
            os.path.join(self.current_config_dir, 'jobs_config.yaml'),
            os.path.join(self.current_config_dir, 'resident_actions.yaml'),
            os.path.join(self.current_config_dir, 'towns_data.json'),
        ]
        
        # 如果所有文件都存在，询问是否跳过
        if not self._check_step_completion("编码阶段", required_files):
            # 用户选择跳过，读取现有文件并返回
            self.logger.info("跳过编码阶段，使用现有文件")
            
            # 收集所有现有文件
            config_files = [f for f in required_files[2:] if os.path.exists(f)]
            prompt_files = []
            for prompt_file in ['government_prompts.yaml', 'rebels_prompts.yaml', 'residents_prompts.yaml']:
                pf_path = os.path.join(self.current_config_dir, prompt_file)
                if os.path.exists(pf_path):
                    prompt_files.append(pf_path)
            
            return {
                'status': 'success',
                'simulator_files': [simulator_file_path],
                'main_files': [main_file_path],
                'config_files': config_files,
                'prompt_files': prompt_files,
                'all_files': [simulator_file_path, main_file_path] + config_files + prompt_files
            }
        
        # 准备上下文（包含上一版本和用户反馈）
        context_suffix = ""
        if previous_version and user_feedback:
            context_suffix = f"\n\n=== 上一版本代码 ===\n"
            if previous_version.get('simulator_files'):
                prev_sim_path = previous_version['simulator_files'][0]
                if os.path.exists(prev_sim_path):
                    with open(prev_sim_path, 'r', encoding='utf-8') as f:
                        context_suffix += f"Simulator代码:\n{f.read()[:2000]}...(已截断)\n\n"
            
            if previous_version.get('main_files'):
                prev_main_path = previous_version['main_files'][0]
                if os.path.exists(prev_main_path):
                    with open(prev_main_path, 'r', encoding='utf-8') as f:
                        context_suffix += f"Main代码:\n{f.read()[:2000]}...(已截断)\n\n"
            
            context_suffix += f"=== 用户反馈 ===\n{user_feedback}\n"
        
        # === 步骤1: 生成simulator代码框架 ===
        self.logger.info("步骤 1: 生成simulator代码框架")
        description_with_context = design_results['description_md'] + context_suffix
        
        simulator_files, skipped = await coder.generate_simulator_code(
            description_with_context,
            design_results.get('modules_config_yaml', '')
        )
        
        if not simulator_files:
            self.logger.error("生成simulator代码失败")
            return {'status': 'failed', 'reason': 'simulator generation failed'}
        
        simulator_file_path = simulator_files[0]
        self.logger.info(f"Simulator代码已生成: {simulator_file_path}")
        
        # === 步骤2: 检查并补完simulator函数 ===
        # 如果用户选择跳过重新生成，则直接跳过步骤2
        if skipped:
            self.logger.info("⏭️  步骤 2: 用户选择使用现有simulator文件，跳过完善步骤")
        else:
            self.logger.info("步骤 2: 根据模块配置完善simulator实现")
            refined_simulator = await coder.refine_simulator_functions(
                simulator_file_path,
                description_with_context,
                design_results.get('modules_config_yaml', '')
            )
            
            if refined_simulator:
                self.logger.info("Simulator函数已补完")
            else:
                self.logger.warning("Simulator函数补完失败，保持原文件")
        
        # === 步骤3: 生成main入口文件完整代码 ===
        self.logger.info("步骤 3: 生成main入口文件完整代码")
        main_result = await coder.generate_main_file(
            description_with_context,
            simulator_file_path
        )
        
        # 解包返回值：(文件路径列表, 是否跳过)
        if isinstance(main_result, tuple):
            main_files, main_skipped = main_result
        else:
            # 兼容旧版本返回值（只有文件列表）
            main_files = main_result
            main_skipped = False
        
        if not main_files:
            self.logger.error("生成main文件失败")
            return {'status': 'failed', 'reason': 'main file generation failed'}
        
        main_file_path = main_files[0]
        if main_skipped:
            self.logger.info(f"Main文件已跳过（使用现有文件）: {main_file_path}")
        else:
            self.logger.info(f"Main文件已生成: {main_file_path}")
        
        # === 步骤4: 检查并补完main函数 ===
        self.logger.info("步骤 4: 检查并补完main函数实现")
        modules_config_yaml = self._read_modules_config()
        refined_main = await coder.refine_main_functions(
            main_file_path,
            simulator_file_path,
            description_with_context,
            modules_config_yaml,
            main_skipped=main_skipped  # 传递跳过标记
        )
        
        if refined_main:
            self.logger.info("Main函数已补完")
        else:
            self.logger.warning("Main函数补完失败，保持原文件")
        
        # === 步骤5: 生成配置文件（按顺序，每次一个） ===
        self.logger.info("步骤 5: 生成配置文件")
        config_files = []
        previous_configs = {}
        
        # 读取说明文件 (description.md)
        description_file_path = os.path.join(self.current_config_dir, 'description.md')
        description_content = ""
        if os.path.exists(description_file_path):
            with open(description_file_path, 'r', encoding='utf-8') as f:
                description_content = f.read()
        else:
            self.logger.warning(f"说明文件不存在: {description_file_path}")
            description_content = design_results['description_md']
        
        # 如果有上一版本的配置，加入上下文
        prev_config_context = ""
        if previous_version and user_feedback and previous_version.get('config_files'):
            prev_config_context = f"\n\n=== 上一版本配置 ===\n"
            for prev_cfg in previous_version['config_files']:
                if os.path.exists(prev_cfg):
                    cfg_name = os.path.basename(prev_cfg)
                    with open(prev_cfg, 'r', encoding='utf-8') as f:
                        prev_config_context += f"{cfg_name}:\n{f.read()[:1000]}...\n\n"
            prev_config_context += f"=== 用户反馈 ===\n{user_feedback}\n"
        
        # 必需的配置文件，按顺序生成
        required_configs = [
            'simulation_config.yaml',
            'jobs_config.yaml',
            'resident_actions.yaml',
            'towns_data.json'
        ]

        # TODO: 这里不应该是硬性的判断，应该是由大模型根据说明文件来判断，是否还需要其他模块，需要思考加在什么位置比较合适
        # 根据说明文件判断是否需要额外的配置文件
        description_lower = description_content.lower()
        if 'message' in description_lower or '信息传播' in description_content or '消息' in description_content:
            if 'message_config.yaml' not in required_configs:
                required_configs.append('message_config.yaml')
                self.logger.info("  根据说明文件，添加配置文件: message_config.yaml")
        
        if 'questionnaire' in description_lower or '问卷' in description_content or '调查' in description_content:
            if 'questionnaire.yaml' not in required_configs:
                required_configs.append('questionnaire.yaml')
                self.logger.info("  根据说明文件，添加配置文件: questionnaire.yaml")
        
        for config_filename in required_configs:
            self.logger.info(f"  生成配置文件: {config_filename}")
            description_with_config_context = description_content + prev_config_context
            
            # 读取模块配置
            modules_config_yaml = self._read_modules_config()
            
            config_path = await coder.generate_config_file(
                config_filename,
                description_with_config_context,
                modules_config_yaml,
                previous_configs
            )
            
            if config_path:
                config_files.append(config_path)
                # 读取刚生成的配置，供后续配置参考
                with open(config_path, 'r', encoding='utf-8') as f:
                    previous_configs[config_filename] = f.read()
                self.logger.info(f"  ✓ {config_filename} 已生成")
            else:
                self.logger.warning(f"  ✗ {config_filename} 生成失败")
        
        # === 步骤6: 生成提示词文件（根据modules_config.yaml决定） ===
        self.logger.info("步骤 6: 生成提示词文件")
        prompt_files = []
        
        # 读取 modules_config.yaml 确定需要生成哪些提示词文件
        modules_config_path = os.path.join(self.current_config_dir, 'modules_config.yaml')
        prompt_file_mapping = {}
        
        if os.path.exists(modules_config_path):
            with open(modules_config_path, 'r', encoding='utf-8') as f:
                modules_config = yaml.safe_load(f)
            
            # 遍历 selected_modules，检查哪些模块是 required: true 并且有对应的提示词文件
            if 'selected_modules' in modules_config:
                for module in modules_config['selected_modules']:
                    module_name = module.get('module_name', '')
                    required = module.get('required', False)
                    config_files_str = module.get('config_files', '')
                    
                    # 如果模块被选中且有配置文件
                    if required and config_files_str:
                        # 解析配置文件列表（可能是逗号分隔的字符串）
                        config_file_list = [f.strip() for f in config_files_str.split(',')]
                        
                        # 检查是否包含提示词文件
                        for config_file in config_file_list:
                            if config_file.endswith('_prompts.yaml'):
                                # 映射模块名到提示词文件
                                prompt_file_mapping[module_name] = config_file
                                self.logger.info(f"  模块 {module_name} (required=true) -> {config_file}")
        else:
            self.logger.warning(f"未找到 modules_config.yaml: {modules_config_path}")
            # 使用默认映射
            prompt_file_mapping = {
                'government': 'government_prompts.yaml',
                'rebels': 'rebels_prompts.yaml',
                'resident': 'residents_prompts.yaml'
            }
        
        # 如果有上一版本的提示词，加入上下文
        prev_prompt_context = ""
        if previous_version and user_feedback and previous_version.get('prompt_files'):
            prev_prompt_context = f"\n\n=== 上一版本提示词 ===\n"
            for prev_prompt in previous_version['prompt_files']:
                if os.path.exists(prev_prompt):
                    prompt_name = os.path.basename(prev_prompt)
                    with open(prev_prompt, 'r', encoding='utf-8') as f:
                        prev_prompt_context += f"{prompt_name}:\n{f.read()[:1000]}...\n\n"
            prev_prompt_context += f"=== 用户反馈 ===\n{user_feedback}\n"
        
        # 生成提示词文件
        modules_config_yaml = self._read_modules_config()
        for module_name, prompt_filename in prompt_file_mapping.items():
            self.logger.info(f"  生成提示词文件: {prompt_filename} (来自模块: {module_name})")
            description_with_prompt_context = description_content + prev_prompt_context
            
            prompt_path = await coder.generate_prompt_file(
                prompt_filename,
                description_with_prompt_context,
                modules_config_yaml,
                config_files
            )
            
            if prompt_path:
                prompt_files.append(prompt_path)
                self.logger.info(f"  ✓ {prompt_filename} 已生成")
            else:
                self.logger.warning(f"  ✗ {prompt_filename} 生成失败")
        
        # === 返回结果 ===
        coding_results = {
            'status': 'success',
            'simulator_files': simulator_files,
            'main_files': main_files,
            'config_files': config_files,
            'prompt_files': prompt_files,
            'all_files': simulator_files + main_files + config_files + prompt_files
        }
        
        self.logger.info("编码阶段完成")
        self.logger.info(f"共生成 {len(coding_results['all_files'])} 个文件")
        
        return coding_results

    async def run_simulation(self, coding_results, max_fix_attempts=10):
        """
        运行模拟程序，如果出错则自动调用编码师进行纠错。
        
        Args:
            coding_results: 编码阶段的结果
            max_fix_attempts: 最大修复尝试次数
        
        Returns:
            结果文件路径或None（如果失败）
        """
        self.logger.info("=" * 50)
        self.logger.info("运行模拟程序")
        self.logger.info("=" * 50)
        
        # 获取文件路径
        main_files = coding_results.get('main_files', [])
        simulator_files = coding_results.get('simulator_files', [])
        
        if not main_files or not simulator_files:
            self.logger.error("❌ 缺少必要的文件（main或simulator）")
            return None
        
        main_file_path = main_files[0]
        simulator_file_path = simulator_files[0]
        
        # 获取模拟名称
        simulation_name = self.current_simulation_name
        
        # 构建运行命令
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, 'config', simulation_name, 'simulation_config.yaml')
        
        # 使用相对路径
        main_file_rel = os.path.relpath(main_file_path, project_root)
        run_command = f'python {main_file_rel} --config_path config/{simulation_name}/simulation_config.yaml'
        
        self.logger.info(f"运行命令: {run_command}")
        self.logger.info(f"工作目录: {project_root}")
        
        # 尝试运行程序
        for attempt in range(1, max_fix_attempts + 1):
            self.logger.info(f"\n第 {attempt}/{max_fix_attempts} 次运行尝试...")
            
            try:
                import subprocess
                
                # 设置环境变量以确保 UTF-8 编码
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                
                # 运行程序
                # 在 Windows 上，使用 chcp 65001 设置 UTF-8 编码
                if os.name == 'nt':  # Windows
                    run_command_with_encoding = f'chcp 65001 >nul && {run_command}'
                else:
                    run_command_with_encoding = run_command
                
                result = subprocess.run(
                    run_command_with_encoding,
                    shell=True,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5分钟超时
                    encoding='utf-8',
                    errors='replace',  # 将无法解码的字符替换为 �
                    env=env  # 使用包含 PYTHONIOENCODING 的环境变量
                )
                
                # 检查是否成功
                if result.returncode == 0:
                    # 检查是否有实际输出
                    output = result.stdout.strip()
                    if not output or len(output) < 10:
                        self.logger.warning("⚠️ 程序返回成功但没有输出，可能存在问题")
                        self.logger.info(f"标准输出: {result.stdout}")
                        self.logger.info(f"标准错误: {result.stderr}")
                        
                        # 将这种情况视为失败，尝试修复
                        error_message = "程序运行后没有输出，可能是代码未执行或出现静默错误"
                        if attempt < max_fix_attempts:
                            self.logger.info(f"\n🔧 调用编码师Agent进行诊断和修复...")
                            
                            # 调用编码师的纠错函数
                            fixed = await self.code_architect.fix_runtime_errors(
                                error_message=error_message,
                                error_traceback=f"标准输出:\n{result.stdout}\n\n标准错误:\n{result.stderr}",
                                main_file_path=main_file_path,
                                simulator_file_path=simulator_file_path,
                                max_attempts=3
                            )
                            
                            if fixed:
                                self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                                continue  # 重新运行
                            else:
                                self.logger.error("❌ 编码师修复失败")
                                return None
                        else:
                            self.logger.error("❌ 已达到最大运行尝试次数")
                            return None
                    
                    self.logger.info("✅ 程序运行成功！")
                    self.logger.info(f"输出:\n{result.stdout}")
                    
                    # 查找结果文件
                    results_dir = os.path.join(self.current_project_dir, 'results')
                    if os.path.exists(results_dir):
                        result_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
                        if result_files:
                            result_file = os.path.join(results_dir, result_files[0])
                            self.logger.info(f"结果文件: {result_file}")
                            return result_file
                    
                    # 如果没有找到结果文件，返回虚拟路径
                    return os.path.join(results_dir, 'simulation_results.json')
                else:
                    # 程序运行出错
                    error_message = result.stderr if result.stderr else result.stdout
                    self.logger.error(f"❌ 程序运行失败 (退出码: {result.returncode})")
                    self.logger.error(f"错误信息:\n{error_message}")
                    
                    # 如果不是最后一次尝试，调用编码师修复
                    if attempt < max_fix_attempts:
                        self.logger.info(f"\n🔧 调用编码师Agent进行纠错...")
                        
                        # 获取完整的错误堆栈
                        error_traceback = result.stderr if result.stderr else result.stdout
                        
                        # 调用编码师的纠错函数
                        fixed = await self.code_architect.fix_runtime_errors(
                            error_message=error_message,
                            error_traceback=error_traceback,
                            main_file_path=main_file_path,
                            simulator_file_path=simulator_file_path,
                            max_attempts=3  # 编码师内部的修复尝试次数
                        )
                        
                        if fixed:
                            self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                        else:
                            self.logger.error("❌ 编码师修复失败")
                            if attempt == max_fix_attempts - 1:
                                self.logger.error("已达到最大修复次数，停止尝试")
                                return None
                    else:
                        self.logger.error("❌ 已达到最大运行尝试次数")
                        return None
                        
            except subprocess.TimeoutExpired:
                self.logger.error("❌ 程序运行超时（超过5分钟）")
                return None
            except Exception as e:
                self.logger.error(f"❌ 运行时发生异常: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return None
        
        return None

    async def run_evaluation_phase(self, simulation_results_path):
        """
        运行评估阶段，调用 ResearchAnalystAgent。
        增强版：根据结果评估是否符合预期，如果不符合则自动修改配置。
        """
        self.logger.info("=" * 50)
        self.logger.info("开始评估阶段")
        self.logger.info("=" * 50)
        
        results_dir = os.path.join(self.current_project_dir, 'results')
        
        analyst = ResearchAnalystAgent(
            agent_id='research_analyst_001',
            output_dir=results_dir,
            docs_dir=self.docs_dir
        )
        
        # 读取设计文档
        design_doc_path = os.path.join(self.current_config_dir, 'description.md')
        design_doc = ""
        if os.path.exists(design_doc_path):
            with open(design_doc_path, 'r', encoding='utf-8') as f:
                design_doc = f.read()
        
        # === 步骤 1: 评估模拟结果 ===
        self.logger.info("步骤 1: 评估模拟结果是否符合预期趋势")
        evaluation_report = await analyst.evaluate_simulation(
            simulation_results_path,
            design_doc=design_doc
        )
        self.logger.info("评估报告已生成")
        
        # 判断是否需要调整
        needs_adjustment = 'NEED_ADJUSTMENT' in evaluation_report.upper()
        
        if needs_adjustment:
            self.logger.info("⚠️  结果不符合预期，开始诊断配置问题...")
            
            # === 步骤 2: 诊断配置问题 ===
            self.logger.info("步骤 2: 诊断需要修改哪些配置或提示词")
            diagnosis_result = await analyst.diagnose_config_issues(
                evaluation_report,
                self.current_config_dir,
                design_doc=design_doc
            )
            self.logger.info("诊断结果已生成")
            
            # === 步骤 3: 生成修改方案 ===
            self.logger.info("步骤 3: 生成具体的配置修改方案")
            modification_proposals = await analyst.generate_config_modifications(
                diagnosis_result,
                self.current_config_dir,
                design_doc=design_doc
            )
            
            if modification_proposals:
                self.logger.info(f"已生成 {len(modification_proposals)} 个文件的修改方案")
                
                # 询问用户是否应用修改
                print(f"\n{'='*60}")
                print(f"检测到配置需要调整，生成了以下修改方案：")
                for prop in modification_proposals:
                    print(f"  - {prop['file_name']}: {len(prop['modifications'])} 个修改项")
                print(f"{'='*60}")
                user_input = input("是否应用这些修改？(y/yes=应用, 其他=跳过): ").strip().lower()
                
                if user_input in ['y', 'yes']:
                    # === 步骤 4: 应用修改 ===
                    self.logger.info("步骤 4: 应用配置修改")
                    application_result = await analyst.apply_modifications(
                        modification_proposals,
                        self.current_config_dir
                    )
                    self.logger.info("✓ 配置修改已应用")
                    
                    return {
                        'evaluation_report': evaluation_report,
                        'needs_adjustment': True,
                        'diagnosis_result': diagnosis_result,
                        'modification_proposals': modification_proposals,
                        'application_result': application_result
                    }
                else:
                    self.logger.info("用户跳过应用修改")
                    return {
                        'evaluation_report': evaluation_report,
                        'needs_adjustment': True,
                        'diagnosis_result': diagnosis_result,
                        'modification_proposals': modification_proposals,
                        'application_result': None
                    }
            else:
                self.logger.warning("未能生成有效的修改方案")
                return {
                    'evaluation_report': evaluation_report,
                    'needs_adjustment': True,
                    'diagnosis_result': diagnosis_result,
                    'modification_proposals': [],
                    'application_result': None
                }
        else:
            self.logger.info("✓ 结果符合预期，无需调整")
            return {
                'evaluation_report': evaluation_report,
                'needs_adjustment': False
            }

    async def run_iteration(self, evaluation_results):
        """
        运行一次迭代优化。
        """
        self.logger.info("=" * 50)
        self.logger.info("开始迭代优化")
        self.logger.info("=" * 50)
        
        results_dir = os.path.join(self.current_project_dir, 'results')
        analyst = ResearchAnalystAgent(
            agent_id='research_analyst_001',
            output_dir=results_dir,
            docs_dir=self.docs_dir
        )
        
        # 应用调整建议
        config_file = os.path.join(self.current_config_dir, 'simulation_config.yaml')
        if os.path.exists(config_file):
            self.logger.info("应用调整建议到配置文件")
            apply_result = await analyst.apply_adjustments(
                evaluation_results['adjustment_proposals'],
                config_file
            )
            self.logger.info(f"调整已应用: {apply_result}")
            return True
        else:
            self.logger.warning("未找到配置文件，跳过调整应用")
            return False

    async def run_full_workflow(self, requirement_text, max_iterations=3):
        """
        运行完整的工作流程。
        
        Args:
            requirement_text: 用户需求描述
            max_iterations: 最大迭代次数
        
        Returns:
            完整的执行结果
        """
        print("开始运行完整工作流程...")
        self.logger.info("=" * 80)
        self.logger.info("开始完整工作流程")
        self.logger.info("=" * 80)
        
        # 1. 解析需求并初始化项目
        self.logger.info("\n阶段 1: 需求分析和项目初始化")
        requirement_dict = await self.parse_user_requirement(requirement_text)
        project_dir = await self.initialize_project(requirement_dict['simulation_name'])
        
        # 2. 设计阶段
        self.logger.info("\n阶段 2: 系统设计")
        design_results = await self.run_design_phase(requirement_dict)
        
        # 3. 编码阶段
        self.logger.info("\n阶段 3: 代码生成")
        coding_results = await self.run_coding_phase(design_results)
        
        # 4. 运行模拟（带自动纠错）
        self.logger.info("\n阶段 4: 运行模拟")
        simulation_results_path = await self.run_simulation(coding_results, max_fix_attempts=10)
        
        if simulation_results_path is None:
            self.logger.error("❌ 模拟运行失败，工作流程终止")
            self.logger.info("=" * 80)
            self.logger.info("工作流程因运行失败而终止")
            self.logger.info(f"项目目录: {project_dir}")
            self.logger.info("请检查日志文件获取详细错误信息")
            self.logger.info("=" * 80)
            
            return {
                'status': 'failed',
                'reason': 'simulation_execution_failed',
                'project_dir': project_dir,
                'design_results': design_results,
                'coding_results': coding_results,
                'simulation_results': None,
            }
        
        self.logger.info("✅ 模拟运行成功")
        
        # 5. 评估阶段
        self.logger.info("\n阶段 5: 结果评估")
        evaluation_results = await self.run_evaluation_phase(simulation_results_path)
        
        # 6. 迭代优化（可选）
        iteration_history = []
        for i in range(max_iterations):
            self.logger.info(f"\n阶段 6.{i+1}: 迭代优化 (第 {i+1}/{max_iterations} 轮)")
            
            # 判断是否需要继续迭代
            should_iterate = await self.should_continue_iteration(evaluation_results)
            if not should_iterate:
                self.logger.info("评估结果已达标，无需继续迭代")
                break
            
            # 应用调整并重新运行
            iteration_success = await self.run_iteration(evaluation_results)
            if iteration_success:
                simulation_results_path = await self.run_simulation(coding_results)
                evaluation_results = await self.run_evaluation_phase(simulation_results_path)
                iteration_history.append({
                    'iteration': i + 1,
                    'results': evaluation_results
                })
            else:
                break
        
        # 7. 生成最终报告
        self.logger.info("\n阶段 7: 生成最终报告")
        if iteration_history:
            results_dir = os.path.join(self.current_project_dir, 'results')
            analyst = ResearchAnalystAgent(
                agent_id='research_analyst_001',
                output_dir=results_dir,
                docs_dir=self.docs_dir
            )
            final_summary = await analyst.generate_optimization_summary(iteration_history)
            self.logger.info("最终优化报告已生成")
        
        self.logger.info("=" * 80)
        self.logger.info("工作流程完成")
        self.logger.info(f"项目目录: {project_dir}")
        self.logger.info("=" * 80)
        
        return {
            'status': 'completed',
            'project_dir': project_dir,
            'design_results': design_results,
            'coding_results': coding_results,
            'simulation_results': simulation_results_path,
            # 'evaluation_results': evaluation_results,
            # 'iteration_history': iteration_history
        }

    async def run_interactive_workflow(self, requirement_text):
        """
        运行交互式工作流程，每个阶段完成后等待用户反馈。
        
        Args:
            requirement_text: 用户需求描述
        
        Returns:
            完整的执行结果和历史记录
        """
        print("\n" + "=" * 80)
        print("开始交互式工作流程")
        print("=" * 80)
        
        self.logger.info("=" * 80)
        self.logger.info("开始交互式工作流程")
        self.logger.info("=" * 80)
        
        # 存储每个阶段的版本历史
        phase_history = {
            'design': [],
            'coding': []
        }
        
        # ============ 阶段 1: 需求分析和项目初始化 ============
        print("\n" + "=" * 80)
        print("阶段 1: 需求分析和项目初始化")
        print("=" * 80)
        self.logger.info("\n阶段 1: 需求分析和项目初始化")
        
        requirement_dict = await self.parse_user_requirement(requirement_text)
        project_dir = await self.initialize_project(requirement_dict['simulation_name'])
        
        print(f"\n✓ 项目已初始化")
        print(f"  - 模拟名称: {requirement_dict['simulation_name']}")
        print(f"  - 描述: {requirement_dict['description']}")
        print(f"  - 项目目录: {project_dir}")
        print(f"  - 配置目录: {self.current_config_dir}")
        
        # ============ 阶段 2: 系统设计（可重复） ============
        design_results = None
        design_version = 0
        
        while True:
            design_version += 1
            print("\n" + "=" * 80)
            print(f"阶段 2: 系统设计 (版本 {design_version})")
            print("=" * 80)
            self.logger.info(f"\n阶段 2: 系统设计 (版本 {design_version})")
            
            # 获取上一版本和反馈
            previous_design = phase_history['design'][-1]['result'] if phase_history['design'] else None
            user_feedback = phase_history['design'][-1]['feedback'] if phase_history['design'] else None
            
            # 运行设计阶段
            design_results = await self.run_design_phase(
                requirement_dict,
                previous_version=previous_design,
                user_feedback=user_feedback
            )
            
            # 显示结果
            print("\n设计阶段完成！")
            print(f"\n✓ 需求解析结果:")
            print(f"  {json.dumps(design_results['parsed_requirement'], ensure_ascii=False, indent=2)}")
            print(f"\n✓ 设计文档: {self.current_config_dir}/description.md")
            if design_results.get('config_files'):
                print(f"✓ 配置文件: {design_results['config_files']}")
            
            # 显示模块配置（如果存在）
            modules_config_path = os.path.join(self.current_config_dir, 'modules_config.yaml')
            if os.path.exists(modules_config_path):
                print(f"✓ 模块配置文件: {modules_config_path}")
                with open(modules_config_path, 'r', encoding='utf-8') as f:
                    modules_config = yaml.safe_load(f)
                    if 'selected_modules' in modules_config:
                        print(f"\n✓ 选择的模块:")
                        for module in modules_config['selected_modules']:
                            if module.get('required', False):
                                print(f"  - {module.get('display_name', module.get('module_name', ''))}")
            
            # 显示设计文档内容（前500字符）
            if design_results.get('description_md'):
                print("\n设计文档摘要:")
                print("-" * 80)
                print(design_results['description_md'][:500])
                if len(design_results['description_md']) > 500:
                    print("...(更多内容请查看文件)")
                print("-" * 80)
            
            # 等待用户反馈
            print("\n请审查设计结果，提供反馈：")
            print("  - 输入 'ok' 或 'yes' 继续下一阶段")
            print("  - 输入反馈意见重新生成设计")
            print("  - 输入 'quit' 退出")
            
            user_input = input("\n您的反馈: ").strip()
            
            # 记录历史
            phase_history['design'].append({
                'version': design_version,
                'result': design_results,
                'feedback': user_input
            })
            
            if user_input.lower() in ['ok', 'yes', '']:
                print("\n✓ 设计阶段确认，进入编码阶段...")
                self.logger.info("用户确认设计结果，进入下一阶段")
                break
            elif user_input.lower() == 'quit':
                print("\n用户终止流程")
                self.logger.info("用户终止流程")
                return {
                    'status': 'terminated',
                    'phase': 'design',
                    'history': phase_history
                }
            else:
                print(f"\n收到反馈，重新生成设计... (版本 {design_version + 1})")
                self.logger.info(f"用户反馈: {user_input}")
                self.logger.info("重新执行设计阶段")
        
        # ============ 阶段 3: 代码生成（可重复） ============
        coding_results = None
        coding_version = 0
        
        while True:
            coding_version += 1
            print("\n" + "=" * 80)
            print(f"阶段 3: 代码生成 (版本 {coding_version})")
            print("=" * 80)
            self.logger.info(f"\n阶段 3: 代码生成 (版本 {coding_version})")
            
            # 获取上一版本和反馈
            previous_coding = phase_history['coding'][-1]['result'] if phase_history['coding'] else None
            user_feedback = phase_history['coding'][-1]['feedback'] if phase_history['coding'] else None
            
            # 运行编码阶段
            coding_results = await self.run_coding_phase(
                design_results,
                previous_version=previous_coding,
                user_feedback=user_feedback
            )
            
            # 显示结果
            if coding_results.get('status') == 'failed':
                print(f"\n✗ 编码阶段失败: {coding_results.get('reason')}")
                print("请提供反馈以重新生成")
            else:
                print("\n编码阶段完成！")
                print(f"\n✓ 生成的文件:")
                if coding_results.get('simulator_files'):
                    print(f"  - Simulator: {coding_results['simulator_files'][0]}")
                if coding_results.get('main_files'):
                    print(f"  - Main: {coding_results['main_files'][0]}")
                if coding_results.get('config_files'):
                    print(f"  - 配置文件 ({len(coding_results['config_files'])}个):")
                    for cfg in coding_results['config_files']:
                        print(f"    * {os.path.basename(cfg)}")
                if coding_results.get('prompt_files'):
                    print(f"  - 提示词文件 ({len(coding_results['prompt_files'])}个):")
                    for pf in coding_results['prompt_files']:
                        print(f"    * {os.path.basename(pf)}")
                
                print(f"\n✓ 总计生成 {len(coding_results.get('all_files', []))} 个文件")
            
            # 等待用户反馈
            print("\n请审查代码和配置文件，提供反馈：")
            print("  - 输入 'ok' 或 'yes' 完成流程")
            print("  - 输入反馈意见重新生成代码")
            print("  - 输入 'back' 返回设计阶段")
            print("  - 输入 'quit' 退出")
            
            user_input = input("\n您的反馈: ").strip()
            
            # 记录历史
            phase_history['coding'].append({
                'version': coding_version,
                'result': coding_results,
                'feedback': user_input
            })
            
            if user_input.lower() in ['ok', 'yes', '']:
                print("\n✓ 编码阶段确认，进入运行模拟阶段...")
                self.logger.info("用户确认编码结果，进入下一阶段")
                break
            elif user_input.lower() == 'back':
                print("\n返回设计阶段...")
                self.logger.info("用户选择返回设计阶段")
                # 重新进入设计阶段循环
                # 这里为简化，直接提示用户重启流程
                print("提示：当前版本暂不支持返回上一阶段，请重新运行流程")
                break
            elif user_input.lower() == 'quit':
                print("\n用户终止流程")
                self.logger.info("用户终止流程")
                return {
                    'status': 'terminated',
                    'phase': 'coding',
                    'history': phase_history
                }
            else:
                print(f"\n收到反馈，重新生成代码... (版本 {coding_version + 1})")
                self.logger.info(f"用户反馈: {user_input}")
                self.logger.info("重新执行编码阶段")
        
        # ============ 阶段 4: 运行模拟 ============
        print("\n" + "=" * 80)
        print("阶段 4: 运行模拟")
        print("=" * 80)
        self.logger.info("\n阶段 4: 运行模拟")
        
        print("\n是否运行模拟程序？")
        print("  - 输入 'ok' 或 'yes' 运行模拟")
        print("  - 输入 'skip' 跳过运行模拟")
        print("  - 输入 'quit' 退出")
        
        user_input = input("\n您的选择: ").strip()
        
        simulation_results_path = None
        if user_input.lower() in ['ok', 'yes', '']:
            print("\n开始运行模拟...")
            simulation_results_path = await self.run_simulation(coding_results, max_fix_attempts=10)
            
            if simulation_results_path is None:
                print("\n❌ 模拟运行失败")
                self.logger.error("模拟运行失败")
                print("\n是否继续工作流程？")
                print("  - 输入 'yes' 继续（跳过评估阶段）")
                print("  - 其他输入退出")
                
                user_input = input("\n您的选择: ").strip()
                if user_input.lower() != 'yes':
                    return {
                        'status': 'terminated',
                        'phase': 'simulation',
                        'project_dir': project_dir,
                        'config_dir': self.current_config_dir,
                        'design_results': design_results,
                        'coding_results': coding_results,
                        'history': phase_history
                    }
            else:
                print(f"\n✅ 模拟运行成功！")
                print(f"结果文件: {simulation_results_path}")
        elif user_input.lower() == 'quit':
            print("\n用户终止流程")
            self.logger.info("用户终止流程")
            return {
                'status': 'terminated',
                'phase': 'simulation',
                'history': phase_history
            }
        else:
            print("\n跳过运行模拟")
            self.logger.info("用户选择跳过运行模拟")
        
        # ============ 阶段 5: 评估结果（可选） ============
        evaluation_results = None
        if simulation_results_path:
            print("\n" + "=" * 80)
            print("阶段 5: 评估结果")
            print("=" * 80)
            self.logger.info("\n阶段 5: 评估结果")
            
            print("\n是否评估模拟结果？")
            print("  - 输入 'ok' 或 'yes' 进行评估")
            print("  - 输入 'skip' 跳过评估")
            print("  - 输入 'quit' 退出")
            
            user_input = input("\n您的选择: ").strip()
            
            if user_input.lower() in ['ok', 'yes', '']:
                print("\n开始评估...")
                try:
                    evaluation_results = await self.run_evaluation_phase(simulation_results_path)
                    
                    print("\n✅ 评估完成！")
                    if evaluation_results.get('evaluation_report'):
                        print("\n评估报告摘要:")
                        print("-" * 80)
                        report = evaluation_results['evaluation_report']
                        print(report[:500] if isinstance(report, str) else str(report)[:500])
                        print("...(更多内容请查看文件)")
                        print("-" * 80)
                except Exception as e:
                    print(f"\n❌ 评估失败: {e}")
                    self.logger.error(f"评估失败: {e}")
            elif user_input.lower() == 'quit':
                print("\n用户终止流程")
                self.logger.info("用户终止流程")
                return {
                    'status': 'terminated',
                    'phase': 'evaluation',
                    'history': phase_history
                }
            else:
                print("\n跳过评估")
                self.logger.info("用户选择跳过评估")
        
        # ============ 阶段 6: 迭代优化（可选） ============
        iteration_history = []
        if evaluation_results:
            print("\n" + "=" * 80)
            print("阶段 6: 迭代优化")
            print("=" * 80)
            self.logger.info("\n阶段 6: 迭代优化")
            
            max_iterations = 3
            for i in range(max_iterations):
                print(f"\n是否进行第 {i+1} 轮迭代优化？")
                print("  - 输入 'ok' 或 'yes' 进行优化")
                print("  - 输入 'no' 或 'skip' 跳过优化")
                print("  - 输入 'quit' 退出")
                
                user_input = input("\n您的选择: ").strip()
                
                if user_input.lower() in ['ok', 'yes']:
                    print(f"\n开始第 {i+1}/{max_iterations} 轮迭代优化...")
                    
                    # 判断是否需要继续迭代
                    should_iterate = await self.should_continue_iteration(evaluation_results)
                    if not should_iterate:
                        print("\n评估结果已达标，无需继续迭代")
                        self.logger.info("评估结果已达标，无需继续迭代")
                        break
                    
                    # 应用调整并重新运行
                    iteration_success = await self.run_iteration(evaluation_results)
                    if iteration_success:
                        print("\n✓ 配置已调整，重新运行模拟...")
                        simulation_results_path = await self.run_simulation(coding_results)
                        
                        if simulation_results_path:
                            print("\n✓ 模拟运行成功，重新评估...")
                            evaluation_results = await self.run_evaluation_phase(simulation_results_path)
                            iteration_history.append({
                                'iteration': i + 1,
                                'results': evaluation_results
                            })
                            print(f"\n✅ 第 {i+1} 轮迭代完成")
                        else:
                            print(f"\n❌ 第 {i+1} 轮模拟运行失败")
                            break
                    else:
                        print(f"\n❌ 第 {i+1} 轮配置调整失败")
                        break
                elif user_input.lower() == 'quit':
                    print("\n用户终止流程")
                    self.logger.info("用户终止流程")
                    break
                else:
                    print("\n跳过迭代优化")
                    self.logger.info("用户选择跳过迭代优化")
                    break
            
            # 生成最终报告
            if iteration_history:
                print("\n" + "=" * 80)
                print("阶段 7: 生成最终报告")
                print("=" * 80)
                self.logger.info("\n阶段 7: 生成最终报告")
                
                try:
                    results_dir = os.path.join(self.current_project_dir, 'results')
                    analyst = ResearchAnalystAgent(
                        agent_id='research_analyst_001',
                        output_dir=results_dir,
                        docs_dir=self.docs_dir
                    )
                    final_summary = await analyst.generate_optimization_summary(iteration_history)
                    print("\n✅ 最终优化报告已生成")
                    self.logger.info("最终优化报告已生成")
                except Exception as e:
                    print(f"\n❌ 报告生成失败: {e}")
                    self.logger.error(f"报告生成失败: {e}")
        
        # ============ 完成 ============
        print("\n" + "=" * 80)
        print("交互式工作流程完成！")
        print("=" * 80)
        print(f"\n项目目录: {project_dir}")
        print(f"配置目录: {self.current_config_dir}")
        print(f"\n设计版本数: {len(phase_history['design'])}")
        print(f"编码版本数: {len(phase_history['coding'])}")
        if iteration_history:
            print(f"迭代优化轮数: {len(iteration_history)}")
        
        self.logger.info("=" * 80)
        self.logger.info("交互式工作流程完成")
        self.logger.info(f"项目目录: {project_dir}")
        self.logger.info("=" * 80)
        
        return {
            'status': 'completed',
            'project_dir': project_dir,
            'config_dir': self.current_config_dir,
            'design_results': design_results,
            'coding_results': coding_results,
            'simulation_results': simulation_results_path,
            'evaluation_results': evaluation_results,
            'iteration_history': iteration_history,
            'history': phase_history
        }

    async def should_continue_iteration(self, evaluation_results):
        """
        判断是否应该继续迭代优化。
        """
        prompt = self.prompts['should_continue_iteration_prompt'].format(
            evaluation_report=evaluation_results.get('evaluation_report', ''),
            metrics_analysis=evaluation_results.get('metrics_analysis', '')
        )
        
        response = await self.generate_llm_response(prompt)
        try:
            result = json.loads(response)
            return result.get('should_continue', False)
        except Exception:
            return False
