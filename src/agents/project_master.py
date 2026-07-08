
from src.utils.custom_logger import CustomLogger
from src.utils.influence_test_runner import InfluencePreflight
from src.utils.ai_system_config import get_retries
from .shared_imports import *
from .sim_architect import SimArchitectAgent
from .code_architect import CodeArchitectAgent, extract_exogenous_nodes
from .code_fixer import CodeFixerAgent
from .research_analyst import ResearchAnalystAgent
from .mechanism_interpreter import MechanismInterpreterAgent

class ProjectMasterAgent(BaseAgent):
    """
    项目管理师Agent，继承BaseAgent，负责协调整个实验流程，调用其他agent并进行质量控制。
    """

    # 冒烟测试使用的最小规模参数：population=5, years=2
    SMOKE_TEST_POPULATION = 5
    SMOKE_TEST_YEARS = 2

    # 支持的时间步数字段名（按优先级排序）
    TIME_STEP_KEYS = ['total_steps', 'total_years', 'total_quarters', 'total_months', 'total_days', 'total_hours']

    def __init__(self, agent_id, docs_dir, config_template_dir, web_mode=False, session_callback=None, session=None):
        super().__init__(agent_id, group_type='project_master', window_size=5)
        self.docs_dir = docs_dir
        self.config_template_dir = config_template_dir
        self.current_project_dir = None
        self.current_config_dir = None
        self.current_simulation_name = None
        self.retries = get_retries()
        self.max_regeneration_attempts = self.retries['regeneration']
        self.logger = CustomLogger('project_master').logger
        self.web_mode = web_mode  # Web模式标志
        self.session = session  # 存储session对象
        self.auto_mode = False  # 完全自动模式标志（run_full_workflow内启用）
        self._auto_scaled_up_after_prototype = False  # 自动模式：原型跑通后是否已放大规模
        
        # 子Agent实例（延迟初始化）
        self.code_architect = None
        self.code_fixer = None
        self.mechanism_interpreter = None
        
        # 加载提示词配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'project_master_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']
    
    def _is_small_scale_config(self, config_path: str) -> bool:
        """判断配置是否为原型小规模（pop=5, years/steps=2）——即冒烟测试规模。"""
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
                for key in self.TIME_STEP_KEYS:
                    if key in simulation_cfg:
                        steps = simulation_cfg[key]
                        break

            try:
                pop = int(pop)
            except (TypeError, ValueError):
                return False
            try:
                steps = int(steps)
            except (TypeError, ValueError):
                return False

            return pop == self.SMOKE_TEST_POPULATION and steps == self.SMOKE_TEST_YEARS
        except Exception as e:
            self.logger.warning(f"检查小规模配置失败: {e}")
            return False

    def _get_simulation_scale(self, config_path: str) -> dict:
        """读取 simulation_config.yaml 中的人口和时间规模。

        Returns:
            dict: {'population': int or None, 'years': int or None, 'time_key': str or None, 'error': str or None}
        """
        if not config_path:
            return {'population': None, 'years': None, 'time_key': None, 'error': 'config_path 为空'}
        if not os.path.exists(config_path):
            return {'population': None, 'years': None, 'time_key': None, 'error': f'配置文件不存在: {config_path}'}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}

            if not isinstance(config_data, dict):
                return {'population': None, 'years': None, 'time_key': None, 'error': '配置文件根节点不是字典'}

            simulation_cfg = config_data.get('simulation', {}) or {}
            if not isinstance(simulation_cfg, dict):
                return {'population': None, 'years': None, 'time_key': None, 'error': 'simulation 段不是字典'}

            pop = simulation_cfg.get('initial_population')
            if pop is None:
                return {'population': None, 'years': None, 'time_key': None, 'error': '缺少 simulation.initial_population'}
            try:
                pop = int(pop)
            except (TypeError, ValueError):
                return {'population': None, 'years': None, 'time_key': None, 'error': f'simulation.initial_population 不是整数: {pop!r}'}

            steps = None
            time_key = None
            time_cfg = simulation_cfg.get('time')
            if isinstance(time_cfg, dict):
                steps = time_cfg.get('total_steps')
                if steps is not None:
                    time_key = 'time.total_steps'
            if steps is None:
                for key in self.TIME_STEP_KEYS:
                    if key in simulation_cfg:
                        steps = simulation_cfg[key]
                        time_key = key
                        break

            if steps is None:
                return {'population': pop, 'years': None, 'time_key': None, 'error': f'缺少时间步数字段（支持的字段: {self.TIME_STEP_KEYS} 或 simulation.time.total_steps）'}
            try:
                steps = int(steps)
            except (TypeError, ValueError):
                return {'population': pop, 'years': None, 'time_key': time_key, 'error': f'时间步数不是整数: {steps!r}'}

            return {'population': pop, 'years': steps, 'time_key': time_key, 'error': None}
        except Exception as e:
            return {'population': None, 'years': None, 'time_key': None, 'error': f'读取配置文件异常: {e}'}

    def _set_simulation_scale(self, config_path: str, population: int, years: int, time_key: str = None) -> bool:
        """设置 simulation_config.yaml 中的人口和时间规模。

        兼容多种配置风格：
        - simulation.time.total_steps
        - simulation.total_years
        - simulation.total_steps
        - simulation.total_quarters 等
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

            simulation_cfg['initial_population'] = int(population)

            # 优先使用指定的时间字段
            if time_key and time_key.startswith('time.') and '.' in time_key:
                _, sub_key = time_key.split('.', 1)
                time_cfg = simulation_cfg.setdefault('time', {})
                if isinstance(time_cfg, dict):
                    time_cfg[sub_key] = int(years)
                else:
                    simulation_cfg['total_years'] = int(years)
            elif time_key and time_key in simulation_cfg:
                simulation_cfg[time_key] = int(years)
            else:
                # 自动查找已有字段，没有则默认 total_years
                time_cfg = simulation_cfg.get('time')
                if isinstance(time_cfg, dict) and 'total_steps' in time_cfg:
                    time_cfg['total_steps'] = int(years)
                else:
                    for key in self.TIME_STEP_KEYS:
                        if key in simulation_cfg:
                            simulation_cfg[key] = int(years)
                            break
                    else:
                        simulation_cfg['total_years'] = int(years)

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

            self.logger.info(f"✓ 已设置实验规模: pop={population}, years={years}")
            return True
        except Exception as e:
            self.logger.error(f"设置实验规模失败: {e}")
            return False

    def _scale_up_simulation_config(self, config_path: str, target_population: int = 100, target_steps: int = 10) -> bool:
        """将原型配置放大到可评估规模（兼容旧逻辑，默认 pop=100, steps=10）。

        - initial_population -> target_population
        - simulation.time.total_steps / simulation.total_* -> target_steps
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
                for key in self.TIME_STEP_KEYS:
                    if key in simulation_cfg:
                        simulation_cfg[key] = int(target_steps)
                        break
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

    def _validate_smoke_test_result(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """对最小规模（冒烟测试）的运行结果做更严格的校验。

        校验项：
        1. stdout/stderr 中不含 "ERROR" 关键字（不区分大小写）。
        2. 找到最新结果文件（CSV/JSON）且不为空。
        3. 结果中至少存在一个数值列出现非零值。

        注：结果数据是否发生变化不在此校验，交由后续步骤判断。

        Returns:
            (is_valid, error_message)
        """
        # 1. 检查输出中是否有 ERROR
        combined_output = (stdout or '') + '\n' + (stderr or '')
        if 'ERROR' in combined_output.upper():
            return False, "程序输出中包含 ERROR 关键字"

        # 2. 找到最新结果文件
        latest_file = self._get_latest_result_file()
        if not latest_file:
            return False, "未找到结果文件"

        # 3. 读取并检查结果数据
        try:
            if latest_file.endswith('.csv'):
                import csv
                with open(latest_file, 'r', encoding='utf-8', errors='replace') as f:
                    reader = csv.DictReader(f)
                    if reader.fieldnames is None:
                        return False, "结果文件没有表头"
                    rows = list(reader)

                if not rows:
                    return False, "结果文件数据为空"

                # 识别数值列（排除时间/ID/名称等非数值列）
                numeric_fields = []
                skip_keywords = {'time', 'year', 'step', 'id', 'name', 'timestamp', 'date', 'pid'}
                for field in reader.fieldnames:
                    if not field:
                        continue
                    if any(kw in field.lower() for kw in skip_keywords):
                        continue
                    try:
                        float(rows[0].get(field, '') or 0)
                        numeric_fields.append(field)
                    except (ValueError, TypeError):
                        continue

                if not numeric_fields:
                    return False, "结果文件中未找到可检查的数值列"

                # 检查是否有非零值
                has_nonzero = False
                for row in rows:
                    for field in numeric_fields:
                        try:
                            if float(row.get(field, '') or 0) != 0:
                                has_nonzero = True
                                break
                        except (ValueError, TypeError):
                            continue
                    if has_nonzero:
                        break

                if not has_nonzero:
                    return False, "结果数据所有数值列均为 0，可能存在 LLM 无行为或逻辑未执行"

            elif latest_file.endswith('.json'):
                with open(latest_file, 'r', encoding='utf-8', errors='replace') as f:
                    data = json.load(f)

                if isinstance(data, list):
                    if not data:
                        return False, "结果文件为空"
                    # 简单检查：至少有一个 dict 值非零
                    has_nonzero = False
                    for item in data:
                        if isinstance(item, dict):
                            for key, value in item.items():
                                try:
                                    if float(value) != 0:
                                        has_nonzero = True
                                except (ValueError, TypeError):
                                    continue
                    if not has_nonzero:
                        return False, "结果数据所有数值均为 0"
                elif isinstance(data, dict):
                    # 简单检查：至少有一个数值非零
                    has_nonzero = False
                    for value in data.values():
                        try:
                            if float(value) != 0:
                                has_nonzero = True
                                break
                        except (ValueError, TypeError):
                            continue
                    if not has_nonzero:
                        return False, "结果数据所有数值均为 0"
                else:
                    return False, "结果文件格式不支持"
            else:
                return False, f"不支持的结果文件格式: {os.path.splitext(latest_file)[1]}"

        except Exception as e:
            self.logger.warning(f"读取结果文件失败: {e}")
            return False, f"读取结果文件失败: {e}"

        return True, ""

    async def _ensure_code_fixer(self):
        """延迟初始化并返回 CodeFixerAgent 实例。"""
        if not self.code_fixer:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            project_dir = os.path.join(project_root, 'projects', self.current_simulation_name)
            simulator_dir = os.path.join(project_root, 'src', 'simulation')
            os.makedirs(simulator_dir, exist_ok=True)

            self.code_fixer = CodeFixerAgent(
                agent_id='code_fixer_001',
                simulator_output_dir=simulator_dir,
                main_output_dir=project_dir,
                docs_dir=self.docs_dir,
                config_dir=self.current_config_dir,
                config_template_dir=self.config_template_dir,
                simulation_name=self.current_simulation_name,
                simulation_type=getattr(self, 'current_simulation_type', 'decision'),
                session=self.session,
                auto_mode=self.auto_mode,
            )
        return self.code_fixer

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
                        selected_modules = config['selected_modules']
                        if isinstance(selected_modules, list):
                            selected_modules = [name for name in selected_modules if isinstance(name, str) and name.strip()]
                            return yaml.dump({'selected_modules': selected_modules}, allow_unicode=True)
                    return ""
        return ""

    def _get_latest_result_file(self):
        """
        查找实验输出（结果）目录下最新的结果文件。

        结果统一存放在 projects/<name>/history/ 下的时间戳子目录中，
        因此只在 history 目录内递归查找数据文件，避免误读 config/ 下的
        配置文件（如 towns_data.json）或 backups/、__pycache__ 等无关目录。
        """
        history_dir = os.path.join(self.current_project_dir, 'history')
        if not os.path.isdir(history_dir):
            self.logger.warning(f"❌ 实验输出目录不存在: {history_dir}")
            return None

        # 仅识别真正的结果数据文件，排除日志/图片等
        all_result_files = []
        for root, dirs, files in os.walk(history_dir):
            # 跳过绘图结果目录
            dirs[:] = [d for d in dirs if d != 'plot_results']
            for f in files:
                if not f.endswith(('.json', '.csv')):
                    continue
                # 排除日志文件（如 complete_*.log 误命名等）
                if f.endswith('.log'):
                    continue
                all_result_files.append(os.path.join(root, f))

        if all_result_files:
            latest_file = max(all_result_files, key=os.path.getmtime)
            self.logger.info(f"找到结果文件: {latest_file}")
            return latest_file

        self.logger.warning(f"❌ 未在实验输出目录中找到任何结果文件: {history_dir}")
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

        max_attempts = 5
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
        所有生成产物统一放在 projects/[模拟名称]/ 下。
        """
        # 项目根目录（Eco3S项目根目录）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # 创建 projects/[模拟名称]/ 文件夹
        project_dir = os.path.join(project_root, 'projects', simulation_name)
        config_dir = os.path.join(project_dir, 'config')
        history_dir = os.path.join(project_dir, 'history')
        backups_dir = os.path.join(project_dir, 'backups')
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(history_dir, exist_ok=True)
        os.makedirs(backups_dir, exist_ok=True)

        # 首次使用时，复制 entrypoints/shared_imports.py 到 projects/shared_imports.py
        shared_imports_src = os.path.join(project_root, 'entrypoints', 'shared_imports.py')
        shared_imports_dst = os.path.join(project_root, 'projects', 'shared_imports.py')
        if os.path.exists(shared_imports_src) and not os.path.exists(shared_imports_dst):
            try:
                import shutil
                shutil.copy2(shared_imports_src, shared_imports_dst)
                self.logger.info(f"已复制共享导入文件: {shared_imports_dst}")
            except Exception as e:
                self.logger.warning(f"复制 shared_imports.py 失败: {e}")

        self.current_project_dir = project_dir
        self.current_config_dir = config_dir
        self.current_simulation_name = simulation_name
        self.logger.info(f"项目文件夹已创建: {project_dir}")
        self.logger.info(f"配置文件夹已创建: {config_dir}")
        self.logger.info(f"实验文件夹已创建: {history_dir}")

        return project_dir

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
            # 通过“选择模块”步骤直接生成 modules_config.yaml
            previous_modules = None
            if user_feedback:
                previous_modules = self._read_modules_config(full_config=False)
            _ = await designer.select_modules(
                previous_modules=previous_modules,
                user_feedback=user_feedback,
                description_md=description_md
            )
            config_files = [modules_config_path] if os.path.exists(modules_config_path) else []
            self.logger.info(f"配置文件已生成: {config_files}")
        else:
            config_files = [modules_config_path] if os.path.exists(modules_config_path) else []
        
        modules_config_yaml = self._read_modules_config(full_config=False)

        # ============ 步骤 2.5: 生成 Agent Profile 配置 ============
        self.logger.info("步骤 2.5: 生成 Agent Profile 配置")
        agent_profile_path = os.path.join(self.current_config_dir, 'agent_profile.yaml')
        agent_profile_yaml = ""
        should_generate_agent_profile = True

        # 检查是否已存在 agent_profile.yaml
        if os.path.exists(agent_profile_path) and not (previous_version and user_feedback):
            if not self._check_step_completion("Agent Profile 配置", [agent_profile_path]):
                should_generate_agent_profile = False
                with open(agent_profile_path, 'r', encoding='utf-8') as f:
                    agent_profile_yaml = f.read()
                self.logger.info("跳过生成，使用现有 agent_profile.yaml")

        if should_generate_agent_profile:
            previous_agent_profile = None
            if previous_version and user_feedback:
                previous_agent_profile = previous_version.get('agent_profile_yaml', '')
            generated_profile = await designer.generate_agent_profile_config(
                description_md=description_md,
                modules_config_yaml=modules_config_yaml,
                previous_agent_profile=previous_agent_profile,
                user_feedback=user_feedback
            )
            if generated_profile:
                with open(agent_profile_path, 'w', encoding='utf-8') as f:
                    f.write(generated_profile)
                agent_profile_yaml = generated_profile
                config_files.append(agent_profile_path)
                self.logger.info(f"agent_profile.yaml 已生成: {agent_profile_path}")
            else:
                self.logger.warning("agent_profile.yaml 生成失败，将在编码阶段使用模板默认值")

        return {
            'parsed_requirement': parsed_req,
            'description_md': description_md,
            'config_files': config_files,
            'modules_config_yaml': modules_config_yaml,
            'agent_profile_path': agent_profile_path if agent_profile_yaml else None,
            'agent_profile_yaml': agent_profile_yaml,
            'simulation_type': simulation_type
        }

    async def _run_exogenous_variable_generation(self, design_results=None, coding_results=None) -> bool:
        """阶段 3.45：外生变量序列生成。

        编码完成后执行：从 influence_pairs.json 提取「只作为 cause、从不作为 effect」
        的根驱动参数，由 LLM 依据设计文档生成随时间变化的序列写入 CSV，
        并把数据路径写入 simulation_config.yaml，使仿真每步直接读取外生值，
        让下游因果链产生更明显的可观察变化。

        失败/无外生变量时返回 True（流程继续，influences 经 fallback 回退内部计算）。
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_dir = self.current_config_dir or os.path.join(
            project_root, 'projects', self.current_simulation_name, 'config'
        )
        pairs_path = os.path.join(config_dir, 'influence_pairs.json')
        sim_config_path = os.path.join(config_dir, 'simulation_config.yaml')

        # 外生序列输出路径固定，先检测文件是否存在：已存在则询问是否跳过，
        # 避免在文件已存在时仍进行无谓的节点识别与 LLM 序列生成。
        exo_dir = os.path.join(project_root, 'projects', self.current_simulation_name, 'experiment_dataset')
        csv_path = os.path.join(exo_dir, 'exogenous.csv')
        rel_path = f"projects/{self.current_simulation_name}/experiment_dataset/exogenous.csv"

        if os.path.exists(csv_path):
            if not self._check_step_completion('外生变量序列生成', [csv_path]):
                # 用户选择跳过：确保 config 仍指向现有文件
                self._patch_simulation_config_exogenous(sim_config_path, rel_path)
                self.logger.info(f"✓ 使用已存在的外生变量序列: {csv_path}")
                return True

        # 文件不存在或用户选择重新生成：开始识别外生变量并生成序列
        if not os.path.exists(pairs_path):
            self.logger.info("未找到 influence_pairs.json，跳过外生变量生成")
            return True

        try:
            with open(pairs_path, 'r', encoding='utf-8') as f:
                pairs = json.load(f)
        except Exception as exc:
            self.logger.warning(f"读取 influence_pairs.json 失败，跳过外生变量生成: {exc}")
            return True

        nodes = extract_exogenous_nodes(pairs if isinstance(pairs, list) else [])
        if not nodes:
            self.logger.info("influence_pairs.json 中无纯 cause 根驱动节点，跳过外生变量生成")
            return True

        self.logger.info(f"识别到 {len(nodes)} 个外生变量（纯 cause 根驱动）: {[n['slug'] for n in nodes]}")

        # 总时间步数
        scale = self._get_simulation_scale(sim_config_path)
        total_steps = scale.get('years')
        if not isinstance(total_steps, int) or total_steps <= 0:
            total_steps = 20
            self.logger.warning(f"无法读取总时间步数，外生序列长度回退为默认 {total_steps}")

        # 设计文档
        description_md = ""
        description_path = os.path.join(config_dir, 'description.md')
        if os.path.exists(description_path):
            try:
                with open(description_path, 'r', encoding='utf-8') as f:
                    description_md = f.read()
            except Exception:
                description_md = ""

        # 确保输出目录存在
        try:
            os.makedirs(exo_dir, exist_ok=True)
        except Exception as exc:
            self.logger.warning(f"创建外生数据目录失败: {exc}")
            return True

        # --- 尝试加载真实数据 ---
        catalog = None
        catalog_dir = os.path.join(project_root, 'experiment_dataset', 'data_catalog')
        if os.path.isdir(catalog_dir):
            try:
                from src.environment.real_world_data import RealWorldCatalog
                catalog = RealWorldCatalog(catalog_dir)
                if not catalog.load():
                    catalog = None
            except Exception as exc:
                self.logger.info(f"真实数据目录加载跳过（不影响流程）: {exc}")

        # --- 逐个生成序列（真实数据优先，LLM fallback） ---
        data: Dict[str, List[float]] = {}

        if catalog is not None:
            from src.environment.real_world_data import ExogenousMapper, ExogenousSeriesBuilder

            mapper = ExogenousMapper(os.path.join(catalog_dir, 'indicator_registry.yaml'))
            if self.code_architect:
                mapper.set_llm_callback(self.code_architect.generate_llm_response)
            builder = ExogenousSeriesBuilder(catalog)

            for node in nodes:
                real_used = False
                try:
                    mapping = await mapper.map_node(node, description_md)
                    direction, _ = self._lookup_pair_direction(pairs, node)

                    if mapping.match_type == 'use_indicator' and mapping.indicator_codes:
                        series = builder.build_series(
                            mapping.indicator_codes[0], total_steps,
                            direction=direction,
                        )
                        if series and len(series) >= max(2, total_steps // 2):
                            data[node['slug']] = series
                            self.logger.info(f"  ✓ {node['slug']}: 使用真实数据 [{mapping.indicator_codes[0]}]")
                            real_used = True

                    elif mapping.match_type == 'context_indicators' and mapping.indicator_codes:
                        ctx = builder.build_context(mapping.indicator_codes)
                        ctx_summary = "; ".join(
                            f"{k}: [{', '.join(str(round(vv,2)) for vv in vs[:5])}...]"
                            for k, vs in ctx.items()
                        ) if ctx else ""
                        if ctx_summary:
                            # 用本地变量临时扩展上下文，不影响 description_md 原值
                            prompt_with_context = description_md + f"\n\n【真实数据参考】\n{ctx_summary}"
                            self.logger.info(f"  → {node['slug']}: 添加 {len(mapping.indicator_codes)} 个真实指标作为 LLM 上下文")
                            direction, effect_size = self._lookup_pair_direction(pairs, node)
                            series = await self._generate_exogenous_series(
                                node, prompt_with_context, total_steps, direction, effect_size
                            )
                        else:
                            direction, effect_size = self._lookup_pair_direction(pairs, node)
                            series = await self._generate_exogenous_series(
                                node, description_md, total_steps, direction, effect_size
                            )
                        data[node['slug']] = series
                        real_used = True
                except Exception as exc:
                    self.logger.info(f"  → {node['slug']}: 数据映射异常 ({exc})，走 LLM 生成")

                if not real_used:
                    direction, effect_size = self._lookup_pair_direction(pairs, node)
                    series = await self._generate_exogenous_series(
                        node, description_md, total_steps, direction, effect_size
                    )
                    data[node['slug']] = series
        else:
            # 无真实数据目录：走原 LLM 生成路径
            for node in nodes:
                direction, effect_size = self._lookup_pair_direction(pairs, node)
                series = await self._generate_exogenous_series(
                    node, description_md, total_steps, direction, effect_size
                )
                data[node['slug']] = series

        if not self._save_exogenous_csv(data, csv_path):
            return True

        # 回填 simulation_config.yaml：data.exogenous_data_path（相对项目根目录）
        self._patch_simulation_config_exogenous(sim_config_path, rel_path)

        self.logger.info(f"✓ 外生变量序列已生成: {csv_path}（{len(data)} 个变量 × {total_steps} 步）")
        return True

    def _lookup_pair_direction(self, pairs, node) -> tuple:
        """从 pairs 中找到以该 node 为 cause 的代表性影响对，返回 (direction, effect_size)。"""
        for p in pairs or []:
            if not isinstance(p, dict):
                continue
            c = p.get('cause') or {}
            if str(c.get('module') or '').strip() == node['module'] and \
               str(c.get('param') or '').strip() == node['param']:
                return str(p.get('direction') or '').strip().lower(), str(p.get('effect_size') or '').strip()
        return '', ''

    async def _generate_exogenous_series(self, node, description_md, total_steps, direction, effect_size) -> List[float]:
        """调用 LLM 为单个外生变量生成长度=total_steps 的时间序列。

        解析失败 / 数值异常时回退为基于 direction 的单调斜坡，保证流程不中断。
        """
        desc_summary = (description_md or "")[:2000]
        prompt = (
            "你是仿真外生变量设计专家。请为下面这个『外生变量（因果链的根驱动参数，"
            "只作为原因、不被其它因素影响）』生成一条随时间步变化的数值序列。\n\n"
            f"- 所属模块: {node['module']}\n"
            f"- 参数含义: {node['param']}\n"
            f"- 该参数对下游的影响方向: {direction or '未指定'}\n"
            f"- 效应大小: {effect_size or '未指定'}\n"
            f"- 总时间步数: {total_steps}\n\n"
            f"【仿真设计文档摘要】\n{desc_summary}\n\n"
            "要求：\n"
            f"1. 恰好输出 {total_steps} 个数值，用英文逗号分隔，全部在同一行。\n"
            "2. 数值应体现该根驱动随时间的合理演化（如政策实施期可阶梯/线性推进、"
            "外部冲击可在某步骤后跃变），变化要足够明显以驱动下游产生可观察的变化。\n"
            "3. 数值量纲要贴合参数语义，正负、范围合理。\n"
            "4. 只返回这一行数值，不要任何解释、表头或代码块。"
        )
        raw = None
        try:
            raw = await self.code_architect.generate_llm_response(prompt)
        except Exception as exc:
            self.logger.warning(f"外生变量 {node['slug']} LLM 生成失败，使用回退序列: {exc}")

        series = self._parse_number_series(raw) if raw else []
        if len(series) >= total_steps:
            series = series[:total_steps]
        elif series:
            # 不足则用末值补齐
            series = series + [series[-1]] * (total_steps - len(series))
        else:
            series = self._fallback_series(total_steps, direction)
            self.logger.info(f"外生变量 {node['slug']} 使用回退斜坡序列")
        return series

    @staticmethod
    def _parse_number_series(text: str) -> List[float]:
        """从 LLM 文本中解析逗号/空白分隔的数值序列。"""
        import re as _re
        if not text:
            return []
        # 去掉可能的代码块围栏
        text = text.replace('```', ' ')
        tokens = _re.findall(r'-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', text)
        out: List[float] = []
        for t in tokens:
            try:
                out.append(round(float(t), 6))
            except ValueError:
                continue
        return out

    @staticmethod
    def _fallback_series(total_steps: int, direction: str) -> List[float]:
        """回退序列：基于影响方向生成单调斜坡（0→1 线性），decrease 时反向。"""
        n = max(1, int(total_steps))
        if n == 1:
            return [1.0]
        ramp = [round(i / (n - 1), 6) for i in range(n)]
        if direction == 'decrease':
            ramp = list(reversed(ramp))
        return ramp

    def _save_exogenous_csv(self, data: Dict[str, List[float]], output_path: str) -> bool:
        """写多列带表头 CSV：每列一个外生变量，每行一个时间步。"""
        import csv as _csv
        if not data:
            self.logger.info("外生变量数据为空，不写文件")
            return False
        keys = list(data.keys())
        n_rows = max((len(v) for v in data.values()), default=0)
        try:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = _csv.writer(f)
                writer.writerow(keys)
                for i in range(n_rows):
                    row = []
                    for k in keys:
                        col = data[k]
                        row.append(col[i] if i < len(col) else (col[-1] if col else 0.0))
                    writer.writerow(row)
            return True
        except Exception as exc:
            self.logger.warning(f"写入 exogenous.csv 失败: {exc}")
            return False

    def _patch_simulation_config_exogenous(self, sim_config_path: str, rel_path: str) -> bool:
        """把 data.exogenous_data_path 写入 simulation_config.yaml。"""
        if not os.path.exists(sim_config_path):
            self.logger.warning("simulation_config.yaml 不存在，无法写入 exogenous_data_path")
            return False
        try:
            with open(sim_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            if not isinstance(config, dict):
                return False
            data_cfg = config.setdefault('data', {})
            if not isinstance(data_cfg, dict):
                config['data'] = data_cfg = {}
            data_cfg['exogenous_data_path'] = rel_path
            with open(sim_config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
            self.logger.info(f"✓ 已写入 simulation_config.yaml: data.exogenous_data_path = {rel_path}")
            return True
        except Exception as exc:
            self.logger.warning(f"写入 exogenous_data_path 失败: {exc}")
            return False

    async def _run_influence_preflight(self, max_fix_attempts: int = 3) -> bool:
        """阶段 3.4：Influence 机制预检。

        在冒烟测试/正式运行之前，用虚拟数据跑一轮 influences.yaml，
        高置信问题（模块名缺失导致静默跳过、expr 引用未定义变量、非有限值等）
        直接触发 code_fixer.run_optimization_session 修复，最多 max_fix_attempts 轮。

        Returns:
            True 表示通过预检或无需预检；False 表示修复后仍不通过，应终止工作流。
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_dir = self.current_config_dir or os.path.join(
            project_root, 'projects', self.current_simulation_name, 'config'
        )
        simulator_path = os.path.join(
            project_root, 'projects', self.current_simulation_name, 'simulator.py'
        )
        influences_path = os.path.join(config_dir, 'influences.yaml')

        if not os.path.exists(influences_path):
            self.logger.info("未找到 influences.yaml，跳过 influence 预检")
            return True

        self.logger.info("=" * 50)
        self.logger.info("阶段 3.4: Influence 机制预检（虚拟数据）")
        self.logger.info("=" * 50)

        design_doc = ""
        description_path = os.path.join(config_dir, 'description.md')
        if os.path.exists(description_path):
            with open(description_path, 'r', encoding='utf-8') as f:
                design_doc = f.read()

        for attempt in range(1, max_fix_attempts + 1):
            preflight = InfluencePreflight.from_project_dir(config_dir, simulator_path)
            result = preflight.run()

            if result.get('ok'):
                self.logger.info(f"✓ influence 预检通过（第 {attempt} 轮）")
                return True

            # 构建 CodeFixer 可消费的评估报告
            evaluation_report = InfluencePreflight.to_evaluation_report(result)
            self.logger.warning(
                f"⚠️ influence 预检发现 {len(result.get('silent_skip', []))} 个静默跳过、"
                f"{len(result.get('broken_influence', []))} 个影响函数异常、"
                f"{len(result.get('non_finite', []))} 个非有限值"
            )
            self.logger.debug(f"预检诊断详情:\n{evaluation_report}")

            if attempt >= max_fix_attempts:
                self.logger.error(
                    f"❌ influence 预检连续 {max_fix_attempts} 轮未通过，终止工作流"
                )
                return False

            self.logger.info(
                f"调用 CodeFixer 修复 influence 问题（第 {attempt}/{max_fix_attempts} 轮）..."
            )
            code_fixer = await self._ensure_code_fixer()
            optimization = await code_fixer.run_optimization_session(
                evaluation_report=evaluation_report,
                design_doc=design_doc,
                interactive=False,
            )

            solved = optimization.get('optimization_passed') or optimization.get('success')
            if not solved:
                self.logger.warning(
                    f"⚠️ CodeFixer 本轮未能解决问题（优化会话 success={optimization.get('success')}）"
                )

        # 再跑最后一次确定是否通过
        final = InfluencePreflight.from_project_dir(config_dir, simulator_path).run()
        if final.get('ok'):
            self.logger.info("✓ influence 预检最终通过")
            return True
        self.logger.error("❌ influence 预检最终仍不通过，终止工作流")
        return False

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

        # simulator 文件现在统一放在项目目录下
        project_dir = os.path.join(project_root, 'projects', self.current_simulation_name)
        simulator_dir = os.path.join(project_root, 'src', 'simulation')
        os.makedirs(simulator_dir, exist_ok=True)

        # 获取模拟类型
        simulation_type = design_results.get('simulation_type', 'decision')  # 默认为决策型
        self.current_simulation_type = simulation_type
        self.logger.info(f"编码阶段使用模拟类型: {simulation_type}")

        # 创建或复用 CodeArchitectAgent 实例
        if not self.code_architect:
            self.code_architect = CodeArchitectAgent(
                agent_id='code_architect_001',
                simulator_output_dir=simulator_dir,
                main_output_dir=project_dir,
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
        simulator_file_path = os.path.join(project_dir, 'simulator.py')

        required_files = [
            simulator_file_path,
            os.path.join(self.current_config_dir, 'simulation_config.yaml'),
            os.path.join(self.current_config_dir, 'jobs_config.yaml'),
            os.path.join(self.current_config_dir, 'influences.yaml'),
            os.path.join(self.current_config_dir, 'resident_actions.yaml'),
            os.path.join(self.current_config_dir, 'towns_data.json'),
        ]

        # 如果所有文件都存在，询问是否跳过
        if not self._check_step_completion("编码阶段", required_files):
            # 用户选择跳过，读取现有文件并返回
            self.logger.info("跳过编码阶段，使用现有文件")

            # 收集所有现有文件
            config_files = [f for f in required_files[1:] if os.path.exists(f)]
            prompt_files = []
            for prompt_file in ['government_prompts.yaml', 'rebels_prompts.yaml', 'residents_prompts.yaml']:
                pf_path = os.path.join(self.current_config_dir, prompt_file)
                if os.path.exists(pf_path):
                    prompt_files.append(pf_path)

            return {
                'status': 'success',
                'simulator_files': [simulator_file_path],
                'config_files': config_files,
                'prompt_files': prompt_files,
                'all_files': [simulator_file_path] + config_files + prompt_files
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

            context_suffix += f"=== 用户反馈 ===\n{user_feedback}\n"
        
        description_with_context = design_results['description_md'] + context_suffix
        # === 步骤0: 若 modules_config.yaml 声明了 new_modules，则先生成新模块插件并自动接线 ===
        try:
            modules_config_full_yaml = self._read_modules_config(full_config=True)
            created_plugins = await coder.ensure_new_modules_before_simulator(
                description_md=description_with_context,
                modules_config_yaml_full=modules_config_full_yaml,
            )
            if created_plugins:
                self.logger.info(f"已创建 {created_plugins} 插件")
        except Exception as e:
            # 不阻断主流程：即使新模块生成失败，仍尝试继续生成 simulator
            self.logger.warning(f"处理 new_modules 失败（将继续生成 simulator）: {e}")

        # === 步骤0.5: 生成影响函数配置（提前到 simulator 之前，供后续约束检查使用） ===
        self.logger.info("步骤 0.5: 生成影响函数 (influences.yaml)")
        influences_config_path = None
        influences_yaml_content = ""
        try:
            modules_config_yaml = self._read_modules_config()
            influences_config_path = await coder.generate_influences_config_file(
                description_with_context,
                modules_config_yaml,
                previous_configs=None,
            )
            if influences_config_path and os.path.exists(influences_config_path):
                self.logger.info(f"  ✓ influences.yaml 已生成: {influences_config_path}")
                with open(influences_config_path, 'r', encoding='utf-8') as f:
                    influences_yaml_content = f.read()
            else:
                self.logger.warning("  ✗ influences.yaml 生成失败（将以默认无影响函数配置运行）")
        except Exception as e:
            self.logger.warning(f"  ✗ influences.yaml 生成异常（将以默认无影响函数配置运行）: {e}")

        # 步骤1和步骤2循环：支持 regenerate 后回到步骤1重新生成
        while True:
            # === 步骤1: 生成simulator代码框架 ===
            self.logger.info("步骤 1: 生成simulator代码框架")

            simulator_files, skipped = await coder.generate_simulator_code(
                description_with_context,
                design_results.get('modules_config_yaml', ''),
                influences_yaml=influences_yaml_content
            )

            if not simulator_files:
                self.logger.error("生成simulator代码失败")
                return {'status': 'failed', 'reason': 'simulator generation failed'}

            simulator_file_path = simulator_files[0]
            self.logger.info(f"Simulator代码已生成: {simulator_file_path}")

            # === 步骤2: 检查并补完simulator函数 ===
            if skipped:
                self.logger.info("⏭️  步骤 2: 用户选择使用现有simulator文件，跳过完善步骤")
                break
            else:
                self.logger.info("步骤 2: 根据模块配置完善simulator实现")
                refined_result = await coder.refine_simulator_functions(
                    simulator_file_path,
                    description_with_context,
                    design_results.get('modules_config_yaml', ''),
                    influences_file_path=influences_config_path
                )

                # 检查是否需要重新生成
                if isinstance(refined_result, dict) and refined_result.get('status') == 'regenerate':
                    self.logger.info("用户选择重新生成 simulator，回到步骤1...")
                    continue

                if refined_result and refined_result.get('files'):
                    self.logger.info("Simulator函数已补完")
                else:
                    self.logger.warning("Simulator函数补完失败，保持原文件")
                break

        # === 步骤3: 生成配置文件（按顺序，每次一个） ===
        self.logger.info("步骤 3: 生成配置文件")
        config_files = []
        previous_configs = {}

        # 将 influences.yaml 纳入后续配置生成的上下文与产物列表
        if influences_config_path and os.path.exists(influences_config_path):
            try:
                config_files.append(influences_config_path)
                with open(influences_config_path, 'r', encoding='utf-8') as f:
                    previous_configs['influences.yaml'] = f.read()
            except Exception:
                pass
        
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
            # 'resident_actions.yaml',
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

            # Agent Profile 保持独立文件，不再嵌入 simulation_config.yaml

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
        
        # === 步骤6: 生成提示词文件与动作文件（优先按 agent_profile.yaml 的角色定义） ===
        self.logger.info("步骤 6: 生成提示词文件与动作文件")
        prompt_files = []
        action_files = []

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

        # 先按 agent_profile.yaml 生成角色级 prompts/actions
        agent_profile_path = os.path.join(self.current_config_dir, 'agent_profile.yaml')
        description_with_prompt_context = description_content + prev_prompt_context
        generated_role_files = []
        if os.path.exists(agent_profile_path):
            try:
                generated_role_files = await coder.generate_role_files_from_agent_profile(
                    description_with_prompt_context,
                    config_files,
                    agent_profile_path=agent_profile_path,
                )
            except Exception as e:
                self.logger.warning(f"按 agent_profile.yaml 生成角色文件失败: {e}")

        if generated_role_files:
            for file_path in generated_role_files:
                normalized_path = file_path.replace('\\', '/')
                if '/actions/' in normalized_path:
                    if file_path not in config_files:
                        config_files.append(file_path)
                    action_files.append(file_path)
                else:
                    prompt_files.append(file_path)
            self.logger.info(f"  ✓ 已生成角色提示词/动作文件: {len(generated_role_files)} 个")
        else:
            self.logger.warning("agent_profile.yaml 存在但未能生成角色级 prompts/actions 文件")
        
        # === 步骤6.1: 自动修正 simulation_config.yaml 的 data 路径 ===
        # 在所有配置文件和提示词文件生成结束后，根据实际存在的文件自动构建路径
        self.logger.info("步骤 6.1: 自动修正 simulation_config.yaml 的 data 路径")
        try:
            coder._finalize_simulation_config_paths()
        except Exception as e:
            self.logger.warning(f"自动修正 simulation_config.yaml 路径失败: {e}")

        # === 返回结果 ===
        coding_results = {
            'status': 'success',
            'simulator_files': simulator_files,
            'config_files': config_files,
            'prompt_files': prompt_files,
            'all_files': simulator_files + config_files + prompt_files
        }

        self.logger.info("编码阶段完成")
        self.logger.info(f"共生成 {len(coding_results['all_files'])} 个文件")

        return coding_results

    async def run_simulation(self, coding_results, max_fix_attempts=10):
        """
        运行模拟程序，如果出错则自动调用编码师进行纠错。
        """
        self.logger.info("=" * 50)
        self.logger.info("运行模拟程序")
        self.logger.info("=" * 50)

        # 获取文件路径
        simulator_files = coding_results.get('simulator_files', [])

        if not simulator_files:
            self.logger.error("❌ 缺少必要的 simulator 文件")
            return False

        simulator_file_path = simulator_files[0]

        # 可选的自定义 main.py
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_dir = os.path.join(project_root, 'projects', self.current_simulation_name)
        main_file_path = os.path.join(project_dir, 'main.py')
        main_file_path = main_file_path if os.path.exists(main_file_path) else None

        # 获取模拟名称
        simulation_name = self.current_simulation_name

        # 构建运行命令
        config_path = os.path.join(project_root, 'projects', simulation_name, 'config', 'simulation_config.yaml')
        run_command = f'python run_project.py --project {simulation_name}'

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
                            
                            # 调用代码修复Agent的纠错函数
                            code_fixer = await self._ensure_code_fixer()
                            fixed = await code_fixer.fix_runtime_errors(
                                error_message=error_message,
                                error_traceback=f"标准输出:\n{result.stdout}\n\n标准错误:\n{result.stderr}",
                                main_file_path=main_file_path,
                                simulator_file_path=simulator_file_path,
                                config_path=config_path,
                                max_attempts=5
                            )
                            
                            if fixed:
                                self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                            else:
                                # 修复未成功：不立即终止，继续下一次尝试，给修复Agent更多机会
                                self.logger.warning(f"⚠️ 第 {attempt} 次修复未成功，将进行下一次尝试...")
                            continue  # 重新运行
                        else:
                            self.logger.error("❌ 已达到最大运行尝试次数")
                            return False

                    self.logger.info("✅ 程序运行成功！")
                    self.logger.info(f"输出:\n{result.stdout}")

                    # 检查是否是小规模冒烟测试（人口=5，年数=2）
                    is_small_scale = False
                    try:
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config_data = yaml.safe_load(f)
                                # Check population
                                pop = config_data.get('simulation', {}).get('initial_population')
                                # Check steps/years
                                simulation_cfg = config_data.get('simulation', {}) or {}
                                time_cfg = simulation_cfg.get('time')
                                steps = time_cfg.get('total_steps') if isinstance(time_cfg, dict) else None
                                if steps is None:
                                    for key in self.TIME_STEP_KEYS:
                                        if key in simulation_cfg:
                                            steps = simulation_cfg[key]
                                            break
                                try:
                                    pop = int(pop)
                                except (TypeError, ValueError):
                                    pop = None
                                try:
                                    steps = int(steps)
                                except (TypeError, ValueError):
                                    steps = None
                                print(f"实验结束：pop={pop}, years={steps}")
                                if pop == self.SMOKE_TEST_POPULATION and steps == self.SMOKE_TEST_YEARS:
                                    is_small_scale = True
                    except Exception as e:
                        self.logger.warning(f"检查配置文件是否为小规模测试时出错: {e}")

                    if is_small_scale:
                        # 对冒烟测试做更严格的校验：ERROR、结果非空、非零、有变化
                        valid, validation_error = self._validate_smoke_test_result(result.stdout, result.stderr)
                        if not valid:
                            self.logger.error(f"❌ 冒烟测试校验失败: {validation_error}")

                            if attempt < max_fix_attempts:
                                self.logger.info(f"\n🔧 调用编码师Agent进行诊断和修复...")

                                code_fixer = await self._ensure_code_fixer()
                                fixed = await code_fixer.fix_runtime_errors(
                                    error_message=f"冒烟测试校验失败: {validation_error}",
                                    error_traceback=f"标准输出:\n{result.stdout}\n\n标准错误:\n{result.stderr}",
                                    main_file_path=main_file_path,
                                    simulator_file_path=simulator_file_path,
                                    config_path=config_path,
                                    max_attempts=5
                                )

                                if fixed:
                                    self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                                else:
                                    # 修复未成功：继续下一次尝试，给修复Agent更多机会
                                    self.logger.warning(f"⚠️ 第 {attempt} 次修复未成功，将进行下一次尝试...")
                                continue
                            return False

                        print(f"\n{'='*60}")
                        print("冒烟测试（最小规模）已完成！")
                        print(f"{'='*60}")
                        # 返回特殊标记，表示冒烟测试完成
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
                        
                        # 调用代码修复Agent的纠错函数
                        code_fixer = await self._ensure_code_fixer()
                        fixed = await code_fixer.fix_runtime_errors(
                            error_message=error_message,
                            error_traceback=error_traceback,
                            main_file_path=main_file_path,
                            simulator_file_path=simulator_file_path,
                            config_path=config_path,
                            max_attempts=5  # 修复Agent内部的修复尝试次数
                        )
                        
                        if fixed:
                            self.logger.info("✓ 编码师已完成修复，准备重新运行...")
                        else:
                            # 修复未成功：不立即终止，继续下一次尝试，给修复Agent
                            # （含其内部多次重试）更多机会，直到用尽 max_fix_attempts
                            self.logger.warning(f"⚠️ 第 {attempt} 次修复未成功，将进行下一次尝试...")
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

        # === 确定性硬检查阶段（无 LLM）：第一个命中即跳过 LLM 评估、直接技能驱动修复 ===
        hard_checks = [
            (analyst.check_resident_activity(),
             'docs/code_fixer_skills/skill_agent_behavior_abnormal.md'),
            (analyst.check_metrics_variation(simulation_results_path),
             'docs/code_fixer_skills/skill_metrics_constant_zero.md'),
        ]
        for check_result, skill in hard_checks:
            if not check_result.get('is_problem'):
                continue

            reason = check_result.get('reason', '')
            self.logger.warning(f"⚠️ 硬检查命中：{reason} → 跳过 LLM 评估，技能驱动修复（{skill}）")

            # 硬编码一句话报告，保持文件/Web 流程一致
            report = f"## 评估结果\n状态：NEED_ADJUSTMENT\n\n原因（确定性硬检查）：{reason}\n"
            report_path = os.path.normpath(
                os.path.join(os.path.dirname(simulation_results_path), '..', 'evaluation_report.md'))
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
            except Exception as e:
                self.logger.warning(f"写入硬检查报告失败（不中断）: {e}")

            if self.web_mode and self.session:
                self.session['pending_evaluation_report'] = report
                self.session['pending_design_doc'] = design_doc
                self.session['pending_skill_files'] = [skill]
                self.session['pending_problem_summary'] = reason
                self.session['pending_problem_detail'] = check_result.get('detail')
                return {
                    'evaluation_report': report,
                    'needs_adjustment': True,
                    'waiting_user_confirmation': True,
                    'optimization_completed': False
                }

            code_fixer = await self._ensure_code_fixer()
            session_result = await code_fixer.run_skill_guided_session(
                problem_summary=reason,
                skill_files=[skill],
                detail=check_result.get('detail'),
                design_doc=design_doc
            )
            return {
                'evaluation_report': report,
                'needs_adjustment': True,
                'optimization_session_result': session_result,
                'optimization_passed': session_result.get('optimization_passed', False),
                'optimization_completed': False
            }

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
            self.logger.info("⚠️  结果不符合预期，启动 CodeFixerAgent 优化...")

            # Web 模式：先等待前端确认，再启动优化会话
            if self.web_mode and self.session:
                self.session['pending_evaluation_report'] = evaluation_report
                self.session['pending_design_doc'] = design_doc
                # 报告驱动路径：清除可能残留的硬检查技能标记，避免误走技能驱动分支
                self.session['pending_skill_files'] = None
                self.session['pending_problem_summary'] = None
                self.session['pending_problem_detail'] = None
                return {
                    'evaluation_report': evaluation_report,
                    'needs_adjustment': True,
                    'waiting_user_confirmation': True,
                    'optimization_completed': False
                }

            code_fixer = await self._ensure_code_fixer()
            session_result = await code_fixer.run_optimization_session(
                evaluation_report=evaluation_report,
                design_doc=design_doc,
                interactive=not self.auto_mode
            )

            optimization_passed = session_result.get('optimization_passed', False)
            if optimization_passed:
                self.logger.info("✓ 本轮优化通过问题解决检查，将进入下一轮运行与评估以确认效果")
            else:
                self.logger.warning(f"⚠️ 本轮优化未通过问题解决检查: {session_result.get('solved', {})}")

            return {
                'evaluation_report': evaluation_report,
                'needs_adjustment': True,
                'optimization_session_result': session_result,
                'optimization_passed': optimization_passed,
                # 完成与否不由"本轮是否改了文件"决定：本轮无论是否通过解决检查，
                # 都需要下一轮重新运行+评估来确认结果是否真正符合预期，因此这里恒为 False，
                # 迫使外层进入下一轮。真正的"完成"由后续某轮评估返回 needs_adjustment=False 触发。
                'optimization_completed': False
            }
        else:
            self.logger.info("✓ 结果符合预期，无需调整")
            return {
                'evaluation_report': evaluation_report,
                'needs_adjustment': False,
                'optimization_completed': True
            }

    async def apply_optimization_adjustments(self, diagnosis_path=None, design_doc=None):
        """
        应用优化调整：启动 CodeFixerAgent 优化会话。
        在 Web 流程中，由前端确认后调用；在 CLI 流程中已由 run_evaluation_and_optimization_phase 直接完成。
        """
        self.logger.info("=" * 50)
        self.logger.info("开始应用优化调整")
        self.logger.info("=" * 50)

        evaluation_report = None
        pending_skill_files = None
        pending_problem_summary = None
        pending_problem_detail = None
        if self.session:
            evaluation_report = self.session.get('pending_evaluation_report')
            design_doc = design_doc or self.session.get('pending_design_doc', '')
            pending_skill_files = self.session.get('pending_skill_files')
            pending_problem_summary = self.session.get('pending_problem_summary')
            pending_problem_detail = self.session.get('pending_problem_detail')

        if not evaluation_report:
            self.logger.warning("未找到待处理的评估报告，无法启动优化会话")
            return {
                'success': False,
                'modification_results': [],
                'message': '未找到待处理的评估报告'
            }

        code_fixer = await self._ensure_code_fixer()
        if pending_skill_files:
            # 硬检查命中路径：用硬编码 skill 直接驱动，不走 LLM 路由
            session_result = await code_fixer.run_skill_guided_session(
                problem_summary=pending_problem_summary or '确定性硬检查命中',
                skill_files=pending_skill_files,
                detail=pending_problem_detail,
                design_doc=design_doc
            )
        else:
            session_result = await code_fixer.run_optimization_session(
                evaluation_report=evaluation_report,
                design_doc=design_doc,
                interactive=False
            )

        # 消费完毕，清理本轮待处理标记，避免残留影响下一轮
        if self.session:
            for key in ('pending_skill_files', 'pending_problem_summary', 'pending_problem_detail'):
                self.session.pop(key, None)

        success = session_result.get('success', False)
        if success:
            self.logger.info(f"✓ 优化会话完成，修改 {len(session_result.get('modification_results', []))} 个文件")
        else:
            self.logger.warning("优化会话未成功完成")

        return {
            'success': success,
            'optimization_passed': session_result.get('optimization_passed', False),
            'solved': session_result.get('solved', {}),
            'modification_results': session_result.get('modification_results', []),
            'message': '优化会话完成',
            'session_result': session_result
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

        # 3.45 外生变量序列生成：提取纯 cause 根驱动，生成随时间变化的数据文件供运行时读取
        self.logger.info("\n阶段 3.45: 外生变量序列生成")
        if not await self._run_exogenous_variable_generation(design_results, coding_results):
            self.logger.warning("外生变量生成未完成，influences 将经 fallback 回退内部计算，流程继续")

        # 3.4 Influence 机制预检：用虚拟数据验证 influences.yaml 是否真的会静默跳过 / 报错
        if not await self._run_influence_preflight(max_fix_attempts=self.retries['influence_preflight']):
            self.auto_mode = False
            return {
                'status': 'failed',
                'phase': 'influence_preflight',
                'project_dir': project_dir,
                'design_results': design_results,
                'coding_results': coding_results,
                'optimization_history': []
            }

        # 3.5 冒烟测试：先用最小规模 p=5, y=2 验证代码可运行
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, 'projects', self.current_simulation_name, 'config', 'simulation_config.yaml')
        original_scale = self._get_simulation_scale(config_path)
        can_restore_scale = (
            original_scale.get('population') is not None
            and original_scale.get('years') is not None
        )
        needs_smoke_test = (
            can_restore_scale
            and (
                original_scale.get('population') != self.SMOKE_TEST_POPULATION
                or original_scale.get('years') != self.SMOKE_TEST_YEARS
            )
        )

        if not can_restore_scale:
            error_detail = original_scale.get('error') or '未知原因'
            self.logger.warning(f"⚠️ 无法读取原始设定规模，跳过冒烟测试，直接进入正式运行。原因: {error_detail}")
        elif needs_smoke_test:
            self.logger.info("\n" + "=" * 50)
            self.logger.info("阶段 3.5: 冒烟测试（最小规模 p=5, y=2）")
            self.logger.info("=" * 50)
            self.logger.info(
                f"原始设定规模: pop={original_scale.get('population')}, "
                f"years={original_scale.get('years')}"
            )

            if self._set_simulation_scale(config_path, self.SMOKE_TEST_POPULATION, self.SMOKE_TEST_YEARS):
                self.logger.info("开始以最小规模运行，确认代码无报错...")
                smoke_result = await self.run_simulation(coding_results, max_fix_attempts=self.retries['smoke_test'])

                if smoke_result != 'small_scale_completed' and not smoke_result:
                    self.logger.error("❌ 冒烟测试失败，工作流程终止")
                    self.auto_mode = False
                    return {
                        'status': 'failed',
                        'phase': 'smoke_test',
                        'project_dir': project_dir,
                        'design_results': design_results,
                        'coding_results': coding_results,
                        'optimization_history': []
                    }

                # 恢复原始设定规模
                self.logger.info("✓ 冒烟测试通过，恢复原始设定规模...")
                self._set_simulation_scale(
                    config_path,
                    original_scale.get('population'),
                    original_scale.get('years'),
                    time_key=original_scale.get('time_key')
                )
            else:
                self.logger.error("❌ 无法设置冒烟测试规模，工作流程终止")
                self.auto_mode = False
                return {
                    'status': 'failed',
                    'phase': 'smoke_test_setup',
                    'project_dir': project_dir,
                    'design_results': design_results,
                    'coding_results': coding_results,
                    'optimization_history': []
                }
        else:
            self.logger.info("\n阶段 3.5: 当前设定规模已是冒烟测试规模，跳过额外冒烟测试")

        # 4-5. 运行模拟和评估优化循环
        optimization_history = []
        for iteration in range(1, max_iterations + 1):
            # 阶段 4: 运行模拟
            self.logger.info(f"\n阶段 4: 运行模拟 (第 {iteration} 轮)")
            simulation_successful = await self.run_simulation(coding_results, max_fix_attempts=self.retries['full_run'])

            # 自动模式：若返回 small_scale_completed 且当前仍为小规模配置，
            # 说明原始设定规模就是最小规模，无需再放大，直接进入评估。
            if (
                self.auto_mode
                and simulation_successful == 'small_scale_completed'
                and not self._auto_scaled_up_after_prototype
            ):
                if self._is_small_scale_config(config_path):
                    self.logger.info("当前规模即为最小规模，直接进行评估...")
                    self._auto_scaled_up_after_prototype = True
                else:
                    # 理论上不会到达此处：冒烟测试后已恢复原始规模
                    self.logger.warning("⚠️ 运行结果标记为小规模，但配置已不是小规模，继续评估")
                    self._auto_scaled_up_after_prototype = True

            if not simulation_successful:
                self.logger.error("❌ 模拟运行失败，工作流程终止")
                break
            
            self.logger.info("✅ 模拟运行完成")
            
            # 阶段 5: 评估结果并优化
            self.logger.info(f"\n阶段 5: 评估结果并优化 (第 {iteration} 轮)")
            evaluation_results = await self.run_evaluation_and_optimization_phase(simulation_successful)
            
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
        应用机制调整，调用CodeFixerAgent进行具体的代码修改

        Args:
            requirements_text: 格式化的需求字符串

        Returns:
            bool: 是否成功应用
        """
        self.logger.info("开始应用机制调整")
        self.logger.info(f"需求内容:\n{requirements_text}")
        
        try:
            # 确保代码修复Agent已初始化
            code_fixer = await self._ensure_code_fixer()

            # 直接将需求文本传给代码修复Agent处理
            print(f"\n{'='*80}")
            print("将需求发送给代码修复Agent进行实现...")
            print(f"{'='*80}")

            # 调用CodeFixerAgent的apply_user_adjustment方法
            success = await code_fixer.apply_user_adjustment(
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
                        selected_modules = modules_config.get('selected_modules')
                        if isinstance(selected_modules, list):
                            for module_name in selected_modules:
                                if isinstance(module_name, str):
                                    print(f"  - {module_name}")
                        else:
                            print("  (modules_config.yaml 的 selected_modules 不是 list[str]，无法展示模块列表)")
            
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
                main_py_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'projects', self.current_simulation_name, 'main.py'
                )
                if os.path.exists(main_py_path):
                    print(f"  - Main (自定义hook): {main_py_path}")
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

        # 阶段 3.45: 外生变量序列生成
        self.logger.info("\n阶段 3.45: 外生变量序列生成")
        if not await self._run_exogenous_variable_generation():
            self.logger.warning("外生变量生成未完成，influences 将经 fallback 回退内部计算，流程继续")

        # 阶段 3.4: Influence 机制预检（虚拟数据）
        if not await self._run_influence_preflight(max_fix_attempts=self.retries['influence_preflight']):
            self.logger.error("❌ Influence 预检失败，工作流程终止")
            return {
                'status': 'failed',
                'phase': 'influence_preflight',
                'project_dir': project_dir,
                'config_dir': self.current_config_dir,
                'design_results': design_results,
                'coding_results': coding_results,
                'optimization_history': [],
                'history': phase_history
            }

        # 阶段 3.5: 冒烟测试（最小规模 p=5, y=2）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, 'projects', self.current_simulation_name, 'config', 'simulation_config.yaml')
        original_scale = self._get_simulation_scale(config_path)
        can_restore_scale = (
            original_scale.get('population') is not None
            and original_scale.get('years') is not None
        )
        needs_smoke_test = (
            can_restore_scale
            and (
                original_scale.get('population') != self.SMOKE_TEST_POPULATION
                or original_scale.get('years') != self.SMOKE_TEST_YEARS
            )
        )

        if not can_restore_scale:
            error_detail = original_scale.get('error') or '未知原因'
            print(f"\n⚠️ 无法读取原始设定规模，跳过冒烟测试，直接进入正式运行。原因: {error_detail}")
            self.logger.warning(f"无法读取原始设定规模，跳过冒烟测试，直接进入正式运行。原因: {error_detail}")
        elif needs_smoke_test:
            print("\n" + "=" * 80)
            print("阶段 3.5: 冒烟测试（最小规模 p=5, y=2）")
            print("=" * 80)
            print(f"原始设定规模: pop={original_scale.get('population')}, years={original_scale.get('years')}")
            print("将临时以最小规模运行，确认代码无报错后恢复原始规模...")
            self.logger.info("\n阶段 3.5: 冒烟测试（最小规模 p=5, y=2）")
            self.logger.info(
                f"原始设定规模: pop={original_scale.get('population')}, "
                f"years={original_scale.get('years')}"
            )

            if self._set_simulation_scale(config_path, self.SMOKE_TEST_POPULATION, self.SMOKE_TEST_YEARS):
                print("\n开始冒烟测试...")
                self.logger.info("开始冒烟测试...")

                # 冒烟测试：每轮最多尝试 5 次（含自动纠错），失败则询问用户是否重试
                smoke_result = await self.run_simulation(coding_results, max_fix_attempts=self.retries['smoke_test'])
                while smoke_result != 'small_scale_completed' and not smoke_result:
                    print("\n❌ 冒烟测试失败（已尝试 5 次）")
                    self.logger.warning("冒烟测试失败（已尝试 5 次）")
                    print("是否重新运行冒烟测试？")
                    print("  - 输入 'yes' 或 'y' 重新运行（再尝试 5 次）")
                    print("  - 按 Enter 或输入其他内容终止工作流程")
                    retry_input = input("\n您的选择: ").strip().lower()
                    if retry_input in ['yes', 'y']:
                        print("\n重新运行冒烟测试...")
                        self.logger.info("用户选择重试冒烟测试")
                        smoke_result = await self.run_simulation(coding_results, max_fix_attempts=self.retries['smoke_test'])
                        continue

                    print("\n❌ 冒烟测试失败，工作流程终止")
                    self.logger.error("冒烟测试失败，工作流程终止")
                    return {
                        'status': 'failed',
                        'phase': 'smoke_test',
                        'project_dir': project_dir,
                        'config_dir': self.current_config_dir,
                        'design_results': design_results,
                        'coding_results': coding_results,
                        'optimization_history': [],
                        'history': phase_history
                    }

                print("\n✓ 冒烟测试通过，恢复原始设定规模...")
                self.logger.info("冒烟测试通过，恢复原始设定规模")
                self._set_simulation_scale(
                    config_path,
                    original_scale.get('population'),
                    original_scale.get('years'),
                    time_key=original_scale.get('time_key')
                )
            else:
                print("\n❌ 无法设置冒烟测试规模，工作流程终止")
                self.logger.error("无法设置冒烟测试规模，工作流程终止")
                return {
                    'status': 'failed',
                    'phase': 'smoke_test_setup',
                    'project_dir': project_dir,
                    'config_dir': self.current_config_dir,
                    'design_results': design_results,
                    'coding_results': coding_results,
                    'optimization_history': [],
                    'history': phase_history
                }
        else:
            print("\n阶段 3.5: 当前设定规模已是冒烟测试规模，跳过额外冒烟测试")
            self.logger.info("当前设定规模已是冒烟测试规模，跳过额外冒烟测试")

        # ============ 阶段 4-5: 运行模拟和评估优化循环 ============
        print("\n" + "=" * 80)
        print("阶段 4-5: 运行模拟和评估优化循环")
        print("=" * 80)
        self.logger.info("\n阶段 4-5: 运行模拟和评估优化循环")
        
        optimization_history = []
        max_iterations = 10
        
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
                
                sim_result = await self.run_simulation(coding_results, max_fix_attempts=self.retries['full_run'])
                
                # 检查是否是冒烟测试完成
                if sim_result == 'small_scale_completed':
                    print("\n✅ 冒烟测试运行成功！")
                    self.logger.info(f"第 {iteration} 轮冒烟测试运行成功")

                    # 提供机制解释与调整选项
                    while True:
                        print("\n请选择下一步操作：")
                        print("  - 输入 'adjust' 进入机制解释与调整会话")
                        print("  - 输入 'continue' 继续使用设定规模运行")
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

                                            # 询问是否重新运行冒烟测试
                                            print("\n调整已应用，是否重新运行冒烟测试验证？")
                                            print("  - 输入 'yes' 或 'y' 重新运行冒烟测试")
                                            print("  - 按Enter继续选择下一步操作")

                                            retest_input = input("\n您的选择: ").strip().lower()
                                            if retest_input in ['yes', 'y']:
                                                print("\n重新运行冒烟测试...")
                                                sim_result = await self.run_simulation(coding_results, max_fix_attempts=self.retries['full_run'])
                                                if sim_result != 'small_scale_completed':
                                                    if sim_result:
                                                        print("\n⚠️ 调整后运行成功，但不是冒烟测试规模")
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
                            # 继续使用设定规模运行
                            print("\n准备使用设定规模运行...")
                            print("请输入运行参数（按Enter使用原始设定规模）:")
                            try:
                                default_pop = original_scale.get('population') if original_scale.get('population') is not None else 300
                                default_steps = original_scale.get('years') if original_scale.get('years') is not None else 50
                                new_pop_input = input(f"人口数量 (默认{default_pop}): ").strip()
                                new_steps_input = input(f"模拟时间步 (默认{default_steps}): ").strip()
                                new_pop = int(new_pop_input) if new_pop_input else default_pop
                                new_steps = int(new_steps_input) if new_steps_input else default_steps

                                # 更新配置文件
                                config_path = os.path.join(
                                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    'projects',
                                    self.current_simulation_name,
                                    'config',
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
                                print("\n开始使用设定规模运行...")

                                # 重新运行模拟
                                sim_result = await self.run_simulation(coding_results, max_fix_attempts=self.retries['full_run'])
                                if sim_result and sim_result != 'small_scale_completed':
                                    simulation_successful = True
                                    print("\n✅ 设定规模运行成功！")
                                    self.logger.info(f"第 {iteration} 轮设定规模运行成功")
                                    break
                                else:
                                    simulation_successful = False
                                    print("\n❌ 设定规模运行失败")
                                    self.logger.error(f"第 {iteration} 轮设定规模运行失败")
                                    break

                            except ValueError:
                                self.logger.error("输入的参数无效，取消设定规模运行")
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
                    if evaluation_results.get('optimization_passed', False):
                        print("\n✓ 本轮优化已通过问题解决检查，需重新运行+评估确认效果...")
                    else:
                        print("\n⚠️  本轮优化未通过问题解决检查，将再次尝试...")
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


