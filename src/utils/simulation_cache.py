import os
import pickle
import logging
from datetime import datetime
from typing import Any, Optional, Type, TypeVar

from src.agents.resident import Resident, ResidentGroup, ResidentSharedInformationPool
from src.agents.government import (
    Government, OrdinaryGovernmentAgent, HighRankingGovernmentAgent, InformationOfficer,
    government_SharedInformationPool
)
from src.agents.rebels import Rebellion, OrdinaryRebel, RebelLeader, RebelsSharedInformationPool, InformationOfficer as RebelsInformationOfficer
from src.agents.memory_manager import MemoryManager, MemoryRecord, BaseMessage
from src.environment.social_network import SocialNetwork
from src.environment.towns import Towns
from src.environment.job_market import JobMarket
from src.environment.population import Population

from camel.configs import ChatGPTConfig
from camel.memories import ScoreBasedContextCreator, MemoryRecord
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.utils import OpenAITokenCounter
from src.agents.model_manager import ModelManager
from camel.types import ModelType

T = TypeVar('T')

class SimulationCache:
    """
    通用的模拟缓存管理类，用于处理模拟状态的保存和加载
    """
    
    @staticmethod
    def generate_cache_filename(population: int, total_years: int, cache_dir: str, with_timestamp: bool = False) -> str:
        """
        生成缓存文件名
        
        Args:
            population: 初始人口数量
            total_years: 总模拟年数
            cache_dir: 缓存目录路径
            with_timestamp: 是否在文件名中添加时间戳
            
        Returns:
            str: 完整的缓存文件路径
        """
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        # 生成基本文件名
        filename = f"simulation_cache_p{population}_y{total_years}"
        
        # 如果需要，添加时间戳
        if with_timestamp:
            now = datetime.now()
            filename += f"_{now.strftime('%Y%m%d_%H%M%S')}"
        
        # 添加文件扩展名
        filename += ".pkl"
        
        # 返回完整路径
        return os.path.join(cache_dir, filename)

    @staticmethod
    def find_latest_cache(population: int, target_years: int, cache_dir: str) -> Optional[str]:
        """
        查找最新的缓存文件
        
        Args:
            population: 初始人口数量
            target_years: 目标模拟年数
            cache_dir: 缓存目录路径
            
        Returns:
            Optional[str]: 找到的缓存文件路径，如果没有找到则返回 None
        """
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        # 生成缓存文件前缀
        cache_file_prefix = f"simulation_cache_p{population}_y"
        
        # 获取所有匹配的缓存文件
        matching_files = [
            f for f in os.listdir(cache_dir) 
            if os.path.isfile(os.path.join(cache_dir, f)) and f.startswith(cache_file_prefix)
        ]
        
        found_cache_file = None
        found_year = None
        
        # 遍历所有匹配的文件
        for file in matching_files:
            try:
                # 从文件名中提取年份
                current_year = int(file.split('y')[-1].split('.')[0].split('_')[0])
                
                # 如果找到完全匹配的年份
                if current_year == target_years:
                    found_cache_file = os.path.join(cache_dir, file)
                    found_year = current_year
                    print(f"发现已有的模拟文件 {file}，模拟年份等于配置文件中年份。")
                    break
                # 如果找到小于目标年份的最大年份
                elif current_year < target_years and (found_year is None or current_year > found_year):
                    found_cache_file = os.path.join(cache_dir, file)
                    found_year = current_year
                    print(f"发现已有的模拟文件 {file}，模拟年份小于配置文件中年份。")
            except ValueError:
                logging.warning(f"缓存文件名 {file} 格式不正确，跳过。")
        
        return found_cache_file, found_year

    @staticmethod
    def save_cache(simulator: Any, file_path: str) -> bool:
        """保存模拟状态到缓存文件
        
        Args:
            simulator: 模拟器实例
            file_path: 缓存文件保存路径
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 构建基础状态字典
            state = {}
            
            # 获取模拟器的所有属性
            for attr_name in dir(simulator):
                # 跳过私有属性和方法
                if attr_name.startswith('_'):
                    continue
                    
                try:
                    attr_value = getattr(simulator, attr_name)
                    
                    # 跳过方法和不可序列化的属性
                    if callable(attr_value):
                        continue
                        
                    # 特殊处理某些复杂对象
                    if attr_name == 'residents':
                        state[attr_name] = [
                            {
                                'resident_id': resident.resident_id,
                                'shared_pool': resident.shared_pool.shared_info if hasattr(resident.shared_pool, 'shared_info') else {},
                                'location': getattr(resident, 'location', None),
                                'town': getattr(resident, 'town', None),
                                'employed': getattr(resident, 'employed', None),
                                'job': getattr(resident, 'job', None),
                                'income': getattr(resident, 'income', None),
                                'satisfaction': getattr(resident, 'satisfaction', None),
                                'health_index': getattr(resident, 'health_index', None),
                                'lifespan': getattr(resident, 'lifespan', None),
                                'personality': getattr(resident, 'personality', None),
                                'system_message': getattr(resident, 'system_message', None),
                                'memory': {
                                    'chat_history': [{
                                        'role': record.memory_record.role_at_backend,
                                        'content': record.memory_record.message.content
                                    } for record in resident.memory.personal_memory.chat_history.retrieve()] if hasattr(resident, 'memory') and resident.memory else [],
                                    'longterm_memory': resident.memory.personal_memory.longterm_memory if hasattr(resident, 'memory') and resident.memory else []
                                } if hasattr(resident, 'memory') and resident.memory else None
                            } for resident in attr_value.values()
                        ] if isinstance(attr_value, dict) else []
                    elif attr_name == 'towns':
                        state[attr_name] = {
                            town_name: {
                                'info': town_data.get('info', {}),
                                'residents': {
                                    resident_id: {
                                        'resident_id': resident.resident_id,
                                        'town': getattr(resident, 'town', None)
                                    } for resident_id, resident in town_data.get('residents', {}).items()
                                },
                                'job_market': {
                                    'town_type': town_data['job_market'].town_type,
                                    'jobs_info': {
                                        job_type: {
                                            'total': info.get('total'),
                                            'employed': info.get('employed', {}),
                                            'base_salary': info.get('base_salary')
                                        } for job_type, info in town_data['job_market'].jobs_info.items()
                                    }
                                } if town_data.get('job_market') else None
                            } for town_name, town_data in attr_value.towns.items()
                        } if hasattr(attr_value, 'towns') else {}
                    elif attr_name == 'government':
                        state[attr_name] = {
                            'budget': getattr(attr_value, 'budget', 0),
                            'tax_rate': getattr(attr_value, 'tax_rate', 0),
                            'military_strength': getattr(attr_value, 'military_strength', 0)
                        }
                    elif attr_name == 'government_officials':
                        state[attr_name] = [
                            {
                                'agent_id': official.agent_id,
                                'group_type': getattr(official, 'group_type', 'government'),
                                'function': getattr(official, 'function', None),
                                'faction': getattr(official, 'faction', None),
                                'personality': getattr(official, 'personality', None),
                                'system_message': getattr(official, 'system_message', None),
                                'memory': {
                                    'chat_history': [{
                                        'role': record.memory_record.role_at_backend,
                                        'content': record.memory_record.message.content
                                    } for record in official.memory.personal_memory.chat_history.retrieve()] if hasattr(official, 'memory') and official.memory else [],
                                    'longterm_memory': official.memory.personal_memory.longterm_memory if hasattr(official, 'memory') and official.memory else []
                                } if hasattr(official, 'memory') and official.memory else None
                            } for official in attr_value.values()
                        ] if isinstance(attr_value, dict) else []
                    elif attr_name == 'rebels_agents':
                        state[attr_name] = [
                            {
                                'agent_id': rebel.agent_id,
                                'group_type': getattr(rebel, 'group_type', 'rebellion'),
                                'role': getattr(rebel, 'role', None),
                                'personality': getattr(rebel, 'personality', None),
                                'system_message': getattr(rebel, 'system_message', None),
                                'memory': {
                                    'chat_history': [{
                                        'role': record.memory_record.role_at_backend,
                                        'content': record.memory_record.message.content
                                    } for record in rebel.memory.personal_memory.chat_history.retrieve()] if hasattr(rebel, 'memory') and rebel.memory else [],
                                    'longterm_memory': rebel.memory.personal_memory.longterm_memory if hasattr(rebel, 'memory') and rebel.memory else []
                                } if hasattr(rebel, 'memory') and rebel.memory else None
                            } for rebel in attr_value.values()
                        ] if isinstance(attr_value, dict) else []
                    elif attr_name == 'rebellion':
                        state[attr_name] = {
                            'strength': getattr(attr_value, 'strength', 0),
                            'resources': getattr(attr_value, 'resources', 0)
                        }
                    elif attr_name == 'social_network':
                        state[attr_name] = attr_value.to_dict() if hasattr(attr_value, 'to_dict') else {}
                    else:
                        # 尝试直接保存其他属性
                        try:
                            pickle.dumps(attr_value)  # 测试是否可序列化
                            state[attr_name] = attr_value
                        except:
                            pass  # 如果无法序列化，则跳过该属性
                            
                except Exception as e:
                    print(f"警告：保存属性 {attr_name} 时出错: {str(e)}")
                    continue
            
            # 保存状态到文件
            with open(file_path, 'wb') as f:
                pickle.dump(state, f)
            print(f"缓存已保存到: {file_path}")
            return True
        except Exception as e:
            raise Exception(f"保存缓存失败: {e}")

    @staticmethod
    def load_cache(file_path: str, simulator_class: Type[T], simulator_years: int, config: dict) -> Optional[T]:
        """从缓存文件加载并恢复模拟器状态
        
        Args:
            file_path: 缓存文件路径
            simulator_class: 模拟器类
            simulator_years: 模拟年数
            config: 配置字典
            
        Returns:
            Optional[T]: 恢复的模拟器实例，如果加载失败则返回 None
        """
        try:
            # 加载缓存文件
            with open(file_path, 'rb') as f:
                state = pickle.load(f)
            print(f"已从缓存加载: {file_path}")
            
            # 创建新的模拟器实例并初始化
            simulator = simulator_class.__new__(simulator_class)
            simulator.config = config
            
            # 重建组件
            simulator.map = state.get('map') if 'map' in state else None
            simulator.time = state.get('time') if 'time' in state else None
            if simulator.time:
                simulator.time.update_total_years(simulator_years)
            simulator.population = state.get('population') if 'population' in state else None
            simulator.transport_economy = state.get('transport_economy') if 'transport_economy' in state else None
            
            # 重建居民
            simulator.residents = {}
            if 'residents' in state:
                residents_data = state.get('residents')
                if residents_data:
                    # 处理元组包裹的情况
                    if isinstance(residents_data, tuple) and len(residents_data) > 0:
                        residents_data = residents_data[0]
                    if isinstance(residents_data, list):
                        for res_state in residents_data:
                            resident = Resident(
                                resident_id=res_state.get('resident_id'),
                                job_market=None,  # 临时设为None，后续更新
                                shared_pool=ResidentSharedInformationPool(),
                                map=simulator.map,
                                resident_prompt_path=simulator.config["data"]["resident_prompt_path"],
                            )
                            # 初始化model_manager和model_backend
                            resident.model_manager = ModelManager()
                            model_config = resident.model_manager.get_random_model_config()
                            resident.model_type = ModelType(model_config["model_type"])
                            resident.model_config = ChatGPTConfig(**model_config["model_config"])
                            resident.model_backend = ModelFactory.create(
                                model_platform=model_config["model_platform"],
                                model_type=resident.model_type,
                                model_config_dict=resident.model_config.as_dict(),
                            )
                            resident.token_counter = OpenAITokenCounter(resident.model_type)
                            resident.context_creator = ScoreBasedContextCreator(resident.token_counter, 4096)
                            # 恢复居民状态
                            resident.shared_pool.shared_info = res_state.get('shared_pool', {})
                            resident.location = res_state.get('location')
                            resident.town = res_state.get('town')
                            resident.employed = res_state.get('employed')
                            resident.job = res_state.get('job')
                            resident.income = res_state.get('income')
                            resident.satisfaction = res_state.get('satisfaction')
                            resident.health_index = res_state.get('health_index')
                            resident.lifespan = res_state.get('lifespan')
                            resident.personality = res_state.get('personality')
                            resident.system_message = res_state.get('system_message')
                            
                            # 恢复记忆系统
                            memory_state = res_state.get('memory')
                            if memory_state:
                                resident.memory = MemoryManager(
                                    agent_id=resident.resident_id,
                                    model_type=resident.model_type,
                                    group_type='resident',
                                    window_size=5
                                )
                                resident.memory.set_agent(resident)
                                # 恢复聊天历史
                                for msg in memory_state.get('chat_history', []):
                                    record = MemoryRecord(
                                        message=BaseMessage.make_assistant_message(
                                            role_name='resident',
                                            content=msg['content']
                                        ) if msg['role'] == 'assistant' else BaseMessage.make_user_message(
                                            role_name='resident',
                                            content=msg['content']
                                        ),
                                        role_at_backend=msg['role']
                                    )
                                    resident.memory.personal_memory.write_record(record)
                                # 恢复长期记忆
                                resident.memory.personal_memory.longterm_memory = memory_state.get('longterm_memory', [])
                            simulator.residents[resident.resident_id] = resident

            # 重建城镇
            if 'towns' in state:
                simulator.towns = Towns(simulator.map, simulator.population.get_population(), simulator.config["data"]["jobs_config_path"])
                towns_state = state.get('towns')
                if towns_state:
                    # 处理元组包裹的情况
                    if isinstance(towns_state, tuple) and len(towns_state) > 0:
                        towns_state = towns_state[0]
                    if isinstance(towns_state, dict):
                        for town_name, town_data in towns_state.items():
                            simulator.towns.towns[town_name] = {
                                'info': town_data.get('info', {}),
                                'residents': {},
                                'job_market': None,  # 临时设为None，后续更新
                                'resident_group': ResidentGroup(town_name)  # 初始化ResidentGroup
                            }

                            # 恢复就业市场
                            if town_data.get('job_market'):
                                job_market = JobMarket(town_data['job_market'].get('town_type'))
                                for job_type, info in town_data['job_market'].get('jobs_info', {}).items():
                                    job_market.jobs_info[job_type] = {
                                        'total': info.get('total'),
                                        'employed': info.get('employed', {}),
                                        'base_salary': info.get('base_salary')
                                    }
                                simulator.towns.towns[town_name]['job_market'] = job_market
                            else:
                                simulator.towns.towns[town_name]['job_market'] = JobMarket(town_data.get('info', {}).get('type', '非沿河'))
                            
                            # 恢复居民关联
                            for resident_id, resident_data in town_data.get('residents', {}).items():
                                if resident_id in simulator.residents:
                                    simulator.towns.towns[town_name]['residents'][resident_id] = simulator.residents[resident_id]
                                    simulator.residents[resident_id].town = town_name
                                    # 更新居民的job_market引用
                                    simulator.residents[resident_id].job_market = simulator.towns.towns[town_name]['job_market']
                                    # 将居民添加到ResidentGroup
                                    simulator.towns.towns[town_name]['resident_group'].add_resident(simulator.residents[resident_id])
                                    # 如果该居民之前有工作，需要重新建立就业关系
                                    if resident_id in town_data.get('job_market', {}).get('jobs_info', {}).get('employed', {}):
                                        simulator.residents[resident_id].employed = True
                                        simulator.residents[resident_id].job = town_data['job_market']['jobs_info']['employed'][resident_id]
            else:
                simulator.towns = Towns(simulator.map, simulator.population.get_population(), simulator.config["data"]["jobs_config_path"]) # Initialize towns even if not in cache

            # 恢复社交网络
            if 'social_network' in state:
                if state.get('social_network'):
                    simulator.social_network = SocialNetwork.from_dict(
                        state.get('social_network', {}), 
                        simulator.residents
                    )
                else:
                    simulator.social_network = SocialNetwork()
                    simulator.social_network.initialize_network(simulator.residents, simulator.towns)
            else:
                simulator.social_network = SocialNetwork()
                simulator.social_network.initialize_network(simulator.residents, simulator.towns)
            # 为每个城镇的居民群组设置社交网络
            for town_name, town_data in simulator.towns.towns.items():
                resident_group = town_data.get('resident_group')
                if resident_group:
                    resident_group.set_social_network(simulator.social_network)

            # 恢复政府数据
            if 'government' in state:
                government_data = state.get('government')
                if government_data:
                    if isinstance(government_data, tuple) and len(government_data) > 0:
                        government_data = government_data[0]
                    simulator.government = Government(
                        map=simulator.map,
                        towns=simulator.towns,
                        military_strength=government_data.get('military_strength'),
                        initial_budget=government_data.get('budget'),
                        time=simulator.time,
                        transport_economy=simulator.transport_economy,
                        government_prompt_path=simulator.config["data"]["government_prompt_path"],
                    )
                    simulator.government.tax_rate = government_data.get('tax_rate')
            else:
                simulator.government = None

            # 恢复政府官员
            if 'government_officials' in state:
                simulator.government_officials = {}
                officials_data = state.get('government_officials')
                if officials_data:
                    if isinstance(officials_data, tuple) and len(officials_data) > 0:
                        officials_data = officials_data[0]
                    shared_pool = government_SharedInformationPool()
                    for off_state in officials_data:
                        if off_state.get('personality'):
                            if off_state.get('function'):
                                official = OrdinaryGovernmentAgent(
                                    agent_id=off_state.get('agent_id'),
                                    government=simulator.government,
                                    shared_pool=shared_pool
                                )
                                official.function = off_state.get('function')
                                official.faction = off_state.get('faction')
                            else:
                                official = HighRankingGovernmentAgent(
                                    agent_id=off_state.get('agent_id'),
                                    government=simulator.government,
                                    shared_pool=shared_pool
                                )
                        else:
                            official = InformationOfficer(
                                agent_id=off_state.get('agent_id'),
                                government=simulator.government,
                                shared_pool=shared_pool
                            )
                        official.personality = off_state.get('personality')
                        official.system_message = off_state.get('system_message')
                        # 恢复记忆系统
                        memory_state = off_state.get('memory')
                        if memory_state:
                            official.memory = MemoryManager(
                                agent_id=official.agent_id,
                                model_type=official.model_type,
                                group_type='government',
                                window_size=5
                            )
                            official.memory.set_agent(official)
                            # 恢复聊天历史
                            for msg in memory_state.get('chat_history', []):
                                record = MemoryRecord(
                                    message=BaseMessage.make_assistant_message(
                                        role_name='government',
                                        content=msg['content']
                                    ) if msg['role'] == 'assistant' else BaseMessage.make_user_message(
                                        role_name='government',
                                        content=msg['content']
                                    ),
                                    role_at_backend=msg['role']
                                )
                                official.memory.personal_memory.write_record(record)
                            # 恢复长期记忆
                            official.memory.personal_memory.longterm_memory = memory_state.get('longterm_memory', [])
                        simulator.government_officials[official.agent_id] = official
            else:
                simulator.government_officials = {}

            # 恢复叛乱数据
            if 'rebellion' in state:
                rebellion_state = state.get('rebellion')
                if isinstance(rebellion_state, tuple) and len(rebellion_state) > 0:
                    rebellion_state = rebellion_state[0]
                simulator.rebellion = Rebellion(
                    initial_strength=rebellion_state.get('strength'),
                    initial_resources=rebellion_state.get('resources'),
                    towns=simulator.towns,
                    rebels_prompt_path=simulator.config["data"]["rebels_prompt_path"],
                )
            else:
                simulator.rebellion = None

            # 恢复叛军
            simulator.rebels_agents = {}
            if 'rebels_agents' in state and simulator.rebellion:
                rebels_data = state.get('rebels_agents')
                if isinstance(rebels_data, tuple) and len(rebels_data) > 0:
                    rebels_data = rebels_data[0]
                shared_pool = RebelsSharedInformationPool()
                for rebel_state in rebels_data:
                    if rebel_state.get('role') == '信息整理官':
                        rebel = RebelsInformationOfficer(
                            agent_id=rebel_state.get('agent_id'),
                            rebellion=simulator.rebellion,
                            shared_pool=shared_pool
                        )
                    elif rebel_state.get('role'):
                        rebel = OrdinaryRebel(
                            agent_id=rebel_state.get('agent_id'),
                            rebellion=simulator.rebellion,
                            shared_pool=shared_pool
                        )
                    else:
                        rebel = RebelLeader(
                            agent_id=rebel_state.get('agent_id'),
                            rebellion=simulator.rebellion,
                            shared_pool=shared_pool
                        )
                    rebel.role = rebel_state.get('role')
                    rebel.personality = rebel_state.get('personality')
                    rebel.system_message = rebel_state.get('system_message')
                    # 初始化model_manager和model_backend
                    rebel.model_manager = ModelManager()
                    model_config = rebel.model_manager.get_random_model_config()
                    rebel.model_type = ModelType(model_config["model_type"])
                    rebel.model_config = ChatGPTConfig(**model_config["model_config"])
                    rebel.model_backend = ModelFactory.create(
                        model_platform=model_config["model_platform"],
                        model_type=rebel.model_type,
                        model_config_dict=rebel.model_config.as_dict(),
                    )
                    rebel.token_counter = OpenAITokenCounter(rebel.model_type)
                    rebel.context_creator = ScoreBasedContextCreator(rebel.token_counter, 4096)
                    # 恢复记忆系统
                    memory_state = rebel_state.get('memory')
                    if memory_state:
                        rebel.memory = MemoryManager(
                            agent_id=rebel.agent_id,
                            model_type=rebel.model_type,
                            group_type='rebellion',
                            window_size=5
                        )
                        rebel.memory.set_agent(rebel)
                        # 恢复聊天历史
                        for msg in memory_state.get('chat_history', []):
                            record = MemoryRecord(
                                message=BaseMessage.make_assistant_message(
                                    role_name='rebellion',
                                    content=msg['content']
                                ) if msg['role'] == 'assistant' else BaseMessage.make_user_message(
                                    role_name='rebellion',
                                    content=msg['content']
                                ),
                                role_at_backend=msg['role']
                            )
                            rebel.memory.personal_memory.write_record(record)
                        # 恢复长期记忆
                        rebel.memory.personal_memory.longterm_memory = memory_state.get('longterm_memory', [])
                    simulator.rebels_agents[rebel.agent_id] = rebel

            # 恢复统计数据和历史记录
            simulator.climate = state.get('climate') if 'climate' in state else None
            simulator.basic_living_cost = state.get('basic_living_cost') if 'basic_living_cost' in state else None
            simulator.average_satisfaction = state.get('average_satisfaction') if 'average_satisfaction' in state else None
            simulator.gdp = state.get('gdp') if 'gdp' in state else None
            simulator.propaganda_prob = state.get('propaganda_prob') if 'propaganda_prob' in state else None
            simulator.propaganda_speech = state.get('propaganda_speech') if 'propaganda_speech' in state else None
            simulator.rebellion_records = state.get('rebellion_records') if 'rebellion_records' in state else None
            simulator.results = state.get('results') if 'results' in state else None
            simulator.rebellion_history = state.get('rebellion_history') if 'rebellion_history' in state else None
            simulator.start_time = state.get('start_time') if 'start_time' in state else None
            simulator.end_time = state.get('end_time') if 'end_time' in state else None

            return simulator
        except Exception as e:
            raise Exception(f"加载缓存失败: {str(e)}")
            return None