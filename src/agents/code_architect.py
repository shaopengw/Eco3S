from .shared_imports import *

class CodeArchitectAgent(BaseAgent):
	"""
	编码师Agent，继承BaseAgent，负责根据设计文档和配置，自动生成模拟器代码、详细配置和提示词。
	工作流程：每次只生成一个文件，逐步完成所有任务。
	"""
	def __init__(self, agent_id, simulator_output_dir, main_output_dir, docs_dir, config_dir, config_template_dir, simulation_name):
		super().__init__(agent_id, group_type='code_architect', window_size=3)
		self.simulator_output_dir = simulator_output_dir  # src/simulation/
		self.main_output_dir = main_output_dir  # entrypoints/
		self.docs_dir = docs_dir
		self.config_dir = config_dir  # config_[模拟名称]/
		self.config_template_dir = config_template_dir  # config_template/
		self.simulation_name = simulation_name
		self.logger = LogManager.get_logger('code_architect')

	async def generate_simulator_code(self, description_md, experiment_template_yaml):
		"""
		步骤1: 生成模拟器主代码（simulator_[模拟名称].py）
		输入：设计文档 + 实验模板配置
		参考：src/simulation/simulator_template.py
		"""
		self.logger.info("开始生成simulator代码...")
		
		# 读取模板文件
		project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		template_path = os.path.join(project_root, 'src', 'simulation', 'simulator_template.py')
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		
		prompt = f"""你是多智能体模拟系统的编码师，请根据设计文档和实验模板，生成模拟器代码框架。

设计文档：
{description_md}

实验模板配置：
{experiment_template_yaml}

代码格式参考（仅参考结构，不要继承）：
{template_content}

要求：
1. 参考模板中的类结构和方法定义格式
2. 根据实验需求初始化所需的环境对象
3. 实现核心方法：__init__, init_results, prepare_experiment, update_state, execute_actions, collect_results, save_results
4. 先生成框架，具体实现可以用pass或简单逻辑

请生成完整的Python代码，文件名为 simulator_{self.simulation_name}.py"""
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return []
		
		# 提取代码块并写入文件
		import re
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		file_paths = []
		if code_blocks:
			fname = f'simulator_{self.simulation_name}.py'
			fpath = os.path.join(self.simulator_output_dir, fname)
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(code_blocks[0].strip())
			file_paths.append(fpath)
			self.logger.info(f"生成simulator代码: {fpath}")
		else:
			self.logger.warning("未找到代码块")
		return file_paths

	async def generate_main_file(self, description_md, simulator_file_path):
		"""
		步骤2: 生成main入口文件（main_[模拟名称].py）
		输入：设计文档 + 已生成的simulator文件路径
		参考：entrypoints/main_template.py
		"""
		self.logger.info("开始生成main入口文件...")
		
		# 读取模板文件
		project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		template_path = os.path.join(project_root, 'entrypoints', 'main_template.py')
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		
		# 读取已生成的simulator代码
		simulator_content = ""
		if os.path.exists(simulator_file_path):
			with open(simulator_file_path, 'r', encoding='utf-8') as f:
				simulator_content = f.read()
		
		prompt = f"""你是多智能体模拟系统的编码师，请根据设计文档和已生成的simulator代码，生成main入口文件。

设计文档：
{description_md}

已生成的Simulator代码：
{simulator_content}

代码模板参考：
{template_content}

要求：
1. 文件名为 main_{self.simulation_name}.py
2. 导入simulator_{self.simulation_name}模块
3. 加载config_{self.simulation_name}/目录下的配置文件
4. 实现run_simulation函数：
   - 根据simulator的__init__参数，初始化所需的环境对象
   - 创建simulator实例
   - 调用simulator.run()
   - 保存结果
5. 实现main函数：解析参数、加载配置、运行模拟
6. 代码风格与模板一致
7. 注意：先生成框架，具体对象初始化可以用注释标注TODO

请生成完整的Python代码。"""
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return []
		
		import re
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		file_paths = []
		if code_blocks:
			fname = f'main_{self.simulation_name}.py'
			fpath = os.path.join(self.main_output_dir, fname)
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(code_blocks[0].strip())
			file_paths.append(fpath)
			self.logger.info(f"生成main文件: {fpath}")
		else:
			self.logger.warning("未找到代码块")
		return file_paths

	async def refine_simulator_functions(self, simulator_file_path, description_md, modules):
		"""
		步骤3: 检查并补完simulator文件的函数
		分为三个子步骤：
		3.1 创建工作列表 - 识别不完整的函数
		3.2 逐个补完函数 - 针对每个函数单独实现
		3.3 总体检查与修复 - 检查问题并自动修复
		"""
		self.logger.info("=== 步骤3: 开始补完simulator函数 ===")
		
		# 读取已生成的simulator代码
		if not os.path.exists(simulator_file_path):
			self.logger.error(f"Simulator文件不存在: {simulator_file_path}")
			return []
		
		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			simulator_content = f.read()
		
		# 3.1 创建工作列表
		self.logger.info("步骤3.1: 创建工作列表...")
		todo_list = await self._create_simulator_todo_list(simulator_content, description_md)
		if not todo_list:
			self.logger.info("✓ 未发现需要补完的函数")
		else:
			self.logger.info(f"\n{'='*60}")
			self.logger.info(f"📋 工作列表（共 {len(todo_list)} 项）:")
			for idx, item in enumerate(todo_list, 1):
				self.logger.info(f"  {idx}. {item['function_name']}")
				self.logger.info(f"     描述: {item['description']}")
				self.logger.info(f"     模块: {', '.join(item.get('required_modules', []))}")
			self.logger.info(f"{'='*60}\n")
			
			# 3.2 逐个补完函数
			self.logger.info("步骤3.2: 逐个补完函数...")
			for idx, todo_item in enumerate(todo_list, 1):
				self.logger.info(f"正在处理 [{idx}/{len(todo_list)}]: {todo_item['function_name']}")
				success = await self._complete_simulator_function(
					simulator_file_path, 
					todo_item, 
					description_md
				)
				if not success:
					self.logger.warning(f"⚠️ 任务 {idx} 未能完成")
		
		# 3.3 总体检查与修复（最多重试2次）
		self.logger.info("步骤3.3: 总体检查与修复...")
		max_fix_attempts = 2
		for attempt in range(1, max_fix_attempts + 1):
			self.logger.info(f"第 {attempt}/{max_fix_attempts} 次检查...")
			
			issues = await self._check_and_fix_code(simulator_file_path, description_md, modules, "simulator")
			
			if not issues:
				self.logger.info("✓ Simulator代码完整无误")
				return [simulator_file_path]
			else:
				if attempt < max_fix_attempts:
					self.logger.warning(f"发现 {len(issues)} 个问题，尝试自动修复...")
				else:
					self.logger.warning(f"仍有 {len(issues)} 个问题未解决，但文件已更新")
		
		return [simulator_file_path]

	async def _create_simulator_todo_list(self, simulator_content, description_md):
		"""
		步骤3.1: 创建simulator的工作列表
		检查代码中的pass、TODO等不完整标记
		"""
		prompt = f"""你是代码审查专家，请检查以下simulator代码，找出所有不完整的地方。

Simulator代码：
{simulator_content}

设计文档：
{description_md}

任务：
1. 检查所有方法，找出只有pass或TODO注释的不完整函数
2. 检查是否有空实现或明显不完整的逻辑
3. 为每个不完整的函数创建一个待办项

返回格式（JSON数组）：
[
  {{
    "function_name": "函数名",
    "description": "该函数的作用描述",
    "required_modules": ["可能用到的模块1", "模块2"]
  }}
]

只返回JSON数组，不要其他解释。"""

		response = await self.generate_llm_response(prompt)
		if not response:
			return []
		
		import json, re
		# 提取JSON
		json_match = re.search(r'\[[\s\S]*\]', response)
		if json_match:
			try:
				todo_list = json.loads(json_match.group())
				self.logger.info(f"识别出 {len(todo_list)} 个待补完的函数")
				for item in todo_list:
					self.logger.info(f"  - {item['function_name']}: {item['description']}")
				return todo_list
			except json.JSONDecodeError as e:
				self.logger.error(f"JSON解析失败: {e}")
		
		return []

	async def _complete_simulator_function(self, simulator_file_path, todo_item, description_md):
		"""
		步骤3.2: 补完单个simulator函数
		"""
		function_name = todo_item['function_name']
		description = todo_item['description']
		required_modules = todo_item.get('required_modules', [])
		
		# 读取当前代码
		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			current_code = f.read()
		
		# 读取相关API文档
		api_docs = ""
		if required_modules:
			api_docs = self._read_api_docs_for_modules(required_modules)
		
		prompt = f"""你是Python编码专家，请补完以下函数的实现。

当前完整代码（用于理解上下文）：
{current_code}

待补完函数：{function_name}
函数作用：{description}

设计文档：
{description_md}

相关API文档：
{api_docs}

要求：
1. 只实现 {function_name} 函数的内容
2. 保持代码风格一致
3. 使用API文档中的方法
4. 确保逻辑完整、可运行
5. 返回完整的函数实现代码（从def开始到函数结束）

请生成该函数的完整实现代码。"""

		response = await self.generate_llm_response(prompt)
		if not response:
			return False
		
		import re
		# 提取代码块
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		if code_blocks:
			new_function_code = code_blocks[0].strip()
			
			# 找到原函数并替换
			# 支持普通 def 和 async def，匹配函数定义到下一个同级 def 或 class 结束
			# 允许前置可选的 async 关键字，并在向前查找下一个函数时也允许 async
			pattern = rf"(\s*)(?:async\s+)?def {re.escape(function_name)}\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*class\s|\Z)"
			match = re.search(pattern, current_code, re.DOTALL)
			
			if match:
				indent = match.group(1)
				# 对新代码添加正确的缩进
				indented_new_code = '\n'.join(indent + line if line.strip() else '' 
											   for line in new_function_code.split('\n'))
				
				updated_code = current_code[:match.start()] + indented_new_code + current_code[match.end():]
				
				with open(simulator_file_path, 'w', encoding='utf-8') as f:
					f.write(updated_code)
				
				self.logger.info(f"✓ 已补完函数: {function_name}")
				return True
			else:
				self.logger.warning(f"未找到函数定义: {function_name}")
				return False
		
		return False

	async def _check_and_fix_code(self, file_path, description_md, modules, file_type="simulator", simulator_content=None):
		"""
		统一的代码检查与修复方法
		
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
		
		# 构建检查提示词
		if file_type == "simulator":
			prompt = f"""你是Python代码专家，请严格检查以下simulator代码并修复所有问题。

