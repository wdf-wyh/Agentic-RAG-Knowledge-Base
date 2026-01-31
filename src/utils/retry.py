"""重试机制 - 自动重试失败的操作

提供指数退避重试、自定义重试条件等功能。
"""

import asyncio
import random
import time
import logging
from typing import Callable, Type, Tuple, Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算重试延迟（指数退避）"""
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        # 添加随机抖动，避免雷同请求同时重试
        delay = delay * (0.5 + random.random())
    
    return delay


def retry(config: RetryConfig = None):
    """同步重试装饰器"""
    cfg = config or RetryConfig()
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(cfg.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except cfg.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < cfg.max_retries:
                        delay = calculate_delay(attempt, cfg)
                        logger.warning(
                            f"[Retry] {func.__name__} 失败 (尝试 {attempt + 1}/{cfg.max_retries + 1}): {e}"
                            f"，{delay:.1f}秒后重试"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"[Retry] {func.__name__} 最终失败: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator


def async_retry(config: RetryConfig = None):
    """异步重试装饰器"""
    cfg = config or RetryConfig()
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(cfg.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except cfg.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < cfg.max_retries:
                        delay = calculate_delay(attempt, cfg)
                        logger.warning(
                            f"[Retry] {func.__name__} 失败 (尝试 {attempt + 1}/{cfg.max_retries + 1}): {e}"
                            f"，{delay:.1f}秒后重试"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"[Retry] {func.__name__} 最终失败: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator


class RetryContext:
    """重试上下文管理器"""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.attempt = 0
        self.last_exception = None
    
    def should_retry(self, exception: Exception) -> bool:
        """判断是否应该重试"""
        if not isinstance(exception, self.config.retryable_exceptions):
            return False
        
        self.last_exception = exception
        self.attempt += 1
        
        return self.attempt <= self.config.max_retries
    
    def get_delay(self) -> float:
        """获取当前重试的延迟时间"""
        return calculate_delay(self.attempt - 1, self.config)
    
    def reset(self):
        """重置状态"""
        self.attempt = 0
        self.last_exception = None


# 预配置的重试策略
QUICK_RETRY = RetryConfig(max_retries=2, base_delay=0.5)
STANDARD_RETRY = RetryConfig(max_retries=3, base_delay=1.0)
PATIENT_RETRY = RetryConfig(max_retries=5, base_delay=2.0, max_delay=120)
NETWORK_RETRY = RetryConfig(
    max_retries=3, 
    base_delay=1.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError)
)
