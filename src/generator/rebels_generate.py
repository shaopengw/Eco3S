import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os

# 职能比例
role_ratio = [0.25, 0.25, 0.25, 0.25]
roles = ['军事', '行政', '情报', '后勤']

# 性格词语
personality_words = []

filepath='src/generator/personality_words.txt'
if not os.path.exists(filepath):
    print(f"警告: 性格词语文件 '{filepath}' 不存在。请确保文件存在且每行包含一个词语。")
with open(filepath, 'r', encoding='utf-8') as f:
    personality_words = [line.strip() for line in f if line.strip()]
if not personality_words:
    print(f"警告: 性格词语文件 '{filepath}' 为空或不包含有效词语。")

# 随机生成职能
def get_random_role():
    return random.choices(roles, role_ratio)[0]

# 随机获取两个性格词语
def get_random_personality():
    if len(personality_words) < 2:
        print("警告: 性格词语不足两个，无法随机选择。请检查 personality_words.txt 文件。")
        return ""
    selected_traits = random.sample(personality_words, 2)
    return "、".join(selected_traits)

# 生成叛军档案
def generate_rebel_profile(is_leader=False):
    rank = '叛军头子' if is_leader else '普通叛军'
    for attempt in range(3):
        try:
            personality = get_random_personality()
            # 构建叛军属性
            rebel_data = {
                "rank": rank,
                "personality": personality,
            }
            if not is_leader:
                role = get_random_role()
                rebel_data["role"] = role

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
    N = 5  # 目标数据量
    rebel_data = generate_rebel_data(N)
    output_path = 'experiment_dataset/rebellion_data/rebels_data.json'
    save_rebel_data(rebel_data, output_path)
    print(f"生成 {N} 叛军信息成功. 已保存到 {output_path}")