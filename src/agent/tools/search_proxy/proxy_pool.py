"""代理池管理 - 支持 HTTP/SOCKS 代理轮换，提高搜索稳定性"""

import os
import time
import random
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import json
import threading

logger = logging.getLogger(__name__)


class ProxyProtocol(Enum):
    """代理协议类型"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyStatus(Enum):
    """代理状态"""
    AVAILABLE = "available"      # 可用
    BUSY = "busy"                # 使用中
    FAILED = "failed"            # 失败
    COOLING = "cooling"          # 冷却中
    BANNED = "banned"            # 被封禁


@dataclass
class Proxy:
    """代理配置"""
    host: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    provider: str = "unknown"
    
    # 状态统计
    status: ProxyStatus = ProxyStatus.AVAILABLE
    last_used: float = 0
    last_check: float = 0
    fail_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    avg_response_time: float = 0
    
    # 冷却配置
    cooldown_until: float = 0
    
    def __post_init__(self):
        if isinstance(self.protocol, str):
            self.protocol = ProxyProtocol(self.protocol)
        if isinstance(self.status, str):
            self.status = ProxyStatus(self.status)
    
    @property
    def url(self) -> str:
        """生成代理 URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol.value}://{auth}{self.host}:{self.port}"
    
    @property
    def requests_config(self) -> Dict[str, str]:
        """生成 requests 库使用的代理配置"""
        proxy_url = self.url
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    @property
    def playwright_config(self) -> Dict[str, Any]:
        """生成 Playwright 使用的代理配置"""
        config = {
            "server": f"{self.protocol.value}://{self.host}:{self.port}"
        }
        if self.username and self.password:
            config["username"] = self.username
            config["password"] = self.password
        return config
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.fail_count + self.success_count
        if total == 0:
            return 1.0
        return self.success_count / total
    
    @property
    def score(self) -> float:
        """计算代理评分（用于选择最优代理）
        
        评分因素：
        - 成功率（权重 0.5）
        - 响应时间（权重 0.3）
        - 最近使用时间（权重 0.2）
        """
        # 成功率评分 (0-1)
        success_score = self.success_rate
        
        # 响应时间评分 (0-1)，假设 10 秒为最差
        time_score = max(0, 1 - self.avg_response_time / 10)
        
        # 空闲时间评分 (0-1)，空闲越久越好
        idle_time = time.time() - self.last_used
        idle_score = min(1, idle_time / 60)  # 1 分钟以上满分
        
        return success_score * 0.5 + time_score * 0.3 + idle_score * 0.2
    
    def is_available(self) -> bool:
        """检查代理是否可用"""
        if self.status == ProxyStatus.BANNED:
            return False
        if self.status == ProxyStatus.COOLING:
            if time.time() < self.cooldown_until:
                return False
            self.status = ProxyStatus.AVAILABLE
        return self.status == ProxyStatus.AVAILABLE
    
    def mark_success(self, response_time: float = 0):
        """标记请求成功"""
        self.success_count += 1
        self.total_requests += 1
        self.last_used = time.time()
        self.fail_count = 0  # 重置连续失败计数
        
        # 更新平均响应时间
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time * 0.7 + response_time * 0.3)
        
        self.status = ProxyStatus.AVAILABLE
    
    def mark_failure(self, cooldown: int = 60):
        """标记请求失败"""
        self.fail_count += 1
        self.total_requests += 1
        self.last_used = time.time()
        
        # 连续失败超过阈值则进入冷却
        if self.fail_count >= 3:
            self.status = ProxyStatus.COOLING
            self.cooldown_until = time.time() + cooldown * self.fail_count
            logger.warning(f"代理 {self.host}:{self.port} 连续失败 {self.fail_count} 次，冷却 {cooldown * self.fail_count} 秒")
        
        # 失败过多则标记为封禁
        if self.fail_count >= 10:
            self.status = ProxyStatus.BANNED
            logger.error(f"代理 {self.host}:{self.port} 失败过多，已被禁用")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol.value,
            "username": self.username,
            "password": self.password,
            "country": self.country,
            "provider": self.provider,
            "status": self.status.value,
            "last_used": self.last_used,
            "last_check": self.last_check,
            "fail_count": self.fail_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "avg_response_time": self.avg_response_time,
            "cooldown_until": self.cooldown_until
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Proxy":
        """从字典反序列化"""
        return cls(**data)
    
    @classmethod
    def from_url(cls, url: str, provider: str = "unknown") -> "Proxy":
        """从代理 URL 解析
        
        支持格式:
        - http://host:port
        - http://user:pass@host:port
        - socks5://host:port
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        protocol = ProxyProtocol(parsed.scheme) if parsed.scheme else ProxyProtocol.HTTP
        
        return cls(
            host=parsed.hostname or "",
            port=parsed.port or 80,
            protocol=protocol,
            username=parsed.username,
            password=parsed.password,
            provider=provider
        )


class ProxyPool:
    """代理池管理器
    
    功能特性：
    - 多来源代理聚合（配置文件、环境变量、API 获取）
    - 智能代理选择（基于成功率、响应时间、空闲时间）
    - 自动健康检查和故障转移
    - 代理轮换策略（轮询、随机、智能选择）
    - 状态持久化
    """
    
    def __init__(
        self,
        proxies: List[Proxy] = None,
        config_file: str = None,
        check_url: str = "https://httpbin.org/ip",
        check_timeout: int = 10,
        auto_check: bool = True,
        check_interval: int = 300,  # 5 分钟
        max_fail_count: int = 10,
        cooldown_time: int = 60,
        rotation_strategy: str = "smart"  # round_robin, random, smart
    ):
        """
        Args:
            proxies: 初始代理列表
            config_file: 代理配置文件路径
            check_url: 健康检查 URL
            check_timeout: 检查超时（秒）
            auto_check: 是否自动进行健康检查
            check_interval: 检查间隔（秒）
            max_fail_count: 最大失败次数
            cooldown_time: 冷却时间（秒）
            rotation_strategy: 轮换策略
        """
        self._proxies: List[Proxy] = proxies or []
        self._config_file = config_file
        self._check_url = check_url
        self._check_timeout = check_timeout
        self._auto_check = auto_check
        self._check_interval = check_interval
        self._max_fail_count = max_fail_count
        self._cooldown_time = cooldown_time
        self._rotation_strategy = rotation_strategy
        
        # 轮询索引
        self._round_robin_index = 0
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 健康检查线程
        self._check_thread: Optional[threading.Thread] = None
        self._stop_check = threading.Event()
        
        # 加载配置
        self._load_config()
        
        # 启动自动检查
        if auto_check and self._proxies:
            self._start_auto_check()
    
    def _load_config(self):
        """加载代理配置"""
        # 从配置文件加载
        if self._config_file and Path(self._config_file).exists():
            self._load_from_file(self._config_file)
        
        # 从环境变量加载
        self._load_from_env()
        
        logger.info(f"代理池已加载 {len(self._proxies)} 个代理")
    
    def _load_from_file(self, filepath: str):
        """从文件加载代理配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for proxy_data in data.get("proxies", []):
                proxy = Proxy.from_dict(proxy_data)
                self.add_proxy(proxy)
                
        except Exception as e:
            logger.error(f"加载代理配置文件失败: {e}")
    
    def _load_from_env(self):
        """从环境变量加载代理
        
        支持的环境变量:
        - PROXY_POOL: 逗号分隔的代理列表
        - HTTP_PROXY, HTTPS_PROXY: 单个代理
        - PROXY_API_URL: 代理 API 地址
        """
        # 从 PROXY_POOL 加载
        proxy_pool_str = os.getenv("PROXY_POOL", "")
        if proxy_pool_str:
            for url in proxy_pool_str.split(","):
                url = url.strip()
                if url:
                    try:
                        proxy = Proxy.from_url(url, provider="env")
                        self.add_proxy(proxy)
                    except Exception as e:
                        logger.warning(f"解析代理 URL 失败: {url}, {e}")
        
        # 从 HTTP_PROXY/HTTPS_PROXY 加载
        for env_name in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            proxy_url = os.getenv(env_name, "")
            if proxy_url and not any(p.url == proxy_url for p in self._proxies):
                try:
                    proxy = Proxy.from_url(proxy_url, provider="env")
                    self.add_proxy(proxy)
                except Exception:
                    pass
    
    def add_proxy(self, proxy: Proxy):
        """添加代理到池中"""
        with self._lock:
            # 检查是否已存在
            for p in self._proxies:
                if p.host == proxy.host and p.port == proxy.port:
                    return
            self._proxies.append(proxy)
    
    def add_proxies_from_urls(self, urls: List[str], provider: str = "manual"):
        """批量从 URL 添加代理"""
        for url in urls:
            try:
                proxy = Proxy.from_url(url, provider=provider)
                self.add_proxy(proxy)
            except Exception as e:
                logger.warning(f"解析代理 URL 失败: {url}, {e}")
    
    def remove_proxy(self, host: str, port: int):
        """移除代理"""
        with self._lock:
            self._proxies = [p for p in self._proxies if not (p.host == host and p.port == port)]
    
    def get_proxy(self) -> Optional[Proxy]:
        """获取一个可用的代理
        
        根据轮换策略选择代理
        """
        with self._lock:
            available = [p for p in self._proxies if p.is_available()]
            
            if not available:
                logger.warning("没有可用的代理")
                return None
            
            if self._rotation_strategy == "round_robin":
                # 轮询选择
                proxy = available[self._round_robin_index % len(available)]
                self._round_robin_index += 1
                
            elif self._rotation_strategy == "random":
                # 随机选择
                proxy = random.choice(available)
                
            else:  # smart
                # 智能选择（基于评分）
                proxy = max(available, key=lambda p: p.score)
            
            proxy.status = ProxyStatus.BUSY
            return proxy
    
    def release_proxy(self, proxy: Proxy, success: bool = True, response_time: float = 0):
        """释放代理并更新状态"""
        with self._lock:
            if success:
                proxy.mark_success(response_time)
            else:
                proxy.mark_failure(self._cooldown_time)
    
    def check_proxy(self, proxy: Proxy) -> bool:
        """检查单个代理是否可用"""
        try:
            import requests
            
            start_time = time.time()
            response = requests.get(
                self._check_url,
                proxies=proxy.requests_config,
                timeout=self._check_timeout
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                proxy.mark_success(response_time)
                proxy.last_check = time.time()
                return True
            
        except Exception as e:
            logger.debug(f"代理 {proxy.host}:{proxy.port} 检查失败: {e}")
        
        proxy.mark_failure(self._cooldown_time)
        proxy.last_check = time.time()
        return False
    
    def check_all_proxies(self):
        """检查所有代理"""
        logger.info("开始检查所有代理...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.check_proxy, self._proxies))
        
        available_count = sum(1 for r in results if r)
        logger.info(f"代理检查完成: {available_count}/{len(self._proxies)} 可用")
    
    def _start_auto_check(self):
        """启动自动检查线程"""
        def check_loop():
            while not self._stop_check.wait(self._check_interval):
                self.check_all_proxies()
        
        self._check_thread = threading.Thread(target=check_loop, daemon=True)
        self._check_thread.start()
        logger.info(f"代理自动检查已启动，间隔 {self._check_interval} 秒")
    
    def stop_auto_check(self):
        """停止自动检查"""
        if self._check_thread:
            self._stop_check.set()
            self._check_thread.join(timeout=1)
    
    def save_state(self, filepath: str = None):
        """保存代理池状态"""
        filepath = filepath or self._config_file or "./config/proxy_pool.json"
        
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "proxies": [p.to_dict() for p in self._proxies],
                    "rotation_strategy": self._rotation_strategy,
                    "check_url": self._check_url,
                    "saved_at": time.time()
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"代理池状态已保存到 {filepath}")
            
        except Exception as e:
            logger.error(f"保存代理池状态失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取代理池统计信息"""
        with self._lock:
            total = len(self._proxies)
            available = sum(1 for p in self._proxies if p.is_available())
            banned = sum(1 for p in self._proxies if p.status == ProxyStatus.BANNED)
            cooling = sum(1 for p in self._proxies if p.status == ProxyStatus.COOLING)
            
            total_requests = sum(p.total_requests for p in self._proxies)
            total_success = sum(p.success_count for p in self._proxies)
            
            return {
                "total": total,
                "available": available,
                "banned": banned,
                "cooling": cooling,
                "busy": total - available - banned - cooling,
                "total_requests": total_requests,
                "total_success": total_success,
                "success_rate": total_success / total_requests if total_requests > 0 else 0,
                "avg_response_time": sum(p.avg_response_time for p in self._proxies) / total if total > 0 else 0
            }
    
    def list_proxies(self) -> List[Dict[str, Any]]:
        """列出所有代理及其状态"""
        with self._lock:
            return [
                {
                    "url": p.url,
                    "status": p.status.value,
                    "success_rate": f"{p.success_rate:.1%}",
                    "avg_response_time": f"{p.avg_response_time:.2f}s",
                    "total_requests": p.total_requests,
                    "score": f"{p.score:.3f}",
                    "provider": p.provider
                }
                for p in self._proxies
            ]
    
    def __len__(self) -> int:
        return len(self._proxies)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_auto_check()
        self.save_state()


class ProxyPoolContext:
    """代理池上下文管理器 - 自动获取和释放代理"""
    
    def __init__(self, pool: ProxyPool):
        self.pool = pool
        self.proxy: Optional[Proxy] = None
        self.start_time: float = 0
    
    def __enter__(self) -> Optional[Proxy]:
        self.proxy = self.pool.get_proxy()
        self.start_time = time.time()
        return self.proxy
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.proxy:
            success = exc_type is None
            response_time = time.time() - self.start_time
            self.pool.release_proxy(self.proxy, success, response_time)


# 获取代理池的装饰器
def with_proxy(pool: ProxyPool):
    """代理池装饰器 - 自动为请求添加代理
    
    使用示例:
    ```python
    pool = ProxyPool()
    
    @with_proxy(pool)
    def fetch_url(url: str, proxy: Proxy = None):
        requests.get(url, proxies=proxy.requests_config if proxy else None)
    ```
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            with ProxyPoolContext(pool) as proxy:
                kwargs["proxy"] = proxy
                return func(*args, **kwargs)
        return wrapper
    return decorator


# 全局代理池实例
_global_pool: Optional[ProxyPool] = None


def get_proxy_pool() -> ProxyPool:
    """获取全局代理池实例"""
    global _global_pool
    if _global_pool is None:
        _global_pool = ProxyPool(
            config_file="./config/proxy_pool.json",
            auto_check=True
        )
    return _global_pool


def init_proxy_pool(
    proxies: List[str] = None,
    config_file: str = None,
    **kwargs
) -> ProxyPool:
    """初始化全局代理池
    
    Args:
        proxies: 代理 URL 列表
        config_file: 配置文件路径
        **kwargs: 其他 ProxyPool 参数
    """
    global _global_pool
    
    proxy_objects = []
    if proxies:
        for url in proxies:
            try:
                proxy_objects.append(Proxy.from_url(url))
            except Exception as e:
                logger.warning(f"解析代理 URL 失败: {url}, {e}")
    
    _global_pool = ProxyPool(
        proxies=proxy_objects,
        config_file=config_file,
        **kwargs
    )
    
    return _global_pool
