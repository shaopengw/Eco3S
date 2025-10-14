import os
from flask import Flask, jsonify, request, send_from_directory
import yaml
import subprocess
import threading
import queue
import uuid
import json
import sys
import os
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime
from visualization.plot_results import plot_all_results
from utils.simulation_context import SimulationContext

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

CONFIG_PATHS = {
    'default': 'config/simulation_config.yaml',
    'TEOG': 'config_TEOG/simulation_config.yaml',
    'info_propagation': 'config_info_propagation/simulation_config.yaml'
}

COMMANDS = {
    'default': 'python main.py --config_path config/simulation_config.yaml',
    'TEOG': 'python main_TEOG.py --config_path config_TEOG/simulation_config.yaml',
    'info_propagation': 'python main_info_propagation.py --config_path config_info_propagation/simulation_config.yaml'
}

# 存储运行中的模拟进程信息
running_simulations = {}

def load_config(config_type):
    path = os.path.join(BASE_DIR, '..', CONFIG_PATHS[config_type])
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(config_type, config_data):
    path = os.path.join(BASE_DIR, '..', CONFIG_PATHS[config_type])
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config_data, f, allow_unicode=True)

def run_process(command, process_id, config_type):
    simulation_info = running_simulations[process_id]
    output_queue = simulation_info['output_queue']
    
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=os.path.join(BASE_DIR, '..'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        simulation_info['process'] = process
        
        # 读取输出流
        def read_output(pipe, prefix=''):
            for line in iter(pipe.readline, ''):
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                output_queue.put(f'[{timestamp}] {prefix}{line}')
            pipe.close()
        
        # 创建线程读取stdout和stderr
        stdout_thread = threading.Thread(target=read_output, args=(process.stdout,))
        stderr_thread = threading.Thread(target=read_output, args=(process.stderr, 'ERROR: '))
        
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        # 等待进程完成
        process.wait()
        
        # 等待输出线程完成
        stdout_thread.join()
        stderr_thread.join()
        
        # 更新状态
        if process.returncode == 0:
            simulation_info['status'] = 'completed'
            # 获取已生成的图表路径
            try:
                # 从 SimulationContext 获取实验类型
                experiment_type = SimulationContext.get_simulation_type()
    
                # 构建基础历史目录路径
                base_experiment_history_dir = os.path.join(SimulationContext._base_history_dir, experiment_type)
    
                plot_results_dir = None
                if os.path.exists(base_experiment_history_dir):
                    # 获取所有子目录
                    test_dirs = [d for d in os.listdir(base_experiment_history_dir)
                               if os.path.isdir(os.path.join(base_experiment_history_dir, d)) and d != 'analysis_results']
                    test_dirs.sort() # 按时间戳排序，最新的在最后
                    
                    if test_dirs:
                        latest_test_dir_name = test_dirs[-1] # 获取最新的子目录名称
                        latest_test_dir_path = os.path.join(base_experiment_history_dir, latest_test_dir_name)
                        plot_results_dir = latest_test_dir_path
                    else:
                        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 未找到 {experiment_type} 类型的任何测试目录')
                else:
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 实验类型 {experiment_type} 的历史目录不存在')
    
    
                if plot_results_dir and os.path.exists(plot_results_dir):
                    # 获取所有图片文件
                    plot_results_dir = os.path.join(plot_results_dir, 'plot_results').replace('\\', '/')
                    plot_files = [f for f in os.listdir(plot_results_dir) if f.endswith('.png')]
                    
                    plot_paths = [os.path.join('history', experiment_type, latest_test_dir_name, 'plot_results', f).replace('\\', '/') for f in plot_files]
                    simulation_info['plot_paths'] = plot_paths
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 在{plot_results_dir}目录下找到 {len(plot_paths)} 个结果图表')
                elif plot_results_dir:
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 图表目录 {plot_results_dir} 不存在')
                else:
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 未能确定图表目录')
            except Exception as e:
                output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 获取图表路径时出错: {str(e)}')
                print(f"Error getting plot paths: {str(e)}") # 调试信息
        else:
            simulation_info['status'] = 'error'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 进程退出代码: {process.returncode}')
            
    except Exception as e:
        simulation_info['status'] = 'error'
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误: {str(e)}')

@app.route('/config/<config_type>', methods=['GET'])
def get_config(config_type):
    if config_type not in CONFIG_PATHS:
        return jsonify({'error': 'Invalid config type'}), 404
    return jsonify(load_config(config_type))

@app.route('/config/<config_type>', methods=['POST'])
def update_config(config_type):
    if config_type not in CONFIG_PATHS:
        return jsonify({'error': 'Invalid config type'}), 404
    
    config_data = request.json
    save_config(config_type, config_data)
    return jsonify({'message': 'Configuration updated successfully'})

@app.route('/run/<config_type>')
def run_simulation(config_type):
    if config_type not in COMMANDS:
        return jsonify({'error': 'Invalid config type'}), 404

    command = COMMANDS[config_type]
    process_id = str(uuid.uuid4())
    
    # 初始化模拟信息
    running_simulations[process_id] = {
        'status': 'running',
        'output_queue': queue.Queue(),
        'process': None,
        'start_time': datetime.now(),
        'plot_paths': [],
        'config_type': config_type  # 添加 config_type
    }

    # 设置SimulationContext
    SimulationContext.set_simulation_type(config_type)
    SimulationContext.set_simulation_name(running_simulations[process_id]['start_time'].strftime("%Y%m%d_%H%M%S"))
    
    # 在新线程中启动模拟
    thread = threading.Thread(target=run_process, args=(command, process_id, config_type))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'process_id': process_id,
        'status': 'running',
        'message': '模拟已启动'
    })

