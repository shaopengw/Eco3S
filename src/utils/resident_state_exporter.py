import os
import json
from src.utils.simulation_context import SimulationContext

class ResidentStateExporter:
    """
    通用居民状态导出器：用于在模拟运行过程中，实时提取所有居民的微观状态
    （包括坐标、职业、满意度等数值状态，以及长短期记忆、思考决策、发言等文本状态）。
    导出的 JSON 数据可供后续深度数据挖掘、全流程回放或者实时大盘展示使用。
    """
    
    @staticmethod
    def _x_to_longitude(x, map_obj):
        if not map_obj or getattr(map_obj, 'width', 0) == 0:
            return 0
        return map_obj.min_longitude + (x / map_obj.width) * (map_obj.max_longitude - map_obj.min_longitude)

    @staticmethod
    def _y_to_latitude(y, map_obj):
        if not map_obj or getattr(map_obj, 'height', 0) == 0:
            return 0
        return map_obj.max_latitude - (y / map_obj.height) * (map_obj.max_latitude - map_obj.min_latitude)

    @staticmethod
    def collect_resident_states(simulator):
        """收集所有居民的位置信息及深度状态数据"""
        residents_data = []
        # 安全获取居民字典和地图对象
        residents = getattr(simulator, 'residents', {})
        map_obj = getattr(simulator, 'map', None)

        for resident_id, resident in residents.items():
            # 兼容多种可能的坐标获取方式
            location = getattr(resident, 'location', (None, None))
            if isinstance(location, (list, tuple)) and len(location) == 2:
                x, y = location
            else:
                x, y = None, None

            if x is not None and y is not None:
                # 获取记忆和决策
                memories = []
                longterm_memory = []
                yearly_decisions = getattr(resident, 'yearly_decisions', [])
                if hasattr(resident, 'memory') and resident.memory:
                    try:
                        pm = getattr(resident.memory, 'personal_memory', None)
                        if pm:
                            if hasattr(pm, 'get_longterm_memory'):
                                longterm_memory = pm.get_longterm_memory()
                            if hasattr(pm, 'chat_history') and hasattr(pm.chat_history, 'retrieve'):
                                records = pm.chat_history.retrieve(50)  # 获取最近50条记录
                                for record in records:
                                    if hasattr(record, 'memory_record') and hasattr(record.memory_record, 'message'):
                                        role = getattr(record.memory_record.message, 'role_type', '')
                                        memories.append({
                                            'role': 'assistant' if role == 'assistant' else 'user',
                                            'content': getattr(record.memory_record.message, 'content', '')
                                        })
                    except Exception:
                        pass
                        
                residents_data.append({
                    'resident_id': resident_id,
                    'location_detail': {
                        'longitude': ResidentStateExporter._x_to_longitude(x, map_obj),
                        'latitude': ResidentStateExporter._y_to_latitude(y, map_obj)
                    },
                    'town': getattr(resident, 'town', None),
                    'job': getattr(resident, 'job', None),
                    'employed': getattr(resident, 'employed', None),
                    'income': getattr(resident, 'income', None),
                    'satisfaction': getattr(resident, 'satisfaction', None),
                    'health_index': getattr(resident, 'health_index', None),
                    'yearly_decisions': yearly_decisions,
                    'memories': memories,
                    'longterm_memory': longterm_memory
                })
        return residents_data

    @staticmethod
    def save_resident_data(simulator):
        """保存居民状态数据到 JSON 文件（持续覆盖更新，保持最新状态）"""
        data_dir = SimulationContext.get_data_dir()
        SimulationContext.ensure_directories()
        filename = os.path.join(data_dir, 'residents_data.json')
        
        try:
            residents_data = ResidentStateExporter.collect_resident_states(simulator)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(residents_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"居民状态数据导出失败: {str(e)}")
