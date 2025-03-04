import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from openai import OpenAI

# 后期需要修改
client = OpenAI(
    api_key="sk-ag6xyYytuTV1aMLx0dspYKh1oQacGmiK6lOGqEYNvHQofYJl",
    base_url="https://api.chatanywhere.tech"  
)

# 加载提示词
with open('src/generator/government_prompt.txt', 'r', encoding='utf-8') as file:
    official_gen_prompt = file.read()

# 偏好与观点
def generate_user_profile():
    prompt = official_gen_prompt
    response = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": prompt}])
    profile = response.choices[0].message.content.strip()
    return json.loads(profile)


def generate_official_profile(is_high_rank=False):
    rank = '高级官员' if is_high_rank else '普通官员'
    for attempt in range(3):
        try:
            profile = generate_user_profile()
            
            # 构建官员属性
            official_data = {
                "rank": rank,
                "realname": profile['realname'],
                "age": profile['age'],
                "political_style": profile['political_style'],
                "preferences_and_views": profile['preferences_and_views'],
                "background": profile['background'],
                "persona": profile['persona'],
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