@app.route('/simulation_status/<process_id>')
def simulation_status(process_id):
    if process_id not in running_simulations:
        return jsonify({'status': 'error', 'output': '模拟进程不存在'})
    
    simulation_info = running_simulations[process_id]
    output = []
    
    # 获取所有可用的输出并清空队列
    while not simulation_info['output_queue'].empty():
        try:
            line = simulation_info['output_queue'].get_nowait()
            output.append(line)
        except queue.Empty:
            break
    
    # 如果模拟已完成，清理资源
    if simulation_info['status'] in ['completed', 'error']:
        if simulation_info['process'] is not None:
            simulation_info['process'].stdout.close()
            simulation_info['process'].stderr.close()
    
    # 尝试读取 running_data 文件
    running_data = {}
    try:
        base_history_dir = os.path.join(BASE_DIR, '..', 'history', simulation_info.get('config_type', ''))
        
        if os.path.exists(base_history_dir):
            simulation_folders = [f for f in os.listdir(base_history_dir) if os.path.isdir(os.path.join(base_history_dir, f)) and f != 'analysis_results']
            if simulation_folders:
                latest_folder = max(simulation_folders)
                latest_folder_path = os.path.join(base_history_dir, latest_folder)
                for filename in os.listdir(latest_folder_path):
                    if filename.startswith('running_data') and (filename.endswith('.json') or filename.endswith('.csv')):
                        file_path = os.path.join(latest_folder_path, filename)
                        print(f"找到数据文件: {file_path}")
                        
                        if filename.endswith('.json'):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data_list = json.load(f)
                                if isinstance(data_list, list):
                                    running_data = {
                                        'years': [],
                                        'rebellions': [],
                                        'unemployment_rate': [],
                                        'population': [],
                                        'government_budget': [],
                                        'rebellion_strength': [],
                                        'average_satisfaction': [],
                                        'tax_rate': [],
                                        'river_navigability': [],
                                        'gdp': [],
                                        'urban_scale': []
                                    }
                                    
                                    for data in data_list:
                                        year = data.get('year') or data.get('time')
                                        if year is not None:
                                            running_data['years'].append(year)
                                            for key in running_data.keys():
                                                if key != 'years' and key in data:
                                                    running_data[key].append(data[key])
                                                elif key != 'years':
                                                    running_data[key].append(None)
                        else:  # CSV 文件
                            df = pd.read_csv(file_path)
                            running_data = {
                                'years': df['year'].tolist() if 'year' in df.columns else df['time'].tolist() if 'time' in df.columns else [],
                            }
                            for col in df.columns:
                                if col not in ['year', 'time']:
                                    running_data[col] = df[col].tolist()
                        break
        else:
            print(f"未找到模拟目录: {base_history_dir}")
    except Exception as e:
        print(f"读取running_data文件失败: {str(e)}")
    
    return jsonify({
        'status': simulation_info['status'],
        'output': '\n'.join(output),
        'plot_paths': simulation_info.get('plot_paths', []),
        'running_data': running_data
    })

