"""AI 系统元配置加载器（全局、唯一真源）。

读取 <root>/config/ai_system.yaml，控制构建层多智能体系统自身行为：
代码审计三关、各构建 Agent 用什么模型、各阶段重试轮数。

与 src/agents/shared_imports.py 的 global_config 不同：那是"运行期模拟实验配置"
（residents/government 跑什么），本文件是"系统怎么构建/修复代码"的元配置。
纯全局：不读取任何项目内的同名配置。
"""
import os
import copy
import yaml

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, 'config', 'ai_system.yaml')

DEFAULTS = {
    'code_audit': {
        'enabled': True, 'threshold': 3, 'max_rounds': 2,
        'semantic_review': True, 'shadow_mode': False, 'attr_check': True,
    },
    'agents': {
        'code_fixer':       {'api': 'CLAUDE',   'model': 'claude-sonnet-4-5-20250929'},
        'auditor':          {'api': 'CLAUDE',   'model': 'claude-sonnet-4-5-20250929'},
        'code_architect':   {'api': 'CLAUDE',   'model': 'claude-sonnet-4-5-20250929'},
        'sim_architect':    {'api': 'DEEPSEEK', 'model': 'deepseek-v4-flash'},
        'research_analyst': {'api': 'DEEPSEEK', 'model': 'deepseek-v4-flash'},
    },
    'retries': {
        'regeneration': 3, 'influence_preflight': 3, 'smoke_test': 5,
        'full_run': 10, 'runtime_fix': 3, 'audit_internal': 5,
    },
    'workflow': {
        'max_optimization_iterations': 0,
    },
    'rag': {
        'funnel_enabled': True,
        'embed_model': 'text-embedding-3-large',
        'db_path': 'experiment_dataset/chroma_db',
        'graph_path': 'experiment_dataset/causal_graph.gpickle',
        'jel_table_path': 'experiment_dataset/jel_embeddings.json',
        'l0_graph_discovery': {
            'enabled': True,
            'max_concepts': 5,          # LLM 抽取概念上限
            'hops': 4,                  # all_simple_paths cutoff（2-4 跳）
            'max_paths_per_pair': 20,   # 每对 anchor 最大路径数，防组合爆炸
            'top_k_chains': 5,          # 最终输出链条数
            'fallback_min_chains': 3,   # 少于此数才回退论文库
            'anchor_semantic_top_k': 3, # 语义锚定每概念召回 claim 数
            'causal_methods': ['RCT', 'DID', 'IV', 'RDD'],  # 打分加成的因果识别方法
        },
        'l1_jel': {'enabled': True, 'top_n': 2},
        'l2_graph': {'hops': 2, 'max_expand': 8, 'per_node_cap': 1, 'include_confounders': True},
        'retrieval': {'top_k_semantic': 5, 'max_distance': 1.0},
        'budget': {'max_chars': 2500},
        'priority_weights': {
            'tier_causal_direct': 3,
            'tier_exogenous': 2,
            'tier_significant': 1,
            'tier_other': 0,
            'bonus_exogenous': 1,
            'bonus_significant': 1,
            'hard_drop_methods': ['Simulations'],
            'hard_drop_rel_types': ['null result', 'spurious', 'collider'],
            'hard_drop_tentative': True,
        },
        'cache': {'enabled': True, 'file_path': 'experiment_dataset/.rag_cache.json'},
    },
}

_cache = None


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_ai_system_config():
    """读取并缓存全局 AI 系统配置（与 DEFAULTS 深合并）。缺文件即返回 DEFAULTS。"""
    global _cache
    if _cache is not None:
        return _cache
    user_cfg = {}
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                user_cfg = yaml.safe_load(f) or {}
    except Exception:
        user_cfg = {}
    _cache = _deep_merge(DEFAULTS, user_cfg)
    return _cache


def get_code_audit():
    return dict(load_ai_system_config()['code_audit'])


def get_agent_model(role):
    """返回 (api_name, model_type)；未知角色回退随机（None, None）。"""
    a = load_ai_system_config()['agents'].get(role)
    if not a:
        return None, None
    return a.get('api'), a.get('model')


def get_retries():
    return dict(load_ai_system_config()['retries'])


def get_workflow():
    return dict(load_ai_system_config()['workflow'])


def get_rag():
    """返回 RAG 检索配置（分层漏斗 + 层级排序 + 缓存）。"""
    return copy.deepcopy(load_ai_system_config()['rag'])

