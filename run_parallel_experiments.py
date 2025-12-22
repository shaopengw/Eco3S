"""
并行运行多个实验的脚本
用法: python run_parallel_experiments.py [实验数量] [脚本路径]
示例: 
  python run_parallel_experiments.py 5
  python run_parallel_experiments.py 5 entrypoints/main_ablation.py
  python run_parallel_experiments.py 5 entrypoints/main_info_propagation.py
  python run_parallel_experiments.py 3 entrypoints/main_climate_migration_sim.py
  python run_parallel_experiments.py 2 entrypoints/main_financial_herd_behavior_sim.py
"""
import subprocess
import sys

def run_parallel_experiments(num_experiments=5, script_path="entrypoints/main.py"):
    """
    启动多个并行实验进程
    :param num_experiments: 要运行的实验数量
    :param script_path: 要运行的脚本路径
    """
    processes = []
    
    print(f"正在启动 {num_experiments} 个并行实验...")
    print(f"运行脚本: {script_path}")
    print()
    
    for i in range(num_experiments):
        # 每个实验在独立的进程中运行
        cmd = [sys.executable, script_path]
        
        # 启动子进程（不重定向输出，让错误信息可见）
        process = subprocess.Popen(cmd)
        processes.append(process)
        print(f"实验 {i+1} 已启动 (PID: {process.pid})")
    
    print(f"\n所有 {num_experiments} 个实验已启动，正在运行中...")
    print("按 Ctrl+C 可以终止所有实验")
    
    # 等待所有进程完成
    try:
        for i, process in enumerate(processes):
            print(f"\n等待实验 {i+1} 完成...")
            returncode = process.wait()
            if returncode == 0:
                print(f"实验 {i+1} 已成功完成")
            else:
                print(f"实验 {i+1} 异常退出 (返回码: {returncode})")
    except KeyboardInterrupt:
        print("\n\n收到中断信号，正在终止所有实验...")
        for process in processes:
            process.terminate()
        print("所有实验已终止")

if __name__ == "__main__":
    # 从命令行参数获取实验数量和脚本路径
    num_exp = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    script_path = sys.argv[2] if len(sys.argv) > 2 else "entrypoints/main.py"
    run_parallel_experiments(num_exp, script_path)
