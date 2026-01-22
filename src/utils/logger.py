"""日志工具模块"""
import logging
import sys
import os
from pathlib import Path
from typing import Optional

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging(
    name: str = "app",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """配置日志系统 - 同时输出到控制台和文件
    
    Args:
        name: logger 名称
        level: 日志级别
        log_file: 日志文件路径（如果为None，则只输出到控制台）
        format_string: 日志格式
        
    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 设置日志级别
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    fmt = format_string or DEFAULT_FORMAT
    formatter = logging.Formatter(fmt)
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"⚠️ 无法创建日志文件 {log_file}: {e}")
    
    return logger


def get_logger(
    name: str,
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """获取配置好的 logger (不配置文件输出)
    
    Args:
        name: logger 名称
        level: 日志级别
        format_string: 日志格式
        
    Returns:
        配置好的 logger 实例
    """
    return setup_logging(name, level, None, format_string)
