"""断路器模式实现 - 防止服务雪崩

参考: https://martinfowler.com/bliki/CircuitBreaker.html
"""

import time
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Callable, Any, Optional
from threading import Lock
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"      # 正常，允许请求通过
    OPEN = "open"          # 断开，拒绝所有请求
    HALF_OPEN = "half_open"  # 半开，允许少量请求测试


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5          # 失败阈值，超过则断开
    success_threshold: int = 3          # 半开状态成功阈值
    timeout: float = 60.0               # 断开后多久尝试恢复（秒）
    half_open_max_calls: int = 3        # 半开状态最大调用数


class CircuitBreaker:
    """断路器实现"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = Lock()
    
    def _should_allow_request(self) -> bool:
        """判断是否允许请求通过"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # 检查是否超时，可以尝试半开
                if self.last_failure_time and \
                   time.time() - self.last_failure_time >= self.config.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    self.success_count = 0
                    logger.info(f"[CircuitBreaker:{self.name}] 状态转换: OPEN -> HALF_OPEN")
                    return True
                return False
            
            # HALF_OPEN 状态
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False
    
    def record_success(self):
        """记录成功调用"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"[CircuitBreaker:{self.name}] 状态转换: HALF_OPEN -> CLOSED")
            elif self.state == CircuitState.CLOSED:
                # 成功时逐渐减少失败计数
                self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """记录失败调用"""
        with self._lock:
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即断开
                self.state = CircuitState.OPEN
                logger.warning(f"[CircuitBreaker:{self.name}] 状态转换: HALF_OPEN -> OPEN (测试失败)")
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(f"[CircuitBreaker:{self.name}] 状态转换: CLOSED -> OPEN (失败次数: {self.failure_count})")
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time
        }


class CircuitBreakerManager:
    """断路器管理器"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._configs: Dict[str, CircuitBreakerConfig] = {
            "llm": CircuitBreakerConfig(failure_threshold=3, timeout=30),
            "web_search": CircuitBreakerConfig(failure_threshold=5, timeout=60),
            "vector_store": CircuitBreakerConfig(failure_threshold=3, timeout=120),
            "default": CircuitBreakerConfig()
        }
    
    def get_breaker(self, name: str) -> CircuitBreaker:
        """获取断路器"""
        if name not in self._breakers:
            config = self._configs.get(name, self._configs["default"])
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get_all_states(self) -> Dict[str, Dict]:
        """获取所有断路器状态"""
        return {name: breaker.get_state() for name, breaker in self._breakers.items()}


# 全局断路器管理器
circuit_manager = CircuitBreakerManager()


def with_circuit_breaker(breaker_name: str, fallback: Callable = None):
    """断路器装饰器
    
    用法:
        @with_circuit_breaker("llm", fallback=lambda: "服务暂时不可用")
        async def call_llm(prompt):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            breaker = circuit_manager.get_breaker(breaker_name)
            
            if not breaker._should_allow_request():
                logger.warning(f"[CircuitBreaker:{breaker_name}] 请求被拒绝 (状态: {breaker.state.value})")
                if fallback:
                    return fallback()
                raise Exception(f"服务 {breaker_name} 暂时不可用 (断路器断开)")
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            breaker = circuit_manager.get_breaker(breaker_name)
            
            if not breaker._should_allow_request():
                logger.warning(f"[CircuitBreaker:{breaker_name}] 请求被拒绝")
                if fallback:
                    return fallback()
                raise Exception(f"服务 {breaker_name} 暂时不可用")
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
