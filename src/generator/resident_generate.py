import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os

# 性别比例
gender_ratio = [0.351, 0.636]  # 女：男
genders = ['女性', '男性']

# 寿命比例（剩余寿命）
lifespan_ratio = [0.45, 0.35, 0.15, 0.05]
lifespan_groups = ['10-19', '20-39', '40-54', '55+'] # 仅考虑劳动力群体

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

# # MBT及其分布比例
# p_mbti = [
#     0.12625, 0.11625, 0.02125, 0.03125, 0.05125, 0.07125, 0.04625, 0.04125,
#     0.04625, 0.06625, 0.07125, 0.03625, 0.10125, 0.11125, 0.03125, 0.03125
# ]
# mbti_types = [
#     "ISTJ", "ISFJ", "INFJ", "INTJ", "ISTP", "ISFP", "INFP", "INTP", "ESTP",
#     "ESFP", "ENFP", "ENTP", "ESTJ", "ESFJ", "ENFJ", "ENTJ"
# ]
# 性格词语
personality_words = []

filepath='src/generator/personality_words.txt'
if not os.path.exists(filepath):
    print(f"警告: 性格词语文件 '{filepath}' 不存在。请确保文件存在且每行包含一个词语。")
with open(filepath, 'r', encoding='utf-8') as f:
    personality_words = [line.strip() for line in f if line.strip()]
if not personality_words:
    print(f"警告: 性格词语文件 '{filepath}' 为空或不包含有效词语。")

# 获取随机的性别
def get_random_gender():
    return random.choices(genders, gender_ratio)[0]

# 获取随机的寿命
def get_random_lifespan():
    group = random.choices(lifespan_groups, lifespan_ratio)[0]
    if group == '18-29':
        return random.randint(18, 29)
    elif group == '30-49':
        return random.randint(30, 49)
    elif group == '50-64':
        return random.randint(50, 64)
    else:
        return random.randint(65, 80)

# 获取随机居住地
def get_random_residence():
    return random.choices(residences, residence_ratio)[0]

# 获取随机满意度
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

# 获取随机健康指数
def get_random_health_index():
    return random.choices(health_indices, health_index_ratio)[0]

# 获取随机收入
def get_random_income():
    return random.choice(income_range)

# # 随机生成性格特征
# def get_random_mbti():
#     return random.choices(mbti_types, p_mbti)[0]

# 随机获取两个性格词语
def get_random_personality():
    if len(personality_words) < 2:
        print("警告: 性格词语不足两个，无法随机选择。请检查 personality_words.txt 文件。")
        return ""
    selected_traits = random.sample(personality_words, 2)
    return "、".join(selected_traits)

# 生成清代民众的个人信息
def generate_resident_profile():
    failure_count = 0
    while True:
        try:
            gender = get_random_gender()
            lifespan = get_random_lifespan()
            residence = get_random_residence()
            satisfaction = get_random_satisfaction()
            health_index = get_random_health_index()
            income = get_random_income()
            # mbti = get_random_mbti()
            personality = get_random_personality()

            profile = {
                "gender": gender,
                "lifespan": lifespan,
                "residence": residence,
                "satisfaction": satisfaction,
                "health_index": health_index,
                "income": income,
                # "mbti": mbti,
                "personality": personality,
            }
            # print(f"Generated profile: {profile}")
            return profile
            
        # except Exception as e:
        #     print(f"Profile generation failed: {e}. Retrying...")
        except Exception as e:
            failure_count += 1  # 失败次数加一
            print(f"Profile generation failed: {e}. Retrying...")
            if failure_count >= 3:  # 如果失败次数达到三次
                print("Failed to generate profile after 3 attempts. Terminating...")
                break  # 终止循环

# 批量生成清代民众数据
def generate_resident_data(n):
    resident_data = []
    start_time = datetime.now()
    max_workers = 10  # 可根据系统能力调整
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(generate_resident_profile) for _ in range(n)]
        for i, future in enumerate(as_completed(futures)):
            profile = future.result()
            resident_data.append(profile)
            elapsed_time = datetime.now() - start_time
            print(f"已生成 {i+1}/{n} 个数据，用时：{elapsed_time}")
    return resident_data

# 保存数据到文件
def save_resident_data(resident_data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(resident_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    N = 10000 # 目标数据量
    resident_data = generate_resident_data(N)
    output_path = 'experiment_dataset/resident_data/resident_data.json'
    save_resident_data(resident_data, output_path)
    print(f"生成 {N} 个清代普通百姓的个人信息并保存到 {output_path}")