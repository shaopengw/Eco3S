import logging
import os
from datetime import datetime
from typing import Optional
from .simulation_context import SimulationContext

class LogManager:
    """统一的日志管理器"""
    _instances = {}
    
    @classmethod
    def get_logger(cls, agent_type: Optional[str] = None, console_output: bool = True, 
                    console_level: int = logging.INFO) -> logging.Logger:
        """
        获取或创建一个日志记录器
        :param agent_type: 代理类型，如'resident', 'government', 'rebels'等
        :param console_output: 是否输出到控制台，默认True
        :param console_level: 控制台输出级别，默认INFO
        :return: 配置好的日志记录器
        """
        # 确保目录结构存在
        SimulationContext.ensure_directories()
        
        # 获取日志目录
        log_dir = SimulationContext.get_logs_dir()
        
        # 生成日志文件名
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        if agent_type:
            logger_name = f"{SimulationContext.get_simulation_type()}.{agent_type}"
            log_file = os.path.join(log_dir, f"{agent_type}_{now}.log")
        else:
            logger_name = SimulationContext.get_simulation_type()
            log_file = os.path.join(log_dir, f"{SimulationContext.get_simulation_type()}_{now}.log")
            
        # 检查是否已存在相同的logger
        if logger_name in cls._instances:
            return cls._instances[logger_name]
            
        # 创建新的logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        # 防止日志传播到父logger（避免重复输出）
        logger.propagate = False
        
        # 清除已有的handlers（防止重复添加）
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 可选：添加控制台处理器
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
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