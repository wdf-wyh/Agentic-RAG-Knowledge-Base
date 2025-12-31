"""日志工具模块"""
import logging
import sys
from typing import Optional

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(
    name: str,
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """获取配置好的 logger
    
    Args:
        name: logger 名称
        level: 日志级别
        format_string: 日志格式
        
    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if not logger.handlers:
        logger.setLevel(level)
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        
        formatter = logging.Formatter(format_string or DEFAULT_FORMAT)
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    return logger
