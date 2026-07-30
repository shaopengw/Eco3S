import json
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os

# =============================================================================
# 旧版硬编码默认配置（当 simulation_config.yaml 中未提供 resident_profile 时使用）
# =============================================================================

# 性别比例
gender_ratio = [0.351, 0.636]  # 女：男
genders = ['女性', '男性']

# 寿命比例（剩余寿命）,仅考虑劳动力群体
lifespan_ratio = [0.10, 0.30, 0.25, 0.25, 0.10]
lifespan_groups = ['1-9', '10-19', '20-39', '40-54', '55+']

# 居住地
residence_ratio = [0.7, 0.3]  # 70% 在沿河，30% 在非沿河地区
residences = ['沿河', '非沿河']

# 满意度（假设为1-100分）
satisfaction_ratio = [0.10, 0.20, 0.25, 0.20, 0.15, 0.10]
satisfaction_groups = ['1-20', '21-40', '41-60', '61-80', '81-90', '91-100']

# 健康指数
health_index_ratio = [0.1, 0.2, 0.4, 0.2, 0.1]  # 假设健康指数 1, 2, 3, 4, 5
health_indices = [1, 2, 3, 4, 5]

# 收入范围（以清代的普通民众收入假设为基础）
income_range = [0, 5, 10, 20, 50]  # 假设收入等级：0, 5, 10, 20, 50（两白银）

# 性格词语
personality_words = []

filepath='src/generator/resident_personality_words.txt'
if not os.path.exists(filepath):
    print(f"警告: 性格词语文件 '{filepath}' 不存在。请确保文件存在且每行包含一个词语。")
else:
    with open(filepath, 'r', encoding='utf-8') as f:
        personality_words = [line.strip() for line in f if line.strip()]
    if not personality_words:
        print(f"警告: 性格词语文件 '{filepath}' 为空或不包含有效词语。")


# =============================================================================
# 旧版辅助生成函数（向后兼容）
# =============================================================================

def get_random_gender():
    return random.choices(genders, gender_ratio)[0]

def get_random_lifespan():
    group = random.choices(lifespan_groups, lifespan_ratio)[0]
    if group == '1-9':
        return random.randint(1, 9)
    elif group == '10-19':
        return random.randint(10, 19)
    elif group == '20-39':
        return random.randint(20, 39)
    elif group == '40-54':
        return random.randint(40, 54)
    else:  # 对应 '55+' 组
        return random.randint(55, 80)

def get_random_residence():
    return random.choices(residences, residence_ratio)[0]

def get_random_satisfaction():
    group = random.choices(satisfaction_groups, satisfaction_ratio)[0]
    if group == '1-20':
        return random.randint(1, 20)
    elif group == '21-40':
        return random.randint(21, 40)
    elif group == '41-60':
        return random.randint(41, 60)
    elif group == '61-80':
        return random.randint(61, 80)
    elif group == '81-90':
        return random.randint(81, 90)
    else:
        return random.randint(91, 100)

def get_random_health_index():
    return random.choices(health_indices, health_index_ratio)[0]

def get_random_income():
    return random.choice(income_range)

def get_random_personality():
    if len(personality_words) < 2:
        print("警告: 性格词语不足两个，无法随机选择。请检查 personality_words.txt 文件。")
        return ""
    selected_traits = random.sample(personality_words, 2)
    return "、".join(selected_traits)


def _legacy_generate_resident_profile():
    """旧版硬编码居民画像生成（向后兼容）。"""
    failure_count = 0
    while True:
        try:
            gender = get_random_gender()
            lifespan = get_random_lifespan()
            residence = get_random_residence()
            satisfaction = get_random_satisfaction()
            health_index = get_random_health_index()
            income = get_random_income()
            personality = get_random_personality()

            profile = {
                "gender": gender,
                "lifespan": lifespan,
                "residence": residence,
                "satisfaction": satisfaction,
                "health_index": health_index,
                "income": income,
                "personality": personality,
            }
            return profile

        except Exception as e:
            failure_count += 1
            print(f"Profile generation failed: {e}. Retrying...")
            if failure_count >= 3:
                print("Failed to generate profile after 3 attempts. Terminating...")
                break


