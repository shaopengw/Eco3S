
from src.utils.custom_logger import CustomLogger
from .shared_imports import *
from .sim_architect import SimArchitectAgent
from .code_architect import CodeArchitectAgent
from .research_analyst import ResearchAnalystAgent
from .mechanism_interpreter import MechanismInterpreterAgent

class ProjectMasterAgent(BaseAgent):
    """
    项目管理师Agent，继承BaseAgent，负责协调整个实验流程，调用其他agent并进行质量控制。
    """
    def __init__(self, agent_id, docs_dir, config_template_dir, web_mode=False, session_callback=None, session=None):
        super().__init__(agent_id, group_type='project_master', window_size=5)
        self.docs_dir = docs_dir
        self.config_template_dir = config_template_dir
        self.current_project_dir = None
        self.current_config_dir = None
        self.current_simulation_name = None
        self.max_regeneration_attempts = 3
        self.logger = CustomLogger('project_master').logger
        self.web_mode = web_mode  # Web模式标志
        self.session = session  # 存储session对象
        self.auto_mode = False  # 完全自动模式标志（run_full_workflow内启用）
        self._auto_scaled_up_after_prototype = False  # 自动模式：原型跑通后是否已放大规模
        
        # 子Agent实例（延迟初始化）
        self.code_architect = None
        self.mechanism_interpreter = None
        
        # 加载提示词配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'project_master_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']

    def _is_small_scale_config(self, config_path: str) -> bool:
        """判断配置是否为原型小规模（pop=5, steps/years=1）。"""
        if not config_path or not os.path.exists(config_path):
            return False
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            simulation_cfg = config_data.get('simulation', {}) or {}
            pop = simulation_cfg.get('initial_population')

            steps = None
            time_cfg = simulation_cfg.get('time')
            if isinstance(time_cfg, dict):
                steps = time_cfg.get('total_steps')
            if steps is None:
                steps = simulation_cfg.get('total_years')

            return pop == 5 and steps == 1
        except Exception as e:
            self.logger.warning(f"检查小规模配置失败: {e}")
            return False

    def _scale_up_simulation_config(self, config_path: str, target_population: int = 100, target_steps: int = 10) -> bool:
        """将原型配置放大到可评估规模。

        - initial_population -> target_population
        - simulation.time.total_steps 或 simulation.total_years -> target_steps
        """
        if not config_path or not os.path.exists(config_path):
            return False

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}

            if not isinstance(config_data, dict):
                return False

            simulation_cfg = config_data.setdefault('simulation', {})
            if not isinstance(simulation_cfg, dict):
                simulation_cfg = {}
                config_data['simulation'] = simulation_cfg

            simulation_cfg['initial_population'] = int(target_population)

            time_cfg = simulation_cfg.get('time')
            if isinstance(time_cfg, dict) and 'total_steps' in time_cfg:
                time_cfg['total_steps'] = int(target_steps)
            else:
                # 默认使用 total_years 作为时间步/周期配置
                simulation_cfg['total_years'] = int(target_steps)

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

            self.logger.info(f"✓ 已放大实验规模: pop={target_population}, steps={target_steps}")
            return True
        except Exception as e:
            self.logger.error(f"放大实验规模失败: {e}")
            return False
    
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
        
        # 如果是Web模式，通过session发送确认请求
        if self.web_mode and self.session:
            try:
                # 发送提示信息到前端
                if 'output_queue' in self.session:
                    import time
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
                    self.session['output_queue'].put(f"[{timestamp}] 检测到 {step_name} 的所有文件已存在:")
                    for f in check_files:
                        self.session['output_queue'].put(f"[{timestamp}]   ✓ {f}")
                    self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
                
                # 设置等待确认状态
                self.session['waiting_confirmation'] = True
                self.session['confirmation_message'] = f"检测到 {step_name} 的所有文件已存在，是否重新生成？"
                self.session['confirmation_type'] = 'yes_no'
                self.session['confirmation_options'] = []
                self.session['user_confirmation'] = None
                
                # 等待用户响应（最多等待5分钟）
                max_wait_time = 300  # 5分钟
                wait_time = 0
                while wait_time < max_wait_time:
                    if not self.session.get('waiting_confirmation', False):
                        # 用户已响应
                        user_confirmed = self.session.get('user_confirmation', False)
                        if user_confirmed:
                            self.logger.info(f"用户选择重新执行步骤: {step_name}")
                            return True
                        else:
                            self.logger.info(f"用户选择跳过步骤: {step_name}")
                            if 'output_queue' in self.session:
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                self.session['output_queue'].put(f"[{timestamp}] ✓ 跳过步骤: {step_name}")
                            return False
                    time.sleep(0.5)
                    wait_time += 0.5
                
                # 超时，默认跳过
                self.logger.warning(f"等待用户确认超时，跳过步骤: {step_name}")
                self.session['waiting_confirmation'] = False
                return False
                
            except Exception as e:
                self.logger.warning(f"Web模式确认失败: {e}，使用命令行模式")
        
        # 非Web模式，使用命令行确认
        user_input = input("是否重新生成？(y/yes=重新生成, 其他=跳过使用现有文件): ").strip().lower()
        
        if user_input in ['y', 'yes']:
            self.logger.info(f"用户选择重新执行步骤: {step_name}")
            return True
        else:
            self.logger.info(f"用户选择跳过步骤: {step_name}")
            print(f"✓ 跳过步骤: {step_name}")
            return False

    def _read_modules_config(self, full_config=False):
        """读取模块配置文件内容
        
        Args:
            full_config: 是否读取完整配置，默认只读取selected_modules
        
        Returns:
            str: 模块配置的YAML内容，如果文件不存在返回空字符串
        """
        modules_config_path = os.path.join(self.current_config_dir, 'modules_config.yaml')
        if os.path.exists(modules_config_path):
            with open(modules_config_path, 'r', encoding='utf-8') as f:
                if full_config:
                    return f.read()
                else:
                    # 只读取selected_modules部分
                    config = yaml.safe_load(f)
                    if config and 'selected_modules' in config:
                        return yaml.dump({'selected_modules': config['selected_modules']}, allow_unicode=True)
                    return ""
        return ""

    def _get_latest_result_file(self):
        """
        查找 self.current_project_dir 下最新的结果文件。
        """
        subdirs = [os.path.join(self.current_project_dir, d) for d in os.listdir(self.current_project_dir) if os.path.isdir(os.path.join(self.current_project_dir, d))]
        
        # 遍历所有子目录，找到包含结果文件的目录
        all_result_files = []
        for subdir in subdirs:
            try:
                result_files = [os.path.join(subdir, f) for f in os.listdir(subdir) if f.endswith(('.json', '.csv'))]
                all_result_files.extend(result_files)
            except Exception as e:
                self.logger.warning(f"无法读取目录 {subdir}: {e}")
                continue
        
        # 如果找到了结果文件，返回最新的一个
        if all_result_files:
            latest_file = max(all_result_files, key=os.path.getmtime)
            self.logger.info(f"找到结果文件: {latest_file}")
            return latest_file
        
        self.logger.warning("❌ 未找到任何结果文件")
        return None

    async def parse_user_requirement(self, requirement_text, user_specified_type=None):
        """
        解析用户需求，确定模拟名称、基本信息和模拟类型。
        
        Args:
            requirement_text: 用户需求文本
            user_specified_type: 用户指定的模拟类型，如果为None则由AI判断
        """
        prompt = self.prompts['parse_user_requirement_prompt'].format(
            requirement_text=requirement_text
        )

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            response = await self.generate_llm_response(prompt)
            try:
                # 尝试提取JSON（处理Markdown代码块）
                response = response.strip()
                if response.startswith('```'):
                    # 移除代码块标记
                    lines = response.split('\n')
                    response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
                parsed = json.loads(response)
                
                # 如果用户指定了模拟类型，使用用户指定的类型
                if user_specified_type:
                    parsed['simulation_type'] = user_specified_type
                    self.logger.info(f"使用用户指定的模拟类型: {user_specified_type}")
                # 如果LLM没有返回simulation_type，默认为decision
                elif 'simulation_type' not in parsed:
                    parsed['simulation_type'] = 'decision'
                    self.logger.info("AI未判断出模拟类型，使用默认类型: decision")
                else:
                    self.logger.info(f"AI判断的模拟类型: {parsed['simulation_type']}")
                
                return parsed
            except Exception as e:
                self.logger.error(f"解析需求失败（第{attempt}次）: {e}, 响应内容: {response[:200]}")
                if attempt == max_attempts:
                    self.logger.error("需求解析连续失败，系统终止。")
                    raise RuntimeError("需求解析失败，系统终止。请检查输入或提示词。")

    async def initialize_project(self, simulation_name):
        """
        创建项目文件夹结构。
        配置文件放在 config/[模拟名称] 文件夹下。
        """
        # 项目根目录（Eco3S项目根目录）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 创建 config/[模拟名称] 文件夹
        config_dir = os.path.join(project_root, 'config', simulation_name)
        os.makedirs(config_dir, exist_ok=True)
        
        # 创建实验数据文件夹
        history_dir = os.path.join(project_root, 'history', simulation_name)
        os.makedirs(history_dir, exist_ok=True)
        
        # 在实验数据文件夹下创建子文件夹
        subdirs = ['results', 'logs']
        for subdir in subdirs:
            os.makedirs(os.path.join(history_dir, subdir), exist_ok=True)
        
        self.current_project_dir = history_dir
        self.current_config_dir = config_dir
        self.current_simulation_name = simulation_name
        self.logger.info(f"配置文件夹已创建: {config_dir}")
        self.logger.info(f"实验文件夹已创建: {history_dir}")
        
        return history_dir

    async def run_design_phase(self, original_requirement, requirement_dict, previous_version=None, user_feedback=None):
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
        simulation_type = requirement_dict.get('simulation_type', 'decision')  # 默认为决策型

        # 使用项目根目录下的config_[模拟名称]文件夹
        designer = SimArchitectAgent(
            agent_id='sim_architect_001',
            output_dir=self.current_config_dir,
            docs_dir=self.docs_dir,
            config_dir=self.config_template_dir,
            simulation_type=simulation_type,
        )
        
        # 直接使用传入的已解析需求
        parsed_req = requirement_dict
        self.logger.info(f"使用已解析的需求: {parsed_req}")
        
        # 从解析结果中获取模拟类型
        simulation_type = parsed_req.get('simulation_type', 'decision')
        self.logger.info(f"模拟类型: {simulation_type}")
        
        # 生成设计文档
        self.logger.info("步骤 1: 生成设计文档")
        
        # 检查是否已存在设计文档
        desc_path = os.path.join(self.current_config_dir, 'description.md')
        should_generate_desc = True
        
        if os.path.exists(desc_path) and not (previous_version and user_feedback):
            print(f"\n{'='*60}")
            print(f"发现已存在的设计文档")
            print(f"路径: {desc_path}")
            print(f"{'='*60}")
            
            # 如果是Web模式，通过session发送确认请求
            if self.web_mode and self.session:
                try:
                    # 发送提示信息到前端
                    if 'output_queue' in self.session:
                        import time
                        from datetime import datetime
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
                        self.session['output_queue'].put(f"[{timestamp}] 发现已存在的设计文档")
                        self.session['output_queue'].put(f"[{timestamp}] 路径: {desc_path}")
                        self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
                    
                    # 设置等待确认状态
                    self.session['waiting_confirmation'] = True
                    self.session['confirmation_message'] = "发现已存在的设计文档，是否重新生成？"
                    self.session['confirmation_type'] = 'yes_no'
                    self.session['confirmation_options'] = []
                    self.session['user_confirmation'] = None
                    
                    # 等待用户响应（最多等待5分钟）
                    max_wait_time = 300
                    wait_time = 0
                    while wait_time < max_wait_time:
                        if not self.session.get('waiting_confirmation', False):
                            user_confirmed = self.session.get('user_confirmation', False)
                            if not user_confirmed:
                                self.logger.info("跳过生成，使用现有设计文档")
                                if 'output_queue' in self.session:
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    self.session['output_queue'].put(f"[{timestamp}] ✓ 跳过，使用现有设计文档")
                                with open(desc_path, 'r', encoding='utf-8') as f:
                                    description_md = f.read()
                                should_generate_desc = False
                                break
                            else:
                                # 用户选择重新生成
                                break
                        time.sleep(0.5)
                        wait_time += 0.5
                    
                    # 超时，默认跳过
                    if wait_time >= max_wait_time:
                        self.logger.warning("等待用户确认超时，跳过生成")
                        self.session['waiting_confirmation'] = False
                        with open(desc_path, 'r', encoding='utf-8') as f:
                            description_md = f.read()
                        should_generate_desc = False
                        
                except Exception as e:
                    self.logger.warning(f"Web模式确认失败: {e}，使用命令行模式")
            else:
                # 非Web模式，使用命令行确认
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
                original_requirement,
                design_context.get('parsed_req'),
                design_context.get('previous_description'),
                design_context.get('user_feedback')
            )
            
            if description_md:
                with open(desc_path, 'w', encoding='utf-8') as f:
                    f.write(description_md)
                self.logger.info(f"设计文档已保存: {desc_path}")
        
        # 生成配置文件（modules_config.yaml）
        self.logger.info("步骤 2: 生成模块配置文件 (modules_config.yaml)")
        
        # 检查是否已存在模块配置文件
        modules_config_path = os.path.join(self.current_config_dir, 'modules_config.yaml')
        should_generate_modules_config = True
        
        if os.path.exists(modules_config_path) and not (previous_version and user_feedback):
            print(f"\n{'='*60}")
            print(f"发现已存在的模块配置文件")
            print(f"路径: {modules_config_path}")
            print(f"{'='*60}")
            
            # 如果是Web模式，通过session发送确认请求
            if self.web_mode and self.session:
                try:
                    if 'output_queue' in self.session:
                        import time
                        from datetime import datetime
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
                        self.session['output_queue'].put(f"[{timestamp}] 发现已存在的模块配置文件")
                        self.session['output_queue'].put(f"[{timestamp}] 路径: {modules_config_path}")
                        self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
                    
                    self.session['waiting_confirmation'] = True
                    self.session['confirmation_message'] = "发现已存在的模块配置文件，是否重新生成？"
                    self.session['confirmation_type'] = 'yes_no'
                    self.session['confirmation_options'] = []
                    self.session['user_confirmation'] = None
                    
                    max_wait_time = 300
                    wait_time = 0
                    while wait_time < max_wait_time:
                        if not self.session.get('waiting_confirmation', False):
                            user_confirmed = self.session.get('user_confirmation', False)
                            if not user_confirmed:
                                self.logger.info("跳过生成，使用现有模块配置文件")
                                if 'output_queue' in self.session:
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    self.session['output_queue'].put(f"[{timestamp}] ✓ 跳过，使用现有模块配置文件")
                                should_generate_modules_config = False
                                break
                            else:
                                break
                        time.sleep(0.5)
                        wait_time += 0.5
                    
                    if wait_time >= max_wait_time:
                        self.logger.warning("等待用户确认超时，跳过生成")
                        self.session['waiting_confirmation'] = False
                        should_generate_modules_config = False
                        
                except Exception as e:
                    self.logger.warning(f"Web模式确认失败: {e}，使用命令行模式")
            else:
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
        
        modules_config_yaml = self._read_modules_config(full_config=False)
        
        return {
            'parsed_requirement': parsed_req,
            'description_md': description_md,
            'config_files': config_files,
            'modules_config_yaml': modules_config_yaml,
            'simulation_type': simulation_type
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
        
        # 获取模拟类型
        simulation_type = design_results.get('simulation_type', 'decision')  # 默认为决策型
        self.logger.info(f"编码阶段使用模拟类型: {simulation_type}")
        
        # 创建或复用 CodeArchitectAgent 实例
        if not self.code_architect:
            self.code_architect = CodeArchitectAgent(
                agent_id='code_architect_001',
                simulator_output_dir=simulator_dir,
                main_output_dir=entrypoints_dir,
                docs_dir=self.docs_dir,
                config_dir=self.current_config_dir,
                config_template_dir=self.config_template_dir,
                simulation_name=self.current_simulation_name,
                simulation_type=simulation_type,  # 传递模拟类型
                session=self.session,  # 传递session对象
                auto_mode=self.auto_mode,
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
        
        # === 步骤4.1: 完善数据可视化及保存代码 ===
        self.logger.info("步骤 4.1: 完善数据可视化及保存代码")
        visualization_dir = "src\\visualization\\plot_results.py"

        refined_visualization = await coder.refine_visualization_code(
            visualization_dir,
            simulator_file_path,
            main_file_path,
            description_with_context
        )

        if refined_visualization:
            self.logger.info("数据可视化及保存代码已完善")
        else:
            self.logger.warning("数据可视化及保存代码完善失败，保持原文件")
        
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
            modules_config_yaml = self._read_modules_config(full_config=True)
            
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
        for module_name, prompt_filename in prompt_file_mapping.items():
            self.logger.info(f"  生成提示词文件: {prompt_filename} (来自模块: {module_name})")
            description_with_prompt_context = description_content + prev_prompt_context
            generated_paths = await coder.generate_prompt_file(
                prompt_filename,
                description_with_prompt_context,
                config_files
            )
            if generated_paths:
                prompt_files.extend(generated_paths)
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
            bool: True表示成功，False表示失败
        """
        self.logger.info("=" * 50)
        self.logger.info("运行模拟程序")
        self.logger.info("=" * 50)
        
        # 获取文件路径
        main_files = coding_results.get('main_files', [])
        simulator_files = coding_results.get('simulator_files', [])
        
        if not main_files or not simulator_files:
            self.logger.error("❌ 缺少必要的文件（main或simulator）")
            return False
        
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
                    errors='replace',  
                    env=env
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
                                config_path=config_path,
                                max_attempts=3
                            )
                            
                            if fixed:
                                self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                                continue  # 重新运行
                            else:
                                self.logger.error("❌ 编码师修复失败")
                            return False
                        else:
                            self.logger.error("❌ 已达到最大运行尝试次数")
                        return False
                    
                    self.logger.info("✅ 程序运行成功！")
                    self.logger.info(f"输出:\n{result.stdout}")

                    # 检查是否是小规模测试（人口=5，步数=1）
                    is_small_scale = False
                    try:
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config_data = yaml.safe_load(f)
                                # Check population
                                pop = config_data.get('simulation', {}).get('initial_population')
                                # Check steps
                                steps = config_data.get('simulation', {}).get('time', {}).get('total_steps')
                                if steps is None:
                                    steps = config_data.get('simulation', {}).get('total_years')
                                print(f"实验结束：pop={pop}, steps={steps}")
                                if pop == 5 and steps == 1:
                                    is_small_scale = True
                    except Exception as e:
                        self.logger.warning(f"检查配置文件是否为小规模测试时出错: {e}")
                    
                    if is_small_scale:
                        print(f"\n{'='*60}")
                        print("原型测试（小规模）已完成！")
                        print(f"{'='*60}")
                        # 返回特殊标记，表示原型测试完成
                        return 'small_scale_completed'
                    
                    return True
                                

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
                            config_path=config_path,
                            max_attempts=3  # 编码师内部的修复尝试次数
                        )
                        
                        if fixed:
                            self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                        else:
                            self.logger.error("❌ 编码师修复失败")
                            if attempt == max_fix_attempts - 1:
                                self.logger.error("已达到最大修复次数，停止尝试")
                            return False
                    else:
                        self.logger.error("❌ 已达到最大运行尝试次数")
                        return False
                        
            except subprocess.TimeoutExpired:
                self.logger.error("❌ 程序运行超时（超过5分钟）")
                return False
            except Exception as e:
                self.logger.error(f"❌ 运行时发生异常: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return False
        
        return None

    async def run_evaluation_and_optimization_phase(self, simulation_successful):
        """
        运行评估并优化阶段，调用 ResearchAnalystAgent。
        根据结果评估是否符合预期，如果不符合则自动修改配置。
        """
        self.logger.info("=" * 50)
        self.logger.info("开始评估结果并优化阶段")
        self.logger.info("=" * 50)
        
        # 获取 self.current_project_dir 下最新的文件夹
        # subdirs = [os.path.join(self.current_project_dir, d) for d in os.listdir(self.current_project_dir) if os.path.isdir(os.path.join(self.current_project_dir, d))]
        # results_dir = max(subdirs, key=os.path.getmtime)

        simulation_results_path = self._get_latest_result_file()
        if simulation_successful:
            self.logger.info("模拟运行成功，开始评估结果并优化阶段。")
            self.logger.info(f"获取模拟结果{simulation_results_path}")
        elif simulation_results_path:
            self.logger.info(f"模拟失败，自动获取上次实验结果{simulation_results_path}")
        else:
            # 如果模拟失败且没有上一次的结果，则尝试查找最新的结果文件
            self.logger.warning("模拟运行失败，且未找到结果。")
            return {'evaluation_report': "模拟失败，且未找到结果", 'needs_adjustment': False, 'optimization_completed': False}

        # 获取结果文件所在的目录
        results_dir = os.path.dirname(simulation_results_path)
        
        analyst = ResearchAnalystAgent(
            agent_id='research_analyst_001',
            output_dir=results_dir,
            config_dir=self.current_config_dir
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
            diagnosis_path = await analyst.diagnose_config_issues(
                evaluation_report,
                design_doc=design_doc
            )
            self.logger.info("诊断结果已生成")
            
            # === 步骤 3: 依次修改文件 ===
            self.logger.info("步骤 3: 根据诊断结果依次修改配置文件")
            
            # 检查是否是自动模式
            # 读取诊断结果
            with open(diagnosis_path, 'r', encoding='utf-8') as f:
                diagnosis_result = json.load(f)
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"检测到配置需要调整，等待用户确认")
            self.logger.info(f"{'='*60}")
            
            # 返回结果，等待用户确认
            return {
                'evaluation_report': evaluation_report,
                'needs_adjustment': True,
                'diagnosis_path': diagnosis_path,
                'diagnosis_result': diagnosis_result,
                'waiting_user_confirmation': True  # 标记等待用户确认
            }
        else:
            self.logger.info("✓ 结果符合预期，无需调整")
            return {
                'evaluation_report': evaluation_report,
                'needs_adjustment': False,
                'optimization_completed': True
            }
    
    async def apply_optimization_adjustments(self, diagnosis_path, design_doc=None):
        """
        应用优化调整，根据诊断结果修改配置文件
        
        Args:
            diagnosis_path: 诊断结果文件路径
            design_doc: 设计文档内容（可选）
        
        Returns:
            dict: 修改结果
        """
        self.logger.info("="*50)
        self.logger.info("开始应用优化调整")
        self.logger.info("="*50)
        
        coder = self.code_architect
        
        # 依次修改文件
        modification_results = await coder.modify_file_sequentially(
            diagnosis_path,
            self.current_config_dir,
            design_doc=design_doc
        )
        
        if modification_results:
            self.logger.info(f"✓ 已完成 {len(modification_results)} 个文件的修改")
            return {
                'success': True,
                'modification_results': modification_results,
                'message': f'成功修改了 {len(modification_results)} 个文件'
            }
        else:
            self.logger.warning("未成功修改任何文件")
            return {
                'success': False,
                'modification_results': [],
                'message': '未成功修改任何文件'
            }



    async def run_full_workflow(self, requirement_text, max_iterations=5):
        """
        运行完整的工作流程。
        
        Args:
            requirement_text: 用户需求描述
            max_iterations: 最大迭代次数
        
        Returns:
            完整的执行结果
        """
        print("开始运行完整工作流程...")
        self.auto_mode = True
        self._auto_scaled_up_after_prototype = False
        self.logger.info("=" * 80)
        self.logger.info("开始完整工作流程")
        self.logger.info("=" * 80)
        
        # 1. 解析需求并初始化项目
        self.logger.info("\n阶段 1: 需求分析和项目初始化")
        requirement_dict = await self.parse_user_requirement(requirement_text)
        project_dir = await self.initialize_project(requirement_dict['simulation_name'])
        
        # 2. 设计阶段
        self.logger.info("\n阶段 2: 系统设计")
        design_results = await self.run_design_phase(requirement_text, requirement_dict)
        
        # 3. 编码阶段
        self.logger.info("\n阶段 3: 代码生成")
        coding_results = await self.run_coding_phase(design_results)
        
        # 4-5. 运行模拟和评估优化循环
        optimization_history = []
        for iteration in range(1, max_iterations + 1):
            # 阶段 4: 运行模拟
            self.logger.info(f"\n阶段 4: 运行模拟 (第 {iteration} 轮)")
            simulation_successful = await self.run_simulation(coding_results, max_fix_attempts=10)

            # 自动模式：原型小规模跑通一次后，自动放大规模并重新实验
            if (
                self.auto_mode
                and simulation_successful == 'small_scale_completed'
                and not self._auto_scaled_up_after_prototype
            ):
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                simulation_name = self.current_simulation_name
                config_path = os.path.join(project_root, 'config', simulation_name, 'simulation_config.yaml')

                # 仅当确实还是小规模配置时才放大
                if self._is_small_scale_config(config_path):
                    self.logger.info("原型测试成功，自动放大模拟人数与时间步以获得可评估结果...")
                    if self._scale_up_simulation_config(config_path, target_population=100, target_steps=10):
                        self._auto_scaled_up_after_prototype = True
                        simulation_successful = await self.run_simulation(coding_results, max_fix_attempts=10)
                    else:
                        self.logger.error("❌ 自动放大规模失败，工作流程终止")
                        break
                else:
                    # 配置已不再是小规模（可能被外部修改），直接继续
                    self._auto_scaled_up_after_prototype = True
            
            if not simulation_successful:
                self.logger.error("❌ 模拟运行失败，工作流程终止")
                break
            
            self.logger.info("✅ 模拟运行完成")
            
            # 阶段 5: 评估结果并优化
            self.logger.info(f"\n阶段 5: 评估结果并优化 (第 {iteration} 轮)")
            evaluation_results = await self.run_evaluation_and_optimization_phase(True)
            
            optimization_history.append({
                'iteration': iteration,
                'simulation_successful': simulation_successful,
                'evaluation_results': evaluation_results
            })
            
            # 如果评估结果符合预期，退出循环
            if evaluation_results.get('optimization_completed', False):
                self.logger.info("✅ 评估结果符合预期，优化完成")
                break
            
            # 如果不需要调整，也退出循环
            if not evaluation_results.get('needs_adjustment', False):
                self.logger.info("✅ 无需进一步调整，优化完成")
                break
            
            if iteration >= max_iterations:
                self.logger.info(f"已达到最大迭代次数 ({max_iterations})，停止优化")
                break
        
        self.logger.info("=" * 80)
        self.logger.info("工作流程完成")
        self.logger.info(f"项目目录: {project_dir}")
        self.logger.info("=" * 80)

        self.auto_mode = False
        
        return {
            'status': 'completed',
            'project_dir': project_dir,
            'design_results': design_results,
            'coding_results': coding_results,
            'optimization_history': optimization_history
        }

    async def run_mechanism_interpretation_session(self, coding_results=None):
        """
        运行机制解释与调整会话，收集用户的调整需求
        
        Args:
            coding_results: 编码阶段的结果（可选）
        
        Returns:
            str: 格式化的需求字符串 或 None
        """
        self.logger.info("="*50)
        self.logger.info("开始机制解释与调整会话")
        self.logger.info("="*50)
        
        # 获取simulator和main文件路径
        simulator_path = None
        main_path = None
        
        if coding_results:
            if coding_results.get('simulator_files'):
                simulator_path = coding_results['simulator_files'][0]
            if coding_results.get('main_files'):
                main_path = coding_results['main_files'][0]
        
        # 创建或复用 MechanismInterpreterAgent 实例
        if not self.mechanism_interpreter:
            self.mechanism_interpreter = MechanismInterpreterAgent(
                agent_id='mechanism_interpreter_001',
                config_dir=self.current_config_dir,
                simulator_path=simulator_path,
                main_path=main_path
            )
        
        # 运行交互式调整会话（收集调整需求，不直接应用）
        try:
            requirements_text = await self.mechanism_interpreter.interactive_adjustment_session()
            
            # 直接返回格式化的需求字符串
            if requirements_text:
                return requirements_text
            
            return None
            
        except Exception as e:
            self.logger.error(f"机制解释与调整会话失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    async def apply_mechanism_adjustments(self, requirements_text):
        """
        应用机制调整，调用CodeArchitectAgent进行具体的代码修改
        
        Args:
            requirements_text: 格式化的需求字符串
        
        Returns:
            bool: 是否成功应用
        """
        self.logger.info("开始应用机制调整")
        self.logger.info(f"需求内容:\n{requirements_text}")
        
        try:
            # 确保CodeArchitectAgent已初始化
            if not self.code_architect:
                self.logger.error("CodeArchitectAgent未初始化")
                return False
            
            # 直接将需求文本传给CodeArchitectAgent处理
            print(f"\n{'='*80}")
            print("将需求发送给编码师Agent进行实现...")
            print(f"{'='*80}")
            
            # 调用CodeArchitectAgent的apply_user_adjustment方法
            success = await self.code_architect.apply_user_adjustment(
                requirements_text=requirements_text
            )
            
            if success:
                print(f"\n✓ 需求实现完成")
                self.logger.info("需求实现成功")
            else:
                print(f"\n✗ 需求实现失败")
                self.logger.warning("需求实现失败")
            
            return success
            
        except Exception as e:
            self.logger.error(f"应用机制调整失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
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

        self.auto_mode = False
        
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
        
        # 询问用户是否指定模拟类型
        print("\n请选择模拟类型（如不选择，AI将自动判断）：")
        print("  1. decision - 决策型模拟")
        print("     特征：居民需要进行经济决策、就业选择、迁移等复杂行为")
        print("     适用场景：经济活动、就业、政府政策、税收、GDP等")
        print("  2. survey - 调查型模拟")
        print("     特征：居民主要进行信息交流、传播和问卷调查")
        print("     适用场景：信息传播、舆论调查、知识扩散、问卷调查、社交网络影响等")
        print("  3. 按Enter跳过，让AI自动判断")
        
        user_type_input = input("\n请输入选项（1/2/Enter）: ").strip()
        
        user_specified_type = None
        if user_type_input == '1':
            user_specified_type = 'decision'
            print("✓ 已选择：decision（决策型模拟）")
        elif user_type_input == '2':
            user_specified_type = 'survey'
            print("✓ 已选择：survey（调查型模拟）")
        else:
            print("✓ 将由AI自动判断模拟类型")
        
        requirement_dict = await self.parse_user_requirement(requirement_text, user_specified_type)
        project_dir = await self.initialize_project(requirement_dict['simulation_name'])
        
        print(f"\n✓ 项目已初始化")
        print(f"  - 模拟名称: {requirement_dict['simulation_name']}")
        print(f"  - 模拟类型: {requirement_dict['simulation_type']}")
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
                requirement_text,
                requirement_dict,
                previous_version=previous_design,
                user_feedback=user_feedback
            )
            
            # 显示结果
            print("\n设计阶段完成！")
            print(f"\n✓ 需求解析结果:")
            print(f"  {json.dumps(design_results['parsed_requirement'], ensure_ascii=False, indent=2)}")
            print(f"\n✓ 设计文档: {self.current_config_dir}/description.md")
            
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
            print("\n您可直接修改实验设计文档，所有后续代码将严格依此生成，请确保其准确反映您的需求。")
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
            print("  - 输入 'ok' 或 'yes' 进入运行模拟阶段")
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
        
        # ============ 阶段 4-5: 运行模拟和评估优化循环 ============
        print("\n" + "=" * 80)
        print("阶段 4-5: 运行模拟和评估优化循环")
        print("=" * 80)
        self.logger.info("\n阶段 4-5: 运行模拟和评估优化循环")
        
        optimization_history = []
        max_iterations = 3
        
        for iteration in range(1, max_iterations + 1):
            print(f"\n{'='*60}")
            print(f"第 {iteration} 轮优化")
            print(f"{'='*60}")
            
            # 阶段 4: 运行模拟
            print(f"\n阶段 4: 运行模拟 (第 {iteration} 轮)")
            
            simulation_successful = False
            
            print("\n是否运行模拟程序？")
            print("  - 输入 'ok' 或 'yes' 运行模拟")
            print("  - 输入 'skip' 跳过模拟运行")
            print("  - 输入 'quit' 退出")
            
            user_input = input("\n您的选择: ").strip()
            
            if user_input.lower() == 'quit':
                print("\n用户退出流程")
                break
            elif user_input.lower() == 'skip':
                print("\n跳过模拟运行")
            else:  # 'ok', 'yes' 或默认
                print("\n开始运行模拟...")
                self.logger.info(f"开始第 {iteration} 轮模拟运行")
                
                sim_result = await self.run_simulation(coding_results, max_fix_attempts=10)
                
                # 检查是否是原型测试完成
                if sim_result == 'small_scale_completed':
                    print("\n✅ 原型测试运行成功！")
                    self.logger.info(f"第 {iteration} 轮原型测试运行成功")
                    
                    # 提供机制解释与调整选项
                    while True:
                        print("\n请选择下一步操作：")
                        print("  - 输入 'adjust' 进入机制解释与调整会话")
                        print("  - 输入 'continue' 继续进行大规模测试")
                        print("  - 输入 'quit' 退出")
                        
                        next_action = input("\n您的选择: ").strip().lower()
                        
                        if next_action == 'adjust':
                            # 进入机制解释与调整会话
                            print("\n进入机制解释与调整会话...")
                            self.logger.info("用户选择进入机制解释与调整会话")
                            
                            try:
                                requirements_text = await self.run_mechanism_interpretation_session(coding_results)
                                
                                if requirements_text:
                                    # 显示需求内容
                                    print("\n" + "="*80)
                                    print("收集到的需求:")
                                    print("="*80)
                                    print(requirements_text)
                                    print("="*80)
                                    
                                    # 询问是否应用调整
                                    print("\n是否应用这些调整？")
                                    print("  - 输入 'yes' 或 'y' 应用调整")
                                    print("  - 输入其他内容取消")
                                    
                                    apply_input = input("\n您的选择: ").strip().lower()
                                    
                                    if apply_input in ['yes', 'y']:
                                        print("\n开始应用调整...")
                                        self.logger.info("开始应用机制调整")
                                        
                                        apply_success = await self.apply_mechanism_adjustments(requirements_text)
                                        
                                        if apply_success:
                                            print(f"\n✓ 调整应用完成")
                                            self.logger.info("机制调整完成")
                                            
                                            # 询问是否重新运行小规模测试
                                            print("\n调整已应用，是否重新运行小规模测试验证？")
                                            print("  - 输入 'yes' 或 'y' 重新运行小规模测试")
                                            print("  - 按Enter继续选择下一步操作")
                                            
                                            retest_input = input("\n您的选择: ").strip().lower()
                                            if retest_input in ['yes', 'y']:
                                                print("\n重新运行小规模测试...")
                                                sim_result = await self.run_simulation(coding_results, max_fix_attempts=10)
                                                if sim_result != 'small_scale_completed':
                                                    if sim_result:
                                                        print("\n⚠️ 调整后运行成功，但不是小规模测试")
                                                    else:
                                                        print("\n❌ 调整后运行失败")
                                                        simulation_successful = False
                                                        break
                                                continue  # 继续显示选择菜单
                                        else:
                                            print("\n❌ 调整应用失败")
                                            self.logger.error("调整应用失败")
                                    else:
                                        print("\n取消应用调整")
                                else:
                                    print("\n✓ 机制解释与调整会话结束，未收集到调整需求")
                                    self.logger.info("机制解释与调整会话结束，未收集到调整需求")
                                    
                            except Exception as e:
                                print(f"\n❌ 机制解释与调整失败: {e}")
                                self.logger.error(f"机制解释与调整失败: {e}")
                                import traceback
                                self.logger.error(traceback.format_exc())
                                
                        elif next_action == 'continue':
                            # 继续进行大规模测试
                            print("\n准备进行大规模测试...")
                            print("请输入大规模测试参数:")
                            try:
                                new_pop = int(input("人口数量 (默认300): ") or "300")
                                new_steps = int(input("模拟时间步 (默认50): ") or "50")
                                
                                # 更新配置文件
                                config_path = os.path.join(
                                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    'config',
                                    self.current_simulation_name,
                                    'simulation_config.yaml'
                                )
                                
                                with open(config_path, 'r', encoding='utf-8') as f:
                                    config_data = yaml.safe_load(f)
                                
                                # 递归更新函数
                                def update_steps_recursively(data, steps):
                                    if isinstance(data, dict):
                                        for key, value in data.items():
                                            if key in ['total_steps', 'total_years']:
                                                data[key] = steps
                                            else:
                                                update_steps_recursively(value, steps)
                                    elif isinstance(data, list):
                                        for item in data:
                                            update_steps_recursively(item, steps)

                                # Update population
                                if 'simulation' not in config_data: config_data['simulation'] = {}
                                config_data['simulation']['initial_population'] = new_pop
                                
                                # Also update agents count if it exists
                                if 'agents' in config_data and 'resident_agents' in config_data['agents']:
                                    config_data['agents']['resident_agents']['count'] = new_pop

                                # Recursively update steps
                                update_steps_recursively(config_data, new_steps)
                                
                                with open(config_path, 'w', encoding='utf-8') as f:
                                    yaml.dump(config_data, f, allow_unicode=True)
                                
                                self.logger.info(f"配置文件已更新: 人口={new_pop}, 时间步={new_steps}")
                                print("\n开始大规模测试...")
                                
                                # 重新运行模拟
                                sim_result = await self.run_simulation(coding_results, max_fix_attempts=10)
                                if sim_result and sim_result != 'small_scale_completed':
                                    simulation_successful = True
                                    print("\n✅ 大规模测试运行成功！")
                                    self.logger.info(f"第 {iteration} 轮大规模测试运行成功")
                                    break
                                else:
                                    simulation_successful = False
                                    print("\n❌ 大规模测试运行失败")
                                    self.logger.error(f"第 {iteration} 轮大规模测试运行失败")
                                    break
                                    
                            except ValueError:
                                self.logger.error("输入的参数无效，取消大规模测试")
                                simulation_successful = False
                                break
                                
                        elif next_action == 'quit':
                            print("\n用户退出流程")
                            simulation_successful = False
                            break
                        else:
                            print("\n无效的选择，请重新输入")
                    
                    if not simulation_successful and sim_result == 'small_scale_completed':
                        # 用户选择quit或出错，跳出主循环
                        break
                        
                elif sim_result:
                    simulation_successful = True
                    print("\n✅ 模拟运行成功！")
                    self.logger.info(f"第 {iteration} 轮模拟运行成功")
                else:
                    simulation_successful = False
                    print("\n❌ 模拟运行失败")
                    self.logger.error(f"第 {iteration} 轮模拟运行失败")
                    break
            
            # 阶段 5: 评估结果并优化
            print(f"\n阶段 5: 评估结果并优化 (第 {iteration} 轮)")
            

            print("\n开始评估模拟结果...")
            self.logger.info(f"开始第 {iteration} 轮评估")
            
            try:
                evaluation_results = await self.run_evaluation_and_optimization_phase(simulation_successful)
                print("\n✅ 评估完成！")
                
                optimization_history.append({
                    'iteration': iteration,
                   'simulation_successful': simulation_successful,
                    'evaluation_results': evaluation_results
                })
                
                # 判断是否需要继续循环
                if evaluation_results.get('optimization_completed', False):
                    print("\n✅ 评估结果符合预期，优化完成！")
                    self.logger.info("优化完成")
                    break
                elif not evaluation_results.get('needs_adjustment', False):
                    print("\n✅ 无需进一步调整，优化完成！")
                    self.logger.info("无需进一步调整")
                    break
                else:
                    print("\n⚠️  结果需要调整，准备下一轮优化...")
                    if iteration >= max_iterations:
                        print(f"\n已达到最大迭代次数 ({max_iterations})，停止优化")
                        self.logger.info("达到最大迭代次数")
                        break
                    
                    # 询问用户是否继续
                    print(f"\n是否继续第 {iteration + 1} 轮优化？")
                    print("  - 输入 'ok' 或 'yes' 继续")
                    print("  - 输入 'no' 或 'quit' 停止")
                        
                    continue_input = input("\n您的选择: ").strip()
                    if continue_input.lower() not in ['ok', 'yes', '']:
                        print("\n用户选择停止优化")
                        self.logger.info("用户选择停止优化")
                        break
                        
            except Exception as e:
                print(f"\n❌ 评估失败: {e}")
                self.logger.error(f"第 {iteration} 轮评估失败: {e}")
                break
        
        # ============ 完成 ============
        print("\n" + "=" * 80)
        print("交互式工作流程完成！")
        print("=" * 80)
        print(f"\n项目目录: {project_dir}")
        print(f"配置目录: {self.current_config_dir}")
        print(f"\n设计版本数: {len(phase_history['design'])}")
        print(f"编码版本数: {len(phase_history['coding'])}")
        if len(optimization_history) > 0:
            print(f"优化迭代轮数: {len(optimization_history)}")
        
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
            'optimization_history': optimization_history,
            'history': phase_history
        }


