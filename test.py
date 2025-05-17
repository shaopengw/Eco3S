import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.agents.resident import Resident
from src.environment.map import Map
from src.environment.job_market import JobMarket
from src.agents.resident import ResidentSharedInformationPool

async def test_resident_migration():
    # 初始化地图（使用默认的城市数据文件）
    map = Map(width=100, height=100)
    # 加载城市数据

    map.initialize_town_matrix()
    
    # 初始化工作市场和共享信息池
    job_market = JobMarket()
    shared_pool = ResidentSharedInformationPool()
    
    # 创建居民实例
    resident = Resident(
        resident_id=1,
        job_market=job_market,
        shared_pool=shared_pool,
        map=map
    )
    
    # 为居民分配初始位置
    initial_town = list(map.town_dict.keys())[0]  # 获取第一个城市
    initial_location, initial_town_id = map.generate_random_location(initial_town)
    resident.location = initial_location
    resident.town = initial_town_id
    
    print(f"初始位置: {initial_location}, 初始城镇: {initial_town_id}")
    
    # 测试迁移
    for i in range(5):  # 测试5次迁移
        print(f"\n第{i+1}次迁移尝试:")
        success = await resident.migrate_to_new_town(map)
        if success:
            print(f"迁移成功！新位置: {resident.location}, 新城镇: {resident.town}")
        else:
            print("迁移失败！")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_resident_migration())