当前代码：
{code_content}

设计文档：
{description_md}

严格检查以下问题：
1. 语法错误：async async def、缩进错误、括号不匹配等
2. 缺失导入：必须包含 from .simulator_imports import *
3. 未完成实现：pass、TODO等
4. 代码质量：逻辑缺陷、异常处理、变量未定义等
5. 方法完整性：__init__, init_results, prepare_experiment, update_state, execute_actions, collect_results, save_results

要求：
1. 如果有问题，直接修复并返回完整的修复后代码
2. 如果没有问题，返回：OK

请返回修复后的代码或OK。"""
		else:  # main
			prompt = f"""你是Python代码专家，请严格检查以下main入口文件代码并修复所有问题。

当前代码：
{code_content}

Simulator代码参考：
{simulator_content[:1000] if simulator_content else ''}...

设计文档：
{description_md}

严格检查以下问题：
1. 缺失导入：argparse, os, sys, yaml等必要模块
2. 未完成实现：TODO、pass等
3. 对象初始化：根据simulator的__init__参数检查是否完整
4. 异常处理：是否完善
5. 配置路径：是否正确
6. 语法错误：缩进、括号等

要求：
1. 如果有问题，直接修复并返回完整的修复后代码
2. 如果没有问题，返回：OK

请返回修复后的代码或OK。"""
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.warning("检查失败：LLM返回空响应")
			return ["LLM返回空响应"]
		
		# 检查是否返回OK
		if 'OK' in response.upper() and len(response.strip()) < 20:
			return []  # 无问题
		
		# 尝试提取修复后的代码
		import re
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		if code_blocks:
			# 找到了修复后的代码，保存并返回空问题列表
			fixed_code = code_blocks[0].strip()
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(fixed_code)
			self.logger.info("✓ 代码已自动修复")
			return []  # 已修复，返回空问题列表
		else:
			# 没找到代码块，说明LLM只列出了问题
			# 提取问题列表
			lines = response.split('\n')
			issues = [line.strip() for line in lines if line.strip() and (
				line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.', '-', '•'))
			)]
			
			if issues:
				self.logger.warning(f"发现以下问题：")
				for issue in issues:
					self.logger.warning(f"  {issue}")
				
				# 尝试让LLM修复这些问题
				self.logger.info("尝试修复这些问题...")
				fix_prompt = f"""请修复以下代码中的所有问题。

