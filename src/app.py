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

# 已知模拟的专用入口映射，其他统一使用模板入口
SPECIAL_ENTRYPOINTS = {
    'default': 'entrypoints/main.py',
    'TEOG': 'entrypoints/main_TEOG.py',
    'info_propagation': 'entrypoints/main_info_propagation.py',
}

def get_config_path(config_type: str):
    """返回配置文件的绝对路径，存在则返回路径，不存在返回None"""
    rel_path = os.path.join('config', config_type, 'simulation_config.yaml')
    path = os.path.join(BASE_DIR, '..', rel_path)
    if os.path.exists(path):
        return path
    return None

def get_description_path(config_type: str):
    """返回描述文件的绝对路径，存在则返回路径，不存在返回None"""
    rel_dir = os.path.join('config', config_type)
    path = os.path.join(BASE_DIR, '..', rel_dir, 'description.md')
    if os.path.exists(path):
        return path
    return None

def get_command_for_simulation(config_type: str):
    """根据模拟类型返回运行命令。已知模拟使用专用入口，其他使用模板入口。"""
    entry_script = SPECIAL_ENTRYPOINTS.get(config_type, 'entrypoints/main_template.py')
    rel_config_path = os.path.join('config', config_type, 'simulation_config.yaml')
    command = f'python {entry_script} --config_path {rel_config_path}'
    return command

# 存储运行中的模拟进程信息
running_simulations = {}

def load_config(config_type):
    path = get_config_path(config_type)
    if not path:
        raise FileNotFoundError(f'配置文件不存在: config/{config_type}/simulation_config.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(config_type, config_data):
    path = get_config_path(config_type)
    if not path:
        # 若不存在则尝试创建目录
        dir_path = os.path.join(BASE_DIR, '..', 'config', config_type)
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, 'simulation_config.yaml')
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
        stderr_thread = threading.Thread(target=read_output, args=(process.stderr,))
        
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
                    
                    if test_dirs:
                        # 按目录创建时间排序，最新的在最后
                        test_dirs.sort(key=lambda d: os.path.getctime(os.path.join(base_experiment_history_dir, d)))
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
    if not get_config_path(config_type):
        return jsonify({'error': 'Invalid config type or config not found'}), 404
    return jsonify(load_config(config_type))

@app.route('/config/<config_type>', methods=['POST'])
def update_config(config_type):
    config_data = request.json
    try:
        save_config(config_type, config_data)
        return jsonify({'message': 'Configuration updated successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to save config: {str(e)}'}), 500

@app.route('/run/<config_type>')
def run_simulation(config_type):
    if not get_config_path(config_type):
        return jsonify({'error': 'Invalid config type or config not found'}), 404

    command = get_command_for_simulation(config_type)
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
                # 按目录创建时间排序，最新的在最后
                simulation_folders.sort(key=lambda d: os.path.getctime(os.path.join(base_history_dir, d)))
                latest_folder = simulation_folders[-1]
                latest_folder_path = os.path.join(base_history_dir, latest_folder)
                
                start_time_str = simulation_info.get('start_time')
                start_timestamp = None
                if start_time_str:
                    try:
                        from datetime import datetime
                        if isinstance(start_time_str, datetime):
                            start_timestamp = start_time_str.timestamp()
                        else:
                            start_timestamp = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').timestamp()
                    except ValueError:
                        print(f"警告: 无法解析 simulation_info['start_time']: {start_time_str}")

                for filename in os.listdir(latest_folder_path):
                    if filename.startswith('running_data') and (filename.endswith('.json') or filename.endswith('.csv')):
                        file_path = os.path.join(latest_folder_path, filename)
                        
                        if start_timestamp:
                            file_creation_time = os.path.getctime(file_path)
                            if file_creation_time < start_timestamp:
                                print(f"跳过旧数据文件: {file_path} (创建时间: {datetime.fromtimestamp(file_creation_time)}, 模拟开始时间: {start_time_str})")
                                continue

                        print(f"找到数据文件: {file_path}")
                        
                        if filename.endswith('.csv'):
                            df = pd.read_csv(file_path)
                            
                            # 支持多种时间列命名
                            time_col = None
                            for col_name in ['year', 'years', 'time', 'period', 'periods', 'step', 'steps', 'round', 'iteration', 'tick']:
                                if col_name in df.columns:
                                    time_col = col_name
                                    break
                            
                            # 如果没找到时间列，使用第一列
                            if time_col is None and len(df.columns) > 0:
                                time_col = df.columns[0]
                            
                            running_data = {
                                'years': df[time_col].tolist() if time_col else [],
                            }
                            
                            # 添加其他列数据
                            for col in df.columns:
                                if col != time_col:
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

