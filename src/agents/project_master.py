
from .shared_imports import *
from .sim_designer import SystemArchitectAgent
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

    async def parse_user_requirement(self, requirement_text):
        """
        解析用户需求，确定模拟名称和基本信息。
        """
        prompt = f"""你是一位项目管理师，请分析以下用户需求，提取关键信息并返回JSON格式：

用户需求：
{requirement_text}

请提取以下信息：
1. simulation_name: 模拟实验的简短英文名称（用下划线连接，如 climate_migration_sim）
2. description: 简短描述
3. estimated_complexity: 复杂度评估（simple/medium/complex）
4. key_requirements: 关键需求列表

返回格式：
{{
  "simulation_name": "名称",
  "description": "描述",
  "estimated_complexity": "复杂度",
  "key_requirements": ["需求1", "需求2"]
}}"""
        
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
        配置文件直接放在项目根目录的config_[模拟名称]文件夹下。
        """
        # 项目根目录（AgentWorld项目根目录）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 创建config_[模拟名称]文件夹
        config_dir = os.path.join(project_root, f'config_{simulation_name}')
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
        prompt = f"""你是一位质量审查专家，请评估以下{content_type}的质量：

内容：
{content}

评估标准：
{criteria}

请返回JSON格式的评估结果：
{{
  "is_valid": true/false,
  "score": 0-100的分数,
  "feedback": "详细反馈",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}}"""
        
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
        运行设计阶段，调用 SystemArchitectAgent。
        
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
        designer = SystemArchitectAgent(
            agent_id='system_architect_001',
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
        
        # 选择模块
        self.logger.info("步骤 2: 选择系统模块")
        
        # 传递上一版本的模块和用户反馈（如果有）
        previous_modules = previous_version.get('modules', None) if previous_version else None
        modules = await designer.select_modules(parsed_req, previous_modules, user_feedback)
        self.logger.info(f"选择的模块: {modules}")
        
        # 生成设计文档
        self.logger.info("步骤 3: 生成设计文档")
        
        # 构建带反馈的参数
        design_context = {
            'parsed_req': parsed_req,
            'modules': modules
        }
        
        if previous_version and user_feedback:
            design_context['previous_description'] = previous_version.get('description_md', '')
            design_context['user_feedback'] = user_feedback
        
        description_md = await designer.generate_description_md(
            design_context.get('parsed_req'),
            design_context.get('modules'),
            design_context.get('previous_description'),
            design_context.get('user_feedback')
        )
        
        if description_md:
            desc_path = os.path.join(self.current_config_dir, 'description.md')
            with open(desc_path, 'w', encoding='utf-8') as f:
                f.write(description_md)
            self.logger.info(f"设计文档已保存: {desc_path}")
        
        # 生成配置文件（experiment_template.yaml）
        self.logger.info("步骤 4: 生成实验配置文件 (experiment_template.yaml)")
        
        config_context = {
            'modules': modules,
            'parsed_req': parsed_req,
            'description_md': description_md
        }
        
        if previous_version and user_feedback:
            config_context['previous_config'] = previous_version.get('config_files', [])
            config_context['user_feedback'] = user_feedback
        
        config_files = await designer.generate_config_files(
            config_context.get('modules'),
            config_context.get('parsed_req'),
            config_context.get('description_md'),
            config_context.get('previous_config'),
            config_context.get('user_feedback')
        )
        self.logger.info(f"配置文件已生成: {config_files}")
        
        return {
            'parsed_requirement': parsed_req,
            'modules': modules,
            'description_md': description_md,
            'config_files': config_files
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
        
        coder = CodeArchitectAgent(
            agent_id='code_architect_001',
            simulator_output_dir=simulator_dir,
            main_output_dir=entrypoints_dir,
            docs_dir=self.docs_dir,
            config_dir=self.current_config_dir,
            config_template_dir=self.config_template_dir,
            simulation_name=self.current_simulation_name
        )
        
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
        
        simulator_files = await coder.generate_simulator_code(
            description_with_context,
            design_results.get('experiment_template_yaml', '')
        )
        
        if not simulator_files:
            self.logger.error("生成simulator代码失败")
            return {'status': 'failed', 'reason': 'simulator generation failed'}
        
        simulator_file_path = simulator_files[0]
        self.logger.info(f"Simulator代码已生成: {simulator_file_path}")
        
        # === 步骤2: 检查并补完simulator函数 ===
        self.logger.info("步骤 2: 检查并补完simulator函数实现")
        refined_simulator = await coder.refine_simulator_functions(
            simulator_file_path,
            description_with_context,
            design_results['modules']
        )
        
        if refined_simulator:
            self.logger.info("Simulator函数已补完")
        else:
            self.logger.warning("Simulator函数补完失败，保持原文件")
        
        # === 步骤3: 生成main入口文件完整代码 ===
        self.logger.info("步骤 3: 生成main入口文件完整代码")
        main_files = await coder.generate_main_file(
            description_with_context,
            simulator_file_path
        )
        
        if not main_files:
            self.logger.error("生成main文件失败")
            return {'status': 'failed', 'reason': 'main file generation failed'}
        
        main_file_path = main_files[0]
        self.logger.info(f"Main文件已生成: {main_file_path}")
        
        # === 步骤4: 检查并补完main函数 ===
        self.logger.info("步骤 4: 检查并补完main函数实现")
        refined_main = await coder.refine_main_functions(
            main_file_path,
            simulator_file_path,
            description_with_context,
            design_results['modules']
        )
        
        if refined_main:
            self.logger.info("Main函数已补完")
        else:
            self.logger.warning("Main函数补完失败，保持原文件")
        
        # === 步骤5: 生成配置文件（按顺序，每次一个） ===
        self.logger.info("步骤 5: 生成配置文件")
        config_files = []
        previous_configs = {}
        
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
        
        for config_filename in required_configs:
            self.logger.info(f"  生成配置文件: {config_filename}")
            description_with_config_context = design_results['description_md'] + prev_config_context
            
            config_path = await coder.generate_config_file(
                config_filename,
                description_with_config_context,
                design_results['modules'],
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
        
        # === 步骤6: 生成提示词文件（如果需要） ===
        self.logger.info("步骤 6: 生成提示词文件")
        prompt_files = []
        modules = design_results.get('modules', {})
        
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
        
        # 根据涉及的模块决定生成哪些提示词文件
        prompt_file_mapping = {
            'government': 'government_prompts.yaml',
            'rebellion': 'rebels_prompts.yaml',
            'residents': 'residents_prompts.yaml'
        }
        
        for module_key, prompt_filename in prompt_file_mapping.items():
            # 检查是否需要该提示词文件
            if module_key in str(modules).lower() or module_key == 'residents':  # residents总是需要
                self.logger.info(f"  生成提示词文件: {prompt_filename}")
                description_with_prompt_context = design_results['description_md'] + prev_prompt_context
                
                prompt_path = await coder.generate_prompt_file(
                    prompt_filename,
                    description_with_prompt_context,
                    design_results['modules'],
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

    async def run_simulation(self, coding_results):
        """
        运行模拟（调用现有模拟系统）。
        """
        self.logger.info("=" * 50)
        self.logger.info("运行模拟")
        self.logger.info("=" * 50)
        
        # TODO: 这里应该调用实际的模拟系统
        # 目前返回模拟的结果路径
        results_dir = os.path.join(self.current_project_dir, 'results')
        result_file = os.path.join(results_dir, 'simulation_results.json')
        
        # 创建模拟结果（实际应该运行模拟系统）
        mock_results = {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'total_steps': 100,
                'agents_count': 50,
                'average_satisfaction': 0.75
            }
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(mock_results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"模拟完成，结果保存至: {result_file}")
        return result_file

    async def run_evaluation_phase(self, simulation_results_path):
        """
        运行评估阶段，调用 ResearchAnalystAgent。
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
        
        # 评估模拟结果
        self.logger.info("步骤 1: 评估模拟结果")
        evaluation_report = await analyst.evaluate_simulation(simulation_results_path)
        self.logger.info("评估报告已生成")
        
        # 分析关键指标
        self.logger.info("步骤 2: 分析关键指标")
        metrics_analysis = await analyst.analyze_metrics(simulation_results_path)
        self.logger.info("指标分析已完成")
        
        # 提出调整建议
        self.logger.info("步骤 3: 提出调整建议")
        config_file = os.path.join(self.current_config_dir, 'simulation_config.yaml')
        if not os.path.exists(config_file):
            # 尝试找到其他配置文件
            config_files = [f for f in os.listdir(self.current_config_dir) 
                          if f.endswith('.yaml') or f.endswith('.json')]
            if config_files:
                config_file = os.path.join(self.current_config_dir, config_files[0])
        
        adjustment_proposals = await analyst.propose_adjustments(
            evaluation_report,
            metrics_analysis,
            config_file
        )
        self.logger.info("调整建议已生成")
        
        return {
            'evaluation_report': evaluation_report,
            'metrics_analysis': metrics_analysis,
            'adjustment_proposals': adjustment_proposals
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
        
        # 4. 运行模拟
        self.logger.info("\n阶段 4: 运行模拟")
        # simulation_results_path = await self.run_simulation(coding_results)
        
        # 5. 评估阶段
        self.logger.info("\n阶段 5: 结果评估")
        # evaluation_results = await self.run_evaluation_phase(simulation_results_path)
        
        # 6. 迭代优化（可选）
        # iteration_history = []
        # for i in range(max_iterations):
        #     self.logger.info(f"\n阶段 6.{i+1}: 迭代优化 (第 {i+1}/{max_iterations} 轮)")
            
        #     # 判断是否需要继续迭代
        #     should_iterate = await self.should_continue_iteration(evaluation_results)
        #     if not should_iterate:
        #         self.logger.info("评估结果已达标，无需继续迭代")
        #         break
            
        #     # 应用调整并重新运行
        #     iteration_success = await self.run_iteration(evaluation_results)
        #     if iteration_success:
        #         simulation_results_path = await self.run_simulation(coding_results)
        #         evaluation_results = await self.run_evaluation_phase(simulation_results_path)
        #         iteration_history.append({
        #             'iteration': i + 1,
        #             'results': evaluation_results
        #         })
        #     else:
        #         break
        
        # 7. 生成最终报告
        # self.logger.info("\n阶段 7: 生成最终报告")
        # if iteration_history:
        #     results_dir = os.path.join(self.current_project_dir, 'results')
        #     analyst = ResearchAnalystAgent(
        #         agent_id='research_analyst_001',
        #         output_dir=results_dir,
        #         docs_dir=self.docs_dir
        #     )
        #     final_summary = await analyst.generate_optimization_summary(iteration_history)
        #     self.logger.info("最终优化报告已生成")
        
        self.logger.info("=" * 80)
        self.logger.info("工作流程完成")
        self.logger.info(f"项目目录: {project_dir}")
        self.logger.info("=" * 80)
        
        return {
            'project_dir': project_dir,
            'design_results': design_results,
            'coding_results': coding_results,
            # 'simulation_results': simulation_results_path,
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
            print(f"\n✓ 选择的模块:")
            print(f"  {json.dumps(design_results['modules'], ensure_ascii=False, indent=2)}")
            print(f"\n✓ 设计文档: {self.current_config_dir}/description.md")
            if design_results.get('config_files'):
                print(f"✓ 配置文件: {design_results['config_files']}")
            
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
                print("\n✓ 编码阶段确认，工作流程完成！")
                self.logger.info("用户确认编码结果，流程完成")
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
        
        # ============ 完成 ============
        print("\n" + "=" * 80)
        print("交互式工作流程完成！")
        print("=" * 80)
        print(f"\n项目目录: {project_dir}")
        print(f"配置目录: {self.current_config_dir}")
        print(f"\n设计版本数: {len(phase_history['design'])}")
        print(f"编码版本数: {len(phase_history['coding'])}")
        
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
            'history': phase_history
        }

    async def should_continue_iteration(self, evaluation_results):
        """
        判断是否应该继续迭代优化。
        """
        prompt = f"""根据以下评估结果，判断是否需要继续迭代优化：

评估报告：
{evaluation_results.get('evaluation_report', '')}

指标分析：
{evaluation_results.get('metrics_analysis', '')}

请返回JSON格式：
{{
  "should_continue": true/false,
  "reason": "原因说明"
}}"""
        
        response = await self.generate_llm_response(prompt)
        try:
            result = json.loads(response)
            return result.get('should_continue', False)
        except Exception:
            return False
