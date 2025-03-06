import asyncio
from src.environment.map import Map
from src.environment.job_market import JobMarket
from src.agents.government_agent_generator import (generate_government_agents)
from src.agents.government import Government

async def main():
    # 创建地图对象
    my_map = Map(size=100)

    # 创建就业市场对象
    job_market = JobMarket()

    # 创建政府对象
    government = Government(map=my_map, job_market=job_market, initial_budget=10000, time=1650)

    # 生成政府官员
    agent_graph = await generate_government_agents(
        government_info_path="experiment_dataset/government_data/official_data.json",
        job_market=job_market,
        government=government,
        model_type="gpt-3.5-turbo"
    )

    # 打印生成的官员图
    for official_id, official in agent_graph.items():
        print(f"官员 ID: {official_id}, 类型: {official.__class__.__name__}")

if __name__ == "__main__":
    asyncio.run(main())