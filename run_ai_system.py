"""
AI驱动的多智能体模拟系统 - 主入口
运行命令: python run_ai_system.py
"""

import os
import sys
import asyncio

# 添加项目路径
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'aide'))

from src.agents.project_master import ProjectMasterAgent


async def main():
    """主函数"""
    print("=" * 80)
    print("AI驱动的多智能体模拟系统")
    print("=" * 80)
    print()
    
    # 1. 选择运行模式
    print("请选择运行模式：")
    print("  1. 自动模式 - 一次性完成所有步骤")
    print("  2. 交互模式 - 每个阶段等待反馈，支持重新生成")
    print()
    mode_input = input("请输入选项 (1/2，默认为1): ").strip()
    
    interactive_mode = (mode_input == '2')
    
    if interactive_mode:
        print("\n✓ 已选择交互模式")
    else:
        print("\n✓ 已选择自动模式")
    print()
    
    # 2. 获取用户需求
    print("请输入您的模拟实验需求（输入完成后直接按回车）：")
    print("示例：我想研究气候变化对居民迁移的影响，需要模拟100个居民在不同气候条件下的行为")
    print()
    
    requirement_text = input("需求: ").strip()
    
    if not requirement_text:
        print("\n使用默认示例需求...")
        requirement_text = "我想研究气候变化对居民迁移的影响，需要模拟100个居民在不同气候条件下的行为，观察他们在极端天气下的决策"
    
    print(f"\n收到需求：\n{requirement_text}")
    print()
    
    # 3. 初始化项目管理师
    print("初始化项目管理师...")
    workspace_dir = os.path.join(os.path.dirname(__file__), 'history')
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    config_template_dir = os.path.join(os.path.dirname(__file__), 'config', 'template')
    
    # 确保目录存在
    os.makedirs(workspace_dir, exist_ok=True)
    
    project_master = ProjectMasterAgent(
        agent_id='project_master_001',
        workspace_dir=workspace_dir,
        docs_dir=docs_dir,
        config_template_dir=config_template_dir
    )
    
    print("项目管理师已初始化")
    print()
    
    # 4. 根据模式运行工作流
    try:
        if interactive_mode:
            # 交互式工作流
            print("开始执行交互式工作流...")
            print("每个阶段完成后，您可以审查结果并提供反馈")
            print()
            
            results = await project_master.run_interactive_workflow(requirement_text)
            
            # 显示交互式结果
            print()
            print("=" * 80)
            if results['status'] == 'completed':
                print("✅ 交互式工作流执行完成！")
                print("=" * 80)
                print()
                print(f"📁 项目目录: {results['project_dir']}")
                print(f"📂 配置目录: {results['config_dir']}")
                print()
                print(f"📊 设计阶段版本数: {len(results['history']['design'])}")
                print(f"📊 编码阶段版本数: {len(results['history']['coding'])}")
                print()
                
                if results.get('coding_results'):
                    coding = results['coding_results']
                    print("生成的文件:")
                    if coding.get('simulator_files'):
                        print(f"  💻 模拟器: {coding['simulator_files'][0]}")
                    if coding.get('main_files'):
                        print(f"  🚀 入口文件: {coding['main_files'][0]}")
                    if coding.get('config_files'):
                        print(f"  ⚙️  配置文件: {len(coding['config_files'])}个")
                    if coding.get('prompt_files'):
                        print(f"  📝 提示词文件: {len(coding['prompt_files'])}个")
            elif results['status'] == 'terminated':
                print(f"⚠️  流程在 {results['phase']} 阶段被用户终止")
                print("=" * 80)
            else:
                print(f"状态: {results['status']}")
                print("=" * 80)
        else:
            # 自动工作流
            print("开始执行自动化工作流...")
            print("这可能需要几分钟时间，请耐心等待...")
            print()
            
            results = await project_master.run_full_workflow(
                requirement_text=requirement_text,
                max_iterations=2  # 最多2轮迭代优化
            )
            
            # 显示自动模式结果
            print()
            print("=" * 80)
            
            if results.get('status') == 'failed':
                print("❌ 工作流执行失败")
                print("=" * 80)
                print()
                print(f"失败原因: {results.get('reason', '未知')}")
                print(f"📁 项目目录: {results['project_dir']}")
                print()
                print("生成的文件（部分）：")
                if results.get('coding_results', {}).get('main_files'):
                    print(f"  🚀 入口文件: {results['coding_results']['main_files'][0]}")
                if results.get('coding_results', {}).get('simulator_files'):
                    print(f"  💻 模拟器代码: {results['coding_results']['simulator_files'][0]}")
                print()
                print("请检查日志文件获取详细错误信息")
                print("=" * 80)
            else:
                print("✅ 工作流执行完成！")
                print("=" * 80)
                print()
                print(f"📁 项目实验目录: {results['project_dir']}")
                
                # 获取项目根目录
                project_root = os.path.dirname(__file__)
                
                # 获取模拟名称
                simulation_name = os.path.basename(results['project_dir'])
                
                # 配置文件夹
                config_dir = os.path.join(project_root, 'config', simulation_name)
                
                print(f"📂 配置文件目录: {config_dir}")
                print(f"   - description.md")
                print(f"   - simulation_config.yaml")
                print(f"   - jobs_config.yaml")
                print(f"   - resident_actions.yaml")
                print(f"   - residents_prompts.yaml")
                print(f"   - 等其他配置文件...")
                print()
                
                if results['coding_results'].get('main_files'):
                    print(f"🚀 入口文件: {results['coding_results']['main_files'][0]}")
                
                if results['coding_results'].get('simulator_files'):
                    print(f"💻 模拟器代码: {results['coding_results']['simulator_files'][0]}")
                
                if results.get('simulation_results'):
                    print(f"� 模拟结果: {results['simulation_results']}")
                
                print()
                print("=" * 80)
                print("文件结构说明：")
                print(f"1. 配置文件: config/{simulation_name}/")
                print(f"2. 入口文件: entrypoints/main_{simulation_name}.py")
                print(f"3. 模拟器: src/simulation/simulator_{simulation_name}.py")
                print(f"4. 实验数据: experiment_dataset/{simulation_name}/")
                print("=" * 80)
                print()
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ 执行过程中出现错误")
        print("=" * 80)
        print(f"错误信息: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
