import os
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from openai import OpenAI

from pathlib import Path
import yaml

# 加载配置文件
config_path = Path(__file__).parent.parent.parent / 'config' / 'simulation_config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# 根据配置初始化客户端
if config['api_settings']['api_type'] == 'openai':
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=config['api_settings'].get('base_url')
    )
elif config['api_settings']['api_type'] == 'deepseek':
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

# 职能比例
function_ratio = [0.02, 0.65, 0.22, 0.07]  # 漕运、行政、军事、经济管理
functions = ['漕运', '行政', '军事', '经济管理']

# MBT及其分布比例
p_mbti = [
    0.12625, 0.11625, 0.02125, 0.03125, 0.05125, 0.07125, 0.04625, 0.04125,
    0.04625, 0.06625, 0.07125, 0.03625, 0.10125, 0.11125, 0.03125, 0.03125
]
mbti_types = [
    "ISTJ", "ISFJ", "INFJ", "INTJ", "ISTP", "ISFP", "INFP", "INTP", "ESTP",
    "ESFP", "ENFP", "ENTP", "ESTJ", "ESFJ", "ENFJ", "ENTJ"
]

# 随机生成职能
def get_random_function():
    return random.choices(functions, function_ratio)[0]

# # 随机生成性格特征
# persona_gen_prompt = """
# 请生成一位中国清代政府官员的详细档案，仅描述其人格化特征（persona），用一句话概括该官员的性格和行为特点。

# **示例输出**：
#     "张显为人冷静沉稳，处事不惊，常以深思熟虑的态度处理政务。他在朝廷中以务实著称，常常偏向于现实的解决方案而非理想化的改革。"
# """

# 随机生成性格特征
def get_random_mbti():
    return random.choices(mbti_types, p_mbti)[0]

def generate_official_profile(is_high_rank=False):
    rank = '高级官员' if is_high_rank else '普通官员'
    for attempt in range(3):
        try:
            mbti = get_random_mbti()
            function = get_random_function()
            # 构建官员属性
            official_data = {
                "rank": rank,
                "function": function,
                "mbti": mbti,
            }
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

if __name__ == "__main__":
    N = 3  # 目标数据量
    official_data = generate_official_data(N)
    output_path = 'experiment_dataset/government_data/official_data.json'
    save_official_data(official_data, output_path)
    print(f"生成 {N} 官员信息成功. 已保存到 {output_path}")