# =============================================================================
# 新版配置驱动生成引擎
# =============================================================================

def generate_resident_profile(profile_config=None):
    """
    生成单个居民画像。

    Args:
        profile_config: 配置字典，格式参考 simulation_config.yaml 中的 resident_profile 段。
                        若为 None，使用旧版硬编码逻辑。

    Returns:
        dict: 居民画像数据
    """
    if profile_config is None:
        return _legacy_generate_resident_profile()

    attributes_cfg = profile_config.get("attributes", {})

    # 兼容两种 attributes 格式：
    #   - 旧版 dict: {attr_name: rule, ...}
    #   - 新版 list: [{name: attr_name, ...}, ...]  (来自 agent_profile.yaml)
    if isinstance(attributes_cfg, list):
        # 用 item["name"] 读取（不 pop），并复制 dict 避免污染原始配置
        attributes_cfg = {item["name"]: dict(item) for item in attributes_cfg}

    profile = {}
    aliases = {}

    # 第一轮：按配置生成各属性
    for attr_name, rule in attributes_cfg.items():
        runtime_key = str(rule.get("runtime_key") or attr_name)
        value = _generate_attribute(attr_name, rule)
        profile[runtime_key] = value
        if runtime_key != attr_name:
            profile[attr_name] = value
            aliases[attr_name] = runtime_key

    if aliases:
        profile["_profile_aliases"] = aliases

    # 第二轮：应用约束修正
    for constraint in profile_config.get("constraints", []):
        if _eval_condition(constraint.get("condition", ""), profile):
            for attr_name, adj in constraint.get("adjustments", {}).items():
                runtime_key = aliases.get(attr_name, attr_name)
                if runtime_key in profile:
                    new_value = _apply_adjustment(profile[runtime_key], adj)
                    profile[runtime_key] = new_value
                    for display_name, canonical in aliases.items():
                        if canonical == runtime_key:
                            profile[display_name] = new_value

    # 第三轮：注入 extra 静态属性
    profile.update(profile_config.get("extra", {}))
    return profile


def _generate_attribute(attr_name: str, rule: dict):
    """根据规则生成单个属性值。"""
    attr_type = rule.get("type", "choice")
    if attr_type == "choice":
        return _generate_choice(rule)
    elif attr_type == "range":
        return _generate_range(rule)
    elif attr_type == "composite":
        return _generate_composite(rule)
    else:
        raise ValueError(f"[resident_generate] 未知属性类型 '{attr_type}' for '{attr_name}'")


def _generate_choice(rule: dict):
    """离散选择型属性。"""
    choices = rule["choices"]
    weights = rule.get("weights")
    if weights is not None and len(weights) != len(choices):
        raise ValueError("[resident_generate] choices 与 weights 长度不匹配")
    return random.choices(choices, weights=weights, k=1)[0]


def _generate_range(rule: dict):
    """连续/离散数值型属性，支持多种分布。"""
    distribution = rule.get("distribution", "uniform")
    dtype = rule.get("dtype", "int")

    if distribution == "normal":
        mean = rule.get("mean", 0)
        std = rule.get("std", 1)
        val = random.gauss(mean, std)
    elif distribution == "uniform":
        min_val = rule.get("min", 0)
        max_val = rule.get("max", 100)
        val = random.uniform(min_val, max_val)
    elif distribution == "exponential":
        scale = rule.get("scale", 1.0)
        # Python 的 random.expovariate 接收 lambda = 1/scale
        if scale <= 0:
            scale = 1.0
        val = random.expovariate(1.0 / scale)
    elif distribution == "weighted_groups":
        groups = rule["groups"]
        weights = [g["weight"] for g in groups]
        chosen = random.choices(groups, weights=weights, k=1)[0]
        lo, hi = chosen["range"]
        val = random.uniform(lo, hi)
    else:
        raise ValueError(f"[resident_generate] 未知分布类型 '{distribution}'")

    # min/max 截断
    if "min" in rule:
        val = max(val, rule["min"])
    if "max" in rule:
        val = min(val, rule["max"])

    if dtype == "int":
        return int(round(val))
    return float(val)


