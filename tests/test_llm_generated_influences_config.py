# 用于测试RAG检索相关逻辑
"""单步测试：直接调用 CodeArchitectAgent.generate_influences_config_file，
验证 influences.yaml 完整生成链路（含 LLM + RAG）。

不额外写测试逻辑，只做最小断言和结果打印。
"""

from __future__ import annotations

import asyncio
import os
import sys

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.agents.code_architect import CodeArchitectAgent

# 测试项目名
SIM_DIR = os.path.join(PROJECT_ROOT, "projects", "cross_border_production_simulation", "config")
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "config", "template")
OUT_DIR = os.path.join(PROJECT_ROOT, "tests", "_generated")


def main():
    print("=" * 60)
    print("测试：generate_influences_config_file（含 LLM + RAG）")
    print("=" * 60)

    # 本测试需要调用外部 LLM 与 OpenAI Embedding，缺少密钥时直接跳过
    missing = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if missing:
        print(f"⚠️  缺少环境变量 {missing}，跳过完整链路测试。")
        print("   在真实密钥环境中运行即可验证 generate_influences_config_file。")
        return 0

    # 读取已有配置
    with open(os.path.join(SIM_DIR, "description.md"), "r", encoding="utf-8") as f:
        description_md = f.read()
    with open(os.path.join(SIM_DIR, "modules_config.yaml"), "r", encoding="utf-8") as f:
        modules_config_yaml = f.read()

    # 直接复用已有 agent 构造方式
    agent = CodeArchitectAgent(
        agent_id="test_code_architect",
        simulator_output_dir=os.path.join(PROJECT_ROOT, "src", "simulation"),
        main_output_dir=os.path.join(PROJECT_ROOT, "entrypoints"),
        docs_dir=str(SIM_DIR),
        config_dir=str(OUT_DIR),
        config_template_dir=str(TEMPLATE_DIR),
        simulation_name="cross_border_production_sim",
        simulation_type="decision",
        session=None,
        auto_mode=False,
    )
    # 跳过交互确认
    agent._check_file_exists_and_ask = lambda *_args, **_kwargs: True  # type: ignore[assignment]

    out_path = asyncio.run(
        agent.generate_influences_config_file(
            description_md,
            modules_config_yaml,
            previous_configs=None,
        )
    )

    print(f"\n生成路径: {out_path}")
    assert out_path and os.path.exists(out_path), "influences.yaml 未生成"

    with open(out_path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    assert isinstance(doc, dict), "YAML 根节点不是字典"
    assert "execution_order" in doc, "缺少 execution_order"
    assert "influences" in doc, "缺少 influences"
    assert isinstance(doc["influences"], list), "influences 不是列表"

    print(f"✓ influences.yaml 正常，共 {len(doc['influences'])} 条 influence")
    for i, inf in enumerate(doc["influences"][:5], 1):
        print(f"  {i}. {inf.get('source', '?')} -> {inf.get('target', '?')} : {inf.get('name', 'unnamed')}")
    if len(doc["influences"]) > 5:
        print(f"  ... 共 {len(doc['influences'])} 条")

    # 检查 influence_pairs.json
    pairs_path = os.path.join(OUT_DIR, "influence_pairs.json")
    if os.path.exists(pairs_path):
        import json
        with open(pairs_path, "r", encoding="utf-8") as f:
            pairs = json.load(f)
        print(f"✓ influence_pairs.json 正常，共 {len(pairs)} 条 pair")
    else:
        print("⚠️ influence_pairs.json 未生成")

    print("\n测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
