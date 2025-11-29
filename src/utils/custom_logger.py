import logging
import os
from datetime import datetime

class CustomLogger:
    _instance = None
    _loggers = {}

    def __new__(cls, log_name: str = "default", log_dir: str = "logs", console_output: bool = True, console_level: int = logging.INFO):
        if cls._instance is None:
            cls._instance = super(CustomLogger, cls).__new__(cls)
            cls._instance._initialize_logger(log_name, log_dir, console_output, console_level)
        return cls._instance

    def _initialize_logger(self, log_name: str, log_dir: str, console_output: bool, console_level: int):
        if log_name in CustomLogger._loggers:
            self.logger = CustomLogger._loggers[log_name]
            return

        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)

        # Create logger
        logger = logging.getLogger(log_name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Clear existing handlers to prevent duplicate logs
        if logger.hasHandlers():
            logger.handlers.clear()

        # Formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # File Handler
        log_file_name = f"{log_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(os.path.join(log_dir, log_file_name), encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Handler
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        self.logger = logger
        CustomLogger._loggers[log_name] = logger

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def debug(self, message: str):
        self.logger.debug(message)

    def critical(self, message: str):
        self.logger.critical(message)