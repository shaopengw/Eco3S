"""政府官员画像生成器

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

default_functions = ['漕运', '行政', '军事', '经济管理']
default_function_ratio = [0.25, 0.25, 0.25, 0.25]

default_factions = ['河运派', '海运派', '中立派']
default_faction_ratio = [0.3, 0.3, 0.4]

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

def get_random_function():
    return random.choices(default_functions, default_function_ratio)[0]

def get_random_faction():
    return random.choices(default_factions, default_faction_ratio)[0]

def get_random_personality():
    if len(personality_words) < 2:
        return "谨慎、果断"  # 占位符
    return "、".join(random.sample(personality_words, 2))


# =============================================================================
# 旧版生成函数
# =============================================================================

def generate_official_profile(is_high_rank=False):
    """旧版：使用模块级硬编码配置生成单个官员画像。"""
    rank = '高级官员' if is_high_rank else '普通官员'
    for attempt in range(3):
        try:
            personality = get_random_personality()
            official_data = {"rank": rank, "personality": personality}
            if not is_high_rank:
                official_data["function"] = get_random_function()
                official_data["faction"] = get_random_faction()
            return official_data
        except Exception as e:
            print(f"官员信息生成失败: {e}. 重试中... ({attempt + 1}/3)")
    return None


def generate_official_data_legacy(n):
    """旧版：批量生成官员数据（硬编码）。"""
    official_data = []
    start_time = datetime.now()
    max_workers = min(os.cpu_count() * 2 or 4, n, 32)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        futures.append(executor.submit(generate_official_profile, is_high_rank=True))
        for _ in range(n - 1):
            futures.append(executor.submit(generate_official_profile, is_high_rank=False))
        for i, future in enumerate(as_completed(futures)):
            profile = future.result()
            if profile:
                official_data.append(profile)
                elapsed_time = datetime.now() - start_time
                print(f"生成 {i+1}/{n} 官员信息成功. 用时: {elapsed_time}")
    return official_data


# =============================================================================
# 新版配置驱动生成
# =============================================================================

def generate_official_data(n, profile_config=None):
    """生成官员数据。

    Args:
        n: 生成数量
        profile_config: agent_profile 中的属性定义。支持两种结构：
            1. ranks 结构（推荐）：{ranks: [{rank, count, attributes}, ...], extra}
               按 rank 分组，各 rank 拥有独立的属性集和数量。
            2. 单 attributes 结构（向后兼容）：{attributes, constraints, extra}
               自动注入 rank（第一个为高级官员，其余为普通官员）。
            为 None 时使用旧版硬编码逻辑。

    Returns:
        list[dict]: 官员画像数据列表
    """
    if profile_config is None:
        return generate_official_data_legacy(n)

    if generate_resident_profile is None:
        raise ImportError("需要 resident_generate.generate_resident_profile 的支持")

    profile_config = dict(profile_config)  # 不污染原始配置

    # ---- 优先：ranks 结构 ----
    ranks_cfg = profile_config.get("ranks")
    if ranks_cfg:
        return _generate_by_ranks(ranks_cfg, profile_config.get("extra", {}))

    # ---- 回退：单 attributes 结构（自动注入 rank） ----
    # 确保至少有一名高级官员（leader）
    official_data = []

    # 注入 rank 固定值：第一个为高级官员
    first_attrs = _inject_rank(profile_config.get("attributes", {}), "高级官员")
    profile_cfg_first = {**profile_config, "attributes": first_attrs}
    profile = generate_resident_profile(profile_cfg_first)
    official_data.append(profile)

    # 剩余为普通官员
    for _ in range(n - 1):
        rest_attrs = _inject_rank(profile_config.get("attributes", {}), "普通官员")
        profile_cfg_rest = {**profile_config, "attributes": rest_attrs}
        profile = generate_resident_profile(profile_cfg_rest)
        official_data.append(profile)

    print(f"已生成 {len(official_data)} 个官员数据（配置驱动）")
    return official_data


def _generate_by_ranks(ranks_cfg, extra=None):
    """按 ranks 结构生成画像列表。

    每个 rank 项格式：{rank: <名称>, count: <数量>, attributes: [...], constraints: [...]}
    为每个 rank 固定注入其 rank 名称，并按 count 调用 generate_resident_profile。
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
    print(f"已生成 {len(data)} 个官员数据（ranks 配置驱动）")
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

def save_official_data(official_data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(official_data, f, ensure_ascii=False, indent=2)


# =============================================================================
# 主入口（兼容旧版独立运行）
# =============================================================================

if __name__ == "__main__":
    N = 5
    official_data = generate_official_data(N)
    output_path = 'experiment_dataset/government_data/official_data.json'
    save_official_data(official_data, output_path)
    print(f"生成 {N} 官员信息成功. 已保存到 {output_path}")
