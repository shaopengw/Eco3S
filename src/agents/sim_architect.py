

from src.utils.custom_logger import CustomLogger

from .shared_imports import *
import re

class SimArchitectAgent(BaseAgent):
	"""
	模拟设计师Agent，继承BaseAgent，负责通过大模型分析需求、选择模块、生成设计文档和配置。
	"""
	def __init__(self, agent_id, output_dir, docs_dir, config_dir, simulation_type):
		super().__init__(agent_id, group_type='sim_architect', window_size=3)
		self.output_dir = output_dir
		self.docs_dir = docs_dir
		self.config_dir = config_dir
		self.logger = CustomLogger('sim_architect').logger
		self.simulation_type = simulation_type
		self.last_module_selection = None
		
		# 加载提示词配置
		prompts_path = os.path.join(os.path.dirname(__file__), 'sim_architect_prompts.yaml')
		with open(prompts_path, 'r', encoding='utf-8') as f:
			self.prompts = yaml.safe_load(f)
		
		self.system_message = self.prompts['system_message']

	def _load_plugins_config(self):
		"""读取并解析 config/plugins.yaml，返回 dict；失败则返回空结构。"""
		plugins_path = os.path.join(os.path.dirname(os.path.abspath(self.config_dir)), 'plugins.yaml')
		try:
			with open(plugins_path, 'r', encoding='utf-8') as f:
				return yaml.safe_load(f) or {}
		except Exception as e:
			self.logger.warning(f"读取插件配置失败: {plugins_path}, {e}")
			return {}

	def _plugins_catalog_text(self, max_plugins=None):
		"""将 plugins.yaml 转成适合提示词的简洁清单文本（name/description/dependencies）。"""
		cfg = self._load_plugins_config()
		plugins = (cfg or {}).get('plugins', []) or []
		if max_plugins is not None:
			plugins = plugins[:max_plugins]
		lines = [
			"可用插件清单（来自 config/plugins.yaml）：",
		]
		for p in plugins:
			name = p.get('name', '')
			meta = p.get('metadata', {}) or {}
			desc = meta.get('description', '')
			lines.append(f"-name: {name},description: {desc}")
		return "\n".join(lines)

	def _extract_yaml_text(self, response: str) -> str:
		"""尽可能从 LLM 输出中提取 YAML 纯文本。

		常见情况：模型会输出 ```yaml ... ``` 或 ```yaml:modules_config.yaml ... ``` 代码块。
		这里做容错提取，避免因为格式不严谨触发兜底空配置。
		"""
		if not response or not isinstance(response, str):
			return ""

		text = response.strip()
		if not text:
			return ""

		# 优先匹配带文件名的代码块：```yaml:modules_config.yaml ...```
		m = re.search(r"```(?:yaml|yml)(?::[^\n]+)?\s*\n([\s\S]*?)\n```", text, re.IGNORECASE)
		if m:
			return m.group(1).strip()

		# 其次匹配通用代码块：``` ... ```
		m = re.search(r"```\s*\n([\s\S]*?)\n```", text)
		if m:
			return m.group(1).strip()

		return text

	def _enabled_plugin_names(self) -> set:
		cfg = self._load_plugins_config()
		plugins = (cfg or {}).get('plugins', []) or []
		enabled = set()
		for p in plugins:
			try:
				if p.get('enabled', True):
					enabled.add(p.get('name'))
			except Exception:
				continue
		return enabled

	def _ensure_modules_config_from_template(self) -> str:
		"""确保 output_dir 下存在 modules_config.yaml。"""
		dst_path = os.path.join(self.output_dir, 'modules_config.yaml')
		if os.path.exists(dst_path):
			return dst_path

		src_path = os.path.join(self.config_dir, 'modules_config.yaml')
		try:
			os.makedirs(self.output_dir, exist_ok=True)
			shutil.copyfile(src_path, dst_path)
			self.logger.info(f"已从模板复制 modules_config.yaml: {dst_path}")
		except Exception as e:
			self.logger.warning(f"复制模板 modules_config.yaml 失败: {e}；将写入最小空结构")
			with open(dst_path, 'w', encoding='utf-8') as f:
				f.write("selected_modules: {}\nnew_modules: []\n")
		return dst_path

	def _parse_json_object(self, text: str) -> Dict[str, Any]:
		"""从 LLM 输出中提取并解析 JSON 对象（容错去掉代码块）。"""
		if not text or not isinstance(text, str):
			raise ValueError("LLM 返回空响应或非字符串")
		raw = text.strip()
		if raw.startswith('```'):
			lines = raw.splitlines()
			# 去掉首尾 fence
			if len(lines) >= 3 and lines[-1].strip().startswith('```'):
				raw = "\n".join(lines[1:-1]).strip()
		obj = json.loads(raw)
		if not isinstance(obj, dict):
			raise ValueError("LLM 输出不是 JSON 对象")
		return obj

	def _merge_modules_config_incremental(self, *, config_path: str, delta: Dict[str, Any]) -> Dict[str, Any]:
		"""把 delta 合并进 modules_config.yaml，不覆盖、不删除。"""
		with open(config_path, 'r', encoding='utf-8') as f:
			base = yaml.safe_load(f) or {}
		if not isinstance(base, dict):
			base = {}

		base_selected = base.get('selected_modules')
		if not isinstance(base_selected, dict):
			base_selected = {}
			base['selected_modules'] = base_selected

		base_new = base.get('new_modules')
		if not isinstance(base_new, list):
			base_new = []
			base['new_modules'] = base_new

		delta_selected = delta.get('selected_modules')
		if delta_selected is None:
			delta_selected = {}
		if not isinstance(delta_selected, dict):
			raise ValueError("selected_modules 必须为 dict")

		delta_new = delta.get('new_modules')
		if delta_new is None:
			delta_new = []
		if not isinstance(delta_new, list):
			raise ValueError("new_modules 必须为 list")

		# 合并 selected_modules（不覆盖已有键）
		for module_name, plugin_name in delta_selected.items():
			if not isinstance(module_name, str) or not module_name.strip():
				continue
			if not isinstance(plugin_name, str) or not plugin_name.strip():
				continue
			if module_name in base_selected:
				continue
			base_selected[module_name] = plugin_name

		# 合并 new_modules（按 name 去重，不覆盖已有项）
		existing_new_names = set()
		for item in base_new:
			if isinstance(item, dict) and isinstance(item.get('name'), str):
				existing_new_names.add(item['name'])
		for item in delta_new:
			if not isinstance(item, dict):
				continue
			name = item.get('name')
			if not isinstance(name, str) or not name.strip():
				continue
			if name in existing_new_names:
				continue
			base_new.append(item)
			existing_new_names.add(name)

		with open(config_path, 'w', encoding='utf-8') as f:
			f.write(yaml.dump(base, allow_unicode=True, sort_keys=False).strip() + "\n")
		return base

	async def select_modules(self, requirement_dict, previous_modules=None, user_feedback=None):
		"""
		调用大模型，根据需求与插件清单（config/plugins.yaml）生成 modules_config.yaml 文件内容。
		
		Args:
			requirement_dict: 解析后的需求字典
			previous_modules: 上一版本 modules_config.yaml（或其片段），用于参考（可选）
			user_feedback: 用户反馈（可选）
		"""
		plugins_catalog = self._plugins_catalog_text()

		# 复制模板到项目目录（首次创建），后续只做增量合并
		modules_config_path = self._ensure_modules_config_from_template()
		
		key_requirements = requirement_dict.get('key_requirements', [])
		description = requirement_dict.get('description', [])
		
		# 构建基础提示词
		if previous_modules and user_feedback:
			# 有反馈的情况
			prompt = self.prompts['select_modules_with_feedback_prompt'].format(
				plugins_catalog=plugins_catalog,
				description=description,
				key_requirements=key_requirements,
				previous_modules=str(previous_modules),
				user_feedback=user_feedback
			)
		else:
			# 没有反馈的情况
			prompt = self.prompts['select_modules_prompt'].format(
				plugins_catalog=plugins_catalog,
				description=description,
				key_requirements=key_requirements
			)
		
		# 添加输出格式说明
		prompt += "\n" + self.prompts['select_modules_output_format']
		response = await self.generate_llm_response(prompt)
		try:
			delta = self._parse_json_object(response)
			# 只允许增量合并：不覆盖、不删除
			merged = self._merge_modules_config_incremental(config_path=modules_config_path, delta=delta)
			self.logger.info(f"modules_config.yaml 已增量更新: {modules_config_path}")
			self.last_module_selection = merged
			return list((merged.get('selected_modules') or {}).keys())
		except Exception as e:
			self.logger.warning(f"模块增量选择失败（将保留现有 modules_config.yaml，不做覆盖/删除）: {e}")
			try:
				with open(modules_config_path, 'r', encoding='utf-8') as f:
					existing = yaml.safe_load(f) or {}
				return list(((existing or {}).get('selected_modules') or {}).keys())
			except Exception:
				return []

	async def generate_description_md(self, original_requirement, requirement_dict, previous_description=None, user_feedback=None):
		"""
		调用大模型，生成 description.md 文件内容。
		参考config_template/description.md作为模板。
		
		Args:
			original_requirement: 用户的原始需求字符串
			requirement_dict: 需求字典
			previous_description: 上一个版本的设计文档（可选）
			user_feedback: 用户反馈意见（可选）
		"""
		# 读取模板文件
		if self.simulation_type == 'survey':
			template_path = os.path.join(self.config_dir, 'description_survey.md')
		else:
			# 默认使用 decision 类型模板
			template_path = os.path.join(self.config_dir, 'description.md')
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		
		# 构建提示词
		if previous_description and user_feedback:
			# 有反馈的情况
			prompt = self.prompts['generate_description_with_feedback_prompt'].format(
				original_requirement=original_requirement,
				requirement_dict=requirement_dict,
				template_content=template_content,
				previous_description=previous_description,
				user_feedback=user_feedback
			)
		else:
			# 没有反馈的情况
			prompt = self.prompts['generate_description_prompt'].format(
				original_requirement=original_requirement,
				requirement_dict=requirement_dict,
				template_content=template_content
			)
		
		# 添加要求说明
		prompt += "\n" + self.prompts['generate_description_requirements']
		
		response = await self.generate_llm_response(prompt)
		
		# 确保返回有效的字符串
		if not response:
			self.logger.error("生成设计文档失败，LLM 返回空响应")
			return "# 实验设计文档\n\n生成失败，请重试。"
		
		return response

	async def generate_config_files(self, requirement_dict, description_md, previous_config=None, user_feedback=None):
		"""
		调用大模型，根据已生成的 description.md 和参考模板，生成 modules_config.yaml 配置文件。
		这是实验的核心配置文件，定义了模拟的整体结构和参数。
		
		Args:
			requirement_dict: 需求字典
			description_md: 设计文档
			previous_config: 上一个版本的配置文件列表（可选）
			user_feedback: 用户反馈意见（可选）
		"""
		# 读取 modules_config.yaml 模板
		template_path = os.path.join(self.config_dir, 'modules_config.yaml')
		modules_config_template = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				modules_config_template = f.read()

		plugins_catalog = self._plugins_catalog_text()
		
		# 构建提示词
		if previous_config and user_feedback:
			# 准备上一版本配置文件内容
			previous_config_content = ""
			if isinstance(previous_config, list) and previous_config:
				for cfg_path in previous_config:
					if os.path.exists(cfg_path):
						cfg_name = os.path.basename(cfg_path)
						with open(cfg_path, 'r', encoding='utf-8') as f:
							previous_config_content += f"\n{cfg_name}:\n{f.read()[:1000]}...\n"
			
			# 有反馈的情况
			prompt = self.prompts['generate_config_with_feedback_prompt'].format(
				description_md=description_md,
				experiment_template=modules_config_template,
				plugins_catalog=plugins_catalog,
				previous_config=previous_config_content,
				user_feedback=user_feedback
			)
		else:
			# 没有反馈的情况
			prompt = self.prompts['generate_config_prompt'].format(
				description_md=description_md,
				experiment_template=modules_config_template,
				plugins_catalog=plugins_catalog
			)
		
		# 添加要求说明
		prompt += "\n" + self.prompts['generate_config_requirements']
		
		response = await self.generate_llm_response(prompt)
		
		# 确保 response 是字符串类型
		if not response or not isinstance(response, str):
			self.logger.error(f"LLM 返回的响应无效: {type(response)}")
			return []
		
		import re
		file_paths = []
		
		# 匹配带文件名的代码块
		named_blocks = re.findall(r'```(?:yaml|json):(\S+)\s*([^`]+)```', response, re.DOTALL)
		if named_blocks:
			for fname, content in named_blocks:
				fpath = os.path.join(self.output_dir, fname)
				with open(fpath, 'w', encoding='utf-8') as f:
					f.write(content.strip())
				file_paths.append(fpath)
		else:
			# 如果没有文件名标注，使用原来的方式
			yaml_blocks = re.findall(r'```(yaml|json)\s*([^`]+)```', response, re.DOTALL)
			if yaml_blocks:
				for idx, (fmt, content) in enumerate(yaml_blocks):
					fname = f'modules_config.{fmt}'
					fpath = os.path.join(self.output_dir, fname)
					with open(fpath, 'w', encoding='utf-8') as f:
						f.write(content.strip())
					file_paths.append(fpath)
			else:
				# 如果没有找到代码块，尝试直接保存响应
				self.logger.warning("未找到代码块标记，尝试直接保存响应内容")
				fname = 'modules_config.yaml'
				fpath = os.path.join(self.output_dir, fname)
				with open(fpath, 'w', encoding='utf-8') as f:
					f.write(response.strip())
				file_paths.append(fpath)
		
		return file_paths
