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

	def _resolve_payload_file_path(self, file_name: str) -> Optional[str]:
		"""Resolve a direct apply payload path to a writable project file."""
		if not file_name:
			return None
		name = str(file_name).strip().replace('\\', '/')
		candidates = []
		if os.path.isabs(name):
			candidates.append(os.path.abspath(name))
		else:
			project_root = os.path.abspath(self._rag_project_root)
			project_name = os.path.basename(os.path.abspath(self.project_dir))
			if name.startswith('projects/'):
				candidates.append(os.path.abspath(os.path.join(project_root, name)))
			if name.startswith(project_name + '/'):
				candidates.append(os.path.abspath(os.path.join(os.path.dirname(self.project_dir), name)))
			candidates.extend([
				os.path.abspath(os.path.join(self.project_dir, name)),
				os.path.abspath(os.path.join(project_root, name)),
				os.path.abspath(os.path.join(self.config_dir, name)),
			])

		allowed_roots = [
			os.path.abspath(self.project_dir),
			os.path.abspath(self.config_dir),
			os.path.abspath(os.path.join(self._rag_project_root, 'plugins', 'generated')),
		]
		for path in candidates:
			if not any(path == root or path.startswith(root + os.sep) for root in allowed_roots):
				continue
			if os.path.exists(path):
				return path
		for path in candidates:
			if any(path == root or path.startswith(root + os.sep) for root in allowed_roots):
				return path
		return None

	@staticmethod
	def _find_line_block(lines: List[str], block: List[str], start: int = 0) -> int:
		if not block:
			return -1
		max_start = len(lines) - len(block)
		for idx in range(start, max_start + 1):
			if lines[idx:idx + len(block)] == block:
				return idx
		stripped_block = [line.strip() for line in block]
		for idx in range(start, max_start + 1):
			if [line.strip() for line in lines[idx:idx + len(block)]] == stripped_block:
				return idx
		# read_file_span displays lines as "<line_no>: <source>".  Accept a block
		# copied verbatim from that tool, but only when every block line has the
		# display prefix so ordinary source text is not altered.
		numbered = [re.match(r'^\s*\d+:\s?(.*)$', line) for line in block]
		if numbered and all(numbered):
			unnumbered_block = [match.group(1) for match in numbered]
			return CodeFixerAgent._find_line_block(lines, unnumbered_block, start)
		return -1

	def _apply_diff_lines_to_file(self, file_path: str, diff_lines: dict) -> bool:
		"""Apply the compact diff_lines protocol emitted inside <apply_modifications>."""
		if not file_path or not isinstance(diff_lines, dict) or not diff_lines or not os.path.exists(file_path):
			return False
		supported_fields = {
			'replace_block', 'replace_with',
			'append_after_block', 'delete_block',
		}
		unknown_fields = sorted(set(diff_lines) - supported_fields)
		if unknown_fields:
			self.logger.warning(f"diff_lines 包含不支持的字段: {unknown_fields}")
			return False
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				content = f.read()
		except Exception as e:
			self.logger.error(f"读取待修改文件失败: {file_path}, {e}")
			return False

		ends_with_newline = content.endswith('\n')
		lines = content.splitlines()
		changed = False
		operation_count = 0

		if isinstance(diff_lines.get('replace_block'), list):
			operation_count += 1
			old_block = [str(line) for line in diff_lines.get('replace_block', [])]
			new_block = [str(line) for line in diff_lines.get('replace_with', [])]
			idx = self._find_line_block(lines, old_block)
			if idx == -1:
				if self._find_line_block(lines, new_block) == -1:
					self.logger.warning(
						f"replace_block 未匹配: {file_path}; "
						f"expected={old_block!r}"
					)
					return False
			else:
				lines[idx:idx + len(old_block)] = new_block
				changed = True

		append_after = diff_lines.get('append_after_block')
		if isinstance(append_after, dict):
			operation_count += 1
			start_line = str(append_after.get('block_start', ''))
			end_line = str(append_after.get('block_end', ''))
			insert_lines = [str(line) for line in append_after.get('insert_lines', [])]
			start_idx = self._find_line_block(lines, [start_line]) if start_line else -1
			end_idx = self._find_line_block(lines, [end_line], start_idx if start_idx != -1 else 0) if end_line else -1
			if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
				self.logger.warning(f"append_after_block 未匹配: {file_path}")
				return False
			if lines[end_idx + 1:end_idx + 1 + len(insert_lines)] != insert_lines:
				lines[end_idx + 1:end_idx + 1] = insert_lines
				changed = True

		delete_block = diff_lines.get('delete_block')
		if isinstance(delete_block, dict):
			operation_count += 1
			start_line = str(delete_block.get('block_start', ''))
			end_line = str(delete_block.get('block_end', ''))
			start_idx = self._find_line_block(lines, [start_line]) if start_line else -1
			end_idx = self._find_line_block(lines, [end_line], start_idx if start_idx != -1 else 0) if end_line else -1
			if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
				del lines[start_idx:end_idx + 1]
				changed = True

		if operation_count == 0:
			return False
		if not changed:
			return True

		new_content = '\n'.join(lines)
		if ends_with_newline:
			new_content += '\n'
		if file_path.lower().endswith('.py'):
			try:
				compile(new_content, file_path, 'exec')
			except SyntaxError as e:
				self.logger.error(
					f"diff_lines 生成的 Python 代码语法无效，拒绝写盘: "
					f"{file_path}:{e.lineno}:{e.offset} {e.msg}"
				)
				return False
		try:
			shutil.copy(file_path, file_path + '.backup')
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(new_content)
			return True
		except Exception as e:
			self.logger.error(f"写入 diff_lines 修改失败: {file_path}, {e}")
			return False

	def _apply_direct_diff_payload(self, response: str) -> Optional[bool]:
		"""Apply list-style direct payloads: [{file_name, diff_lines}, ...]."""
		parsed = self._extract_json(response)
		if not isinstance(parsed, list):
			return None
		items = [item for item in parsed if isinstance(item, dict) and item.get('diff_lines')]
		if not items:
			return None

		applied = 0
		for item in items:
			file_path = self._resolve_payload_file_path(item.get('file_name', ''))
			if not file_path:
				self.logger.warning(f"无法解析直接修改目标文件: {item.get('file_name')}")
				continue
			if self._apply_diff_lines_to_file(file_path, item.get('diff_lines') or {}):
				applied += 1
				self.logger.info(f"✓ 已应用 diff_lines 修改: {file_path}")
			else:
				self.logger.warning(f"diff_lines 修改未应用: {file_path}")
		return applied == len(items)

	def _apply_runtime_fix(self, response, main_file_path, simulator_file_path):
		direct_diff_result = self._apply_direct_diff_payload(response)
		if direct_diff_result is not None:
			return direct_diff_result

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

	async def fix_runtime_errors(self, error_message, error_traceback, main_file_path=None, simulator_file_path=None, config_path=None, max_attempts=None):
		"""运行时错误修复：多轮工具诊断 + 直接应用修改 + 冒烟验证。

		Args:
			error_message: 错误信息（用于 FileNotFoundError 快速判断）
			error_traceback: 完整的错误堆栈
			main_file_path: main.py 路径（可选）
			simulator_file_path: simulator.py 路径（传给 quick_verify_with_minimal_config）
			config_path: simulation_config.yaml 路径（传给 quick_verify_with_minimal_config）
			max_attempts: 最大修复尝试次数（None=读全局 retries.runtime_fix）

		Returns:
			bool: 是否修复成功
		"""
		if max_attempts is None:
			max_attempts = get_retries()['runtime_fix']
		self.logger.info("🔧 开始修复运行时错误...")

		# 特殊处理 FileNotFoundError
		if "FileNotFoundError" in error_message:
			if await self._handle_file_not_found_error(error_traceback, config_path):
				self.logger.info("✓ 已成功处理 FileNotFoundError 并生成了缺失文件。")
				return True

		prompt = self.prompts['fix_runtime_errors_prompt'].format(
			error_traceback=error_traceback,
		)

		for attempt in range(1, max_attempts + 1):
			self.logger.info(f"第 {attempt}/{max_attempts} 次修复尝试...")

			# 两态协议：LLM 可多轮调用工具；最终只允许输出“应用修改”内容
			response = await self._generate_with_tools(prompt, enforce_apply_protocol=True)
			if not response:
				continue

			# 解析 <apply_modifications> 包裹（严格两态协议）
			apply_payload = self._extract_apply_payload(response)
			if not apply_payload:
				self.logger.warning("⚠️ 本轮输出未遵循两态协议（缺少 <apply_modifications>）")
				continue

			# 直接应用本轮增量修改
			if not self._apply_runtime_fix(apply_payload, main_file_path, simulator_file_path):
				self.logger.warning("⚠️ 本轮修改应用失败")
				continue

			# 冒烟验证
			verify_result = await self.quick_verify_with_minimal_config(simulator_file_path, config_path)
			if verify_result.get('success'):
				self.logger.info("✓ 修复通过冒烟验证")
				return True

			err_out = verify_result.get('error') or verify_result.get('output') or '冒烟验证失败'
			self.logger.warning(f"⚠️ 第 {attempt} 次冒烟验证未通过")
			prompt += f"\n\n【第 {attempt} 次修复后验证失败】\n标准输出：{verify_result.get('output', '')}\n标准错误：{err_out}"

		self.logger.error("❌ 所有修复尝试均失败")
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
		if diagnosis.get('apply_payload'):
			self.logger.info("✓ 诊断阶段已返回可直接应用修改，跳过 files_to_modify 流程")
			return await self._apply_payload_and_verify(diagnosis.get('apply_payload', ''), diagnosis)

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
		if diagnosis.get('apply_payload'):
			self.logger.info("✓ 技能驱动诊断已返回可直接应用修改，跳过 files_to_modify 流程")
			return await self._apply_payload_and_verify(diagnosis.get('apply_payload', ''), diagnosis)
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

	def _resolve_read_path(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
		"""Resolve a project-readable file path and keep access inside allowed roots."""
		if not file_path:
			return None, "[error: file_path is empty]"

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
			if not any(path.startswith(root + os.sep) or path == root for root in allowed_roots):
				return None, f"[error: reading this path is not allowed: {file_path}]"
			return path, None
		return None, f"[file not found: {file_path}]"

	def _read_text_file(self, path: str) -> Tuple[Optional[str], Optional[str]]:
		"""Read a text file with the encodings used across generated projects."""
		for enc in ('utf-8', 'gbk', 'gb2312', 'utf-8-sig'):
			try:
				with open(path, 'r', encoding=enc) as f:
					return f.read(), None
			except UnicodeDecodeError:
				continue
			except Exception as e:
				return None, f"[read failed: {path}: {e}]"
		return None, f"[read failed: unsupported encoding: {path}]"

	@staticmethod
	def _format_numbered_lines(lines: List[str], start_line: int) -> str:
		return "\n".join(f"{idx}: {line}" for idx, line in enumerate(lines, start=start_line))

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
					max_len = 8000
					if len(content) > max_len:
						content = content[:max_len] + f"\n\n[文件过长，已截断；原始长度 {len(content)} 字符]"
					return content
				except UnicodeDecodeError:
					continue
				except Exception as e:
					return f"[读取文件失败 {file_path}: {e}]"
		return f"[未找到文件: {file_path}]"

	def read_file_span(self, file_path: str, start_line: Any = 1, end_line: Any = 160) -> str:
		"""Read a bounded, line-numbered span from a project file."""
		path, error = self._resolve_read_path(file_path)
		if error:
			return error
		content, error = self._read_text_file(path)
		if error:
			return error
		lines = content.splitlines()
		try:
			start = max(1, int(start_line))
			end = max(start, int(end_line))
		except (TypeError, ValueError):
			return "[error: start_line/end_line must be integers]"

		max_lines = 220
		if end - start + 1 > max_lines:
			end = start + max_lines - 1
		start_idx = min(start - 1, len(lines))
		end_idx = min(end, len(lines))
		rel = os.path.relpath(path, self._rag_project_root)
		body = self._format_numbered_lines(lines[start_idx:end_idx], start_idx + 1)
		return f"[file: {rel}; lines: {start_idx + 1}-{end_idx}; total_lines: {len(lines)}]\n{body}"

	def outline_file(self, file_path: str) -> str:
		"""Return a compact outline of imports, classes, functions, and top-level config keys."""
		path, error = self._resolve_read_path(file_path)
		if error:
			return error
		content, error = self._read_text_file(path)
		if error:
			return error
		rel = os.path.relpath(path, self._rag_project_root)
		lines = content.splitlines()
		outline = [f"[file: {rel}; total_lines: {len(lines)}]"]
		ext = os.path.splitext(path)[1].lower()

		if ext == '.py':
			for i, line in enumerate(lines, start=1):
				stripped = line.strip()
				if (
					stripped.startswith('class ')
					or stripped.startswith('def ')
					or stripped.startswith('async def ')
					or (line.startswith(('import ', 'from ')) and len(outline) < 40)
				):
					outline.append(f"{i}: {line.rstrip()}")
				if len(outline) >= 120:
					outline.append("[outline truncated]")
					break
		elif ext in {'.yaml', '.yml', '.json'}:
			for i, line in enumerate(lines, start=1):
				if line and not line.startswith((' ', '\t', '#')):
					outline.append(f"{i}: {line.rstrip()[:180]}")
				if len(outline) >= 120:
					outline.append("[outline truncated]")
					break
		else:
			sample = lines[:80]
			outline.append(self._format_numbered_lines(sample, 1))
			if len(lines) > len(sample):
				outline.append("[outline truncated]")
		return "\n".join(outline)

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

	def _extract_apply_payload(self, text: str) -> Optional[str]:
		"""提取 <apply_modifications> 包裹内容；未包裹返回 None。"""
		if not text:
			return None
		m = re.search(r'<apply_modifications>\s*([\s\S]*?)\s*</apply_modifications>', text, re.DOTALL)
		if m:
			return m.group(1).strip()
		return None

	def _validate_apply_payload(self, payload: str) -> Optional[str]:
		"""Return a protocol error before an apply payload leaves the LLM conversation."""
		parsed = self._extract_json(payload)
		if isinstance(parsed, list):
			if not parsed:
				return "JSON 数组不能为空"
			allowed = {'replace_block', 'replace_with', 'append_after_block', 'delete_block'}
			for index, item in enumerate(parsed, start=1):
				if not isinstance(item, dict) or not item.get('file_name'):
					return f"第 {index} 项缺少 file_name"
				diff_lines = item.get('diff_lines')
				if not isinstance(diff_lines, dict) or not diff_lines:
					actual_type = type(diff_lines).__name__ if diff_lines is not None else "missing"
					return f"第 {index} 项的 diff_lines 必须是非空对象，当前类型: {actual_type}"
				unknown = sorted(set(diff_lines) - allowed)
				if unknown:
					return f"第 {index} 项含有不支持的 diff_lines 字段: {unknown}"
				operation_count = sum(
					key in diff_lines for key in ('replace_block', 'append_after_block', 'delete_block')
				)
				if operation_count == 0:
					return f"第 {index} 项没有 replace/delete/append 操作"
				if ('replace_block' in diff_lines) != ('replace_with' in diff_lines):
					return f"第 {index} 项的 replace_block 和 replace_with 必须同时出现"
				if 'replace_block' in diff_lines:
					if not isinstance(diff_lines['replace_block'], list) or not isinstance(diff_lines['replace_with'], list):
						return f"第 {index} 项的 replace_block/replace_with 必须是行数组"
				for key in ('append_after_block', 'delete_block'):
					if key in diff_lines and not isinstance(diff_lines[key], dict):
						return f"第 {index} 项的 {key} 必须是对象"
				if 'append_after_block' in diff_lines:
					append = diff_lines['append_after_block']
					if not append.get('block_start') or not append.get('block_end'):
						return f"第 {index} 项的 append_after_block 缺少现有代码锚点"
					if not isinstance(append.get('insert_lines'), list) or not append['insert_lines']:
						return f"第 {index} 项的 insert_lines 必须是非空行数组"
				if 'delete_block' in diff_lines:
					delete = diff_lines['delete_block']
					if not delete.get('block_start') or not delete.get('block_end'):
						return f"第 {index} 项的 delete_block 缺少 block_start/block_end"
			return None

		if isinstance(parsed, dict):
			if any(key in parsed for key in ('methods', 'functions', 'config_files')):
				return None
			return "JSON 对象不含 methods、functions 或 config_files"

		if re.search(r'```ya?ml\s+[\s\S]+?```', payload, re.IGNORECASE):
			return None
		return "无法解析 apply_modifications 中的 JSON/YAML"

	@staticmethod
	def _normalize_import_lines(value) -> List[str]:
		"""把 imports_to_add / delete_imports 规范化为逐行字符串列表。"""
		if not value:
			return []
		if isinstance(value, str):
			items = value.splitlines()
		else:
			items = list(value) if isinstance(value, (list, tuple, set)) else [str(value)]
		return [str(item).strip() for item in items if str(item).strip()]

	def _apply_python_import_changes(self, file_path: str, imports_to_add=None, delete_imports=None) -> bool:
		"""在 Python 文件顶部追加/删除 import 语句。"""
		imports_to_add = self._normalize_import_lines(imports_to_add)
		delete_imports = self._normalize_import_lines(delete_imports)
		if not imports_to_add and not delete_imports:
			return True
		if not file_path or not os.path.exists(file_path):
			return False
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				content = f.read()
		except Exception as e:
			self.logger.error(f"读取文件失败，无法修改 import: {file_path}, {e}")
			return False

		lines = content.splitlines()
		original_lines = list(lines)
		insert_idx = 0
		seen_imports = set(line.strip() for line in lines)

		for idx, line in enumerate(lines):
			stripped = line.strip()
			if stripped.startswith('import ') or stripped.startswith('from '):
				insert_idx = idx + 1
			elif stripped and not stripped.startswith('#'):
				if insert_idx == 0:
					insert_idx = idx
					break

		for import_line in delete_imports:
			lines = [line for line in lines if line.strip() != import_line]

		for import_line in imports_to_add:
			if import_line not in seen_imports:
				lines.insert(insert_idx, import_line)
				insert_idx += 1
				seen_imports.add(import_line)

		if lines != original_lines:
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write('\n'.join(lines) + '\n')
			self.logger.info(f"✓ 已更新 Python 导入: {file_path}")
		return True

	async def _execute_tool(self, tool_call: dict) -> str:
		"""执行一次工具调用并返回文本结果。"""
		name = tool_call.get('name')
		args = tool_call.get('args', {})
		if name == 'read_file':
			return self.read_file(args.get('file_path', ''))
		if name == 'read_file_span':
			return self.read_file_span(
				args.get('file_path', ''),
				args.get('start_line', 1),
				args.get('end_line', 160)
			)
		if name == 'outline_file':
			return self.outline_file(args.get('file_path', ''))
		if name == 'search_project':
			return self.search_project(
				args.get('pattern', ''),
				args.get('glob', '**/*.py'),
				args.get('path')
			)
		return f"[未知工具: {name}]"

	async def _chat(self, messages: list) -> Optional[str]:
		"""直接调用模型后端（不经过 BaseAgent 的 memory 拼接）。

		model_backend.run 不支持 {"role":"system"}，需提取 system 内容
		注入到首条 user 消息中。
		"""
		# 分离 system 消息，拼入首条 user 消息
		system_parts = []
		chat_messages = []
		for m in messages:
			if m.get("role") == "system":
				system_parts.append(m["content"])
			else:
				chat_messages.append(m)
		if system_parts and chat_messages:
			system_text = "\n\n".join(system_parts)
			first_user = chat_messages[0]
			if first_user.get("role") == "user":
				chat_messages[0] = {
					"role": "user",
					"content": f"{system_text}\n\n{first_user['content']}"
				}
			else:
				chat_messages.insert(0, {"role": "user", "content": system_text})

		attempts = 0
		while attempts < self.max_retry_attempts:
			try:
				sent_messages = chat_messages
				extra_kwargs = getattr(self, '_extra_kwargs', None)
				if extra_kwargs:
					from openai import OpenAI
					client = OpenAI(base_url=self._api_url, api_key=self._api_key, timeout=self.api_timeout)
					sent_messages = messages
					response = await asyncio.wait_for(
						asyncio.to_thread(
							client.chat.completions.create,
							model=self.model_type,
							messages=messages,
							timeout=self.api_timeout,
							**extra_kwargs
						),
						timeout=120.0
					)
					print(f"[LLM {self.__class__.__name__}._chat] 使用 extra_kwargs 调用模型，返回: {response}")
				else:
					response = await asyncio.wait_for(
						asyncio.to_thread(self.model_backend.run, chat_messages),
						timeout=120.0
					)
				content = response.choices[0].message.content
				if content is not None:
					# DEBUG: 输出 LLM 原始返回
					caller = self.__class__.__name__
					try:
						prompt_dump = json.dumps(sent_messages, ensure_ascii=False, indent=2)
					except Exception:
						prompt_dump = str(sent_messages)
					# print(f"\n{'='*60}\n[LLM {caller}._chat] 完整提示词:\n{prompt_dump}\n{'='*60}\n")
					print(f"\n{'='*60}\n[LLM {caller}._chat] 原始返回:\n{content}\n{'='*60}\n")
					self.logger.debug(f"[LLM {caller}._chat] 原始返回:\n{content}")
					return content
				self.logger.warning(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次返回空，准备重试")
			except asyncio.TimeoutError:
				self.logger.error(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次超时（{self.api_timeout}s）")
			except Exception as e:
				self.logger.error(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次出错：{e}")
			attempts += 1
			if attempts < self.max_retry_attempts:
				await asyncio.sleep(self.retry_delay)
		self.logger.error(f"{self.__class__.__name__} 工具调用在 {self.max_retry_attempts} 次尝试后失败")
		return None

	async def _generate_with_tools(self, prompt: str, enforce_apply_protocol: bool = False) -> Optional[str]:
		"""带 read_file / search_project 工具调用的 LLM 对话循环。

		当 enforce_apply_protocol=True 时启用两态输出协议：
		1) 调用工具：输出一个 <tool ...>...</tool>
		2) 应用修改：输出 <apply_modifications>...</apply_modifications>
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
				apply_payload = self._extract_apply_payload(response)
				if apply_payload:
					protocol_error = self._validate_apply_payload(apply_payload)
					if not protocol_error:
						return response
					self.logger.warning(f"apply_modifications 协议校验失败: {protocol_error}")
					messages.append({"role": "assistant", "content": response})
					messages.append({
						"role": "user",
						"content": (
							f"你的 apply_modifications 无法执行：{protocol_error}。\n"
							"只重新输出完整补丁。结构必须是："
							'<apply_modifications>[{"file_name":"路径","file_type":"config",'
							'"diff_lines":{"replace_block":["原行"],"replace_with":["新行"]}}]'
							"</apply_modifications>。每个 diff_lines 是对象且只含一个操作；"
							"多个操作（包括同一文件）拆成多个顶层数组项。"
						)
					})
					continue
				if not enforce_apply_protocol:
					return response
				# 格式纠偏：仅允许两态输出
				messages.append({"role": "assistant", "content": response})
				messages.append({
					"role": "user",
					"content": (
						"你的输出格式无效。只能二选一：\n"
						"1) <tool name=\"search_project\">...</tool> / <tool name=\"outline_file\">...</tool> / <tool name=\"read_file_span\">...</tool> / <tool name=\"read_file\">...</tool>\n"
						"2) <apply_modifications>...</apply_modifications>（其中放置可直接应用的 JSON/YAML 修改块）"
					)
				})
				continue

			round_no += 1
			self.logger.info(f"🔧 工具调用 #{round_no}: {tool_call['name']}({tool_call['args']})")
			result = await self._execute_tool(tool_call)
			# 截断过长的工具结果，防止上下文爆炸
			if len(result) > 8000:
				result = result[:8000] + "\n\n[tool result truncated; use outline_file/search_project/read_file_span for narrower context]"

			messages.append({"role": "assistant", "content": response})
			messages.append({
				"role": "user",
				"content": f"<tool_result name=\"{tool_call['name']}\">\n{result}\n</tool_result>"
			})

	# ---------- 文档读取 / 技能路由 / 技能驱动诊断 ----------

	def _load_doc(self, rel_path: str) -> str:
		"""读取文档内容（rel_path 相对仓库根，如 'docs/code_fixer_skills/xxx.md'，
		也兼容相对 docs/ 目录的路径、以及只给出 skill 裸文件名的情况）。失败返回 ''。"""
		# 用 __file__ 定位仓库根，不依赖 self.docs_dir（外部可能传错）
		repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		base = os.path.basename(rel_path)
		candidates = [
			os.path.join(repo_root, rel_path),
			os.path.join(self.docs_dir, rel_path),
		]
		# 兜底：路由表里 skill 常以裸文件名出现（skill_xxx.md），按约定目录补全
		if base.startswith('skill_') and base.endswith('.md'):
			candidates.append(os.path.join(self.docs_dir, 'code_fixer_skills', base))
			candidates.append(os.path.join(repo_root, 'docs', 'code_fixer_skills', base))
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
				# 文件存在但所有编码均无法解码，继续尝试下一个候选路径
				self.logger.warning(f"文件存在但所有编码均无法解码: {path}")
		self.logger.warning(f"未找到文档: {rel_path}")
		return ''

	@staticmethod
	def _resolve_skill_path(path: str) -> str:
		"""将裸 skill 文件名补全为相对路径，非裸文件名原样返回。"""
		if not path:
			return path
		base = os.path.basename(path)
		if base == path and base.startswith('skill_') and base.endswith('.md'):
			return os.path.join('docs', 'code_fixer_skills', base)
		return path

	def _load_skill_files(self, paths: list) -> str:
		"""读取并拼接选中的 skill 文件内容。"""
		if not paths:
			return ''
		blocks = []
		for p in paths:
			p = self._resolve_skill_path(p)
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
		attempt = 0
		while True:
			prompt = self.prompts['skill_guided_diagnosis_prompt'].format(
				problem_context=problem_context,
				skill_text=skill_text or '（未匹配到具体 skill，请基于问题与通用规范判断）',
				design_doc=design_doc or '（无）',
				file_descriptions=file_descriptions or '（暂未提供项目文件地图；如需定位文件，请在 need_file_descriptions 置 true 后重试）',
			)
			response = await self._generate_with_tools(prompt)
			# 兼容两态协议：若直接返回可应用修改，优先透传给上层直接应用
			apply_payload = self._extract_apply_payload(response or '')
			if apply_payload:
				diagnosis['apply_payload'] = apply_payload
				return diagnosis
			parsed = self._extract_json(response)
			if not isinstance(parsed, dict):
				attempt += 1
				continue
			# 兼容非包裹直出：若返回的是修改 JSON（methods/functions/config_files），也当作直接应用
			if any(k in parsed for k in ('methods', 'functions', 'config_files')):
				diagnosis['apply_payload'] = f"```json\n{json.dumps(parsed, ensure_ascii=False)}\n```"
				return diagnosis
			if parsed.get('need_file_descriptions') and not file_descriptions and attempt == 0:
				self.logger.info("诊断请求项目文件地图，补读 docs/file_descriptions.yaml 后重试")
				file_descriptions = self._load_doc('docs/file_descriptions.yaml')
				attempt += 1
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

	async def _apply_payload_and_verify(self, apply_payload: str, diagnosis: Optional[dict] = None) -> dict:
		"""直接应用 <apply_modifications> 负载并执行冒烟验证。"""
		simulator_file_path = os.path.join(self.project_dir, 'simulator.py')
		config_path = os.path.join(self.config_dir, 'simulation_config.yaml')
		main_file_path = os.path.join(self.project_dir, 'main.py')
		main_file_path = main_file_path if os.path.exists(main_file_path) else None

		success = self._apply_runtime_fix(apply_payload or '', main_file_path, simulator_file_path)
		modification_results = [
			{'file_name': 'direct_apply_payload', 'result': 'success' if success else 'failed'}
		] if apply_payload else []

		verify_result = {'success': False, 'error': '未执行'}
		if success and os.path.exists(simulator_file_path) and os.path.exists(config_path):
			verify_result = await self.quick_verify_with_minimal_config(simulator_file_path, config_path)

		optimization_passed = success and verify_result.get('success', False)
		if optimization_passed:
			solved = {'issues_addressed': 1, 'reason': '已直接应用修改并通过冒烟验证'}
		elif success:
			solved = {'issues_addressed': 1, 'reason': '已直接应用修改，但冒烟验证未通过'}
		else:
			solved = {'issues_addressed': 0, 'reason': '直接应用修改失败'}

		return {
			'diagnosis': diagnosis or {'files_to_modify': []},
			'success': success,
			'optimization_passed': optimization_passed,
			'solved': solved,
			'modification_results': modification_results,
			'verify_result': verify_result
		}

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
