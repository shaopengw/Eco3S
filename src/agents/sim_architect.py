

from src.utils.custom_logger import CustomLogger

from .shared_imports import *
import re

class SimArchitectAgent(BaseAgent):
	"""
	模拟设计师Agent，继承BaseAgent，负责通过大模型分析需求、选择模块、生成设计文档和配置。
	"""
	def __init__(self, agent_id, output_dir, docs_dir, config_dir, simulation_type):
		super().__init__(agent_id, group_type='sim_architect', window_size=3,
		                 model_api_name='DEEPSEEK', model_type_name='deepseek-v4-flash')
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

	def _scan_plugins_dir(self):
		"""扫描 plugins/ 目录下所有 plugin.yaml，返回 [(name, description, dependencies), ...]。"""
		plugins_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'plugins')
		results = []
		if not os.path.isdir(plugins_root):
			self.logger.warning(f"插件目录不存在: {plugins_root}")
			return results

		for subdir in sorted(os.listdir(plugins_root)):
			yaml_path = os.path.join(plugins_root, subdir, 'plugin.yaml')
			if not os.path.exists(yaml_path):
				continue
			try:
				with open(yaml_path, 'r', encoding='utf-8') as f:
					cfg = yaml.safe_load(f) or {}
				if not isinstance(cfg, dict):
					continue
				name = cfg.get('name', subdir)
				desc = cfg.get('description', '')
				# 支持多行 description（YAML | 块标量）
				if isinstance(desc, str):
					desc = ' '.join(desc.splitlines()).strip()
				deps = cfg.get('dependencies', []) or []
				results.append((name, desc, deps))
			except Exception as e:
				self.logger.warning(f"读取插件配置失败: {yaml_path}, {e}")
				continue
		return results

	def _plugins_catalog_text(self, max_plugins=None):
		"""将 plugins/ 目录扫描结果转成适合提示词的简洁清单文本（name/description/dependencies）。"""
		plugins = self._scan_plugins_dir()
		if max_plugins is not None:
			plugins = plugins[:max_plugins]
		lines = [
			"可用插件清单：",
		]
		for name, desc, deps in plugins:
			line = f"- name: {name}, description: {desc}"
			if deps:
				line += f", dependencies: {deps}"
			lines.append(line)
		return "\n".join(lines)

	def _extract_section_from_md(self, text: str, section_title: str) -> str:
		"""从 Markdown 文本中提取指定章节标题下的内容（含标题本身），到下一个同级标题或文档末尾。

		Args:
			text: Markdown 文本
			section_title: 章节标题，如 "## 2. 智能体与行为"

		Returns:
			提取的章节文本，未找到时返回空字符串
		"""
		if not text or not section_title:
			return ""
		# 匹配以 section_title 开头，到下一个 ## 标题或文档结尾
		pattern = rf'(?:^|\n)({re.escape(section_title)}.*?)(?=\n## |\Z)'
		match = re.search(pattern, text, re.DOTALL)
		if match:
			return match.group(1).strip()
		self.logger.warning(f"未在文档中找到章节：{section_title}，将使用完整文档作为替代")
		return ""

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

	def _normalize_selected_module_names(self, selected_modules):
		"""将 selected_modules 统一为按顺序排列的名称列表。"""
		names = []
		if isinstance(selected_modules, list):
			for item in selected_modules:
				if not isinstance(item, str) or not item.strip():
					continue
				name = item.strip()
				if name not in names:
					names.append(name)
		return names

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
					f.write("selected_modules: []\nnew_modules: []\n")
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

		base_selected = self._normalize_selected_module_names(base.get('selected_modules'))
		base['selected_modules'] = base_selected

		base_new = base.get('new_modules')
		if not isinstance(base_new, list):
			base_new = []
			base['new_modules'] = base_new

		delta_selected = delta.get('selected_modules')
		if delta_selected is None:
			delta_selected = []
		if not isinstance(delta_selected, list):
			raise ValueError("selected_modules 必须为 list")
		delta_selected_names = self._normalize_selected_module_names(delta_selected)

		delta_new = delta.get('new_modules')
		if delta_new is None:
			delta_new = []
		if not isinstance(delta_new, list):
			raise ValueError("new_modules 必须为 list")

		# 合并 selected_modules（不重复追加）
		for module_name in delta_selected_names:
			if module_name not in base_selected:
				base_selected.append(module_name)

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

	async def select_modules(self, previous_modules=None, user_feedback=None, description_md=None):
		"""
		调用大模型，根据需求与插件清单（plugins/*/plugin.yaml）生成 modules_config.yaml 文件内容。
		
		Args:
			requirement_dict: 解析后的需求字典
			previous_modules: 上一版本 modules_config.yaml（或其片段），用于参考（可选）
			user_feedback: 用户反馈（可选）
			description_md: 已生成的 description.md 内容
		"""
		plugins_catalog = self._plugins_catalog_text()

		# 复制模板到项目目录（首次创建），后续只做增量合并
		modules_config_path = self._ensure_modules_config_from_template()
		
		description_md_text = (description_md or '').strip()
		
		# 构建基础提示词
		if previous_modules and user_feedback:
			# 有反馈的情况
			prompt = self.prompts['select_modules_with_feedback_prompt'].format(
				plugins_catalog=plugins_catalog,
				previous_modules=str(previous_modules),
				user_feedback=user_feedback,
				description_md_text=description_md_text
			)
		else:
			# 没有反馈的情况
			prompt = self.prompts['select_modules_prompt'].format(
				plugins_catalog=plugins_catalog,
				description_md_text=description_md_text
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
			return self._normalize_selected_module_names(merged.get('selected_modules'))
		except Exception as e:
			self.logger.warning(f"模块增量选择失败（将保留现有 modules_config.yaml，不做覆盖/删除）: {e}")
			try:
				with open(modules_config_path, 'r', encoding='utf-8') as f:
					existing = yaml.safe_load(f) or {}
				return self._normalize_selected_module_names((existing or {}).get('selected_modules'))
			except Exception:
				return []

	async def generate_agent_profile_config(self, description_md, modules_config_yaml, previous_agent_profile=None, user_feedback=None):
		"""
		调用大模型，根据设计文档和模块配置生成 agent_profile.yaml 内容。

		Args:
			description_md: 设计文档内容
			modules_config_yaml: 模块配置YAML内容
			previous_agent_profile: 上一版本的agent_profile内容（可选）
			user_feedback: 用户反馈（可选）

		Returns:
			str: agent_profile 的 YAML 内容
		"""
		# 从设计文档中提取"智能体与行为"章节，聚焦 LLM 上下文
		agent_behavior_section = self._extract_section_from_md(description_md, "## 2. 智能体与行为")
		# 如果找不到指定章节，回退使用完整文档
		if not agent_behavior_section:
			agent_behavior_section = f"（未找到独立的「智能体与行为」章节，以下是完整设计文档供参考）\n\n{description_md or ''}"

		if previous_agent_profile and user_feedback:
			prompt = self.prompts['generate_agent_profile_with_feedback_prompt'].format(
				agent_behavior_section=agent_behavior_section,
				modules_config_yaml=modules_config_yaml or "（未提供模块配置）",
				previous_agent_profile=previous_agent_profile,
				user_feedback=user_feedback
			)
		else:
			prompt = self.prompts['generate_agent_profile_prompt'].format(
				agent_behavior_section=agent_behavior_section,
				modules_config_yaml=modules_config_yaml or "（未提供模块配置）"
			)

		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("生成 agent_profile 失败，LLM 返回空响应")
			return None

		# 提取 YAML 内容（容错处理）
		yaml_text = self._extract_yaml_text(response)
		if not yaml_text:
			self.logger.warning("从 LLM 响应中提取 YAML 失败，尝试直接使用原始响应")
			yaml_text = response.strip()

		# 基础校验：确保包含 entity_type 和 attributes（支持 agents 列表和简写两种格式）
		try:
			parsed = yaml.safe_load(yaml_text)
			if not isinstance(parsed, dict):
				self.logger.warning("agent_profile 解析后不是字典，放弃保存")
				return None

			# 确定要检查的 agent 定义列表
			check_targets = []
			if "agents" in parsed and isinstance(parsed.get("agents"), list):
				check_targets = parsed["agents"]
				if not check_targets:
					self.logger.warning("agent_profile['agents'] 为空列表")
			elif "entity_type" in parsed:
				# 简写格式，单实体直接出现在顶层
				check_targets = [parsed]

			for agent_def in check_targets:
				name = agent_def.get("name", "unknown")
				if "entity_type" not in agent_def:
					agent_def["entity_type"] = "resident"
					self.logger.info(f"agent_profile 中「{name}」缺少 entity_type，已自动设为 'resident'")
				if "attributes" not in agent_def or not isinstance(agent_def.get("attributes"), (dict, list)):
					self.logger.warning(f"agent_profile 中「{name}」缺少 attributes，可能不符合要求")

			# 重新序列化，确保格式规范
			yaml_text = yaml.dump(parsed, allow_unicode=True, sort_keys=False).strip()
		except Exception as e:
			self.logger.warning(f"agent_profile YAML 校验失败: {e}，将直接保存原始内容")

		return yaml_text

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