当前代码：
{code_content}

发现的问题：
{chr(10).join(issues)}

要求：
1. 修复所有问题
2. 保持代码逻辑完整
3. 返回完整的修复后代码

请返回修复后的完整代码。"""
				
				fix_response = await self.generate_llm_response(fix_prompt)
				if fix_response:
					fix_code_blocks = re.findall(r'```python\s*([^`]+)```', fix_response, re.DOTALL)
					if not fix_code_blocks:
						fix_code_blocks = re.findall(r'```\s*([^`]+)```', fix_response, re.DOTALL)
					
					if fix_code_blocks:
						fixed_code = fix_code_blocks[0].strip()
						with open(file_path, 'w', encoding='utf-8') as f:
							f.write(fixed_code)
						self.logger.info("✓ 代码已修复")
						return []  # 已修复
				
				return issues  # 无法自动修复
			else:
				return ["未知问题"]

	def _read_api_docs_for_modules(self, module_names):
		"""
		根据模块名列表读取API文档
		"""
		module_to_file = {
			'time': 'time.md',
			'map': 'map.md',
			'population': 'population.md',
			'resident': 'resident.md',
			'residents': 'resident.md',
			'government': 'government.md',
			'rebellion': 'rebels.md',
			'rebels': 'rebels.md',
			'social': 'social_network.md',
			'social_network': 'social_network.md',
			'job': 'job_market.md',
			'job_market': 'job_market.md',
			'climate': 'climate.md',
			'transport': 'transport_economy.md',
			'economy': 'transport_economy.md',
			'towns': 'towns.md',
		}
		
		api_docs_str = ""
		api_dir = os.path.join(self.docs_dir, 'api')
		
		for module_name in module_names:
			module_key = module_name.lower().strip()
			api_file = module_to_file.get(module_key)
			
			if api_file:
				api_path = os.path.join(api_dir, api_file)
				if os.path.exists(api_path):
					with open(api_path, 'r', encoding='utf-8') as f:
						content = f.read()
						if len(content) > 2000:
							content = content[:2000] + "\n...(已截断)"
						api_docs_str += f"\n## {api_file}\n{content}\n"
		
		return api_docs_str if api_docs_str else "（未找到相关API文档）"

	async def refine_main_functions(self, main_file_path, simulator_file_path, description_md, modules):
		"""
		步骤4: 检查并补完main文件的函数
		分为三个子步骤：
		4.1 创建工作列表 - 识别不完整的部分
		4.2 逐个补完 - 针对每个部分单独实现
		4.3 总体检查与修复 - 检查问题并自动修复
		"""
		self.logger.info("=== 步骤4: 开始补完main函数 ===")
		
		# 读取main代码
		if not os.path.exists(main_file_path):
			self.logger.error(f"Main文件不存在: {main_file_path}")
			return []
		
		with open(main_file_path, 'r', encoding='utf-8') as f:
			main_content = f.read()
		
		# 读取simulator代码
		simulator_content = ""
		if os.path.exists(simulator_file_path):
			with open(simulator_file_path, 'r', encoding='utf-8') as f:
				simulator_content = f.read()
		
		# 4.1 创建工作列表
		self.logger.info("步骤4.1: 创建工作列表...")
		todo_list = await self._create_main_todo_list(main_content, simulator_content, description_md)
		if not todo_list:
			self.logger.info("✓ 未发现需要补完的任务")
		else:
			self.logger.info(f"\n{'='*60}")
			self.logger.info(f"📋 工作列表（共 {len(todo_list)} 项）:")
			for idx, item in enumerate(todo_list, 1):
				self.logger.info(f"  {idx}. {item['task_name']}")
				self.logger.info(f"     描述: {item['description']}")
				self.logger.info(f"     模块: {', '.join(item.get('required_modules', []))}")
			self.logger.info(f"{'='*60}\n")
			
			# 4.2 逐个补完
			self.logger.info("步骤4.2: 逐个补完任务...")
			for idx, todo_item in enumerate(todo_list, 1):
				self.logger.info(f"正在处理 [{idx}/{len(todo_list)}]: {todo_item['task_name']}")
				success = await self._complete_main_task(
					main_file_path,
					todo_item,
					simulator_content,
					description_md
				)
				if not success:
					self.logger.warning(f"⚠️ 任务 {idx} 未能完成")
		
		# 4.3 总体检查与修复（最多重试2次）
		self.logger.info("步骤4.3: 总体检查与修复...")
		max_fix_attempts = 2
		for attempt in range(1, max_fix_attempts + 1):
			self.logger.info(f"第 {attempt}/{max_fix_attempts} 次检查...")
			
			issues = await self._check_and_fix_code(main_file_path, description_md, modules, "main", simulator_content)
			
			if not issues:
				self.logger.info("✓ Main代码完整无误")
				return [main_file_path]
			else:
				if attempt < max_fix_attempts:
					self.logger.warning(f"发现 {len(issues)} 个问题，尝试自动修复...")
				else:
					self.logger.warning(f"仍有 {len(issues)} 个问题未解决，但文件已更新")
		
		return [main_file_path]

	async def _create_main_todo_list(self, main_content, simulator_content, description_md):
		"""
		步骤4.1: 创建main文件的工作列表
		检查代码中的pass、TODO等不完整标记
		"""
		prompt = f"""你是代码审查专家，请检查以下main入口文件代码，找出所有不完整的地方。

