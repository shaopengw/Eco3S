import json
import time
from typing import Dict, List, Optional, Tuple

from src.utils.custom_logger import CustomLogger
from src.utils.ai_system_config import get_agent_model
from .shared_imports import *
from .code_change_mixin import CodeChangeMixin

import chromadb
from openai import OpenAI


def exogenous_slug(module: str, param: str) -> str:
	"""把 (module, param) 规范化为外生变量的 context key / CSV 列名。

	例：("time", "policy implementation period") -> "time_policy_implementation_period"
	"""
	import re as _re
	module = str(module or "").strip()
	param = str(param or "").strip()
	base = f"{module}_{param}".lower()
	# 非字母数字一律转下划线，并压缩连续下划线
	base = _re.sub(r"[^a-z0-9]+", "_", base)
	return _re.sub(r"_+", "_", base).strip("_")


def extract_exogenous_nodes(pairs: List[dict]) -> List[dict]:
	"""从 influence_pairs 列表中提取「只作为 cause、从不作为 effect」的根驱动节点。

	Args:
		pairs: influence_pairs.json 解析出的列表。

	Returns:
		去重后的纯 cause 节点列表，每项 {"module", "param", "slug"}。
	"""
	causes = set()
	effects = set()
	for p in pairs or []:
		if not isinstance(p, dict):
			continue
		c = p.get("cause") or {}
		e = p.get("effect") or {}
		cm, cp = str(c.get("module") or "").strip(), str(c.get("param") or "").strip()
		em, ep = str(e.get("module") or "").strip(), str(e.get("param") or "").strip()
		if cm and cp:
			causes.add((cm, cp))
		if em and ep:
			effects.add((em, ep))
	pure = causes - effects
	# 保持稳定顺序：按 module、param 排序
	nodes = []
	for (m, p) in sorted(pure):
		nodes.append({"module": m, "param": p, "slug": exogenous_slug(m, p)})
	return nodes


def exogenous_pair_id_to_slug(pairs: List[dict]) -> Dict[int, str]:
	"""构建 {pair_id: slug}，仅包含 cause 为纯 cause 根驱动节点的 pair。

	用于在 influence 块生成后，按 pair_id 定位需要重定向到外生变量的块。
	"""
	pure_keys = {(n["module"], n["param"]) for n in extract_exogenous_nodes(pairs)}
	mapping: Dict[int, str] = {}
	for p in pairs or []:
		if not isinstance(p, dict):
			continue
		c = p.get("cause") or {}
		cm, cp = str(c.get("module") or "").strip(), str(c.get("param") or "").strip()
		pid = p.get("pair_id")
		if pid is not None and (cm, cp) in pure_keys:
			mapping[int(pid)] = exogenous_slug(cm, cp)
	return mapping


