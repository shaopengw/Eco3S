import os
from flask import Flask, jsonify, request, send_from_directory
import yaml
import subprocess
import threading
import queue
import uuid
import json
from datetime import datetime
from visualization.plot_results import plot_all_results

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
                plot_results_dir = os.path.join(BASE_DIR, '..', 'experiment_dataset', 'plot_results')
                if os.path.exists(plot_results_dir):
                    # 获取最新生成的图片文件
                    plot_files = [f for f in os.listdir(plot_results_dir) 
                                if f.endswith('.png') and 
                                os.path.getmtime(os.path.join(plot_results_dir, f)) >= simulation_info['start_time'].timestamp()]
                    plot_paths = [os.path.join('experiment_dataset', 'plot_results', f) for f in plot_files]
                    simulation_info['plot_paths'] = plot_paths
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 找到 {len(plot_paths)} 个结果图表')
                    print(f"图表路径：{plot_paths}")  # 调试信息
            except Exception as e:
                output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 获取图表路径时出错: {str(e)}')
                print(f"Error getting plot paths: {str(e)}")  # 调试信息
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
        'plot_paths': []
    }
    
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
    
    return jsonify({
        'status': simulation_info['status'],
        'output': '\n'.join(output),
        'plot_paths': simulation_info.get('plot_paths', [])
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

@app.route('/api/experiment_dataset/plot_results/<path:filename>')
def serve_plot_results(filename):
    plot_results_dir = os.path.join(BASE_DIR, '..', 'experiment_dataset', 'plot_results')
    file_path = os.path.join(plot_results_dir, filename)
    print(f"Attempting to serve file: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    if os.path.exists(file_path):
        return send_from_directory(plot_results_dir, filename)
    else:
        return jsonify({'error': f'File not found: {filename}', 'searched_path': file_path}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)