Main代码：
{main_content}

Simulator代码（用于了解需要初始化什么）：
{simulator_content[:1000]}...（已截断）

设计文档：
{description_md}

任务：
1. 检查是否有TODO、pass或空实现
2. 检查对象初始化是否完整（Map, Time, Population, Residents等）
3. 检查simulator实例创建是否正确
4. 检查结果保存逻辑是否完整
5. 为每个不完整的部分创建待办项

返回格式（JSON数组）：
[
  {{
    "task_name": "任务名称（如：初始化Map对象）",
    "description": "该任务的具体描述",
    "required_modules": ["可能用到的模块1", "模块2"]
  }}
]

只返回JSON数组，不要其他解释。"""

		response = await self.generate_llm_response(prompt)
		if not response:
			return []
		
		import json, re
		json_match = re.search(r'\[[\s\S]*\]', response)
		if json_match:
			try:
				todo_list = json.loads(json_match.group())
				self.logger.info(f"识别出 {len(todo_list)} 个待补完的任务")
				for item in todo_list:
					self.logger.info(f"  - {item['task_name']}: {item['description']}")
				return todo_list
			except json.JSONDecodeError as e:
				self.logger.error(f"JSON解析失败: {e}")
		
		return []

	async def _complete_main_task(self, main_file_path, todo_item, simulator_content, description_md):
		"""
		步骤4.2: 补完main文件的单个任务
		"""
		task_name = todo_item['task_name']
		description = todo_item['description']
		required_modules = todo_item.get('required_modules', [])
		
		# 读取当前代码
		with open(main_file_path, 'r', encoding='utf-8') as f:
			current_code = f.read()
		
		# 读取相关API文档
		api_docs = ""
		if required_modules:
			api_docs = self._read_api_docs_for_modules(required_modules)
		
		prompt = f"""你是Python编码专家，请补完main文件中的以下任务。