@app.route('/resident_states/<process_id>')
def get_resident_states(process_id):
    if process_id not in running_simulations:
        return jsonify({'error': '模拟进程不存在'}), 404

    simulation_info = running_simulations[process_id]
    config_type = simulation_info.get('config_type', '')

    residents_data = []
    try:
        base_history_dir = os.path.join(BASE_DIR, '..', 'history', config_type)

        if os.path.exists(base_history_dir):
            simulation_folders = [f for f in os.listdir(base_history_dir) if os.path.isdir(os.path.join(base_history_dir, f)) and f != 'analysis_results']
            if simulation_folders:
                simulation_folders.sort(key=lambda d: os.path.getctime(os.path.join(base_history_dir, d)))
                latest_folder = simulation_folders[-1]
                latest_folder_path = os.path.join(base_history_dir, latest_folder)

                residents_file = os.path.join(latest_folder_path, 'residents_data.json')
                if os.path.exists(residents_file):
                    with open(residents_file, 'r', encoding='utf-8') as f:
                        residents_data = json.load(f)
    except Exception as e:
        print(f"读取居民位置数据失败: {str(e)}")

    return jsonify({
        'status': simulation_info['status'],
        'residents': residents_data
    })

@app.route('/description/<config_type>')
def get_description(config_type):
    desc_path = get_description_path(config_type)
    if not desc_path:
        return jsonify({'description': '暂无描述'})
    try:
        with open(desc_path, 'r', encoding='utf-8') as f:
            description = f.read()
        return jsonify({'description': description})
    except Exception as e:
        return jsonify({'error': f'读取描述失败: {str(e)}'}), 500

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

@app.route('/towns/<config_type>')
def get_towns_data(config_type):
    try:
        config_dir = os.path.join(BASE_DIR, '..', 'config', config_type)
        towns_file = os.path.join(config_dir, 'towns_data.json')
        if not os.path.exists(towns_file):
            # Fallback to default if not found
            towns_file = os.path.join(BASE_DIR, '..', 'config', 'default', 'towns_data.json')
            
        if os.path.exists(towns_file):
            with open(towns_file, 'r', encoding='utf-8') as f:
                towns_data = json.load(f)
            return jsonify(towns_data)
        else:
            return jsonify({'error': 'Towns data not found'}), 404
    except Exception as e:
        return jsonify({'error': f'读取城镇数据失败: {str(e)}'}), 500

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

        # 获取最新生成的图表（从最新的时间戳子文件夹中）
        analysis_base_dir = os.path.join(working_dir, 'history', config_type, 'analysis_results')
        plots = []
        if os.path.exists(analysis_base_dir):
            # 获取所有时间戳子文件夹
            timestamp_dirs = [d for d in os.listdir(analysis_base_dir) 
                            if os.path.isdir(os.path.join(analysis_base_dir, d))]
            
            if timestamp_dirs:
                # 按目录创建时间排序，获取最新的
                timestamp_dirs.sort(key=lambda d: os.path.getctime(os.path.join(analysis_base_dir, d)))
                latest_dir = timestamp_dirs[-1]
                analysis_dir = os.path.join(analysis_base_dir, latest_dir)
                
                # 获取该文件夹中的所有png文件
                if os.path.exists(analysis_dir):
                    png_files = [f for f in os.listdir(analysis_dir) if f.endswith('.png')]
                    for f in png_files:
                        plot_path = os.path.join('history', config_type, 'analysis_results', latest_dir, f).replace('\\', '/')
                        plots.append({
                            'name': f,
                            'path': plot_path
                        })

        return jsonify({
            'report': report,
            'plots': plots
        })

    except Exception as e:
        return jsonify({
            'error': f'分析过程出错: {str(e)}'
        }), 500

# ============ AI设计编码系统API ============

# 存储AI系统运行状态
ai_system_sessions = {}

