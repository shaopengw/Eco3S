import os
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()


# 加载配置文件
config_path = Path(__file__).parent.parent.parent / 'config' / 'simulation_config.yaml'
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 职能比例
function_ratio = [0.25, 0.25, 0.25, 0.25]  # 漕运、行政、军事、经济管理
functions = ['漕运', '行政', '军事', '经济管理']

# 派别及其分布比例
faction_ratio = [0.3,0.3,0.4]
factions = ['河运派', '海运派', '中立派']

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
def get_random_function():
    return random.choices(functions, function_ratio)[0]

# 随机获取两个性格词语
def get_random_personality():
    if len(personality_words) < 2:
        print("警告: 性格词语不足两个，无法随机选择。请检查 personality_words.txt 文件。")
        return ""
    selected_traits = random.sample(personality_words, 2)
    return "、".join(selected_traits)



def generate_official_profile(is_high_rank=False):
    rank = '高级官员' if is_high_rank else '普通官员'
    for attempt in range(3):
        try:
            personality = get_random_personality()
            # 构建官员属性
            official_data = {
                "rank": rank,
                "personality": personality,
                
            }
            if not is_high_rank: # 普通官员独有属性
                function = get_random_function()
                faction = get_random_faction()
                official_data["function"] = function
                official_data["faction"] = faction

            print(f"生成的官员信息: {official_data}")
            return official_data
        except Exception as e:
            print(f"官员信息生成失败: {e}. 重试中... ({attempt + 1}/3)")
    print("重试3次后仍然失败，放弃生成该官员信息。")
    return None  # 返回None表示生成失败

# 批量生成官员数据
def generate_official_data(n):
    official_data = []
    start_time = datetime.now()
    max_workers = 10  # 可根据系统能力调整
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        # 先生成一名高级官员
        futures.append(executor.submit(generate_official_profile, is_high_rank=True))
        # 然后生成普通官员
        for _ in range(n - 1):
            futures.append(executor.submit(generate_official_profile, is_high_rank=False))
        
        for i, future in enumerate(as_completed(futures)):
            profile = future.result()
            official_data.append(profile)
            elapsed_time = datetime.now() - start_time
            print(f"生成 {i+1}/{n} 官员信息成功. 用时: {elapsed_time}")
    
    return official_data

# 保存数据到文件
def save_official_data(official_data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(official_data, f, ensure_ascii=False, indent=2)

# 随机生成派别
def get_random_faction():
    return random.choices(factions, faction_ratio)[0]

if __name__ == "__main__":
    N = 5 # 目标数据量
    official_data = generate_official_data(N)
    output_path = 'experiment_dataset/government_data/official_data.json'
    save_official_data(official_data, output_path)
    print(f"生成 {N} 官员信息成功. 已保存到 {output_path}")