def _generate_composite(rule: dict):
    """组合型属性（如从词库中随机抽取若干个拼接）。"""
    # 优先使用直接给出的候选词列表
    words = rule.get("words")
    if isinstance(words, list):
        count = rule.get("count", 1)
        if len(words) < count:
            print(f"警告: composite 候选词不足 {count} 个，返回全部")
            count = len(words)
        selected = random.sample(words, count)
        return rule.get("separator", " ").join(selected)

    # 兼容旧版：从外部文件读取候选词
    source = rule.get("source")
    if source == "file":
        filepath = rule["file"]
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"[resident_generate] composite 源文件不存在: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            words = [line.strip() for line in f if line.strip()]
        count = rule.get("count", 1)
        if len(words) < count:
            print(f"警告: 文件 '{filepath}' 中词语不足 {count} 个，返回全部")
            count = len(words)
        selected = random.sample(words, count)
        return rule.get("separator", " ").join(selected)

    raise ValueError(f"[resident_generate] composite 规则缺少候选词，需要 'words' 列表或 'source: file'")


def _eval_condition(condition: str, profile: dict) -> bool:
    """简易条件求值（安全子集）。支持 profile 字段的直接比较表达式。

    示例条件:
        "education_level in ['硕士', '博士']"
        "cross_border_experience > 0"
        "age >= 25"
    """
    if not condition:
        return True
    # 构建安全上下文：只允许 profile 中的字段和基本字面量
    safe_ctx = {"__builtins__": {}}
    safe_ctx.update(profile)
    try:
        return bool(eval(condition, safe_ctx, {}))
    except Exception:
        # 条件解析失败时默认不触发约束
        return False


def _apply_adjustment(current_value, adjustment: dict):
    """对单个属性值应用修正。"""
    if "set" in adjustment:
        return adjustment["set"]

    # 如果 adjustment 指定了新的 choices/weights，则重新抽样
    if "choices" in adjustment:
        choices = adjustment["choices"]
        weights = adjustment.get("weights")
        return random.choices(choices, weights=weights, k=1)[0]

    # 数值修正
    val = current_value
    if isinstance(val, (int, float)):
        if "multiplier" in adjustment:
            val = val * adjustment["multiplier"]
        if "add" in adjustment:
            val = val + adjustment["add"]
        if "min_override" in adjustment:
            val = max(val, adjustment["min_override"])
        if "max_override" in adjustment:
            val = min(val, adjustment["max_override"])
        # 保持原类型
        if isinstance(current_value, int):
            return int(round(val))
        return val
    return current_value


# =============================================================================
# 批量生成入口
# =============================================================================

def generate_resident_data(n, profile_config=None):
    """批量生成居民数据。

    Args:
        n: 生成数量
        profile_config: 若为 None，使用旧版硬编码逻辑；否则按配置驱动生成。
    """
    if n <= 0:
        return []

    resident_data = []
    start_time = datetime.now()

    if profile_config is None:
        # 旧逻辑：并发线程池
        max_workers = min(os.cpu_count() * 2, n, 32)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_legacy_generate_resident_profile) for _ in range(n)]
            for future in as_completed(futures):
                profile = future.result()
                if profile:
                    resident_data.append(profile)
    else:
        # 新逻辑：配置驱动，单线程生成足够快（纯 Python 随机运算）
        for _ in range(n):
            profile = generate_resident_profile(profile_config)
            resident_data.append(profile)

    elapsed_time = datetime.now() - start_time
    print(f"已生成 {len(resident_data)} 个居民数据，用时：{elapsed_time}")
    return resident_data


def save_resident_data(resident_data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(resident_data, f, ensure_ascii=False, indent=2)


# 向后兼容别名
generate_agent_data = generate_resident_data
save_agent_data = save_resident_data


if __name__ == "__main__":
    N = 10000  # 目标数据量
    resident_data = generate_resident_data(N)
    output_path = 'experiment_dataset/resident_data/resident_data.json'
    save_resident_data(resident_data, output_path)
    print(f"生成 {N} 个清代普通百姓的个人信息并保存到 {output_path}")