# 添加用户确认接口
@app.route('/ai_system/confirm/<session_id>', methods=['POST'])
def confirm_action(session_id):
    """处理用户确认"""
    try:
        if session_id not in ai_system_sessions:
            return jsonify({'error': '会话不存在'}), 404
        
        data = request.json
        session = ai_system_sessions[session_id]
        
        # 设置用户的确认响应
        confirmed = data.get('confirmed', False)
        session['user_confirmation'] = confirmed
        session['user_input'] = data.get('input', '')
        session['waiting_confirmation'] = False
        
        print(f"[确认] Session {session_id}: confirmed={confirmed}, input={data.get('input', '')}")
        
        return jsonify({'message': '确认已接收', 'confirmed': confirmed}), 200
        
    except Exception as e:
        print(f"[错误] 处理确认请求失败: {str(e)}")
        return jsonify({'error': f'处理确认失败: {str(e)}'}), 500

@app.route('/ai_system/parse_requirement', methods=['POST'])
def parse_requirement():
    """解析用户需求"""
    try:
        data = request.json
        requirement_text = data.get('requirement_text', '')
        
        if not requirement_text:
            return jsonify({'error': '需求文本不能为空'}), 400
        
        # 创建会话ID
        session_id = str(uuid.uuid4())
        
        # 初始化会话状态
        ai_system_sessions[session_id] = {
            'status': 'parsing',
            'requirement_text': requirement_text,
            'phase': 'parse',
            'output_queue': queue.Queue(),
            'start_time': datetime.now(),
            'project_master': None,
            'results': {},
            'waiting_confirmation': False,
            'confirmation_message': '',
            'confirmation_type': '',  # 'yes_no', 'input', 'choice'
            'confirmation_options': [],
            'user_confirmation': None,
            'user_input': ''
        }
        
        # 在后台线程中运行解析
        thread = threading.Thread(target=run_ai_system_parse, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'parsing',
            'message': '开始解析需求...'
        })
        
    except Exception as e:
        return jsonify({'error': f'解析需求失败: {str(e)}'}), 500

@app.route('/ai_system/run_design', methods=['POST'])
def run_design_phase():
    """运行设计阶段"""
    try:
        data = request.json
        session_id = data.get('session_id')
        user_feedback = data.get('user_feedback')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        session['status'] = 'designing'
        session['phase'] = 'design'
        session['user_feedback'] = user_feedback
        
        # 在后台线程中运行设计阶段
        thread = threading.Thread(target=run_ai_system_design, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'designing',
            'message': '开始设计阶段...'
        })
        
    except Exception as e:
        return jsonify({'error': f'运行设计阶段失败: {str(e)}'}), 500

@app.route('/ai_system/run_coding', methods=['POST'])
def run_coding_phase():
    """运行编码阶段"""
    try:
        data = request.json
        session_id = data.get('session_id')
        user_feedback = data.get('user_feedback')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        session['status'] = 'coding'
        session['phase'] = 'coding'
        session['user_feedback'] = user_feedback
        
        # 在后台线程中运行编码阶段
        thread = threading.Thread(target=run_ai_system_coding, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'coding',
            'message': '开始编码阶段...'
        })
        
    except Exception as e:
        return jsonify({'error': f'运行编码阶段失败: {str(e)}'}), 500

@app.route('/ai_system/run_simulation', methods=['POST'])
def run_ai_system_simulation():
    """运行模拟并评估"""
    try:
        data = request.json
        session_id = data.get('session_id')
        test_type = data.get('test_type', 'small')  # 'small' 或 'large'
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        session['status'] = 'running_simulation'
        session['phase'] = 'simulation'
        session['test_type'] = test_type
        
        # 在后台线程中运行模拟
        thread = threading.Thread(target=run_ai_system_full_simulation, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'running_simulation',
            'message': f'开始运行{"小规模" if test_type == "small" else "大规模"}测试...'
        })
        
    except Exception as e:
        return jsonify({'error': f'运行模拟失败: {str(e)}'}), 500