当前Main代码：
{current_code}

Simulator代码参考（了解需要什么参数）：
{simulator_content[:1500]}...

待补完任务：{task_name}
任务描述：{description}

设计文档：
{description_md}

相关API文档：
{api_docs}

要求：
1. 只修改与该任务相关的代码部分
2. 保持代码风格一致
3. 确保逻辑完整、可运行
4. 返回完整的Python代码文件内容

请返回完整的main文件代码。"""

		response = await self.generate_llm_response(prompt)
		if not response:
			return False
		
		import re
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		if code_blocks:
			updated_code = code_blocks[0].strip()
			with open(main_file_path, 'w', encoding='utf-8') as f:
				f.write(updated_code)
			
			self.logger.info(f"✓ 已补完任务: {task_name}")
			return True
		
		return False

	async def _final_check_main(self, main_file_path, simulator_content, description_md, modules):
		"""
		步骤4.4: 总体检查main代码
		检查代码完整性、语法正确性和逻辑合理性
		"""
		with open(main_file_path, 'r', encoding='utf-8') as f:
			main_content = f.read()
		
		prompt = f"""你是代码审查专家，请对以下main入口文件代码进行严格的总体检查。

Main代码：
{main_content}

Simulator代码参考：
{simulator_content[:1000]}...

设计文档：
{description_md}

严格检查项：
1. 语法检查：
   - 是否有语法错误（缩进错误、括号不匹配等）？
   - 是否有重复的关键字？

