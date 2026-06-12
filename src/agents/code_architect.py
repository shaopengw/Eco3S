import json
import time
from typing import Dict, List, Optional, Tuple

from src.utils.custom_logger import CustomLogger
from .shared_imports import *

import chromadb
from openai import OpenAI

class CodeArchitectAgent(BaseAgent):
	# 常量定义
	MAX_RETRY_ATTEMPTS = 5  # 每个步骤的最大重试次数
	MAX_FIX_ATTEMPTS = 2     # 总体检查的最大修复次数
	"""
	编码师Agent，继承BaseAgent，负责根据设计文档和配置，自动生成模拟器代码、详细配置和提示词。
	工作流程：每次只生成一个文件，逐步完成所有任务。
	"""
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
		# 指定使用 CLAUDE 的 claude-sonnet-4-5-20250929 模型
		super().__init__(agent_id, group_type='code_architect', window_size=3, 
		                 model_api_name='CLAUDE', model_type_name='claude-sonnet-4-5-20250929')
		# super().__init__(agent_id, group_type='research_analyst', window_size=3)
		
		# 加载prompts配置
		prompts_path = os.path.join(os.path.dirname(__file__), 'code_architect_prompts.yaml')
		with open(prompts_path, 'r', encoding='utf-8') as f:
			self.prompts = yaml.safe_load(f)
		
		self.system_message = self.prompts['system_message']
		self.simulator_output_dir = simulator_output_dir  # src/simulation/
		self.main_output_dir = main_output_dir  # entrypoints/
		self.docs_dir = docs_dir
		self.config_dir = config_dir  # config_[模拟名称]/
		self.config_template_dir = config_template_dir  # config_template/
		self.simulation_name = simulation_name
		self.simulation_type = simulation_type  # 'decision' 或 'survey'
		self.session = session  # Web模式的会话对象
		self.auto_mode = bool(auto_mode)
		self.logger = CustomLogger('code_architect').logger
		# RAG shared config
		self._rag_api_key = os.environ.get('OPENAI_API_KEY')
		self._rag_base_url = os.environ.get('OPENAI_API_BASE_URL')
		self._rag_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		self._rag_db_path = os.environ.get('CAUSAL_CLAIMS_DB_PATH', os.path.join(self._rag_project_root, 'experiment_dataset', 'chroma_db'))
		self._rag_embed_model = os.environ.get('CAUSAL_CLAIMS_EMBED_MODEL', 'text-embedding-3-large')

	def _rag_embed(self, client, text):
		max_retries = 3
		for attempt in range(max_retries):
			try:
				resp = client.embeddings.create(model=self._rag_embed_model, input=[text])
				return resp.data[0].embedding
			except Exception:
				if attempt == max_retries - 1:
					self.logger.warning("RAG embedding failed")
					return None
				time.sleep(2 ** attempt)
		return None

	def _interfaces_dir(self) -> str:
		return os.path.join(self._rag_project_root, 'src', 'interfaces')

	def _candidate_interface_stems(self, module_name: str) -> List[str]:
		name = (module_name or '').strip().lower()
		if not name:
			return []
		aliases = {
			'rebellion': 'rebels',
			'rebels': 'rebels',
			'residents': 'resident',
			'social': 'social_network',
			'job': 'job_market',
			'transport': 'transport_economy',
			'economy': 'transport_economy',
		}
		stems = [name]
		if name in aliases:
			stems.append(aliases[name])
		# 再加一个“去掉 module_ 前缀/后缀”的宽松版本
		stems.append(name.replace('-', '_'))
		# 去重保持顺序
		seen = set()
		ordered: List[str] = []
		for s in stems:
			if s and s not in seen:
				seen.add(s)
				ordered.append(s)
		return ordered

	def _find_interface_files(self, module_name: str) -> List[str]:
		interfaces_dir = self._interfaces_dir()
		if not os.path.isdir(interfaces_dir):
			return []

		stems = self._candidate_interface_stems(module_name)
		# 优先精确匹配 i<stem>.py
		for stem in stems:
			candidate = os.path.join(interfaces_dir, f"i{stem}.py")
			if os.path.exists(candidate):
				return [candidate]

		# 否则做一次文件名包含匹配（例如 rebellion -> irebels.py）
		try:
			files = [f for f in os.listdir(interfaces_dir) if f.endswith('.py') and f.startswith('i')]
		except Exception:
			return []

		needles = [s.replace('_', '') for s in stems]
		matched: List[str] = []
		for fname in files:
			base = fname.lower().replace('_', '')
			if any(n and n in base for n in needles):
				matched.append(os.path.join(interfaces_dir, fname))
		return matched[:3]

	def _read_interface_docs_for_modules(self, module_names: List[str], max_chars_per_file: int = 2000) -> str:
		"""读取 src/interfaces 下与模块名匹配的接口源码，作为“接口说明”。

		若找不到对应接口文件，则回退到读取 plugins/<module> 下的插件源码。
		"""
		parts: List[str] = []
		seen_files: set[str] = set()
		for name in module_names or []:
			interface_paths = self._find_interface_files(name)
			for path in interface_paths:
				if path in seen_files:
					continue
				seen_files.add(path)
				try:
					with open(path, 'r', encoding='utf-8') as f:
						content = f.read()
					if max_chars_per_file and len(content) > max_chars_per_file:
						content = content[:max_chars_per_file] + "\n...(已截断)"
					parts.append(f"\n## {os.path.basename(path)}\n{content}\n")
				except Exception as e:
					self.logger.warning(f"读取接口文件失败: {path}, {e}")
			# 未找到接口文件时，回退读取插件源码
			if not interface_paths:
				plugin_code = self._read_plugin_code_for_module(name, max_chars=max_chars_per_file)
				if plugin_code:
					parts.append(f"\n## Plugin Code: {name}\n```python\n{plugin_code}\n```\n")
		return "".join(parts).strip() if parts else "（未找到相关接口文件）"

	def _group_module_params_from_pairs(self, pairs: List[dict]) -> Dict[str, List[str]]:
		"""从 influence pairs 中聚合每个模块出现过的参数描述，保持出现顺序且去重。"""
		grouped: Dict[str, List[str]] = {}
		seen: Dict[str, set] = {}
		for pair in pairs or []:
			if not isinstance(pair, dict):
				continue
			for role in ('cause', 'effect'):
				segment = pair.get(role) or {}
				if not isinstance(segment, dict):
					continue
				module_name = str(segment.get('module') or '').strip()
				param_name = str(segment.get('param') or '').strip()
				if not module_name or not param_name:
					continue
				if module_name not in grouped:
					grouped[module_name] = []
					seen[module_name] = set()
				norm = param_name.lower()
				if norm in seen[module_name]:
					continue
				seen[module_name].add(norm)
				grouped[module_name].append(param_name)
		return grouped

	def _read_plugin_code_for_module(self, module_name: str, max_chars: int = 2200) -> str:
		"""读取 plugins/<module> 下源码片段；优先与模块同名文件。"""
		plugins_root = os.path.join(self._rag_project_root, 'plugins')
		stems = self._candidate_interface_stems(module_name)
		for stem in stems:
			plugin_dir = os.path.join(plugins_root, stem)
			if not os.path.isdir(plugin_dir):
				continue
			try:
				py_files = sorted([f for f in os.listdir(plugin_dir) if f.endswith('.py')])
			except Exception:
				continue
			preferred = f"{stem}.py"
			if preferred in py_files:
				ordered_files = [preferred] + [f for f in py_files if f != preferred]
			else:
				ordered_files = py_files

			parts: List[str] = []
			for fname in ordered_files:
				fpath = os.path.join(plugin_dir, fname)
				try:
					with open(fpath, 'r', encoding='utf-8') as f:
						parts.append(f"# {fname}\n" + f.read())
				except Exception as exc:
					self.logger.warning(f"读取插件文件失败: {fpath}, {exc}")
					continue
				if len('\n\n'.join(parts)) > max_chars:
					break

			if parts:
				chunk = '\n\n'.join(parts)
				if len(chunk) > max_chars:
					chunk = chunk[:max_chars] + "\n...(truncated)"
				return chunk
		return ""

	def _wait_for_user_confirmation(self, step_name):
		"""等待用户确认是否继续"""
		print(f"\n{'='*60}")
		print(f"✓ {step_name} 已完成")
		print(f"{'='*60}")

		# 自动模式下不做交互式确认，直接继续
		if self.auto_mode:
			self.logger.info(f"{step_name} 已完成（自动模式：跳过确认）")
			return
		
		# 如果是Web模式，将输出发送到前端，但不等待确认
		if self.session:
			try:
				# 将输出发送到前端
				if 'output_queue' in self.session:
					self.session['output_queue'].put(f"\n{'='*60}")
					self.session['output_queue'].put(f"✓ {step_name} 已完成")
					self.session['output_queue'].put(f"{'='*60}")
				self.logger.info(f"{step_name} 已完成，继续下一步")
				# Web模式下自动继续，不等待用户确认
				return
			except Exception as e:
				self.logger.warning(f"发送输出到前端失败: {e}")
		
		# 非Web模式，使用命令行确认
		user_input = input("是否继续？(按回车继续/输入'n'退出): ").strip().lower()
		if user_input == 'n':
			self.logger.info("用户选择退出")
			raise KeyboardInterrupt("用户选择退出流程")
		self.logger.info(f"用户确认继续，开始下一步...")

	async def _llm_customize_new_plugin(
		self,
		*,
		plugin_name: str,
		inherits_from: Optional[str],
		notes: str,
		description_md: str,
		plugin_py_path: str,
		plugin_class: str,
	) -> tuple[str, bool]:
		"""让 LLM 基于 notes 对新插件做一次整文件生成，同时返回 description 和代码。

		返回: (description, success)
		"""
		prompt_tmpl = (self.prompts or {}).get("customize_new_plugin_prompt")
		try:
			with open(plugin_py_path, "r", encoding="utf-8") as f:
				current_code = f.read()
		except Exception:
			self.logger.warning(f"LLM 生成：读取插件代码失败 (plugin={plugin_name})")
			return "", False

		base_code = ""
		if inherits_from:
			try:
				base_manifest = self._read_plugin_manifest(inherits_from)
				base_module = str(base_manifest.get("module") or f"{inherits_from}_plugin").strip()
				base_py = os.path.join(self._plugin_dir(inherits_from), f"{base_module}.py")
				if os.path.exists(base_py):
					with open(base_py, "r", encoding="utf-8") as f:
						base_code = f.read()
			except Exception:
				base_code = ""

		def _truncate(text: str, max_chars: int) -> str:
			text = text or ""
			return text if len(text) <= max_chars else (text[:max_chars] + "\n...(truncated)")

		prompt = prompt_tmpl.format(
			plugin_name=plugin_name,
			inherits_from=inherits_from or "null",
			notes=notes.strip(),
			plugin_class=plugin_class,
			description_md=_truncate(description_md, 2000),
			current_code=_truncate(current_code, 2600),
			base_code=_truncate(base_code, 2600),
		)

		self.logger.info(f"开始 LLM 生成新插件: plugin={plugin_name}, inherits_from={inherits_from or 'null'}")
		resp = await self.generate_llm_response(prompt)
		if not resp:
			self.logger.warning(f"LLM 生成无响应: plugin={plugin_name}")
			return "", False

		# 提取 DESCRIPTION
		desc = ""
		m_desc = re.search(r"^DESCRIPTION:\s*(.+)$", resp, re.MULTILINE)
		if m_desc:
			desc = m_desc.group(1).strip()
			self.logger.info(f"LLM 生成 description: {desc[:60]}...")

		# 提取 python 代码块
		m = re.search(r"```python\s*([\s\S]*?)```", resp, re.IGNORECASE)
		if not m:
			m = re.search(r"```\s*([\s\S]*?)```", resp)
		if not m:
			self.logger.warning(f"LLM 生成输出缺少代码块: plugin={plugin_name}")
			return desc, False
		new_code = m.group(1).strip()
		if "class" not in new_code:
			self.logger.warning(f"LLM 生成输出疑似无效（缺少 class）: plugin={plugin_name}")
			return desc, False
		try:
			with open(plugin_py_path, "w", encoding="utf-8") as f:
				f.write(new_code + "\n")
			self.logger.info(f"LLM 生成代码写入成功: {plugin_py_path}")
			return desc, True
		except Exception:
			self.logger.warning(f"LLM 生成代码写入失败: plugin={plugin_name}")
			return desc, False

	async def ensure_new_modules_before_simulator(self, *, description_md: str, modules_config_yaml_full: str) -> List[str]:
		"""在生成 simulator 之前处理 modules_config.yaml 的 new_modules。

		行为：
		- 若 new_modules 为空：什么也不做。
		- 若存在：对每个 new module 调用 LLM 生成 description 和代码，验证通过后注册。

		返回：本次创建/处理的插件名列表。
		"""
		from src.utils import plugin_generator as pg

		created: List[str] = []
		failed: List[tuple[str, Optional[str]]] = []
		modules_config_path = os.path.join(self.config_dir, "modules_config.yaml")
		project_root = pg.project_root_from(self.config_dir)

		specs = pg.parse_new_modules(modules_config_yaml_full)
		if not specs:
			return created

		self.logger.info(f"检测到 new_modules={len(specs)}，开始 LLM 生成...")

		for spec in specs:
			plugin_name = spec.name
			base_name = spec.inherits_from
			notes_str = spec.notes or ""

			# 1) 生成/复制插件骨架（description 后续由 LLM 一并生成）
			try:
				if pg.plugin_exists(project_root, plugin_name):
					manifest = pg.read_yaml_file(pg.plugin_manifest_path(project_root, plugin_name))
				else:
					if base_name and pg.plugin_exists(project_root, base_name):
						manifest = pg.copy_plugin_as_new(
							project_root=project_root,
							new_name=plugin_name,
							base_name=base_name,
						)
					else:
						manifest = pg.create_minimal_plugin_from_template(
							project_root=project_root,
							new_name=plugin_name,
						)
			except Exception as e:
				self.logger.error(f"创建新模块插件失败: {plugin_name}, {e}")
				failed.append((plugin_name, base_name))
				continue

			# 2) LLM 生成 description + 代码（一次调用）
			try:
				plugin_py_path = pg.plugin_module_py_path(project_root, plugin_name, manifest)
				description, ok = await self._llm_customize_new_plugin(
					plugin_name=plugin_name,
					inherits_from=base_name,
					notes=notes_str,
					description_md=description_md,
					plugin_py_path=plugin_py_path,
					plugin_class=manifest.get("plugin_class", ""),
				)
				if not ok:
					self.logger.error(f"LLM 生成失败: {plugin_name}")
					failed.append((plugin_name, base_name))
					continue
				if description:
					manifest["description"] = description
					pg.write_yaml_file(pg.plugin_manifest_path(project_root, plugin_name), manifest)
			except Exception as e:
				self.logger.error(f"LLM 生成异常: {plugin_name}, {e}")
				failed.append((plugin_name, base_name))
				continue

			# 3) 验证（description 准确详细，代码语法正确，依赖存在）
			errors = pg.validate_manifest(manifest, plugin_name)
			errors.extend(pg.validate_plugin_code(project_root, plugin_name, manifest))
			pending = {s.name for s in specs}
			errors.extend(pg.validate_dependencies(project_root, manifest, pending))
			if errors:
				self.logger.error(
					f"插件 '{plugin_name}' 验证失败，未注册:\n" + "\n".join(f"  - {e}" for e in errors)
				)
				failed.append((plugin_name, base_name))
				continue

				# 4) 自动接线：更新 modules_config.yaml 的 selected_modules
				try:
					pg.patch_modules_config_binding(
						modules_config_path=modules_config_path,
						new_plugin_name=plugin_name,
						inherits_from=base_name,
					)
				except Exception as e:
					self.logger.warning(f"更新 modules_config.yaml 绑定失败: {e}")

			created.append(plugin_name)

		# 5) 收尾：全部成功则清空 new_modules；存在失败则回滚 selected_modules 中对失败插件的引用
		try:
			cfg = pg.read_yaml_file(modules_config_path) or {}
			if not isinstance(cfg, dict):
				cfg = {}
			selected = cfg.get("selected_modules")
			if isinstance(selected, list):
				selected_names = [name for name in selected if isinstance(name, str) and name.strip()]
			else:
				selected_names = []
			cfg["selected_modules"] = selected_names

			if failed:
				failed_names = [n for n, _ in failed]
				for plugin_name, base_name in failed:
					if plugin_name in selected_names:
						if base_name and base_name not in selected_names:
							selected_names = [base_name if name == plugin_name else name for name in selected_names]
						else:
							selected_names = [name for name in selected_names if name != plugin_name]
					elif base_name and base_name not in selected_names:
						selected_names.append(base_name)

				cfg["selected_modules"] = selected_names
				pg.write_yaml_file(modules_config_path, cfg)
				self.logger.info(f"new_modules 存在创建失败项，已从 selected_modules 移除/回滚: {', '.join(failed_names)}")
			else:
				cfg["new_modules"] = []
				pg.write_yaml_file(modules_config_path, cfg)
				self.logger.info("new_modules 均创建成功，已清空 new_modules")
		except Exception as e:
			self.logger.warning(f"收尾更新 modules_config.yaml 失败: {e}")

		return created
	
	def _check_file_exists_and_ask(self, file_path, file_description):
		"""检查文件是否存在，如果存在则询问是否重新生成
		
		Args:
			file_path: 文件路径
			file_description: 文件描述（用于显示）
		
		Returns:
			bool: True表示需要生成（不存在或用户选择重新生成），False表示跳过
		"""
		if not os.path.exists(file_path):
			return True  # 文件不存在，需要生成
		
		print(f"\n{'='*60}")
		print(f"发现已存在的文件: {file_description}")
		print(f"路径: {file_path}")
		print(f"{'='*60}")
		
		# 如果是Web模式，通过session发送确认请求
		if self.session:
			try:
				# 发送提示信息到前端
				if 'output_queue' in self.session:
					import time
					from datetime import datetime
					timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
					self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
					self.session['output_queue'].put(f"[{timestamp}] 发现已存在的{file_description}")
					self.session['output_queue'].put(f"[{timestamp}] 路径: {file_path}")
					self.session['output_queue'].put(f"[{timestamp}] {'='*60}")
				
				# 设置等待确认状态
				self.session['waiting_confirmation'] = True
				self.session['confirmation_message'] = f"发现已存在的{file_description}，是否重新生成？"
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
							self.logger.info(f"用户选择重新生成: {file_description}")
							return True
						else:
							self.logger.info(f"跳过生成，使用现有文件: {file_description}")
							if 'output_queue' in self.session:
								timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
								self.session['output_queue'].put(f"[{timestamp}] ✓ 跳过，使用现有文件")
							return False
					time.sleep(0.5)
					wait_time += 0.5
				
				# 超时，默认跳过
				self.logger.warning(f"等待用户确认超时，跳过生成: {file_description}")
				self.session['waiting_confirmation'] = False
				return False
				
			except Exception as e:
				self.logger.warning(f"Web模式确认失败: {e}，使用命令行模式")
		
		# 非Web模式，使用命令行确认
		user_input = input("是否重新生成？(y/yes=重新生成, 其他=跳过使用现有文件): ").strip().lower()
		
		if user_input in ['y', 'yes']:
			self.logger.info(f"用户选择重新生成: {file_description}")
			return True
		else:
			self.logger.info(f"跳过生成，使用现有文件: {file_description}")
			print(f"✓ 跳过，使用现有文件")
			return False

	async def generate_simulator_code(self, description_md, modules_config_yaml, influences_yaml=''):
		"""
		步骤1：生成simulator模拟器主代码（simulator_[模拟名称].py）
		策略：先复制模板文件到目标位置，然后让LLM基于模板进行修改
		输入：设计文档 + 实验模板配置 + 影响函数配置
		参考：根据simulation_type选择模板
		  - decision: src/simulation/simulator_template.py
		  - survey: src/simulation/simulator_survey_template.py

		Args:
			influences_yaml: influences.yaml 内容，作为生成simulator时的重要参考

		Returns:
			tuple: (file_paths, skipped)
				- file_paths: 生成的文件路径列表
				- skipped: 是否跳过了生成（True表示使用现有文件）
		"""
		self.logger.info(f"开始生成simulator代码（类型: {self.simulation_type}）...")
		
		# 目标文件路径
		fname = f'simulator_{self.simulation_name}.py'
		fpath = os.path.join(self.simulator_output_dir, fname)
		
		# 检查文件是否已存在
		if not self._check_file_exists_and_ask(fpath, f"Simulator代码 ({fname})"):
			return ([fpath], True)  # 跳过生成，返回现有文件路径和跳过标记
		
		# 根据模拟类型选择模板文件
		if self.simulation_type == 'survey':
			template_filename = 'simulator_survey_template.py'
		else:
			template_filename = 'simulator_template.py'

		template_path = os.path.join(self._rag_project_root, 'src', 'simulation', template_filename)
		
		if not os.path.exists(template_path):
			self.logger.error(f"模板文件不存在: {template_path}")
			return ([], False)
		
		# 步骤1：复制模板到目标位置
		shutil.copy2(template_path, fpath)
		self.logger.info(f"✓ 已复制模板文件 ({template_filename}) 到: {fpath}")
		
		# 读取模板内容
		with open(template_path, 'r', encoding='utf-8') as f:
			template_content = f.read()

		# 直接替换类名（兼容有/无父类继承的写法）
		simulator_class_name = self.simulation_name.replace('_', ' ').title().replace(' ', '') + 'Simulator'
		if self.simulation_type == 'survey':
			# 交流调查型模板类名是 SurveySimulator
			original_class_name = 'SurveySimulator'
			modified_content = re.sub(
				r'class\s+SurveySimulator\s*(\([^)]*\))?:',
				f'class {simulator_class_name}\\1:',
				template_content,
				count=1,
			)
		else:
			# 决策型模板类名是 YourSimulator
			original_class_name = 'YourSimulator'
			modified_content = re.sub(
				r'class\s+YourSimulator\s*(\([^)]*\))?:',
				f'class {simulator_class_name}\\1:',
				template_content,
				count=1,
			)

		# 去除模板中 BaseSimulator 方法说明注释块（生成代码不需要这些提示）
		modified_content = re.sub(
			r'\n(    |\t)# BaseSimulator 已提供的通用方法.*?(?:\n\1# 如需扩展 collect_results[^\n]*\n)',
			'\n',
			modified_content,
			flags=re.DOTALL,
		)

		# 保存修改后的模板
		with open(fpath, 'w', encoding='utf-8') as f:
			f.write(modified_content)
		self.logger.info(f"✓ 已替换类名: {original_class_name} -> {simulator_class_name}")
		
		# 步骤2：让LLM生成修改方案（JSON格式）
		prompt = self.prompts['generate_simulator_code_prompt'].format(
			template_content=template_content,
			description_md=description_md,
			modules_config_yaml=modules_config_yaml,
			influences_yaml=influences_yaml or "（未提供影响函数配置）",
			simulator_class_name=simulator_class_name
		)
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return ([], False)
		
		# 步骤3：应用修改到已复制的文件
		if not self._apply_code_changes(fpath, response, "simulator"):
			self.logger.error("应用修改失败")
			return ([], False)

		# 步骤3.5：自动校验并补全 results 结构一致性
		self._auto_fix_results_schema(fpath)

		# 等待用户确认
		self._wait_for_user_confirmation("生成simulator代码")
		
		return ([fpath], False)  # 返回文件路径和未跳过标记

	async def generate_main_file(self, description_md, simulator_file_path):
		"""
		步骤3：生成main入口文件（main_[模拟名称].py）
		策略：直接生成完整文件，不使用增量修改
		输入：设计文档 + 已生成的simulator文件路径
		参考：根据simulation_type选择模板
		  - decision: entrypoints/main_template.py
		  - survey: entrypoints/main_survey_template.py
		
		Returns:
			tuple: (file_paths, skipped)
				- file_paths: 生成的文件路径列表
				- skipped: 是否跳过了生成（True表示使用现有文件）
		"""
		self.logger.info(f"开始生成main入口文件（类型: {self.simulation_type}）...")
		
		# 目标文件路径
		fname = f'main_{self.simulation_name}.py'
		fpath = os.path.join(self.main_output_dir, fname)
		
		# 检查文件是否已存在
		if not self._check_file_exists_and_ask(fpath, f"Main入口文件 ({fname})"):
			return ([fpath], True)  # 跳过生成，返回现有文件路径和跳过标记
		
		# 根据模拟类型选择模板文件
		if self.simulation_type == 'survey':
			template_filename = 'main_survey_template.py'
		else:
			template_filename = 'main_template.py'

		template_path = os.path.join(self._rag_project_root, 'entrypoints', template_filename)
		
		if not os.path.exists(template_path):
			self.logger.error(f"模板文件不存在: {template_path}")
			return ([], False)
		
		# 读取模板内容
		with open(template_path, 'r', encoding='utf-8') as f:
			template_content = f.read()
		
		# 读取已生成的simulator代码
		simulator_content = ""
		if os.path.exists(simulator_file_path):
			with open(simulator_file_path, 'r', encoding='utf-8') as f:
				simulator_content = f.read()
		
		# 让LLM生成完整的main文件
		prompt = self.prompts['generate_main_file_prompt'].format(
			template_content=template_content,
			simulator_content=simulator_content,
			simulation_name=self.simulation_name
		)
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return ([], False)
		
		# 提取代码块并保存
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		if not code_blocks:
			self.logger.error("未找到代码块")
			return ([], False)
		
		code = code_blocks[0].strip()
		
		# 验证代码完整性（必须包含入口部分）
		if 'if __name__ == "__main__"' not in code:
			self.logger.error("⚠️ 生成的代码缺少入口部分，尝试从模板补充...")
			# 从模板提取入口部分
			entry_match = re.search(r'(# ===== 以下代码块不可删除或修改 =====[\s\S]*)', template_content)
			if entry_match:
				code = code + '\n\n' + entry_match.group(1)
				self.logger.info("✓ 已自动补充入口部分")
		
		# 保存文件
		with open(fpath, 'w', encoding='utf-8') as f:
			f.write(code)
		
		self.logger.info(f"✓ 已生成main文件: {fpath}")
		
		# 等待用户确认
		self._wait_for_user_confirmation("生成main入口文件")
		
		return ([fpath], False)  # 返回文件路径和未跳过标记

	async def refine_simulator_functions(self, simulator_file_path, description_md, modules_config_yaml, influences_file_path=None):
		"""
		步骤2：基于模块配置完善simulator文件（循环重试版本）
		分为三个子步骤，每个步骤都有重试机制：
		2.1 创建工作列表 - 从modules_config.yaml提取选定的模块（最多5次重试）
		2.2 逐个完善模块 - 根据每个模块的接口文件完善相关代码（每个模块最多5次重试）
		2.3 总体检查与修复 - 检查问题并自动修复（最多2次重试）
		"""
		# self.logger.info("=== 步骤2: 开始基于模块配置完善simulator ===")
		
		# 读取已生成的simulator代码
		if not os.path.exists(simulator_file_path):
			self.logger.error(f"Simulator文件不存在: {simulator_file_path}")
			return {'status': 'abort', 'files': []}
		
		# ============ 步骤2.1: 创建工作列表（循环重试） ============
		self.logger.info("步骤2.1: 从模块配置创建工作列表...")
		todo_list = None
		for attempt in range(1, self.MAX_RETRY_ATTEMPTS + 1):
			self.logger.info(f"  尝试 [{attempt}/{self.MAX_RETRY_ATTEMPTS}] 创建工作列表...")
			todo_list = await self._create_simulator_todo_list(modules_config_yaml, description_md)
			if todo_list is not None:
				break
			self.logger.warning(f"⚠️ 第 {attempt} 次创建工作列表失败")

		if todo_list is None:
			action = await self._ask_user_retry_action("创建模块工作列表", simulator_file_path)
			if action == 'abort':
				self.logger.error("❌ 用户选择放弃创建工作列表")
				return {'status': 'abort', 'files': []}
			# retry 或 regenerate：额外再试一次
			todo_list = await self._create_simulator_todo_list(modules_config_yaml, description_md)
			if todo_list is None:
				self.logger.error("❌ 额外尝试后仍无法创建工作列表")
				return {'status': 'abort', 'files': []}
		if len(todo_list) == 0:
			self.logger.info("✓ 未发现需要完善的模块，代码已完整")
		else:
			self.logger.info(f"✓ 成功创建工作列表（共 {len(todo_list)} 个模块）")
		
		if not todo_list:
			return {'status': 'success', 'files': [simulator_file_path]}  # 代码已完整
		
		# 显示工作列表
		self.logger.info(f"\n{'='*60}")
		self.logger.info(f"📋 模块工作列表（共 {len(todo_list)} 个模块）:")
		for idx, item in enumerate(todo_list, 1):
			self.logger.info(f"  {idx}. {item['module_name']} - {item.get('display_name', '')}")
			self.logger.info(f"     说明: {item.get('description', '')}")
		self.logger.info(f"{'='*60}\n")
		
		# ============ 步骤2.2: 逐个完善模块（每个模块循环重试） ============
		self.logger.info("步骤2.2: 逐个根据接口文件完善模块...")
		for idx, todo_item in enumerate(todo_list, 1):
			module_name = todo_item['module_name']
			self.logger.info(f"\n处理模块 [{idx}/{len(todo_list)}]: {module_name}")

			# 对每个模块进行循环重试
			success = False
			for attempt in range(1, self.MAX_RETRY_ATTEMPTS + 1):
				self.logger.info(f"  尝试 [{attempt}/{self.MAX_RETRY_ATTEMPTS}] 完善模块 {module_name}...")
				success = await self._complete_simulator_function(
					simulator_file_path,
					todo_item,
					description_md
				)
				if success:
					break
				self.logger.warning(f"⚠️ 第 {attempt} 次完善失败")

			if not success:
				action = await self._ask_user_retry_action(
					f"完善模块 {module_name}", simulator_file_path
				)
				if action == 'abort':
					self.logger.error(f"❌ 用户选择放弃模块 {module_name}，跳过")
				else:
					# retry 或 regenerate：额外再试一次
					success = await self._complete_simulator_function(
						simulator_file_path, todo_item, description_md
					)
					if success:
						self.logger.info(f"✓ 额外尝试后成功完善模块: {module_name}")
					else:
						self.logger.error(f"❌ 额外尝试后仍无法完善模块 {module_name}，跳过")

		# ============ 步骤2.25: 基于 influences.yaml 的参数存在性检查 ============
		if influences_file_path and os.path.exists(influences_file_path):
			self.logger.info("\n步骤2.25: 基于 influences.yaml 检查参数定义...")
			await self.check_simulator_with_influences(simulator_file_path, influences_file_path)
		else:
			self.logger.info("\n步骤2.25: 未提供 influences.yaml，跳过参数存在性检查")

		# ============ 步骤2.3: 总体检查与修复（循环重试） ============
		self.logger.info("\n步骤2.3: 总体检查与修复...")
		issues = []
		for attempt in range(1, self.MAX_FIX_ATTEMPTS + 1):
			self.logger.info(f"第 {attempt}/{self.MAX_FIX_ATTEMPTS} 次总体检查...")

			issues = await self._check_and_fix_code(simulator_file_path, description_md, modules_config_yaml, "simulator")

			if not issues:
				self.logger.info("✓ Simulator代码完整无误")
				return {'status': 'success', 'files': [simulator_file_path]}
			self.logger.warning(f"发现 {len(issues)} 个问题: {issues[:3]}...")  # 只显示前3个
			if attempt < self.MAX_FIX_ATTEMPTS:
				self.logger.info("尝试自动修复...")

		if issues:
			action = await self._ask_user_retry_action("总体检查与修复", simulator_file_path)
			if action == 'abort':
				self.logger.error("❌ 用户选择放弃总体检查")
			elif action == 'regenerate':
				self.logger.info("用户选择重新生成 simulator，结束当前完善阶段...")
				return {'status': 'regenerate', 'files': [simulator_file_path]}
			else:  # retry
				self.logger.info("额外尝试一次总体检查...")
				issues = await self._check_and_fix_code(simulator_file_path, description_md, modules_config_yaml, "simulator")
				if not issues:
					self.logger.info("✓ 额外尝试后代码完整无误")
					return {'status': 'success', 'files': [simulator_file_path]}
				self.logger.error("❌ 额外尝试后仍有问题")
		
		# 等待用户确认
		self._wait_for_user_confirmation("完善simulator函数")

		return {'status': 'success', 'files': [simulator_file_path]}

	async def check_simulator_with_influences(self, simulator_file_path, influences_file_path):
		"""
		基于 influences.yaml 检查 simulator 代码合规性，并同步修改 influences.yaml。
		在 refine_simulator_functions 的总体检查之前调用，确保 simulator 逻辑与影响对约束严格对齐。
		"""
		self.logger.info("=== 基于 influences.yaml 检查 simulator 代码并同步对齐 ===")

		if not os.path.exists(simulator_file_path):
			self.logger.error(f"Simulator文件不存在: {simulator_file_path}")
			return False

		if not influences_file_path or not os.path.exists(influences_file_path):
			self.logger.info("influences.yaml 路径不存在，跳过检查")
			return True

		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			simulator_content = f.read()

		with open(influences_file_path, 'r', encoding='utf-8') as f:
			influences_yaml = f.read()

		if not influences_yaml.strip():
			self.logger.info("influences.yaml 为空，跳过检查")
			return True

		prompt = self.prompts.get('check_simulator_with_influences_prompt')
		if not prompt:
			self.logger.warning("未找到 check_simulator_with_influences_prompt，跳过检查")
			return True

		prompt = prompt.format(
			influences_yaml=influences_yaml,
			simulator_content=simulator_content
		)

		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.warning("LLM返回空响应，跳过检查")
			return True

		if 'OK' in response.upper():
			self.logger.info("✓ simulator 代码与 influences.yaml 已通过约束检查")
			return True

		# 解析JSON响应并分别应用simulator和influences.yaml修改
		json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
		if not json_match:
			self.logger.warning("⚠️ 无法从响应中解析JSON修改，尝试直接应用simulator修改")
			return self._apply_code_changes(simulator_file_path, response, "simulator")

		try:
			changes = json.loads(json_match.group(1))
		except json.JSONDecodeError as e:
			self.logger.warning(f"JSON解析失败: {e}，尝试直接应用simulator修改")
			return self._apply_code_changes(simulator_file_path, response, "simulator")

		# 应用simulator增量修改
		simulator_changes = {k: v for k, v in changes.items() if k in ('methods', 'delete_methods')}
		if simulator_changes:
			success_sim = self._apply_incremental_changes(simulator_file_path, simulator_changes, "simulator")
		else:
			success_sim = True

		# 同步应用influences.yaml修改
		influences_yaml_content = changes.get('influences_yaml')
		if influences_yaml_content:
			try:
				with open(influences_file_path, 'w', encoding='utf-8') as f:
					f.write(influences_yaml_content)
				self.logger.info(f"✓ 已同步更新 influences.yaml: {influences_file_path}")
				success_inf = True
			except Exception as e:
				self.logger.error(f"❌ 更新 influences.yaml 失败: {e}")
				success_inf = False
		else:
			success_inf = True

		return success_sim and success_inf

	async def _create_simulator_todo_list(self, modules_config_yaml, description_md):
		"""
		步骤2.1: 创建simulator的工作列表（基于模块配置）
		从 modules_config.yaml 中提取所有选定的模块。
		"""
		import yaml
		try:
			modules_config = yaml.safe_load(modules_config_yaml) or {}
		except Exception as e:
			self.logger.error(f"解析 modules_config.yaml 失败: {e}")
			return []

		selected_modules = modules_config.get("selected_modules", [])
		if not isinstance(selected_modules, list):
			self.logger.warning("modules_config.yaml 中 selected_modules 不是列表")
			return []

		todo_list = [
			{
				"module_name": name,
				"display_name": name,
				"description": "",
			}
			for name in selected_modules
			if isinstance(name, str) and name.strip()
		]

		self.logger.info(f"从 modules_config.yaml 识别出 {len(todo_list)} 个需要完善的模块")
		for item in todo_list:
			self.logger.info(f"  - {item['module_name']} ({item['display_name']})")

		return todo_list

	async def _complete_simulator_function(self, simulator_file_path, todo_item, description_md):
		"""
		步骤2.2: 根据模块接口文件完善simulator代码（增量修改版）
		只修改需要改动的方法，而不是替换整个文件
		"""
		module_name = todo_item['module_name']
		module_display_name = todo_item.get('display_name', module_name)
		# 接口文件由系统根据 module_name 从 src/interfaces/ 自动检索
		
		# 读取当前simulator代码
		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			simulator_content = f.read()
		
		# 读取接口文件（src/interfaces）
		interface_docs = self._read_interface_docs_for_modules([module_name])
		if not interface_docs or interface_docs.strip() == "（未找到相关接口文件）":
			self.logger.warning(f"未找到模块 {module_name} 的接口文件，将继续尝试基于现有代码与设计文档修复")

		# 精简设计文档：只取 ## 1. 基本信息 部分，上限 500 字
		import re
		_m = re.search(r"## 1\. 基本信息[\s\S]*?(?=## |\Z)", description_md)
		doc_trimmed = _m.group()[:500] if _m else description_md[:500]
		prompt = self.prompts["refine_simulator_with_module_prompt"].format(
			simulator_content=simulator_content,
			interface_docs=interface_docs,
			description_md=doc_trimmed
		)

		response = await self.generate_llm_response(prompt)
		if not response:
			return False
		elif "OK" in response:
			self.logger.info(f"模块 {module_name} 已完整，无需修改")
			return True
		# self.logger.info(f"LLM返回的响应: {response}")
		
		# 应用修改
		if self._apply_code_changes(simulator_file_path, response, "simulator"):
			return True
		else:
			return False

	def _apply_code_changes(self, file_path, llm_response, file_type="simulator", allow_add_new=True):
		"""
		应用代码修改（统一处理LLM响应的增量修改方式）

		Args:
			file_path: 文件路径
			llm_response: LLM返回的响应（可以是JSON格式的修改，也可以是完整代码）
			file_type: 文件类型（"simulator" 或 "main"）
			allow_add_new: 是否允许新增方法/函数（语法修复等场景应设为 False，防止臆造）

		Returns:
			bool: 是否成功应用修改
		"""
		
		# 策略1: 尝试提取JSON格式的增量修改
		json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', llm_response, re.DOTALL)
		if not json_match:
			if file_type == "main":
				json_match = re.search(r'\{[\s\S]*"functions"[\s\S]*\}', llm_response, re.DOTALL)
			else:
				json_match = re.search(r'\{[\s\S]*"methods"[\s\S]*\}', llm_response, re.DOTALL)
		
		if json_match:
			json_str = json_match.group(1) if json_match.lastindex else json_match.group(0)
			try:
				changes = json.loads(json_str)
				
				# 应用JSON格式的增量修改
				if self._apply_incremental_changes(file_path, changes, file_type, allow_add_new=allow_add_new):
					self.logger.info(f"✓ 已基于JSON增量修改并保存: {file_path}")
					return True
				else:
					self.logger.warning("JSON增量修改失败，尝试完整替换")
			except json.JSONDecodeError as e:
				self.logger.warning(f"JSON解析失败: {e}，尝试提取部分完整的函数/方法...")
				# 尝试提取部分完整的JSON内容
				partial_changes = self._extract_partial_json(json_str, file_type)
				if partial_changes:
					self.logger.info(f"成功提取 {len(partial_changes.get('methods' if file_type == 'simulator' else 'functions', []))} 个完整的{'方法' if file_type == 'simulator' else '函数'}")
					if self._apply_incremental_changes(file_path, partial_changes, file_type, allow_add_new=allow_add_new):
						self.logger.info(f"✓ 已基于部分JSON增量修改并保存: {file_path}")
						return True
					else:
						self.logger.warning("部分JSON增量修改失败")
				else:
					self.logger.warning("部分提取也失败，尝试从响应文本恢复方法/函数代码...")
					recovered_changes = self._extract_items_from_malformed_response(llm_response, file_type)
					if recovered_changes:
						recovered_count = len(recovered_changes.get('methods' if file_type == 'simulator' else 'functions', []))
						self.logger.info(f"成功从响应文本恢复 {recovered_count} 个{'方法' if file_type == 'simulator' else '函数'}")
						if self._apply_incremental_changes(file_path, recovered_changes, file_type, allow_add_new=allow_add_new):
							self.logger.info(f"✓ 已基于恢复的增量修改并保存: {file_path}")
							return True
						self.logger.warning("恢复后的增量修改应用失败")
		
		# 所有增量修改策略都失败，直接报错
		self.logger.error("❌ 未找到有效的JSON增量修改内容，拒绝进行完整文件替换")
		self.logger.error(f"大模型返回内容（前500字符）：{llm_response[:500]}...")
		return False

	def _extract_items_from_malformed_response(self, llm_response, file_type="simulator"):
		"""当LLM返回的JSON格式损坏时，尝试直接从文本中恢复方法/函数代码。"""
		item_key = 'methods' if file_type == 'simulator' else 'functions'
		name_key = 'method_name' if file_type == 'simulator' else 'function_name'
		code_key = 'method_code' if file_type == 'simulator' else 'function_code'

		if not llm_response:
			return None

		# 将常见转义恢复为文本，便于匹配 def/async def。
		text = llm_response.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '    ').replace('\\"', '"')

		name_pattern = rf'"{name_key}"\s*:\s*"([^"]+)"'
		names = re.findall(name_pattern, text)
		if not names:
			return None

		items = []
		for raw_name in names:
			name = raw_name.strip()
			if not name:
				continue

			def_header = re.search(rf'(?:async\s+def|def)\s+{re.escape(name)}\s*\(', text)
			if not def_header:
				continue

			start = def_header.start()
			next_def = re.search(r'\n\s*(?:async\s+def|def)\s+\w+\s*\(', text[start + 1:])
			next_desc = re.search(r'\n\s*"description"\s*:', text[start + 1:])

			end_candidates = []
			if next_def:
				end_candidates.append(start + 1 + next_def.start())
			if next_desc:
				end_candidates.append(start + 1 + next_desc.start())
			end = min(end_candidates) if end_candidates else len(text)

			code = text[start:end].strip()
			code = code.rstrip('"').rstrip(',').rstrip()
			if not re.match(r'^(async\s+def|def)\s+', code):
				continue

			items.append({
				name_key: name,
				code_key: code,
				"description": "从损坏JSON响应自动恢复",
			})

		if not items:
			return None

		return {item_key: items}
	
	def _verify_and_fix_final_indentation(self, file_path, file_type):
		"""
		验证并修正最终文件的缩进
		"""
		if file_type != "simulator":
			return
			
		with open(file_path, 'r', encoding='utf-8') as f:
			content = f.read()
		
		# 检查是否有缩进问题
		lines = content.split('\n')
		has_issue = False
		
		for i, line in enumerate(lines):
			stripped = line.strip()
			if stripped.startswith(('def ', 'async def ')):
				# 检查函数缩进
				indent = len(line) - len(line.lstrip())
				if indent != 4:
					has_issue = True
					break
		
		if has_issue:
			self.logger.warning("检测到缩进问题，重新修正...")
			fixed_content = self._fix_indentation_and_whitespace(content)
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(fixed_content)

	def _extract_partial_json(self, json_str, file_type="simulator"):
		"""
		从不完整的JSON字符串中提取完整的函数/方法定义
		
		Args:
			json_str: 不完整的JSON字符串
			file_type: 文件类型（"simulator" 或 "main"）
		
		Returns:
			dict: 包含完整函数/方法的字典，格式为 {"methods": [...]} 或 {"functions": [...]}
				  如果无法提取任何完整内容，返回None
		"""
		item_key = 'methods' if file_type == 'simulator' else 'functions'
		name_key = 'method_name' if file_type == 'simulator' else 'function_name'
		code_key = 'method_code' if file_type == 'simulator' else 'function_code'
		
		self.logger.info(f"尝试从不完整的JSON中提取完整的{item_key}...")
		
		complete_items = []
		
		# 使用更安全的方法：手动查找 { 和配对的 }
		i = 0
		while i < len(json_str):
			# 查找对象开始标记
			if json_str[i] == '{':
				# 尝试找到配对的 }
				brace_count = 1
				j = i + 1
				in_string = False
				escape_next = False
				
				while j < len(json_str) and brace_count > 0:
					if escape_next:
						escape_next = False
						j += 1
						continue
					
					if json_str[j] == '\\':
						escape_next = True
					elif json_str[j] == '"' and not escape_next:
						in_string = not in_string
					elif not in_string:
						if json_str[j] == '{':
							brace_count += 1
						elif json_str[j] == '}':
							brace_count -= 1
					
					j += 1
				
				# 如果找到了配对的 }，尝试解析这个对象
				if brace_count == 0:
					item_json = json_str[i:j]
					try:
						item = json.loads(item_json)
						# 验证是否包含必要字段
						if isinstance(item, dict) and name_key in item and code_key in item:
							complete_items.append(item)
							self.logger.info(f"✓ 提取到完整的{item_key[:-1]}: {item[name_key]}")
					except json.JSONDecodeError:
						pass  # 跳过无效的 JSON 对象
					
					i = j  # 继续从下一个位置查找
				else:
					i += 1  # 没找到配对，移动到下一个字符
			else:
				i += 1

		if complete_items:
			self.logger.info(f"共提取到 {len(complete_items)} 个完整的{item_key}")
			return {item_key: complete_items}
		else:
			self.logger.warning(f"未能从JSON中提取任何完整的{item_key}")
			return None

	def _apply_incremental_changes(self, file_path, changes, file_type="simulator", allow_add_new=True):
		"""
		应用增量修改（内部方法，处理JSON格式的修改）

		Args:
			file_path: 文件路径
			changes: JSON格式的修改内容（dict，包含methods/functions和delete_methods/delete_functions）
			file_type: 文件类型（"simulator" 或 "main"）
			allow_add_new: 是否允许新增方法/函数（语法修复等场景应设为 False）

		Returns:
			bool: 是否成功应用修改
		"""
		try:
			# 读取当前文件内容
			with open(file_path, 'r', encoding='utf-8') as f:
				current_content = f.read()
			
			# main文件使用functions，simulator文件使用methods
			code_items = changes.get('functions' if file_type == "main" else 'methods', [])
			delete_items = changes.get('delete_functions' if file_type == "main" else 'delete_methods', [])
			if not code_items and not delete_items:
				self.logger.info(f"无需修改")
				return True
			
			print(f"开始应用增量修改，待处理 {len(code_items)} 个更新，{len(delete_items)} 个删除。")
			modified_content = current_content
			
			# ===== 步骤1: 删除不需要的函数/方法 =====
			if delete_items:
				self.logger.info(f"准备删除 {len(delete_items)} 个{'方法' if file_type == 'simulator' else '函数'}")
				for item_name in delete_items:
					# 提取纯函数名
					pure_name = item_name
					if 'def ' in item_name:
						name_match = re.search(r'def\s+(\w+)', item_name)
						if name_match:
							pure_name = name_match.group(1)

					# 保护核心方法不被删除（防止LLM误删导致模拟器骨架崩溃）
					if file_type == "simulator" and pure_name in {
						'__init__', 'run', 'update_state', 'execute_actions',
						'collect_results', 'save_results', 'init_results'
					}:
						self.logger.warning(f"⚠️ 拒绝删除受保护的核心方法: {pure_name}")
						continue

					# 匹配函数/方法定义并删除
					# 对于main文件，需要在入口标记前停止匹配
					if file_type == "main":
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\n#\s*=====\s*以下代码块不可删除或修改\s*=====|\Z)"
					else:
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\Z)"
					match = re.search(pattern, modified_content, re.DOTALL)
					
					deleted_count = 0
					# 循环删除所有匹配的同名方法/函数（处理重复定义的情况）
					while True:
						match = re.search(pattern, modified_content, re.DOTALL)
						if not match:
							break
						# 删除匹配的函数/方法（包括前导空白行）
						start_pos = match.start()
						end_pos = match.end()

						# 删除多余前导空行，但保留至少1个空行
						while start_pos > 1 and modified_content[start_pos-1] == '\n' and modified_content[start_pos-2] == '\n':
							start_pos -= 1

						modified_content = modified_content[:start_pos] + modified_content[end_pos:]
						deleted_count += 1

					if deleted_count > 0:
						self.logger.info(f"✓ 已删除{'方法' if file_type == 'simulator' else '函数'}: {pure_name} (共 {deleted_count} 个)")
					else:
						self.logger.warning(f"⚠️ 未找到要删除的{'方法' if file_type == 'simulator' else '函数'}: {pure_name}")
			
			# 用于收集需要添加的新方法
			methods_to_add = []
			
			# 替换或添加方法/函数
			for item_info in code_items:
				item_name = item_info.get('method_name') or item_info.get('function_name')
				item_code = item_info.get('method_code') or item_info.get('function_code')
				description = item_info.get('description', '')
				# 关键修复：将字面的\n转换为真正的换行符
				if isinstance(item_code, str):
					# 如果代码中包含字面的 \n，将其替换为真正的换行符
					item_code = item_code.replace('\\n', '\n')
				
				# 从可能包含完整签名的 item_name 中提取纯函数名
				# 例如: "async def update_state(self):" -> "update_state"
				# 或: "update_state" -> "update_state"
				pure_name = item_name
				if 'def ' in item_name:
					# 匹配 def 或 async def 后面的函数名
					name_match = re.search(r'def\s+(\w+)', item_name)
					if name_match:
						pure_name = name_match.group(1)
				
				self.logger.info(f"{'修改' if file_type == 'simulator' else '处理'}{'方法' if file_type == 'simulator' else '函数'}: {pure_name} - {description}")
				
				# 查找并替换方法/函数（缩进感知，避免嵌套函数干扰边界）
				# 步骤1: 匹配方法头
				header_pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):"
				header_match = re.search(header_pattern, modified_content)
				match_start = match_end = None
				full_prefix = None

				if header_match:
					full_prefix = header_match.group(1)
					indent_target = full_prefix.split('\n')[-1]
					# 步骤2: 从方法头之后搜索下一个相同缩进级别的方法边界
					# 这样嵌套函数（更大缩进）不会被误当作当前方法的边界
					rest = modified_content[header_match.end():]
					if file_type == "main":
						boundary_pattern = rf"\n{re.escape(indent_target)}(?:async\s+)?def\s|\n{re.escape(indent_target)}@|\nclass\s|\n#\s*=====\s*以下代码块不可删除或修改\s*=====|\Z"
					else:
						boundary_pattern = rf"\n{re.escape(indent_target)}(?:async\s+)?def\s|\n{re.escape(indent_target)}@|\nclass\s|\Z"
					boundary_match = re.search(boundary_pattern, rest)
					if boundary_match:
						match_end = header_match.end() + boundary_match.start()
					else:
						match_end = len(modified_content)
					match_start = header_match.start()

				if match_start is not None:
					# 找到了，替换现有方法
					# indent_target 已在上方计算
					# 保留换行前缀，规范为最多1个空行（防止函数粘在一起）
					newline_prefix = full_prefix[:len(full_prefix) - len(indent_target)]
					if newline_prefix.count('\n') > 2:
						newline_prefix = '\n\n'
					elif newline_prefix:
						newline_prefix = '\n'
					code_lines = item_code.split('\n')

					# 计算 LLM 代码的公共前导缩进，避免双重缩进
					non_empty = [ln for ln in code_lines if ln.strip()]
					if non_empty:
						min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
					else:
						min_indent = 0

					# 整体平移：去掉公共缩进，再加上目标缩进
					indented_lines = []
					for line in code_lines:
						if line.strip():
							indented_lines.append(indent_target + line[min_indent:])
						else:
							indented_lines.append('')
					indented_code = '\n'.join(indented_lines)

					# 替换方法/函数（显式保留换行前缀，避免 match.start() 吞掉换行后函数粘在一起）
					modified_content = modified_content[:match_start] + newline_prefix + indented_code + modified_content[match_end:]
					self.logger.info(f"✓ 已替换{'方法' if file_type == 'simulator' else '函数'}: {pure_name}")
				else:
					if not allow_add_new:
						# 语法修复等场景不允许新增方法，避免 LLM 认错方法后污染文件
						self.logger.error(
							f"❌ {file_type} 修复模式下不允许新增{'方法' if file_type == 'simulator' else '函数'}: {pure_name}，跳过"
						)
						continue
					# 未找到，标记为需要添加
					self.logger.info(f"→ 方法 {pure_name} 不存在，将作为新方法添加")
					methods_to_add.append({
						'name': pure_name,
						'code': item_code,
						'description': description
					})
			
			# 添加新方法到类的末尾
			if methods_to_add:
				# 查找类定义的结束位置
				if file_type == "simulator":
					# 对于simulator，找到类的最后一个方法后添加
					# 匹配类定义中的最后一个完整方法
					class_pattern = r'class\s+\w+.*?(?=\nclass\s|\Z)'
					class_match = re.search(class_pattern, modified_content, re.DOTALL)
					
					if class_match:
						class_content = class_match.group(0)
						# 找到类中最后一个方法的结束位置
						# 方法通常以 4 个空格或 1 个 tab 缩进
						last_method_pattern = r'(\s{4}|\t)(?:async\s+)?def\s+\w+.*?(?=\n(?:\s{4}|\t)(?:async\s+)?def\s|\n(?:\s{0,3})\S|\Z)'
						all_methods = list(re.finditer(last_method_pattern, class_content, re.DOTALL))
						
						if all_methods:
							last_method = all_methods[-1]
							# 在最后一个方法后添加新方法
							insert_pos = class_match.start() + last_method.end()
							
							# 确定缩进（使用类中现有方法的缩进）
							indent = '    '  # 默认4个空格
							
							# 构建要添加的代码
							new_methods_code = ""
							for method_info in methods_to_add:
								# 添加空行分隔
								new_methods_code += "\n\n"
								# 添加方法代码，计算公共缩进后平移
								lines = method_info['code'].split('\n')
								non_empty = [ln for ln in lines if ln.strip()]
								if non_empty:
									min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
								else:
									min_indent = 0
								for line in lines:
									if line.strip():
										new_methods_code += indent + line[min_indent:] + '\n'
									else:
										new_methods_code += '\n'

								self.logger.info(f"✓ 已添加新方法: {method_info['name']} - {method_info['description']}")
							
							# 插入新方法
							modified_content = modified_content[:insert_pos] + new_methods_code + modified_content[insert_pos:]
						else:
							self.logger.warning("⚠️ 无法找到类中的方法位置，无法添加新方法")
					else:
						self.logger.warning("⚠️ 无法找到类定义，无法添加新方法")
				else:
					# 对于main文件，添加到文件末尾（入口代码之前）
					entry_match = re.search(r'(# ===== 以下代码块不可删除或修改 =====)', modified_content)
					if entry_match:
						insert_pos = entry_match.start()
						# 确保在入口标记前保留适当的空行
						new_functions_code = ""
						for func_info in methods_to_add:
							new_functions_code += "\n\n" + func_info['code']
							self.logger.info(f"✓ 已添加新函数: {func_info['name']} - {func_info['description']}")
						# 在新函数和入口标记之间添加空行
						new_functions_code += "\n\n"
						modified_content = modified_content[:insert_pos] + new_functions_code + modified_content[insert_pos:]
					else:
						# 如果没有入口标记，添加到文件末尾
						insert_pos = len(modified_content)
						new_functions_code = ""
						for func_info in methods_to_add:
							new_functions_code += "\n\n" + func_info['code'] + "\n"
							self.logger.info(f"✓ 已添加新函数: {func_info['name']} - {func_info['description']}")
						
						modified_content = modified_content[:insert_pos] + new_functions_code + modified_content[insert_pos:]
			
			# 清理多余的连续空白行（保留最多2个空行，即最多1个空行）
			modified_content = re.sub(r'\n{4,}', '\n\n\n', modified_content)
			
			# 对于simulator文件，进行缩进和空白行修正
			if file_type == "simulator":
				modified_content = self._fix_indentation_and_whitespace(modified_content)
				self.logger.info("✓ 已对simulator代码进行缩进和空白行修正")

			# 保存修改后的代码
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(modified_content)

			# 对于simulator文件，验证并修正最终缩进
			if file_type == "simulator":
				self._verify_and_fix_final_indentation(file_path, file_type)
			
			# 统计信息
			replaced_count = len(code_items) - len(methods_to_add)
			added_count = len(methods_to_add)
			deleted_count = len(delete_items) if delete_items else 0
			self.logger.info(f"✓ 已应用增量修改")
			if replaced_count > 0:
				self.logger.info(f"  - 替换{'方法' if file_type == 'simulator' else '函数'}: {replaced_count} 个")
			if added_count > 0:
				self.logger.info(f"  - 新增{'方法' if file_type == 'simulator' else '函数'}: {added_count} 个")
			if deleted_count > 0:
				self.logger.info(f"  - 删除{'方法' if file_type == 'simulator' else '函数'}: {deleted_count} 个")

			# 硬性 py_compile 语法检查（每次修改后必须通过）
			import py_compile
			try:
				py_compile.compile(file_path, doraise=True)
				self.logger.info(f"✓ py_compile 语法检查通过")
			except py_compile.PyCompileError as e:
				# 尝试修正后重试一次
				self.logger.warning(f"⚠️ py_compile 语法错误: {e}，尝试硬性修正...")
				with open(file_path, 'r', encoding='utf-8') as f:
					raw = f.read()
				fixed = self._fix_indentation_and_whitespace(raw)
				with open(file_path, 'w', encoding='utf-8') as f:
					f.write(fixed)
				try:
					py_compile.compile(file_path, doraise=True)
					self.logger.info(f"✓ py_compile 语法检查通过（修正后）")
				except py_compile.PyCompileError as e2:
					self.logger.error(f"❌ py_compile 语法错误（修正后仍失败）: {e2}")
					return False

			return True			
		except Exception as e:
			self.logger.error(f"应用增量修改失败: {e}")
			return False

	def _fix_indentation_and_whitespace(self, code_content):
		"""
		硬性修正代码缩进和空白行问题

		主要处理：
		1. 将tab统一替换为4个空格
		2. 清理多余的连续空白行（全局压缩）
		3. class 定义后空行规范化
		注意：不再强制修改 def 行缩进，避免破坏 main 文件的顶层函数和嵌套函数结构

		Args:
			code_content: 原始代码内容

		Returns:
			str: 修正后的代码内容
		"""
		# 将tab替换为4个空格
		code = code_content.replace('\t', '    ')

		# 清理只包含空格的行（变为真正空行，防止 IndentationError）
		lines = code.split('\n')
		lines = [line if line.strip() else '' for line in lines]
		code = '\n'.join(lines)

		# 注意：不再强制将所有 def 行缩进为4个空格。
		# 原因：main 文件中的 run_simulation 是顶层函数（0缩进），
		# 内部嵌套的 build_new_simulator 是 8 缩进，强制 4 空格会破坏正确结构。
		# 真正的缩进缺失问题（如 expected an indented block）由 _auto_fix_syntax_error 处理。
		# tab 转空格已在上文完成，可解决绝大多数缩进不一致问题。

		# 全局清理：任何2个及以上连续空行（\n{3,} = 3个及以上换行符）压缩为1个空行
		code = re.sub(r'\n{3,}', '\n\n', code)

		# class 定义后面最多留1个空行（避免class和后续内容之间出现大片空白）
		code = re.sub(r'(class\s+\w+[^:]*:)\n{2,}', r'\1\n', code)

		# 确保文件末尾只有一个换行符
		code = code.rstrip() + '\n'

		return code

	def _sanitize_and_validate_config(self, file_path: str) -> bool:
		"""验证并清理配置文件中的非法字符，移除AI常误写入的Markdown标记。

		Args:
			file_path: 配置文件路径（.yaml/.yml/.json）

		Returns:
			bool: 清理并验证通过返回 True，否则返回 False
		"""
		import yaml

		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				content = f.read()
		except Exception as e:
			self.logger.warning(f"读取配置文件失败，跳过清理: {file_path}, {e}")
			return False

		original_content = content
		# 1. 移除Markdown代码块标记（AI常把 ``` 写进文件）
		content = re.sub(r'\n```\w*\r?\n?', '\n', content)
		content = re.sub(r'^```\w*\r?\n?', '', content)
		content = re.sub(r'\n```\s*$', '\n', content)

		# 2. 移除纯Markdown说明行（如 **关键设计说明**：）及其后续段落
		lines = content.split('\n')
		cleaned_lines = []
		skip_markdown_section = False
		for line in lines:
			# 检测Markdown标题/加粗行（如 **...** 或 # ...）
			if re.match(r'^\s*\*\*.*\*\*\s*$', line) or re.match(r'^\s*#{1,6}\s+', line):
				skip_markdown_section = True
				continue
			# 如果当前在跳过Markdown区域，遇到空行或YAML内容则恢复
			if skip_markdown_section:
				if line.strip() == '':
					continue
				# 如果遇到YAML特征行（键值对、列表、注释），恢复保留
				if re.match(r'^\s*(#|[\w-]+\s*:|-\s)', line):
					skip_markdown_section = False
				else:
					continue
			cleaned_lines.append(line)

		content = '\n'.join(cleaned_lines).rstrip() + '\n'

		# 3. 重新验证语法
		is_valid = False
		try:
			if file_path.endswith(('.yaml', '.yml')):
				yaml.safe_load(content)
				is_valid = True
			elif file_path.endswith('.json'):
				json.loads(content)
				is_valid = True
		except Exception as e:
			self.logger.error(f"配置文件语法验证失败: {file_path}, {e}")
			# 即使验证失败也写入清理后的内容（可能比原来好）
			is_valid = False

		# 只有内容变化或需要强制保存时才写入
		if content != original_content or not is_valid:
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(content)
			if content != original_content:
				self.logger.info(f"✓ 已清理配置文件中的Markdown标记: {os.path.basename(file_path)}")

		return is_valid

	def _auto_fix_syntax_error(self, file_path, py_exc):
		"""尝试自动修复常见语法错误，无需调用 LLM。

		目前支持的自动修复：
		- 缩进不一致（再次执行硬性修正）
		- def/class/if/for 后缺少缩进（expected an indented block）
		- 括号未闭合（简单计数补全）
		- 行尾多余引号（unterminated string literal，通过AST验证避免误删）

		Args:
			file_path: 文件路径
			py_exc: py_compile.PyCompileError 异常对象

		Returns:
			bool: 如果修复成功并保存文件返回 True
		"""
		with open(file_path, 'r', encoding='utf-8') as f:
			content = f.read()

		lines = content.split('\n')
		error_line = getattr(py_exc, 'lineno', None)
		error_msg = str(py_exc)
		# py_compile.PyCompileError 的 lineno 在某些 SyntaxError 场景下为 None，
		# 需要从异常文本中解析出行号，否则后续基于 error_line 的修复策略会全部失效。
		if not error_line:
			line_match = re.search(r'line\s+(\d+)', error_msg)
			if line_match:
				try:
					error_line = int(line_match.group(1))
				except ValueError:
					error_line = None
		fixed = False

		# 策略1: 缩进错误（再次执行硬性修正）
		if 'IndentationError' in error_msg or 'unexpected indent' in error_msg:
			fixed_content = self._fix_indentation_and_whitespace(content)
			if fixed_content != content:
				content = fixed_content
				fixed = True
				self.logger.info("✓ 自动修复：修正缩进")

		# 策略2: expected an indented block（def/class/if/for 后缺少缩进）
		if not fixed and error_line and 'expected an indented block' in error_msg:
			idx = error_line - 1
			if 0 <= idx < len(lines):
				lines[idx] = '    ' + lines[idx]
				content = '\n'.join(lines)
				fixed = True
				self.logger.info(f"✓ 自动修复：第 {error_line} 行补缩进")

		# 策略3: 括号未闭合（简单计数，修复文件尾部常见截断）
		if not fixed and ('unexpected EOF' in error_msg or 'invalid syntax' in error_msg):
			paren_open = content.count('(') - content.count(')')
			bracket_open = content.count('[') - content.count(']')
			brace_open = content.count('{') - content.count('}')
			trail = ""
			if paren_open > 0:
				trail += ')' * paren_open
				fixed = True
				self.logger.info(f"✓ 自动修复：补全 {paren_open} 个右圆括号")
			if bracket_open > 0:
				trail += ']' * bracket_open
				fixed = True
				self.logger.info(f"✓ 自动修复：补全 {bracket_open} 个右方括号")
			if brace_open > 0:
				trail += '}' * brace_open
				fixed = True
				self.logger.info(f"✓ 自动修复：补全 {brace_open} 个右花括号")
			if trail:
				content = content.rstrip() + '\n' + trail + '\n'

		# 策略4: 未终止的字符串字面量（常见原因是行尾多了一个孤立引号）
		if not fixed and error_line and 'unterminated string literal' in error_msg:
			idx = error_line - 1
			if 0 <= idx < len(lines):
				stripped = lines[idx].rstrip()
				# 依次尝试检测双引号和单引号
				for quote_char in ('"', "'"):
					if not (stripped.endswith(quote_char) and len(stripped) >= 2):
						continue
					# 统计该行内未转义的 quote_char 数量；偶数说明大概率是合法字符串的闭合引号，跳过
					unescaped_count = 0
					escape_next = False
					for ch in stripped:
						if escape_next:
							escape_next = False
							continue
						if ch == '\\':
							escape_next = True
							continue
						if ch == quote_char:
							unescaped_count += 1
					if unescaped_count % 2 == 0:
						continue
					candidate = stripped[:-1]
					tentative_lines = lines[:]
					tentative_lines[idx] = candidate
					tentative_content = '\n'.join(tentative_lines)
					# 先用整文件 compile 验证，防止误删多行字符串的合法闭合引号
					try:
						compile(tentative_content, file_path, 'exec')
						lines = tentative_lines
						content = tentative_content
						fixed = True
						label = "单引号" if quote_char == "'" else "双引号"
						self.logger.info(f"✓ 自动修复：删除第 {error_line} 行末尾多余的{label}")
						break
					except SyntaxError:
						# 退回到单行 AST 验证（兼容旧逻辑）
						try:
							import ast
							ast.parse(candidate.lstrip() + '\n')
							lines = tentative_lines
							content = tentative_content
							fixed = True
							label = "单引号" if quote_char == "'" else "双引号"
							self.logger.info(f"✓ 自动修复：删除第 {error_line} 行末尾多余的{label}")
							break
						except SyntaxError:
							pass

		if fixed:
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(content)
			return True

		return False

	def _get_syntax_error_context(self, file_path, error_line, radius=8):
		"""获取语法错误位置附近的代码上下文，带行号标记。

		Args:
			file_path: 文件路径
			error_line: 1-based 行号
			radius: 上下各取多少行

		Returns:
			str: 带标记的上下文字符串
		"""
		with open(file_path, 'r', encoding='utf-8') as f:
			lines = f.readlines()

		if not error_line or error_line < 1:
			return "（无法定位错误行）"

		start = max(0, error_line - radius - 1)
		end = min(len(lines), error_line + radius)

		context_lines = []
		for i in range(start, end):
			marker = ">>> " if i == error_line - 1 else "    "
			context_lines.append(f"{marker}{i+1:4d} | {lines[i].rstrip()}")

		return '\n'.join(context_lines)

	def _get_enclosing_method_name(self, file_path, error_line):
		"""根据错误行号定位其所在的函数/方法名（用于语法错误修复提示）。"""
		if not error_line or error_line < 1:
			return "（无法定位）"
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				lines = f.readlines()
		except Exception:
			return "（无法读取文件）"
		if error_line > len(lines):
			return "（行号超出范围）"
		err_idx = error_line - 1
		err_indent = len(lines[err_idx]) - len(lines[err_idx].lstrip())
		for i in range(err_idx, -1, -1):
			stripped = lines[i].strip()
			if stripped.startswith('def ') or stripped.startswith('async def '):
				header_indent = len(lines[i]) - len(lines[i].lstrip())
				if header_indent < err_indent:
					name_match = re.search(r'def\s+(\w+)', stripped)
					if name_match:
						return name_match.group(1)
		return "（未找到）"

	def _auto_fix_results_schema(self, simulator_file_path: str) -> bool:
		"""自动校验并补全 init_results 与 __init__ 的 results 初始值一致性。

		若 init_results() 中返回的键在 __init__() 中缺少 self.results[键].append(...)，
		则自动在 __init__ 末尾补全 self.results["键"].append(0.0)。

		Returns:
			bool: True 表示已修复或无需修复，False 表示修复失败。
		"""
		try:
			import ast
			with open(simulator_file_path, 'r', encoding='utf-8') as f:
				content = f.read()
			tree = ast.parse(content)
		except Exception as e:
			self.logger.warning(f"Schema自动校验：解析失败，跳过: {e}")
			return False

		class_def = None
		for node in tree.body:
			if isinstance(node, ast.ClassDef):
				class_def = node
				break
		if not class_def:
			return False

		# 提取 init_results 返回的字典键
		init_keys = set()
		for node in class_def.body:
			if isinstance(node, ast.FunctionDef) and node.name == 'init_results':
				for stmt in node.body:
					if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
						for k in stmt.value.keys:
							if isinstance(k, ast.Constant) and isinstance(k.value, str):
								init_keys.add(k.value)
						break
				break

		# 提取 __init__ 中 self.results[...].append(...) 的键
		append_keys = set()
		init_node = None
		for node in class_def.body:
			if isinstance(node, ast.FunctionDef) and node.name == '__init__':
				init_node = node
				for stmt in ast.walk(node):
					if (isinstance(stmt, ast.Call) and
						isinstance(stmt.func, ast.Attribute) and
						stmt.func.attr == 'append' and
						isinstance(stmt.func.value, ast.Subscript) and
						isinstance(stmt.func.value.value, ast.Attribute) and
						stmt.func.value.value.attr == 'results' and
						isinstance(stmt.func.value.value.value, ast.Name) and
						stmt.func.value.value.value.id == 'self'):
						slice_node = stmt.func.value.slice
						if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
							append_keys.add(slice_node.value)
				break

		if not init_keys or init_node is None:
			return False

		missing = init_keys - append_keys
		if not missing:
			self.logger.info("Schema自动校验：init_results 与 __init__ 已对齐")
			return True

		self.logger.warning(f"Schema自动校验：__init__ 缺失 {len(missing)} 个 results 初始值：{sorted(missing)}")

		lines = content.split('\n')
		stmt_indent = '    '  # 类方法体默认4空格缩进
		# 尝试从 __init__ 第一行非空内容推断实际缩进
		for i in range(init_node.lineno, min(init_node.end_lineno, len(lines))):
			stripped = lines[i].strip()
			if stripped and not stripped.startswith('def ') and not stripped.startswith('#'):
				stmt_indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
				break

		new_code_lines = [f'{stmt_indent}self.results["{k}"].append(0.0)' for k in sorted(missing)]
		insert_pos = init_node.end_lineno - 1  # 0-based，在 __init__ 最后一行之前插入
		before = lines[:insert_pos]
		after = lines[insert_pos:]

		with open(simulator_file_path, 'w', encoding='utf-8') as f:
			f.write('\n'.join(before + new_code_lines + after))

		self.logger.info(f"Schema自动校验：已自动补全 {len(missing)} 个缺失的初始值")
		return True

	async def _check_and_fix_code(self, file_path, description_md, modules, file_type="simulator", simulator_content=None):
		"""
		统一的代码检查与修复方法（增量修改版）
		
		Args:
			file_path: 文件路径
			description_md: 设计文档
			modules: 模块信息
			file_type: 文件类型（"simulator" 或 "main"）
			simulator_content: simulator代码内容（仅main文件需要）
		
		Returns:
			list: 问题列表（空列表表示无问题）
		"""
		with open(file_path, 'r', encoding='utf-8') as f:
			code_content = f.read()
		
		# ===== 步骤0: 硬性修正缩进和空白行（在LLM检查之前） =====
		if file_type == "simulator":
			code_content = self._fix_indentation_and_whitespace(code_content)
			# 保存修正后的代码
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(code_content)
			self.logger.info("✓ 已执行硬性缩进和空白行修正")

		import py_compile

		max_check_rounds = 3
		for round_idx in range(1, max_check_rounds + 1):
			# 每次循环前先做 py_compile 语法检查
			compile_ok = True
			compile_error = ""
			try:
				py_compile.compile(file_path, doraise=True)
				self.logger.info(f"✓ py_compile 语法检查通过 (round {round_idx})")
			except py_compile.PyCompileError as e:
				compile_ok = False
				compile_error = str(e)
				self.logger.warning(f"⚠️ py_compile 发现语法错误 (round {round_idx}): {compile_error}")

				# ===== 第一层：自动修复（无需 LLM）=====
				auto_fixed = self._auto_fix_syntax_error(file_path, e)
				if auto_fixed:
					# 重新读取修复后的文件，跳过本轮 LLM 直接再验
					with open(file_path, 'r', encoding='utf-8') as f:
						code_content = f.read()
					continue

				# 提取异常信息供后续 prompt 构建使用
				error_line = getattr(e, 'lineno', None)
				if not error_line:
					line_match = re.search(r'line\s+(\d+)', str(e))
					if line_match:
						error_line = int(line_match.group(1))
				error_text = getattr(e, 'text', '')
				exc_type = e.exc_type_name if hasattr(e, 'exc_type_name') else 'SyntaxError'
				error_method = self._get_enclosing_method_name(file_path, error_line)

			# 构建检查提示词
			if compile_error:
				# ===== 语法错误场景：使用专用修复提示词（不传设计文档等冗余内容）=====
				context = self._get_syntax_error_context(file_path, error_line)
				fix_prompt_tmpl = self.prompts.get('fix_syntax_error_prompt')
				if compile_error and fix_prompt_tmpl:
					prompt = fix_prompt_tmpl.format(
						exc_type=exc_type,
						error_line=error_line,
						error_text=error_text,
						compile_error=compile_error,
						error_context=context,
						error_method=error_method,
					)
			else:
				# ===== 无语法错误场景 =====
				# main文件结构固定且高度模板化，py_compile通过即可认为语法和结构正确
				# 跳过LLM通用检查，避免LLM对嵌套函数(build_new_simulator)的过度修复引入缩进问题
				if file_type == "main":
					self.logger.info(f"✓ main文件 py_compile 通过，跳过LLM通用检查以避免过度修复")
					return []

				# ===== 无专用模板：使用通用检查提示词 =====
				if file_type == "simulator":
					prompt = self.prompts['check_and_fix_simulator_prompt'].format(
						code_content=code_content,
						description_md=description_md
					)

			response = await self.generate_llm_response(prompt)
			if not response:
				self.logger.warning(f"检查失败 (round {round_idx}): LLM返回空响应")
				return ["LLM返回空响应"]

			# 检查是否返回OK
			if 'OK' in response.upper():
				if compile_ok:
					self._wait_for_user_confirmation(f"检查代码 ({file_type}) - 无问题")
					return []  # 无问题且语法通过，结束循环
				else:
					self.logger.warning(f"LLM返回OK但py_compile未通过，继续检查...")
					# 继续下一轮，让LLM再次检查并修复
					continue

			# 应用修改（语法修复场景下禁止新增方法/函数，防止 LLM 臆造新方法）
			if self._apply_code_changes(file_path, response, file_type, allow_add_new=False):
				# 重新读取文件内容，用于下一轮检查
				with open(file_path, 'r', encoding='utf-8') as f:
					code_content = f.read()
				# 修改已应用，继续下一轮做 py_compile + LLM 检查
				continue
			else:
				self.logger.warning(f"无法应用修复内容 (round {round_idx})")
				return ["无法应用修复内容"]

		# 达到最大循环次数仍未完全解决
		self.logger.error("❌ 循环检查达到最大次数，仍存在问题")
		return ["循环检查达到最大次数仍有问题"]
		
	async def refine_main_functions(self, main_file_path, simulator_file_path, description_md, modules_config_yaml, main_skipped=False):
		"""
		步骤4: 检查并修复main文件代码
		只进行总体检查与修复，不再逐个补完函数
		
		Args:
			main_file_path: main文件路径
			simulator_file_path: simulator文件路径
			description_md: 设计文档
			modules_config_yaml: 模块配置YAML内容
			main_skipped: main文件生成是否被跳过（默认False）
		"""
		self.logger.info("=== 步骤4: 开始检查main文件 ===")
		
		# 如果main文件生成被跳过，也跳过检查
		if main_skipped:
			self.logger.info("✓ Main文件生成已跳过，自动跳过检查步骤")
			return [main_file_path]
		
		# 读取main代码
		if not os.path.exists(main_file_path):
			self.logger.error(f"Main文件不存在: {main_file_path}")
			return []
		
		# 读取simulator代码
		simulator_content = ""
		if os.path.exists(simulator_file_path):
			with open(simulator_file_path, 'r', encoding='utf-8') as f:
				simulator_content = f.read()
		
		# ============ 总体检查与修复（循环重试） ============
		self.logger.info("开始总体检查与修复...")
		issues = []
		for attempt in range(1, self.MAX_FIX_ATTEMPTS + 1):
			self.logger.info(f"第 {attempt}/{self.MAX_FIX_ATTEMPTS} 次总体检查...")

			issues = await self._check_and_fix_code(main_file_path, description_md, modules_config_yaml, "main", simulator_content)

			if not issues:
				self.logger.info("✓ Main代码完整无误")
				return [main_file_path]
			self.logger.warning(f"发现 {len(issues)} 个问题: {issues[:3]}...")  # 只显示前3个
			if attempt < self.MAX_FIX_ATTEMPTS:
				self.logger.info("尝试自动修复...")

		if issues:
			action = await self._ask_user_retry_action("Main总体检查与修复", main_file_path)
			if action == 'abort':
				self.logger.error("❌ 用户选择放弃总体检查")
			elif action == 'regenerate':
				self.logger.info("重新生成 main 文件...")
				template_filename = 'main_survey_template.py' if self.simulation_type == 'survey' else 'main_template.py'
				template_path = os.path.join(self._rag_project_root, 'entrypoints', template_filename)
				if os.path.exists(template_path):
					shutil.copy2(template_path, main_file_path)
					self.logger.info("✓ 已重新复制模板")
				else:
					self.logger.warning(f"模板文件不存在: {template_path}")
			else:  # retry
				self.logger.info("额外尝试一次总体检查...")
				issues = await self._check_and_fix_code(main_file_path, description_md, modules_config_yaml, "main", simulator_content)
				if not issues:
					self.logger.info("✓ 额外尝试后代码完整无误")
					return [main_file_path]
				self.logger.error("❌ 额外尝试后仍有问题")

		return [main_file_path]

	async def generate_influences_config_file(self, description_md, modules_config_yaml, previous_configs=None):
		"""生成 influences.yaml（影响函数配置）"""
		config_filename = 'influences.yaml'
		self.logger.info(f"开始生成配置文件: {config_filename}")

		fpath = os.path.join(self.config_dir, config_filename)
		if not self._check_file_exists_and_ask(fpath, f"配置文件 ({config_filename})"):
			return fpath if os.path.exists(fpath) else None

		template_path = os.path.join(self.config_template_dir, config_filename)
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		else:
			self.logger.warning(f"模板文件不存在: {template_path}")

		interface_docs = self._read_relevant_api_docs(config_filename)
		structured_pairs: List[dict] = []
		pairs_path = os.path.join(self.config_dir, 'influence_pairs.json')

		def parse_json_array(response_text: Optional[str]) -> List[dict]:
			if not response_text:
				return []
			patterns = [
				r'```json\s*(\[[\s\S]+?\])\s*```',
				r'```\s*(\[[\s\S]+?\])\s*```',
				r'(\[[\s\S]+\])',
			]
			for pattern in patterns:
				match = re.search(pattern, response_text, re.DOTALL)
				if not match:
					continue
				candidate = match.group(1) if match.lastindex else match.group(0)
				try:
					data = json.loads(candidate)
					return data if isinstance(data, list) else []
				except json.JSONDecodeError:
					continue
			try:
				data = json.loads(response_text)
				return data if isinstance(data, list) else []
			except json.JSONDecodeError:
				self.logger.warning("JSON解析失败，忽略响应")
				return []

		def merge_pair_updates(base_pairs: List[dict], updates: List[dict], include_resolved: bool, update_params: bool = False):
			if not base_pairs or not updates:
				return
			lookup = {item.get('pair_id'): item for item in updates if isinstance(item, dict) and item.get('pair_id') is not None}
			for pair in base_pairs:
				payload = lookup.get(pair.get('pair_id'))
				if not payload:
					continue
				for field in ('direction', 'effect_size', 'rationale'):
					if field in payload:
						pair[field] = payload[field]
				if update_params:
					for role in ('cause', 'effect'):
						segment = payload.get(role)
						if isinstance(segment, dict) and 'param' in segment:
							pair.setdefault(role, {})['param'] = segment['param']
				if include_resolved:
					for role in ('cause', 'effect'):
						segment = payload.get(role)
						if isinstance(segment, dict) and segment.get('resolved_param'):
							pair.setdefault(role, {})['resolved_param'] = segment['resolved_param']

		def build_module_code_bundle(module_name: str) -> str:
			interface_chunk = self._read_interface_docs_for_modules([module_name], max_chars_per_file=1200)
			plugin_chunk = self._read_plugin_code_for_module(module_name, max_chars=2200)
			pieces: List[str] = []
			if interface_chunk and interface_chunk.strip() and interface_chunk.strip() != "（未找到相关接口文件）":
				pieces.append(f"## Interface Docs: {module_name}\n```python\n{interface_chunk}\n```")
			if plugin_chunk and plugin_chunk.strip():
				pieces.append(f"## Plugin Code: {module_name}\n```python\n{plugin_chunk}\n```")
			return "\n\n".join(pieces).strip()

		pairs_prompt = (self.prompts or {}).get('generate_influence_pairs_prompt')
		if pairs_prompt:
			# print("[generate_influences] 调用影响对生成提示词...")
			# 从论文库检索候选影响对（减少top_k避免信息过载）
			paper_candidates = self._rag_query_paper_candidates(description_md, top_k=3)
			paper_candidates_context = ""
			if paper_candidates:
				paper_candidates_context = "【论文库检索到的参考影响对】\n" + "\n".join(paper_candidates)
				# 统计实际影响对数量（paper_candidates包含标题行、影响对行和空行）
				actual_pair_count = sum(1 for s in paper_candidates if s.startswith('- '))
				self.logger.info(f"步骤0 论文候选检索: {actual_pair_count}条影响对 (来自{len([s for s in paper_candidates if s.startswith('论文:')])}篇论文)")

			# 步骤1：依据设计文档+modules_config+论文候选先产出粗粒度影响对清单
			response = await self.generate_llm_response(pairs_prompt.format(
				description_md=description_md,
				modules_config_yaml=modules_config_yaml,
				paper_candidates_context=paper_candidates_context,
			))
			# print(f"[generate_influences] 影响对原始响应: {response}")
			parsed = parse_json_array(response)
			normalized: List[dict] = []
			for idx, item in enumerate(parsed, 1):
				if not isinstance(item, dict):
					continue
				entry = dict(item)
				entry['pair_id'] = int(entry.get('pair_id') or idx)
				normalized.append(entry)
			structured_pairs = normalized
			if structured_pairs:
				try:
					with open(pairs_path, 'w', encoding='utf-8') as pf:
						json.dump(structured_pairs, pf, ensure_ascii=False, indent=2)
					self.logger.info(f"✓ 写入影响对草案: {pairs_path}")
				except Exception as exc:
					self.logger.warning(f"无法写入 influence_pairs.json: {exc}")

				# 交互模式下暂停，允许用户手动修改 influence_pairs.json
				if not self.auto_mode:
					self.logger.info(f"影响对草案已写入: {pairs_path}")
					print(f"\n{'='*60}")
					print(f"📋 影响对草案已生成，共 {len(structured_pairs)} 条")
					print(f"文件路径: {pairs_path}")
					print(f"您可以手动修改该文件，修改完成后按回车继续...")
					print(f"{'='*60}")

					if self.session:
						# Web 模式：发送通知到前端，自动继续
						try:
							if 'output_queue' in self.session:
								self.session['output_queue'].put(f"\n{'='*60}")
								self.session['output_queue'].put(f"📋 影响对草案已生成，共 {len(structured_pairs)} 条")
								self.session['output_queue'].put(f"文件路径: {pairs_path}")
								self.session['output_queue'].put(f"您可以手动修改该文件")
								self.session['output_queue'].put(f"{'='*60}")
						except Exception as e:
							self.logger.warning(f"发送输出到前端失败: {e}")
					else:
						# CLI 交互模式：等待用户按回车
						input("按回车继续生成...").strip()

					# 重新读取 influence_pairs.json（用户可能已修改）
					try:
						with open(pairs_path, 'r', encoding='utf-8') as pf:
							reloaded_pairs = json.load(pf)
						if isinstance(reloaded_pairs, list) and reloaded_pairs:
							structured_pairs = reloaded_pairs
							self.logger.info(f"✓ 重新读取 influence_pairs.json，共 {len(structured_pairs)} 条")
						else:
							self.logger.warning("重新读取 influence_pairs.json 结果为空或格式不正确，使用原始数据")
					except Exception as exc:
						self.logger.warning(f"重新读取 influence_pairs.json 失败，使用原始数据: {exc}")

			rag_prompt = (self.prompts or {}).get('enrich_influence_pairs_prompt')
			resolve_prompt = (self.prompts or {}).get('resolve_influence_pair_params_prompt')
			if structured_pairs and rag_prompt:
				# 步骤2：并列检索 + 并列生成增强（2a直接证据 + 2b相关声明 + 2c调节变量论文）
				total_pairs = len(structured_pairs)
				queried_pairs = 0
				updated_pairs = 0
				total_update_items = 0

				async def _retrieve_evidence(pair: dict):
					"""并行检索单条影响对的RAG证据。"""
					cause = pair.get('cause') or {}
					effect = pair.get('effect') or {}
					cause_param = str(cause.get('param') or '').strip()
					effect_param = str(effect.get('param') or '').strip()
					cause_module = str(cause.get('module') or '').strip()
					effect_module = str(effect.get('module') or '').strip()
					pair_id = pair.get('pair_id')

					query = " ".join(filter(None, [
						cause_module, cause_param, "→", effect_module, effect_param,
					])).strip()

					# 并列检索 2a/2b/2c
					direct_evidence, related_evidence, moderator_papers = await asyncio.gather(
						asyncio.to_thread(self._rag_query_causal_claims, query, 3),
						asyncio.to_thread(self._rag_query_related_claims, cause_param or cause_module, effect_param or effect_module),
						asyncio.to_thread(self._rag_query_moderator_papers, cause_param or cause_module, effect_param or effect_module),
					)

					# 构建简洁的RAG上下文（2a/2b 用 paper_edge_id 全局去重）
					seen_eids: set[str] = set()
					context_lines: List[str] = []
					if direct_evidence:
						context_lines.append("【直接证据】")
						for eid, line in direct_evidence:
							if eid and eid in seen_eids:
								continue
							if eid:
								seen_eids.add(eid)
							context_lines.append(line)
					if related_evidence:
						context_lines.append("\n【相关影响对】")
						for eid, line in related_evidence:
							if eid and eid in seen_eids:
								continue
							if eid:
								seen_eids.add(eid)
							context_lines.append(line)
					if moderator_papers:
						context_lines.append("\n【调节/中介变量论文】")
						context_lines.extend(moderator_papers)
					rag_context = "\n".join(context_lines)[:2500]

					has_evidence = bool(direct_evidence or related_evidence or moderator_papers)
					return {
						'pair_id': pair_id,
						'pair': pair,
						'rag_context': rag_context,
						'has_evidence': has_evidence,
						'evidence_counts': {
							'direct': len(direct_evidence),
							'related': len(related_evidence),
							'moderator': len(moderator_papers),
						},
					}

				# Phase 1: 并列检索所有证据
				self.logger.info(f"步骤2 Phase1: 并列检索 {total_pairs} 条影响对的RAG证据...")
				evidence_results = await asyncio.gather(*[_retrieve_evidence(p) for p in structured_pairs])
				queried_pairs = sum(1 for r in evidence_results if r['has_evidence'])
				self.logger.info(f"步骤2 Phase1完成: {queried_pairs}/{total_pairs} 条触发RAG检索")

				agent_profile_attrs = self._load_agent_profile_attrs_text()

				# 预加载所有相关模块的接口文档；resident 模块附加 agent_profile 属性清单
				relevant_modules: set[str] = set()
				for p in structured_pairs:
					cause_module = str((p.get('cause') or {}).get('module') or '').strip()
					effect_module = str((p.get('effect') or {}).get('module') or '').strip()
					if cause_module:
						relevant_modules.add(cause_module)
					if effect_module:
						relevant_modules.add(effect_module)
				module_interface_cache: Dict[str, str] = {}
				for module_name in relevant_modules:
					docs = self._read_interface_docs_for_modules([module_name], max_chars_per_file=1200)
					if module_name in ('resident', 'residents') and agent_profile_attrs:
						docs = f"{agent_profile_attrs}\n\n{docs}"
					module_interface_cache[module_name] = docs

				# Phase 1.5: 基于接口文档解析所有影响对的参数名
				if resolve_prompt:
					async def _resolve_one(pair: dict):
						pair_id = pair.get('pair_id')
						cause_module = str((pair.get('cause') or {}).get('module') or '').strip()
						effect_module = str((pair.get('effect') or {}).get('module') or '').strip()
						cause_docs = module_interface_cache.get(cause_module, "（未找到相关接口文件）")
						effect_docs = module_interface_cache.get(effect_module, "（未找到相关接口文件）")
						response = await self.generate_llm_response(
							resolve_prompt.format(
								pair_json=json.dumps([pair], ensure_ascii=False, indent=2),
								cause_interface_docs=cause_docs,
								effect_interface_docs=effect_docs,
							)
						)
						updates = parse_json_array(response)
						if updates:
							merge_pair_updates([pair], updates, include_resolved=False, update_params=True)
						else:
							self.logger.warning(f"步骤1.5 pair_id={pair_id} 未返回可解析参数解析结果")

					self.logger.info(f"步骤1.5: 并列解析 {total_pairs} 条影响对的参数名...")
					await asyncio.gather(*[_resolve_one(p) for p in structured_pairs])
					self.logger.info(f"步骤1.5完成: 已解析 {total_pairs} 条影响对的参数名")

				async def _enhance_one(evidence: dict):
					"""并行LLM增强单条影响对。"""
					pair_id = evidence['pair_id']
					rag_context = evidence['rag_context']
					pair = evidence['pair']
					counts = evidence['evidence_counts']

					print(f"[generate_influences] 步骤2增强 pair_id={pair_id} (2a直接证据:{counts['direct']}条, 2b相关影响对:{counts['related']}条, 2c调节论文:{counts['moderator']}条)...")
					response = await self.generate_llm_response(
						rag_prompt.format(
							pairs_json=json.dumps([pair], ensure_ascii=False, indent=2),
							rag_context=rag_context,
						)
					)
					updates = parse_json_array(response)
					if updates:
						return updates
					else:
						self.logger.warning(f"步骤2 pair_id={pair_id} 未返回可解析增强结果")
						return []

				# Phase 2: 并列生成增强（只针对检索到证据的pair）
				enhance_tasks = [asyncio.create_task(_enhance_one(r)) for r in evidence_results if r['has_evidence']]
				if enhance_tasks:
					self.logger.info(f"步骤2 Phase2: 并列生成 {len(enhance_tasks)} 条影响对的增强...")
					enhance_results = await asyncio.gather(*enhance_tasks)
					for updates in enhance_results:
						if updates:
							merge_pair_updates(structured_pairs, updates, include_resolved=False)
							updated_pairs += 1
							total_update_items += len(updates)

				self.logger.info(
					f"步骤2 RAG增强完成：总pair={total_pairs}, 触发RAG={queried_pairs}, "
					f"成功更新pair={updated_pairs}, 更新条目={total_update_items}"
				)

		# 步骤3：按 pair 逐条生成 influence 块，并实时写入 influences.yaml
		block_prompt = (self.prompts or {}).get('generate_influence_block_prompt')
		if not block_prompt:
			raise KeyError("code_architect_prompts.yaml 缺少 generate_influence_block_prompt")

		previous_yaml_doc: dict = {}
		if os.path.exists(fpath):
			try:
				with open(fpath, 'r', encoding='utf-8') as f:
					loaded_doc = yaml.safe_load(f) or {}
				if isinstance(loaded_doc, dict):
					previous_yaml_doc = loaded_doc
			except Exception as exc:
				self.logger.warning(f"读取现有 influences.yaml 失败，将重新初始化: {exc}")
		if not isinstance(previous_yaml_doc, dict):
			previous_yaml_doc = {}
		if not isinstance(previous_yaml_doc.get('execution_order'), list):
			previous_yaml_doc['execution_order'] = []
		if not isinstance(previous_yaml_doc.get('influences'), list):
			previous_yaml_doc['influences'] = []
		if previous_configs and isinstance(previous_configs, dict):
			prior_yaml = previous_configs.get('influences.yaml') or previous_configs.get('influence.yaml')
			if prior_yaml and isinstance(prior_yaml, str):
				try:
					prior_doc = yaml.safe_load(prior_yaml) or {}
					if isinstance(prior_doc, dict):
						if prior_doc.get('execution_order'):
							previous_yaml_doc['execution_order'] = prior_doc.get('execution_order')
						if isinstance(prior_doc.get('influences'), list) and prior_doc.get('influences'):
							previous_yaml_doc['influences'] = prior_doc.get('influences')
				except Exception:
					pass

		total_pairs = len(structured_pairs)
		success_pairs = 0
		failed_pairs: List[int] = []
		written_blocks = 0
		ordered_names: List[str] = []
		ordered_steps: List[Dict[str, str]] = []

		async def _generate_one_block(pair: dict):
			"""并行生成单条 influence 块。"""
			pair_id = pair.get('pair_id')
			cause = pair.get('cause') or {}
			effect = pair.get('effect') or {}
			cause_module = str(cause.get('module') or '').strip()
			effect_module = str(effect.get('module') or '').strip()
			if not cause_module or not effect_module:
				self.logger.warning(f"pair_id={pair_id} 缺少 cause/effect 模块名，跳过")
				return {'pair_id': pair_id, 'success': False, 'reason': 'missing_module'}

			cause_code = build_module_code_bundle(cause_module)
			effect_code = build_module_code_bundle(effect_module)
			if not cause_code and not effect_code:
				self.logger.warning(f"pair_id={pair_id} 未找到 cause/effect 模块源码，跳过")
				return {'pair_id': pair_id, 'success': False, 'reason': 'missing_code'}

			print(f"[generate_influences] 步骤3/4 生成 influence 块 pair_id={pair_id} ({cause_module} -> {effect_module})")
			response = await self.generate_llm_response(
				block_prompt.format(
					pair_json=json.dumps(pair, ensure_ascii=False, indent=2),
					cause_module_code=cause_code,
					effect_module_code=effect_code,
					template_content=template_content,
				)
			)
			yaml_text = None
			if response:
				for pattern in (r'```yaml\s*([\s\S]*?)```', r'```\s*([\s\S]*?)```'):
					match = re.search(pattern, response, re.DOTALL)
					if match:
						candidate = match.group(1).strip()
						if candidate:
							yaml_text = candidate
							break
				if not yaml_text:
					try:
						parsed_block = yaml.safe_load(response)
						if isinstance(parsed_block, dict):
							yaml_text = yaml.safe_dump(parsed_block, allow_unicode=True, sort_keys=False).strip()
						elif isinstance(parsed_block, list) and parsed_block:
							# LLM 返回列表时取第一个元素回写为单条 YAML
							yaml_text = yaml.safe_dump(parsed_block[0], allow_unicode=True, sort_keys=False).strip()
					except Exception:
						yaml_text = None
			if not yaml_text:
				self.logger.warning(f"pair_id={pair_id} 未解析到 YAML block")
				return {'pair_id': pair_id, 'success': False, 'reason': 'parse_failed'}

			try:
				block_data = yaml.safe_load(yaml_text)
				if isinstance(block_data, list):
					if not block_data:
						self.logger.warning(f"pair_id={pair_id} 解析后 YAML 列表为空")
						return {'pair_id': pair_id, 'success': False, 'reason': 'empty_list'}
					block_data = block_data[0]
				if not isinstance(block_data, dict):
					self.logger.warning(f"pair_id={pair_id} 解析后不是字典结构，实际类型={type(block_data).__name__}")
					return {'pair_id': pair_id, 'success': False, 'reason': 'not_dict'}
				if 'name' not in block_data or 'type' not in block_data or 'source' not in block_data or 'target' not in block_data:
					self.logger.warning(f"pair_id={pair_id} influence 块缺少必要字段")
					return {'pair_id': pair_id, 'success': False, 'reason': 'missing_fields'}
				return {'pair_id': pair_id, 'success': True, 'block_data': block_data}
			except Exception as exc:
				self.logger.warning(f"pair_id={pair_id} influence 块解析失败: {exc}")
				return {'pair_id': pair_id, 'success': False, 'reason': 'exception'}

		# 并列生成所有 influence 块
		self.logger.info(f"步骤3: 并列生成 {len(structured_pairs)} 条 influence 块...")
		block_results = await asyncio.gather(*[_generate_one_block(p) for p in structured_pairs])

		# 统一收集结果并写入 influences.yaml
		for result in block_results:
			pair_id = result['pair_id']
			if not result['success']:
				failed_pairs.append(pair_id)
				continue

			block_data = result['block_data']
			name = str(block_data.get('name') or '').strip()
			target = str(block_data.get('target') or '').strip()
			source = block_data.get('source') or {}
			if isinstance(source, dict):
				source_module = str(source.get('module') or '').strip()
			else:
				source_module = str(source or '').strip()
			identity = f"{source_module}->{target}:{name}"
			filtered_influences = []
			for existing in previous_yaml_doc.get('influences', []):
				if not isinstance(existing, dict):
					continue
				existing_name = str(existing.get('name') or '').strip()
				existing_target = str(existing.get('target') or '').strip()
				existing_source = existing.get('source') or {}
				if isinstance(existing_source, dict):
					existing_source_module = str(existing_source.get('module') or '').strip()
				else:
					existing_source_module = str(existing_source or '').strip()
				existing_identity = f"{existing_source_module}->{existing_target}:{existing_name}"
				if existing_identity != identity:
					filtered_influences.append(existing)
			filtered_influences.append(block_data)
			previous_yaml_doc['influences'] = filtered_influences
			with open(fpath, 'w', encoding='utf-8') as f:
				yaml.safe_dump(previous_yaml_doc, f, allow_unicode=True, sort_keys=False)
			written_blocks += 1
			success_pairs += 1
			ordered_names.append(name)
			ordered_steps.append({'module': source_module, 'target': target})
			self.logger.info(f"✓ 已写入 pair_id={pair_id} 的 influence 块到 {fpath}")

		if ordered_steps:
			previous_yaml_doc['execution_order'] = ordered_steps
			with open(fpath, 'w', encoding='utf-8') as f:
				yaml.safe_dump(previous_yaml_doc, f, allow_unicode=True, sort_keys=False)
			self.logger.info(f"✓ 已更新 execution_order: {ordered_names}")

		self.logger.info(
			f"步骤3完成：总pair={total_pairs}, 成功写入={success_pairs}, 失败={len(failed_pairs)}, 写入次数={written_blocks}"
		)
		if not os.path.exists(fpath):
			with open(fpath, 'w', encoding='utf-8') as f:
				yaml.safe_dump(previous_yaml_doc, f, allow_unicode=True, sort_keys=False)
			self.logger.info(f"✓ 未命中任何 influence 块，已新建空 influences.yaml: {fpath}")
		else:
			self.logger.info(f"✓ influences.yaml 已更新: {fpath}")
		return fpath

	def _rag_query_causal_claims(self, query_text: str, top_k: int = 3, max_distance: float = 1.0) -> List[Tuple[str, str]]:
		query_text = (query_text or '').strip()
		if not query_text:
			return []
		try:
			chroma_client = chromadb.PersistentClient(path=self._rag_db_path)
			collection = chroma_client.get_collection(name='causal_claims')
		except Exception as exc:
			self.logger.debug(f"RAG跳过：无法连接Chroma ({exc})")
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		embedding = self._rag_embed(client, query_text)
		if not embedding:
			return []
		try:
			results = collection.query(
				query_embeddings=[embedding],
				n_results=top_k,
				include=['documents', 'metadatas', 'distances'],
			)
		except Exception as exc:
			self.logger.debug(f"RAG查询失败: {exc}")
			return []
		documents = results.get('documents', [[]])[0]
		metadatas = results.get('metadatas', [[]])[0]
		distances = results.get('distances', [[]])[0]
		formatted: List[Tuple[str, str]] = []
		for doc, meta, dist in zip(documents, metadatas, distances):
			if not doc or dist > max_distance:
				continue
			snippet = (doc[:600] + ('...' if len(doc) > 600 else '')).strip()
			if meta:
				snippet += f"\n(meta: {meta})"
			snippet += f"\n(distance={dist})"
			eid = (meta or {}).get('paper_edge_id', '')
			formatted.append((eid, snippet))
		return formatted
	def _rag_query_paper_candidates(self, query_text: str, top_k: int = 3, max_distance: float = 1.0) -> List[str]:
		"""从papers集合向量检索相关论文，提取候选影响对文本。
		"""
		query_text = (query_text or '').strip()
		if not query_text:
			return []
		try:
			chroma_client = chromadb.PersistentClient(path=self._rag_db_path)
			collection = chroma_client.get_collection(name='papers')
		except Exception:
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		embedding = self._rag_embed(client, query_text)
		if not embedding:
			return []
		try:
			results = collection.query(
				query_embeddings=[embedding],
				n_results=top_k,
				include=['metadatas', 'distances'],
			)
		except Exception:
			return []
		metas = results.get('metadatas', [[]])[0]
		dists = results.get('distances', [[]])[0]

		formatted: List[str] = []
		total_pairs = 0
		for meta, dist in zip(metas, dists):
			if not meta or dist > max_distance:
				continue
			title = meta.get('title', '')
			year = meta.get('year', '')
			claim_list = meta.get('claim_list', [])
			if isinstance(claim_list, str):
				try:
					claim_list = json.loads(claim_list)
				except Exception:
					claim_list = []
			if not claim_list:
				continue

			# 去重
			seen: set[str] = set()
			unique_claims: List[str] = []
			for claim in claim_list:
				if claim and claim not in seen:
					seen.add(claim)
					unique_claims.append(claim)

			if unique_claims:
				formatted.append(f"论文: {title} ({year}, distance={dist:.3f})")
				for claim in unique_claims:
					formatted.append(f"- {claim}")
					total_pairs += 1
				formatted.append("")

		print(f"[RAG-papers] 从 {len([s for s in formatted if s.startswith('论文:')])} 篇论文提取 {total_pairs} 条候选影响对")
		return formatted

	def _rag_query_related_claims(self, cause: str, effect: str, max_per_side: int = 2) -> List[Tuple[str, str]]:
		"""检索包含相同cause或相同effect的其他因果声明。"""
		if not cause and not effect:
			return []
		try:
			chroma_client = chromadb.PersistentClient(path=self._rag_db_path)
			collection = chroma_client.get_collection(name='causal_claims')
		except Exception:
			return []
		lines: List[Tuple[str, str]] = []
		for field, value in [('cause', cause), ('effect', effect)]:
			if not value:
				continue
			try:
				res = collection.get(
					where={field: {'$eq': value}},
					limit=max_per_side,
					include=['documents', 'metadatas'],
				)
				for doc, meta in zip(res.get('documents', []), res.get('metadatas', [])):
					if not meta:
						continue
					c = meta.get('cause', '')
					e = meta.get('effect', '')
					if c == cause and e == effect:
						continue
					snippet = (doc or '')[:300]
					eid = meta.get('paper_edge_id', '')
					line = f"- {c} -> {e} | 方向:{meta.get('direction','')} 确定性:{meta.get('certainty','')} | {snippet}"
					lines.append((eid, line))
			except Exception:
				continue
		# print(f"[RAG-related] 检索到 {len(lines)} 条相关声明：\n" + "\n".join([l for _, l in lines[:5]]))
		return lines

	def _rag_query_moderator_papers(self, cause: str, effect: str, top_k: int = 2, max_distance: float = 1.0) -> List[str]:
		"""检索可能包含调节/中介变量的论文。"""
		query = f"{cause} {effect} mediating moderating interaction".strip()
		if not query:
			return []
		try:
			chroma_client = chromadb.PersistentClient(path=self._rag_db_path)
			collection = chroma_client.get_collection(name='papers')
		except Exception:
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		embedding = self._rag_embed(client, query)
		if not embedding:
			return []
		try:
			results = collection.query(
				query_embeddings=[embedding],
				n_results=top_k,
				include=['documents', 'metadatas', 'distances'],
			)
		except Exception:
			return []
		docs = results.get('documents', [[]])[0]
		metas = results.get('metadatas', [[]])[0]
		dists = results.get('distances', [[]])[0]
		lines = []
		for doc, meta, dist in zip(docs, metas, dists):
			if dist > max_distance:
				continue
			title = (meta or {}).get('title', '')
			snippet = (doc or '')[:300]
			lines.append(f"- {title} (distance={dist:.3f}): {snippet}")
		# print(f"[RAG-moderator] 检索到 {len(lines)} 条论文：\n" + "\n".join(lines[:5]))
		return lines

	async def generate_config_file(self, config_filename, description_md, modules_config_yaml, previous_configs=None):
		"""
		步骤5: 生成单个配置文件
		输入：配置文件名 + 设计文档 + 模块配置YAML + 已生成的配置（可选）
		输出：生成的配置文件路径
		
		支持的配置文件：
		- simulation_config.yaml
		- jobs_config.yaml
		- towns_data.json
		
		Args:
			config_filename: 配置文件名
			description_md: 设计文档
			modules_config_yaml: 模块配置YAML内容
			previous_configs: 已生成的配置字典
		"""

		self.logger.info(f"开始生成配置文件: {config_filename}")
		
		# 目标文件路径
		fpath = os.path.join(self.config_dir, config_filename)
		
		# 检查文件是否已存在
		if not self._check_file_exists_and_ask(fpath, f"配置文件 ({config_filename})"):
			# 如果跳过生成，仍需读取文件内容返回（供后续配置参考）
			if os.path.exists(fpath):
				return fpath
			else:
				return None
		
		# 读取模板
		template_path = os.path.join(self.config_template_dir, config_filename)
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				raw_template = f.read()
			# 替换模板中的项目名占位符
			template_content = raw_template.replace("{模拟名称}", self.simulation_name)
		else:
			self.logger.warning(f"模板文件不存在: {template_path}")
		
		# 读取接口文件（根据配置类型选择相关模块接口）
		interface_docs = self._read_relevant_api_docs(config_filename)
		
		file_format = 'YAML' if config_filename.endswith('.yaml') else 'JSON'
		prompt = self.prompts['generate_config_file_prompt'].format(
			config_filename=config_filename,
			description_md=description_md,
			modules=modules_config_yaml,
			template_content=template_content,
			interface_docs=interface_docs,
			file_format=file_format
		)
		
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return None

		# 策略1: 提取指定格式的代码块
		file_format = 'yaml' if config_filename.endswith('.yaml') else 'json'
		code_blocks = re.findall(rf'```{file_format}\s*([^`]+)```', response, re.DOTALL)
		
		# 策略2: 尝试匹配任意代码块
		if not code_blocks:
			code_blocks = re.findall(r'```(?:yaml|json)?\s*([^`]+)```', response, re.DOTALL)
		
		# 策略3: 如果没有代码块标记，尝试直接提取
		if not code_blocks:
			if file_format == 'yaml' and ':' in response:
				# YAML特征检测
				lines = response.split('\n')
				yaml_start = -1
				for i, line in enumerate(lines):
					if line and not line.startswith(' ') and ':' in line and not line.startswith('#'):
						yaml_start = i
						break
				if yaml_start >= 0:
					yaml_content = '\n'.join(lines[yaml_start:]).strip()
					self.logger.info(f"使用直接提取的YAML内容（无代码块标记）")
					code_blocks = [yaml_content]
			elif file_format == 'json':
				# JSON特征检测：寻找最外层的{}
				json_match = re.search(r'\{[\s\S]*\}', response)
				if json_match:
					self.logger.info(f"使用直接提取的JSON内容（无代码块标记）")
					code_blocks = [json_match.group(0)]
		
		if code_blocks:
			fpath = os.path.join(self.config_dir, config_filename)
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(code_blocks[0].strip())
			self.logger.info(f"生成配置文件: {fpath}")
			# 保存后立即清理并验证配置
			valid = self._sanitize_and_validate_config(fpath)
			if not valid:
				self.logger.warning(f"⚠️ 配置文件生成后验证未通过，但已尽力清理: {fpath}")
			return fpath
		else:
			self.logger.warning(f"未找到代码块，无法生成 {config_filename}，将使用模板/兜底内容")
			self.logger.debug(f"LLM响应预览: {response[:500]}")
			# 兜底：使用模板内容或最小 stub，确保运行时不会因文件缺失而崩溃
			fpath = os.path.join(self.config_dir, config_filename)
			fallback_content = template_content.strip() if template_content else None
			if fallback_content is None:
				if config_filename.endswith('.json'):
					fallback_content = "{}"
				elif config_filename.endswith('.yaml') or config_filename.endswith('.yml'):
					fallback_content = "# Auto-generated fallback config\n"
				else:
					fallback_content = ""
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(fallback_content)
			self.logger.info(f"✓ 已写入兜底配置文件: {fpath}")
			return fpath

	def _load_agent_profile_yaml(self, profile_path: str) -> dict:
		"""读取 agent_profile.yaml，兼容单文档（含 agents 键）和多文档（--- 分隔）格式。"""
		import yaml
		with open(profile_path, 'r', encoding='utf-8') as f:
			data = yaml.safe_load(f)
		if isinstance(data, dict) and 'agents' in data:
			return data
		# safe_load 在多文档场景下只返回首文档，因此用 safe_load_all 兜底
		with open(profile_path, 'r', encoding='utf-8') as f:
			docs = list(yaml.safe_load_all(f))
		agents = [d for d in docs if isinstance(d, dict)]
		return {'agents': agents}

	def _ensure_agent_profile_in_simulation_config(self) -> bool:
		"""确保 simulation_config.yaml 的 data.agent_profile_path 指向 agent_profile.yaml。

		不再将 agent_profile 内容嵌入 simulation_config.yaml，保持独立文件。

		Returns:
			bool: True 表示已修补或无需修补
		"""
		import yaml

		sim_path = os.path.join(self.config_dir, 'simulation_config.yaml')
		profile_path = os.path.join(self.config_dir, 'agent_profile.yaml')

		if not os.path.exists(sim_path):
			return False
		if not os.path.exists(profile_path):
			return True  # 没有 agent_profile.yaml，无需修补

		try:
			with open(sim_path, 'r', encoding='utf-8') as f:
				sim_config = yaml.safe_load(f) or {}
			if not isinstance(sim_config, dict):
				return False

			# 如果已内嵌 agent_profile，删除它
			if 'agent_profile' in sim_config:
				del sim_config['agent_profile']
				self.logger.info("已从 simulation_config.yaml 中移除内嵌的 agent_profile")

			# 确保 data.agent_profile_path 指向独立文件
			data_cfg = sim_config.setdefault('data', {})
			if isinstance(data_cfg, dict):
				expected_path = f"config/{self.simulation_name}/agent_profile.yaml"
				if data_cfg.get('agent_profile_path') != expected_path:
					data_cfg['agent_profile_path'] = expected_path
					with open(sim_path, 'w', encoding='utf-8') as f:
						yaml.dump(sim_config, f, allow_unicode=True, sort_keys=False)
					self.logger.info(f"✓ 已设置 data.agent_profile_path: {expected_path}")

			return True
		except Exception as exc:
			self.logger.warning(f"设置 agent_profile_path 失败: {exc}")
			return False

	def _finalize_simulation_config_paths(self) -> None:
		"""在所有配置文件和提示词文件生成结束后，自动修正 simulation_config.yaml 的 data 路径。

		规则：
		1. 自动设置必有的固定路径（climate/government/resident info）
		2. 扫描 config_dir 下实际存在的文件，按 PROJECT_FILE_MAP 映射
		3. 若存在 rebels_prompts.yaml，额外加入 rebellion_info_path
		4. 若不存在 rebels_prompts.yaml，清理 group_decision.rebellion
		5. simulation_name 强制设为空字符串
		"""
		import yaml

		fpath = os.path.join(self.config_dir, 'simulation_config.yaml')
		if not os.path.exists(fpath):
			self.logger.warning("simulation_config.yaml 不存在，跳过路径修正")
			return

		PROJECT_FILE_MAP = {
			'government_prompts.yaml': 'government_prompt_path',
			'jobs_config.yaml': 'jobs_config_path',
			'message_config.yaml': 'message_config_path',
			'questionnaire.yaml': 'questionnaire_path',
			'rebels_prompts.yaml': 'rebels_prompt_path',
			'residents_prompts.yaml': 'resident_prompt_path',
			'resident_actions.yaml': 'resident_actions_path',
			'towns_data.json': 'towns_data_path',
		}

		try:
			with open(fpath, 'r', encoding='utf-8') as f:
				config = yaml.safe_load(f) or {}
		except Exception as exc:
			self.logger.warning(f"读取 simulation_config.yaml 失败: {exc}")
			return

		if not isinstance(config, dict):
			self.logger.warning("simulation_config.yaml 根节点不是字典，跳过路径修正")
			return

		sim_cfg = config.setdefault('simulation', {})
		data_cfg = config.setdefault('data', {})
		if not isinstance(data_cfg, dict):
			data_cfg = {}
			config['data'] = data_cfg

		# 1. 强制修正 simulation_name
		if isinstance(sim_cfg, dict):
			old_name = sim_cfg.get('simulation_name')
			sim_cfg['simulation_name'] = ""
			if old_name and old_name != "":
				self.logger.info(f"已强制修正 simulation_name: '{old_name}' -> ''")

		# 2. 必有的固定路径
		data_cfg['climate_info_path'] = 'experiment_dataset/climate_data/climate.csv'
		data_cfg['government_info_path'] = 'experiment_dataset/government_data/official_data.json'
		data_cfg['resident_info_path'] = 'experiment_dataset/resident_data/resident_data.json'

		# 3. 扫描 config_dir 下实际存在的文件
		matched_files = []
		if os.path.isdir(self.config_dir):
			for filename in os.listdir(self.config_dir):
				if filename in PROJECT_FILE_MAP:
					key = PROJECT_FILE_MAP[filename]
					data_cfg[key] = f"config/{self.simulation_name}/{filename}"
					matched_files.append(filename)

			# 3.5 特殊：存在 agent_profile.yaml 时加入 agent_profile_path，
			# 同时根据 agent_profile 里的 role 列表写入 role 级 prompts/actions 路径
			if os.path.exists(os.path.join(self.config_dir, 'agent_profile.yaml')):
				data_cfg['agent_profile_path'] = f"config/{self.simulation_name}/agent_profile.yaml"
				matched_files.append('agent_profile.yaml')
				try:
					agent_profile_data = self._load_agent_profile_yaml(os.path.join(self.config_dir, 'agent_profile.yaml'))
					agents_def = agent_profile_data.get('agents', []) if isinstance(agent_profile_data, dict) else []
					if isinstance(agents_def, list):
						for agent_def in agents_def:
							if not isinstance(agent_def, dict):
								continue
							extra = agent_def.get('extra', {})
							if not isinstance(extra, dict):
								extra = {}
							role_name = str(extra.get('role') or agent_def.get('name') or '').strip()
							if not role_name:
								continue
							data_cfg[f'{role_name}_prompt_path'] = f"config/{self.simulation_name}/prompts/{role_name}.yaml"
							data_cfg[f'{role_name}_actions_path'] = f"config/{self.simulation_name}/actions/{role_name}.yaml"
						# 清理旧的 resident_* 平铺键，避免根目录兼容文件继续被引用
						for legacy_key in ('resident_prompt_path', 'resident_actions_path'):
							if legacy_key in data_cfg:
								del data_cfg[legacy_key]
				except Exception as exc:
					self.logger.warning(f"解析 agent_profile.yaml 以写入 role 路径失败: {exc}")

		# 4. 特殊：存在 rebels_prompts.yaml 时加入 rebellion_info_path
		if 'rebels_prompts.yaml' in matched_files:
			data_cfg['rebellion_info_path'] = 'experiment_dataset/rebellion_data/rebels_data.json'
		else:
			if 'rebellion_info_path' in data_cfg:
				del data_cfg['rebellion_info_path']

		# 5. 清理 group_decision：不存在 rebels 时删除 rebellion
		group_decision = sim_cfg.setdefault('group_decision', {})
		if isinstance(group_decision, dict):
			if 'rebels_prompts.yaml' not in matched_files and 'rebellion' in group_decision:
				del group_decision['rebellion']
				self.logger.info("已删除 group_decision.rebellion（rebels_prompts.yaml 不存在）")

		# 写回
		try:
			with open(fpath, 'w', encoding='utf-8') as f:
				yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
			self.logger.info(
				f"✓ 已自动修正 simulation_config.yaml 路径（项目文件 {len(matched_files)} 个）"
			)
		except Exception as exc:
			self.logger.warning(f"写回 simulation_config.yaml 失败: {exc}")

		# 6. 确保 agent_profile 已嵌入（fallback）
		self._ensure_agent_profile_in_simulation_config()

	def _extract_role_definitions_from_agent_profile(self, agent_profile_path: str) -> List[dict]:
		"""从 agent_profile.yaml 中提取角色定义。"""
		if not agent_profile_path or not os.path.exists(agent_profile_path):
			return []

		try:
			agent_profile_data = self._load_agent_profile_yaml(agent_profile_path)
		except Exception as exc:
			self.logger.warning(f"读取 agent_profile.yaml 失败: {exc}")
			return []

		agents_def = agent_profile_data.get('agents', []) if isinstance(agent_profile_data, dict) else []
		if not isinstance(agents_def, list):
			return []

		role_defs = []
		for index, agent_def in enumerate(agents_def):
			if not isinstance(agent_def, dict):
				continue
			extra = agent_def.get('extra', {})
			if not isinstance(extra, dict):
				extra = {}
			role_name = str(extra.get('role') or agent_def.get('name') or f'role_{index + 1}').strip()
			if not role_name:
				continue
			role_defs.append({
				'name': str(agent_def.get('name') or role_name).strip(),
				'role': role_name,
				'entity_type': str(agent_def.get('entity_type') or 'resident').strip(),
				'agent_def': agent_def,
			})

		return role_defs

	def _role_output_paths(self, role_name: str) -> tuple[str, str]:
		"""返回角色对应的新目录输出路径（prompts/actions）。"""
		role_name = (role_name or '').strip()
		prompt_rel_path = os.path.join('prompts', f'{role_name}.yaml')
		action_rel_path = os.path.join('actions', f'{role_name}.yaml')
		return os.path.join(self.config_dir, prompt_rel_path), os.path.join(self.config_dir, action_rel_path)

	async def generate_role_files_from_agent_profile(self, description_md, config_files, agent_profile_path=None):
		"""根据 agent_profile.yaml 为每个角色生成 prompts/actions 文件。"""
		if not agent_profile_path:
			agent_profile_path = os.path.join(self.config_dir, 'agent_profile.yaml')

		role_defs = self._extract_role_definitions_from_agent_profile(agent_profile_path)
		if not role_defs:
			self.logger.warning("未从 agent_profile.yaml 中解析到任何角色定义")
			return []

		generated_files = []
		for role_def in role_defs:
			role_name = role_def['role']
			entity_type = role_def.get('entity_type') or 'resident'
			prompt_path, action_path = self._role_output_paths(role_name)

			os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
			os.makedirs(os.path.dirname(action_path), exist_ok=True)

			prompt_content = ""
			action_content = ""
			prompt_should_write = True
			action_should_write = True
			prompt_exists = os.path.exists(prompt_path)
			action_exists = os.path.exists(action_path)

			if prompt_exists and not self._check_file_exists_and_ask(prompt_path, f"提示词文件 ({os.path.relpath(prompt_path, self.config_dir)})"):
				with open(prompt_path, 'r', encoding='utf-8') as f:
					prompt_content = f.read().strip()
				prompt_should_write = False
			if action_exists and not self._check_file_exists_and_ask(action_path, f"动作文件 ({os.path.relpath(action_path, self.config_dir)})"):
				with open(action_path, 'r', encoding='utf-8') as f:
					action_content = f.read().strip()
				action_should_write = False

			if prompt_content and action_content and prompt_exists and action_exists:
				self.logger.info(f"跳过生成，使用现有角色文件: {role_name}")
				generated_files.extend([prompt_path, action_path])
				continue

			prompt_template_content = ""
			prompt_template_candidates = [
				os.path.join(self._rag_project_root, 'config', 'template', 'entities', role_name, 'prompts.yaml'),
				os.path.join(self._rag_project_root, 'config', 'template', 'entities', entity_type, 'prompts.yaml'),
				os.path.join(self.config_template_dir, f'{role_name}_prompts.yaml'),
				os.path.join(self.config_template_dir, 'residents_prompts.yaml'),
			]
			for template_prompt in prompt_template_candidates:
				if os.path.exists(template_prompt):
					with open(template_prompt, 'r', encoding='utf-8') as f:
						prompt_template_content = f.read()
					self.logger.info(f"已读取角色提示词模板: {template_prompt}")
					break

			action_template_content = ""
			action_template_candidates = [
				os.path.join(self._rag_project_root, 'config', 'template', 'entities', role_name, 'actions.yaml'),
				os.path.join(self._rag_project_root, 'config', 'template', 'entities', entity_type, 'actions.yaml'),
				os.path.join(self.config_template_dir, f'{role_name}_actions.yaml'),
				os.path.join(self.config_template_dir, 'resident_actions.yaml'),
			]
			for template_action in action_template_candidates:
				if os.path.exists(template_action):
					with open(template_action, 'r', encoding='utf-8') as f:
						action_template_content = f.read()
					self.logger.info(f"已读取角色动作模板: {template_action}")
					break

			agent_profile_attrs_doc = ""
			all_attrs = set()
			attributes = role_def.get('agent_def', {}).get('attributes', [])
			if isinstance(attributes, list):
				for attr in attributes:
					if isinstance(attr, dict):
						attr_name = attr.get('name')
						if attr_name:
							all_attrs.add(str(attr_name))
			if all_attrs:
				agent_profile_attrs_doc = (
					"该角色在 agent_profile.yaml 中定义的属性包括：\n"
					+ "\n".join(f"  - {{{attr}}}" for attr in sorted(all_attrs))
					+ "\n请在提示词和动作模板中按需使用 {属性名} 作为占位符，不要编造未定义的属性。\n"
				)

			role_prompt = self.prompts.get('generate_role_files_prompt')
			prompt = role_prompt.format(
				role_name=role_name,
				role_type=role_name,
				entity_type=entity_type,
				description_md=description_md,
				prompt_template_content=prompt_template_content,
				action_template_content=action_template_content,
				template_content=prompt_template_content,
				template_content_action=action_template_content,
				agent_profile_attrs_doc=agent_profile_attrs_doc,
			)

			response = await self.generate_llm_response(prompt)
			if not response:
				self.logger.warning(f"LLM返回空响应，跳过角色 {role_name}")
				continue

			prompt_rel_path = os.path.relpath(prompt_path, self.config_dir).replace('\\', '/')
			action_rel_path = os.path.relpath(action_path, self.config_dir).replace('\\', '/')
			prompt_patterns = [
				rf'```yaml\s*# {re.escape(prompt_rel_path)}\s*([\s\S]*?)```',
				rf'```yaml\s*# {re.escape(os.path.basename(prompt_path))}\s*([\s\S]*?)```',
			]
			action_patterns = [
				rf'```yaml\s*# {re.escape(action_rel_path)}\s*([\s\S]*?)```',
				rf'```yaml\s*# {re.escape(os.path.basename(action_path))}\s*([\s\S]*?)```',
			]

			if prompt_should_write:
				prompt_content = prompt_content or ""
				for pattern in prompt_patterns:
					match = re.search(pattern, response, re.DOTALL)
					if match:
						prompt_content = match.group(1).strip()
						break

			if action_should_write:
				action_content = action_content or ""
				for pattern in action_patterns:
					match = re.search(pattern, response, re.DOTALL)
					if match:
						action_content = match.group(1).strip()
						break

			if prompt_should_write or action_should_write:
				code_blocks = re.findall(r'```yaml\s*([\s\S]*?)```', response, re.DOTALL)
				if code_blocks:
					if prompt_should_write and not prompt_content:
						prompt_content = code_blocks[0].strip()
					if action_should_write and not action_content:
						index = 1 if prompt_should_write and len(code_blocks) > 1 else 0
						if len(code_blocks) > index:
							action_content = code_blocks[index].strip()

			if prompt_should_write and not prompt_content and prompt_template_content:
				prompt_content = prompt_template_content.strip()
			if action_should_write and not action_content and action_template_content:
				action_content = action_template_content.strip()

			if prompt_should_write:
				with open(prompt_path, 'w', encoding='utf-8') as f:
					f.write(prompt_content.strip())
				self.logger.info(f"生成角色提示词文件: {prompt_path}")
			generated_files.append(prompt_path)

			if action_should_write:
				with open(action_path, 'w', encoding='utf-8') as f:
					f.write(action_content.strip())
				self.logger.info(f"生成角色动作文件: {action_path}")
			generated_files.append(action_path)

		return generated_files


	def _load_agent_profile_attrs_text(self) -> str:
		"""从 agent_profile.yaml 提取属性清单文本，供 resident 模块接口文档拼接引用。"""
		profile_path = os.path.join(self.config_dir, "agent_profile.yaml")
		if not os.path.exists(profile_path):
			return "（未找到 agent_profile.yaml）"
		try:
			with open(profile_path, "r", encoding="utf-8") as f:
				profile = yaml.safe_load(f) or {}
			all_attrs = set()
			agents_list = profile.get("agents", [])
			if not agents_list and "entity_type" in profile:
				agents_list = [profile]
			for agent_def in agents_list:
				attrs = agent_def.get("attributes", {})
				if isinstance(attrs, list):
					for attr in attrs:
						name = attr.get("name") if isinstance(attr, dict) else None
						if name:
							all_attrs.add(str(name))
				elif isinstance(attrs, dict):
					all_attrs.update(attrs.keys())
			if not all_attrs:
				return "（agent_profile.yaml 中未找到属性定义）"
			lines_out = ["agent_profile 中定义的属性："]
			lines_out.extend(f"  - {a}" for a in sorted(all_attrs))
			lines_out.append("residents 模块的 param 必须与上述属性名严格一致。")
			return "\n".join(lines_out)
		except Exception as e:
			return f"（读取 agent_profile.yaml 失败: {e}）"

	def _read_relevant_api_docs(self, config_filename):
		"""根据配置文件名读取相关接口文件（src/interfaces）。
		
		Args:
			config_filename: 配置文件名
		
		Returns:
			str: 格式化的接口文件内容字符串（精简版）
		"""
		config_to_modules = {
			'simulation_config.yaml': ['time', 'map', 'population'],
			'jobs_config.yaml': ['job_market', 'resident'],
			'resident_actions.yaml': ['resident', 'social_network'],
			'towns_data.json': ['towns', 'map'],
			'government_prompts.yaml': ['government'],
			'rebels_prompts.yaml': ['rebels'],
			'residents_prompts.yaml': ['resident', 'social_network'],
		}
		relevant_modules = config_to_modules.get(config_filename, [])
		return self._read_interface_docs_for_modules(relevant_modules, max_chars_per_file=1500)

	async def _ask_user_retry_action(self, step_name, file_path=None):
		"""当某个步骤达到最大重试次数后，询问用户是继续重试、重新生成还是放弃。

		自动模式下默认选择重新生成（regenerate）。

		Returns:
			str: 'retry' | 'regenerate' | 'abort'
		"""
		if self.auto_mode:
			self.logger.info(f"自动模式：默认选择重新生成 ({step_name})")
			return 'regenerate'

		print(f"\n{'='*60}")
		print(f"⚠️ {step_name} 在多次尝试后仍未能成功")
		if file_path:
			print(f"相关文件: {file_path}")
		print(f"{'='*60}")

		# Web模式
		if self.session:
			try:
				self.session['waiting_confirmation'] = True
				self.session['confirmation_message'] = f"{step_name} 多次尝试后仍未成功，请选择操作"
				self.session['confirmation_type'] = 'options'
				self.session['confirmation_options'] = [
					{'label': '继续重试', 'value': 'retry'},
					{'label': '重新生成', 'value': 'regenerate'},
					{'label': '放弃', 'value': 'abort'},
				]
				self.session['user_confirmation'] = None

				max_wait_time = 300
				wait_time = 0
				while wait_time < max_wait_time:
					if not self.session.get('waiting_confirmation', False):
						result = self.session.get('user_confirmation', 'regenerate')
						if result in ('retry', 'regenerate', 'abort'):
							return result
						return 'regenerate'
					time.sleep(0.5)
					wait_time += 0.5

				self.session['waiting_confirmation'] = False
				self.logger.warning("等待用户选择超时，默认重新生成")
				return 'regenerate'
			except Exception as e:
				self.logger.warning(f"Web模式交互失败: {e}，使用命令行模式")

		# CLI模式
		print("请选择操作：")
		print("  [1] 继续重试")
		print("  [2] 重新生成（默认）")
		print("  [3] 放弃")

		user_input = input("请输入选项 (1/2/3): ").strip()
		if user_input == '1':
			return 'retry'
		if user_input == '3':
			return 'abort'
		return 'regenerate'

	async def _extract_module_api_docs_from_error(self, error_traceback):
		"""
		从错误堆栈中提取相关模块和配置文件
		使用LLM智能分析错误信息，判断需要哪些接口文件和配置文件
		
		Args:
			error_traceback: 错误堆栈信息
		
		Returns:
			tuple: (api_docs_str, config_files_dict)
				- api_docs_str: 接口文件内容字符串
				- config_files_dict: 配置文件内容字典 {文件名: 内容}
		"""
		def _camel_to_snake(name: str) -> str:
			if not name:
				return ""
			# e.g. SocialNetwork -> social_network
			s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
			return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

		def _normalize_module_token(token: str) -> str:
			"""将 token（可能是文件名/模块名/CamelCase/旧md名）归一化为 module_name（如 map, social_network）。"""
			base = (token or "").strip()
			if not base:
				return ""
			# 去扩展名
			base = re.sub(r'\.(py|md|txt|yaml|yml)$', '', base, flags=re.IGNORECASE)
			# 去 i 前缀（接口文件常见）
			if base.startswith('i') and len(base) > 1 and base[1].isalpha() and base[1].islower():
				base = base[1:]
			# CamelCase -> snake_case
			if re.match(r'^[A-Z][A-Za-z0-9]*$', base):
				base = _camel_to_snake(base)
			return base.strip().lower()

		# 扫描 src/interfaces，动态生成“模块->接口文件”索引
		interfaces_dir = self._interfaces_dir()
		available_iface_files: List[str] = []
		if os.path.isdir(interfaces_dir):
			try:
				available_iface_files = sorted(
					[f for f in os.listdir(interfaces_dir) if f.startswith('i') and f.endswith('.py')]
				)
			except Exception:
				available_iface_files = []

		module_mapping_str = "\n".join(
			[f"- {f[1:-3]}: {f}" for f in available_iface_files]
		) or "（未找到接口文件）"
		
		# 读取配置文件和提示词文件列表
		config_files_list = ""
		available_config_files = []
		if os.path.exists(self.config_dir):
			try:
				files = os.listdir(self.config_dir)
				available_config_files = [f for f in files if os.path.isfile(os.path.join(self.config_dir, f))]
				if available_config_files:
					config_files_list = "配置目录中的文件：\n" + "\n".join([f"- {f}" for f in sorted(available_config_files)])
				else:
					config_files_list = "（配置目录为空）"
			except Exception as e:
				self.logger.warning(f"读取配置目录失败: {e}")
				config_files_list = "（无法读取配置目录）"
		else:
			config_files_list = "（配置目录不存在）"
		
		# 使用LLM分析错误信息
		prompt = self.prompts['analyze_error_modules_prompt'].format(
			error_traceback=error_traceback,
			module_mapping=module_mapping_str,
			config_files_list=config_files_list
		)
		
		response = await self.generate_llm_response(prompt)
		relevant_api_files = []
		relevant_config_files = []
		
		if response:
			# 尝试从LLM响应中提取JSON对象
			json_match = re.search(r'\{[\s\S]*?\}', response)
			if json_match:
				try:
					result = json.loads(json_match.group(0))
					relevant_api_files = result.get('api_docs', [])
					relevant_config_files = result.get('config_files', [])
					self.logger.info(f"✓ LLM分析识别到 {len(relevant_api_files)} 个接口文件: {relevant_api_files}")
					self.logger.info(f"✓ LLM分析识别到 {len(relevant_config_files)} 个配置文件: {relevant_config_files}")
				except json.JSONDecodeError as e:
					self.logger.warning(f"解析LLM返回的JSON失败: {e}")
		else:
			self.logger.warning("LLM返回空响应，使用兜底方案")
		
		# 兜底方案：如果LLM分析失败，使用正则匹配（从类名推断模块名）
		if not relevant_api_files:
			module_pattern = r"'(\w+)'\s+object\s+has\s+no\s+attribute"
			matches = re.findall(module_pattern, error_traceback)
			relevant_api_files = [_normalize_module_token(m) for m in matches if _normalize_module_token(m)]
			if relevant_api_files:
				self.logger.info(f"✓ 正则匹配识别到 {len(relevant_api_files)} 个接口文件: {relevant_api_files}")
		
		# 读取相关模块的接口文件（按需在 interfaces 目录中动态查找）
		api_docs_str = ""
		loaded_files: set[str] = set()
		for token in set(relevant_api_files):  # 去重
			module_name = _normalize_module_token(token)
			if not module_name:
				continue
			for iface_path in self._find_interface_files(module_name):
				iface_file = os.path.basename(iface_path)
				if iface_file in loaded_files:
					continue
				loaded_files.add(iface_file)
				try:
					with open(iface_path, 'r', encoding='utf-8') as f:
						content = f.read()
					api_docs_str += f"\n## {module_name} 模块接口 ({iface_file})\n{content}\n"
					self.logger.info(f"✓ 已加载接口文件: {iface_file} (module={module_name})")
				except Exception as e:
					self.logger.warning(f"读取接口文件失败 {iface_file}: {e}")
		
		# 读取相关的配置文件
		config_files_dict = {}
		for config_file in set(relevant_config_files):  # 去重
			# 验证文件确实存在于可用列表中
			if config_file in available_config_files:
				config_path = os.path.join(self.config_dir, config_file)
				try:
					with open(config_path, 'r', encoding='utf-8') as f:
						content = f.read()
						config_files_dict[config_file] = content
						self.logger.info(f"✓ 已读取配置文件: {config_file}")
				except Exception as e:
					self.logger.warning(f"读取配置文件失败 {config_file}: {e}")
			else:
				self.logger.warning(f"配置文件不在可用列表中: {config_file}")
		
		return api_docs_str, config_files_dict

	async def _handle_file_not_found_error(self, error_traceback, config_path):
		"""
		处理 FileNotFoundError
		"""
		self.logger.info("处理 FileNotFoundError...")
		# 从错误堆栈中解析文件路径
		match = re.search(r"FileNotFoundError: \[Errno 2\] No such file or directory: '(.+?)'", error_traceback)
		if not match:
			return False

		file_path = match.group(1)
		self.logger.info(f"检测到缺失文件: {file_path}")

		# 检查文件是否真的不存在
		if os.path.exists(file_path):
			self.logger.info(f"文件 {file_path} 实际存在，跳过处理。")
			return False
		
		# 判断文件类型并调用相应函数
		description_md = ""
		modules_config_yaml = ""
		config_files = {}
		if config_path:
			description_md_path = os.path.join(os.path.dirname(config_path), 'description.md')
			modules_config_yaml_path = os.path.join(os.path.dirname(config_path), 'modules_config.yaml')
			with open(description_md_path, 'r', encoding='utf-8') as f:
				description_md = f.read()
			if os.path.exists(modules_config_yaml_path):
				with open(modules_config_yaml_path, 'r', encoding='utf-8') as f:
					modules_config_yaml = f.read()
					config_files['modules_config.yaml'] = modules_config_yaml
		filename = os.path.basename(file_path)
		if 'prompt' in filename:
			await self.generate_role_files_from_agent_profile(description_md, config_files)
		else:
			await self.generate_config_file(filename, description_md, modules_config_yaml)
		
		return True

	async def fix_runtime_errors(self, error_message, error_traceback, main_file_path, simulator_file_path, config_path, max_attempts=3):
		"""
		运行时错误修复函数 - 使用增量修改方式
		支持同时修复 main 和 simulator 文件
		
		Args:
			error_message: 错误信息
			error_traceback: 完整的错误堆栈
			main_file_path: main文件路径
			simulator_file_path: simulator文件路径
			max_attempts: 最大修复尝试次数
		
		Returns:
			bool: 是否修复成功
		"""
		self.logger.info("🔧 开始修复运行时错误...")

		# 首先检查是否是 FileNotFoundError
		if "FileNotFoundError" in error_message:
			if await self._handle_file_not_found_error(error_traceback, config_path):
				self.logger.info("✓ 已成功处理 FileNotFoundError 并生成了缺失文件。")
				return True # 假设文件生成后问题就解决了，直接返回成功

		
		# 读取当前代码
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
				main_file_path=main_file_path,
				main_content=main_content,
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
		
		# 应用main文件的增量修改
		if main_json_match:
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
					file_path = os.path.join(self.config_dir, file_name)
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
				file_path = os.path.join(self.config_dir, file_name)

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

	async def modify_file_sequentially(self, diagnosis_path, config_dir, design_doc=""):
		"""
		根据 diagnosis_path 路径依次修改配置文件或代码文件。
		diagnosis_path: 包含诊断结果的 JSON 文件路径
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

		results = []
		for file_info in files_to_modify:
			file_name = file_info.get('file_name')
			file_type = file_info.get('file_type')
			reason = file_info.get('modification', '') # Changed from 'reason'

			self.logger.info(f"正在处理文件 : {file_name} (类型: {file_type})")
			self.logger.info(f"修改原因: {reason}")

			if file_type == 'simulator':
				simulator_file_name = f'simulator_{self.simulation_name}.py'
				file_path = os.path.join(self.simulator_output_dir, simulator_file_name)
			else:
				file_path = os.path.join(config_dir, file_name)
					
			if not os.path.exists(file_path):
				self.logger.warning(f"文件不存在: {file_path}")
				continue

			# 读取
			with open(file_path, 'r', encoding='utf-8') as f:
				current_content = f.read()

			if file_type == 'simulator':
				# 使用专门为修改代码设计的prompt
				prompt = self.prompts['generate_simulator_modifications_prompt'].format(
					diagnosis_result=json.dumps(file_info, ensure_ascii=False),
					current_code=current_content[:8000], # 代码可以给多一点
					design_doc=design_doc
				)
				response = await self.generate_llm_response(prompt)
				# 调用 apply_code_changes
				if response:
					result = self._apply_code_changes(file_path, response, "simulator")
					results.append({'file_name': simulator_file_name, 'result': 'success' if result else 'failed'})
					if result:
						self.logger.info(f"✓ {simulator_file_name} 已修改")
					else:
						self.logger.error(f"✗ {simulator_file_name} 修改失败")

			else: # config or prompt files
				# 生成修改方案
				prompt = self.prompts['generate_config_modifications_prompt'].format(
					diagnosis_result=json.dumps(file_info, ensure_ascii=False),
					current_config=current_content[:5000],
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
							result = self._apply_modifications(file_path, modification_list)
							results.append({'file_name': file_name, 'result': result})
							self.logger.info(f"✓ {file_name} 已修改")

					except json.JSONDecodeError as e:
						self.logger.error(f"解析失败 {file_name}: {e}")

		return results

	def _apply_modifications(self, file_path, modifications, create_if_missing=False):
		"""
		精确修改文件中的指定参数，保持文件结构不变。
		支持 yaml/json/文本三种类型的参数替换。
		支持通过点分路径（e.g. 'a.b.c'）进行深层嵌套修改和新增。

		Args:
			create_if_missing: 文件不存在时，根据 modifications 创建新文件（仅对 yaml/json 有效）
		"""
		changes = []
		# 文件不存在时，根据 create_if_missing 初始化空结构
		if not os.path.exists(file_path):
			if not create_if_missing:
				return {'changes': [], 'error': f'文件不存在: {file_path}'}
			self.logger.info(f"基于 modifications 创建新文件: {file_path}")
			original_content = "{}" if file_path.endswith('.json') else ""
			# yaml 用空字符串，yaml.safe_load('') -> None，下方会处理
		else:
			# 备份原文件
			backup_path = file_path + f'.backup'
			shutil.copy(file_path, backup_path)
			with open(file_path, 'r', encoding='utf-8') as f:
				original_content = f.read()

		def _set_nested_value(data_dict, path, value):
			keys = path.split('.')
			temp_dict = data_dict
			for key in keys[:-1]:
				# 如果路径中的某个键对应的值不是字典，就创建一个新字典
				if not isinstance(temp_dict.get(key), dict):
					temp_dict[key] = {}
				temp_dict = temp_dict[key]
			
			last_key = keys[-1]
			old_value = temp_dict.get(last_key)
			temp_dict[last_key] = value
			return old_value

		# YAML 文件
		if file_path.endswith(('.yaml', '.yml')):
			try:
				data = yaml.safe_load(original_content)
			except yaml.YAMLError as e:
				self.logger.error(f"配置文件已损坏，无法应用参数级修改: {file_path}, {e}")
				return {'changes': [], 'error': f'配置文件语法已损坏，需重写修复: {e}'}
			if data is None:
				data = {}
			for mod in modifications:
				param = mod.get('parameter')
				new_value = mod.get('value')
				if param:
					old_value = _set_nested_value(data, param, new_value)
					changes.append(f"{param}: {old_value} -> {new_value}")
			with open(file_path, 'w', encoding='utf-8') as f:
				yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
		# JSON 文件
		elif file_path.endswith('.json'):
			data = json.loads(original_content) if original_content.strip() else {}
			for mod in modifications:
				param = mod.get('parameter')
				new_value = mod.get('value')
				if param:
					old_value = _set_nested_value(data, param, new_value)
					changes.append(f"{param}: {old_value} -> {new_value}")
			with open(file_path, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=2, ensure_ascii=False)
		# 纯文本文件（如提示词）
		else:
			content = original_content
			for mod in modifications:
				old_text = mod.get('parameter')
				new_text = mod.get('value')
				if old_text in content:
					content = content.replace(old_text, new_text)
					changes.append(f"已替换文本片段")
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(content)

		return {'changes': changes}

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
			simulator_path = None
			main_path = None
			
			# 查找 simulator 和 main 文件
			if os.path.exists(self.simulator_output_dir):
				simulator_file = f'simulator_{self.simulation_name}.py'
				simulator_path = os.path.join(self.simulator_output_dir, simulator_file)
			
			if os.path.exists(self.main_output_dir):
				main_file = f'main_{self.simulation_name}.py'
				main_path = os.path.join(self.main_output_dir, main_file)
			
			if not simulator_path or not os.path.exists(simulator_path):
				self.logger.error(f"Simulator文件不存在: {simulator_path}")
				return False
				
			if not main_path or not os.path.exists(main_path):
				self.logger.error(f"Main文件不存在: {main_path}")
				return False
			
			# 读取代码内容
			with open(simulator_path, 'r', encoding='utf-8') as f:
				simulator_content = f.read()
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
			success = self._apply_runtime_fix(response, main_path, simulator_path)
			
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