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
    'default': 'config/default/simulation_config.yaml',
    'TEOG': 'config/TEOG/simulation_config.yaml',
    'info_propagation': 'config/info_propagation/simulation_config.yaml'
}

COMMANDS = {
    'default': 'python entrypoints/main.py --config_path config/default/simulation_config.yaml',
    'TEOG': 'python entrypoints/main_TEOG.py --config_path config/TEOG/simulation_config.yaml',
    'info_propagation': 'python entrypoints/main_info_propagation.py --config_path config/info_propagation/simulation_config.yaml'
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

        # 获取最新生成的图表（从最新的时间戳子文件夹中）
        analysis_base_dir = os.path.join(working_dir, 'history', config_type, 'analysis_results')
        plots = []
        if os.path.exists(analysis_base_dir):
            # 获取所有时间戳子文件夹
            timestamp_dirs = [d for d in os.listdir(analysis_base_dir) 
                            if os.path.isdir(os.path.join(analysis_base_dir, d))]
            
            if timestamp_dirs:
                # 按文件夹名称（时间戳）排序，获取最新的
                timestamp_dirs.sort(reverse=True)
                latest_dir = timestamp_dirs[0]
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
@app.route('/api/ai_system/confirm/<session_id>', methods=['POST'])
def confirm_action(session_id):
    """处理用户确认"""
    if session_id not in ai_system_sessions:
        return jsonify({'error': '会话不存在'}), 404
    
    data = request.json
    session = ai_system_sessions[session_id]
    
    # 设置用户的确认响应
    session['user_confirmation'] = data.get('confirmed', False)
    session['user_input'] = data.get('input', '')
    session['waiting_confirmation'] = False
    
    return jsonify({'message': '确认已接收'})

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
        
        if not session_id or session_id not in ai_system_sessions:
            return jsonify({'error': '无效的会话ID'}), 400
        
        session = ai_system_sessions[session_id]
        session['status'] = 'running_simulation'
        session['phase'] = 'simulation'
        
        # 在后台线程中运行模拟
        thread = threading.Thread(target=run_ai_system_full_simulation, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'session_id': session_id,
            'status': 'running_simulation',
            'message': '开始运行模拟...'
        })
        
    except Exception as e:
        return jsonify({'error': f'运行模拟失败: {str(e)}'}), 500

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
            web_mode=True  # 启用Web模式
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
                session['results']['requirement_dict'],
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
        
        if simulation_results:
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 模拟运行完成')
            
            # 运行评估
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始评估结果...')
            
            evaluation_results = loop.run_until_complete(
                project_master.run_evaluation_and_optimization_phase(True)
            )
            
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 评估完成，更新状态...')
            
            session['results']['evaluation_results'] = evaluation_results
            session['status'] = 'completed'
            
            output_queue.put(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ✓ 全流程完成')
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)