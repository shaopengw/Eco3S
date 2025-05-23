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
        # 工资单位为季度
        self.jobs_info = {
            "农民": {"total": 0, "employed": [], "salary": 10},  # 基础农业劳动者工资
            "商人": {"total": 0, "employed": [], "salary": 30},  # 经商收入较高
            "叛军": {"total": 0, "employed": [], "salary": 15},  # 非正规收入
            "官员及士兵": {"total": 0, "employed": [], "salary": 25},  # 正规军饷和俸禄
            "其他": {"total": 0, "employed": [], "salary": 12}   # 其他普通职业工资
        }
        
        # 根据城镇类型初始化工作数量
        self._initialize_jobs(initial_jobs_count)
    
    def _initialize_jobs(self, total_count):
        """
        根据比例初始化各类工作的数量
        :param total_count: 总工作数量
        """
        professions_ratio = {
            "农民": {"沿河": [0.5, 0.6], "非沿河": [0.7, 0.8]},
            "商人": {"沿河": [0.1, 0.15], "非沿河": [0.0, 0.05]},
            "叛军": {"沿河": [0.01, 0.1], "非沿河": [0.01, 0.02]},
            "官员及士兵": {"沿河": [0.05, 0.08], "非沿河": [0.02, 0.03]},
            "其他": {"沿河": [0.1, 0.2], "非沿河": [0.1, 0.15]}
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

    def assign_specific_job(self, resident, job_type):
        """
        分配指定职业给指定居民
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
                info["employed"].remove(resident.resident_id)
                break
                
        # 分配新工作
        self.jobs_info[job_type]["employed"].append(resident.resident_id)
        salary = self.jobs_info[job_type]["salary"]
        resident.employ(job_type, salary)  # 更新居民的工作和工资信息
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
            self.jobs_info[job]["employed"].append(resident.resident_id)
            salary = self.jobs_info[job]["salary"]
            resident.employ(job, salary)  # 更新居民的工作和工资信息
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
        :return: 失业率（0到1之间的值）
        """
        total_employed = sum(len(info["employed"]) for info in self.jobs_info.values())
        
        if total_residents == 0:
            return 0.0
        return 1.0 - (total_employed / total_residents)

    def print_job_market_status(self):
        """
        打印就业市场状态（用于调试）
        """
        print(f"\n城镇类型: {self.town_type}")
        for job, info in self.jobs_info.items():
            print(f"{job}: 总数 {info['total']}, 已就业 {len(info['employed'])}, "
                  f"空缺 {info['total'] - len(info['employed'])}, "
                  f"工资 {info['salary']}")

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
                self.jobs_info[job_type]["employed"].remove(resident_id)
                return True
        else:
            # 如果没有指定工作类型，搜索所有工作类型
            for job_info in self.jobs_info.values():
                if resident_id in job_info["employed"]:
                    job_info["employed"].remove(resident_id)
                    return True
        return False

    def get_job_statistics(self, job_type):
        """
        获取指定职业的统计信息
        """
        if job_type in self.jobs_info:
            total_positions = self.jobs_info[job_type]["total"]
            current_employed = len(self.jobs_info[job_type]["employed"])
            salary = self.jobs_info[job_type]["salary"]
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
            
        print(f"已随机减少 {num_jobs} 个工作岗位")

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
        获取指定职业的工资
        :param job_type: 职业类型
        :return: 工资金额，如果职业不存在则返回None
        """
        if job_type in self.jobs_info:
            return self.jobs_info[job_type]["salary"]
        return None

    def process_job_applications(self, job_requests):
        """
        处理求职申请
        :param job_requests: 求职申请列表，每个申请包含居民信息、期望职业和最低工资要求
        :return: 成功录用的居民ID列表
        """
        # 按职业类型对申请进行分组
        job_type_applications = defaultdict(list)
        for request in job_requests:
            job_type = request["desired_job"]
            if job_type in self.jobs_info:
                job_type_applications[job_type].append(request)
        
        hired_residents = []
        
        # 处理每种职业的申请
        for job_type, applications in job_type_applications.items():
            # 获取该职业的空缺数量
            vacant_positions = self.jobs_info[job_type]["total"] - len(self.jobs_info[job_type]["employed"])
            
            if vacant_positions <= 0:
                continue
                
            # 如果空缺数量大于申请人数，全部录用
            if vacant_positions >= len(applications):
                for app in applications:
                    resident = app["resident"]
                    if self.assign_specific_job(resident, job_type):
                        hired_residents.append(resident.resident_id)
            else:
                # 空缺数量小于申请人数，按最低工资要求排序，择优录取
                applications.sort(key=lambda x: x["min_salary"])
                for app in applications[:vacant_positions]:
                    resident = app["resident"]
                    if self.assign_specific_job(resident, job_type):
                        hired_residents.append(resident.resident_id)
        
        return hired_residents