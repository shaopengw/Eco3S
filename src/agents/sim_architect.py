

from src.utils.custom_logger import CustomLogger

from .shared_imports import *

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
		
		# 加载提示词配置
		prompts_path = os.path.join(os.path.dirname(__file__), 'sim_architect_prompts.yaml')
		with open(prompts_path, 'r', encoding='utf-8') as f:
			self.prompts = yaml.safe_load(f)
		
		self.system_message = self.prompts['system_message']

	async def select_modules(self, requirement_dict, previous_modules=None, user_feedback=None):
		"""
		调用大模型，根据需求和 system_capabilities.md，选择所需模块。
		
		Args:
			requirement_dict: 解析后的需求字典
			previous_modules: 上一版本选择的模块列表（可选）
			user_feedback: 用户反馈（可选）
		"""
		with open(os.path.join(self.docs_dir, 'system_capabilities.md'), 'r', encoding='utf-8') as f:
			sys_cap = f.read()
		
		# 安全获取 key_elements，如果不存在则使用空列表
		key_elements = requirement_dict.get('key_elements', [])
		objectives = requirement_dict.get('objectives', [])
		
		# 构建基础提示词
		if previous_modules and user_feedback:
			# 有反馈的情况
			prompt = self.prompts['select_modules_with_feedback_prompt'].format(
				system_capabilities=sys_cap,
				objectives=objectives,
				key_elements=key_elements,
				previous_modules=json.dumps(previous_modules, ensure_ascii=False),
				user_feedback=user_feedback
			)
		else:
			# 没有反馈的情况
			prompt = self.prompts['select_modules_prompt'].format(
				system_capabilities=sys_cap,
				objectives=objectives,
				key_elements=key_elements
			)
		
		# 添加输出格式说明
		prompt += "\n" + self.prompts['select_modules_output_format']
		response = await self.generate_llm_response(prompt)
		import json
		try:
			if not response:
				raise ValueError("LLM 返回空响应")
			modules = json.loads(response)
			if not isinstance(modules, list):
				self.logger.warning(f"模块列表格式错误，期望列表但得到: {type(modules)}")
				modules = []
		except Exception as e:
			self.logger.warning(f"选择模块失败: {e}，返回空列表")
			modules = []
		return modules

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
				previous_config=previous_config_content,
				user_feedback=user_feedback
			)
		else:
			# 没有反馈的情况
			prompt = self.prompts['generate_config_prompt'].format(
				description_md=description_md,
				experiment_template=modules_config_template
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