def apply_exogenous_source_override(block_data: dict, slug: str, source_module: str) -> bool:
	"""把 influence 块中「来自 source 模块的 cause 输入」重定向到外生变量。

	策略（保证向后兼容）：
	  - 仅改写 source.inputs 中、其 path/fallback_paths 引用了 source 模块的输入
	    （即 cause 派生量，如 elapsed_steps 的 module.get_elapsed_time_steps()）；
	  - 把 context.exogenous.<slug> 设为该输入的首选 path，原有 path 全部降级为
	    fallback_paths —— 这样数据文件缺失/列不存在时会自动回退到内部计算值；
	  - 在块上打 exogenous: true 标记（信息性，运行时不跳过）。

	Returns:
		是否成功重定向了至少一个输入。
	"""
	if not isinstance(block_data, dict) or not slug:
		return False
	source = block_data.get("source")
	if not isinstance(source, dict):
		return False
	inputs = source.get("inputs")
	if not isinstance(inputs, dict) or not inputs:
		return False

	exo_path = f"context.exogenous.{slug}"
	module_token = str(source_module or "").strip()
	redirected = False

	def _refs_source_module(spec) -> bool:
		paths = []
		if isinstance(spec, str):
			paths = [spec]
		elif isinstance(spec, dict):
			if spec.get("path"):
				paths.append(str(spec["path"]))
			paths.extend(str(x) for x in (spec.get("fallback_paths") or []))
		for pth in paths:
			head = pth.split(".")[0] if pth else ""
			if head == "module":
				return True
			if module_token and head == module_token:
				return True
		return False

	for var_name, spec in list(inputs.items()):
		if not _refs_source_module(spec):
			continue
		# 收集原有 path，全部降级为 fallback
		old_paths: List[str] = []
		if isinstance(spec, str):
			old_paths = [spec]
			new_spec: dict = {}
		elif isinstance(spec, dict):
			new_spec = dict(spec)
			if new_spec.get("path"):
				old_paths.append(str(new_spec["path"]))
			old_paths.extend(str(x) for x in (new_spec.get("fallback_paths") or []))
		else:
			continue
		# 去重，排除已是 exo_path 的项
		fallback = [p for p in old_paths if p and p != exo_path]
		new_spec["path"] = exo_path
		if fallback:
			new_spec["fallback_paths"] = fallback
		new_spec.setdefault("coerce", "float")
		inputs[var_name] = new_spec
		redirected = True

	if redirected:
		block_data["exogenous"] = True
	return redirected


