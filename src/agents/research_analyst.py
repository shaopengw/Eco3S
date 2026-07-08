
from src.utils.custom_logger import CustomLogger
from src.utils.ai_system_config import get_agent_model
from .shared_imports import *

class ResearchAnalystAgent(BaseAgent):
    """
    实验评估师/研究助手Agent，继承BaseAgent，负责评估模拟结果、分析指标、提出调整建议并应用优化。
    """
    def __init__(self, agent_id, output_dir, config_dir):
        _api, _model = get_agent_model('research_analyst')
        super().__init__(agent_id, group_type='sim_architect', window_size=3,
		                 model_api_name=_api, model_type_name=_model)
        # super().__init__(agent_id, group_type='research_analyst', window_size=3)
        
        # 加载prompts配置
        prompts_path = os.path.join(os.path.dirname(__file__), 'research_analyst_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        
        self.system_message = self.prompts['system_message']
        self.output_dir = output_dir
        self.config_dir = config_dir
        self.logger = CustomLogger('research_analyst').logger

    def _load_influence_pairs(self):
        """读取项目的 influence_pairs.json，返回因果对列表（失败时返回空列表）。"""
        pairs_path = os.path.join(self.config_dir, 'influence_pairs.json')
        if not os.path.exists(pairs_path):
            self.logger.warning(f"influence_pairs.json不存在: {pairs_path}")
            return []
        try:
            with open(pairs_path, 'r', encoding='utf-8') as f:
                pairs = json.load(f)
            if not isinstance(pairs, list):
                self.logger.warning("influence_pairs.json 格式不正确（应为列表）")
                return []
            self.logger.info(f"✓ 已读取 influence_pairs.json，共 {len(pairs)} 条因果对")
            return pairs
        except Exception as e:
            self.logger.error(f"读取 influence_pairs.json 失败: {e}")
            return []

    def _format_influence_pairs(self, pairs):
        """将因果对列表格式化为供评估时核对方向的文本表格。"""
        if not pairs:
            return "（本项目未提供 influence_pairs.json，跳过因果方向核对。）"

        lines = [
            "以下是本项目设计的因果对（cause → effect）及其预期方向，",
            "请在评估时逐条核对：当原因参数增大时，结果参数是否按预期方向（increase=上升 / decrease=下降）变化。",
            "",
            "| pair_id | 原因(cause) | 结果(effect) | 预期方向 | 效应大小 |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for p in pairs:
            try:
                pid = p.get('pair_id', '?')
                cause = p.get('cause', {})
                effect = p.get('effect', {})
                cause_str = f"{cause.get('module', '?')}.{cause.get('param', '?')}"
                effect_str = f"{effect.get('module', '?')}.{effect.get('param', '?')}"
                direction = p.get('direction', '?')
                effect_size = p.get('effect_size', '?')
                lines.append(f"| {pid} | {cause_str} | {effect_str} | {direction} | {effect_size} |")
            except Exception:
                continue
        return "\n".join(lines)

    def _find_complete_logs(self):
        """在运行目录（self.output_dir）下查找 complete 开头的日志文件。

        优先在结果文件所在目录直接查找；找不到时在该目录下递归找一层兜底。
        返回匹配到的日志文件路径列表（可能为空）。
        """
        run_dir = self.output_dir
        if not run_dir or not os.path.isdir(run_dir):
            return []

        # 1) 直接在运行目录下找 complete*.log
        direct = []
        try:
            for f in os.listdir(run_dir):
                if f.startswith('complete') and f.endswith('.log'):
                    full = os.path.join(run_dir, f)
                    if os.path.isfile(full):
                        direct.append(full)
        except Exception as e:
            self.logger.warning(f"列出运行目录失败: {e}")
        if direct:
            return direct

        # 2) 兜底：递归查找
        found = []
        for root, _dirs, files in os.walk(run_dir):
            for f in files:
                if f.startswith('complete') and f.endswith('.log'):
                    found.append(os.path.join(root, f))
        return found

    def _check_resident_activity(self):
        """检查本次运行中居民/政府是否有行动输出（确定性硬检查，不依赖大模型）。

        通过读取运行目录中的 complete 开头日志文件，统计是否出现
        resident / 居民 / government / 政府 等关键字，以此判断居民是否参与了模拟。

        返回 dict：
            {
              'checked': bool,         # 是否完成了一次有意义的检查
              'log_file': str,         # 实际检查的日志文件
              'byte_size': int,        # 日志字节数
              'hit_count': int,        # 关键字命中次数
              'has_activity': bool,    # 是否检测到居民/政府行动
              'is_problem': bool,      # 是否判定为问题
              'reason': str            # 结论说明
            }
        """
        keywords = ['resident', '居民', 'government', '政府']
        log_files = self._find_complete_logs()

        if not log_files:
            return {
                'checked': False,
                'log_file': '',
                'byte_size': 0,
                'hit_count': 0,
                'has_activity': False,
                'is_problem': True,
                'reason': f"未在运行目录找到 complete 开头的日志文件（目录: {self.output_dir}），无法验证居民行动。"
            }

        # 选最新的一个 complete 日志检查
        try:
            log_file = max(log_files, key=os.path.getmtime)
        except Exception:
            log_file = log_files[0]

        try:
            byte_size = os.path.getsize(log_file)
        except Exception:
            byte_size = 0

        # 空日志：有日志文件但无内容，无法验证
        if byte_size == 0:
            return {
                'checked': True,
                'log_file': log_file,
                'byte_size': 0,
                'hit_count': 0,
                'has_activity': False,
                'is_problem': True,
                'reason': f"日志文件为空（0 字节）: {os.path.basename(log_file)}，无法验证居民是否行动。"
            }

        # 多编码读取
        content = ""
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
        for encoding in encodings:
            try:
                with open(log_file, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.warning(f"读取日志失败: {e}")
                break

        lowered = content.lower()
        hit_count = sum(lowered.count(kw.lower()) for kw in keywords)
        has_activity = hit_count > 0

        if has_activity:
            return {
                'checked': True,
                'log_file': log_file,
                'byte_size': byte_size,
                'hit_count': hit_count,
                'has_activity': True,
                'is_problem': False,
                'reason': f"日志中检测到居民/政府相关输出，命中 {hit_count} 次，居民有行动。"
            }

        return {
            'checked': True,
            'log_file': log_file,
            'byte_size': byte_size,
            'hit_count': 0,
            'has_activity': False,
            'is_problem': True,
            'reason': f"日志有内容（{byte_size} 字节）但未检测到任何居民/政府相关关键字（resident/居民/government/政府），判定为居民无行动。"
        }

    def check_resident_activity(self):
        """公开包装：供评估前置的确定性硬检查阶段调用居民行动检查。"""
        return self._check_resident_activity()

    @staticmethod
    def _to_float(v):
        """尽力把单元格值转为 float；非数值返回 None。"""
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip()
            if s == '':
                return None
            try:
                return float(s)
            except ValueError:
                return None
        return None

    def _json_to_rows(self, data):
        """把 JSON 结果数据规整为行记录列表（每行一个 dict）。"""
        if data is None:
            return []
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            # 典型：{'history': [...]} / {'steps': [...]}，取第一个 list[dict]
            for v in data.values():
                if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                    return v
            # 典型：{'gdp': [...], 'pop': [...]}，按索引转置成行
            list_cols = {
                k: v for k, v in data.items()
                if isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v)
            }
            if list_cols:
                n = min(len(v) for v in list_cols.values())
                return [{k: list_cols[k][i] for k in list_cols} for i in range(n)]
        return []

    def check_metrics_variation(self, results_file_path):
        """数据无变化硬检查（确定性，不依赖大模型）。

        读取结果文件（CSV/JSON），统计数值列跨步是否有变化。
        判定为问题（保守，避免误报）：存在 >=2 行数据，且所有数值列取值恒定，
        或所有数值全部为 0。命中后交由 CodeFixer + skill_metrics_constant_zero.md 解决。

        返回 dict：{'checked','is_problem','reason','detail'}
        """
        import csv

        result = {'checked': False, 'is_problem': False, 'reason': '', 'detail': {}}

        if not results_file_path or not os.path.isfile(results_file_path):
            result['reason'] = f'未找到结果文件，跳过数据变化检查: {results_file_path}'
            return result

        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
        rows = []
        try:
            if results_file_path.endswith('.csv'):
                for enc in encodings:
                    try:
                        with open(results_file_path, 'r', encoding=enc, newline='') as f:
                            rows = list(csv.DictReader(f))
                        break
                    except UnicodeDecodeError:
                        continue
            elif results_file_path.endswith('.json'):
                data = None
                for enc in encodings:
                    try:
                        with open(results_file_path, 'r', encoding=enc) as f:
                            data = json.load(f)
                        break
                    except UnicodeDecodeError:
                        continue
                rows = self._json_to_rows(data)
            else:
                result['reason'] = f'不支持的结果文件类型，跳过数据变化检查: {os.path.basename(results_file_path)}'
                return result
        except Exception as e:
            result['reason'] = f'读取结果文件失败，跳过数据变化检查: {e}'
            return result

        if len(rows) < 2:
            result['checked'] = True
            result['reason'] = f'结果数据不足 2 行（{len(rows)} 行），无法判定数据变化，跳过。'
            return result

        # 收集数值列
        numeric_cols = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            for k, v in row.items():
                fv = self._to_float(v)
                if fv is None:
                    continue
                numeric_cols.setdefault(k, []).append(fv)

        full_cols = {k: vals for k, vals in numeric_cols.items() if len(vals) >= 2}
        if not full_cols:
            result['checked'] = True
            result['reason'] = '结果数据中未发现可用的数值列，跳过数据变化检查。'
            return result

        # 排除步数/时间等单调索引列（它们天然递增，会掩盖真实指标恒定）
        index_names = {'step', 'steps', 'tick', 'ticks', 'time', 'year', 'years',
                       'day', 'days', 'month', 'round', 'rounds', 't', 'index',
                       'id', 'iteration', 'epoch', 'turn'}
        metric_cols = {k: vals for k, vals in full_cols.items()
                       if str(k).strip().lower() not in index_names}
        if not metric_cols:
            result['checked'] = True
            result['reason'] = '结果数据除索引列外未发现指标数值列，跳过数据变化检查。'
            return result

        constant_cols = [k for k, vals in metric_cols.items() if min(vals) == max(vals)]
        all_zero = all(all(v == 0 for v in vals) for vals in metric_cols.values())
        all_constant = len(constant_cols) == len(metric_cols)

        result['checked'] = True
        result['detail'] = {
            'total_metric_columns': len(metric_cols),
            'constant_columns': constant_cols,
            'all_zero': all_zero,
            'excluded_index_columns': [k for k in full_cols if k not in metric_cols],
        }

        if all_zero:
            result['is_problem'] = True
            result['reason'] = (f'结果数据的全部 {len(metric_cols)} 个指标数值列在所有步骤中恒为 0，'
                                f'指标未被有效更新（疑似指标恒定/未写回）。')
        elif all_constant:
            result['is_problem'] = True
            result['reason'] = (f'结果数据的全部 {len(metric_cols)} 个指标数值列在所有步骤中取值恒定无变化，'
                                f'指标未随模拟推进而变化（疑似指标恒定/未写回）。')
        else:
            result['reason'] = (f'指标数值列存在变化（{len(metric_cols)} 列中 {len(constant_cols)} 列恒定），'
                                f'数据变化检查通过。')
        return result

    def _build_resident_activity_section(self, activity):
        """根据居民行动检查结果，生成注入评估报告的 Markdown 段落。"""
        log_name = os.path.basename(activity.get('log_file', '')) or '（无）'
        lines = [
            "",
            "## 居民行动检查（严重问题）",
            "",
            "**状态：NEED_ADJUSTMENT**",
            "",
            "本节由评估环节的确定性硬检查生成（读取运行日志判定，非大模型推断）。",
            "",
            f"- 检查日志：`{log_name}`",
            f"- 日志字节数：{activity.get('byte_size', 0)}",
            f"- 关键字命中次数：{activity.get('hit_count', 0)}（关键字：resident / 居民 / government / 政府）",
            f"- 判定结论：{activity.get('reason', '')}",
            "",
            "**问题定性**：模拟运行中未观察到居民（resident）/政府（government）的行动输出，"
            "属于严重问题——居民未参与模拟会导致结果数据无效。",
            "",
            "**建议排查方向（交由 CodeFixer 解决）**：",
            "- 检查 `simulator.py` 中居民的初始化与每步行动调度逻辑是否被正确调用；",
            "- 检查居民 Agent 是否成功创建、是否被加入到模拟主循环；",
            "- 检查日志记录逻辑：若行动确实发生但未写入日志，需修复日志输出。",
            "",
        ]
        return "\n".join(lines)

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
        
        # 读取并格式化因果对，供评估时核对方向
        influence_pairs = self._load_influence_pairs()
        influence_pairs_text = self._format_influence_pairs(influence_pairs)

        prompt = self.prompts['evaluate_simulation_prompt'].format(
            results_data=results_data,
            design_doc=design_doc,
            influence_pairs=influence_pairs_text
        )
        
        response = await self.generate_llm_response(prompt)

        # 保存评估报告
        report_path = os.path.join(os.path.dirname(self.output_dir), 'evaluation_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(response)

        # 提取并保存结构化发现（供 CodeFixerAgent 使用）
        # 注：evaluation_findings.json 目前仅写入、无任何下游读取，暂时停用以避免误导。
        # findings = self._extract_structured_findings(response)
        # findings_path = os.path.join(os.path.dirname(self.output_dir), 'evaluation_findings.json')
        # try:
        #     with open(findings_path, 'w', encoding='utf-8') as f:
        #         json.dump(findings, f, ensure_ascii=False, indent=2)
        #     self.logger.info(f"✓ 评估发现已保存: {findings_path}")
        # except Exception as e:
        #     self.logger.warning(f"保存评估发现失败: {e}")

        self.logger.info(f"✓ 评估报告已保存: {report_path}")

        return response

    def _extract_structured_findings(self, response):
        """从评估报告末尾提取结构化发现 JSON。"""
        if not response:
            return {}
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
        if not json_match:
            self.logger.info("评估报告中未找到结构化 JSON 块，跳过提取")
            return {}
        raw_json = json_match.group(1)
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                self.logger.info("✓ 已成功提取结构化发现")
                return parsed
        except Exception as e:
            self.logger.warning(f"结构化发现 JSON 解析失败: {e}")
            self.logger.debug(f"待解析 JSON 内容: {raw_json[:500]}")
        return {}
