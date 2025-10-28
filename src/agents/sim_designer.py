

from .shared_imports import *

class SystemArchitectAgent(BaseAgent):
	"""
	模拟设计师Agent，继承BaseAgent，负责通过大模型分析需求、选择模块、生成设计文档和配置。
	"""
	def __init__(self, agent_id, output_dir, docs_dir, config_dir):
		super().__init__(agent_id, group_type='system_architect', window_size=3)
		self.output_dir = output_dir
		self.docs_dir = docs_dir
		self.config_dir = config_dir
		self.logger = logging.getLogger(f'{self.__class__.__name__}_{agent_id}')

	async def parse_requirement(self, requirement_text):
		"""
		调用大模型解析用户需求，返回结构化需求字典。
		"""
		prompt = f"""你是一个多智能体模拟系统的设计师，请根据以下用户需求，提取关键信息并返回JSON格式。

用户需求：
{requirement_text}

请返回以下JSON格式（严格遵守格式）：
{{
  "simulation_name": "模拟名称（使用下划线连接的英文，如climate_migration）",
  "objectives": ["目标1", "目标2"],
  "key_elements": ["关键要素1", "关键要素2", "关键要素3"]
}}

注意：
- simulation_name 必须是简短的英文标识符
- objectives 是实验的主要目标列表
- key_elements 是实验涉及的关键要素（如气候、人口、经济等）
"""
		response = await self.generate_llm_response(prompt)
		import json
		try:
			if not response:
				raise ValueError("LLM 返回空响应")
			result = json.loads(response)
			# 确保必需的键存在
			if 'simulation_name' not in result:
				result['simulation_name'] = 'default_sim'
			if 'objectives' not in result:
				result['objectives'] = []
			if 'key_elements' not in result:
				result['key_elements'] = []
		except Exception as e:
			# fallback: 尝试简单修正
			self.logger.warning(f"解析需求失败: {e}，使用默认值")
			result = {'simulation_name': 'default_sim', 'objectives': [], 'key_elements': []}
		return result

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
		prompt = f"""系统能力如下：
{sys_cap}

根据以下需求信息，列出最相关的系统模块。

需求目标：
{objectives}

关键要素：
{key_elements}
"""
		
		# 如果有上一版本和用户反馈，添加到提示词中
		if previous_modules and user_feedback:
			prompt += f"""

上一版本选择的模块：
{json.dumps(previous_modules, ensure_ascii=False)}

用户反馈意见：
{user_feedback}

请根据用户反馈调整模块选择。
"""
		
		prompt += """
请只返回模块英文名列表的JSON格式，例如：
["climate", "population", "map", "government"]

注意：只返回JSON数组，不要有其他文字。
"""
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

	async def generate_description_md(self, requirement_dict, modules, previous_description=None, user_feedback=None):
		"""
		调用大模型，生成 description.md 文件内容。
		参考config_template/description.md作为模板。
		
		Args:
			requirement_dict: 需求字典
			modules: 选择的模块列表
			previous_description: 上一个版本的设计文档（可选）
			user_feedback: 用户反馈意见（可选）
		"""
		# 读取模板文件
		template_path = os.path.join(self.config_dir, 'description.md')
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		
		# 构建提示词
		prompt = f"""请根据以下需求和模块，生成一份简明的实验设计文档（markdown格式）。

需求：
{requirement_dict}

模块：
{modules}

参考模板格式：
{template_content}
"""
		
		# 如果有上一版本和用户反馈，添加到提示词中
		if previous_description and user_feedback:
			prompt += f"""

=== 上一版本的设计文档 ===
{previous_description}

=== 用户反馈意见 ===
{user_feedback}

请根据用户反馈，改进并重新生成设计文档。
"""
		
		prompt += """
请按照模板格式生成新的实验设计文档，包含：
1. 实验名称和目标
2. 涉及的系统模块
3. 系统架构设计
4. 预期结果
5. 关键参数说明
"""
		
		response = await self.generate_llm_response(prompt)
		
		# 确保返回有效的字符串
		if not response:
			self.logger.error("生成设计文档失败，LLM 返回空响应")
			return "# 实验设计文档\n\n生成失败，请重试。"
		
		return response

	async def generate_config_files(self, modules, requirement_dict, description_md, previous_config=None, user_feedback=None):
		"""
		调用大模型，根据已生成的 description.md 和参考模板，生成 experiment_template.yaml 配置文件。
		这是实验的核心配置文件，定义了模拟的整体结构和参数。
		
		Args:
			modules: 模块列表
			requirement_dict: 需求字典
			description_md: 设计文档
			previous_config: 上一个版本的配置文件列表（可选）
			user_feedback: 用户反馈意见（可选）
		"""
		# 读取 experiment_template.yaml 模板
		template_path = os.path.join(self.config_dir, 'experiment_template.yaml')
		experiment_template = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				experiment_template = f.read()
		
		# 构建提示词
		prompt = f"""根据实验设计文档和参考模板，生成 experiment_template.yaml 配置文件。

# 实验设计文档：
{description_md}

# 参考模板：
{experiment_template}
"""
		
		# 如果有上一版本和用户反馈，添加到提示词中
		if previous_config and user_feedback:
			prompt += f"""

=== 上一版本的配置文件 ===
"""
			if isinstance(previous_config, list) and previous_config:
				for cfg_path in previous_config:
					if os.path.exists(cfg_path):
						cfg_name = os.path.basename(cfg_path)
						with open(cfg_path, 'r', encoding='utf-8') as f:
							prompt += f"\n{cfg_name}:\n{f.read()[:1000]}...\n"
			
			prompt += f"""
=== 用户反馈意见 ===
{user_feedback}

请根据用户反馈，改进并重新生成配置文件。
"""
		
		prompt += """
要求：
1. 根据设计文档调整模块配置和参数
2. 只保留实验需要的模块（enabled: true）
3. 删除不相关的配置项
4. 参数值要合理且一致

用代码块输出：
```yaml:experiment_template.yaml
内容
```
"""
		
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
					fname = f'experiment_template.{fmt}'
					fpath = os.path.join(self.output_dir, fname)
					with open(fpath, 'w', encoding='utf-8') as f:
						f.write(content.strip())
					file_paths.append(fpath)
			else:
				# 如果没有找到代码块，尝试直接保存响应
				self.logger.warning("未找到代码块标记，尝试直接保存响应内容")
				fname = 'experiment_template.yaml'
				fpath = os.path.join(self.output_dir, fname)
				with open(fpath, 'w', encoding='utf-8') as f:
					f.write(response.strip())
				file_paths.append(fpath)
		
		return file_paths
