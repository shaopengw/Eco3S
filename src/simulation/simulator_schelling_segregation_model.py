from .simulator_imports import *

class SchellingSegregationModelSimulator:
    
    def __init__(self, **kwargs):

        self.logger = LogManager.get_logger('simulator', console_output=True)

        self.map = kwargs.get('map')

        self.time = kwargs.get('time')

        self.population = kwargs.get('population')

    
        self.social_network = kwargs.get('social_network')

    
        self.residents = kwargs.get('residents')

    
        self.towns = kwargs.get('towns')

    
        self.config = kwargs.get('config')


    
        self.basic_living_cost = 8

    
        self.average_satisfaction = None

    
        self.similarity_threshold = 0.5


    
        self.results = self.init_results()

    
        self.start_time = None

    
        self.end_time = None


    
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    
        pid = os.getpid()

    
        data_dir = SimulationContext.get_data_dir()

    
        SimulationContext.ensure_directories()

    
        self.result_file = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
    
    def init_results(self):

    
        return {

    
            "years": [],

    
            "population": [],

    
            "migration_rate": [],

    
            "average_satisfaction": [],

    
            "average_similarity": [],

    
            "segregation_index": [],

    
            "type_a_population": [],

    
            "type_b_population": [],

    
        }

    async def run(self):
            """主运行流程：初始化→主循环→结束"""
            self.start_time = datetime.now()

            while not self.time.is_end():


                self.print_time_step()


                await self.update_state()


                await self.execute_actions()


                self.collect_results()


                self.save_results(self.result_file, append=True)

                ResidentStateExporter.save_resident_data(self)

                self.time.step()


            self.end_time = datetime.now()


            self.display_total_simulation_time()

    def print_time_step(self):


            """打印当前时间步信息"""


            print(Back.GREEN + f"年份:{self.time.current_time}" + Back.RESET)


            self.logger.info(f"年份:{self.time.current_time}")

    async def update_state(self):


            self.average_satisfaction = self.calculate_average_satisfaction()


            self.population.update_birth_rate(self.average_satisfaction)

    async def execute_actions(self):

            print("[模拟] 居民决策与行动执行中...")
            self.migration_count = 0


            new_count = int(self.population.birth_rate * self.population.get_population())


            new_residents = await generate_new_residents(


                count=new_count,


                map=self.map,


                residents=self.residents,


                social_network=self.social_network,


                resident_prompt_path=self.config["data"]["resident_prompt_path"],


                resident_actions_path=self.config["data"]["resident_actions_path"],


            )


            await self.integrate_new_residents(new_residents)


            self.population.birth(new_count)


            self.logger.info(f"新加入{new_count}名居民，目前出生率为{self.population.birth_rate}")


            # 创建居民引用列表和任务列表，保持顺序一致
            residents_list = list(self.residents.values())
            
            # 记录所有居民的位置
            old_locations = {id(resident): resident.location for resident in residents_list}
            
            tasks = []


            for resident in residents_list:
                if resident.update_resident_status(self.basic_living_cost):
                    del self.residents[resident.resident_id]
                    self.population.death()

                neighbor_similarity = self.calculate_neighbor_similarity(resident)

                task = resident.decide_action_by_llm(
                    basic_living_cost=self.basic_living_cost,
                    neighbor_similarity=neighbor_similarity,
                    similarity_threshold=self.similarity_threshold,
                    current_year=self.time.current_time
                )
                tasks.append(task)

            if tasks:

                results = await asyncio.gather(*tasks)

                for i, result in enumerate(results):


                    if i >= len(residents_list):


                        break


                    resident = residents_list[i]


                    if isinstance(result, tuple) and len(result) >= 2:


                        select, reason = result[0], result[1]


                        await resident.execute_decision(select, map=self.map)


                        # 检查迁移是否真的发生（通过位置变化检测）
                        old_location = old_locations.get(id(resident))
                        if old_location and resident.location != old_location:


                            self.migration_count += 1


                            self.logger.debug(f"居民 {resident.resident_id} 迁移: {old_location} -> {resident.location}, 当前总数: {self.migration_count}")



            current_year = self.time.current_time


            if current_year % random.randint(3, 5) == 0:


                self.social_network.update_network_edges()

    def collect_results(self):


            # 获取本期迁移计数
            current_migration_count = getattr(self, 'migration_count', 0)
            total_population = self.population.get_population()
            migration_rate = current_migration_count / total_population * 100 if total_population > 0 else 0.0


            average_similarity = self.calculate_average_similarity()


            segregation_index = self.calculate_segregation_index()


            type_a_count, type_b_count = self.count_resident_types()


            self.results["years"].append(self.time.current_time)


            self.results["population"].append(total_population)


            self.results["migration_rate"].append(migration_rate)


            self.results["average_satisfaction"].append(self.average_satisfaction)


            self.results["average_similarity"].append(average_similarity)


            self.results["segregation_index"].append(segregation_index)


            self.results["type_a_population"].append(type_a_count)


            self.results["type_b_population"].append(type_b_count)


            self.logger.info(f"年份: {self.time.current_time}, "


                  f"人口: {total_population}, "


                  f"迁移人数: {current_migration_count}, "
                  f"迁移率: {migration_rate:.2f}%, "


                  f"平均满意度: {self.average_satisfaction:.2f}, "


                  f"平均相似度: {average_similarity:.2f}, "


                  f"隔离指数: {segregation_index:.2f}, "


                  f"类型A: {type_a_count}, 类型B: {type_b_count}"


            )

    def save_results(self, filename=None, append=False):
        """保存结果到CSV文件"""
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()  # 获取进程ID以避免并行实验文件名冲突
            filename = os.path.join(data_dir, f"running_data_{timestamp}_pid{pid}.csv")
        
        if append:
            last_row_data = {key: [value[-1]] for key, value in self.results.items() if value}
            df = pd.DataFrame(last_row_data)
        else:
            df = pd.DataFrame(self.results)
        
        if append and os.path.exists(filename):
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            df.to_csv(filename, index=False)
        
        if not append:
            self.logger.info(f"模拟结果已完整保存至 {filename}")

    def display_total_simulation_time(self):
        """显示总模拟时间"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            self.logger.info(f"总模拟时间: {total_time}")
    
    # ==================== 群体决策方法 ====================
    
    def calculate_average_satisfaction(self):
        """计算所有居民的平均满意度"""
        if not self.residents:
            self.logger.warning("没有居民，平均满意度为 0.0")
            return 0.0
        
        total_satisfaction = sum(resident.satisfaction for resident in self.residents.values())
        if self.population.population == 0:
            self.logger.warning("人口为零，平均满意度为 0.0")
            return 0.0
        average_satisfaction = total_satisfaction / self.population.population
        self.logger.info(f"平均满意度: {average_satisfaction} = {total_satisfaction / self.population.population:.2f}")
        return average_satisfaction
    
    def get_basic_living_cost(self):
        """获取当前基本生活所需值"""
        return self.basic_living_cost
    
    async def integrate_new_residents(self, new_residents):

    
            """整合新居民到系统"""

    
            if not new_residents:

    
                return

    
            # 为新居民随机分配类型（A或B）
            for resident in new_residents.values():
                resident.resident_type = random.choice(['A', 'B'])

    
            self.residents.update(new_residents)

    
            self.logger.info(f"{len(new_residents)} 名新居民已出生")

    
            for resident_id, resident in new_residents.items():

    
                if resident.location:

    
                    nearest_town = self.towns.get_nearest_town(resident.location)

    
                    if nearest_town:

    
                        self.towns.add_resident(resident, nearest_town)

    
            self.logger.info("新居民已加入各自城镇")

    
            if new_residents:

    
                self.social_network.add_new_residents(new_residents)

    
                self.logger.info(f"{len(new_residents)} 名新居民已加入社交网络")

    def calculate_neighbor_similarity(self, resident):


            if not resident.location:


                return 0.0


            x, y = resident.location


            neighbors = []


            for dx in [-1, 0, 1]:


                for dy in [-1, 0, 1]:


                    if dx == 0 and dy == 0:


                        continue


                    nx, ny = x + dx, y + dy


                    if 0 <= nx < self.map.width and 0 <= ny < self.map.height:


                        neighbors.append((nx, ny))


            if not neighbors:


                return 0.0


            same_type_count = 0


            total_neighbors = 0


            resident_type = getattr(resident, 'resident_type', 'A')


            for neighbor_loc in neighbors:


                for neighbor_id, neighbor in self.residents.items():


                    if neighbor.location == neighbor_loc:


                        neighbor_type = getattr(neighbor, 'resident_type', 'A')


                        if neighbor_type == resident_type:


                            same_type_count += 1


                        total_neighbors += 1


                        break


            return same_type_count / total_neighbors if total_neighbors > 0 else 0.0


    def calculate_average_similarity(self):
        if not self.residents:
            return 0.0

        total_similarity = 0
        for resident in self.residents.values():
            total_similarity += self.calculate_neighbor_similarity(resident)

        return total_similarity / len(self.residents)


    def calculate_segregation_index(self):
        """
        使用相异指数（Index of Dissimilarity）计算隔离指数。
        该指数衡量两组在空间单元中的分布差异。
        指数范围从0（完全整合）到1（完全隔离）。
        """
        if not self.residents:
            return 0.0

        type_a_total = 0
        type_b_total = 0
        for resident in self.residents.values():
            resident_type = getattr(resident, 'resident_type', 'A')
            if resident_type == 'A':
                type_a_total += 1
            else:
                type_b_total += 1

        if type_a_total == 0 or type_b_total == 0:
            return 0.0  # 如果只有一个组别，则无隔离

        # 动态调整邻域网格大小，例如，取地图较小维度的20%
        map_width = self.map.width
        map_height = self.map.height
        grid_size = max(1, int(min(map_width, map_height) * 0.2))
        
        # 确保网格大小合理
        num_cells_x = max(1, map_width // grid_size)
        num_cells_y = max(1, map_height // grid_size)

        neighborhoods = [[{'A': 0, 'B': 0} for _ in range(num_cells_y)] for _ in range(num_cells_x)]

        for resident in self.residents.values():
            if resident.location:
                x, y = resident.location
                grid_x = min(int(x // grid_size), num_cells_x - 1)
                grid_y = min(int(y // grid_size), num_cells_y - 1)
                
                resident_type = getattr(resident, 'resident_type', 'A')
                if resident_type == 'A':
                    neighborhoods[grid_x][grid_y]['A'] += 1
                else:
                    neighborhoods[grid_x][grid_y]['B'] += 1

        dissimilarity_sum = 0
        for i in range(num_cells_x):
            for j in range(num_cells_y):
                a_i = neighborhoods[i][j]['A']
                b_i = neighborhoods[i][j]['B']
                
                term1 = a_i / type_a_total if type_a_total > 0 else 0
                term2 = b_i / type_b_total if type_b_total > 0 else 0
                
                dissimilarity_sum += abs(term1 - term2)

        segregation_index = 0.5 * dissimilarity_sum
        return segregation_index


    def count_resident_types(self):
        type_a_count = 0
        type_b_count = 0

        for resident in self.residents.values():
            resident_type = getattr(resident, 'resident_type', 'A')
            if resident_type == 'A':
                type_a_count += 1
            else:
                type_b_count += 1

        return type_a_count, type_b_count
