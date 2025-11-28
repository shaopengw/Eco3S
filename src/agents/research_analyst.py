
from src.utils.custom_logger import CustomLogger
from .shared_imports import *

class ResearchAnalystAgent(BaseAgent):
    """
    实验评估师/研究助手Agent，继承BaseAgent，负责评估模拟结果、分析指标、提出调整建议并应用优化。
    """
    def __init__(self, agent_id, output_dir, config_dir):
        # super().__init__(agent_id, group_type='code_architect', window_size=3, 
		#         model_api_name='CLAUDE', model_type_name='claude-sonnet-4-5-20250929')
        super().__init__(agent_id, group_type='research_analyst', window_size=3)
        
        # 加载prompts配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'research_analyst_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']
        self.output_dir = output_dir
        self.config_dir = config_dir
        self.logger = CustomLogger('research_analyst').logger

    def read_config_descriptions(self):
        """
        读取file_descriptions.yaml中的config_files_description和prompt_files_description，
        并根据config_dir下的实际文件生成描述字符串。
        """
        file_descriptions_path = os.path.normpath(os.path.join(os.path.dirname(self.config_dir), 'template', 'file_descriptions.yaml'))
        self.logger.info(f"尝试读取文件描述文件: {file_descriptions_path}")
        all_descriptions = {}
        if not os.path.exists(file_descriptions_path):
            self.logger.warning(f"file_descriptions.yaml不存在: {file_descriptions_path}")
        else:
            try:
                with open(file_descriptions_path, 'r', encoding='utf-8') as f:
                    all_descriptions = yaml.safe_load(f)
            except Exception as e:
                self.logger.error(f"读取file_descriptions.yaml失败: {e}")

        config_files_desc = all_descriptions.get('config_files_description', {})
        prompt_files_desc = all_descriptions.get('prompt_files_description', {})

        # 获取config_dir下的所有文件
        actual_files = [f for f in os.listdir(self.config_dir) if os.path.isfile(os.path.join(self.config_dir, f))]

        description_str = "当前项目目录下的配置文件及其作用：\n"
        for file_name in actual_files:
            if file_name in config_files_desc:
                description_str += f"- {file_name}: {config_files_desc[file_name]}\n"
            elif file_name in prompt_files_desc:
                description_str += f"- {file_name}: {prompt_files_desc[file_name]}\n"
        
        if not actual_files:
            description_str += "  (未找到任何配置文件或提示词文件)\n"

        self.logger.info(f"✓ 已生成配置文件描述字符串")
        return description_str

    async def evaluate_simulation(self, simulation_results, design_doc=""):
        """
        调用大模型评估模拟结果，判断是否符合预期趋势。
        
        Args:
            simulation_results: 模拟结果数据（可以是字典、列表或文件路径）
            design_doc: 设计文档内容（用于了解预期目标）
        
        Returns:
            评估报告字符串
        """
        results_file_path = ""
        results_data = ""
        
        # 如果是字符串，尝试作为文件路径处理
        if isinstance(simulation_results, str):
            # 检查文件是否存在
            if os.path.isfile(simulation_results):
                results_file_path = simulation_results
                self.logger.info(f"读取模拟结果文件: {simulation_results}")
                
                try:
                    # 尝试多种编码格式
                    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
                    for encoding in encodings:
                        try:
                            with open(simulation_results, 'r', encoding=encoding) as f:
                                if simulation_results.endswith('.json'):
                                    results_data = json.load(f)
                                    results_data = str(results_data)[:10000]
                                elif simulation_results.endswith('.csv'):
                                    lines = f.readlines()
                                    results_data = ''.join(lines[:100])
                                else:
                                    results_data = f.read()[:10000]
                            self.logger.info(f"已读取文件（编码: {encoding}），数据长度: {len(results_data)} 字符")
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        raise Exception("无法用任何编码格式读取文件")
                except Exception as e:
                    self.logger.error(f"读取文件失败: {e}")
                    results_data = f"[文件读取失败: {e}]"
            else:
                # 文件不存在，记录警告
                self.logger.warning(f"⚠️ 指定的文件路径不存在: {simulation_results}")
                self.logger.warning(f"将路径字符串作为数据内容处理（这可能不是预期行为）")
                results_data = f"[警告：文件不存在 - {simulation_results}]\n\n请确保模拟已成功运行并生成了结果文件。"
        else:
            # 不是字符串，直接转换为字符串
            results_data = str(simulation_results)[:10000]
            self.logger.info(f"使用传入的数据对象，数据长度: {len(results_data)} 字符")
        
        prompt = self.prompts['evaluate_simulation_prompt'].format(
            results_data=results_data,
            design_doc=design_doc
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 保存评估报告
        report_path = os.path.join(os.path.dirname(self.output_dir), 'evaluation_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        self.logger.info(f"✓ 评估报告已保存: {report_path}")
        
        return response

    async def diagnose_config_issues(self, evaluation_report, design_doc=""):
        """
        根据评估报告，诊断需要修改哪些配置文件或提示词。
        在实验分析第一步结束后，读取config_files_description和prompt_files_description。
        
        Args:
            evaluation_report: 评估报告
            config_dir: 配置文件目录
            design_doc: 设计文档内容
        
        Returns:
            诊断结果文件路径
        """
    
        # 读取配置文件和提示词文件的描述信息
        config_context = self.read_config_descriptions()

        prompt = self.prompts['diagnose_config_issues_prompt'].format(
            evaluation_report=evaluation_report,
            design_doc=design_doc,
            config_context=config_context
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 清理响应，去除markdown代码块标记
        clean_response = response
        if '```json' in response:
            # 提取JSON内容，去除markdown标记
            json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
            if json_match:
                clean_response = json_match.group(1)
        
        # 保存诊断结果
        diagnosis_path = os.path.join(os.path.dirname(self.output_dir), 'diagnosis_result.json')
        with open(diagnosis_path, 'w', encoding='utf-8') as f:
            f.write(clean_response)
        
        self.logger.info(f"✓ 诊断结果已保存: {diagnosis_path}")
        
        return diagnosis_path
