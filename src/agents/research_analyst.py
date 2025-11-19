
from .shared_imports import *

class ResearchAnalystAgent(BaseAgent):
    """
    实验评估师/研究助手Agent，继承BaseAgent，负责评估模拟结果、分析指标、提出调整建议并应用优化。
    """
    def __init__(self, agent_id, output_dir, docs_dir):
        super().__init__(agent_id, group_type='research_analyst', window_size=3)
        
        # 加载prompts配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'research_analyst_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']
        self.output_dir = output_dir
        self.docs_dir = docs_dir
        self.logger = LogManager.get_logger('research_analyst')

    def read_config_descriptions(self, config_dir):
        """
        读取modules_config.yaml中的config_files_description和prompt_files_description。
        只在实验分析第一步结束后调用。
        """
        modules_config_path = os.path.join(config_dir, 'modules_config.yaml')
        if not os.path.exists(modules_config_path):
            self.logger.warning(f"modules_config.yaml不存在: {modules_config_path}")
            return {'config_files_description': {}, 'prompt_files_description': {}}
        try:
            with open(modules_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            descriptions = {
                'config_files_description': config.get('config_files_description', {}),
                'prompt_files_description': config.get('prompt_files_description', {})
            }
            
            self.logger.info(f"✓ 已读取配置文件描述：{len(descriptions['config_files_description'])}个配置文件，{len(descriptions['prompt_files_description'])}个提示词文件")
            return descriptions
            
        except Exception as e:
            self.logger.error(f"读取配置文件描述失败: {e}")
            return {'config_files_description': {}, 'prompt_files_description': {}}

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
            results_file_path=results_file_path,
            results_data=results_data,
            design_doc=design_doc
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 保存评估报告
        report_path = os.path.join(self.output_dir, 'evaluation_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        self.logger.info(f"✓ 评估报告已保存: {report_path}")
        
        return response

    async def diagnose_config_issues(self, evaluation_report, config_dir, design_doc=""):
        """
        根据评估报告，诊断需要修改哪些配置文件或提示词。
        在实验分析第一步结束后，读取config_files_description和prompt_files_description。
        
        Args:
            evaluation_report: 评估报告
            config_dir: 配置文件目录
            design_doc: 设计文档内容
        
        Returns:
            诊断结果（JSON格式）
        """
    
        # 读取配置文件和提示词文件的描述信息
        descriptions = self.read_config_descriptions(config_dir)
        print(descriptions)
        config_context = ""
        
        if descriptions['config_files_description'] or descriptions['prompt_files_description']:
            config_context = f"""

可用配置文件及其作用说明：
{yaml.dump(descriptions['config_files_description'], allow_unicode=True)}

可用提示词文件及其作用说明：
{yaml.dump(descriptions['prompt_files_description'], allow_unicode=True)}
"""
        
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
        diagnosis_path = os.path.join(self.output_dir, 'diagnosis_result.json')
        with open(diagnosis_path, 'w', encoding='utf-8') as f:
            f.write(clean_response)
        
        self.logger.info(f"✓ 诊断结果已保存: {diagnosis_path}")
        
        return response

    async def modify_file_sequentially(self, diagnosis_result, config_dir, design_doc=""):
        """
        根据diagnosis_result依次修改配置文件，只修改指定参数的值。
        """
        # 解析诊断结果
        import re
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', diagnosis_result, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*"diagnosis"[\s\S]*\}', diagnosis_result, re.DOTALL)
        
        if not json_match:
            self.logger.error("无法解析诊断结果")
            return []
        
        try:
            diagnosis = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            return []
        
        files_to_modify = diagnosis.get('diagnosis', {}).get('files_to_modify', [])
        if not files_to_modify:
            self.logger.info("无需修改任何文件")
            return []
        
        results = []
        for file_info in files_to_modify:
            file_name = file_info.get('file_name')
            file_path = os.path.join(config_dir, file_name)
            reason = file_info.get('reason', '')
            
            self.logger.info(f"正在处理文件 : {file_name}")
            self.logger.info(f"修改原因: {reason}")
            
            if not os.path.exists(file_path):
                self.logger.warning(f"文件不存在: {file_path}")
                continue
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                current_config = f.read()
            
            # 生成修改方案
            prompt = self.prompts['generate_config_modifications_prompt'].format(
                diagnosis_result=json.dumps(file_info, ensure_ascii=False),
                current_config=current_config[:5000],
                design_doc=design_doc
            )
            
            response = await self.generate_llm_response(prompt)
            
            # 解析并应用修改
            json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    modifications = json.loads(json_match.group(1))
                    modification_list = modifications.get('modifications', [])
                    
                    if modification_list:
                        result = await self._apply_modifications(file_path, modification_list)
                        results.append({'file_name': file_name, 'result': result})
                        self.logger.info(f"✓ {file_name} 已修改")
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析失败 {file_name}: {e}")
        
        return results
    
    async def _apply_modifications(self, file_path, modifications):
        """
        精确修改文件中的指定参数，保持文件结构不变。
        """
        # 创建备份
        backup_path = file_path + f'.backup_{int(asyncio.get_event_loop().time())}'
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        changes = []
        
        if file_path.endswith(('.yaml', '.yml')):
            # 处理YAML文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            for mod in modifications:
                param = mod.get('parameter')
                new_value = mod.get('value')
                
                if param in data:
                    old_value = data[param]
                    data[param] = new_value
                    changes.append(f"{param}: {old_value} -> {new_value}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
                
        elif file_path.endswith('.json'):
            # 处理JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for mod in modifications:
                param = mod.get('parameter')
                new_value = mod.get('value')
                
                if param in data:
                    old_value = data[param]
                    data[param] = new_value
                    changes.append(f"{param}: {old_value} -> {new_value}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        else:
            # 处理文本文件（提示词等）
            content = original_content
            for mod in modifications:
                old_text = mod.get('parameter')  # 在文本文件中，parameter是要替换的文本
                new_text = mod.get('value')
                
                if old_text in content:
                    content = content.replace(old_text, new_text)
                    changes.append(f"已替换文本片段")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return {'backup': backup_path, 'changes': changes}