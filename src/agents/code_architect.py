from .shared_imports import *

class CodeArchitectAgent(BaseAgent):
	# 常量定义
	MAX_RETRY_ATTEMPTS = 5  # 每个步骤的最大重试次数
	MAX_FIX_ATTEMPTS = 2     # 总体检查的最大修复次数
	"""
	编码师Agent，继承BaseAgent，负责根据设计文档和配置，自动生成模拟器代码、详细配置和提示词。
	工作流程：每次只生成一个文件，逐步完成所有任务。
	"""
	def __init__(self, agent_id, simulator_output_dir, main_output_dir, docs_dir, config_dir, config_template_dir, simulation_name, simulation_type='decision'):
		# 指定使用 CLAUDE 的 claude-sonnet-4-5-20250929 模型
		super().__init__(agent_id, group_type='code_architect', window_size=3, 
		                 model_api_name='CLAUDE', model_type_name='claude-sonnet-4-5-20250929')
		
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
		self.logger = LogManager.get_logger('code_architect')

	def _wait_for_user_confirmation(self, step_name): #测试用
		"""等待用户确认是否继续"""
		print(f"\n{'='*60}")
		print(f"✓ {step_name} 已完成")
		print(f"{'='*60}")
		user_input = input("是否继续？(按回车继续/输入'n'退出): ").strip().lower()
		if user_input == 'n':
			self.logger.info("用户选择退出")
			raise KeyboardInterrupt("用户选择退出流程")
		self.logger.info(f"用户确认继续，开始下一步...")
	
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
		user_input = input("是否重新生成？(y/yes=重新生成, 其他=跳过使用现有文件): ").strip().lower()
		
		if user_input in ['y', 'yes']:
			self.logger.info(f"用户选择重新生成: {file_description}")
			return True
		else:
			self.logger.info(f"跳过生成，使用现有文件: {file_description}")
			print(f"✓ 跳过，使用现有文件")
			return False

	async def generate_simulator_code(self, description_md, modules_config_yaml):
		"""
		步骤1：生成simulator模拟器主代码（simulator_[模拟名称].py）
		策略：先复制模板文件到目标位置，然后让LLM基于模板进行修改
		输入：设计文档 + 实验模板配置
		参考：根据simulation_type选择模板
		  - decision: src/simulation/simulator_template.py
		  - survey: src/simulation/simulator_survey_template.py
		
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
		project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		if self.simulation_type == 'survey':
			template_filename = 'simulator_survey_template.py'
		else:
			template_filename = 'simulator_template.py'
		
		template_path = os.path.join(project_root, 'src', 'simulation', template_filename)
		
		if not os.path.exists(template_path):
			self.logger.error(f"模板文件不存在: {template_path}")
			return ([], False)
		
		# 步骤1：复制模板到目标位置
		import shutil
		shutil.copy2(template_path, fpath)
		self.logger.info(f"✓ 已复制模板文件 ({template_filename}) 到: {fpath}")
		
		# 读取模板内容
		with open(template_path, 'r', encoding='utf-8') as f:
			template_content = f.read()

		# 直接替换类名
		simulator_class_name = self.simulation_name.replace('_', ' ').title().replace(' ', '') + 'Simulator'
		if self.simulation_type == 'survey':
			# 交流调查型模板类名是 SurveySimulator
			original_class_name = 'SurveySimulator'
			modified_content = template_content.replace('class SurveySimulator:', f'class {simulator_class_name}:')
		else:
			# 决策型模板类名是 YourSimulator
			original_class_name = 'YourSimulator'
			modified_content = template_content.replace('class YourSimulator:', f'class {simulator_class_name}:')
		
		# 保存修改后的模板
		with open(fpath, 'w', encoding='utf-8') as f:
			f.write(modified_content)
		self.logger.info(f"✓ 已替换类名: {original_class_name} -> {simulator_class_name}")
		
		# 步骤2：让LLM生成修改方案（JSON格式）
		prompt = self.prompts['generate_simulator_code_prompt'].format(
			template_content=template_content,
			description_md=description_md,
			modules_config_yaml=modules_config_yaml,
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
		project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		if self.simulation_type == 'survey':
			template_filename = 'main_survey_template.py'
		else:
			template_filename = 'main_template.py'
		
		template_path = os.path.join(project_root, 'entrypoints', template_filename)
		
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
		import re
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

	async def refine_simulator_functions(self, simulator_file_path, description_md, modules_config_yaml):
		"""
		步骤2：基于模块配置完善simulator文件（循环重试版本）
		分为三个子步骤，每个步骤都有重试机制：
		2.1 创建工作列表 - 从modules_config.yaml提取选定的模块（最多5次重试）
		2.2 逐个完善模块 - 根据每个模块的API文档完善相关代码（每个模块最多5次重试）
		2.3 总体检查与修复 - 检查问题并自动修复（最多2次重试）
		"""
		self.logger.info("=== 步骤2: 开始基于模块配置完善simulator ===")
		
		# 读取已生成的simulator代码
		if not os.path.exists(simulator_file_path):
			self.logger.error(f"Simulator文件不存在: {simulator_file_path}")
			return []
		
		# ============ 步骤2.1: 创建工作列表（循环重试） ============
		self.logger.info("步骤2.1: 从模块配置创建工作列表...")
		todo_list = None
		for attempt in range(1, self.MAX_RETRY_ATTEMPTS + 1):
			self.logger.info(f"  尝试 [{attempt}/{self.MAX_RETRY_ATTEMPTS}] 创建工作列表...")
			todo_list = await self._create_simulator_todo_list(modules_config_yaml, description_md)
			
			# 验证工作列表质量
			if todo_list is not None:  # 即使是空列表也是有效的
				if len(todo_list) == 0:
					self.logger.info("✓ 未发现需要完善的模块，代码已完整")
					break
				else:
					self.logger.info(f"✓ 成功创建工作列表（共 {len(todo_list)} 个模块）")
					break
			else:
				self.logger.warning(f"⚠️ 第 {attempt} 次创建工作列表失败")
				if attempt == self.MAX_RETRY_ATTEMPTS:
					# 超过5次，让大模型直接修复
					self.logger.error("❌ 创建工作列表失败次数过多，请求大模型修复...")
					fixed = await self._diagnose_failure(
						step_name="创建模块工作列表",
						file_path=simulator_file_path,
						error_info="无法成功从模块配置生成工作列表",
						attempt_count=attempt
					)
					if not fixed:
						self.logger.error("❌ 大模型修复失败")
						return []
					# 修复成功，重新读取代码并继续
		
		if not todo_list:
			return [simulator_file_path]  # 代码已完整
		
		# 显示工作列表
		self.logger.info(f"\n{'='*60}")
		self.logger.info(f"📋 模块工作列表（共 {len(todo_list)} 个模块）:")
		for idx, item in enumerate(todo_list, 1):
			self.logger.info(f"  {idx}. {item['module_name']} - {item.get('display_name', '')}")
			self.logger.info(f"     API文档: {item.get('api_doc', '')}")
			self.logger.info(f"     说明: {item.get('description', '')}")
		self.logger.info(f"{'='*60}\n")
		
		# ============ 步骤2.2: 逐个完善模块（每个模块循环重试） ============
		self.logger.info("步骤2.2: 逐个根据API文档完善模块...")
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
					self.logger.info(f"✓ 成功完善模块: {module_name}")
					break
				else:
					self.logger.warning(f"⚠️ 第 {attempt} 次完善失败")
				if attempt == self.MAX_RETRY_ATTEMPTS:
					# 超过5次，让大模型直接修复
					self.logger.error(f"❌ 模块 {module_name} 完善失败次数过多，请求大模型修复...")
					fixed = await self._diagnose_failure(
						step_name=f"完善模块 {module_name}",
						file_path=simulator_file_path,
						error_info=f"无法成功完善模块: {todo_item}",
						attempt_count=attempt
					)
					if fixed:
						self.logger.info(f"✓ 大模型已修复模块 {module_name}")
					else:
						self.logger.error(f"❌ 大模型修复失败，跳过模块 {module_name}")
					# 无论成功与否，继续处理下一个模块
		
		# ============ 步骤2.3: 总体检查与修复（循环重试） ============
		self.logger.info("\n步骤2.3: 总体检查与修复...")
		for attempt in range(1, self.MAX_FIX_ATTEMPTS + 1):
			self.logger.info(f"第 {attempt}/{self.MAX_FIX_ATTEMPTS} 次总体检查...")
			
			issues = await self._check_and_fix_code(simulator_file_path, description_md, modules_config_yaml, "simulator")
			
			if not issues:
				self.logger.info("✓ Simulator代码完整无误")
				return [simulator_file_path]
			else:
				self.logger.warning(f"发现 {len(issues)} 个问题: {issues[:3]}...")  # 只显示前3个
				if attempt < self.MAX_FIX_ATTEMPTS:
					self.logger.info("尝试自动修复...")
				else:
					# 最后一次仍有问题，请求大模型直接修复
					self.logger.error("❌ 总体检查仍有问题，请求大模型修复...")
					fixed = await self._diagnose_failure(
						step_name="总体检查与修复",
						file_path=simulator_file_path,
						error_info=f"剩余问题: {issues}",
						attempt_count=attempt
					)
					if not fixed:
						self.logger.error("❌ 大模型修复失败")
		
		# 等待用户确认
		self._wait_for_user_confirmation("完善simulator函数")
		
		return [simulator_file_path]

	async def _create_simulator_todo_list(self, modules_config_yaml, description_md):
		"""
		步骤2.1: 创建simulator的工作列表（基于模块配置）
		从modules_config.yaml中提取所有选定的模块
		"""
		prompt = self.prompts['create_simulator_todo_list_prompt'].format(
			modules_config_yaml=modules_config_yaml,
			description_md=description_md
		)

		response = await self.generate_llm_response(prompt)
		if not response:
			return []
		# self.logger.info(f"LLM返回的响应: {response}")
		# 提取JSON
		json_match = re.search(r'\[[\s\S]*\]', response)
		if json_match:
			try:
				todo_list = json.loads(json_match.group())
				self.logger.info(f"识别出 {len(todo_list)} 个需要完善的模块")
				for item in todo_list:
					self.logger.info(f"  - {item['module_name']} ({item['display_name']}): {item.get('description', '')}")
				
				# 等待用户确认
				self._wait_for_user_confirmation("创建simulator工作列表")
				
				return todo_list
			except json.JSONDecodeError as e:
				self.logger.error(f"JSON解析失败: {e}")
		
		return []

	async def _complete_simulator_function(self, simulator_file_path, todo_item, description_md):
		"""
		步骤2.2: 根据模块API文档完善simulator代码（增量修改版）
		只修改需要改动的方法，而不是替换整个文件
		"""
		module_name = todo_item['module_name']
		module_display_name = todo_item.get('display_name', module_name)
		api_doc_file = todo_item.get('api_doc', '')
		
		# 读取当前simulator代码
		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			simulator_content = f.read()
		
		# 读取API文档
		api_docs = ""
		if api_doc_file:
			api_path = os.path.join(self.docs_dir, 'api', api_doc_file)
			if os.path.exists(api_path):
				with open(api_path, 'r', encoding='utf-8') as f:
					api_docs = f.read()
				self.logger.info(f"读取API文档: {api_doc_file}")
			else:
				self.logger.warning(f"API文档不存在: {api_path}")
				return False
		else:
			self.logger.warning(f"未指定API文档")
			return False
		
		prompt = self.prompts['refine_simulator_with_module_prompt'].format(
			simulator_content=simulator_content,
			api_docs=api_docs,
			description_md=description_md
		)

		response = await self.generate_llm_response(prompt)
		if not response:
			return False
		
		self.logger.info(f"LLM返回的响应长度: {len(response)}")
		
		# 应用修改
		if self._apply_code_changes(simulator_file_path, response, "simulator"):
			# 等待用户确认
			self._wait_for_user_confirmation(f"完善模块 {module_name}")
			return True
		else:
			return False

	def _apply_code_changes(self, file_path, llm_response, file_type="simulator"):
		"""
		应用代码修改（统一处理LLM响应的增量修改方式）
		
		Args:
			file_path: 文件路径
			llm_response: LLM返回的响应（可以是JSON格式的修改，也可以是完整代码）
			file_type: 文件类型（"simulator" 或 "main"）
		
		Returns:
			bool: 是否成功应用修改
		"""
		import re
		import json
		
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
				if self._apply_incremental_changes(file_path, changes, file_type):
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
					if self._apply_incremental_changes(file_path, partial_changes, file_type):
						self.logger.info(f"✓ 已基于部分JSON增量修改并保存: {file_path}")
						return True
				self.logger.warning("部分提取也失败，尝试完整替换")
		
		# 策略2: 尝试提取完整代码块并替换
		code_blocks = re.findall(r'```python\s*([^`]+)```', llm_response, re.DOTALL)
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', llm_response, re.DOTALL)
		
		# 如果没有代码块标记，但包含代码特征，尝试直接使用
		if not code_blocks:
			if file_type == "simulator" and 'class ' in llm_response and 'def ' in llm_response:
				self.logger.warning("未找到代码块标记，尝试直接使用响应内容")
				code_blocks = [llm_response]
			elif file_type == "main" and 'import ' in llm_response and 'def ' in llm_response:
				self.logger.warning("未找到代码块标记，尝试直接使用响应内容")
				code_blocks = [llm_response]
		
		if code_blocks:
			code = code_blocks[0].strip()
			
			# 对simulator代码进行硬性缩进和空白行修正
			if file_type == "simulator":
				code = self._fix_indentation_and_whitespace(code)
			else:
				# main文件只做基本清理
				# 1. 将3个及以上连续空行替换为2个空行
				code = re.sub(r'\n\n\n+', '\n\n', code)
				
				# 2. 清理class和第一个方法之间的多余空白行（最多1个空行）
				code = re.sub(r'(class\s+\w+[^:]*:)\n\n+(\s+def\s)', r'\1\n\2', code)
				
				# 3. 确保文件末尾只有一个换行符
				code = code.rstrip() + '\n'
			
			# 特殊处理：main 文件需要保留入口部分
			if file_type == "main":
				# 读取原文件，提取入口部分
				if os.path.exists(file_path):
					with open(file_path, 'r', encoding='utf-8') as f:
						original_content = f.read()
					
					# 提取原文件中的入口部分（从 "# ===== 以下代码块不可删除或修改 =====" 到文件末尾）
					entry_match = re.search(r'(# ===== 以下代码块不可删除或修改 =====[\s\S]*)', original_content)
					
					# 检查新代码是否已包含入口部分
					has_entry = 'if __name__ == "__main__"' in code
					
					if entry_match and not has_entry:
						# 原文件有入口部分，新代码没有，需要补上
						entry_code = entry_match.group(1)
						code = code + '\n\n' + entry_code
						self.logger.info("✓ 已自动保留 main 文件的入口部分")
			
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(code)
			self.logger.info(f"✓ 已完整替换并保存: {file_path}")
			return True
		
		# 策略3: 都失败了，保留原文件
		self.logger.error("未找到可用的代码修改内容，保留原文件")
		return False
	
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
		import re
		import json
		
		item_key = 'methods' if file_type == 'simulator' else 'functions'
		name_key = 'method_name' if file_type == 'simulator' else 'function_name'
		code_key = 'method_code' if file_type == 'simulator' else 'function_code'
		
		self.logger.info(f"尝试从不完整的JSON中提取完整的{item_key}...")
		
		# 尝试找到完整的函数/方法对象
		# 匹配模式：{"method_name": "...", "method_code": "...", "description": "..."}
		pattern = rf'\{{\s*"{name_key}":\s*"([^"]+)"\s*,\s*"{code_key}":\s*"([^"]+(?:\\.[^"]*)*?)"\s*,\s*"description":\s*"([^"]+)"\s*\}}'
		
		complete_items = []
		for match in re.finditer(pattern, json_str, re.DOTALL):
			try:
				# 尝试解析单个对象
				item_json = match.group(0)
				item = json.loads(item_json)
				
				# 验证是否包含必要字段
				if name_key in item and code_key in item:
					complete_items.append(item)
					self.logger.info(f"✓ 提取到完整的{item_key[:-1]}: {item[name_key]}")
			except json.JSONDecodeError:
				continue
		
		if complete_items:
			self.logger.info(f"共提取到 {len(complete_items)} 个完整的{item_key}")
			return {item_key: complete_items}
		else:
			self.logger.warning(f"未能从JSON中提取任何完整的{item_key}")
			return None

	def _apply_incremental_changes(self, file_path, changes, file_type="simulator"):
		"""
		应用增量修改（内部方法，处理JSON格式的修改）
		
		Args:
			file_path: 文件路径
			changes: JSON格式的修改内容（dict，包含methods/functions和delete_methods/delete_functions）
			file_type: 文件类型（"simulator" 或 "main"）
		
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
					
					# 匹配函数/方法定义并删除
					# 对于main文件，需要在入口标记前停止匹配
					if file_type == "main":
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\n#\s*=====\s*以下代码块不可删除或修改\s*=====|\Z)"
					else:
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\Z)"
					match = re.search(pattern, modified_content, re.DOTALL)
					
					if match:
						# 删除匹配的函数/方法（包括前导空白行）
						start_pos = match.start()
						end_pos = match.end()
						
						# 检查前面是否有多余的空行，一并删除
						while start_pos > 0 and modified_content[start_pos-1] == '\n':
							start_pos -= 1
						
						modified_content = modified_content[:start_pos] + modified_content[end_pos:]
						self.logger.info(f"✓ 已删除{'方法' if file_type == 'simulator' else '函数'}: {pure_name}")
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
				
				# 查找并替换方法/函数
				# 匹配函数定义，支持 def 和 async def
				# 对于main文件，需要在入口标记前停止匹配
				if file_type == "main":
					pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\n#\s*=====\s*以下代码块不可删除或修改\s*=====|\Z)"
				else:
					pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\([^)]*\):.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\Z)"
				match = re.search(pattern, modified_content, re.DOTALL)
				
				if match:
					# 找到了，替换现有方法
					# 获取原方法/函数的缩进
					indent = match.group(1)
					# 确保新代码有正确的缩进（空行保持为空行，不添加缩进空格）
					lines = item_code.split('\n')
					indented_lines = []
					for line in lines:
						if line.strip():  # 非空行，添加缩进
							indented_lines.append(indent + line)
						else:  # 空行，保持为空
							indented_lines.append('')
					indented_code = '\n'.join(indented_lines)
					
					# 替换方法/函数
					modified_content = modified_content[:match.start()] + indented_code + modified_content[match.end():]
					self.logger.info(f"✓ 已替换{'方法' if file_type == 'simulator' else '函数'}: {pure_name}")
				else:
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
								# 添加方法代码（已经包含缩进）
								lines = method_info['code'].split('\n')
								for line in lines:
									if line.strip():
										new_methods_code += indent + line + '\n'
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
			
			# 保存修改后的代码
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(modified_content)
			
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
			
			return True
			
		except Exception as e:
			self.logger.error(f"应用增量修改失败: {e}")
			return False

	def _fix_indentation_and_whitespace(self, code_content):
		"""
		硬性修正代码缩进和空白行问题
		
		主要处理：
		1. 将tab统一替换为4个空格
		2. 所有 def 或 async def 函数定义增加4个空格缩进
		3. 清理多余的连续空白行
		4. 确保类方法的缩进一致
		
		Args:
			code_content: 原始代码内容
		
		Returns:
			str: 修正后的代码内容
		"""
		# 将tab替换为4个空格
		code = code_content.replace('\t', '    ')
		
		# 所有 def 或 async def 行缩进严格为4个空格（多则减少，少则增加）
		lines = code.split('\n')
		fixed_lines = []
		for line in lines:
			match = re.match(r'^(\s*)(async\s+)?def\s+', line)
			if match:
				# 只保留4个空格缩进
				line = '    ' + line.lstrip()
			fixed_lines.append(line)
		code = '\n'.join(fixed_lines)
		
		# 清理多余的连续空白行（4个及以上 → 2个，即最多保留1个空行）
		code = re.sub(r'\n\n\n\n+', '\n\n\n', code)
		
		# 清理class和第一个方法之间的多余空行（最多1个空行）
		code = re.sub(r'(class\s+\w+[^:]*:)\n\n+(\s+(?:async\s+)?def\s)', r'\1\n\2', code)
		
		# 清理方法之间的多余空行（最多保留2个空行，即1个空白行）
		code = re.sub(r'(\n\s+(?:async\s+)?def\s[^\n]+:[^\n]*)\n\n\n+(\s+(?:async\s+)?def\s)', r'\1\n\n\2', code)
		
		# 确保文件末尾只有一个换行符
		code = code.rstrip() + '\n'
		
		return code

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
		
		# 构建检查提示词
		if file_type == "simulator":
			prompt = self.prompts['check_and_fix_simulator_prompt'].format(
				code_content=code_content,
				description_md=description_md
			)
		else:  # main
			prompt = self.prompts['check_and_fix_main_prompt'].format(
				code_content=code_content,
				simulator_content=simulator_content[:1000] if simulator_content else '',
				description_md=description_md
			)
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.warning("检查失败：LLM返回空响应")
			return ["LLM返回空响应"]
		
		# 检查是否返回OK
		if 'OK' in response.upper() and len(response.strip()) < 20:
			# 等待用户确认
			self._wait_for_user_confirmation(f"检查代码 ({file_type}) - 无问题")
			return []  # 无问题
		
		# 应用修改
		if self._apply_code_changes(file_path, response, file_type):
			self._wait_for_user_confirmation(f"检查并修复代码 ({file_type})")
			return []  # 已修复
		else:
			# 修复失败
			self.logger.warning("无法应用修复内容")
			return ["无法应用修复内容"]

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
		for attempt in range(1, self.MAX_FIX_ATTEMPTS + 1):
			self.logger.info(f"第 {attempt}/{self.MAX_FIX_ATTEMPTS} 次总体检查...")
			
			issues = await self._check_and_fix_code(main_file_path, description_md, modules_config_yaml, "main", simulator_content)
			
			if not issues:
				self.logger.info("✓ Main代码完整无误")
				return [main_file_path]
			else:
				self.logger.warning(f"发现 {len(issues)} 个问题: {issues[:3]}...")  # 只显示前3个
				if attempt < self.MAX_FIX_ATTEMPTS:
					self.logger.info("尝试自动修复...")
				else:
					# 最后一次仍有问题，请求大模型直接修复
					self.logger.error("❌ 总体检查仍有问题，请求大模型修复...")
					fixed = await self._diagnose_failure(
						step_name="Main总体检查与修复",
						file_path=main_file_path,
						error_info=f"剩余问题: {issues}",
						attempt_count=attempt
					)
					if not fixed:
						self.logger.error("❌ 大模型修复失败")
		
		return [main_file_path]

	async def generate_config_file(self, config_filename, description_md, modules_config_yaml, previous_configs=None):
		"""
		步骤5: 生成单个配置文件
		输入：配置文件名 + 设计文档 + 模块配置YAML + 已生成的配置（可选）
		输出：生成的配置文件路径
		
		支持的配置文件：
		- simulation_config.yaml
		- jobs_config.yaml
		- resident_actions.yaml
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
				template_content = f.read()
		else:
			self.logger.warning(f"模板文件不存在: {template_path}")
		
		# 读取API文档（根据配置类型选择相关文档）
		api_docs = self._read_relevant_api_docs(config_filename)
		
		file_format = 'YAML' if config_filename.endswith('.yaml') else 'JSON'
		prompt = self.prompts['generate_config_file_prompt'].format(
			config_filename=config_filename,
			description_md=description_md,
			modules=modules_config_yaml,
			template_content=template_content,
			api_docs=api_docs,
			file_format=file_format
		)
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return None
		
		import re
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
			return fpath
		else:
			self.logger.warning(f"未找到代码块，无法生成 {config_filename}")
			self.logger.debug(f"LLM响应预览: {response[:500]}")
			return None

	async def generate_prompt_file(self, prompt_filename, description_md, config_files):
		"""
		步骤6: 生成单个提示词文件
		输入：提示词文件名 + 设计文档 + 模块配置YAML + 对应代码
		输出：生成的提示词文件路径
		
		支持的提示词文件：
		- government_prompts.yaml -> 参考 src/agents/government.py
		- rebels_prompts.yaml -> 参考 src/agents/rebels.py
		- residents_prompts.yaml -> 参考 src/agents/resident.py
		
		Args:
			prompt_filename: 提示词文件名
			description_md: 设计文档
		"""
		self.logger.info(f"开始生成提示词文件: {prompt_filename}")
		
		# 目标文件路径
		fpath = os.path.join(self.config_dir, prompt_filename)
		
		# 检查文件是否已存在
		if not self._check_file_exists_and_ask(fpath, f"提示词文件 ({prompt_filename})"):
			if os.path.exists(fpath):
				return fpath
			else:
				return None
		
		# 读取模板
		template_path = os.path.join(self.config_template_dir, prompt_filename)
		template_content = ""
		if os.path.exists(template_path):
			with open(template_path, 'r', encoding='utf-8') as f:
				template_content = f.read()
		else:
			self.logger.warning(f"模板文件不存在: {template_path}")
		
		# 确定角色类型和对应代码文件
		role_type = prompt_filename.replace('_prompts.yaml', '')  # government, rebels, residents
		
		# 映射提示词文件到对应代码文件
		agent_file_mapping = {
			'government': 'government.py',
			'rebels': 'rebels.py',
			'residents': 'resident.py'
		}
		
		# 读取对应的代码文件
		agent_code_str = ""
		agent_filename = agent_file_mapping.get(role_type)
		if agent_filename:
			project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
			agent_file_path = os.path.join(project_root, 'src', 'agents', agent_filename)
			if os.path.exists(agent_file_path):
				with open(agent_file_path, 'r', encoding='utf-8') as f:
					agent_code_content = f.read()
					agent_code_str = f"参考代码 ({agent_filename}):\n```python\n{agent_code_content}\n```\n"
				self.logger.info(f"已读取代码: {agent_file_path}")
			else:
				self.logger.warning(f"代码文件不存在: {agent_file_path}")
				agent_code_str = f"（未找到对应的代码: {agent_filename}）"
		else:
			agent_code_str = f"（未知的角色类型: {role_type}）"
		
		prompt = self.prompts['generate_prompt_file_prompt'].format(
			role_type=role_type,
			description_md=description_md,
			template_content=template_content,
			configs_str=agent_code_str
		)
		
		response = await self.generate_llm_response(prompt)
		if not response:
			self.logger.error("LLM返回空响应")
			return None
		
		import re
		# 策略1: 尝试提取带yaml标记的代码块
		code_blocks = re.findall(r'```yaml\s*([^`]+)```', response, re.DOTALL)
		
		# 策略2: 尝试提取任意代码块
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		# 策略3: 如果没有代码块标记，但响应包含YAML特征，直接使用
		if not code_blocks:
			# 检查是否包含YAML特征（如缩进、冒号、键值对等）
			if ':' in response and '\n' in response:
				# 尝试清理响应中的解释性文字，只保留YAML内容
				# 通常YAML内容会以某个键开始（如 system_prompt:）
				lines = response.split('\n')
				yaml_start = -1
				for i, line in enumerate(lines):
					# 寻找第一个看起来像YAML键的行（顶层键，无缩进）
					if line and not line.startswith(' ') and ':' in line and not line.startswith('#'):
						yaml_start = i
						break
				
				if yaml_start >= 0:
					# 从该行开始提取到末尾
					yaml_content = '\n'.join(lines[yaml_start:]).strip()
					self.logger.info(f"使用直接提取的YAML内容（无代码块标记）")
					code_blocks = [yaml_content]
		
		if code_blocks:
			fpath = os.path.join(self.config_dir, prompt_filename)
			with open(fpath, 'w', encoding='utf-8') as f:
				f.write(code_blocks[0].strip())
			self.logger.info(f"生成提示词文件: {fpath}")
			return fpath
		else:
			self.logger.warning(f"未找到代码块，无法生成 {prompt_filename}")
			self.logger.debug(f"LLM响应预览: {response[:500]}")
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

	async def _diagnose_failure(self, step_name, file_path, error_info, attempt_count):
		"""
		当某个步骤失败超过5次后，请求大模型诊断并直接修复问题
		
		Args:
			step_name: 失败的步骤名称
			file_path: 相关文件路径
			error_info: 错误信息
			attempt_count: 尝试次数
		
		Returns:
			bool: 是否成功修复
		"""
		self.logger.info(f"🔍 正在请求大模型诊断并修复步骤 '{step_name}' 的问题...")
		
		# 读取当前文件内容
		file_content = ""
		if os.path.exists(file_path):
			with open(file_path, 'r', encoding='utf-8') as f:
				file_content = f.read()
		
		prompt = self.prompts['diagnose_failure_prompt'].format(
			step_name=step_name,
			attempt_count=attempt_count,
			error_info=error_info,
			file_content=file_content
		)
		
		response = await self.generate_llm_response(prompt)
		
		if not response:
			self.logger.error("❌ 大模型未返回有效响应")
			return False
		
		# 提取修复后的代码
		import re
		code_blocks = re.findall(r'```python\s*([^`]+)```', response, re.DOTALL)
		if not code_blocks:
			code_blocks = re.findall(r'```\s*([^`]+)```', response, re.DOTALL)
		
		if code_blocks:
			fixed_code = code_blocks[0].strip()
			
			# 保存修复后的代码
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(fixed_code)
			
			self.logger.info(f"✓ 大模型已修复代码并保存到: {file_path}")
			self.logger.info(f"修复的代码长度: {len(fixed_code)} 字符")
			return True
		else:
			self.logger.error("❌ 未能从大模型响应中提取代码块")
			self.logger.debug(f"大模型响应预览: {response[:500]}")
			return False

	async def _extract_module_api_docs_from_error(self, error_traceback):
		"""
		从错误堆栈中提取相关模块和配置文件
		使用LLM智能分析错误信息，判断需要哪些API文档和配置文件
		
		Args:
			error_traceback: 错误堆栈信息
		
		Returns:
			tuple: (api_docs_str, config_files_dict)
				- api_docs_str: API文档内容字符串
				- config_files_dict: 配置文件内容字典 {文件名: 内容}
		"""
		# 模块到API文档的映射
		module_to_file = {
			'Climate': 'climate.md',
			'Time': 'time.md',
			'Map': 'map.md',
			'Population': 'population.md',
			'Resident': 'resident.md',
			'Government': 'government.md',
			'Rebels': 'rebels.md',
			'SocialNetwork': 'social_network.md',
			'Job_market': 'job_market.md',
			'TransportEconomy': 'transport_economy.md',
			'Towns': 'towns.md',
		}
		
		# 构建模块映射说明
		module_mapping_str = "\n".join([f"- {module}: {file}" for module, file in module_to_file.items()])
		
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
			import re
			import json
			json_match = re.search(r'\{[\s\S]*?\}', response)
			if json_match:
				try:
					result = json.loads(json_match.group(0))
					relevant_api_files = result.get('api_docs', [])
					relevant_config_files = result.get('config_files', [])
					self.logger.info(f"✓ LLM分析识别到 {len(relevant_api_files)} 个API文档: {relevant_api_files}")
					self.logger.info(f"✓ LLM分析识别到 {len(relevant_config_files)} 个配置文件: {relevant_config_files}")
				except json.JSONDecodeError as e:
					self.logger.warning(f"解析LLM返回的JSON失败: {e}")
		else:
			self.logger.warning("LLM返回空响应，使用兜底方案")
		
		# 兜底方案：如果LLM分析失败，使用正则匹配
		if not relevant_api_files:
			import re
			module_pattern = r"'(\w+)'\s+object\s+has\s+no\s+attribute"
			matches = re.findall(module_pattern, error_traceback)
			relevant_api_files = [module_to_file.get(m) for m in matches if module_to_file.get(m)]
			if relevant_api_files:
				self.logger.info(f"✓ 正则匹配识别到 {len(relevant_api_files)} 个API文档: {relevant_api_files}")
		
		# 读取相关模块的API文档
		api_docs_str = ""
		api_dir = os.path.join(self.docs_dir, 'api')
		
		for api_file in set(relevant_api_files):  # 去重
			if api_file:
				api_path = os.path.join(api_dir, api_file)
				if os.path.exists(api_path):
					with open(api_path, 'r', encoding='utf-8') as f:
						content = f.read()
						# 提取模块名
						module_name = api_file.replace('.md', '').replace('_', ' ').title()
						api_docs_str += f"\n## {module_name} 模块API文档 ({api_file})\n{content}\n"
					self.logger.info(f"✓ 已加载 {api_file} 模块的API文档")
		
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

	async def fix_runtime_errors(self, error_message, error_traceback, main_file_path, simulator_file_path, max_attempts=3):
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
		
		# 读取当前代码
		with open(main_file_path, 'r', encoding='utf-8') as f:
			main_content = f.read()
		with open(simulator_file_path, 'r', encoding='utf-8') as f:
			simulator_content = f.read()
		
		# 从错误堆栈中提取相关模块的API文档和配置文件（使用LLM智能分析）
		module_api_docs, config_files_dict = await self._extract_module_api_docs_from_error(error_traceback)
		
		# 格式化配置文件内容
		config_files_str = ""
		if config_files_dict:
			config_files_str = "\n相关配置文件：\n"
			for filename, content in config_files_dict.items():
				config_files_str += f"\n{'='*60}\n"
				config_files_str += f"配置文件: {filename}\n"
				config_files_str += f"{'='*60}\n{content}\n"
		
		for attempt in range(1, max_attempts + 1):
			self.logger.info(f"第 {attempt}/{max_attempts} 次修复尝试...")
			
			# 将API文档和配置文件合并到一起
			reference_docs = module_api_docs if module_api_docs else ""
			if config_files_str:
				reference_docs += config_files_str
			if not reference_docs:
				reference_docs = "（无相关参考文档）"
			
			# 提示词
			prompt = self.prompts['fix_runtime_errors_prompt'].format(
				error_traceback=error_traceback,
				main_file_path=main_file_path,
				main_content=main_content,
				simulator_file_path=simulator_file_path,
				simulator_content=simulator_content,
				module_api_docs=reference_docs
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
		import re
		
		# 只支持策略：JSON增量修改
		# 查找带有文件标记的JSON块
		
		# 提取 MAIN FILE 的JSON修改
		main_json_pattern = r'```json\s*#\s*===\s*MAIN\s*FILE\s*===\s*(\{[\s\S]*?\})\s*```'
		main_json_match = re.search(main_json_pattern, response, re.DOTALL | re.IGNORECASE)
		
		# 提取 SIMULATOR FILE 的JSON修改
		simulator_json_pattern = r'```json\s*#\s*===\s*SIMULATOR\s*FILE\s*===\s*(\{[\s\S]*?\})\s*```'
		simulator_json_match = re.search(simulator_json_pattern, response, re.DOTALL | re.IGNORECASE)
		
		main_fixed = False
		simulator_fixed = False
		
		# 应用main文件的增量修改
		if main_json_match:
			try:
				json_content = main_json_match.group(1)
				# 构造完整的JSON代码块供_apply_code_changes处理
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
		
		# 如果成功应用了增量修改，返回成功
		if main_fixed or simulator_fixed:
			return True
		
		# 兼容：尝试查找单个JSON块（不带文件标记）
		# 这种情况下根据内容判断是main还是simulator
		single_json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
		if single_json_match:
			json_content = single_json_match.group(1)
			json_block = f"```json\n{json_content}\n```"
			
			# 判断是functions还是methods
			if '"functions"' in json_content:
				# main文件
				if self._apply_code_changes(main_file_path, json_block, "main"):
					self.logger.info("✓ 已修复 main 文件（增量修改）")
					return True
				else:
					self.logger.error("❌ 应用main文件增量修改失败")
			elif '"methods"' in json_content:
				# simulator文件
				if self._apply_code_changes(simulator_file_path, json_block, "simulator"):
					self.logger.info("✓ 已修复 simulator 文件（增量修改）")
					return True
				else:
					self.logger.error("❌ 应用simulator文件增量修改失败")
			else:
				self.logger.error("❌ JSON内容既不包含'functions'也不包含'methods'，无法判断文件类型")
		
		# 所有策略都失败，直接报错
		self.logger.error("❌ 未能从响应中提取有效的JSON增量修改内容")
		self.logger.error("期望格式：")
		self.logger.error("```json")
		self.logger.error("# === MAIN FILE ===")
		self.logger.error('{"functions": [{"function_name": "...", "function_code": "...", "description": "..."}]}')
		self.logger.error("```")
		self.logger.error("或：")
		self.logger.error("```json")
		self.logger.error("# === SIMULATOR FILE ===")
		self.logger.error('{"methods": [{"method_name": "...", "method_code": "...", "description": "..."}]}')
		self.logger.error("```")
		self.logger.debug(f"LLM响应预览: {response[:500]}")
		return False
