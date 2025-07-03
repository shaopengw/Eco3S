import random
from collections import defaultdict
class JobMarket:
    def __init__(self, town_type="非沿河", initial_jobs_count=100):
        """
        初始化就业市场类
        :param town_type: 城镇类型（"沿河"或"非沿河"）
        :param initial_jobs_count: 初始工作总数
        """
        self.town_type = town_type
        # 收入单位为季度
        self.jobs_info = {
            "农民": {"total": 0, "employed": {}, "base_salary": 10},  # 基础农业劳动者收入
            "商人": {"total": 0, "employed": {}, "base_salary": 30},  # 经商收入较高
            "叛军": {"total": 0, "employed": {}, "base_salary": 12},  # 非正规收入
            "官员及士兵": {"total": 0, "employed": {}, "base_salary": 25},  # 正规军饷和俸禄
            "运河维护工": {"total": 0, "employed": {}, "base_salary": 15},  # 运河维护收入
            "其他": {"total": 0, "employed": {}, "base_salary": 12}   # 其他普通职业收入
        }
        
        # 根据城镇类型初始化工作数量
        self._initialize_jobs(initial_jobs_count)
    
    def _initialize_jobs(self, total_count):
        """
        根据比例初始化各类工作的数量
        :param total_count: 总工作数量
        """
        professions_ratio = {
            "农民": {"沿河": [0.4, 0.5], "非沿河": [0.7, 0.8]},
            "商人": {"沿河": [0.1, 0.15], "非沿河": [0.0, 0.05]},
            "叛军": {"沿河": [0.01, 0.1], "非沿河": [0.01, 0.02]},
            "官员及士兵": {"沿河": [0.05, 0.08], "非沿河": [0.02, 0.03]},
            "运河维护工": {"沿河": [0.15, 0.25], "非沿河": [0.0, 0.0]},
            "其他": {"沿河": [0.05, 0.1], "非沿河": [0.1, 0.15]}
        }

        # 确保总岗位数不小于职业类型数
        total_count = max(total_count, len(professions_ratio))
        
        # 首先为每种工作分配一个基础岗位
        remaining_count = total_count - len(professions_ratio)
        for job in professions_ratio:
            self.jobs_info[job]["total"] = 1
        
        # 然后按比例分配剩余岗位，保留一部分给农民
        reserved_for_farmers = int(remaining_count * 0.2)  # 预留20%给农民
        remaining_for_others = remaining_count - reserved_for_farmers
        
        allocated_count = 0
        for job, ratios in professions_ratio.items():
            if job == "农民":
                continue
            ratio_range = ratios[self.town_type]
            ratio = random.uniform(ratio_range[0], ratio_range[1])
            additional_jobs = max(0, int(remaining_for_others * ratio))
            self.jobs_info[job]["total"] += additional_jobs
            allocated_count += additional_jobs
        
        # 将所有剩余的工作分配给农民，确保非负
        remaining_jobs = max(0, remaining_count - allocated_count)
        self.jobs_info["农民"]["total"] += remaining_jobs + reserved_for_farmers
    
    def add_job(self, job, num=1):
        """
        添加工作机会
        :param job: 工作名称
        :param num: 添加该工作的数量，默认为1
        """
        if job in self.jobs_info:
            self.jobs_info[job]["total"] += num

    def remove_job(self, job):
        """
        移除工作机会
        :param job: 工作名称
        """
        if job in self.jobs_info and self.jobs_info[job]["total"] > 0:
            self.jobs_info[job]["total"] -= 1

    def assign_specific_job(self, resident, job_type, actual_salary=None):
        """
        分配指定职业给指定居民
        :param actual_salary: 实际支付的居民收入，如果为None则使用基础收入
        """
        # 检查职业类型是否存在
        if job_type not in self.jobs_info:
            print(f"错误：不存在的职业类型 {job_type}")
            return False
            
        # 检查该职业是否还有空缺
        if len(self.jobs_info[job_type]["employed"]) >= self.jobs_info[job_type]["total"]:
            print(f"错误：{job_type} 职位已满")
            return False
            
        # 如果居民已经在其他职业就业，先移除原有工作
        for job, info in self.jobs_info.items():
            if resident.resident_id in info["employed"]:
                del info["employed"][resident.resident_id]
                break
                
        # 分配新工作，使用实际收入或基础收入
        salary = actual_salary if actual_salary is not None else self.jobs_info[job_type]["base_salary"]
        self.jobs_info[job_type]["employed"][resident.resident_id] = salary
        resident.employ(job_type, salary)  # 更新居民的工作和收入信息
        return True

    def assign_job(self, resident):
        """
        随机分配工作给居民
        :param resident: 居民对象
        """
        available_jobs = [job for job, info in self.jobs_info.items() 
                         if len(info["employed"]) < info["total"]]
        
        if available_jobs:
            # 随机选择一个可用工作
            job = random.choice(available_jobs)
            base_salary = self.jobs_info[job]["base_salary"]
            self.jobs_info[job]["employed"][resident.resident_id] = base_salary
            resident.employ(job, base_salary)  # 更新居民的工作和收入信息
        else:
            resident.unemploy()

    def get_available_jobs(self):
        """
        获取当前可用工作列表
        :return: 可用工作及其剩余数量的字典
        """
        return {job: info["total"] - len(info["employed"]) 
                for job, info in self.jobs_info.items()}

    def get_employed_residents(self):
        """
        获取已就业居民信息
        :return: 职业及其从业人员ID的字典
        """
        return {job: info["employed"] for job, info in self.jobs_info.items()}

    def get_unemployment_rate(self, total_residents):
        """
        计算失业率
        :param total_residents: 总居民数
        :return: 失业率（0到100之间的值）
        """
        total_employed = sum(len(info["employed"]) for info in self.jobs_info.values())
        
        if total_residents == 0:
            return 0.0
        return (1.0 - (total_employed / total_residents)) * 100

    def print_job_market_status(self):
        """
        打印就业市场状态（用于调试）
        """
        print(f"\n城镇类型: {self.town_type}")
        for job, info in self.jobs_info.items():
            print(f"{job}:总数：{info['total']}, 已就业：{info['employed']},基本收入：{info['base_salary']}")

    def remove_resident(self, resident_id, job_type=None):
        """
        从就业市场中删除指定居民的信息
        :param resident_id: 居民ID
        :param job_type: 工作类型，如果不指定则搜索所有工作类型
        :return: 是否成功删除
        """
        if job_type and job_type in self.jobs_info:
            # 如果指定了工作类型，直接从该类型中删除
            if resident_id in self.jobs_info[job_type]["employed"]:
                del self.jobs_info[job_type]["employed"][resident_id]
                return True
        else:
            # 如果没有指定工作类型，搜索所有工作类型
            for job_info in self.jobs_info.values():
                if resident_id in job_info["employed"]:
                    del job_info["employed"][resident_id]
                    return True
        return False

    def get_job_statistics(self, job_type):
        """
        获取指定职业的统计信息
        """
        if job_type in self.jobs_info:
            total_positions = self.jobs_info[job_type]["total"]
            current_employed = len(self.jobs_info[job_type]["employed"])
            salary = self.jobs_info[job_type]["base_salary"]
            return total_positions, current_employed, salary
        return None

    def remove_random_jobs(self, num_jobs):
        """
        随机减少指定数量的工作岗位
        :param num_jobs: 需要减少的工作岗位数量
        """
        # 获取所有职业类型的当前总工作数量
        total_jobs = sum(info["total"] for info in self.jobs_info.values())
        
        # 如果要减少的数量大于现有工作数量，则调整为现有数量
        num_jobs = min(num_jobs, total_jobs)
        
        # 按比例分配每个职业要减少的数量
        remaining_jobs = num_jobs
        for job_type, info in self.jobs_info.items():
            if remaining_jobs <= 0:
                break
                
            # 计算该职业应该减少的数量（按比例）
            job_ratio = info["total"] / total_jobs if total_jobs > 0 else 0
            jobs_to_remove = min(int(num_jobs * job_ratio), info["total"], remaining_jobs)
            
            # 减少该职业的工作数量
            info["total"] = max(0, info["total"] - jobs_to_remove)
            remaining_jobs -= jobs_to_remove
            
            # 如果减少后的工作数量小于当前就业人数，需要随机解雇一些员工
            if len(info["employed"]) > info["total"]:
                # 需要解雇的人数
                num_to_layoff = len(info["employed"]) - info["total"]
                # 随机选择要解雇的员工
                employees_to_layoff = random.sample(info["employed"], num_to_layoff)
                # 从就业列表中移除这些员工
                for employee in employees_to_layoff:
                    info["employed"].remove(employee)
        # print(f"已随机减少 {num_jobs} 个工作岗位").

    def adjust_canal_maintenance_jobs(self, change_rate, residents):
        """
        根据运河状态的变化率调整运河维护工的数量
        :param change_rate: 运河状态的变化率（-1到1之间的值）
        """
        # 只处理沿河城镇
        if self.town_type != "沿河":
            return

        # 只处理负变化率的情况
        if change_rate >= 0:
            return
            
        # 获取当前运河维护工的数量
        current_jobs = self.jobs_info["运河维护工"]["total"]
        # 减少工作数量（按比例，最少减少1个）
        reduction = max(1, int(current_jobs * abs(change_rate)))
        new_jobs = max(0, current_jobs - reduction)
        self.jobs_info["运河维护工"]["total"] = new_jobs
        
        # 如果当前就业人数超过新的总数，需要解雇一些工人
        employed_count = len(self.jobs_info["运河维护工"]["employed"])
        if employed_count > new_jobs:
            # 随机选择要解雇的工人
            workers_to_layoff_ids = random.sample(
                list(self.jobs_info["运河维护工"]["employed"].keys()),
                employed_count - new_jobs
            )
            # 解雇工人
            for resident_id in workers_to_layoff_ids:
                # 从传入的residents列表中找到对应的居民对象
                resident = residents.get(resident_id)
                if resident:
                    self.remove_resident(resident.resident_id, "运河维护工")
                    resident.unemploy()
                else:
                    print(f"警告: 未找到ID为 {resident_id} 的居民对象，无法解雇。")


    def get_vacant_jobs(self):
        """
        获取所有空工作岗位的名称和数量
        :return: 字典，键为工作名称，值为空缺数量
        """
        vacant_jobs = {}
        for job_type, info in self.jobs_info.items():
            vacant_count = info["total"] - len(info["employed"])
            if vacant_count > 0:
                vacant_jobs[job_type] = vacant_count
        return vacant_jobs

    def get_job_salary(self, job_type):
        """
        获取指定职业的收入
        :param job_type: 职业类型
        :return: 收入金额，如果职业不存在则返回None
        """
        if job_type in self.jobs_info:
            return self.jobs_info[job_type]["salary"]
        return None

    def process_job_applications(self, job_requests):
        """
        处理求职申请
        :param job_requests: 求职申请列表，每个申请包含居民信息、期望职业和最低收入要求
        :return: (成功录用的居民ID列表, 总支出)
        """
        # 按职业类型对申请进行分组
        job_type_applications = defaultdict(list)
        for request in job_requests:
            job_type = request["desired_job"]
            if job_type in self.jobs_info:
                job_type_applications[job_type].append(request)
        
        hired_residents = []
        total_salary_expense = 0  # 记录总支出
        
        # 处理每种职业的申请
        for job_type, applications in job_type_applications.items():
            vacant_positions = self.jobs_info[job_type]["total"] - len(self.jobs_info[job_type]["employed"])
            
            if vacant_positions <= 0:
                continue
            
            # 获取该职业的基础收入
            base_salary = self.jobs_info[job_type]["base_salary"]
            
            # 所有申请者按最低收入要求排序
            applications.sort(key=lambda x: x["min_salary"])
            
            # 根据空缺数量择优录取
            for app in applications[:vacant_positions]:
                if app["min_salary"] > base_salary:
                    continue
                resident = app["resident"]
                actual_salary = app["min_salary"]  # 使用居民要求的最低收入
                if self.assign_specific_job(resident, job_type, actual_salary):  # 传入实际收入
                    hired_residents.append(resident.resident_id)
                    total_salary_expense += actual_salary
        
        return hired_residents, total_salary_expense

    def get_rebel_total_salary(self):
        """
        获取叛军总收入
        :return: 叛军总收入
        """
        return sum(salary for salary in self.jobs_info["叛军"]["employed"].values())
    
    def get_other_total_salary(self):
        """
        获取除叛军外其他职业的总收入
        :return: 其他职业总收入
        """
        other_total = 0
        for job_type, info in self.jobs_info.items():
            if job_type != "叛军":
                other_total += sum(salary for salary in info["employed"].values())
        return other_total

    def add_random_jobs(self, num_jobs):
        """
        随机增加指定数量的工作岗位（除叛军外）
        :param num_jobs: 需要增加的工作岗位数量
        """
        # 获取除叛军外的所有职业类型
        available_jobs = [job for job in self.jobs_info.keys() if job != "叛军"]
        
        # 计算每个职业平均分配的岗位数
        jobs_per_profession = num_jobs // len(available_jobs)
        remaining_jobs = num_jobs % len(available_jobs)
        
        # 为每个职业分配基础岗位数
        for job in available_jobs:
            self.jobs_info[job]["total"] += jobs_per_profession
        
        # 随机分配剩余的岗位
        if remaining_jobs > 0:
            selected_jobs = random.sample(available_jobs, remaining_jobs)
            for job in selected_jobs:
                self.jobs_info[job]["total"] += 1
    