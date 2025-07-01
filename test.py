# 测试文件
import asyncio
from src.agents.shared_imports import *

async def test_model_manager_conversation():
    """测试ModelManager与大模型的对话功能"""
    

    
    #创建BaseAgent实例用于对话
    agent = BaseAgent(agent_id="test_agent", group_type="test_group")
    print(f"BaseAgent初始化成功，使用模型: {agent.model_type}")
    
    # 4. 测试对话

    test_prompts = [
        "[{'role': 'user', 'content': '我的意见：建议调整河运比例至0.9，海运比例至0.1，以提高就业机会和支出节省。同时调整税率至15%，以增加国库收入用于维护支出和军事拨款。'}, {'role': 'user', 'content': '时间: 1651\n决策内容: {\"increase_employment\": 2, \"transport_ratio\": 0.9, \"maintenance_investment\": 2, \"military_support\": 3, \"tax_adjustment\": 0.025}\n执行结果:\n- GDP变化率: 0.00%\n- 政府预算变化率: -95.58%\n- 叛军力量变化率: 0.00%\n- 平均满意度变化: 0.00%\n- 失业率变化: 0.00%\n- 叛乱次数: 0'}, {'role': 'user', 'content': '我的意见：建议调整税率至20%，增加国库收入，以支持维护支出和军事拨款，同时保持河运比例为0.9，以提高就业机会和节省支出。'}, {'role': 'user', 'content': '你是清代普通政府官员，用一句话总结这几年的x'd、产生的效果，以及从中得到的经验教训。\n'}]"
    ]

    for prompt in test_prompts:
        response = await agent.generate_llm_response(prompt)
        print(f"AI回复: {response}")
    
    print("\n测试完成")

if __name__ == "__main__":
    asyncio.run(test_model_manager_conversation())