@app.route('/ai_system/mechanism_overview', methods=['POST'])
def get_mechanism_overview():
    """获取机制概览（用于机制调整对话的开始）"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        project_master = session.get('project_master')
        
        if not project_master:
            return jsonify({'error': '项目主管未初始化'}), 400
        
        # 获取编码结果
        coding_results = session.get('results', {}).get('coding_results')
        simulator_path = None
        main_path = None
        
        if coding_results:
            if coding_results.get('simulator_files'):
                simulator_path = coding_results['simulator_files'][0]
            if coding_results.get('main_files'):
                main_path = coding_results['main_files'][0]
        
        # 创建或获取 MechanismInterpreterAgent
        if not project_master.mechanism_interpreter:
            from src.agents.mechanism_interpreter import MechanismInterpreterAgent
            project_master.mechanism_interpreter = MechanismInterpreterAgent(
                agent_id='mechanism_interpreter_001',
                config_dir=project_master.current_config_dir,
                simulator_path=simulator_path,
                main_path=main_path
            )
        
        # 运行异步任务获取概览
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        overview = loop.run_until_complete(
            project_master.mechanism_interpreter.explain_mechanism()
        )
        
        # 初始化对话状态
        if 'mechanism_dialog' not in session:
            session['mechanism_dialog'] = {
                'history': [],
                'adjustments': []
            }
        
        return jsonify({
            'overview': overview,
            'message': '机制概览获取成功'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'获取机制概览失败: {str(e)}'}), 500

@app.route('/ai_system/mechanism_chat', methods=['POST'])
def mechanism_chat():
    """处理机制调整对话"""
    try:
        data = request.json
        session_id = data.get('session_id')
        message = data.get('message', '').strip()
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        if not message:
            return jsonify({'error': '消息不能为空'}), 400
        
        session = ai_system_sessions[session_id]
        project_master = session.get('project_master')
        
        if not project_master or not project_master.mechanism_interpreter:
            return jsonify({'error': '机制解释器未初始化'}), 400
        
        # 获取对话状态
        dialog_state = session.get('mechanism_dialog', {'history': [], 'adjustments': []})
        
        # 运行异步任务处理消息
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 识别意图
        intent_result = loop.run_until_complete(
            project_master.mechanism_interpreter.recognize_intent(message)
        )
        
        if not intent_result:
            return jsonify({
                'response': '抱歉，我没有理解您的意思。请尝试换个方式表达。',
                'intent': 'unknown'
            })
        
        intent = intent_result.get('intent')
        response_text = ''
        confirmed = False
        adjustment_description = None
        
        if intent == 'question':
            # 用户在提问
            answer = loop.run_until_complete(
                project_master.mechanism_interpreter.answer_question(
                    message, 
                    intent_result.get('required_files', [])
                )
            )
            response_text = answer
            
        elif intent == 'adjustment':
            # 用户想调整配置
            description = intent_result.get('description', message)
            response_text = f"我理解您的意思是: {description}\\n\\n这个需求已添加到调整列表中。"
            confirmed = True
            adjustment_description = description
            
            # 添加到调整列表
            dialog_state['adjustments'].append(description)
            
        elif intent == 'view_adjustments':
            # 用户想查看需求列表
            adjustments = dialog_state['adjustments']
            if adjustments:
                response_text = "【当前需求列表】:\\n\\n" + "\\n".join([f"{i+1}. {req}" for i, req in enumerate(adjustments)])
            else:
                response_text = "暂无需求"
        else:
            response_text = "抱歉，我没有理解您的意图。请尝试换个方式表达。"
        
        # 更新对话历史
        dialog_state['history'].append({'role': 'user', 'content': message})
        dialog_state['history'].append({'role': 'assistant', 'content': response_text})
        session['mechanism_dialog'] = dialog_state
        
        return jsonify({
            'response': response_text,
            'intent': intent,
            'confirmed': confirmed,
            'adjustment_description': adjustment_description
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'处理对话失败: {str(e)}'}), 500

@app.route('/ai_system/run_mechanism_adjust', methods=['POST'])
def run_mechanism_adjust():
    """运行机制调整会话（已弃用，保留用于兼容）"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        session['status'] = 'mechanism_adjusting'
        session['phase'] = 'mechanism_adjust'
        
        # 在后台线程中运行机制调整
        thread = threading.Thread(target=run_ai_system_mechanism_adjust, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'mechanism_adjusting',
            'message': '开始机制解释与调整会话...'
        })
        
    except Exception as e:
        return jsonify({'error': f'运行机制调整失败: {str(e)}'}), 500

