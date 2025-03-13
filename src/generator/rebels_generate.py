import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 叛军等级比例
rank_ratio = [0.8, 0.2]  # 普通叛军、叛军头子
ranks = ['普通叛军', '叛军头子']

# 角色比例
role_ratio = [0.3, 0.2, 0.2, 0.1, 0.1, 0.1]
roles = ['侦察兵', '指挥官', '战士', '谋士', '间谍', '后勤']

# MBT及其分布比例
p_mbti = [
    0.12625, 0.11625, 0.02125, 0.03125, 0.05125, 0.07125, 0.04625, 0.04125,
    0.04625, 0.06625, 0.07125, 0.03625, 0.10125, 0.11125, 0.03125, 0.03125
]
mbti_types = [
    "ISTJ", "ISFJ", "INFJ", "INTJ", "ISTP", "ISFP", "INFP", "INTP", "ESTP",
    "ESFP", "ENFP", "ENTP", "ESTJ", "ESFJ", "ENFJ", "ENTJ"
]

# 随机生成叛军等级
def get_random_rank():
    return random.choices(ranks, rank_ratio)[0]

# 随机生成角色
def get_random_role():
    return random.choices(roles, role_ratio)[0]

# 随机生成性格特征
def get_random_mbti():
    return random.choices(mbti_types, p_mbti)[0]

# 生成叛军档案
def generate_rebel_profile(is_leader=False):
    rank = '叛军头子' if is_leader else '普通叛军'
    for attempt in range(3):
        try:
            role = get_random_role()
            mbti = get_random_mbti()
            # 构建叛军属性
            rebel_data = {
                "rank": rank,
                "role": role,
                "mbti": mbti,
            }
            print(f"生成的叛军信息: {rebel_data}")
            return rebel_data
        except Exception as e:
            print(f"叛军信息生成失败: {e}. 重试中... ({attempt + 1}/3)")
    print("重试3次后仍然失败，放弃生成该叛军信息。")
    return None  # 返回None表示生成失败

# 批量生成叛军数据
def generate_rebel_data(n):
    rebel_data = []
    start_time = datetime.now()
    max_workers = 10  # 可根据系统能力调整
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        # 先生成一名叛军头子
        futures.append(executor.submit(generate_rebel_profile, is_leader=True))
        # 然后生成普通叛军
        for _ in range(n - 1):
            futures.append(executor.submit(generate_rebel_profile, is_leader=False))
        
        for i, future in enumerate(as_completed(futures)):
            profile = future.result()
            rebel_data.append(profile)
            elapsed_time = datetime.now() - start_time
            print(f"生成 {i+1}/{n} 叛军信息成功. 用时: {elapsed_time}")
    
    return rebel_data

# 保存数据到文件
def save_rebel_data(rebel_data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(rebel_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    N = 3  # 目标数据量
    rebel_data = generate_rebel_data(N)
    output_path = 'experiment_dataset/rebellion_data/rebels_data.json'
    save_rebel_data(rebel_data, output_path)
    print(f"生成 {N} 叛军信息成功. 已保存到 {output_path}")