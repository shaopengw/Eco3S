"""审计 Agent（AuditorAgent）。

作为 CodeFixer 的子 agent，在改动写入文件之前对其逐处复核：

- 第一关·匹配快检（硬性检查）：用 AST 抓出改动里引用的方法/属性，去真实代码里查是否存在，
  挡住"编造方法名"这类幻觉。
- 第二关·语义审查（调用 LLM）：判断改动是否真能解决诊断问题、是否会数值爆炸、是否符合设计。

复核结论写进共享的审计日志（audit_ledger），供 CodeFixer 重新生成时参考。

设计要点：
- 第一关宁可漏报不可误杀——任何不确定的校验一律放行，只精准打击"调用了本类里不存在的方法"。
"""

import ast
import difflib
import hashlib
import json
import os
import re
import textwrap
from typing import Any, Dict, List, Optional

import yaml

from src.utils.custom_logger import CustomLogger
from src.utils.ai_system_config import get_agent_model
from .base_agent import BaseAgent
from .code_change_mixin import CodeChangeMixin
from .audit_ledger import AuditLedger


class AuditorAgent(CodeChangeMixin, BaseAgent):
    """代码修改复核专家。审计 CodeFixer 提出的改动，拦截幻觉与无效修改。"""

    def __init__(
        self,
        agent_id: str,
        project_dir: str,
        config_dir: str,
        simulator_path: str,
        simulation_name: str,
        ledger: AuditLedger,
        semantic_review: bool = True,
        attr_check: bool = True,
        session=None,
    ):
        _api, _model = get_agent_model('auditor')
        super().__init__(
            agent_id,
            group_type='auditor',
            window_size=2,
            model_api_name=_api,
            model_type_name=_model,
        )

        prompts_path = os.path.join(os.path.dirname(__file__), 'auditor_prompts.yaml')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)
        self.system_message = self.prompts.get('system_message')

        self.project_dir = project_dir
        self.config_dir = config_dir
        self.simulator_path = simulator_path
        self.simulation_name = simulation_name
        self.ledger = ledger
        self.semantic_review = bool(semantic_review)
        self.attr_check = bool(attr_check)
        self.session = session
        self.logger = CustomLogger('auditor').logger

        # CodeChangeMixin 的接口/插件读取需要这些路径
        self._rag_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._rag_api_key = os.environ.get('OPENAI_API_KEY')
        self._rag_base_url = os.environ.get('OPENAI_API_BASE_URL')
        self._rag_db_path = os.environ.get('CAUSAL_CLAIMS_DB_PATH', os.path.join(self._rag_project_root, 'experiment_dataset', 'chroma_db'))
        self._rag_embed_model = os.environ.get('CAUSAL_CLAIMS_EMBED_MODEL', 'text-embedding-3-large')

    # ---------- 工具：读文件 / 搜索项目 ----------

    def read_file(self, file_path: str) -> str:
        """读取项目内的文本文件内容（多编码兜底）。"""
        if not file_path:
            return "[错误：file_path 为空]"

        docs_dir = os.path.join(self._rag_project_root, 'docs')
        allowed_roots = {
            os.path.abspath(self._rag_project_root),
            os.path.abspath(self.project_dir),
            os.path.abspath(self.config_dir),
            os.path.abspath(docs_dir),
        }

        candidates = []
        if os.path.isabs(file_path):
            candidates.append(os.path.abspath(file_path))
        else:
            candidates.extend([
                os.path.abspath(os.path.join(self.project_dir, file_path)),
                os.path.abspath(os.path.join(self.config_dir, file_path)),
                os.path.abspath(os.path.join(self._rag_project_root, file_path)),
                os.path.abspath(os.path.join(docs_dir, file_path)),
            ])

        for path in candidates:
            if not os.path.isfile(path):
                continue
            if not any(path.startswith(root + os.sep) or path == root for root in allowed_roots):
                return f"[错误：无权读取该路径: {file_path}]"
            for enc in ('utf-8', 'gbk', 'gb2312', 'utf-8-sig'):
                try:
                    with open(path, 'r', encoding=enc) as f:
                        content = f.read()
                    max_len = 15000
                    if len(content) > max_len:
                        content = content[:max_len] + f"\n\n[文件过长，已截断；原始长度 {len(content)} 字符]"
                    return content
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    return f"[读取文件失败 {file_path}: {e}]"
        return f"[未找到文件: {file_path}]"

    def search_project(self, pattern: str, glob: str = "**/*.py", path: str = None) -> str:
        """在项目代码中按正则搜索内容，返回匹配文件路径与片段。"""
        import fnmatch
        from pathlib import PurePosixPath

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

    async def _execute_tool(self, tool_call: dict) -> str:
        """执行一次工具调用并返回文本结果。"""
        name = tool_call.get('name')
        args = tool_call.get('args', {})
        if name == 'read_file':
            return self.read_file(args.get('file_path', ''))
        if name == 'search_project':
            return self.search_project(
                args.get('pattern', ''),
                args.get('glob', '**/*.py'),
                args.get('path')
            )
        return f"[未知工具: {name}]"

    async def _chat(self, messages: list) -> Optional[str]:
        """直接调用模型后端（不经过 BaseAgent 的 memory 拼接）。"""
        attempts = 0
        while attempts < self.max_retry_attempts:
            try:
                extra_kwargs = getattr(self, '_extra_kwargs', None)
                if extra_kwargs:
                    from openai import OpenAI
                    client = OpenAI(base_url=self._api_url, api_key=self._api_key)
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=self.model_type,
                        messages=messages,
                        **extra_kwargs
                    )
                else:
                    response = await asyncio.to_thread(self.model_backend.run, messages)
                content = response.choices[0].message.content
                if content is not None:
                    return content
                self.logger.warning(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次返回空，准备重试")
            except Exception as e:
                self.logger.error(f"{self.__class__.__name__} 工具调用第 {attempts + 1} 次出错：{e}")
            attempts += 1
            if attempts < self.max_retry_attempts:
                await asyncio.sleep(self.retry_delay)
        self.logger.error(f"{self.__class__.__name__} 工具调用在 {self.max_retry_attempts} 次尝试后失败")
        return None

    async def _generate_with_tools(self, prompt: str) -> Optional[str]:
        """带 read_file / search_project 工具调用的 LLM 对话循环。"""
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
                return response

            round_no += 1
            self.logger.info(f"🔧 审计工具调用 #{round_no}: {tool_call['name']}({tool_call['args']})")
            result = await self._execute_tool(tool_call)
            if len(result) > 12000:
                result = result[:12000] + "\n\n[工具结果过长，已截断]"

            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": f"<tool_result name=\"{tool_call['name']}\">\n{result}\n</tool_result>"
            })

    # ==================== 对外主入口 ====================

    async def audit_batch(
        self,
        proposed: List[Dict[str, Any]],
        round_no: int,
        diagnosis_context: str = "",
        design_doc: str = "",
    ) -> Dict[str, Any]:
        """逐处复核 CodeFixer 提出的改动清单。

        Args:
            proposed: 改动清单，每项形如
                {'file_name','file_type'('simulator'|'config'),'file_path','changes'(已解析 dict)}
            round_no: 第几轮审计
            diagnosis_context: 本轮要解决的问题（来自诊断/评估报告）
            design_doc: 设计文档内容

        Returns:
            {
              'verdict': 'APPROVE' | 'REVISE',
              'approved': [{'file_path','file_type','methods'|'modifications'}],
              'rejected': [{'location','reason','suggestion','signature','stage'}],
              'feedback': str,
            }
        """
        symbol_table = self._build_symbol_table(proposed)
        approved: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for item in proposed:
            file_type = item.get('file_type')
            if file_type == 'simulator':
                self._audit_simulator_item(
                    item, symbol_table, round_no, diagnosis_context, design_doc,
                    approved, rejected,
                )
            else:
                await self._audit_config_item(
                    item, round_no, diagnosis_context, design_doc,
                    approved, rejected,
                )

        # 语义审查（第二关）：对过了第一关的 simulator/config 改动整体复核
        if self.semantic_review:
            approved, rejected = await self._run_semantic_review(
                approved, rejected, round_no, diagnosis_context, design_doc,
            )

        verdict = 'APPROVE' if not rejected else 'REVISE'
        feedback = self.ledger.get_recent_feedback()

        return {
            'verdict': verdict,
            'approved': approved,
            'rejected': rejected,
            'feedback': feedback,
        }

    # ==================== 第一关：匹配快检 ====================

    def _audit_simulator_item(self, item, symbol_table, round_no, diagnosis_context,
                              design_doc, approved, rejected):
        """对一处 simulator 改动，逐个方法做符号快检。"""
        file_name = item.get('file_name', 'simulator.py')
        methods = (item.get('changes') or {}).get('methods', [])
        good_methods = []

        for m in methods:
            method_name = self._pure_name(m.get('method_name', ''))
            findings = self._stage1_check_method(m, symbol_table)
            if self.attr_check:
                findings = findings + self._stage1b_attr_findings(m, symbol_table)
            if not findings:
                good_methods.append(m)
                continue

            # 命中疑似幻觉 → 驳回该方法
            primary = findings[0]
            location = f"{file_name} 的 {method_name} 方法"
            reason = "；".join(f["原因"] for f in findings)
            suggestion = primary.get("建议", "—")
            signature = primary.get("签名")
            stage = primary.get("关", "第一关·匹配快检")
            self.ledger.append_record(
                round_no=round_no,
                location=location,
                summary=m.get('description', ''),
                verdict="驳回",
                stage=stage,
                reason=reason,
                suggestion=suggestion,
                signature=signature,
            )
            rejected.append({
                'location': location,
                'reason': reason,
                'suggestion': suggestion,
                'signature': signature,
                'stage': stage,
            })

        if good_methods:
            approved.append({
                'file_path': item.get('file_path'),
                'file_type': 'simulator',
                'file_name': file_name,
                'methods': good_methods,
                'diagnosis_context': diagnosis_context,
            })

    def _stage1_check_method(self, method: Dict[str, Any], symbol_table: Dict[str, set]) -> List[Dict]:
        """对单个方法代码做符号快检，返回疑似幻觉清单（空=通过）。"""
        code = method.get('method_code', '') or ''
        method_name = self._pure_name(method.get('method_name', ''))
        findings: List[Dict] = []

        try:
            tree = ast.parse(textwrap.dedent(code))
        except SyntaxError:
            # 代码本身解析不了，交给第二关/编译检查处理，这里不武断驳回
            return findings

        known_methods = symbol_table.get('methods', set())
        objects = symbol_table.get('objects', {})
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            called = node.func.attr
            target = node.func.value

            # 情形一：self.<method>(...) —— 调用本类不存在的方法
            if isinstance(target, ast.Name) and target.id == 'self':
                if called in known_methods:
                    continue
                if called in self._COMMON_METHODS or called.startswith('__'):
                    continue
                nearest = self._nearest(called, known_methods)
                hint = f"，最接近的是 {nearest}()" if nearest else ""
                findings.append({
                    "原因": f"本类没有 self.{called}() 方法{hint}",
                    "建议": f"改用真实方法{(' ' + nearest + '()') if nearest else '，或先在类中定义该方法'}",
                    "签名": f"simulator.py::{method_name}::self.{called}",
                    "关": "第一关·匹配快检",
                })
                continue

            # 情形二：self.<obj>.<method>(...) —— 在已知类型的框架对象上调用不存在的方法
            if (isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == 'self'):
                attr = target.attr
                info = objects.get(attr)
                if not info:
                    # 未能确定 self.<attr> 的类型，放行不误杀
                    continue
                if called in info['methods'] or called.startswith('__'):
                    continue
                # 非 strict 对象（接口模块）保留通用方法白名单，减少误杀；
                # strict 对象（InfluenceManager 等固定类型）不吃白名单，精准抓幻觉。
                if not info['strict'] and called in self._COMMON_METHODS:
                    continue
                nearest = self._nearest(called, info['methods'])
                hint = f"，最接近的是 {nearest}()" if nearest else ""
                findings.append({
                    "原因": f"self.{attr} 是 {info['label']}，没有 .{called}() 方法{hint}",
                    "建议": f"改用其真实方法{(' ' + nearest + '()') if nearest else '，请查该对象接口确认方法名'}",
                    "签名": f"simulator.py::{method_name}::self.{attr}.{called}",
                    "关": "第一关·匹配快检",
                })

        return findings

    # 常见的内建/容器方法名，调用它们不算幻觉
    _COMMON_METHODS = {
        'append', 'get', 'items', 'keys', 'values', 'update', 'pop', 'setdefault',
        'add', 'remove', 'extend', 'insert', 'sort', 'copy', 'format', 'join',
        'split', 'strip', 'lower', 'upper', 'replace', 'count', 'index',
    }

    def _build_symbol_table(self, proposed: List[Dict[str, Any]]) -> Dict[str, set]:
        """构建"真实存在的符号表"：当前 simulator 方法 + 基类方法 + 本次将新增的方法。

        宁可多收不可少收——表越全，第一关误杀越少。
        另外构建"已知框架对象的方法表"（objects），用于检查 self.<obj>.<method>() 跨对象调用。
        """
        methods: set = set()

        # 1. 当前 simulator.py 里定义的方法
        methods |= self._class_methods_of_file(self.simulator_path)

        # 2. BaseSimulator 基类方法（simulator 继承它）
        base_path = os.path.join(self._rag_project_root, 'src', 'simulation', 'base_simulator.py')
        methods |= self._class_methods_of_file(base_path)

        # 3. 本次改动将新增/替换的方法（避免方法间互相调用被误判）
        for item in proposed:
            if item.get('file_type') != 'simulator':
                continue
            for m in (item.get('changes') or {}).get('methods', []):
                name = self._pure_name(m.get('method_name', ''))
                if name:
                    methods.add(name)

        return {
            'methods': methods,
            'objects': self._build_object_method_tables(proposed),
            'assigned_attrs': self._build_assigned_attrs(proposed),
        }

    def _class_methods_of_file(self, file_path: str) -> set:
        """用 AST 解析文件，收集其中所有类里定义的方法名。"""
        names: set = set()
        if not file_path or not os.path.exists(file_path):
            return names
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
        except Exception:
            return names
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
        return names

    # ---------- 第一关·属性快检：未初始化属性 ----------

    def _build_assigned_attrs(self, proposed: List[Dict[str, Any]]) -> set:
        """收集"改完之后全类已赋值的属性名"集合：基类 + 现有 simulator 整文件 + 本批新增方法体。

        宁可多收不可少收——整文件（含将被替换的旧方法）一并计入，宁可漏报也不误杀：
        某属性只要在任何地方被赋过值，就当它已初始化。

        例外：如果本批改动包含 __init__ 方法，说明旧的 __init__ 将被整体替换，
        此时不能再把旧 __init__ 里的赋值当成"改完后仍然已初始化"的依据，否则新 __init__
        遗漏的属性会被漏报。基类 __init__ 不受影响。
        """
        assigned: set = set()
        base_path = os.path.join(self._rag_project_root, 'src', 'simulation', 'base_simulator.py')

        # 是否本次会替换 __init__
        has_new_init = any(
            self._pure_name(m.get('method_name', '')) == '__init__'
            for item in proposed
            if item.get('file_type') == 'simulator'
            for m in (item.get('changes') or {}).get('methods', [])
        )

        for path in (base_path, self.simulator_path):
            if path and os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                    # 只有当前 simulator 文件且本批替换 __init__ 时才排除旧 __init__
                    exclude = '__init__' if (has_new_init and path == self.simulator_path) else None
                    assigned |= self._collect_assigned_attrs(tree, exclude_method_name=exclude)
                except Exception:
                    pass
        for item in proposed:
            if item.get('file_type') != 'simulator':
                continue
            for m in (item.get('changes') or {}).get('methods', []):
                code = m.get('method_code') or ''
                if not code:
                    continue
                try:
                    assigned |= self._collect_assigned_attrs(ast.parse(textwrap.dedent(code)))
                except SyntaxError:
                    pass
        return assigned

    def _collect_assigned_attrs(self, tree: ast.AST, exclude_method_name: Optional[str] = None) -> set:
        """从 AST 收集对 self 的属性赋值名：self.x=、self.x:T、self.x+=、for self.x in、setattr(self,'x',...)；
        以及类体里直接定义的类变量（NAME=... / NAME:T），它们也能通过 self.NAME 访问。

        Args:
            exclude_method_name: 若指定，跳过该类方法体内部的赋值收集（用于替换 __init__ 时
                排除旧 __init__ 的赋值）。类体级变量仍正常收集。
        """
        out: set = set()
        excluded_bodies: list = []
        if exclude_method_name:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for stmt in node.body:
                        if (isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                                and stmt.name == exclude_method_name):
                            excluded_bodies.append(stmt)

        for node in ast.walk(tree):
            # 跳过被排除方法体内部的所有节点
            if any(node is not b and self._is_descendant(node, b) for b in excluded_bodies):
                continue
            if isinstance(node, ast.ClassDef):
                # 类级变量（class 体里直接的 NAME = ... / NAME: T）
                for stmt in node.body:
                    if any(stmt is b for b in excluded_bodies):
                        continue
                    if isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                out.add(t.id)
                            elif isinstance(t, (ast.Tuple, ast.List)):
                                for e in t.elts:
                                    if isinstance(e, ast.Name):
                                        out.add(e.id)
                    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        out.add(stmt.target.id)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    out |= self._attr_targets(t)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                out |= self._attr_targets(node.target)
            elif isinstance(node, ast.For):
                out |= self._attr_targets(node.target)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == 'setattr' and len(node.args) >= 2
                  and isinstance(node.args[0], ast.Name) and node.args[0].id == 'self'
                  and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                out.add(node.args[1].value)
        return out

    @staticmethod
    def _is_descendant(node: ast.AST, ancestor: ast.AST) -> bool:
        """判断 node 是否位于 ancestor 的子树中（node 自身除外）。"""
        for child in ast.iter_child_nodes(ancestor):
            if child is node or AuditorAgent._is_descendant(node, child):
                return True
        return False

    def _attr_targets(self, target: ast.AST) -> set:
        """从赋值目标里取出 self.<attr> 名（支持元组/列表解包嵌套）。"""
        out: set = set()
        elts = target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]
        for n in elts:
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id == 'self'):
                out.add(n.attr)
            elif isinstance(n, (ast.Tuple, ast.List)):
                out |= self._attr_targets(n)
        return out

    def _stage1b_attr_findings(self, method: Dict[str, Any], symbol_table: Dict[str, Any]) -> List[Dict]:
        """对单个改动方法体做"属性未初始化"快检，返回疑似清单（空=通过）。

        只挑【确会崩】的危险读取：
        - 字面量 self.x（读取语境），且 x 在全类任何地方都没被赋值过；
        - 无默认值的 getattr(self, "x")。
        带默认值的 getattr(self,"x",默认)、hasattr(self,"x") 视为安全；getattr(self, 动态变量)
        无法静态判断，一律放行（盲区，宁可漏报不误杀）。
        """
        code = method.get('method_code', '') or ''
        method_name = self._pure_name(method.get('method_name', ''))
        findings: List[Dict] = []
        try:
            tree = ast.parse(textwrap.dedent(code))
        except SyntaxError:
            return findings

        assigned = symbol_table.get('assigned_attrs', set())
        known_methods = symbol_table.get('methods', set())

        # 本方法内被 hasattr / getattr(默认) 守卫的属性，视为安全
        guarded: set = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ('hasattr', 'getattr') and len(node.args) >= 2
                    and isinstance(node.args[0], ast.Name) and node.args[0].id == 'self'
                    and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                if node.func.id == 'hasattr' or len(node.args) >= 3:
                    guarded.add(node.args[1].value)

        seen: set = set()
        for node in ast.walk(tree):
            attr = None
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == 'self' and isinstance(node.ctx, ast.Load)):
                attr = node.attr
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == 'getattr' and len(node.args) == 2
                  and isinstance(node.args[0], ast.Name) and node.args[0].id == 'self'
                  and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                attr = node.args[1].value
            if not attr or attr in seen:
                continue
            if attr in assigned or attr in known_methods or attr in guarded:
                continue
            if attr.startswith('__'):
                continue
            seen.add(attr)
            findings.append({
                "原因": f"读取了 self.{attr}，但全类（含基类与本批改动）都没有初始化它，运行到此会 AttributeError",
                "建议": f"在 __init__ 中初始化 self.{attr} = <合理初值>，或确认应读取的真实属性名",
                "签名": f"simulator.py::{method_name}::self.{attr}",
                "关": "第一关·属性快检",
            })
        return findings

    # ---------- 跨对象调用：已知框架对象的方法表 ----------

    # 框架注入、类型固定的对象 → (源码相对路径, 类名)。这些对象不是容器，
    # 调用其上不存在的方法即为幻觉，按 strict 处理（不吃 _COMMON_METHODS 白名单）。
    _FRAMEWORK_OBJECTS = {
        'influence_manager': ('src/influences/influence_manager.py', 'InfluenceManager'),
    }

    def _build_object_method_tables(self, proposed: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """构建 self.<attr> -> {'methods':set,'label':str,'strict':bool}，仅收录能确定类型的对象。

        三类来源：
        1) 框架注入对象（如 influence_manager → InfluenceManager），strict。
        2) require_module(reg, "x") 注入的插件模块 → 接口文件 i<x>.py 的方法，非 strict
           （接口可能未列全容器式辅助方法，保留白名单以减少误杀）。
        3) self.x = ClassName(...) 直接实例化、且能在工程类索引里找到的类，strict。
        未能确定类型的对象不收录——第一关对它一律放行，绝不误杀。
        """
        objects: Dict[str, Dict] = {}

        # 汇总要扫描的源码：基类 + 当前 simulator + 本次新增方法体
        sources: List[str] = []
        for path in (
            os.path.join(self._rag_project_root, 'src', 'simulation', 'base_simulator.py'),
            self.simulator_path,
        ):
            if path and os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        sources.append(f.read())
                except Exception:
                    pass
        for item in proposed:
            if item.get('file_type') != 'simulator':
                continue
            for m in (item.get('changes') or {}).get('methods', []):
                code = m.get('method_code') or ''
                if code:
                    sources.append(textwrap.dedent(code))
        blob = "\n".join(sources)

        # 来源1：框架对象
        for attr, (rel_path, class_name) in self._FRAMEWORK_OBJECTS.items():
            methods = self._class_methods_of_file(os.path.join(self._rag_project_root, rel_path))
            if methods:
                objects[attr] = {'methods': methods, 'label': class_name, 'strict': True}

        # 来源2：require_module 注入的插件模块
        for attr, modname in re.findall(
            r'self\.(\w+)\s*=\s*require_module\([^,]+,\s*[\'"](\w+)[\'"]\)', blob
        ):
            iface = os.path.join(self._interfaces_dir(), f'i{modname}.py')
            methods = self._class_methods_of_file(iface)
            if methods:
                objects.setdefault(attr, {'methods': methods, 'label': f'{modname} 模块', 'strict': False})

        # 来源3：self.x = ClassName(...) 直接实例化
        class_index = self._collect_class_index()
        for attr, class_name in re.findall(r'self\.(\w+)\s*=\s*([A-Z][A-Za-z0-9_]*)\s*\(', blob):
            if attr in objects:
                continue
            methods = class_index.get(class_name)
            if methods:
                objects[attr] = {'methods': methods, 'label': class_name, 'strict': True}

        return objects

    def _collect_class_index(self) -> Dict[str, set]:
        """扫描 src/ 与项目目录下的 .py，建立 类名 -> 方法名集合（含可解析的基类方法）。结果缓存。"""
        if getattr(self, '_class_index_cache', None) is not None:
            return self._class_index_cache

        raw: Dict[str, Dict] = {}  # class -> {'methods':set,'bases':[str]}
        roots = [os.path.join(self._rag_project_root, 'src'), self.project_dir]
        for root in roots:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    if not fn.endswith('.py'):
                        continue
                    try:
                        with open(os.path.join(dirpath, fn), 'r', encoding='utf-8') as f:
                            tree = ast.parse(f.read())
                    except Exception:
                        continue
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.ClassDef):
                            continue
                        ms = {n.name for n in node.body
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                        # 同名类以"方法更多者"为准，避免被空壳覆盖
                        if node.name not in raw or len(ms) > len(raw[node.name]['methods']):
                            raw[node.name] = {'methods': ms, 'bases': bases}

        def resolve(name: str, seen: set) -> set:
            if name in seen or name not in raw:
                return set()
            seen.add(name)
            out = set(raw[name]['methods'])
            for b in raw[name]['bases']:
                out |= resolve(b, seen)
            return out

        self._class_index_cache = {name: resolve(name, set()) for name in raw}
        return self._class_index_cache

    # ==================== 第二关：LLM 语义审查 ====================

    async def _run_semantic_review(self, approved, rejected, round_no,
                                   diagnosis_context, design_doc):
        """对过了第一关的改动做**整批**语义审查，驳回的从 approved 移除。

        关键：同一轮的多处改动是协同修复同一批问题的整体（如 simulator.py 真修逻辑 +
        simulation_config.yaml 加诊断日志）。必须把它们作为一个整体送审、按条目编号定位
        问题，而不是逐文件孤立评判——否则配套的诊断/日志类改动会被误判为"答非所问"。
        """
        if not approved:
            return approved, rejected

        reject_map = await self._stage2_batch_review(approved, diagnosis_context, design_doc)

        still_approved = []
        for idx, item in enumerate(approved):
            location = self._item_location(item)
            summary = self._item_summary(item)
            if idx in reject_map:
                info = reject_map[idx]
                reason = info.get('reason', '')
                suggestion = info.get('suggestion', '—')
                signature = hashlib.md5(
                    f"{location}|{reason}".encode('utf-8')
                ).hexdigest()
                self.ledger.append_record(
                    round_no=round_no, location=location, summary=summary,
                    verdict="驳回", stage="第二关·语义审查",
                    reason=reason, suggestion=suggestion,
                    signature=signature,
                )
                rejected.append({
                    'location': location, 'reason': reason,
                    'suggestion': suggestion,
                    'signature': signature, 'stage': '第二关·语义审查',
                })
            else:
                still_approved.append(item)
                self.ledger.append_record(
                    round_no=round_no, location=location, summary=summary,
                    verdict="通过", stage="—", reason="两关均通过，已应用",
                )
        return still_approved, rejected

    async def _stage2_batch_review(self, approved, diagnosis_context, design_doc) -> Dict[int, Dict]:
        """把整批改动一次性送 LLM 审查，返回 {被驳回条目下标: {reason, suggestion}}。

        失败/无响应/解析不出 → 返回空（全部放行），保持"宁可放行不臆测"。
        """
        try:
            blocks = []
            iface_modules: set = set()
            file_paths_seen = set()
            files_to_update_blocks = []
            for idx, item in enumerate(approved):
                blocks.append(
                    f"[{idx}] 位置：{self._item_location(item)}（类型：{item.get('file_type')}）\n"
                    f"改动内容：\n{self._item_change_text(item)}"
                )
                change_text = self._item_change_text(item)
                iface_modules |= set(re.findall(r'self\.([a-z_]+)\.', change_text))

                file_path = item.get('file_path')
                if file_path and file_path not in file_paths_seen:
                    file_paths_seen.add(file_path)
                    rel_path = os.path.relpath(file_path, self._rag_project_root)
                    current_code = self.read_file(file_path)
                    files_to_update_blocks.append(
                        f"===== {rel_path}（当前代码）=====\n{current_code[:8000]}"
                    )

            changes_block = "\n\n".join(blocks)
            files_to_update_code = "\n\n".join(files_to_update_blocks) if files_to_update_blocks else "（无）"
            interface_docs = (
                self._read_interface_docs_for_modules(list(iface_modules), max_chars_per_file=1200)
                if iface_modules else "（无相关接口）"
            )

            prompt = self.prompts['batch_semantic_review_prompt'].format(
                diagnosis_context=diagnosis_context or "（未提供）",
                files_to_update_code=files_to_update_code,
                changes_block=changes_block,
                interface_docs=interface_docs,
            )
            response = await self._generate_with_tools(prompt)
            if not response:
                self.logger.warning("整批语义审查 LLM 无响应，降级放行")
                return {}

            json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
            raw = json_match.group(1) if json_match else response
            parsed = json.loads(raw)
            reject_map: Dict[int, Dict] = {}
            for r in parsed.get('rejections', []) or []:
                try:
                    idx = int(r.get('index'))
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(approved):
                    reject_map[idx] = {
                        'reason': r.get('reason', ''),
                        'suggestion': r.get('suggestion', '—'),
                    }
            return reject_map
        except Exception as e:
            self.logger.warning(f"整批语义审查异常，降级放行: {e}")
            return {}

    # ==================== 工具方法 ====================

    @staticmethod
    def _pure_name(name: str) -> str:
        if not name:
            return ""
        if 'def ' in name:
            m = re.search(r'def\s+(\w+)', name)
            if m:
                return m.group(1)
        return name.strip()

    @staticmethod
    def _nearest(name: str, candidates: set) -> Optional[str]:
        matches = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.7)
        return matches[0] if matches else None

    @staticmethod
    def _item_location(item) -> str:
        if item.get('file_type') == 'simulator':
            names = [AuditorAgent._pure_name(m.get('method_name', '')) for m in item.get('methods', [])]
            return f"{item.get('file_name', 'simulator.py')} 的 {', '.join(names)} 方法"
        return f"{item.get('file_name', '配置文件')}"

    @staticmethod
    def _item_summary(item) -> str:
        if item.get('file_type') == 'simulator':
            return "；".join(m.get('description', '') for m in item.get('methods', []) if m.get('description'))
        return "；".join(f"{mod.get('parameter')}={mod.get('value')}" for mod in item.get('modifications', []))

    @staticmethod
    def _item_change_text(item) -> str:
        if item.get('file_type') == 'simulator':
            return "\n\n".join(m.get('method_code', '') for m in item.get('methods', []))
        return json.dumps(item.get('modifications', []), ensure_ascii=False, indent=2)

    async def _audit_config_item(self, item, round_no, diagnosis_context, design_doc,
                                 approved, rejected):
        """配置改动第一关默认放行（幻觉风险低），交由第二关语义审查判断是否合理。"""
        modifications = (item.get('changes') or {}).get('modifications', [])
        if modifications:
            approved.append({
                'file_path': item.get('file_path'),
                'file_type': 'config',
                'file_name': item.get('file_name'),
                'modifications': modifications,
                'diagnosis_context': diagnosis_context,
            })

