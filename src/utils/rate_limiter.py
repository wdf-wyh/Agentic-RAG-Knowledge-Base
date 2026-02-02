"""请求限流器 - 防止API过载和被封禁"""

import time
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import deque
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限流配置"""
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    burst_limit: int = 10  # 突发请求限制
    cooldown_seconds: float = 1.0  # 请求间隔


class TokenBucket:
    """令牌桶算法实现"""
    
    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: 每秒生成的令牌数
            capacity: 桶容量
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌
        
        Returns:
            是否成功获取
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def acquire_async(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """异步获取令牌，带超时"""
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire(tokens):
                return True
            await asyncio.sleep(0.1)
        return False


class SlidingWindowRateLimiter:
    """滑动窗口限流器"""
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._minute_window: deque = deque()
        self._hour_window: deque = deque()
        self._lock = Lock()
        
        # 令牌桶用于突发控制
        self._bucket = TokenBucket(
            rate=self.config.requests_per_minute / 60,
            capacity=self.config.burst_limit
        )
    
    def _clean_windows(self, now: float):
        """清理过期的请求记录"""
        minute_ago = now - 60
        hour_ago = now - 3600
        
        while self._minute_window and self._minute_window[0] < minute_ago:
            self._minute_window.popleft()
        
        while self._hour_window and self._hour_window[0] < hour_ago:
            self._hour_window.popleft()
    
    def can_proceed(self) -> tuple[bool, float]:
        """检查是否可以发送请求
        
        Returns:
            (是否可以继续, 需要等待的秒数)
        """
        with self._lock:
            now = time.time()
            self._clean_windows(now)
            
            # 检查分钟限制
            if len(self._minute_window) >= self.config.requests_per_minute:
                wait_time = 60 - (now - self._minute_window[0])
                return False, max(0, wait_time)
            
            # 检查小时限制
            if len(self._hour_window) >= self.config.requests_per_hour:
                wait_time = 3600 - (now - self._hour_window[0])
                return False, max(0, wait_time)
            
            # 检查突发限制
            if not self._bucket.acquire():
                return False, self.config.cooldown_seconds
            
            return True, 0
    
    def record_request(self):
        """记录一次请求"""
        with self._lock:
            now = time.time()
            self._minute_window.append(now)
            self._hour_window.append(now)
    
    async def wait_if_needed(self) -> bool:
        """如果需要则等待，返回是否可以继续"""
        can_proceed, wait_time = self.can_proceed()
        if not can_proceed and wait_time > 0:
            logger.info(f"[RateLimiter] 限流触发，等待 {wait_time:.1f} 秒")
            await asyncio.sleep(wait_time)
        
        self.record_request()
        return True


class MultiServiceRateLimiter:
    """多服务限流管理器"""
    
    def __init__(self):
        self._limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self._configs: Dict[str, RateLimitConfig] = {
            "duckduckgo": RateLimitConfig(requests_per_minute=20, requests_per_hour=200),
            "tavily": RateLimitConfig(requests_per_minute=60, requests_per_hour=1000),
            "baidu": RateLimitConfig(requests_per_minute=30, requests_per_hour=300),
            "openai": RateLimitConfig(requests_per_minute=50, requests_per_hour=500),
            "deepseek": RateLimitConfig(requests_per_minute=60, requests_per_hour=1000),
            "ollama": RateLimitConfig(requests_per_minute=100, requests_per_hour=5000),  # 本地服务限制宽松
            "default": RateLimitConfig(),
        }
    
    def get_limiter(self, service: str) -> SlidingWindowRateLimiter:
        """获取指定服务的限流器"""
        if service not in self._limiters:
            config = self._configs.get(service, self._configs["default"])
            self._limiters[service] = SlidingWindowRateLimiter(config)
        return self._limiters[service]
    
    async def acquire(self, service: str) -> bool:
        """获取服务访问权限"""
        limiter = self.get_limiter(service)
        return await limiter.wait_if_needed()


# 全局限流器实例
rate_limiter = MultiServiceRateLimiter()