2. 导入检查：
   - 是否正确导入了simulator模块？
   - 是否导入了必要的依赖（os, sys, yaml等）？

3. 实现完整性：
   - 是否还有TODO或pass未实现？
   - 对象初始化是否完整（根据simulator的__init__参数）？
   - simulator实例创建是否正确？
   - 结果保存逻辑是否完整？

4. 代码质量：
   - 配置文件路径是否正确？
   - 代码是否可以正常运行？
   - 异常处理是否完善？

请返回检查结果：
- 如果代码完整无问题，只返回：OK
- 如果有问题，列出具体问题清单（每行一个问题）

要求：严格检查，有任何问题都要指出。"""

		response = await self.generate_llm_response(prompt)
		if response and 'OK' in response.upper() and len(response.strip()) < 10:
			self.logger.info("✓ 总体检查通过")
			return True
		else:
			self.logger.warning(f"总体检查发现问题:\n{response}")
			return False

	async def generate_config_file(self, config_filename, description_md, modules, previous_configs=None):
		"""
		步骤5: 生成单个配置文件
		输入：配置文件名 + 设计文档 + 模块信息 + 已生成的配置（可选）
		输出：生成的配置文件路径
		
		支持的配置文件：
		- simulation_config.yaml
		- jobs_config.yaml
		- resident_actions.yaml
		- towns_data.json
		"""
		self.logger.info(f"开始生成配置文件: {config_filename}")
		
		# 读取模板
		template_path = os.path.join(self.config_template_dir, config_filename)
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		else:
			self.logger.warning(f"模板文件不存在: {template_path}")
		
		# 读取API文档（根据配置类型选择相关文档）
		api_docs = self._read_relevant_api_docs(config_filename)
		
		# 构建已生成配置的说明
		previous_configs_str = ""
		if previous_configs:
			previous_configs_str = "已生成的配置文件：\n"
			for fname, content in previous_configs.items():
				previous_configs_str += f"\n{fname}:\n{content}\n"
		
		prompt = f"""你是多智能体模拟系统的配置专家，请根据设计文档生成配置文件 {config_filename}。

设计文档：
{description_md}

涉及模块：
{modules}

配置模板参考：
{template_content}

API文档参考：
{api_docs}

{previous_configs_str}

要求：
1. 参考模板的结构和字段
2. 根据设计文档调整具体数值和内容
3. 确保配置的完整性和一致性
4. 如果有已生成的配置，保持参数之间的关联性

请生成完整的配置文件内容（{"YAML" if config_filename.endswith(".yaml") else "JSON"}格式）。"""
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return None
		
		import re
		# 提取代码块
		file_format = 'yaml' if config_filename.endswith('.yaml') else 'json'
		code_blocks = re.findall(rf'```{file_format}\s*([^`]+)```', response, re.DOTALL)
		
		if not code_blocks:
			# 尝试匹配任意代码块
			code_blocks = re.findall(r'```(?:yaml|json)?\s*([^`]+)```', response, re.DOTALL)
		
		if code_blocks:
			fpath = os.path.join(self.config_dir, config_filename)
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(code_blocks[0].strip())
			self.logger.info(f"生成配置文件: {fpath}")
			return fpath
		else:
			self.logger.warning(f"未找到代码块，无法生成 {config_filename}")
			return None

	async def generate_prompt_file(self, prompt_filename, description_md, modules, config_files):
		"""
		步骤6: 生成单个提示词文件
		输入：提示词文件名 + 设计文档 + 模块信息 + 已生成的配置文件
		输出：生成的提示词文件路径
		
		支持的提示词文件：
		- government_prompts.yaml
		- rebels_prompts.yaml
		- residents_prompts.yaml
		"""
		self.logger.info(f"开始生成提示词文件: {prompt_filename}")
		
		# 读取模板
		template_path = os.path.join(self.config_template_dir, prompt_filename)
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		else:
			self.logger.warning(f"模板文件不存在: {template_path}")
		
		# 读取相关配置文件
		configs_str = ""
		if config_files:
			configs_str = "相关配置文件：\n"
			for fpath in config_files:
				if os.path.exists(fpath):
					fname = os.path.basename(fpath)
					with open(fpath, 'r', encoding='utf-8') as f:
						configs_str += f"\n{fname}:\n{f.read()}\n"
		
		# 确定角色类型
		role_type = prompt_filename.replace('_prompts.yaml', '')  # government, rebels, residents
		
		prompt = f"""你是多智能体模拟系统的提示词专家，请根据设计文档生成{role_type}的提示词文件。

