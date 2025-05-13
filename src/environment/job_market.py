import random
class JobMarket:
    def __init__(self, town_type="非沿河", initial_jobs_count=100):
        """
        初始化就业市场类
        :param town_type: 城镇类型（"沿河"或"非沿河"）
        :param initial_jobs_count: 初始工作总数
        """
        self.town_type = town_type
        self.jobs_info = {
            "农民": {"total": 0, "employed": []},
            "商人": {"total": 0, "employed": []},
            "叛军": {"total": 0, "employed": []},
            "官员及士兵": {"total": 0, "employed": []},
            "其他": {"total": 0, "employed": []}
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
        
        remaining_count = total_count
        for job, ratios in professions_ratio.items():
            ratio_range = ratios[self.town_type]
            # 使用随机比例
            ratio = random.uniform(ratio_range[0], ratio_range[1])
            job_count = int(total_count * ratio)
            self.jobs_info[job]["total"] = job_count
            remaining_count -= job_count
        
        # 将剩余的工作分配给农民
        self.jobs_info["农民"]["total"] += remaining_count

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

    def get_job(self, resident):
        """
        分配工作给居民
        :param resident: 居民对象
        """
        available_jobs = [job for job, info in self.jobs_info.items() 
                         if len(info["employed"]) < info["total"]]
        
        if available_jobs:
            # 随机选择一个可用工作
            job = random.choice(available_jobs)
            self.jobs_info[job]["employed"].append(resident.resident_id)
            resident.employ(job)
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
                  f"空缺 {info['total'] - len(info['employed'])}")

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