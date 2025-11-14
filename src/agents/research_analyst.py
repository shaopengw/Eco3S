
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
        
        # 如果是文件路径，读取文件内容
        if isinstance(simulation_results, str) and os.path.isfile(simulation_results):
            results_file_path = simulation_results
            with open(simulation_results, 'r', encoding='utf-8') as f:
                if simulation_results.endswith('.json'):
                    results_data = json.load(f)
                    # 限制数据大小
                    results_data = str(results_data)[:10000]
                elif simulation_results.endswith('.csv'):
                    # 只读取前100行
                    lines = f.readlines()
                    results_data = ''.join(lines[:100])
                else:
                    results_data = f.read()[:10000]
        else:
            results_data = str(simulation_results)[:10000]
        
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
        
        Args:
            evaluation_report: 评估报告
            config_dir: 配置文件目录
            design_doc: 设计文档内容
        
        Returns:
            诊断结果（JSON格式）
        """
        # 列出配置目录中的所有文件
        available_files = []
        if os.path.exists(config_dir):
            for file in os.listdir(config_dir):
                if file.endswith(('.yaml', '.yml', '.json', '.md')):
                    available_files.append(file)
        
        available_files_str = '\n'.join([f"  - {f}" for f in available_files])
        
        prompt = self.prompts['diagnose_config_issues_prompt'].format(
            evaluation_report=evaluation_report,
            config_dir=config_dir,
            available_files=available_files_str,
            design_doc=design_doc
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 保存诊断结果
        diagnosis_path = os.path.join(self.output_dir, 'diagnosis_result.json')
        with open(diagnosis_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        self.logger.info(f"✓ 诊断结果已保存: {diagnosis_path}")
        
        return response
    
    async def generate_config_modifications(self, diagnosis_result, config_dir, design_doc=""):
        """
        根据诊断结果，生成具体的配置修改方案。
        
        Args:
            diagnosis_result: 诊断结果
            config_dir: 配置文件目录
            design_doc: 设计文档内容
        
        Returns:
            修改方案列表
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
        
        # 对每个需要修改的文件，生成修改方案
        all_modifications = []
        
        for file_info in files_to_modify:
            file_name = file_info.get('file_name')
            file_path = os.path.join(config_dir, file_name)
            
            if not os.path.exists(file_path):
                self.logger.warning(f"文件不存在: {file_path}")
                continue
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                current_config = f.read()
            
            # 生成修改方案
            prompt = self.prompts['generate_config_modifications_prompt'].format(
                diagnosis_result=json.dumps(file_info, ensure_ascii=False),
                current_config=current_config[:5000],  # 限制长度
                design_doc=design_doc
            )
            
            response = await self.generate_llm_response(prompt)
            
            # 解析修改方案
            json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{[\s\S]*"modifications"[\s\S]*\}', response, re.DOTALL)
            
            if json_match:
                try:
                    modifications = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
                    all_modifications.append({
                        'file_name': file_name,
                        'file_path': file_path,
                        'modifications': modifications.get('modifications', [])
                    })
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析修改方案失败 ({file_name}): {e}")
        
        # 保存所有修改方案
        modifications_path = os.path.join(self.output_dir, 'modification_proposals.json')
        with open(modifications_path, 'w', encoding='utf-8') as f:
            json.dump(all_modifications, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"✓ 修改方案已保存: {modifications_path}")
        
        return all_modifications
    
    async def apply_modifications(self, modification_proposals, config_dir):
        """
        应用修改方案到配置文件。
        
        Args:
            modification_proposals: 修改方案列表
            config_dir: 配置文件目录
        
        Returns:
            应用结果报告
        """
        applied_results = []
        
        for file_proposal in modification_proposals:
            file_name = file_proposal.get('file_name')
            file_path = file_proposal.get('file_path')
            modifications = file_proposal.get('modifications', [])
            
            if not modifications:
                continue
            
            self.logger.info(f"正在修改文件: {file_name}")
            
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith(('.yaml', '.yml')):
                    content = yaml.safe_load(f)
                    file_type = 'yaml'
                elif file_path.endswith('.json'):
                    content = json.load(f)
                    file_type = 'json'
                else:
                    # 文本文件（如提示词）
                    content = f.read()
                    file_type = 'text'
            
            # 备份原文件
            backup_path = file_path + f'.backup_{int(asyncio.get_event_loop().time())}'
            with open(backup_path, 'w', encoding='utf-8') as f:
                if file_type == 'yaml':
                    yaml.dump(content, f, allow_unicode=True)
                elif file_type == 'json':
                    json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    f.write(content)
            
            self.logger.info(f"  - 已备份: {backup_path}")
            
            # 应用修改
            applied_changes = []
            
            for mod in modifications:
                param = mod.get('parameter')
                suggested_value = mod.get('suggested_value')
                reason = mod.get('reason')
                
                if file_type in ['yaml', 'json']:
                    # 结构化配置文件
                    if param in content:
                        old_value = content[param]
                        content[param] = suggested_value
                        applied_changes.append({
                            'parameter': param,
                            'old_value': old_value,
                            'new_value': suggested_value,
                            'reason': reason
                        })
                        self.logger.info(f"  - {param}: {old_value} → {suggested_value}")
                else:
                    # 文本文件（提示词）
                    current_value = mod.get('current_value', '')
                    if current_value and current_value in content:
                        content = content.replace(current_value, suggested_value)
                        applied_changes.append({
                            'parameter': param,
                            'old_value': current_value,
                            'new_value': suggested_value,
                            'reason': reason
                        })
                        self.logger.info(f"  - 已替换提示词片段")
            
            # 保存修改后的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                if file_type == 'yaml':
                    yaml.dump(content, f, allow_unicode=True)
                elif file_type == 'json':
                    json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    f.write(content)
            
            applied_results.append({
                'file_name': file_name,
                'backup_path': backup_path,
                'applied_changes': applied_changes
            })
        
        # 保存应用结果
        result_path = os.path.join(self.output_dir, 'modification_application_report.json')
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(applied_results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"✓ 应用结果已保存: {result_path}")
        
        return applied_results

    async def analyze_metrics(self, simulation_results, target_metrics=None):
        """
        调用大模型分析模拟结果的关键指标。
        
        Args:
            simulation_results: 模拟结果数据
            target_metrics: 目标分析的指标列表（可选）
        
        Returns:
            指标分析报告
        """
        # 如果是文件路径，读取文件内容
        if isinstance(simulation_results, str) and os.path.isfile(simulation_results):
            with open(simulation_results, 'r', encoding='utf-8') as f:
                if simulation_results.endswith('.json'):
                    results_data = json.load(f)
                elif simulation_results.endswith('.csv'):
                    results_data = f.read()
                else:
                    results_data = f.read()
        else:
            results_data = simulation_results
        
        metrics_info = f"关注指标：{target_metrics}" if target_metrics else "请自动识别关键指标"
        
        prompt = self.prompts['analyze_metrics_prompt'].format(
            results_data=results_data,
            metrics_info=metrics_info
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 保存指标分析
        analysis_path = os.path.join(self.output_dir, 'metrics_analysis.json')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        return response

    async def propose_adjustments(self, evaluation_report, metrics_analysis, current_config):
        """
        调用大模型根据评估结果和指标分析，提出参数调整建议。
        
        Args:
            evaluation_report: 评估报告
            metrics_analysis: 指标分析结果
            current_config: 当前配置（字典或文件路径）
        
        Returns:
            调整建议（包含具体的参数修改方案）
        """
        # 读取当前配置
        if isinstance(current_config, str) and os.path.isfile(current_config):
            with open(current_config, 'r', encoding='utf-8') as f:
                if current_config.endswith('.yaml') or current_config.endswith('.yml'):
                    config_data = yaml.safe_load(f)
                elif current_config.endswith('.json'):
                    config_data = json.load(f)
                else:
                    config_data = f.read()
        else:
            config_data = current_config
        
        prompt = self.prompts['propose_adjustments_prompt'].format(
            evaluation_report=evaluation_report,
            metrics_analysis=metrics_analysis,
            config_data=config_data
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 保存调整建议
        adjustments_path = os.path.join(self.output_dir, 'adjustment_proposals.json')
        with open(adjustments_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        return response

    async def apply_adjustments(self, adjustment_proposals, config_file):
        """
        应用调整建议到配置文件。
        
        Args:
            adjustment_proposals: 调整建议（JSON字符串或字典）
            config_file: 要修改的配置文件路径
        
        Returns:
            应用结果报告
        """
        # 解析调整建议
        if isinstance(adjustment_proposals, str):
            try:
                proposals = json.loads(adjustment_proposals)
            except json.JSONDecodeError:
                # 如果无法解析，尝试从文件读取
                if os.path.isfile(adjustment_proposals):
                    with open(adjustment_proposals, 'r', encoding='utf-8') as f:
                        proposals = json.load(f)
                else:
                    return "无法解析调整建议"
        else:
            proposals = adjustment_proposals
        
        # 读取当前配置
        with open(config_file, 'r', encoding='utf-8') as f:
            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                config = yaml.safe_load(f)
            elif config_file.endswith('.json'):
                config = json.load(f)
            else:
                return "不支持的配置文件格式"
        
        # 应用调整
        applied_changes = []
        if 'adjustments' in proposals:
            for adjustment in proposals['adjustments']:
                param = adjustment.get('parameter')
                new_value = adjustment.get('suggested_value')
                if param and new_value is not None:
                    # 简单处理：假设参数在顶层
                    # 实际应用中需要处理嵌套字典
                    if param in config:
                        old_value = config[param]
                        config[param] = new_value
                        applied_changes.append({
                            'parameter': param,
                            'old_value': old_value,
                            'new_value': new_value
                        })
        
        # 保存新配置
        backup_file = config_file + '.backup'
        
        # 如果备份文件已存在，先删除
        if os.path.exists(backup_file):
            os.remove(backup_file)
        
        os.rename(config_file, backup_file)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                yaml.dump(config, f, allow_unicode=True)
            elif config_file.endswith('.json'):
                json.dump(config, f, indent=2, ensure_ascii=False)
        
        # 生成应用报告
        report = {
            'status': 'success',
            'backup_file': backup_file,
            'applied_changes': applied_changes,
            'timestamp': str(asyncio.get_event_loop().time())
        }
        
        report_path = os.path.join(self.output_dir, 'adjustment_application_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report

    async def generate_optimization_summary(self, iteration_results):
        """
        调用大模型生成多轮迭代优化的总结报告。
        
        Args:
            iteration_results: 多轮迭代的结果列表
        
        Returns:
            优化总结报告
        """
        prompt = self.prompts['generate_optimization_summary_prompt'].format(
            iteration_results=iteration_results
        )
        
        response = await self.generate_llm_response(prompt)
        
        # 保存优化总结
        summary_path = os.path.join(self.output_dir, 'optimization_summary.md')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        return response