@app.route('/ai_system/apply_optimization', methods=['POST'])
def apply_optimization():
    """应用评估优化调整"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        
        # 检查是否有诊断结果
        evaluation_results = session.get('results', {}).get('evaluation_results', {})
        diagnosis_path = evaluation_results.get('diagnosis_path')
        
        if not diagnosis_path:
            return jsonify({'error': '没有找到诊断结果'}), 400
        
        session['status'] = 'applying_optimization'
        
        # 在后台线程中应用优化
        thread = threading.Thread(target=run_ai_system_apply_optimization, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'applying_optimization',
            'message': '开始应用优化调整...'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'应用优化失败: {str(e)}'}), 500

@app.route('/ai_system/skip_optimization', methods=['POST'])
def skip_optimization():
    """跳过优化调整"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        output_queue = session['output_queue']
        
        # 记录跳过信息
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ℹ️  用户选择跳过优化调整')
        
        # 更新评估结果
        if 'evaluation_results' in session.get('results', {}):
            session['results']['evaluation_results']['waiting_user_confirmation'] = False
            session['results']['evaluation_results']['modification_results'] = None  # 标记为跳过
        
        # 标记为完成
        session['status'] = 'completed'
        
        output_queue.put(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 🎉 全流程完成（已跳过优化）')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}\n')
        
        return jsonify({
            'session_id': session_id,
            'status': 'completed',
            'message': '已跳过优化调整'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'应用优化失败: {str(e)}'}), 500

@app.route('/ai_system/apply_adjustments', methods=['POST'])
def apply_mechanism_adjustments():
    """应用机制调整"""
    try:
        data = request.json
        session_id = data.get('session_id')
        adjustments = data.get('adjustments', '')
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        session['status'] = 'applying_adjustments'
        session['adjustments_text'] = adjustments
        
        # 在后台线程中应用调整
        thread = threading.Thread(target=run_ai_system_apply_adjustments, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'applying_adjustments',
            'message': '开始应用机制调整...'
        })
        
    except Exception as e:
        return jsonify({'error': f'应用调整失败: {str(e)}'}), 500

@app.route('/ai_system/save_design_doc', methods=['POST'])
def save_design_doc():
    """保存设计文档"""
    try:
        data = request.json
        session_id = data.get('session_id')
        simulation_name = data.get('simulation_name')
        content = data.get('content')
        
        if not all([session_id, simulation_name, content]):
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 获取配置目录
        project_root = os.path.join(BASE_DIR, '..')
        config_dir = os.path.join(project_root, 'config', simulation_name)
        
        if not os.path.exists(config_dir):
            return jsonify({'error': '配置目录不存在'}), 404
        
        # 保存设计文档
        desc_path = os.path.join(config_dir, 'description.md')
        with open(desc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'status': 'success',
            'message': '设计文档已保存',
            'file_path': desc_path
        })
        
    except Exception as e:
        return jsonify({'error': f'保存设计文档失败: {str(e)}'}), 500

@app.route('/ai_system/status/<session_id>')
def get_ai_system_status(session_id):
    """获取AI系统状态"""
    if session_id not in ai_system_sessions:
        return jsonify({'status': 'error', 'error': '会话不存在'}), 404
    
    session = ai_system_sessions[session_id]
    output = []
    
    # 获取所有可用的输出
    while not session['output_queue'].empty():
        try:
            line = session['output_queue'].get_nowait()
            output.append(line)
        except queue.Empty:
            break
    
    response = {
        'status': session['status'],
        'phase': session['phase'],
        'output': '\n'.join(output),
        'results': session.get('results', {}),
        'waiting_confirmation': session.get('waiting_confirmation', False),
        'confirmation_message': session.get('confirmation_message', ''),
        'confirmation_type': session.get('confirmation_type', ''),
        'confirmation_options': session.get('confirmation_options', [])
    }
    
    # 如果是完成状态，添加额外信息
    if session['status'] in ['completed', 'error']:
        if 'project_dir' in session.get('results', {}):
            response['project_dir'] = session['results']['project_dir']
        if 'config_dir' in session.get('results', {}):
            response['config_dir'] = session['results']['config_dir']
        if 'simulation_name' in session.get('results', {}):
            response['simulation_name'] = session['results']['simulation_name']
    
    return jsonify(response)