class CodeArchitectAgent(CodeChangeMixin, BaseAgent):
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
		# 指定使用 KIMI 的 kimi-k2-0905-preview 模型
		# super().__init__(agent_id, group_type='code_architect', window_size=3,
		#                  model_api_name='KIMI', model_type_name='kimi-k2-0905-preview')
		# 指定使用 CLAUDE 的 claude-sonnet-4-5-20250929 模型
		_api, _model = get_agent_model('code_architect')
		super().__init__(agent_id, group_type='code_architect', window_size=3,
		                 model_api_name=_api, model_type_name=_model)
		# super().__init__(agent_id, group_type='research_analyst', window_size=3)
		
		# 加载prompts配置
		prompts_path = os.path.join(os.path.dirname(__file__), 'code_architect_prompts.yaml')
		with open(prompts_path, 'r', encoding='utf-8') as f:
			self.prompts = yaml.safe_load(f)
		
		self.system_message = self.prompts['system_message']
		self.simulator_output_dir = simulator_output_dir  # src/simulation/（保留兼容，但新项目不再使用）
		self.main_output_dir = main_output_dir  # entrypoints/（保留兼容，但新项目不再使用）
		self.docs_dir = docs_dir
		self.config_dir = config_dir  # projects/<name>/config/
		self.project_dir = os.path.dirname(config_dir)  # projects/<name>/
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
		# RAG 共享 client：避免 Phase1 并行检索时同时打开多个 PersistentClient 导致 HNSW 索引冲突
		self._chroma_client = None



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

				# LLM 可能未严格遵循 plugin_class 约束，硬性同步 __init__.py 与 manifest
				manifest = pg.sync_plugin_exports(project_root, plugin_name, manifest)
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

		# 目标文件路径：统一放到项目目录下
		os.makedirs(self.project_dir, exist_ok=True)
		fpath = os.path.join(self.project_dir, 'simulator.py')

		# 检查文件是否已存在
		if not self._check_file_exists_and_ask(fpath, "Simulator代码 (simulator.py)"):
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

		# 步骤3.6：确保 simulator 使用绝对导入（适配 projects/<name>/ 布局）
		self._ensure_absolute_simulator_imports(fpath)

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

		# 确保 simulator 使用绝对导入
		self._ensure_absolute_simulator_imports(simulator_file_path)

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
			# 步骤0：初始候选生成 —— 优先因果图拓扑路径发现，论文库降为后备
			rag_cfg = self._rag_get_config()
			disc_cfg = rag_cfg.get('l0_graph_discovery', {}) if isinstance(rag_cfg, dict) else {}
			l0_enabled = disc_cfg.get('enabled', True)
			graph_candidate_chains = ""
			graph_chains: List[str] = []

			if l0_enabled:
				# 0a：LLM 抽取英文可量化变量概念（覆盖驱动/机制/结果，跨因果两端），用于图锚定
				concepts: List[str] = []
				metrics_prompt = (self.prompts or {}).get('extract_key_metrics_prompt')
				if metrics_prompt:
					try:
						concept_resp = await self.generate_llm_response(
							metrics_prompt.format(description_md=description_md)
						)
						parsed_concepts = parse_json_array(concept_resp)
						concepts = [str(c).strip() for c in parsed_concepts if isinstance(c, str) and str(c).strip()]
						concepts = concepts[:int(disc_cfg.get('max_concepts', 5))]
						self.logger.info(f"步骤0 概念抽取: {concepts}")
					except Exception as exc:
						self.logger.warning(f"步骤0 概念抽取失败，将回退论文检索: {exc}")
				# 0b：因果图拓扑路径发现
				if concepts:
					graph_chains = self._rag_discover_graph_chains(
						concepts, top_k=int(disc_cfg.get('top_k_chains', 5))
					)
				if graph_chains:
					graph_candidate_chains = "【因果图发现的候选传导链（优先级最高）】\n" + "\n".join(graph_chains)
					self.logger.info(f"步骤0 图路径发现: {len(graph_chains)}条候选传导链")

			# 论文库检索：L0 关闭、或图链条不足时作为后备补充
			paper_candidates_context = ""
			fallback_min = int(disc_cfg.get('fallback_min_chains', 3))
			if (not l0_enabled) or (len(graph_chains) < fallback_min):
				paper_candidates = self._rag_query_paper_candidates(description_md, top_k=3)
				if paper_candidates:
					paper_candidates_context = "【论文库检索到的参考影响对】\n" + "\n".join(paper_candidates)
					# 统计实际影响对数量（paper_candidates包含标题行、影响对行和空行）
					actual_pair_count = sum(1 for s in paper_candidates if s.startswith('- '))
					self.logger.info(f"步骤0 论文候选检索(后备): {actual_pair_count}条影响对 (来自{len([s for s in paper_candidates if s.startswith('论文:')])}篇论文)")

			# 步骤1：依据设计文档+modules_config+图链条+论文候选先产出粗粒度影响对清单
			response = await self.generate_llm_response(pairs_prompt.format(
				description_md=description_md,
				modules_config_yaml=modules_config_yaml,
				graph_candidate_chains=graph_candidate_chains,
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
				# 步骤2：检索 + 生成增强（2a直接证据 + 2b相关声明 + 2c调节变量论文）
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

					# 检索 2a/2b/2c：2a/2b 都访问 causal_claims，串行；2c 访问 papers，与 2a/2b 并行
					cfg = self._rag_get_config()
					use_funnel = cfg.get('funnel_enabled', True)

					if use_funnel:
						cache_hit = self._rag_cache_get(cause_param, effect_param)
						if cache_hit is not None:
							rag_context, counts = cache_hit
							has_evidence = bool(rag_context)
						else:
							jel = self._rag_gate_jel(cause_param or cause_module, cfg['l1_jel'].get('top_n', 2)) \
								if cfg.get('l1_jel', {}).get('enabled', True) else []
							pool = self._rag_funnel_retrieve(
								cause_param or cause_module,
								effect_param or effect_module,
								query,
								jel,
							)
							rag_context, picked = self._rag_rank_and_fill(
								pool,
								cfg.get('priority_weights', {}),
								cfg['budget'].get('max_chars', 2500),
							)
							counts = {
								'direct': picked,
								'related': len(pool) - picked,
								'moderator': 0,
								'jel': jel,
							}
							self._rag_cache_set(cause_param, effect_param, (rag_context, counts))
							has_evidence = bool(rag_context)
					else:
						moderator_task = asyncio.create_task(asyncio.to_thread(
							self._rag_query_moderator_papers, cause_param or cause_module, effect_param or effect_module
						))
						direct_evidence = await asyncio.to_thread(self._rag_query_causal_claims, query, 3)
						related_evidence = await asyncio.to_thread(
							self._rag_query_related_claims, cause_param or cause_module, effect_param or effect_module
						)
						moderator_papers = await moderator_task

						# 测试输出：便于观察每个 pair 的三类检索结果
						print(f"[generate_influences] 步骤2 Phase1 pair_id={pair_id} (2a直接证据:{len(direct_evidence)}条, 2b相关影响对:{len(related_evidence)}条, 2c调节论文:{len(moderator_papers)}条), query={query!r}, cause_module={cause_module!r}, effect_module={effect_module!r}")

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
						counts = {
							'direct': len(direct_evidence),
							'related': len(related_evidence),
							'moderator': len(moderator_papers),
						}

					return {
						'pair_id': pair_id,
						'pair': pair,
						'rag_context': rag_context,
						'has_evidence': has_evidence,
						'evidence_counts': counts,
					}

				# Phase 1: 顺序处理每条影响对（每对内部3个RAG查询仍并发），避免多个影响对同时触发HNSW索引冲突
				self.logger.info(f"步骤2 Phase1: 顺序检索 {total_pairs} 条影响对的RAG证据...")
				evidence_results = []
				for pair in structured_pairs:
					evidence_results.append(await _retrieve_evidence(pair))
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

		# 前置声明：从磁盘 influence_pairs.json（原始 param）计算纯 cause 根驱动节点，
		# 建立 {pair_id: slug}。与编码后阶段 3.45 读取同一份磁盘文件，保证 slug 一致。
		pid_to_slug: Dict[int, str] = {}
		try:
			if os.path.exists(pairs_path):
				with open(pairs_path, 'r', encoding='utf-8') as pf:
					disk_pairs = json.load(pf)
				if isinstance(disk_pairs, list):
					pid_to_slug = exogenous_pair_id_to_slug(disk_pairs)
			if pid_to_slug:
				self.logger.info(f"步骤3.5 外生变量前置声明: 纯cause块 pair_id={sorted(pid_to_slug.keys())}")
		except Exception as exc:
			self.logger.warning(f"计算外生变量纯cause节点失败，跳过前置声明: {exc}")
			pid_to_slug = {}

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

			# 前置声明：若该块的 cause 是纯 cause 根驱动，将其来自 source 模块的输入
			# 重定向到 context.exogenous.<slug>（原 path 降级为 fallback，保证回退兼容）。
			try:
				pid_key = int(pair_id) if pair_id is not None else None
			except (TypeError, ValueError):
				pid_key = None
			if pid_key is not None and pid_key in pid_to_slug:
				if apply_exogenous_source_override(block_data, pid_to_slug[pid_key], source_module):
					self.logger.info(
						f"  ↳ pair_id={pair_id} 已声明外生变量输入: context.exogenous.{pid_to_slug[pid_key]}"
					)
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
				expected_path = f"projects/{self.simulation_name}/config/agent_profile.yaml"
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
					data_cfg[key] = f"projects/{self.simulation_name}/config/{filename}"
					matched_files.append(filename)

			# 3.5 特殊：存在 agent_profile.yaml 时加入 agent_profile_path，
			# 同时根据 agent_profile 里的 role 列表写入 role 级 prompts/actions 路径
			if os.path.exists(os.path.join(self.config_dir, 'agent_profile.yaml')):
				data_cfg['agent_profile_path'] = f"projects/{self.simulation_name}/config/agent_profile.yaml"
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
							data_cfg[f'{role_name}_prompt_path'] = f"projects/{self.simulation_name}/config/prompts/{role_name}.yaml"
							data_cfg[f'{role_name}_actions_path'] = f"projects/{self.simulation_name}/config/actions/{role_name}.yaml"
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



	



