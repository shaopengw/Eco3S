"""叛军画像生成器

支持两种模式：
1. 旧版硬编码模式（profile_config=None）：使用模块级硬编码配置向后兼容。
2. 配置驱动模式（profile_config=dict）：使用 agent_profile 中的 attributes 定义驱动生成。
"""

import json
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from src.generator.resident_generate import generate_resident_profile
except ImportError:
    generate_resident_profile = None


# =============================================================================
# 向后兼容的硬编码默认配置
# =============================================================================

default_roles = ['军事', '行政', '情报', '后勤']
default_role_ratio = [0.25, 0.25, 0.25, 0.25]

personality_words = []
filepath = 'src/generator/personality_words.txt'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        personality_words = [line.strip() for line in f if line.strip()]

if not personality_words:
    print("警告: personality_words.txt 为空或不存在，性格生成将使用占位符。")


# =============================================================================
# 旧版辅助函数（向后兼容）
# =============================================================================

def get_random_role():
    return random.choices(default_roles, default_role_ratio)[0]

def get_random_personality():
    if len(personality_words) < 2:
        return "凶狠、狡猾"  # 占位符
    return "、".join(random.sample(personality_words, 2))


# =============================================================================
# 旧版生成函数
# =============================================================================

def generate_rebel_profile_legacy(is_leader=False):
    """旧版：使用模块级硬编码配置生成单个叛军画像。"""
    rank = '叛军头子' if is_leader else '普通叛军'
    for attempt in range(3):
        try:
            personality = get_random_personality()
            rebel_data = {"rank": rank, "personality": personality}
            if not is_leader:
                rebel_data["role"] = get_random_role()
            return rebel_data
        except Exception as e:
            print(f"叛军信息生成失败: {e}. 重试中... ({attempt + 1}/3)")
    return None


def generate_rebel_data_legacy(n):
    """旧版：批量生成叛军数据（硬编码）。"""
    rebel_data = []
    start_time = datetime.now()
    max_workers = min(os.cpu_count() * 2 or 4, n, 32)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        futures.append(executor.submit(generate_rebel_profile_legacy, is_leader=True))
        for _ in range(n - 1):
            futures.append(executor.submit(generate_rebel_profile_legacy, is_leader=False))
        for i, future in enumerate(as_completed(futures)):
            profile = future.result()
            if profile:
                rebel_data.append(profile)
                elapsed_time = datetime.now() - start_time
                print(f"生成 {i+1}/{n} 叛军信息成功. 用时: {elapsed_time}")
    return rebel_data


# =============================================================================
# 新版配置驱动生成
# =============================================================================

def generate_rebel_data(n, profile_config=None):
    """生成叛军数据。

    Args:
        n: 生成数量
        profile_config: agent_profile 中的属性定义。支持两种结构：
            1. ranks 结构（推荐）：{ranks: [{rank, count, attributes}, ...], extra}
            2. 单 attributes 结构（向后兼容）：{attributes, constraints, extra}
               自动注入 rank（第一个为叛军头子，其余为普通叛军）。
            为 None 时使用旧版硬编码逻辑。

    Returns:
        list[dict]: 叛军画像数据列表
    """
    if profile_config is None:
        return generate_rebel_data_legacy(n)

    if generate_resident_profile is None:
        raise ImportError("需要 resident_generate.generate_resident_profile 的支持")

    profile_config = dict(profile_config)

    # ---- 优先：ranks 结构 ----
    ranks_cfg = profile_config.get("ranks")
    if ranks_cfg:
        return _generate_by_ranks(ranks_cfg, profile_config.get("extra", {}))

    # ---- 回退：单 attributes 结构（自动注入 rank） ----
    # 确保至少有一名头子（leader）
    rebel_data = []

    first_attrs = _inject_rank(profile_config.get("attributes", {}), "叛军头子")
    profile_cfg_first = {**profile_config, "attributes": first_attrs}
    profile = generate_resident_profile(profile_cfg_first)
    rebel_data.append(profile)

    # 剩余为普通叛军
    for _ in range(n - 1):
        rest_attrs = _inject_rank(profile_config.get("attributes", {}), "普通叛军")
        profile_cfg_rest = {**profile_config, "attributes": rest_attrs}
        profile = generate_resident_profile(profile_cfg_rest)
        rebel_data.append(profile)

    print(f"已生成 {len(rebel_data)} 个叛军数据（配置驱动）")
    return rebel_data


def _generate_by_ranks(ranks_cfg, extra=None):
    """按 ranks 结构生成画像列表。

    每个 rank 项格式：{rank: <名称>, count: <数量>, attributes: [...], constraints: [...]}
    """
    extra = extra or {}
    data = []
    for rank_item in ranks_cfg:
        if not isinstance(rank_item, dict):
            continue
        rank_value = rank_item.get("rank")
        count = int(rank_item.get("count", 1))
        attrs = _inject_rank(rank_item.get("attributes", {}), rank_value)
        profile_cfg = {
            "attributes": attrs,
            "constraints": rank_item.get("constraints", []),
            "extra": {**extra, **rank_item.get("extra", {})},
        }
        for _ in range(count):
            data.append(generate_resident_profile(profile_cfg))
    print(f"已生成 {len(data)} 个叛军数据（ranks 配置驱动）")
    return data


def _inject_rank(attributes, rank_value):
    """在 attributes 中固定 rank 值，或添加 rank 属性。

    支持 list 格式（[{name: ..., type: ...}]）和 dict 格式（{attr_name: rule}）。
    """
    if isinstance(attributes, list):
        result = []
        found = False
        for item in attributes:
            if isinstance(item, dict) and item.get("name") == "rank":
                result.append({
                    **item,
                    "runtime_key": item.get("runtime_key", "rank"),
                    "type": "choice",
                    "choices": [rank_value],
                    "weights": [1.0],
                })
                found = True
            else:
                result.append(dict(item))
        if not found:
            result.insert(0, {"name": "rank", "runtime_key": "rank", "type": "choice", "choices": [rank_value], "weights": [1.0]})
        return result
    elif isinstance(attributes, dict):
        result = dict(attributes)
        if "rank" not in result:
            new_result = {"rank": {"type": "choice", "choices": [rank_value], "weights": [1.0]}}
            new_result.update(result)
            return new_result
        if isinstance(result["rank"], dict):
            result["rank"] = {**result["rank"], "type": "choice", "choices": [rank_value], "weights": [1.0]}
        return result
    return attributes


# =============================================================================
# 文件 I/O
# =============================================================================

def save_rebel_data(rebel_data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(rebel_data, f, ensure_ascii=False, indent=2)


# =============================================================================
# 主入口（兼容旧版独立运行）
# =============================================================================

if __name__ == "__main__":
    N = 5
    rebel_data = generate_rebel_data(N)
    output_path = 'experiment_dataset/rebellion_data/rebels_data.json'
    save_rebel_data(rebel_data, output_path)
    print(f"生成 {N} 叛军信息成功. 已保存到 {output_path}")
