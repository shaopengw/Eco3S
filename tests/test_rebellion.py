import asyncio
from src.environment.map import Map
from src.environment.job_market import JobMarket
from src.agents.rebellion_agent_generator import (generate_rebellion_agents)
from src.agents.rebels import Rebellion

async def main():


    rebellion = Rebellion(initial_strength=100, initial_resources=500, initial_support=50)
    agent_graph = await generate_rebellion_agents(
        rebellion_info_path="experiment_dataset/rebellion_data/rebellion_data.json",
        rebellion=rebellion,
        model_type="gpt-3.5-turbo"
    )
    # 打印生成的官员图
    for official_id, official in agent_graph.items():
        print(f"叛军 ID: {official_id}, 类型: {official.__class__.__name__}")

if __name__ == "__main__":
    asyncio.run(main())