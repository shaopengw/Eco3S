
from .shared_imports import *

class ResearchAnalystAgent(BaseAgent):
    """
    实验评估师/研究助手Agent，继承BaseAgent，负责评估模拟结果、分析指标、提出调整建议并应用优化。
    """
    def __init__(self, agent_id, output_dir, docs_dir):
        super().__init__(agent_id, group_type='research_analyst', window_size=3)
        self.output_dir = output_dir
        self.docs_dir = docs_dir

    async def evaluate_simulation(self, simulation_results):
        """
        调用大模型评估模拟结果，返回评估报告。
        
        Args:
            simulation_results: 模拟结果数据（可以是字典、列表或文件路径）
        
        Returns:
            评估报告字符串
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
        
        prompt = f"""你是一位多智能体模拟系统的研究分析师，请评估以下模拟结果，分析其质量、可信度和有效性：

模拟结果：
{results_data}

请从以下几个方面进行评估：
1. 数据完整性和一致性
2. 结果的合理性
3. 关键指标的表现
4. 潜在问题和异常
5. 总体评价

请以结构化的方式给出评估报告。"""
        
        response = await self.generate_llm_response(prompt)
        
        # 保存评估报告
        report_path = os.path.join(self.output_dir, 'evaluation_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        return response

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
        
        prompt = f"""你是一位多智能体模拟系统的数据分析师，请分析以下模拟结果的关键指标：

模拟结果：
{results_data}

{metrics_info}

请进行以下分析：
1. 识别关键性能指标（KPI）
2. 计算统计特征（均值、方差、趋势等）
3. 发现异常值和模式
4. 指标之间的相关性分析
5. 与预期目标的对比

请以JSON格式输出分析结果，包含各指标的数值和解释。"""
        
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
        
        prompt = f"""你是一位多智能体模拟系统的优化专家，请根据评估报告和指标分析，提出具体的参数调整建议：

评估报告：
{evaluation_report}

指标分析：
{metrics_analysis}

当前配置：
{config_data}

请提出：
1. 需要调整的参数及原因
2. 具体的调整方案（参数名、当前值、建议值）
3. 预期的改进效果
4. 调整的优先级和风险评估

请以JSON格式输出调整建议，格式如下：
{{
  "adjustments": [
    {{
      "parameter": "参数名",
      "current_value": "当前值",
      "suggested_value": "建议值",
      "reason": "调整原因",
      "priority": "high/medium/low",
      "expected_impact": "预期效果"
    }}
  ],
  "overall_strategy": "整体优化策略"
}}"""
        
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
        prompt = f"""你是一位多智能体模拟系统的研究助手，请总结以下多轮迭代优化的过程和结果：

迭代结果：
{iteration_results}

请生成包含以下内容的总结报告：
1. 优化历程回顾（每轮的主要变化）
2. 关键指标的演化趋势
3. 成功的优化策略
4. 遇到的挑战和解决方案
5. 最终成果评价
6. 进一步改进建议

请以结构化的markdown格式输出报告。"""
        
        response = await self.generate_llm_response(prompt)
        
        # 保存优化总结
        summary_path = os.path.join(self.output_dir, 'optimization_summary.md')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        return response
