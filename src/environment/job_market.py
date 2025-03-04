class JobMarket:
    def __init__(self):
        """
        初始化就业市场类
        """
        self.jobs = []  # 可用工作列表
        self.employed_residents = {}  # 已就业工人字典，键为工作，值为工人列表

    def add_job(self, job):
        """
        添加工作机会
        :param job: 工作名称
        """
        self.jobs.append(job)
        self.employed_residents[job] = []

    def remove_job(self, job):
        """
        移除工作机会
        :param job: 工作名称
        """
        if job in self.jobs:
            self.jobs.remove(job)
            if job in self.employed_residents:
                del self.employed_residents[job]

    def get_job(self, resident):
        """
        分配工作给居民
        :param resident: 居民对象
        """
        if self.jobs:
            job = self.jobs.pop(0)  # 分配第一个可用工作
            resident.employ(job)
            self.employed_residents[job].append(resident)
        else:
            resident.unemploy()

    def get_available_jobs(self):
        """
        获取当前可用工作列表
        :return: 可用工作列表
        """
        return self.jobs

    def get_employed_residents(self):
        """
        获取已就业居民字典
        :return: 已就业居民字典
        """
        return self.employed_residents

    def get_unemployment_rate(self, total_residents):
        """
        计算失业率
        :param total_residents: 总居民数
        :return: 失业率（0到1之间的值）
        """
        employed_residents = sum(len(residents) for residents in self.employed_residents.values())
        if total_residents == 0:
            return 0.0
        return 1.0 - (employed_residents / total_residents)

    def print_job_market_status(self):
        """
        打印就业市场状态（用于调试）
        """
        print("Available Jobs:", self.jobs)
        print("Employed residents:")
        for job, residents in self.employed_residents.items():
            print(f"{job}: {len(residents)} residents")