@app.route('/description/<config_type>')
def get_description(config_type):
    if config_type not in CONFIG_PATHS:
        return jsonify({'error': 'Invalid config type'}), 404
    
    description_path = os.path.join(
        BASE_DIR,
        '..',
        os.path.dirname(CONFIG_PATHS[config_type]),
        'description.md'
    )
    
    try:
        with open(description_path, 'r', encoding='utf-8') as f:
            description = f.read()
        return jsonify({'description': description})
    except FileNotFoundError:
        return jsonify({'description': '暂无描述'})

@app.route('/history/<config_type>')
def get_history(config_type):
    SimulationContext.set_simulation_type(config_type)
    base_history_dir = os.path.join(BASE_DIR, '..', SimulationContext.get_current_simulation_dir())

    logs = []
    plots = []

    if os.path.exists(base_history_dir):
        for timestamp_dir_name in os.listdir(base_history_dir):
            timestamp_dir_path = os.path.join(base_history_dir, timestamp_dir_name)
            if os.path.isdir(timestamp_dir_path):
                # 查找日志文件
                for f in os.listdir(timestamp_dir_path):
                    if f.endswith('.log'):
                        logs.append({
                            'name': f,
                            'path': os.path.join('history', config_type, timestamp_dir_name, f).replace('\\', '/')
                        })
                
                # 查找图表文件
                plot_results_dir = os.path.join(timestamp_dir_path, 'plot_results')
                if os.path.exists(plot_results_dir):
                    for f in os.listdir(plot_results_dir):
                        if f.endswith('.png'):
                            plots.append({
                                'name': f,
                                'path': os.path.join('history', config_type, timestamp_dir_name, 'plot_results', f).replace('\\', '/')
                            })
    
    return jsonify({'logs': logs, 'plots': plots})

@app.route('/history/<path:filename>')
def serve_history_files(filename):
    project_root = os.path.abspath(os.path.join(BASE_DIR, '..'))
    full_path = os.path.join(project_root, 'history', filename)
    print(f"Attempting to serve history file: {full_path}")
    if os.path.exists(full_path):
        return send_from_directory(os.path.join(project_root, 'history'), filename)
    else:
        return jsonify({'error': f'File not found: {filename}', 'searched_path': full_path}), 404

@app.route('/log/<path:log_path>')
def get_log_content(log_path):
    full_path = os.path.join(BASE_DIR, '..', log_path)
    if not os.path.exists(full_path):
        return jsonify({'error': 'Log file not found'}), 404
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_data():
    try:
        data = request.json
        config_type = data.get('type')
        if not config_type:
            return jsonify({'error': '必须提供模拟类型'}), 400

        # 构建分析命令
        cmd = ['python', 'src/analyzer/simulation_analyzer.py', '--type', config_type]
        
        # 添加可选参数
        if 'p' in data:
            cmd.extend(['--p', str(data['p'])])
        if 'y' in data:
            cmd.extend(['--y', str(data['y'])])

        # 设置工作目录为项目根目录
        working_dir = os.path.join(BASE_DIR, '..')
        
        # 运行分析器
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        if result.returncode != 0:
            return jsonify({
                'error': f'分析失败: {result.stderr}'
            }), 500

        # 获取分析报告
        report = result.stdout

        # 获取最新生成的图表
        analysis_dir = os.path.join(working_dir, 'history', config_type, 'analysis_results')
        plots = []
        if os.path.exists(analysis_dir):
            # 获取所有png文件及其修改时间
            png_files = [(f, os.path.getmtime(os.path.join(analysis_dir, f))) 
                        for f in os.listdir(analysis_dir) if f.endswith('.png')]
            
            if png_files:
                # 按修改时间排序，获取最新的文件
                png_files.sort(key=lambda x: x[1], reverse=True)
                latest_files = []
                latest_time = png_files[0][1]
                
                # 获取所有最新时间戳的文件（同一批次生成的文件）
                for f, mtime in png_files:
                    if abs(mtime - latest_time) < 5:  # 5秒内的文件视为同一批次
                        plot_path = os.path.join('history', config_type, 'analysis_results', f).replace('\\', '/')
                        latest_files.append({
                            'name': f,
                            'path': plot_path
                        })
                plots = latest_files

        return jsonify({
            'report': report,
            'plots': plots
        })

    except Exception as e:
        return jsonify({
            'error': f'分析过程出错: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)