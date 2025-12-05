from src.agents.shared_imports import *
from src.agents.sim_architect import SimArchitectAgent
from src.agents.code_architect import CodeArchitectAgent
from src.agents.research_analyst import ResearchAnalystAgent

async def main():

    coder = CodeArchitectAgent(
        agent_id='code_architect_001',
        simulator_output_dir="src\\simulation",
        main_output_dir="entrypoints",
        docs_dir="",
        config_dir="config\\extreme_climate_canal_abandonment",
        config_template_dir="config\\template",
        simulation_name="extreme_climate_canal_abandonment",
        simulation_type="decision"
    )
    modification_results = await coder.modify_file_sequentially(
        "history\\climate_migration_sim\\diagnosis_result.json",
        "config\\extreme_climate_canal_abandonment",
        design_doc="design_doc"
        )            
    if modification_results:
        print(f"✓ 已完成 {len(modification_results)} 个文件的修改")
        return True
    else:
        print("未成功修改任何文件")
        return False
    # fixed = await coder.fix_runtime_errors(
    #     error_message=error_message,
    #     error_traceback=f"",
    #     main_file_path=main_file_path,
    #     simulator_file_path=simulator_file_path,
    #     max_attempts=3
    # )                       
    # if fixed:
    #     self.logger.info("✓ 编码师已完成修复，准备重新运行...")
    #     return True
    # else:
    #     self.logger.error("❌ 编码师修复失败")
    #     return False

if __name__ == '__main__':
    asyncio.run(main())