import json
import math
import os
import pickle
import re
import shutil
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import yaml
from openai import OpenAI

try:
    import networkx as nx
except Exception:  # pragma: no cover
    nx = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


class CodeChangeMixin:
	"""共享代码修改、验证、修复与接口读取工具方法。

	该 Mixin 设计为与 BaseAgent 子类一起使用，提供 CodeArchitectAgent 和
	CodeFixerAgent 都需要的基础代码/配置操作能力。
	"""
	def _get_chroma_client(self):
		"""返回复用的 Chroma PersistentClient，避免并发检索时反复新建 client。"""
		if getattr(self, '_chroma_client', None) is None:
			self._chroma_client = chromadb.PersistentClient(path=self._rag_db_path)
		return self._chroma_client

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

		def _parse_path_tokens(path):
			"""把点分路径解析为 token 列表，支持列表下标。

			支持的写法：
			  a.b.c            -> ['a', 'b', 'c']
			  influences[5]    -> ['influences', 5]
			  a[2].b           -> ['a', 2, 'b']
			  a.2.b            -> ['a', 2, 'b']   （纯数字段当作列表下标）
			下标统一解析为 int，dict 键解析为 str。
			"""
			tokens = []
			for segment in path.split('.'):
				if segment == '':
					continue
				# 先取出 [n] 之前的名字部分（可能为空，如 "[5]"）
				name, *brackets = re.split(r'\[(\d+)\]', segment)
				if name != '':
					# 纯数字段（如 "influences.5"）按下标处理，否则按 dict 键
					tokens.append(int(name) if name.isdigit() else name)
				# re.split 会把捕获的数字夹在结果里，过滤出数字部分
				for b in brackets:
					if b is not None and b != '':
						tokens.append(int(b))
			return tokens

		def _set_nested_value(data_dict, path, value):
			tokens = _parse_path_tokens(path)
			if not tokens:
				return None

			container = data_dict
			# 逐级下钻到倒数第二个 token，按下一个 token 的类型决定容器类型
			for idx, token in enumerate(tokens[:-1]):
				next_token = tokens[idx + 1]
				want_list = isinstance(next_token, int)

				if isinstance(token, int):
					# 当前层是列表下标
					if not isinstance(container, list):
						# 容器类型不匹配，无法安全索引，放弃
						return None
					while len(container) <= token:
						container.append({} if not want_list else [])
					child = container[token]
					if want_list and not isinstance(child, list):
						container[token] = []
					elif not want_list and not isinstance(child, dict):
						container[token] = {}
					container = container[token]
				else:
					# 当前层是 dict 键
					if not isinstance(container, dict):
						return None
					child = container.get(token)
					if want_list and not isinstance(child, list):
						container[token] = []
					elif not want_list and not isinstance(child, dict):
						container[token] = {}
					container = container[token]

			last = tokens[-1]
			if isinstance(last, int):
				if not isinstance(container, list):
					return None
				while len(container) <= last:
					container.append(None)
				old_value = container[last]
				container[last] = value
				return old_value
			else:
				if not isinstance(container, dict):
					return None
				old_value = container.get(last)
				container[last] = value
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

	def _plugin_dir(self, plugin_name: str) -> str:
		from src.utils import plugin_generator as pg
		return pg.plugin_dir(self._rag_project_root, plugin_name)

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

	def _rag_query_paper_candidates(self, query_text: str, top_k: int = 3, max_distance: float = 1.0) -> List[str]:
		"""从papers集合向量检索相关论文，提取候选影响对文本。
		"""
		query_text = (query_text or '').strip()
		if not query_text:
			return []
		try:
			chroma_client = self._get_chroma_client()
			collection = chroma_client.get_collection(name='papers')
		except Exception:
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		embedding = self._rag_embed(client, query_text, dimensions=1024)
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

	# ============================================================
	#  步骤0 初始候选：因果图拓扑路径发现（L0-graph）
	# ============================================================

	def _rag_node_label(self, G, node) -> str:
		"""取图节点的代表性显示名，缺失则回退节点 key。"""
		try:
			return G.nodes[node].get('label') or node
		except Exception:
			return node

	def _rag_anchor_concepts(self, concepts: List[str], G, semantic_top_k: int = 3,
								 collection_name: str = "concepts") -> Dict[str, Tuple[str, float]]:
		"""把英文概念锚定到因果图节点：先精确/surface_form/label 匹配，
		未命中则用指定集合语义召回。
		- collection_name="concepts": 取 metadata.concept 单节点
		- collection_name="causal_claims": 取 cause/effect 双节点（旧逻辑，降级用）

		返回 {node_key: (来源概念, cos_sim)}；每个输入概念最多贡献 2 个节点，避免锚点爆炸。
		"""
		anchors: Dict[str, Tuple[str, float]] = {}
		collection = None
		client = None
		is_fallback = (collection_name == "causal_claims")
		for concept in concepts:
			concept = (concept or "").strip()
			if not concept:
				continue
			nodes: List[Tuple[str, float]] = []
			node = self._rag_locate_node(concept, G)
			if node:
				nodes.append((node, 1.0))
				self.logger.info(f"[L0-anchor] 概念 {concept!r} 精确匹配到图节点 {node!r} (cos_sim=1.000, 精确)")
			else:
				try:
					if collection is None:
						collection = self._get_chroma_client().get_collection(name=collection_name)
						client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
					emb = self._rag_embed(client, concept, dimensions=1024)
					if emb:
						res = collection.query(
							query_embeddings=[emb],
							n_results=semantic_top_k,
							include=['metadatas', 'distances'],
						)
						for idx, meta in enumerate((res.get('metadatas', [[]])[0] or [])):
							distance = (res.get('distances', [[]])[0] or [None])[idx]
							# ChromaDB cosine distance = 1 - cos_sim
							cos_sim = max(0.0, 1.0 - distance) if distance is not None else None
							if is_fallback:
								# causal_claims: cause + effect both candidates
								for role in ('cause', 'effect'):
									txt = (meta or {}).get(role)
									if not txt:
										continue
									n = self._rag_locate_node(txt, G)
									if n and n not in [x[0] for x in nodes]:
										nodes.append((n, cos_sim))
										sim_str = f"{cos_sim:.4f}" if cos_sim is not None else "N/A"
										self.logger.info(
											f"[L0-anchor] 概念 {concept!r} 语义召回#{idx} "
											f"{role}={txt!r} -> 锚定到节点 {n!r} "
											f"(cos_sim={sim_str}, 降级补充)"
										)
							else:
								# concepts: single concept field
								matched = (meta or {}).get('concept', '').strip()
								if not matched:
									continue
								n = self._rag_locate_node(matched, G)
								if n and n not in [x[0] for x in nodes]:
									nodes.append((n, cos_sim))
									sim_str = f"{cos_sim:.4f}" if cos_sim is not None else "N/A"
									self.logger.info(
										f"[L0-anchor] 概念 {concept!r} 语义召回#{idx} "
										f"concept={matched!r} -> 锚定到节点 {n!r} "
										f"(cos_sim={sim_str})"
									)
							if len(nodes) >= 2:
								break
				except Exception as exc:
					self.logger.info(f"[L0-anchor] 概念语义锚定失败 {concept!r}: {exc}")
			for n, sim in nodes[:2]:
				anchors.setdefault(n, (concept, sim))
		# ---- 锚定结构汇总 ----
		by_concept: Dict[str, List[str]] = {}
		for n, (src, _sim) in anchors.items():
			by_concept.setdefault(src, []).append(n)
		tag = " (降级补充)" if is_fallback else ""
		self.logger.info(f"[L0-anchor] 锚定结构汇总 (来源概念 -> 图节点){tag}:")
		for src, nodes in by_concept.items():
			self.logger.info(f"  {src!r} -> {nodes}")
		self.logger.info(f"[L0-anchor] 锚定完成: {len(anchors)} 个节点{tag}")
		return anchors

	def _rag_edge_evidence_score(self, data: Dict[str, Any], causal_methods: set) -> float:
		"""单条因果边的证据强度：因果识别方法 +2，certainty=certain +1。"""
		score = 0.0
		method = str(data.get('method') or '').strip().lower()
		certainty = str(data.get('certainty') or '').strip().lower()
		if method in causal_methods:
			score += 2.0
		if certainty == 'certain':
			score += 1.0
		return score

	def _rag_best_edge(self, G, u: str, v: str, causal_methods: set) -> Optional[Dict[str, Any]]:
		"""MultiDiGraph 中 u→v 的多重边里选证据最强的一条边属性。"""
		edges = G.get_edge_data(u, v)
		if not edges:
			return None
		best = None
		best_score = None
		edge_details = []
		for _key, data in edges.items():
			s = self._rag_edge_evidence_score(data, causal_methods)
			method = data.get('method', '无')
			certainty = data.get('certainty', '无')
			edge_details.append(f"(method={method}, certainty={certainty}, score={s})")
			if best_score is None or s > best_score:
				best_score = s
				best = data
		if len(edges) > 1:
			self.logger.debug(
				f"[L0-edge] {u}→{v} 含 {len(edges)} 条多重边: "
				f"{'; '.join(edge_details)} → 选中 score={best_score}"
			)
		return best

	def _rag_score_chain(self, path: List[str], hop_edges: List[Dict[str, Any]], anchor_set: set, causal_methods: set) -> float:
		"""传导链打分：覆盖锚点数为主，平均证据强度 tie-break，路径越长略减分。"""
		coverage = sum(1 for n in path if n in anchor_set)
		avg_evidence = (
			sum(self._rag_edge_evidence_score(e, causal_methods) for e in hop_edges) / len(hop_edges)
			if hop_edges else 0.0
		)
		length_penalty = 0.05 * (len(hop_edges) - 1)
		return coverage * 10.0 + avg_evidence - length_penalty

	@staticmethod
	def _rag_is_subpath(short: Tuple[str, ...], long: Tuple[str, ...]) -> bool:
		"""short 是否为 long 的连续子序列。"""
		n, m = len(short), len(long)
		if n > m:
			return False
		for i in range(m - n + 1):
			if long[i:i + n] == short:
				return True
		return False

	def _rag_dedup_subpaths(self, scored: List[Tuple[float, List[str], List[Dict[str, Any]]]], top_k: int) -> List[Tuple[float, List[str], List[Dict[str, Any]]]]:
		"""按分数降序，剔除与已选链互为连续子路径的冗余项，取 Top-K。"""
		selected: List[Tuple[float, List[str], List[Dict[str, Any]]]] = []
		for item in scored:
			path = tuple(item[1])
			dup = False
			for sitem in selected:
				spath = tuple(sitem[1])
				if self._rag_is_subpath(path, spath) or self._rag_is_subpath(spath, path):
					dup = True
					break
			if not dup:
				selected.append(item)
			if len(selected) >= top_k:
				break
		return selected

	def _rag_search_chain_candidates(
			self, G, anchor_set: set,
			hops: int, max_paths_per_pair: int, causal_methods: set,
		) -> List[Tuple[float, List[str], List[Dict[str, Any]]]]:
		"""对锚定节点集做有向路径搜索，返回 [(score, path, hop_edges), ...]。"""
		scored: List[Tuple[float, List[str], List[Dict[str, Any]]]] = []
		seen_paths: set = set()
		anchors_list = sorted(anchor_set)
		pair_stats: Dict[str, Dict[str, int]] = {}
		for a in anchors_list:
			for b in anchors_list:
				if a == b:
					continue
				pair_label_a = self._rag_node_label(G, a)
				pair_label_b = self._rag_node_label(G, b)
				pair_key = f"{pair_label_a}->{pair_label_b}"
				stats = {"原始路径": 0, "跳数过滤": 0, "重复路径": 0, "缺边丢弃": 0, "候选通过": 0}
				try:
					paths_iter = nx.all_simple_paths(G, a, b, cutoff=hops)
				except Exception:
					pair_stats[pair_key] = stats
					continue
				count = 0
				for path in paths_iter:
					if count >= max_paths_per_pair:
						count += 1
						break
					count += 1
					stats["原始路径"] += 1
					edge_n = len(path) - 1
					if edge_n < 1 or edge_n > hops:
						stats["跳数过滤"] += 1
						continue
					sig = tuple(path)
					if sig in seen_paths:
						stats["重复路径"] += 1
						continue
					seen_paths.add(sig)
					hop_edges: List[Dict[str, Any]] = []
					ok = True
					for i in range(len(path) - 1):
						e = self._rag_best_edge(G, path[i], path[i + 1], causal_methods)
						if e is None:
							ok = False
							break
						hop_edges.append(e)
					if not ok:
						stats["缺边丢弃"] += 1
						continue
					score = self._rag_score_chain(path, hop_edges, anchor_set, causal_methods)
					scored.append((score, path, hop_edges))
					stats["候选通过"] += 1
				pair_stats[pair_key] = stats
		# ---- 节点对统计 ----
		if pair_stats:
			self.logger.info("[L0-graph] 节点对统计:")
			for pair_key, st in sorted(pair_stats.items()):
				total = st["原始路径"]
				passed = st["候选通过"]
				pct = f"{passed / total * 100:.0f}%" if total else "-"
				self.logger.info(
					f"  {pair_key}: {st['原始路径']}->{st['跳数过滤']}->{st['重复路径']}->{st['缺边丢弃']}->{st['候选通过']} ({pct})"
				)
		return scored
	def _rag_discover_graph_chains(self, concepts: List[str], top_k: int = 5) -> List[str]:
		"""图拓扑路径发现：概念→图节点锚定→节点对间 2-4 跳有向路径→按覆盖度+证据排序，
		返回 Top-K 传导链文本行（供 generate_influence_pairs_prompt 消费）。失败时静默返回 []。
		"""
		concepts = [c.strip() for c in (concepts or []) if c and str(c).strip()]
		if not concepts:
			return []
		if nx is None:
			self.logger.debug("networkx 不可用，跳过图路径发现")
			return []
		G = self._rag_load_causal_graph()
		if G is None:
			return []

		cfg = self._rag_get_config()
		disc = cfg.get('l0_graph_discovery', {}) if isinstance(cfg, dict) else {}
		hops = int(disc.get('hops', 4))
		max_paths_per_pair = int(disc.get('max_paths_per_pair', 20))
		semantic_top_k = int(disc.get('anchor_semantic_top_k', 3))
		causal_methods = {str(m).strip().lower() for m in disc.get('causal_methods', ['RCT', 'DID', 'IV', 'RDD'])}
		fallback_anchor_threshold = float(disc.get('fallback_anchor_threshold', 0.45))

		# ---- 锚定：概念 → 图节点 ----
		# ---- Phase 1: concepts anchor + path search ----
		anchors = self._rag_anchor_concepts(concepts, G, semantic_top_k, collection_name="concepts")
		anchor_set = set(anchors)
		scored: List[Tuple[float, List[str], List[Dict[str, Any]]]] = []
		fallback_used = False
		if len(anchor_set) >= 2:
			self.logger.info(f"[L0-graph] Phase1 concepts anchor {len(anchor_set)} nodes")
			scored = self._rag_search_chain_candidates(G, anchor_set, hops, max_paths_per_pair, causal_methods)
		else:
			self.logger.info(f"[L0-graph] Phase1 concepts anchor insufficient({len(anchor_set)})")

		# ---- Phase 2: fallback to causal_claims if < top_k ----
		if len(scored) < top_k:
			self.logger.info(f"[L0-graph] Phase1 {len(scored)} chains < {top_k}, fallback to causal_claims")
			anchors2 = self._rag_anchor_concepts(concepts, G, semantic_top_k, collection_name="causal_claims")
			fallback_anchor_set = {
				node for node, (_src, sim) in anchors2.items()
				if sim is not None and sim >= fallback_anchor_threshold
			}
			dropped = set(anchors2) - fallback_anchor_set
			if dropped:
				self.logger.info(
					f"[L0-graph] Phase2 过滤低置信度节点(<{fallback_anchor_threshold}): "
					f"{len(dropped)} 个剔除，保留 {len(fallback_anchor_set)} 个"
				)
			if len(fallback_anchor_set) >= 2:
				self.logger.info(f"[L0-graph] Phase2 causal_claims anchor {len(fallback_anchor_set)} nodes (独立搜索)")
				extra = self._rag_search_chain_candidates(
					G, fallback_anchor_set, hops, max_paths_per_pair, causal_methods
				)
				seen_sigs = set(tuple(s[1]) for s in scored)
				for s in extra:
					sig = tuple(s[1])
					if sig not in seen_sigs:
						seen_sigs.add(sig)
						scored.append(s)
				fallback_used = True
			else:
				self.logger.info(
					f"[L0-graph] Phase2 causal_claims 高置信度节点不足({len(fallback_anchor_set)}), skip"
				)

		if not scored:
			self.logger.info("[L0-graph] no valid chains found")
			return []
		scored.sort(key=lambda x: x[0], reverse=True)
		raw_scores_str = "; ".join(
			f"[score={s:.2f}] {' → '.join(self._rag_node_label(G, n) for n in p)}"
			for s, p, _ in scored[:10]
		)
		self.logger.info(f"[L0-graph] 排序后候选链 {len(scored)} 条，Top-10 得分: {raw_scores_str}")
		if len(scored) > 10:
			self.logger.debug(f"[L0-graph] 剩余 {len(scored) - 10} 条候选链待去重")

		selected = self._rag_dedup_subpaths(scored, top_k)
		self.logger.info(
			f"[L0-graph] 去重: {len(scored)} 候选 → {len(selected)} 最终输出 "
			f"(top_k={top_k}, 剔除 {len(scored) - len(selected)} 条子路径冗余链)"
		)

		# ---- 格式化 ----
		lines: List[str] = []
		for _score, path, hop_edges in selected:
			labels = [self._rag_node_label(G, n) for n in path]
			methods = [str(e.get('method') or '').strip() for e in hop_edges if e.get('method')]
			certs = [str(e.get('certainty') or '').strip().lower() for e in hop_edges if e.get('certainty')]
			method_str = '/'.join(dict.fromkeys([m for m in methods if m])) or '未知'
			cert_str = '高' if any(c == 'certain' for c in certs) else ('中' if certs else '未知')
			chain = ' → '.join(labels)
			line = f"- {chain} (证据: {method_str}, 确定性{cert_str})"
			lines.append(line)
		self.logger.info("[L0-graph] 最终选定的传导链:")
		for line in lines:
			self.logger.info(f"  {line}")
		if fallback_used:
			note = "部分传导链基于 causal_claims 边数据补充，可信度稍低"
			self.logger.info(f"[L0-graph] 提示: {note}")
		self.logger.info(f"[L0-graph] 发现 {len(lines)} 条候选传导链 (fallback={fallback_used})")
		return lines

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

	def _rag_query_causal_claims(self, query_text: str, top_k: int = 3, max_distance: float = 1.0) -> List[Tuple[str, str]]:
		query_text = (query_text or '').strip()
		if not query_text:
			return []
		try:
			chroma_client = self._get_chroma_client()
			collection = chroma_client.get_collection(name='causal_claims')
		except Exception as exc:
			self.logger.debug(f"RAG跳过：无法连接Chroma ({exc})")
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		embedding = self._rag_embed(client, query_text, dimensions=1024)
		if not embedding:
			return []
		try:
			results = collection.query(
				query_embeddings=[embedding],
				n_results=top_k,
				include=['documents', 'metadatas', 'distances'],
			)
		except Exception as exc:
			# 测试输出：便于定位哪类 query 触发 HNSW 错误
			print(f"[RAG-DEBUG] _rag_query_causal_claims 失败 query={query_text!r}: {exc}")
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

	def _ensure_absolute_simulator_imports(self, file_path: str) -> None:
		"""将 simulator 文件中的相对导入强制转换为绝对导入。

		新项目 simulator.py 位于 projects/<name>/ 下，无法使用相对导入；
		该兜底转换可防止 LLM 复用旧模板中的相对导入写法。
		"""
		if not file_path or not os.path.exists(file_path):
			return
		with open(file_path, 'r', encoding='utf-8') as f:
			content = f.read()
		new_content = content.replace(
			'from .simulator_imports import *', 'from src.simulation.simulator_imports import *'
		)
		new_content = new_content.replace(
			'from .base_simulator import BaseSimulator', 'from src.simulation.base_simulator import BaseSimulator'
		)
		if new_content != content:
			with open(file_path, 'w', encoding='utf-8') as f:
				f.write(new_content)
			self.logger.info(f"✓ 已转换相对导入为绝对导入: {file_path}")

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

	def _interfaces_dir(self) -> str:
		return os.path.join(self._rag_project_root, 'src', 'interfaces')

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
					# 只用方法名 + 左括号作为锚点，签名其余部分（参数、-> 返回注解、跨行）一律不参与匹配，
					# 避免 def f(...) -> None: 这类带返回注解的签名匹配失败。
					if file_type == "main":
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\(.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\n#\s*=====\s*以下代码块不可删除或修改\s*=====|\Z)"
					else:
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\(.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\Z)"
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
			# 策略：所有方法统一先删除所有旧定义，再统一追加到类/文件末尾，
			# 避免原实现中新增块在 for 循环内导致的三角重复问题。
			replaced_count = 0
			truly_new_count = 0
			for item_info in code_items:
				item_name = item_info.get('method_name') or item_info.get('function_name')
				item_code = item_info.get('method_code') or item_info.get('function_code')
				description = item_info.get('description', '')

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

				# 判断方法/函数是否已存在
				header_pattern = rf"^(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\("
				header_match = re.search(header_pattern, modified_content, re.MULTILINE)

				if header_match:
					# 已存在：删除所有同名定义，稍后统一追加
					if file_type == "main":
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\(.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\n#\s*=====\s*以下代码块不可删除或修改\s*=====|\Z)"
					else:
						pattern = rf"(\s*)(?:async\s+)?def\s+{re.escape(pure_name)}\s*\(.*?(?=\n\s*(?:async\s+)?def\s|\n\s*@|\nclass\s|\Z)"

					deleted_count = 0
					while True:
						match = re.search(pattern, modified_content, re.DOTALL)
						if not match:
							break
						start_pos = match.start()
						end_pos = match.end()
						while start_pos > 1 and modified_content[start_pos-1] == '\n' and modified_content[start_pos-2] == '\n':
							start_pos -= 1
						modified_content = modified_content[:start_pos] + modified_content[end_pos:]
						deleted_count += 1

					self.logger.info(f"✓ 已删除同名{'方法' if file_type == 'simulator' else '函数'}: {pure_name} (共 {deleted_count} 个)")
					replaced_count += 1
				else:
					if not allow_add_new:
						# 语法修复等场景不允许新增方法，避免 LLM 认错方法后污染文件
						self.logger.error(
							f"❌ {file_type} 修复模式下不允许新增{'方法' if file_type == 'simulator' else '函数'}: {pure_name}，跳过"
						)
						continue
					self.logger.info(f"→ 方法 {pure_name} 不存在，将作为新方法添加")
					truly_new_count += 1

				methods_to_add.append({
					'name': pure_name,
					'code': item_code,
					'description': description
				})

			# 添加新方法到类的末尾
			if methods_to_add:
				# 查找类定义的结束位置
				if file_type == "simulator":
					class_pattern = r'class\s+\w+.*?(?=class\s|\Z)'
					class_match = re.search(class_pattern, modified_content, re.DOTALL)

					if class_match:
						class_start = class_match.start()
						class_end = class_match.end()
						# 直接在类内容末尾追加（去掉尾部空白，保留一个换行），
						# 避免 last_method 正则把类级注释块误判为方法体的一部分。
						class_body = modified_content[class_start:class_end].rstrip() + '\n'

						indent = '    '  # 默认4个空格
						new_methods_code = ""
						for method_info in methods_to_add:
							new_methods_code += "\n"
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
							self.logger.info(f"✓ 已添加{'方法' if file_type == 'simulator' else '函数'}: {method_info['name']} - {method_info['description']}")

						class_body += new_methods_code
						modified_content = modified_content[:class_start] + class_body + modified_content[class_end:]
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
							self.logger.info(f"✓ 已添加{'方法' if file_type == 'simulator' else '函数'}: {func_info['name']} - {func_info['description']}")
						# 在新函数和入口标记之间添加空行
						new_functions_code += "\n\n"
						modified_content = modified_content[:insert_pos] + new_functions_code + modified_content[insert_pos:]
					else:
						# 如果没有入口标记，添加到文件末尾
						insert_pos = len(modified_content)
						new_functions_code = ""
						for func_info in methods_to_add:
							new_functions_code += "\n\n" + func_info['code'] + "\n"
							self.logger.info(f"✓ 已添加{'方法' if file_type == 'simulator' else '函数'}: {func_info['name']} - {func_info['description']}")

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
			deleted_count = len(delete_items) if delete_items else 0
			self.logger.info(f"✓ 已应用增量修改")
			if replaced_count > 0:
				self.logger.info(f"  - 替换{'方法' if file_type == 'simulator' else '函数'}: {replaced_count} 个")
			if truly_new_count > 0:
				self.logger.info(f"  - 新增{'方法' if file_type == 'simulator' else '函数'}: {truly_new_count} 个")
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

	def _rag_query_moderator_papers(self, cause: str, effect: str, top_k: int = 2, max_distance: float = 1.0) -> List[str]:
		"""检索可能包含调节/中介变量的论文。"""
		query = f"{cause} {effect} mediating moderating interaction".strip()
		if not query:
			return []
		try:
			chroma_client = self._get_chroma_client()
			collection = chroma_client.get_collection(name='papers')
		except Exception:
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		embedding = self._rag_embed(client, query, dimensions=1024)
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

			# 应用修改（语法修复场景允许新增方法/函数，便于补全被截断或缺失的方法）
			if self._apply_code_changes(file_path, response, file_type, allow_add_new=True):
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

	def _read_plugin_code_for_module(self, module_name: str, max_chars: int = 2200) -> str:
		"""读取 plugins/ 或 plugins/generated/ 下源码片段；优先与模块同名文件。"""
		plugins_root = os.path.join(self._rag_project_root, 'plugins')
		generated_root = os.path.join(plugins_root, 'generated')
		stems = self._candidate_interface_stems(module_name)
		for root in (plugins_root, generated_root):
			for stem in stems:
				plugin_dir = os.path.join(root, stem)
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

	def _rag_query_related_claims(self, cause: str, effect: str, max_per_side: int = 2) -> List[Tuple[str, str]]:
		"""检索包含相同cause或相同effect的其他因果声明。"""
		if not cause and not effect:
			return []
		try:
			chroma_client = self._get_chroma_client()
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
			except Exception as exc:
				print(f"[RAG-DEBUG] _rag_query_related_claims 失败 field={field} value={value!r}: {exc}")
				continue
		print(f"[RAG-DEBUG] _rag_query_related_claims cause={cause!r} effect={effect!r} -> {len(lines)} 条")
		return lines

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

	def _rag_embed(self, client, text, dimensions: Optional[int] = None):
		"""获取文本的 embedding 向量。

		项目数据现状：
		- ChromaDB collections（causal_claims / concepts / papers）均为 1024 维，
		  由 text-embedding-3-large 指定 dimensions=1024 构建。
		- JEL 嵌入表（jel_embeddings.json）为 3072 维，未截断。
		因此查询 Chroma 时传 dimensions=1024，JEL 门控时不传（保持 3072）。
		"""
		max_retries = 3
		for attempt in range(max_retries):
			try:
				kwargs = {'model': self._rag_embed_model, 'input': [text]}
				if dimensions is not None:
					kwargs['dimensions'] = dimensions
				resp = client.embeddings.create(**kwargs)
				return resp.data[0].embedding
			except Exception:
				if attempt == max_retries - 1:
					self.logger.warning("RAG embedding failed")
					return None
				time.sleep(2 ** attempt)
		return None

	# ============================================================
	#  新 RAG 漏斗检索：L1 JEL 门控 + L2 有向图扩展 + L3 层级排序贪心填充
	# ============================================================

	def _rag_get_config(self):
		"""读取 config/ai_system.yaml 的 rag 配置。"""
		if not hasattr(self, '_rag_cfg'):
			try:
				from src.utils.ai_system_config import get_rag
				self._rag_cfg = get_rag()
			except Exception as exc:
				self.logger.warning(f"RAG配置读取失败，使用空配置: {exc}")
				self._rag_cfg = {}
		return self._rag_cfg

	def _rag_resolve_path(self, rel_path: str) -> str:
		"""把相对路径解析为绝对路径（优先相对项目根目录）。"""
		if os.path.isabs(rel_path):
			return rel_path
		root = getattr(self, '_rag_project_root', None)
		if not root:
			root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		return os.path.join(root, rel_path)

	def _rag_load_jel_table(self) -> Optional[Dict[str, Any]]:
		"""懒加载 JEL 嵌入表。"""
		if not hasattr(self, '_rag_jel_table'):
			cfg = self._rag_get_config()
			path = self._rag_resolve_path(cfg.get('jel_table_path', 'experiment_dataset/jel_embeddings.json'))
			try:
				with open(path, 'r', encoding='utf-8') as f:
					self._rag_jel_table = json.load(f)
			except Exception as exc:
				self.logger.debug(f"JEL嵌入表加载失败，门控降级: {exc}")
				self._rag_jel_table = None
		return self._rag_jel_table

	def _rag_load_causal_graph(self) -> Optional[Any]:
		"""懒加载因果图 gpickle。"""
		if not hasattr(self, '_rag_causal_graph'):
			cfg = self._rag_get_config()
			path = self._rag_resolve_path(cfg.get('graph_path', 'experiment_dataset/causal_graph.gpickle'))
			try:
				with open(path, 'rb') as f:
					self._rag_causal_graph = pickle.load(f)
			except Exception as exc:
				self.logger.debug(f"因果图加载失败，L2降级: {exc}")
				self._rag_causal_graph = None
		return self._rag_causal_graph

	@staticmethod
	def _rag_cosine(a: List[float], b: List[float]) -> float:
		"""计算余弦相似度；无 numpy 时纯 Python 兜底。"""
		if not a or not b:
			return 0.0
		if np is not None:
			va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
			norm = np.linalg.norm(va) * np.linalg.norm(vb)
			return float(np.dot(va, vb) / norm) if norm else 0.0
		dot = sum(float(x) * float(y) for x, y in zip(a, b))
		norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
		norm_b = math.sqrt(sum(float(x) * float(x) for x in b))
		return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

	def _rag_gate_jel(self, cause_text: str, top_n: int = 2) -> List[str]:
		"""L1: 通过 JEL 嵌入表锁定 Top-N 个 JEL 领域码。"""
		cause_text = (cause_text or '').strip()
		if not cause_text or top_n <= 0:
			return []
		table = self._rag_load_jel_table()
		if not table:
			return []
		client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
		emb = self._rag_embed(client, cause_text)
		if not emb:
			return []
		scores = []
		for code, data in table.items():
			vec = data.get('embedding')
			if not vec:
				continue
			scores.append((self._rag_cosine(emb, vec), code))
		scores.sort(reverse=True)
		codes = [code for _, code in scores[:top_n]]
		if codes:
			self.logger.info(f"[RAG-L1] JEL门控命中: {codes} for cause={cause_text!r}")
			self.logger.info(f"[RAG-L1] Top scores: {[(code, round(s, 4)) for s, code in scores[:top_n+3]]}")
		return codes

	def _rag_normalize_token(self, text: str) -> str:
		"""与 gpickle 节点 key 一致的轻量归一化。"""
		return re.sub(r'\s+', ' ', (text or '').strip().lower())

	def _rag_locate_node(self, text: str, G: Optional[Any] = None) -> Optional[str]:
		"""把 cause/effect 文本映射到图节点 key。"""
		text = (text or '').strip()
		if not text:
			return None
		if G is None:
			G = self._rag_load_causal_graph()
		if G is None:
			return None
		norm = self._rag_normalize_token(text)
		if norm in G:
			return norm
		for node, data in G.nodes(data=True):
			if norm in [self._rag_normalize_token(x) for x in data.get('surface_forms') or []]:
				return node
			if norm == self._rag_normalize_token(data.get('label')):
				return node
		return None

	def _rag_diverse_sample(
		self,
		candidates: List[Tuple[str, Dict[str, Any], Any]],
		max_expand: int,
		per_node_cap: int,
	) -> List[Tuple[str, Dict[str, Any], Any]]:
		"""按中间节点分组做多样性采样，避免热门变量导致图召回退化为重复抽样。

		candidates: [(paper_edge_id, edge_data, role), ...]
		"""
		if not candidates:
			return []
		groups = defaultdict(list)
		for eid, data, role in candidates:
			mid = data.get('graph_mid_node') or role
			groups[mid].append((eid, data, role))
		result = []
		idx = 0
		while len(result) < max_expand:
			added = 0
			for grp in groups.values():
				if idx < len(grp):
					result.append(grp[idx])
					added += 1
					if len(result) >= max_expand:
						break
			if added == 0:
				break
			idx += 1
		return result[:max_expand]

	def _rag_funnel_retrieve(
		self,
		cause: str,
		effect: str,
		query: str,
		jel_codes: List[str],
	) -> List[Dict[str, Any]]:
		"""L1 语义召回 + L2 有向图扩展，返回统一候选池（每条 dict 含完整 metadata）。"""
		cfg = self._rag_get_config()
		ret_cfg = cfg.get('retrieval', {})
		graph_cfg = cfg.get('l2_graph', {})
		max_distance = ret_cfg.get('max_distance', 1.0)
		top_k = ret_cfg.get('top_k_semantic', 5)
		G = self._rag_load_causal_graph()

		pool: List[Dict[str, Any]] = []
		seen_eids: set = set()

		self.logger.info(
			f"[RAG-Request] cause={cause!r} effect={effect!r} query={query!r} "
			f"jel_codes={jel_codes} top_k={top_k} max_distance={max_distance} "
			f"graph_loaded={G is not None}"
		)

		# ---------------- L1 语义召回 ----------------
		# jel_codes 现在是一级字母（如 'I'）。库中存的是 'I24' 等细码，无法直接用 Chroma $in 精确匹配，
		# 因此若启用门控，先语义召回再按首字母过滤；若为细码则保留原 where 逻辑。
		coarse_jel = bool(jel_codes) and all(len(str(c)) == 1 for c in jel_codes)
		try:
			chroma_client = self._get_chroma_client()
			collection = chroma_client.get_collection(name='causal_claims')
			client = OpenAI(api_key=self._rag_api_key, base_url=self._rag_base_url)
			embedding = self._rag_embed(client, (query or '').strip(), dimensions=1024)
			where = None
			if jel_codes and not coarse_jel:
				where = {
					'$or': [
						{'jel_cause': {'$in': jel_codes}},
						{'jel_effect': {'$in': jel_codes}},
					]
				}
			if embedding:
				q_kwargs = {
					'query_embeddings': [embedding],
					'n_results': top_k,
					'include': ['documents', 'metadatas', 'distances'],
				}
				if where is not None:
					q_kwargs['where'] = where
				results = collection.query(**q_kwargs)
				docs = results.get('documents', [[]])[0]
				metas = results.get('metadatas', [[]])[0]
				dists = results.get('distances', [[]])[0]
				for doc, meta, dist in zip(docs, metas, dists):
					if not doc or dist > max_distance:
						continue
					if coarse_jel:
						cause_jel = str(meta.get('jel_cause') or '').strip().upper()
						effect_jel = str(meta.get('jel_effect') or '').strip().upper()
						cause_letter = next((ch for ch in cause_jel if ch.isalpha()), '')
						effect_letter = next((ch for ch in effect_jel if ch.isalpha()), '')
						if cause_letter not in jel_codes and effect_letter not in jel_codes:
							continue
					eid = (meta or {}).get('paper_edge_id')
					if eid in seen_eids:
						continue
					seen_eids.add(eid)
					pool.append({
						'eid': eid,
						'doc': doc,
						'meta': meta,
						'distance': dist,
						'role': 'semantic',
					})
		except Exception as exc:
			self.logger.debug(f"L1 语义召回失败: {exc}")

		self.logger.info(
			f"[RAG-L1] 语义召回完成: {len([p for p in pool if p.get('role') == 'semantic'])} 条，"
			f"eids={[p.get('eid') for p in pool if p.get('role') == 'semantic']}"
		)

		# ---------------- L2 有向图扩展 ----------------
		if G is not None and nx is not None:
			try:
				nc = self._rag_locate_node(cause, G)
				ne = self._rag_locate_node(effect, G)
				l2_candidates: List[Tuple[str, Dict[str, Any], str]] = []

				if nc and ne:
					succ_nc = set(G.successors(nc))
					pred_ne = set(G.predecessors(ne))
					pred_nc = set(G.predecessors(nc))
					succ_ne = set(G.successors(ne))

					# 中介机制：A -> M -> B
					for mid in succ_nc & pred_ne:
						for _, _, key, data in G.out_edges(nc, keys=True, data=True):
							if key in seen_eids:
								continue
							if G.has_edge(mid, ne):
								d2 = dict(data)
								d2['graph_mid_node'] = mid
								l2_candidates.append((key, d2, 'mediator'))
					# 混杂因子：C -> A, C -> B
					if graph_cfg.get('include_confounders', True):
						for cnode in pred_nc & pred_ne:
							for _, _, key, data in G.in_edges(nc, keys=True, data=True):
								if key in seen_eids:
									continue
								if G.has_edge(cnode, ne):
									d2 = dict(data)
									d2['graph_mid_node'] = cnode
									l2_candidates.append((key, d2, 'confounder'))
					# 碰撞节点：A -> K, B -> K（识别后丢弃）
					_colliders = succ_nc & succ_ne
					if _colliders:
						self.logger.debug(f"L2 丢弃碰撞节点: {_colliders}")

				# 兜底：1-hop 下游机制（闭合路径为空时仍给通路）
				if nc and not l2_candidates:
					for _, v, key, data in G.out_edges(nc, keys=True, data=True):
						if key in seen_eids:
							continue
						d2 = dict(data)
						d2['graph_mid_node'] = v
						l2_candidates.append((key, d2, 'mediator_1hop'))

				if l2_candidates:
					l2_sample = self._rag_diverse_sample(
						l2_candidates,
						graph_cfg.get('max_expand', 8),
						graph_cfg.get('per_node_cap', 1),
					)
					batch_ids = [eid for eid, _, _ in l2_sample if eid not in seen_eids]
					if batch_ids:
						try:
							chroma_client = self._get_chroma_client()
							collection = chroma_client.get_collection(name='causal_claims')
							res = collection.get(ids=batch_ids, include=['documents', 'metadatas'])
							doc_map = {eid: doc for eid, doc in zip(res.get('ids', []), res.get('documents', []))}
							meta_map = {eid: meta for eid, meta in zip(res.get('ids', []), res.get('metadatas', []))}
							for eid, data, role in l2_sample:
								if eid in seen_eids:
									continue
								doc = doc_map.get(eid)
								meta = meta_map.get(eid)
								if doc is None and meta is None:
									continue
								seen_eids.add(eid)
								merged_meta = dict(meta or {})
								for k in ['rel_type', 'method', 'certainty', 'sig_level', 'exogenous_var', 'paper_edge_id']:
									if k in data:
										merged_meta.setdefault(k, data[k])
								pool.append({
									'eid': eid,
									'doc': doc or '',
									'meta': merged_meta,
									'distance': None,
									'role': role,
								})
						except Exception as exc:
							self.logger.debug(f"L2 批量查向量库失败: {exc}")
			except Exception as exc:
				self.logger.debug(f"L2 图扩展失败: {exc}")

		self.logger.info(
			f"[RAG-L2] 图扩展完成: 总池 {len(pool)} 条，"
			f"角色分布={ {role: sum(1 for p in pool if p.get('role') == role) for role in sorted({p.get('role') for p in pool})} },"
			f" eids={[p.get('eid') for p in pool]}"
		)

		return pool

	def _rag_format_evidence_line(self, item: Dict[str, Any]) -> str:
		"""把候选证据格式化成供 LLM 消费的文本行，保留 role 标签。"""
		meta = item.get('meta') or {}
		doc = (item.get('doc') or '')
		snippet = doc[:500].strip() + ('...' if len(doc) > 500 else '')
		role = item.get('role', 'semantic')
		method = meta.get('method', '')
		rel_type = meta.get('rel_type', '')
		certainty = meta.get('certainty', '')
		sig = meta.get('sig_level', '')
		exog = meta.get('exogenous_var', '')
		distance = item.get('distance')
		parts = [f"[{role}]"]
		if method or rel_type:
			parts.append(f"method={method}, rel={rel_type}")
		if certainty or sig:
			parts.append(f"certainty={certainty}, sig={sig}")
		if exog:
			parts.append(f"exogenous={exog[:60]}")
		if distance is not None:
			parts.append(f"distance={distance:.3f}")
		return f"- {' | '.join(parts)} | {snippet}"

	def _rag_rank_and_fill(
		self,
		pool: List[Dict[str, Any]],
		weights: Dict[str, Any],
		max_chars: int,
	) -> Tuple[str, int]:
		"""层级阻断式排序 + 按条目边界贪心填充。"""
		hard_methods = {str(m).strip().lower() for m in weights.get('hard_drop_methods', [])}
		hard_rels = {str(r).strip().lower() for r in weights.get('hard_drop_rel_types', [])}
		hard_tentative = bool(weights.get('hard_drop_tentative', True))
		causal_methods = {'rct', 'did', 'iv', 'rdd', 'twfe', 'event study'}

		def _tier(item):
			meta = item.get('meta') or {}
			method = str(meta.get('method') or '').strip().lower()
			rel = str(meta.get('rel_type') or '').strip().lower()
			certainty = str(meta.get('certainty') or '').strip().lower()
			if method in hard_methods or rel in hard_rels or (hard_tentative and certainty == 'tentative'):
				return -1
			is_causal_method = method in causal_methods
			is_direct_rel = 'direct' in rel or rel in ('mediation', 'indirect effect')
			if is_causal_method and is_direct_rel:
				return weights.get('tier_causal_direct', 3)
			if str(meta.get('exogenous_var') or '').strip():
				return weights.get('tier_exogenous', 2)
			sig = str(meta.get('sig_level') or '').strip().lower()
			if 'p<0.01' in sig and certainty == 'certain':
				return weights.get('tier_significant', 1)
			return weights.get('tier_other', 0)

		def _bonus(item):
			meta = item.get('meta') or {}
			b = 0
			if str(meta.get('exogenous_var') or '').strip():
				b += weights.get('bonus_exogenous', 1)
			if 'p<0.01' in str(meta.get('sig_level') or '').lower() and str(meta.get('certainty') or '').lower() == 'certain':
				b += weights.get('bonus_significant', 1)
			return b

		scored = []
		hard_dropped = 0
		for item in pool:
			t = _tier(item)
			if t < 0:
				hard_dropped += 1
				continue
			d = item.get('distance')
			scored.append((t, _bonus(item), 0.0 if d is None else d, item))
		scored.sort(key=lambda x: (x[0], x[1], -x[2]), reverse=True)

		self.logger.info(
			f"[RAG-L3] 候选池 {len(pool)} 条，硬门槛排除 {hard_dropped} 条，"
			f"进入排序 {len(scored)} 条；tier分布="
			f"{ {f'tier_{t}': sum(1 for s in scored if s[0] == t) for t in sorted({s[0] for s in scored})} }"
		)

		seen: set = set()
		lines: List[str] = []
		current_len = 0
		for _, _, _, item in scored:
			eid = item.get('eid')
			if eid in seen:
				continue
			line = self._rag_format_evidence_line(item)
			line_len = len(line) + 1
			if current_len + line_len > max_chars and lines:
				break
			seen.add(eid)
			lines.append(line)
			current_len += line_len
			if current_len >= max_chars:
				break
		rag_context = '\n'.join(lines)
		self.logger.info(
			f"[RAG-L3] 贪心填充完成: 选中 {len(lines)} 条，总字符 {len(rag_context)}，"
			f"eids={ [item.get('eid') for _, _, _, item in scored if item.get('eid') in seen] }"
		)
		return rag_context, len(lines)

	def _rag_cache_key(self, cause: str, effect: str) -> str:
		"""基于 cause/effect 文本生成缓存 key。"""
		return f"{self._rag_normalize_token(cause)}||{self._rag_normalize_token(effect)}"

	def _rag_cache_load(self):
		"""懒加载进程内 + 文件缓存。"""
		if hasattr(self, '_rag_cache'):
			return self._rag_cache
		self._rag_cache = {}
		cfg = self._rag_get_config().get('cache', {})
		if not cfg.get('enabled', True):
			return self._rag_cache
		path = self._rag_resolve_path(cfg.get('file_path', 'experiment_dataset/.rag_cache.json'))
		try:
			with open(path, 'r', encoding='utf-8') as f:
				data = json.load(f)
			if isinstance(data, dict):
				self._rag_cache = data
		except Exception:
			pass
		return self._rag_cache

	def _rag_cache_get(self, cause: str, effect: str) -> Optional[Tuple[str, Dict[str, Any]]]:
		cache = self._rag_cache_load()
		key = self._rag_cache_key(cause, effect)
		val = cache.get(key)
		if val is None:
			return None
		if isinstance(val, (list, tuple)) and len(val) == 2:
			return val[0], val[1]
		return None

	def _rag_cache_set(self, cause: str, effect: str, value: Tuple[str, Dict[str, Any]]):
		cfg = self._rag_get_config().get('cache', {})
		if not cfg.get('enabled', True):
			return
		cache = self._rag_cache_load()
		key = self._rag_cache_key(cause, effect)
		cache[key] = value
		path = self._rag_resolve_path(cfg.get('file_path', 'experiment_dataset/.rag_cache.json'))
		try:
			with open(path, 'w', encoding='utf-8') as f:
				json.dump(cache, f, ensure_ascii=False)
		except Exception as exc:
			self.logger.debug(f"RAG 缓存落盘失败: {exc}")

	# ============================================================
	#  /新 RAG 漏斗检索
	# ============================================================

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