@app.route('/ai_system/list_projects')
def list_projects():
    """列出所有AI生成的项目"""
    try:
        project_root = os.path.join(BASE_DIR, '..')
        config_base_dir = os.path.join(project_root, 'config')
        
        projects = []
        if os.path.exists(config_base_dir):
            for item in os.listdir(config_base_dir):
                item_path = os.path.join(config_base_dir, item)
                if os.path.isdir(item_path) and item != 'template':
                    # 读取description.md获取项目信息
                    desc_path = os.path.join(item_path, 'description.md')
                    description = ''
                    if os.path.exists(desc_path):
                        with open(desc_path, 'r', encoding='utf-8') as f:
                            description = f.read()[:200] + '...'
                    
                    projects.append({
                        'name': item,
                        'description': description,
                        'config_path': f'config/{item}',
                        'created_time': datetime.fromtimestamp(os.path.getctime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        return jsonify({'projects': projects})
        
    except Exception as e:
        return jsonify({'error': f'获取项目列表失败: {str(e)}'}), 500

# AI系统后台运行函数

class OutputCapture:
    """捕获print输出到队列"""
    def __init__(self, output_queue):
        self.output_queue = output_queue
        self.original_stdout = sys.stdout
        
    def write(self, text):
        if text and text.strip():
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.output_queue.put(f'[{timestamp}] {text.rstrip()}')
        # 同时输出到原始stdout
        self.original_stdout.write(text)
        
    def flush(self):
        self.original_stdout.flush()

def run_ai_system_parse(session_id):
    """后台运行需求解析"""
    import asyncio
    from src.agents.project_master import ProjectMasterAgent
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        # 初始化ProjectMaster
        project_root = os.path.join(BASE_DIR, '..')
        docs_dir = os.path.join(project_root, 'docs')
        config_template_dir = os.path.join(project_root, 'config', 'template')
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 初始化项目管理器...')
        
        project_master = ProjectMasterAgent(
            agent_id='project_master_web',
            docs_dir=docs_dir,
            config_template_dir=config_template_dir,
            web_mode=True,  # 启用Web模式
            session=session  # 传递session对象
        )
        
        session['project_master'] = project_master
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始解析需求...')
        
        # 运行异步解析
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        requirement_dict = loop.run_until_complete(
            project_master.parse_user_requirement(session['requirement_text'])
        )
        
        if not requirement_dict:
            raise Exception("需求解析失败")
        
        # 初始化项目
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 创建项目目录...')
        simulation_name = requirement_dict.get('simulation_name', 'unnamed_simulation')
        project_dir = loop.run_until_complete(
            project_master.initialize_project(simulation_name)
        )
        
        session['status'] = 'parsed'
        session['results']['requirement_dict'] = requirement_dict
        session['results']['simulation_name'] = simulation_name
        session['results']['project_dir'] = project_dir
        session['results']['config_dir'] = project_master.current_config_dir
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 需求解析完成')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 模拟名称: {simulation_name}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 项目目录: {project_dir}')
        
    except Exception as e:
        session['status'] = 'error'
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ 错误: {str(e)}')
    finally:
        sys.stdout = old_stdout

def run_ai_system_design(session_id):
    """后台运行设计阶段"""
    import asyncio
    import traceback
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    project_master = session['project_master']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始设计阶段...')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 需求字典: {session["results"]["requirement_dict"]}')
        
        design_results = loop.run_until_complete(
            project_master.run_design_phase(
                session['requirement_text'],  # original_requirement
                session['results']['requirement_dict'],  # requirement_dict
                user_feedback=session.get('user_feedback')
            )
        )
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 设计阶段执行完成，处理结果...')
        
        session['status'] = 'design_completed'
        session['results']['design_results'] = design_results
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 设计阶段完成')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 已生成设计文档和模块配置')
        
    except Exception as e:
        session['status'] = 'error'
        error_msg = f'设计阶段错误: {str(e)}'
        stack_trace = traceback.format_exc()
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {error_msg}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误堆栈:\n{stack_trace}')
        print(f'设计阶段异常: {error_msg}\n{stack_trace}')  # 同时输出到控制台
    finally:
        sys.stdout = old_stdout

