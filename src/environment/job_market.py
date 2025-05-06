class JobMarket:
    def __init__(self):
        """
        初始化就业市场类
        """
        self.jobs = []  # 可用工作列表
        self.rebel_residents = []  # 叛军居民列表
        self.civilian_residents = {}  # 普通职业居民字典，键为工作，值为工人列表

    def add_job(self, job, num=1):
        """
        添加工作机会
        :param job: 工作名称
        :param num: 添加该工作的数量，默认为1
        """
        for _ in range(num):
            self.jobs.append(job)
        if job != "叛军" and job not in self.civilian_residents:
            self.civilian_residents[job] = []

    def remove_job(self, job):
        """
        移除工作机会
        :param job: 工作名称
        """
        if job in self.jobs:
            self.jobs.remove(job)
            if job != "叛军" and job in self.civilian_residents:
                del self.civilian_residents[job]

    def remove_random_jobs(self, num):
        """
        随机删除指定数量的工作机会
        :param num: 要删除的工作数量
        :return: 实际删除的工作数量
        """
        # 确保删除数量不超过现有工作数量
        num = min(num, len(self.jobs))
        
        # 随机选择要删除的工作
        jobs_to_remove = random.sample(self.jobs, num)
        
        # 删除选中的工作
        for job in jobs_to_remove:
            self.jobs.remove(job)
            if job != "叛军" and job in self.civilian_residents:
                del self.civilian_residents[job]
        return num

    def get_job(self, resident):
        """
        分配工作给居民
        :param resident: 居民对象
        """
        if self.jobs:
            job = self.jobs.pop(0)  # 分配第一个可用工作
            resident.employ(job)
            if job == "叛军":
                self.rebel_residents.append(resident)
            else:
                self.civilian_residents[job].append(resident)
        else:
            resident.unemploy()

    def remove_rebel(self, resident):
        """
        从叛军列表中移除指定居民
        :param resident: 要移除的叛军居民
        """
        if resident in self.rebel_residents:
            self.rebel_residents.remove(resident)
            resident.unemploy()

    def get_available_jobs(self):
        """
        获取当前可用工作列表
        :return: 可用工作列表
        """
        return self.jobs

    def get_employed_residents(self):
        """
        获取已就业居民信息
        :return: 包含叛军和普通职业居民的元组
        """
        return self.rebel_residents, self.civilian_residents

    def get_unemployment_rate(self, total_residents):
        """
        计算失业率
        :param total_residents: 总居民数
        :return: 失业率（0到1之间的值）
        """
        employed_rebels = len(self.rebel_residents)
        employed_civilians = sum(len(residents) for residents in self.civilian_residents.values())
        total_employed = employed_rebels + employed_civilians
        
        if total_residents == 0:
            return 0.0
        return 1.0 - (total_employed / total_residents)

    def print_job_market_status(self):
        """
        打印就业市场状态（用于调试）
        """
        print("Available Jobs:", self.jobs)
        print("Rebel residents count:", len(self.rebel_residents))
        print("Civilian residents:")
        for job, residents in self.civilian_residents.items():
            print(f"{job}: {len(residents)} residents")