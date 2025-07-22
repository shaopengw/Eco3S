# 测试文件
import asyncio
from src.agents.shared_imports import *

async def test_model_manager_conversation():
    """测试ModelManager与大模型的对话功能"""
    

    
    #创建BaseAgent实例用于对话
    agent = BaseAgent(agent_id="test_agent", group_type="test_group",window_size=3)
    print(f"BaseAgent初始化成功，使用模型: {agent.model_type}")
    
    # 4. 测试对话

    test_prompts = [
        "你是一个清代普通无业游民，你积极、乐观，收入为0两，生活极度困难，健康，目前对政府怨气深重，斥其昏庸无道。你听说了一条信息：'我要加入叛军。'\n现在你在和其他老百姓聊天，根据这句话发表一些看法，注意考虑你的性格和处境,要简短，口语化。"
    ]

    for prompt in test_prompts:
        response = await agent.generate_llm_response(prompt)
        print(f"AI回复: {response}")
    
    print("\n测试完成")

if __name__ == "__main__":
    asyncio.run(test_model_manager_conversation())