def run_ai_system_coding(session_id):
    """后台运行编码阶段"""
    import asyncio
    import traceback
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    project_master = session['project_master']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始编码阶段...')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 正在初始化异步事件循环...')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 正在调用编码阶段...')
        
        coding_results = loop.run_until_complete(
            project_master.run_coding_phase(
                session['results']['design_results'],
                user_feedback=session.get('user_feedback')
            )
        )
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 编码阶段执行完成，处理结果...')
        
        session['status'] = 'coding_completed'
        session['results']['coding_results'] = coding_results
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 编码阶段完成')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 已生成所有代码和配置文件')
        
    except Exception as e:
        session['status'] = 'error'
        error_msg = f'编码阶段错误: {str(e)}'
        stack_trace = traceback.format_exc()
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {error_msg}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误堆栈:\n{stack_trace}')
        print(f'编码阶段异常: {error_msg}\n{stack_trace}')  # 同时输出到控制台
    finally:
        sys.stdout = old_stdout

def run_ai_system_full_simulation(session_id):
    """后台运行完整模拟和评估"""
    import asyncio
    import traceback
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    project_master = session['project_master']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始运行模拟...')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 正在初始化异步事件循环...')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        test_type = session.get('test_type', 'small')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 测试类型: {"小规模测试" if test_type == "small" else "大规模测试"}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 正在执行模拟...')
        
        # 运行模拟
        simulation_results = loop.run_until_complete(
            project_master.run_simulation(
                session['results']['coding_results'],
                max_fix_attempts=3
            )
        )
        
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 模拟执行完成，检查结果...')
        
        session['results']['simulation_results'] = simulation_results
        session['results']['test_type'] = test_type
        
        # 根据test_type判断是否是小规模测试完成
        if simulation_results and test_type == 'small':
            session['status'] = 'small_scale_completed'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ 小规模测试运行成功！')
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 可选操作：')
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] - 进行机制调整以优化参数')
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] - 继续大规模测试')
        elif simulation_results:
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 模拟运行完成')
            
            # 如果是大规模测试，运行评估
            if test_type == 'large':
                output_queue.put(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}')
                output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 📊 开始评估与优化阶段')
                output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}\n')
                session['phase'] = 'evaluation'
                session['status'] = 'evaluating'
                
                # 运行评估（不自动修改文件）
                evaluation_results = loop.run_until_complete(
                    project_master.run_evaluation_and_optimization_phase(True)
                )
                
                # 美化显示评估结果
                if evaluation_results:
                    output_queue.put(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}')
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ 评估完成')
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}\n')
                    
                    # 显示评估报告摘要
                    if 'evaluation_report' in evaluation_results:
                        report = evaluation_results['evaluation_report']
                        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 📋 评估报告摘要：')
                        # 提取关键部分（前500字符）
                        summary = report[:500] + '...' if len(report) > 500 else report
                        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {summary}\n')
                    
                    # 显示是否需要调整
                    if evaluation_results.get('needs_adjustment'):
                        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ⚠️  检测到需要调整配置')
                        
                        # 如果有诊断结果，显示
                        if 'diagnosis_result' in evaluation_results:
                            diagnosis = evaluation_results['diagnosis_result']
                            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 📝 诊断建议：')
                            if 'files_to_modify' in diagnosis:
                                for file_info in diagnosis['files_to_modify'][:3]:  # 只显示前3个
                                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]   - {file_info.get("file_name", "未知文件")}: {file_info.get("reason", "")[:80]}...')
                        
                        # 如果等待用户确认
                        if evaluation_results.get('waiting_user_confirmation'):
                            output_queue.put(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ⏸️  等待用户决定是否应用优化调整...')
                            session['status'] = 'evaluation_waiting_confirm'
                        else:
                            # 已经应用了修改
                            if 'modification_results' in evaluation_results:
                                mods = evaluation_results['modification_results']
                                if mods:
                                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 已自动修改 {len(mods)} 个文件')
                                elif mods is None:
                                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ℹ️  跳过了配置修改')
                            session['status'] = 'completed'
                    else:
                        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ 结果符合预期，无需调整')
                        session['status'] = 'completed'
                
                session['results']['evaluation_results'] = evaluation_results
                
                if session['status'] == 'completed':
                    output_queue.put(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}')
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 🎉 全流程完成')
                    output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {"="*60}\n')
            else:
                # 小规模测试也完成了模拟
                session['status'] = 'simulation_completed'
                output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ 小规模测试完成')
        else:
            session['status'] = 'simulation_failed'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ 模拟运行失败')
        
    except Exception as e:
        session['status'] = 'error'
        error_msg = f'模拟运行错误: {str(e)}'
        stack_trace = traceback.format_exc()
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {error_msg}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误堆栈:\n{stack_trace}')
        print(f'模拟运行异常: {error_msg}\n{stack_trace}')  # 同时输出到控制台
    finally:
        sys.stdout = old_stdout

def run_ai_system_mechanism_adjust(session_id):
    """后台运行机制调整会话"""
    import asyncio
    import traceback
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    project_master = session['project_master']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始机制解释与调整会话...')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 运行机制解释会话
        requirements_text = loop.run_until_complete(
            project_master.run_mechanism_interpretation_session(
                session['results'].get('coding_results')
            )
        )
        
        if requirements_text:
            session['status'] = 'mechanism_adjust_completed'
            session['results']['adjustment_requirements'] = requirements_text
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ 机制调整需求收集完成')
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 调整需求:\n{requirements_text}')
        else:
            session['status'] = 'mechanism_adjust_skipped'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ℹ️ 未收集到调整需求')
        
    except Exception as e:
        session['status'] = 'error'
        error_msg = f'机制调整会话错误: {str(e)}'
        stack_trace = traceback.format_exc()
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {error_msg}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误堆栈:\n{stack_trace}')
        print(f'机制调整异常: {error_msg}\n{stack_trace}')
    finally:
        sys.stdout = old_stdout

def run_ai_system_apply_adjustments(session_id):
    """后台应用机制调整"""
    import asyncio
    import traceback
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    project_master = session['project_master']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始应用机制调整...')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        adjustments_text = session.get('adjustments_text', '')
        
        # 应用调整
        success = loop.run_until_complete(
            project_master.apply_mechanism_adjustments(adjustments_text)
        )
        
        if success:
            session['status'] = 'adjustments_applied'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ 机制调整应用成功')
            
            # 记录调整历史
            if 'mechanism_adjustments' not in session['results']:
                session['results']['mechanism_adjustments'] = []
            
            session['results']['mechanism_adjustments'].append({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'description': adjustments_text[:100] + '...' if len(adjustments_text) > 100 else adjustments_text
            })
        else:
            session['status'] = 'error'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ 机制调整应用失败')
        
    except Exception as e:
        session['status'] = 'error'
        error_msg = f'应用调整错误: {str(e)}'
        stack_trace = traceback.format_exc()
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {error_msg}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误堆栈:\n{stack_trace}')
        print(f'应用调整异常: {error_msg}\n{stack_trace}')
    finally:
        sys.stdout = old_stdout

def run_ai_system_apply_optimization(session_id):
    """后台应用评估优化调整"""
    import asyncio
    import traceback
    
    session = ai_system_sessions[session_id]
    output_queue = session['output_queue']
    project_master = session['project_master']
    
    # 捕获stdout
    output_capture = OutputCapture(output_queue)
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始应用优化调整...')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        evaluation_results = session.get('results', {}).get('evaluation_results', {})
        diagnosis_path = evaluation_results.get('diagnosis_path')
        
        # 获取设计文档
        design_doc = None
        if 'design_results' in session.get('results', {}):
            design_results = session['results']['design_results']
            if 'description_content' in design_results:
                design_doc = design_results['description_content']
        
        # 应用优化
        result = loop.run_until_complete(
            project_master.apply_optimization_adjustments(diagnosis_path, design_doc)
        )
        
        if result.get('success'):
            session['status'] = 'optimization_applied'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✅ {result["message"]}')
            
            # 更新结果
            session['results']['optimization_applied'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'modification_results': result.get('modification_results', [])
            }
            
            output_queue.put(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 💡 建议：重新运行大规模测试以验证优化效果')
        else:
            session['status'] = 'error'
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {result["message"]}')
        
    except Exception as e:
        session['status'] = 'error'
        error_msg = f'应用优化错误: {str(e)}'
        stack_trace = traceback.format_exc()
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ❌ {error_msg}')
        output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 错误堆栈:\n{stack_trace}')
        print(f'应用优化异常: {error_msg}\n{stack_trace}')
    finally:
        sys.stdout = old_stdout

if __name__ == '__main__':
    app.run(debug=True, port=5000)