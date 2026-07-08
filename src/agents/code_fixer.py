import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import yaml
from src.utils.custom_logger import CustomLogger
from src.utils.ai_system_config import get_code_audit, get_agent_model, get_retries
from .shared_imports import *
from .code_change_mixin import CodeChangeMixin
from .auditor import AuditorAgent
from .audit_ledger import AuditLedger


class CodeFixerAgent(CodeChangeMixin, BaseAgent):
	"""代码修复与优化专家 Agent。

	负责运行时错误修复、诊断驱动的配置/代码修改、评估优化闭环、用户机制调整。
	不生成初始代码，只修改已生成的代码与配置。
	"""
	MAX_FIX_ATTEMPTS = 5  # 修复专用，比生成阶段更宽松

	def __init__(
			self,
			agent_id,
			simulator_output_dir,
			main_output_dir,
			docs_dir,
			config_dir,
			config_template_dir,
			simulation_name,
			simulation_type='decision',
			session=None,
			auto_mode: bool = False,
	):
		_api, _model = get_agent_model('code_fixer')
		super().__init__(agent_id, group_type='code_fixer', window_size=3,
		                 model_api_name=_api, model_type_name=_model)

		prompts_path = os.path.join(os.path.dirname(__file__), 'code_fixer_prompts.yaml')
		with open(prompts_path, 'r', encoding='utf-8') as f:
			self.prompts = yaml.safe_load(f)

		self.system_message = self.prompts['system_message']
		self.simulator_output_dir = simulator_output_dir
		self.main_output_dir = main_output_dir
		self.docs_dir = docs_dir
		self.config_dir = config_dir
		self.project_dir = os.path.dirname(config_dir)
		self.config_template_dir = config_template_dir
		self.simulation_name = simulation_name
		self.simulation_type = simulation_type
		self.session = session
		self.auto_mode = bool(auto_mode)
		self.logger = CustomLogger('code_fixer').logger

		# RAG shared config
		self._rag_api_key = os.environ.get('OPENAI_API_KEY')
		self._rag_base_url = os.environ.get('OPENAI_API_BASE_URL')
		self._rag_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		self._rag_db_path = os.environ.get('CAUSAL_CLAIMS_DB_PATH', os.path.join(self._rag_project_root, 'experiment_dataset', 'chroma_db'))
		self._rag_embed_model = os.environ.get('CAUSAL_CLAIMS_EMBED_MODEL', 'text-embedding-3-large')
		# 审计子 Agent（懒加载）
		self.auditor = None
		self._audit_ledger = None

	def _resolve_under_config(self, config_dir, file_name):
		"""把诊断给出的 file_name 稳健解析到 config_dir 下的物理路径。

		容忍 LLM/诊断返回带 'config/' 前缀、反斜杠、甚至 'projects/<name>/config/'
		这类相对路径的情况——直接 os.path.join(config_dir, 'config/influences.yaml')
		会拼出不存在的 config/config/influences.yaml，导致改动被静默跳过。
		"""
		if not file_name:
			return None
		name = str(file_name).strip().replace('\\', '/')
		# 绝对路径：规范化后直接返回，不再拼 config_dir
		if os.path.isabs(name):
			return os.path.normpath(name)
		# 去掉任意层级的 config/ 前缀，取最后一个 'config/' 之后的相对部分，
		# 使 'config/influences.yaml'、'projects/x/config/influences.yaml'、
		# 'influences.yaml' 三种写法都解析到同一物理文件。
		marker = 'config/'
		idx = name.rfind(marker)
		if idx != -1:
			name = name[idx + len(marker):]
		return os.path.normpath(os.path.join(config_dir, name))

	def _apply_runtime_fix(self, response, main_file_path, simulator_file_path):
		"""
		应用运行时错误修复（仅支持增量修改）
		
		只支持JSON增量修改格式，不支持完整代码块替换。
		如果LLM返回的不是JSON增量修改格式，则报错。
		
		Args:
			response: LLM返回的修复内容
			main_file_path: main文件路径
			simulator_file_path: simulator文件路径
		
		Returns:
			bool: 是否成功应用修复
		"""
		# 只支持策略：JSON增量修改
		# 查找带有文件标记的JSON块
		main_json_pattern = r'```json\s*#\s*===\s*MAIN\s*FILE\s*===\s*(\{[\s\S]*?\})\s*```'
		main_json_match = re.search(main_json_pattern, response, re.DOTALL | re.IGNORECASE)
		
		# 提取 SIMULATOR FILE 的JSON修改
		simulator_json_pattern = r'```json\s*#\s*===\s*SIMULATOR\s*FILE\s*===\s*(\{[\s\S]*?\})\s*```'
		simulator_json_match = re.search(simulator_json_pattern, response, re.DOTALL | re.IGNORECASE)
		
		# 提取 CONFIG FILES 的JSON修改
		config_json_pattern = r'```json\s*#\s*===\s*CONFIG\s*FILES\s*===\s*(\{[\s\S]*?\})\s*```'
		config_json_match = re.search(config_json_pattern, response, re.DOTALL | re.IGNORECASE)


		# 如果没有找到带注释的JSON块，尝试通用匹配并根据内容判断类型
		if not (main_json_match or simulator_json_match or config_json_match):
			generic_json_pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
			generic_json_matches = re.finditer(generic_json_pattern, response, re.DOTALL)
			
			for match in generic_json_matches:
				try:
					json_str = match.group(1)
					parsed_json = json.loads(json_str)
					if "functions" in parsed_json and not main_json_match:
						main_json_match = match
						self.logger.info("通过内容识别到 MAIN FILE JSON")
					elif "methods" in parsed_json and not simulator_json_match:
						simulator_json_match = match
						self.logger.info("通过内容识别到 SIMULATOR FILE JSON")
					elif "config_files" in parsed_json and not config_json_match:
						config_json_match = match
						self.logger.info("通过内容识别到 CONFIG FILES JSON")
				except json.JSONDecodeError:
					continue

		main_fixed = False
		simulator_fixed = False
		config_fixed = False

		# 应用main文件的增量修改（main 文件可选）
		if main_file_path and main_json_match:
			try:
				json_content = main_json_match.group(1)
				json_block = f"```json\n{json_content}\n```"
				if self._apply_code_changes(main_file_path, json_block, "main"):
					self.logger.info("✓ 已修复 main 文件（增量修改）")
					main_fixed = True
				else:
					self.logger.error("❌ 应用main文件增量修改失败")
			except Exception as e:
				self.logger.error(f"❌ 应用main文件修复失败: {e}")

		# 应用simulator文件的增量修改
		if simulator_json_match:
			try:
				json_content = simulator_json_match.group(1)
				# 构造完整的JSON代码块供_apply_code_changes处理
				json_block = f"```json\n{json_content}\n```"
				if self._apply_code_changes(simulator_file_path, json_block, "simulator"):
					self.logger.info("✓ 已修复 simulator 文件（增量修改）")
					simulator_fixed = True
				else:
					self.logger.error("❌ 应用simulator文件增量修改失败")
			except Exception as e:
				self.logger.error(f"❌ 应用simulator文件修复失败: {e}")
		
		if config_json_match:
			self.logger.info(f"尝试解析配置文件JSON内容：{config_json_match.group(1)}")
			try:
				config_json = json.loads(config_json_match.group(1))
				files_to_modify = config_json.get('config_files', [])
				config_fixed = True
				for file_info in files_to_modify:
					file_name = file_info.get('file_name')
					modifications = file_info.get('modifications', [])
					file_path = self._resolve_under_config(self.config_dir, file_name)
					if not os.path.exists(file_path):
						self.logger.warning(f"配置/提示词文件不存在，将基于 modifications 创建: {file_path}")
					result = self._apply_modifications(file_path, modifications, create_if_missing=True)
					if not result or not result.get('changes'):
						config_fixed = False
			except Exception as e:
				self.logger.error(f"❌ 应用配置文件修复失败: {e}")
				config_fixed = False

		# 新增：配置文件完整重写模式（用于修复YAML/JSON语法错误）
		rewrite_fixed = False
		rewrite_yaml_pattern = r'```yaml\s*#\s*===\s*REWRITE\s*FILE:\s*(.+?)\s*===\s*([\s\S]*?)```'
		rewrite_json_pattern = r'```json\s*#\s*===\s*REWRITE\s*FILE:\s*(.+?)\s*===\s*([\s\S]*?)```'

		for pattern in [rewrite_yaml_pattern, rewrite_json_pattern]:
			for match in re.finditer(pattern, response, re.DOTALL | re.IGNORECASE):
				file_name = match.group(1).strip()
				new_content = match.group(2).strip()
				file_path = self._resolve_under_config(self.config_dir, file_name)

				# 先验证新内容语法
				try:
					if file_path.endswith(('.yaml', '.yml')):
						yaml.safe_load(new_content)
					elif file_path.endswith('.json'):
						json.loads(new_content)

					with open(file_path, 'w', encoding='utf-8') as f:
						f.write(new_content + '\n')
					rewrite_fixed = True
					self.logger.info(f"✓ 已重写配置文件: {file_name}")
				except Exception as e:
					self.logger.error(f"❌ 重写的配置文件语法仍错误或未通过验证: {file_name}, {e}")

		# 如果成功应用了增量修改或重写，返回成功
		if main_fixed or simulator_fixed or config_fixed or rewrite_fixed:
			return True

		# 所有策略都失败，直接报错
		self.logger.error("❌ 未能从响应中提取有效的JSON增量修改内容")
		self.logger.debug(f"LLM响应预览: {response[:500]}")
		return False

	async def fix_runtime_errors(self, error_message, error_traceback, main_file_path, simulator_file_path, config_path, max_attempts=None):
		"""
		运行时错误修复函数 - 使用增量修改方式
		支持同时修复 main 和 simulator 文件

		Args:
			error_message: 错误信息
			error_traceback: 完整的错误堆栈
			main_file_path: main文件路径，若为 None 则只修复 simulator
			simulator_file_path: simulator文件路径
			config_path: simulation_config.yaml 路径
			max_attempts: 最大修复尝试次数（None=读全局 retries.runtime_fix）

		Returns:
			bool: 是否修复成功
		"""
		if max_attempts is None:
			max_attempts = get_retries()['runtime_fix']
		self.logger.info("🔧 开始修复运行时错误...")

		# 首先检查是否是 FileNotFoundError
		if "FileNotFoundError" in error_message:
			if await self._handle_file_not_found_error(error_traceback, config_path):
				self.logger.info("✓ 已成功处理 FileNotFoundError 并生成了缺失文件。")
				return True # 假设文件生成后问题就解决了，直接返回成功


		# 读取当前代码
		main_content = ""
		if main_file_path and os.path.exists(main_file_path):
			with open(main_file_path, 'r', encoding='utf-8') as f:
				main_content = f.read()
		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			simulator_content = f.read()

		# 从错误堆栈中提取相关模块的接口文件和配置文件（使用LLM智能分析）
		module_interface_docs, config_files_dict = await self._extract_module_api_docs_from_error(error_traceback)

		# config_files_str为所有相关配置文件的具体内容
		config_files_str = ""
		if config_files_dict:
			config_files_str = "\n相关配置文件：\n"
			for filename, content in config_files_dict.items():
				config_files_str += f"\n{'='*60}\n"
				config_files_str += f"配置文件: {filename}\n"
				config_files_str += f"{'='*60}\n{content}\n"

		for attempt in range(1, max_attempts + 1):
			self.logger.info(f"第 {attempt}/{max_attempts} 次修复尝试...")

			# 提示词
			prompt = self.prompts['fix_runtime_errors_prompt'].format(
				error_traceback=error_traceback,
				main_file_path=main_file_path or "（未提供 main 文件）",
				main_content=main_content or "（未提供 main 文件内容）",
				simulator_file_path=simulator_file_path,
				simulator_content=simulator_content,
				module_interface_docs=module_interface_docs,
				config_files_str=config_files_str
			)

			response = await self.generate_llm_response(prompt)
			if not response:
				self.logger.error("LLM未返回响应")
				continue

			# 尝试应用修复
			if self._apply_runtime_fix(response, main_file_path, simulator_file_path):
				self.logger.info(f"✓ 修复完成")
				return True
			else:
				self.logger.warning(f"⚠️ 第 {attempt} 次修复失败")

		self.logger.error("❌ 修复失败")
		return False

	async def modify_file_sequentially(self, diagnosis_path, config_dir, design_doc=""):
		"""
		根据 diagnosis_path 路径依次修改配置文件或代码文件。
		diagnosis_path: 包含诊断结果的 JSON 文件路径

		流程（开启审计时）：生成改动方案 → 交审计子 Agent 复核 → 只应用通过的改动；
		被驳回的当轮读审计日志重新生成，最多 max_rounds 轮。审计关闭/不触发时退回原逐文件直接应用。
		"""
		diagnosis = None
		if not diagnosis_path or not os.path.exists(diagnosis_path):
			self.logger.error(f"诊断文件不存在: {diagnosis_path}")
			return []
		try:
			with open(diagnosis_path, 'r', encoding='utf-8') as f:
				diagnosis_content = f.read()
			diagnosis = json.loads(diagnosis_content)
		except Exception as e:
			self.logger.error(f"诊断文件解析失败: {e}")
			return []

		files_to_modify = diagnosis.get('files_to_modify', [])
		if not files_to_modify:
			self.logger.info("无需修改任何文件")
			return []

		audit_cfg = self._load_audit_config()
		diagnosis_context = self._summarize_diagnosis(files_to_modify)

		results = []
		round_no = 0
		prior_feedback = ""
		while True:
			round_no += 1
			# 1) 生成改动方案（不写文件）
			proposed, passthrough = await self._generate_modifications(
				files_to_modify, config_dir, design_doc, prior_feedback
			)

			# 2) 判断是否需要审计
			if not (audit_cfg.get('enabled') and self._should_audit(proposed, audit_cfg)):
				# 不审计：直接应用本轮全部改动（等价于原逐文件直接落盘）
				results += self._apply_proposed(proposed)
				results += self._apply_proposed(passthrough)
				return results

			# 3) 交审计子 Agent 复核
			auditor = self._ensure_auditor(audit_cfg)
			audit = await auditor.audit_batch(
				proposed, round_no, diagnosis_context=diagnosis_context, design_doc=design_doc
			)

			# 4) 应用通过的改动 + 解析失败回退项
			results += self._apply_audited(audit.get('approved', []))
			results += self._apply_proposed(passthrough)

			# 5) 收敛判断
			rejected = audit.get('rejected', [])
			if audit.get('verdict') == 'APPROVE' or not rejected:
				return results
			if round_no >= int(audit_cfg.get('max_rounds', 2)):
				self.logger.warning(f"⚠️ 审计驳回 {len(rejected)} 处，已达最大重生轮数 {round_no}，放弃这些改动")
				for r in rejected:
					self.logger.info(f"  放弃: {r.get('location')} —— {r.get('reason')}")
				return results

			# 6) 当轮重生：收窄到被驳回的文件，带上审计反馈
			prior_feedback = audit.get('feedback', '')
			files_to_modify = self._narrow_to_rejected(files_to_modify, rejected)
			if not files_to_modify:
				return results
			self.logger.info(f"🔁 审计驳回，第 {round_no + 1} 轮针对 {len(files_to_modify)} 个文件重新生成...")

	# ==================== 审计辅助方法 ====================

	def _ensure_auditor(self, audit_cfg):
		"""懒加载审计子 Agent 与共享日志。"""
		if self._audit_ledger is None:
			ledger_path = os.path.join(self.project_dir, 'audit', 'audit_ledger.json')
			self._audit_ledger = AuditLedger(ledger_path, simulation_name=self.simulation_name)
		if self.auditor is None:
			simulator_path = os.path.join(self.project_dir, 'simulator.py')
			self.auditor = AuditorAgent(
				agent_id='auditor_001',
				project_dir=self.project_dir,
				config_dir=self.config_dir,
				simulator_path=simulator_path,
				simulation_name=self.simulation_name,
				ledger=self._audit_ledger,
				semantic_review=bool(audit_cfg.get('semantic_review', True)),
				attr_check=bool(audit_cfg.get('attr_check', True)),
				session=self.session,
			)
		return self.auditor

	def _load_audit_config(self) -> dict:
		"""纯全局：从 config/ai_system.yaml 读 code_audit，不再读项目 simulation_config.yaml。

		code_audit 是"AI 系统怎么改代码"的元配置，与"某个模拟实验跑什么"无关，
		因此集中到全局 config/ai_system.yaml，项目内即使写了 code_audit 也不再生效。
		"""
		return get_code_audit()

	def _should_audit(self, proposed, audit_cfg) -> bool:
		"""触发条件：动到 simulator 一定审；否则改动总数达到门槛才审。"""
		if not proposed:
			return False
		has_sim = any(p.get('file_type') == 'simulator' for p in proposed)
		if has_sim:
			return True
		total = 0
		for p in proposed:
			changes = p.get('changes') or {}
			total += len(changes.get('methods', [])) + len(changes.get('modifications', []))
		return total >= int(audit_cfg.get('threshold', 3))

	def _summarize_diagnosis(self, files_to_modify) -> str:
		"""把诊断条目汇总成"本轮要解决的问题"文本，供审计语义审查参考。"""
		parts = []
		for fi in files_to_modify:
			desc = fi.get('modification') or fi.get('reason') or ''
			parts.append(f"- {fi.get('file_name')}: {desc}")
		return "\n".join(parts)

	def _group_files_to_modify(self, files_to_modify):
		"""把指向同一物理文件的诊断条目合并，使每个文件本轮只生成一次改动。

		所有 file_type=='simulator' 的条目都指向同一个 simulator.py，必须合并；
		同名配置文件的多条诊断也合并。合并时把各自的问题描述拼到一起，让一次 LLM
		调用同时看到该文件的全部问题，从而产出一套自洽的改法，而不是多套互相冲突的。
		"""
		groups = {}
		order = []
		for fi in files_to_modify:
			key = 'simulator.py' if fi.get('file_type') == 'simulator' else fi.get('file_name')
			if key not in groups:
				merged = dict(fi)
				merged['_merged_count'] = 1
				groups[key] = merged
				order.append(key)
			else:
				g = groups[key]
				g['_merged_count'] += 1
				prev = g.get('modification') or g.get('reason') or ''
				cur = fi.get('modification') or fi.get('reason') or ''
				if cur and cur not in prev:
					g['modification'] = (prev + '\n' + cur).strip() if prev else cur
		for key in order:
			if groups[key].get('_merged_count', 1) > 1:
				self.logger.info(
					f"🧹 已合并指向 {key} 的 {groups[key]['_merged_count']} 条诊断为一次生成，避免同批冲突改法"
				)
		return [groups[key] for key in order]

	async def _generate_modifications(self, files_to_modify, config_dir, design_doc, prior_feedback=""):
		"""生成每个文件的改动方案，但不写盘。

		Returns:
			(proposed, passthrough)
			- proposed: 成功解析成结构化改动的项 [{file_name,file_type,file_path,changes}]
			- passthrough: 未能解析、回退到原逻辑整体应用的项 [{file_name,file_type,file_path,raw_response}]
		"""
		proposed = []
		passthrough = []
		feedback_block = ""
		if prior_feedback:
			feedback_block = f"\n\n【上一轮审计反馈，请据此修正，不要重复被驳回的改法】\n{prior_feedback}\n"

		# 把指向同一物理文件的诊断条目合并为一次生成，避免同批对一个文件多次独立生成、
		# 产出互相覆盖的冲突改法（这正是 simulator.py 被连灌两套方法、拼出 current_step/gdp
		# 等不一致 bug 的根源）。
		files_to_modify = self._group_files_to_modify(files_to_modify)

		for file_info in files_to_modify:
			file_name = file_info.get('file_name')
			file_type = file_info.get('file_type')
			self.logger.info(f"生成改动方案 : {file_name} (类型: {file_type})")

			if file_type == 'simulator':
				file_path = os.path.join(self.project_dir, 'simulator.py')
			else:
				file_path = self._resolve_under_config(config_dir, file_name)

			if not os.path.exists(file_path):
				self.logger.warning(f"文件不存在: {file_path}")
				continue

			with open(file_path, 'r', encoding='utf-8') as f:
				current_content = f.read()

			if file_type == 'simulator':
				prompt = self.prompts['generate_simulator_modifications_prompt'].format(
					diagnosis_result=json.dumps(file_info, ensure_ascii=False),
					current_code=current_content[:8000],
					design_doc=design_doc + feedback_block,
				)
				response = await self.generate_llm_response(prompt)
				if not response:
					passthrough.append({'file_name': 'simulator.py', 'file_type': 'simulator',
					                    'file_path': file_path, 'raw_response': ''})
					continue
				changes = self._parse_simulator_changes(response)
				if changes and changes.get('methods'):
					proposed.append({'file_name': 'simulator.py', 'file_type': 'simulator',
					                 'file_path': file_path, 'changes': changes, 'raw_response': response})
				else:
					# 解析不出结构化方法：回退原逻辑整体应用，不纳入审计
					passthrough.append({'file_name': 'simulator.py', 'file_type': 'simulator',
					                    'file_path': file_path, 'raw_response': response})
			else:
				prompt = self.prompts['generate_config_modifications_prompt'].format(
					diagnosis_result=json.dumps(file_info, ensure_ascii=False),
					current_config=current_content[:5000],
					design_doc=design_doc + feedback_block,
				)
				response = await self.generate_llm_response(prompt)
				changes = self._parse_config_changes(response) if response else None
				if changes and changes.get('modifications'):
					proposed.append({'file_name': file_name, 'file_type': 'config',
					                 'file_path': file_path, 'changes': changes, 'raw_response': response or ''})
				# 配置解析失败则跳过（原逻辑也无法应用）

		return proposed, passthrough

	def _parse_simulator_changes(self, response):
		"""从 LLM 响应里解析出 {'methods':[...]}，失败返回 None。"""
		json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
		if not json_match:
			json_match = re.search(r'(\{[\s\S]*"methods"[\s\S]*\})', response, re.DOTALL)
		if not json_match:
			return None
		try:
			data = json.loads(json_match.group(1))
		except json.JSONDecodeError:
			return None
		if not (isinstance(data, dict) and data.get('methods')):
			return None
		# 安全网：同一份响应里若出现同名方法的多个版本，去重（保留最后一个），
		# 避免增量应用时 delete-then-add 把方法拼成自相矛盾的版本。
		data['methods'] = self._dedup_methods(data['methods'])
		return data

	@staticmethod
	def _pure_method_name(name: str) -> str:
		"""从 'def foo(self, ...)' 或 'foo' 里取出纯方法名。"""
		if not name:
			return ''
		m = re.search(r'def\s+(\w+)', name)
		return m.group(1) if m else name.strip()

	def _dedup_methods(self, methods):
		"""按方法名去重，保留最后一个版本，保持首次出现的顺序。"""
		latest = {}
		order = []
		for m in methods:
			name = self._pure_method_name(m.get('method_name', ''))
			if not name:
				# 取不出名字的保守保留，避免误删
				order.append(id(m))
				latest[id(m)] = m
				continue
			if name in latest:
				self.logger.warning(f"⚠️ 同批出现同名方法 {name} 的多个版本，保留最后一个")
			else:
				order.append(name)
			latest[name] = m
		return [latest[k] for k in order]

	def _parse_config_changes(self, response):
		"""从 LLM 响应里解析出 {'modifications':[...]}，失败返回 None。"""
		json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
		if not json_match:
			return None
		try:
			data = json.loads(json_match.group(1))
			return data if isinstance(data, dict) and data.get('modifications') else None
		except json.JSONDecodeError:
			return None

	def _apply_audited(self, approved):
		"""应用审计通过的改动。"""
		results = []
		for item in approved:
			file_path = item.get('file_path')
			if item.get('file_type') == 'simulator':
				payload = json.dumps({'methods': item.get('methods', [])}, ensure_ascii=False)
				ok = self._apply_code_changes(file_path, f"```json\n{payload}\n```", "simulator")
				results.append({'file_name': item.get('file_name', 'simulator.py'),
				                'result': 'success' if ok else 'failed'})
			else:
				res = self._apply_modifications(file_path, item.get('modifications', []), create_if_missing=True)
				ok = bool(res and res.get('changes'))
				results.append({'file_name': item.get('file_name'),
				                'result': 'success' if ok else 'failed'})
		return results

	def _apply_proposed(self, items):
		"""应用未经审计的项（解析失败回退、或审计不触发时的直接应用）。"""
		results = []
		for item in items:
			file_path = item.get('file_path')
			file_type = item.get('file_type')
			if file_type == 'simulator':
				raw = item.get('raw_response') or ''
				if 'changes' in item and item.get('changes', {}).get('methods'):
					payload = json.dumps({'methods': item['changes']['methods']}, ensure_ascii=False)
					raw = f"```json\n{payload}\n```"
				ok = self._apply_code_changes(file_path, raw, "simulator") if raw else False
				results.append({'file_name': item.get('file_name', 'simulator.py'),
				                'result': 'success' if ok else 'failed'})
			else:
				mods = (item.get('changes') or {}).get('modifications', [])
				if not mods:
					continue
				res = self._apply_modifications(file_path, mods, create_if_missing=True)
				ok = bool(res and res.get('changes'))
				results.append({'file_name': item.get('file_name'),
				                'result': 'success' if ok else 'failed'})
		return results

	def _narrow_to_rejected(self, files_to_modify, rejected):
		"""把待改文件清单收窄到被驳回涉及的文件，用于当轮重生。"""
		rejected_files = set()
		for r in rejected:
			loc = r.get('location', '')
			m = re.match(r'(\S+\.\w+)', loc)
			if m:
				rejected_files.add(m.group(1))
		if not rejected_files:
			return []
		narrowed = []
		for fi in files_to_modify:
			fn = fi.get('file_name', '')
			if fn in rejected_files or (fi.get('file_type') == 'simulator' and 'simulator.py' in rejected_files):
				narrowed.append(fi)
		return narrowed


	async def apply_user_adjustment(self, requirements_text):
		"""
		应用用户的机制调整需求
		
		Args:
			requirements_text: 格式化的需求字符串 ("1. 需求1\n2. 需求2")
		
		Returns:
			bool: 是否成功应用
		"""
		self.logger.info(f"应用用户调整:\n{requirements_text}")
		
		try:
			# 读取当前代码文件
			simulator_path = os.path.join(self.project_dir, 'simulator.py')
			main_path = os.path.join(self.project_dir, 'main.py')

			if not os.path.exists(simulator_path):
				self.logger.error(f"Simulator文件不存在: {simulator_path}")
				return False

			main_exists = os.path.exists(main_path)
			if not main_exists:
				self.logger.info(f"项目未提供 main.py，仅调整 simulator/config: {main_path}")

			# 读取代码内容
			with open(simulator_path, 'r', encoding='utf-8') as f:
				simulator_content = f.read()
			main_content = ""
			if main_exists:
				with open(main_path, 'r', encoding='utf-8') as f:
					main_content = f.read()

			# 读取配置文件
			configs = {}
			if os.path.exists(self.config_dir):
				for filename in os.listdir(self.config_dir):
					if filename.endswith(('.yaml', '.yml', '.json', '.md')):
						file_path = os.path.join(self.config_dir, filename)
						try:
							with open(file_path, 'r', encoding='utf-8') as f:
								configs[filename] = f.read()
						except Exception as e:
							self.logger.warning(f"读取配置文件失败 {filename}: {e}")

			# 构建上下文
			code_files_context = f"=== Simulator文件 ({simulator_path}) ===\n{simulator_content}\n\n"
			if main_exists:
				code_files_context += f"=== Main文件 ({main_path}) ===\n{main_content}\n\n"
			
			config_files_context = ""
			for filename, content in configs.items():
				config_files_context += f"=== {filename} ===\n{content[:3000]}\n\n"  # 限制配置文件长度
			
			# 构建提示词
			prompt = self.prompts['apply_user_adjustment_prompt'].format(
				requirements_text=requirements_text,
				code_files=code_files_context,
				config_files=config_files_context
			)
			
			# 调用LLM生成增量修改
			self.logger.info("调用LLM生成增量修改方案")
			response = await self.generate_llm_response(prompt)
			
			if not response:
				self.logger.error("LLM未返回响应")
				return False
			
			# 使用 _apply_runtime_fix 应用修改
			self.logger.info("应用增量修改")
			success = self._apply_runtime_fix(response, main_path if main_exists else None, simulator_path)
			
			if success:
				self.logger.info("✓ 用户调整应用成功")
			else:
				self.logger.error("❌ 用户调整应用失败")
			
			return success
			
		except Exception as e:
			self.logger.error(f"应用用户调整失败: {e}")
			import traceback
			self.logger.error(traceback.format_exc())
			return False

	async def evaluate_and_optimize(self, evaluation_report: str, coding_results: dict, design_doc: str = "") -> dict:
		"""根据评估报告判断是否需要调整，并执行优化闭环。

		Args:
			evaluation_report: ResearchAnalystAgent 生成的评估报告
			coding_results: 编码阶段产物
			design_doc: 设计文档内容

		Returns:
			{'needs_adjustment': bool, 'modification_results': list}
		"""
		needs_adjustment = 'NEED_ADJUSTMENT' in evaluation_report.upper()
		if not needs_adjustment:
			self.logger.info("✓ 评估报告未触发调整")
			return {'needs_adjustment': False, 'modification_results': []}

		self.logger.info("⚠️ 评估报告触发调整，准备执行优化...")
		# 主流程中 ProjectMasterAgent 已经生成 diagnosis_path，这里提供主动入口：
		# 如果 coding_results 中未携带 diagnosis_path，则仅返回需要调整的信号。
		diagnosis_path = coding_results.get('diagnosis_path')
		if diagnosis_path and os.path.exists(diagnosis_path):
			modification_results = await self.modify_file_sequentially(
				diagnosis_path,
				self.config_dir,
				design_doc=design_doc
			)
			return {'needs_adjustment': True, 'modification_results': modification_results}

		self.logger.warning("评估报告需要调整，但未提供 diagnosis_path")
		return {'needs_adjustment': True, 'modification_results': []}

	async def run_optimization_session(self, evaluation_report: str, design_doc: str = "", interactive: bool = True) -> dict:
		"""根据评估报告运行优化会话，修改代码/配置以解决问题。

		Args:
			evaluation_report: ResearchAnalystAgent 生成的评估报告
			design_doc: 设计文档内容
			interactive: 是否交互式等待用户确认（当前仅作标记）

		Returns:
			{
				'success': bool,
				'optimization_passed': bool,
				'solved': dict,
				'modification_results': list
			}
		"""
		needs_adjustment = 'NEED_ADJUSTMENT' in evaluation_report.upper()
		if not needs_adjustment:
			self.logger.info("✓ 评估报告未触发调整")
			return {
				'success': True,
				'optimization_passed': True,
				'solved': {},
				'modification_results': []
			}

		self.logger.info("⚠️ 评估报告触发调整，准备执行优化会话...")

		# ① 读整份报告 → ② 路由匹配 skill → ③ 读 skill → ④ 据 skill 诊断待改文件
		skill_files = await self._route_report_to_skills(evaluation_report)
		skill_text = self._load_skill_files(skill_files)
		diagnosis = await self._diagnose_files_from_skills(
			problem_context=evaluation_report,
			skill_text=skill_text,
			design_doc=design_doc,
		)

		if not diagnosis.get('files_to_modify'):
			self.logger.info("✓ 诊断完成，但未识别到需要修改的文件")
			return {
				'reason': 'no_files_to_modify',
				'diagnosis': diagnosis,
				'success': True,
				'optimization_passed': False,
				'solved': {},
				'modification_results': [],
				'verify_result': {'success': False, 'error': '无文件需要修改'}
			}

		# ⑤ 应用 + 冒烟验证（与技能驱动路径共享）
		return await self._apply_and_verify(diagnosis, design_doc)

	async def run_skill_guided_session(self, problem_summary: str, skill_files: list,
	                                   detail=None, design_doc: str = "") -> dict:
		"""硬检查命中路径：用硬编码的 skill 文件直接驱动诊断与修复（不走 LLM 路由）。

		Args:
			problem_summary: 确定性硬检查给出的问题结论（如"居民无行动…"）
			skill_files: 命中的 skill 文件相对路径列表（如 ['docs/code_fixer_skills/skill_agent_behavior_abnormal.md']）
			detail: 硬检查的详情字典（命中列、命中次数等）
			design_doc: 设计文档内容
		"""
		self.logger.info(f"⚙️ 技能驱动修复会话启动：{problem_summary}")
		skill_text = self._load_skill_files(skill_files)
		context = f"问题：{problem_summary}\n\n硬检查详情：{detail}"
		diagnosis = await self._diagnose_files_from_skills(
			problem_context=context,
			skill_text=skill_text,
			design_doc=design_doc,
		)
		if not diagnosis.get('files_to_modify'):
			self.logger.info("✓ 技能驱动诊断完成，但未识别到需要修改的文件")
			return {
				'reason': 'no_files_to_modify',
				'diagnosis': diagnosis,
				'success': True,
				'optimization_passed': False,
				'solved': {},
				'modification_results': [],
				'verify_result': {'success': False, 'error': '无文件需要修改'}
			}
		return await self._apply_and_verify(diagnosis, design_doc)

	# ---------- 工具：读文件 / 搜索项目 ----------

	def read_file(self, file_path: str) -> str:
		"""读取项目内的文本文件内容（多编码兜底）。

		支持相对项目目录、项目根目录、docs 目录的路径；也支持绝对路径（但会限制在允许根目录内）。
		"""
		if not file_path:
			return "[错误：file_path 为空]"

		allowed_roots = {
			os.path.abspath(self._rag_project_root),
			os.path.abspath(self.project_dir),
			os.path.abspath(self.config_dir),
			os.path.abspath(self.docs_dir),
		}

		candidates = []
		if os.path.isabs(file_path):
			candidates.append(os.path.abspath(file_path))
		else:
			candidates.extend([
				os.path.abspath(os.path.join(self.project_dir, file_path)),
				os.path.abspath(os.path.join(self.config_dir, file_path)),
				os.path.abspath(os.path.join(self._rag_project_root, file_path)),
				os.path.abspath(os.path.join(self.docs_dir, file_path)),
			])

		for path in candidates:
			if not os.path.isfile(path):
				continue
				# 安全检查：必须落在允许根目录下
			if not any(path.startswith(root + os.sep) or path == root for root in allowed_roots):
				return f"[错误：无权读取该路径: {file_path}]"

			for enc in ('utf-8', 'gbk', 'gb2312', 'utf-8-sig'):
				try:
					with open(path, 'r', encoding=enc) as f:
						content = f.read()
					# 对超大文件做截断，避免一次撑爆上下文
					max_len = 15000
					if len(content) > max_len:
						content = content[:max_len] + f"\n\n[文件过长，已截断；原始长度 {len(content)} 字符]"
					return content
				except UnicodeDecodeError:
					continue
				except Exception as e:
					return f"[读取文件失败 {file_path}: {e}]"
		return f"[未找到文件: {file_path}]"

	def search_project(self, pattern: str, glob: str = "**/*.py", path: str = None) -> str:
		"""在项目代码中按正则搜索内容，返回匹配文件路径与片段。"""
		import fnmatch
		from pathlib import PurePath, PurePosixPath

		if not pattern:
			return "[错误：pattern 为空]"
		try:
			compiled = re.compile(pattern)
		except re.error as e:
			return f"[正则表达式错误: {e}]"

		roots = []
		if path:
			roots.append(os.path.abspath(path))
		else:
			roots.extend([os.path.abspath(self.project_dir), os.path.abspath(self._rag_project_root)])

		skip_dirs = {'.git', '__pycache__', '.claude', 'node_modules', 'venv', '.venv', 'experiment_dataset'}
		max_results = 30
		results = []

		for root in roots:
			if not os.path.isdir(root):
				continue
			for dirpath, dirnames, filenames in os.walk(root):
				dirnames[:] = [d for d in dirnames if d not in skip_dirs]
				for filename in filenames:
					file_path = os.path.join(dirpath, filename)
					rel_path = os.path.relpath(file_path, self._rag_project_root)
					# 支持文件名通配符，也支持带路径的 glob（如 src/**/*.py）
					matches = fnmatch.fnmatch(filename, glob)
					if not matches and '/' in glob:
						matches = PurePosixPath(rel_path.replace(os.sep, '/')).match(glob)
					if not matches:
						continue
					try:
						content = None
						for enc in ('utf-8', 'gbk', 'gb2312', 'utf-8-sig'):
							try:
								with open(file_path, 'r', encoding=enc) as f:
									content = f.read()
								break
							except UnicodeDecodeError:
								continue
						if content is None:
							continue
						for i, line in enumerate(content.splitlines(), start=1):
							if compiled.search(line):
								results.append(f"{rel_path}:{i}: {line.strip()}")
								if len(results) >= max_results:
									return "\n".join(results)
					except Exception:
						continue

		if not results:
			return f"未找到匹配 pattern='{pattern}' glob='{glob}' 的内容。"
		return "\n".join(results)

	def _extract_tool_call(self, text: str) -> Optional[dict]:
		"""从 LLM 响应中提取一次 <tool> 调用。"""
		if not text or '<tool' not in text:
			return None
		m = re.search(r'<tool\s+name="(\w+)"\s*>(.*?)\s*</tool>', text, re.DOTALL)
		if not m:
			return None
		name = m.group(1)
		inner = m.group(2)
		args = {}
		for am in re.finditer(r'<arg\s+name="(\w+)"\s*>(.*?)\s*</arg>', inner, re.DOTALL):
			args[am.group(1)] = am.group(2).strip()
		return {'name': name, 'args': args}

	async def _execute_tool(self, tool_call: dict) -> str:
		"""执行一次工具调用并返回文本结果。"""
		name = tool_call.get('name')
		args = tool_call.get('args', {})
		if name == 'read_file':
			return self.read_file(args.get('file_path', ''))
		if name == 'search_project':
			return self.search_project(
				args.get('pattern', ''),
				args.get('glob', '**/*.py'),
				args.get('path')
			)
		return f"[未知工具: {name}]"

	async def _chat(self, messages: list) -> Optional[str]:
		"""直接调用模型后端（不经过 BaseAgent 的 memory 拼接）。"""
		attempts = 0
		while attempts < self.max_retry_attempts:
			try:
				extra_kwargs = getattr(self, '_extra_kwargs', None)
				if extra_kwargs:
					from openai import OpenAI
					client = OpenAI(base_url=self._api_url, api_key=self._api_key)
					response = await asyncio.to_thread(
						client.chat.completions.create,
						model=self.model_type,
						messages=messages,
						**extra_kwargs
					)
				else:
					response = await asyncio.to_thread(self.model_backend.run, messages)
				content = response.choices[0].message.content
				if content is not None:
					return content
				self.logger.warning(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次返回空，准备重试")
			except Exception as e:
				self.logger.error(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次出错：{e}")
			attempts += 1
			if attempts < self.max_retry_attempts:
				await asyncio.sleep(self.retry_delay)
		self.logger.error(f"{self.__class__.__name__} 工具调用在 {self.max_retry_attempts} 次尝试后失败")
		return None

	async def _generate_with_tools(self, prompt: str) -> Optional[str]:
		"""带 read_file / search_project 工具调用的 LLM 对话循环。

		模型每次只输出一个 <tool> 调用时执行并把结果塞回上下文；
		不再输出工具调用时返回最终文本。
		"""
		tool_instructions = self.prompts.get('tool_system_message', '')
		system_content = (self.system_message or '')
		if tool_instructions:
			system_content += "\n\n" + tool_instructions

		messages = [
			{"role": "system", "content": system_content},
			{"role": "user", "content": prompt},
		]

		round_no = 0
		while True:
			response = await self._chat(messages)
			if not response:
				return None
			tool_call = self._extract_tool_call(response)
			if not tool_call:
				return response

			round_no += 1
			self.logger.info(f"🔧 工具调用 #{round_no}: {tool_call['name']}({tool_call['args']})")
			result = await self._execute_tool(tool_call)
			# 截断过长的工具结果，防止上下文爆炸
			if len(result) > 12000:
				result = result[:12000] + "\n\n[工具结果过长，已截断]"

			messages.append({"role": "assistant", "content": response})
			messages.append({
				"role": "user",
				"content": f"<tool_result name=\"{tool_call['name']}\">\n{result}\n</tool_result>"
			})

	# ---------- 文档读取 / 技能路由 / 技能驱动诊断 ----------

	def _load_doc(self, rel_path: str) -> str:
		"""读取文档内容（rel_path 相对仓库根，如 'docs/code_fixer_skills/xxx.md'，
		也兼容相对 docs/ 目录的路径、以及只给出 skill 裸文件名的情况）。失败返回 ''。"""
		repo_root = os.path.dirname(self.docs_dir)
		base = os.path.basename(rel_path)
		candidates = [
			os.path.join(repo_root, rel_path),
			os.path.join(self.docs_dir, rel_path),
		]
		# 兜底：路由表里 skill 常以裸文件名出现（skill_xxx.md），按约定目录补全
		if base.startswith('skill_') and base.endswith('.md'):
			candidates.append(os.path.join(self.docs_dir, 'code_fixer_skills', base))
		for path in candidates:
			if os.path.isfile(path):
				for enc in ('utf-8', 'gbk', 'gb2312', 'utf-8-sig'):
					try:
						with open(path, 'r', encoding=enc) as f:
							return f.read()
					except UnicodeDecodeError:
						continue
					except Exception as e:
						self.logger.warning(f"读取文档失败 {path}: {e}")
						return ''
		self.logger.warning(f"未找到文档: {rel_path}")
		return ''

	def _load_skill_files(self, paths: list) -> str:
		"""读取并拼接选中的 skill 文件内容。"""
		if not paths:
			return ''
		blocks = []
		for p in paths:
			content = self._load_doc(p)
			if content:
				blocks.append(f"===== Skill 文件: {p} =====\n{content}")
		return "\n\n".join(blocks)

	@staticmethod
	def _extract_json(text: str):
		"""从 LLM 响应中提取首个 JSON（对象或数组）。失败返回 None。"""
		if not text:
			return None
		m = re.search(r'```(?:json)?\s*([\[{][\s\S]*?[\]}])\s*```', text, re.DOTALL)
		raw = m.group(1) if m else None
		if raw is None:
			m2 = re.search(r'[\[{][\s\S]*[\]}]', text, re.DOTALL)
			raw = m2.group(0) if m2 else None
		if raw is None:
			return None
		try:
			return json.loads(raw)
		except Exception:
			return None

	async def _route_report_to_skills(self, evaluation_report: str) -> list:
		"""读诊断路由表，用 LLM 把报告问题匹配到 skill 文件相对路径列表。失败返回 []。"""
		router = self._load_doc('docs/code_fixer_diagnostic_router.md')
		if not router:
			self.logger.warning("诊断路由表缺失，跳过路由匹配")
			return []
		try:
			prompt = self.prompts['route_report_to_skills_prompt'].format(
				evaluation_report=evaluation_report,
				diagnostic_router=router,
			)
			response = await self._generate_with_tools(prompt)
			parsed = self._extract_json(response)
			if isinstance(parsed, dict):
				parsed = parsed.get('skills', [])
			if not isinstance(parsed, list):
				return []
			skills = [s for s in parsed if isinstance(s, str) and s.strip()]
			self.logger.info(f"✓ 路由匹配到 {len(skills)} 个 skill: {skills}")
			return skills
		except Exception as e:
			self.logger.warning(f"路由匹配失败，跳过: {e}")
			return []

	async def _diagnose_files_from_skills(self, problem_context: str, skill_text: str,
	                                      design_doc: str = "") -> dict:
		"""据 skill 必查步骤，让 LLM 产出 files_to_modify。
		若 LLM 返回 need_file_descriptions=True，则补读 docs/file_descriptions.yaml 再问一次（懒加载）。"""
		diagnosis = {'files_to_modify': []}
		file_descriptions = ''
		for attempt in range(2):
			prompt = self.prompts['skill_guided_diagnosis_prompt'].format(
				problem_context=problem_context,
				skill_text=skill_text or '（未匹配到具体 skill，请基于问题与通用规范判断）',
				design_doc=design_doc or '（无）',
				file_descriptions=file_descriptions or '（暂未提供项目文件地图；如需定位文件，请在 need_file_descriptions 置 true 后重试）',
			)
			response = await self._generate_with_tools(prompt)
			parsed = self._extract_json(response)
			if not isinstance(parsed, dict):
				self.logger.warning("技能驱动诊断未返回有效 JSON")
				break
			if parsed.get('need_file_descriptions') and not file_descriptions and attempt == 0:
				self.logger.info("诊断请求项目文件地图，补读 docs/file_descriptions.yaml 后重试")
				file_descriptions = self._load_doc('docs/file_descriptions.yaml')
				continue
			for loc in parsed.get('files_to_modify', []) or []:
				if not isinstance(loc, dict):
					continue
				file_name = loc.get('file_name') or loc.get('file', '')
				if not file_name:
					continue
				file_type = loc.get('file_type') or ('simulator' if file_name.endswith('.py') else 'config')
				diagnosis['files_to_modify'].append({
					'file_name': file_name,
					'file_type': file_type,
					'modification': loc.get('modification', ''),
					'param_or_method': loc.get('param_or_method', ''),
				})
			break
		return diagnosis

	async def _apply_and_verify(self, diagnosis: dict, design_doc: str = "") -> dict:
		"""写临时诊断 → 逐文件修改（含审计）→ 冒烟验证。两条优化路径共享。"""
		import tempfile
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
			json.dump(diagnosis, f, ensure_ascii=False, indent=2)
			diagnosis_path = f.name

		modification_results = []
		try:
			modification_results = await self.modify_file_sequentially(
				diagnosis_path,
				self.config_dir,
				design_doc=design_doc
			)
		finally:
			try:
				os.remove(diagnosis_path)
			except Exception:
				pass

		success = any(r.get('result') in (True, 'success') for r in modification_results)

		# 冒烟验证：失败则把运行时错误交给修复Agent继续修改，直到通过或达到最大尝试次数
		verify_result = {'success': False, 'error': '未执行'}
		if success:
			simulator_file_path = os.path.join(self.project_dir, 'simulator.py')
			config_path = os.path.join(self.config_dir, 'simulation_config.yaml')
			main_file_path = os.path.join(self.project_dir, 'main.py')
			main_file_path = main_file_path if os.path.exists(main_file_path) else None
			if os.path.exists(simulator_file_path) and os.path.exists(config_path):
				max_verify_fix_attempts = 5
				for verify_attempt in range(1, max_verify_fix_attempts + 1):
					verify_result = await self.quick_verify_with_minimal_config(simulator_file_path, config_path)
					if verify_result.get('success'):
						if verify_attempt > 1:
							self.logger.info(f"✓ 冒烟验证在第 {verify_attempt} 次尝试后通过")
						break

					if verify_attempt >= max_verify_fix_attempts:
						self.logger.error(f"❌ 冒烟验证连续 {max_verify_fix_attempts} 次未通过，停止修复")
						break

					self.logger.warning(
						f"⚠️ 冒烟验证未通过（第 {verify_attempt}/{max_verify_fix_attempts} 次），调用修复Agent继续修改..."
					)
					error_output = verify_result.get('error') or verify_result.get('output') or '未知错误'
					await self.fix_runtime_errors(
						error_message=error_output,
						error_traceback=f"标准输出:\n{verify_result.get('output', '')}\n\n标准错误:\n{verify_result.get('error', '')}",
						main_file_path=main_file_path,
						simulator_file_path=simulator_file_path,
						config_path=config_path,
						max_attempts=5
					)

		optimization_passed = success and verify_result.get('success', False)

		if optimization_passed:
			solved = {
				'issues_addressed': len(modification_results),
				'reason': '修改已应用并通过冒烟验证'
			}
		elif success:
			solved = {
				'issues_addressed': len(modification_results),
				'reason': '修改已应用但冒烟验证未通过'
			}
		else:
			solved = {
				'issues_addressed': 0,
				'reason': '未能成功应用任何修改'
			}

		return {
			'diagnosis': diagnosis,
			'success': success,
			'optimization_passed': optimization_passed,
			'solved': solved,
			'modification_results': modification_results,
			'verify_result': verify_result
		}

	async def diagnose_by_traceback(self, error_traceback: str, simulator_content: str = "", main_content: str = "", config_files: Dict[str, str] = None) -> Dict[str, Any]:
		"""从报错现象出发，沿调用链与数据流反向追踪根因。

		1. 用 LLM 分析错误堆栈，识别相关模块/配置。
		2. 读取相关接口文档与配置文件。
		3. 返回结构化的诊断信息。
		"""
		module_interface_docs, config_files_dict = await self._extract_module_api_docs_from_error(error_traceback)

		prompt_tmpl = self.prompts.get('trace_issue_backwards_prompt')
		if not prompt_tmpl:
			self.logger.warning("未找到 trace_issue_backwards_prompt，使用兜底分析")
			return {
				'root_cause': '未配置 trace_issue_backwards_prompt',
				'files_to_check': list((config_files or {}).keys()),
				'module_interface_docs': module_interface_docs,
			}

		prompt = prompt_tmpl.format(
			error_traceback=error_traceback,
			simulator_content=simulator_content[:6000],
			main_content=main_content[:3000],
			module_interface_docs=module_interface_docs,
			config_files_str=self._format_config_files_str(config_files_dict or config_files or {}),
		)

		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.warning("LLM 根因分析返回空响应")
			return {'root_cause': 'LLM 无响应', 'files_to_check': []}

		# 尝试解析 JSON 诊断结果
		json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
		if json_match:
			try:
				return json.loads(json_match.group(1))
			except json.JSONDecodeError as e:
				self.logger.warning(f"解析诊断 JSON 失败: {e}")

		return {'root_cause': response, 'files_to_check': []}

	def _format_config_files_str(self, config_files: Dict[str, str]) -> str:
		"""将配置文件字典格式化为文本。"""
		if not config_files:
			return "（未提供配置文件）"
		parts = []
		for filename, content in config_files.items():
			parts.append(f"{'='*40}\n配置文件: {filename}\n{'='*40}\n{content}\n")
		return '\n'.join(parts)

	def validate_llm_io(self, response: str, expected_schema: dict) -> bool:
		"""验证 LLM 输出是否符合预期的 JSON/YAML schema（轻量级检查）。"""
		if not response:
			self.logger.warning("validate_llm_io: response 为空")
			return False
		response_clean = re.sub(r"^```json\s*|^```yaml\s*|\s*```$", "", response, flags=re.DOTALL).strip()
		if expected_schema.get('format') == 'json':
			try:
				parsed = json.loads(response_clean)
				required = expected_schema.get('required_keys', [])
				missing = [k for k in required if k not in parsed]
				if missing:
					self.logger.warning(f"validate_llm_io: 缺少必要字段 {missing}")
					return False
				return True
			except json.JSONDecodeError as e:
				self.logger.warning(f"validate_llm_io: JSON 解析失败: {e}")
				return False
		# YAML 或文本格式暂不做严格校验
		return True

	async def check_config_agreement_alignment(self, config_path: str, design_doc_path: str) -> List[str]:
		"""检查配置文件是否与设计文档/约定一致（基于规则 + LLM）。

		Returns:
			不一致项描述列表
		"""
		issues = []
		if not os.path.exists(config_path):
			issues.append(f"配置文件不存在: {config_path}")
			return issues
		if not os.path.exists(design_doc_path):
			issues.append(f"设计文档不存在: {design_doc_path}")
			return issues

		with open(config_path, 'r', encoding='utf-8') as f:
			config_content = f.read()
		with open(design_doc_path, 'r', encoding='utf-8') as f:
			design_content = f.read()

		prompt_tmpl = self.prompts.get('validate_config_alignment_prompt')
		if not prompt_tmpl:
			self.logger.warning("未找到 validate_config_alignment_prompt，跳过 LLM 对齐检查")
			return issues

		prompt = prompt_tmpl.format(
			config_file_name=os.path.basename(config_path),
			config_content=config_content[:5000],
			design_doc=design_content[:5000],
		)
		response = await self.generate_llm_response(prompt)
		if not response:
			return issues

		# 返回应为 JSON 数组
		json_match = re.search(r'```json\s*(\[[\s\S]*?\])\s*```', response, re.DOTALL)
		if json_match:
			try:
				parsed = json.loads(json_match.group(1))
				if isinstance(parsed, list):
					issues.extend(parsed)
			except json.JSONDecodeError:
				pass
		return issues

	async def quick_verify_with_minimal_config(self, simulator_file_path: str, config_path: str) -> dict:
		"""使用 pop=5, steps=1 的最小配置快速验证修复是否有效。

		Args:
			simulator_file_path: simulator.py 路径（用于校验存在性，目前不影响运行）
			config_path: simulation_config.yaml 路径

		Returns:
			{'success': bool, 'output': str, 'error': str, 'backup_path': str}
		"""
		if not os.path.exists(config_path):
			return {'success': False, 'error': f'配置文件不存在: {config_path}', 'output': '', 'backup_path': ''}

		backup_path = config_path + '.quick_verify_backup'
		shutil.copy2(config_path, backup_path)
		self.logger.info(f"✓ 已备份原配置: {backup_path}")

		try:
			with open(config_path, 'r', encoding='utf-8') as f:
				config_data = yaml.safe_load(f) or {}

			if not isinstance(config_data, dict):
				return {'success': False, 'error': '配置文件根节点不是字典', 'output': '', 'backup_path': backup_path}

			sim_cfg = config_data.setdefault('simulation', {})
			if not isinstance(sim_cfg, dict):
				sim_cfg = {}
				config_data['simulation'] = sim_cfg

			sim_cfg['initial_population'] = 5
			time_cfg = sim_cfg.get('time')
			if isinstance(time_cfg, dict):
				time_cfg['total_steps'] = 1
			else:
				sim_cfg['total_years'] = 1

			with open(config_path, 'w', encoding='utf-8') as f:
				yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
			self.logger.info("✓ 已写入最小验证配置 (pop=5, steps=1)")

			project_root = self._rag_project_root
			run_command = f'python run_project.py --project {self.simulation_name}'
			env = os.environ.copy()
			env['PYTHONIOENCODING'] = 'utf-8'

			if os.name == 'nt':
				run_command = f'chcp 65001 >nul && {run_command}'

			result = subprocess.run(
				run_command,
				shell=True,
				cwd=project_root,
				capture_output=True,
				text=True,
				timeout=120,
				encoding='utf-8',
				errors='replace',
				env=env,
			)

			success = result.returncode == 0
			if success:
				self.logger.info("✓ 最小配置验证通过")
			else:
				self.logger.error(f"❌ 最小配置验证失败: {result.stderr}")

			return {
				'success': success,
				'output': result.stdout,
				'error': result.stderr,
				'backup_path': backup_path,
			}
		except Exception as e:
			self.logger.error(f"最小配置验证异常: {e}")
			return {'success': False, 'error': str(e), 'output': '', 'backup_path': backup_path}
		finally:
			# 恢复原配置
			if os.path.exists(backup_path):
				shutil.copy2(backup_path, config_path)
				os.remove(backup_path)
				self.logger.info("✓ 已恢复原配置")
