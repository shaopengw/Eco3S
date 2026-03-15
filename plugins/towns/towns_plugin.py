"""
城镇插件实现 - 包装器模式
"""
from typing import Dict, Any, Optional
from collections import defaultdict
from src.plugins import ITownsPlugin, PluginContext
from src.interfaces import ITowns, IMap
from src.environment.towns import Towns


class DefaultTownsPlugin(ITownsPlugin):
    """
    默认城镇插件 - 包装现有 Towns 类
    """
    
    def __init__(self, map: IMap = None,
                 initial_population: int = 10,
                 job_market_config_path: Optional[str] = None):
        """
        初始化城镇插件
        
        Args:
            map: 地图实例
            initial_population: 初始人口
            job_market_config_path: 就业市场配置路径
        """
        super().__init__()
        
        # 保存参数
        self._map_param = map
        self._initial_population_param = initial_population
        self._job_market_config_path_param = job_market_config_path
        self._towns = None
    
    def init(self, context: PluginContext) -> None:
        """接收插件上下文并初始化"""
        self._context = context
        self.logger = context.logger
        self.config = context.config
        
        # 从插件上下文获取 map 实例（依赖项）
        if self._map_param is None and context.registry:
            map_plugin = context.registry.get_plugin('default_map')
            if map_plugin:
                self._map_param = map_plugin
                self.logger.info("从插件系统获取 default_map 依赖")
            else:
                self.logger.warning("无法获取 map 插件，将在 on_load 时重试")
        
        # 创建原始 Towns 实例
        if self._map_param is not None:
            self._towns = Towns(
                map=self._map_param,
                initial_population=self._initial_population_param,
                job_market_config_path=self._job_market_config_path_param
            )
        else:
            # 延迟初始化，等待依赖加载
            self._towns = None
            self.logger.info("Towns 插件延迟初始化，等待 map 依赖")
    
    # ===== BasePlugin 生命周期方法 =====
    
    def on_load(self) -> None:
        """插件加载时调用"""
        # 如果 Towns 实例还未创建，现在创建它
        if self._towns is None:
            if self.context.registry:
                map_plugin = self.context.registry.get_plugin('default_map')
                if map_plugin:
                    self._towns = Towns(
                        map=map_plugin,
                        initial_population=self._initial_population_param,
                        job_market_config_path=self._job_market_config_path_param
                    )
                    self.logger.info("Towns 实例在 on_load 阶段创建")
                else:
                    raise RuntimeError("无法加载 Towns 插件：依赖的 map 插件未找到")
            else:
                raise RuntimeError("无法加载 Towns 插件：PluginContext 缺少 registry")
        
        self.logger.info(f"DefaultTownsPlugin 正在加载 (towns_count={len(self._towns.towns)})")
        
        # 订阅事件
        self.context.event_bus.subscribe('map_initialized', self._on_map_initialized)
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        self.logger.info("DefaultTownsPlugin 正在卸载")
        
        # 取消订阅
        self.context.event_bus.unsubscribe('map_initialized', self._on_map_initialized)
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": "DefaultTowns",
            "version": "1.0.0",
            "description": "默认城镇系统插件（包装 Towns 类）",
            "author": "AgentWorld Team",
            "dependencies": ["default_map"]
        }
    
    # ===== ITowns 接口属性 - 代理到内部 Towns 实例 =====
    
    @property
    def towns(self):
        return self._towns.towns
    
    # ===== ITowns 接口方法 - 代理到内部 Towns 实例 =====
    
    def initialize_towns(self, map, initial_population, job_market_config_path=None):
        """初始化所有城镇信息"""
        self._towns.initialize_towns(map, initial_population, job_market_config_path)
    
    def initialize_resident_groups(self, residents):
        """初始化居民组"""
        self._towns.initialize_resident_groups(residents)
        
        # 发布事件
        self.context.event_bus.publish('resident_groups_initialized', {
            'towns_count': len(self._towns.towns)
        })
    
    def get_town_info(self, town_name: str):
        """获取城镇信息"""
        return self._towns.get_town_info(town_name)
    
    def get_all_towns(self):
        """获取所有城镇"""
        return self._towns.get_all_towns()
    
    def add_residents_to_town(self, town_name: str, residents: list):
        """向城镇添加居民"""
        self._towns.add_residents_to_town(town_name, residents)
    
    def get_town_residents(self, town_name: str):
        """获取城镇的所有居民"""
        return self._towns.get_town_residents(town_name)
    
    def get_town_resident_group(self, town_name: str):
        """获取城镇的居民组"""
        return self._towns.get_town_resident_group(town_name)
    
    def get_total_population(self) -> int:
        """获取总人口"""
        return self._towns.get_total_population()
    
    def _create_town_dict(self):
        """创建城镇字典"""
        return self._towns._create_town_dict()
    
    def add_jobs(self, add_job_amount, job_name=None, town_type=None, use_random_assignment=True):
        """添加工作"""
        return self._towns.add_jobs(add_job_amount, job_name, town_type, use_random_assignment)
    
    def add_jobs_across_towns(self, total_jobs_to_add, job_name=None):
        """跨城镇添加工作"""
        return self._towns.add_jobs_across_towns(total_jobs_to_add, job_name)
    
    def add_resident(self, resident, town_name):
        """添加居民到城镇"""
        return self._towns.add_resident(resident, town_name)
    
    def add_specific_job(self, add_job_amount, town_type, job_name):
        """添加特定工作"""
        return self._towns.add_specific_job(add_job_amount, town_type, job_name)
    
    def adjust_job_market(self, change_rate, residents):
        """调整就业市场"""
        return self._towns.adjust_job_market(change_rate, residents)
    
    def batch_add_residents(self, residents_list, town_name):
        """批量添加居民"""
        return self._towns.batch_add_residents(residents_list, town_name)
    
    def get_hometown_group(self, town_name):
        """获取家乡组"""
        return self._towns.get_hometown_group(town_name)
    
    def get_nearest_town(self, location):
        """获取最近的城镇"""
        return self._towns.get_nearest_town(location)
    
    def get_town_job_market(self, town_name):
        """获取城镇就业市场"""
        return self._towns.get_town_job_market(town_name)
    
    def print_towns(self):
        """打印城镇信息"""
        return self._towns.print_towns()
    
    def print_towns_status(self):
        """打印城镇状态"""
        return self._towns.print_towns_status()
    
    def process_town_job_requests(self, town_job_requests):
        """处理城镇工作请求"""
        return self._towns.process_town_job_requests(town_job_requests)
    
    def remove_jobs_across_towns(self, total_jobs_to_remove, residents):
        """跨城镇移除工作"""
        return self._towns.remove_jobs_across_towns(total_jobs_to_remove, residents)
    
    def remove_resident_in_town(self, resident_id, town_name, job_type=None):
        """从城镇移除居民"""
        return self._towns.remove_resident_in_town(resident_id, town_name, job_type)
    
    def update_hometown_group(self, town_name, group_id):
        """更新家乡组"""
        return self._towns.update_hometown_group(town_name, group_id)
    
    # ===== 内部方法 =====
    
    def _on_map_initialized(self, data: Dict[str, Any]) -> None:
        """地图初始化时的处理"""
        self.logger.info("收到 map_initialized 事件")