设计文档：
{description_md}

涉及模块：
{modules}

提示词模板参考：
{template_content}

{configs_str}

要求：
1. 参考模板的结构和风格
2. 提示词要详细、具体、符合{role_type}角色特征
3. 根据设计文档中的实验背景和目标定制提示词
4. 确保提示词能引导Agent做出合理的决策
5. 与配置文件中的参数保持一致

请生成完整的YAML格式提示词文件。"""
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return None
		
		import re
		code_blocks = re.findall(r'```yaml\s*([^`]+)```', response, re.DOTALL)
		
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		if code_blocks:
			fpath = os.path.join(self.config_dir, prompt_filename)
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(code_blocks[0].strip())
			self.logger.info(f"生成提示词文件: {fpath}")
			return fpath
		else:
			self.logger.warning(f"未找到代码块，无法生成 {prompt_filename}")
			return None

	def _read_api_docs_by_modules(self, modules):
		"""
		根据涉及的模块读取相关API文档
		
		Args:
			modules: 模块信息（字典或字符串）
		
		Returns:
			str: 格式化的API文档字符串
		"""
		# 将modules转为字符串（用于检索）
		modules_str = str(modules).lower()
		
		# 模块到API文档的映射
		module_to_api = {
			'time': 'time.md',
			'map': 'map.md',
			'population': 'population.md',
			'resident': 'resident.md',
			'government': 'government.md',
			'rebellion': 'rebels.md',
			'rebels': 'rebels.md',
			'social': 'social_network.md',
			'job': 'job_market.md',
			'climate': 'climate.md',
			'transport': 'transport_economy.md',
			'towns': 'towns.md',
		}
		
		# 确定需要读取哪些API文档
		relevant_apis = set()
		
		# 基础模块（总是需要）
		relevant_apis.update(['time.md', 'map.md', 'population.md', 'resident.md', 'towns.md'])
		
		# 根据modules中的关键词添加相关API
		for keyword, api_file in module_to_api.items():
			if keyword in modules_str:
				relevant_apis.add(api_file)
		
		# 读取API文档
		api_docs_str = ""
		api_dir = os.path.join(self.docs_dir, 'api')
		
		for api_file in sorted(relevant_apis):
			api_path = os.path.join(api_dir, api_file)
			if os.path.exists(api_path):
				with open(api_path, 'r', encoding='utf-8') as f:
					content = f.read()
					# 只读取前2000字符（如果文档太长）
					if len(content) > 2000:
						content = content[:2000] + "\n...(文档已截断，完整内容请查看原文件)"
					api_docs_str += f"\n## {api_file}\n{content}\n"
		
		if not api_docs_str:
			api_docs_str = "（未找到相关API文档）"
		
		return api_docs_str

	def _read_relevant_api_docs(self, config_filename):
		"""
		根据配置文件名读取相关的API文档
		
		Args:
			config_filename: 配置文件名
		
		Returns:
			str: 格式化的API文档字符串（精简版）
		"""
		# 映射配置文件到相关API文档
		config_to_api = {
			'simulation_config.yaml': ['time.md', 'map.md', 'population.md'],
			'jobs_config.yaml': ['job_market.md', 'resident.md'],
			'resident_actions.yaml': ['resident.md', 'social_network.md'],
			'towns_data.json': ['towns.md', 'map.md'],
			'government_prompts.yaml': ['government.md'],
			'rebels_prompts.yaml': ['rebels.md'],
			'residents_prompts.yaml': ['resident.md', 'social_network.md'],
		}
		
		api_docs_str = ""
		api_dir = os.path.join(self.docs_dir, 'api')
		relevant_docs = config_to_api.get(config_filename, [])
		
		for doc_name in relevant_docs:
			doc_path = os.path.join(api_dir, doc_name)
			if os.path.exists(doc_path):
				with open(doc_path, 'r', encoding='utf-8') as f:
					content = f.read()
					# 只读取关键部分（前1500字符）
					if len(content) > 1500:
						content = content[:1500] + "\n...(已截断)"
					api_docs_str += f"\n## {doc_name}\n{content}\n"
		
		if not api_docs_str:
			api_docs_str = "（未找到相关API文档）"
		
		return api_docs_str

