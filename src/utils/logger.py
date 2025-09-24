import logging
import os
from datetime import datetime
from typing import Optional
from .simulation_context import SimulationContext

class LogManager:
    """统一的日志管理器"""
    _instances = {}
    
    @classmethod
    def get_logger(cls, agent_type: Optional[str] = None) -> logging.Logger:
        """
        获取或创建一个日志记录器
        :param agent_type: 代理类型，如'resident', 'government', 'rebels'等
        :return: 配置好的日志记录器
        """
        # 获取当前模拟类型
        simulation_type = SimulationContext.get_simulation_type()
        
        # 创建基本日志目录
        base_log_dir = "./log"
        os.makedirs(base_log_dir, exist_ok=True)
        
        # 创建模拟类型特定的日志目录
        sim_log_dir = os.path.join(base_log_dir, simulation_type)
        os.makedirs(sim_log_dir, exist_ok=True)
        
        # 生成日志文件名
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        if agent_type:
            logger_name = f"{simulation_type}.{agent_type}"
            log_file = os.path.join(sim_log_dir, f"{agent_type}_{now}.log")
        else:
            logger_name = simulation_type
            log_file = os.path.join(sim_log_dir, f"{simulation_type}_{now}.log")
            
        # 检查是否已存在相同的logger
        if logger_name in cls._instances:
            return cls._instances[logger_name]
            
        # 创建新的logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        
        # 保存实例
        cls._instances[logger_name] = logger
        
        return logger
    
    @classmethod
    def clear_loggers(cls):
        """清除所有日志记录器的处理器"""
        for logger in cls._instances.values():
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        cls._instances.clear()