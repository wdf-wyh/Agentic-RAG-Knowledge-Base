"""请求分散器 - 模拟人类行为，防止被反爬虫系统检测"""

import time
import random
import logging
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import hashlib

logger = logging.getLogger(__name__)


class RequestPattern(Enum):
    """请求模式"""
    HUMAN = "human"          # 模拟人类（随机延迟，不规则）
    GENTLE = "gentle"        # 温和模式（固定慢速）
    BURST = "burst"          # 突发模式（快速请求后长休息）
    ADAPTIVE = "adaptive"    # 自适应（根据响应调整）


@dataclass
class DomainConfig:
    """域名级别的配置"""
    domain: str
    min_delay: float = 1.0          # 最小延迟（秒）
    max_delay: float = 5.0          # 最大延迟（秒）
    requests_per_minute: int = 10   # 每分钟最大请求数
    burst_size: int = 3             # 突发请求数
    burst_delay: float = 10.0       # 突发后休息时间
    last_request: float = 0         # 上次请求时间
    request_count: int = 0          # 请求计数
    request_history: deque = field(default_factory=lambda: deque(maxlen=60))
    
    def __post_init__(self):
        if not isinstance(self.request_history, deque):
            self.request_history = deque(maxlen=60)


@dataclass
class RequestContext:
    """请求上下文"""
    url: str
    domain: str
    method: str = "GET"
    start_time: float = 0
    end_time: float = 0
    success: bool = False
    status_code: int = 0
    retry_count: int = 0


class RequestScatterer:
    """请求分散器
    
    功能特性：
    - 随机延迟：模拟人类不规则的请求间隔
    - 域名级限速：每个域名独立的速率控制
    - 请求指纹随机化：User-Agent、Headers 随机化
    - 突发检测和自动减速
    - 自适应延迟调整
    """
    
    # 常用 User-Agent 列表
    USER_AGENTS = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]
    
    # 常用 Accept-Language
    ACCEPT_LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "zh-CN,zh;q=0.9,en;q=0.8",
        "zh-TW,zh;q=0.9,en;q=0.8",
        "ja-JP,ja;q=0.9,en;q=0.8",
        "ko-KR,ko;q=0.9,en;q=0.8",
        "de-DE,de;q=0.9,en;q=0.8",
        "fr-FR,fr;q=0.9,en;q=0.8",
    ]
    
    # 屏幕分辨率
    SCREEN_RESOLUTIONS = [
        "1920x1080", "2560x1440", "1366x768", "1536x864",
        "1440x900", "1280x720", "3840x2160", "2560x1080"
    ]
    
    def __init__(
        self,
        pattern: RequestPattern = RequestPattern.HUMAN,
        default_min_delay: float = 1.0,
        default_max_delay: float = 5.0,
        global_rate_limit: int = 60,  # 全局每分钟最大请求
        enable_fingerprint_rotation: bool = True,
        enable_adaptive: bool = True
    ):
        """
        Args:
            pattern: 请求模式
            default_min_delay: 默认最小延迟（秒）
            default_max_delay: 默认最大延迟（秒）
            global_rate_limit: 全局每分钟最大请求数
            enable_fingerprint_rotation: 是否启用指纹轮换
            enable_adaptive: 是否启用自适应调整
        """
        self._pattern = pattern
        self._default_min_delay = default_min_delay
        self._default_max_delay = default_max_delay
        self._global_rate_limit = global_rate_limit
        self._enable_fingerprint = enable_fingerprint_rotation
        self._enable_adaptive = enable_adaptive
        
        # 域名配置缓存
        self._domain_configs: Dict[str, DomainConfig] = {}
        
        # 全局请求历史
        self._global_history: deque = deque(maxlen=120)
        
        # 当前指纹
        self._current_fingerprint: Dict[str, str] = {}
        self._fingerprint_rotate_count = 0
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 初始化指纹
        self._rotate_fingerprint()
    
    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]
    
    def _get_domain_config(self, domain: str) -> DomainConfig:
        """获取域名配置"""
        if domain not in self._domain_configs:
            self._domain_configs[domain] = DomainConfig(
                domain=domain,
                min_delay=self._default_min_delay,
                max_delay=self._default_max_delay
            )
        return self._domain_configs[domain]
    
    def set_domain_config(
        self,
        domain: str,
        min_delay: float = None,
        max_delay: float = None,
        requests_per_minute: int = None,
        burst_size: int = None,
        burst_delay: float = None
    ):
        """设置域名级别的配置
        
        Args:
            domain: 域名
            min_delay: 最小延迟
            max_delay: 最大延迟
            requests_per_minute: 每分钟最大请求数
            burst_size: 突发请求数
            burst_delay: 突发后休息时间
        """
        config = self._get_domain_config(domain)
        
        if min_delay is not None:
            config.min_delay = min_delay
        if max_delay is not None:
            config.max_delay = max_delay
        if requests_per_minute is not None:
            config.requests_per_minute = requests_per_minute
        if burst_size is not None:
            config.burst_size = burst_size
        if burst_delay is not None:
            config.burst_delay = burst_delay
    
    def _calculate_delay(self, domain_config: DomainConfig) -> float:
        """计算下次请求的延迟时间"""
        now = time.time()
        
        # 清理过期的请求历史
        while domain_config.request_history and \
              now - domain_config.request_history[0] > 60:
            domain_config.request_history.popleft()
        
        # 检查速率限制
        recent_requests = len(domain_config.request_history)
        
        if recent_requests >= domain_config.requests_per_minute:
            # 已达到速率限制，等待到下一个窗口
            oldest = domain_config.request_history[0]
            wait_time = 60 - (now - oldest) + random.uniform(1, 3)
            logger.debug(f"域名 {domain_config.domain} 达到速率限制，等待 {wait_time:.1f}s")
            return wait_time
        
        # 根据模式计算延迟
        if self._pattern == RequestPattern.HUMAN:
            # 人类模式：使用正态分布
            mean = (domain_config.min_delay + domain_config.max_delay) / 2
            std = (domain_config.max_delay - domain_config.min_delay) / 4
            delay = max(domain_config.min_delay, random.gauss(mean, std))
            
            # 偶尔添加额外的"思考时间"
            if random.random() < 0.1:  # 10% 概率
                delay += random.uniform(2, 8)
            
        elif self._pattern == RequestPattern.GENTLE:
            # 温和模式：固定较长延迟
            delay = domain_config.max_delay
            
        elif self._pattern == RequestPattern.BURST:
            # 突发模式：快速请求后长休息
            domain_config.request_count += 1
            
            if domain_config.request_count >= domain_config.burst_size:
                domain_config.request_count = 0
                delay = domain_config.burst_delay + random.uniform(0, 5)
            else:
                delay = domain_config.min_delay * 0.5
                
        else:  # ADAPTIVE
            # 自适应模式：基于历史响应调整
            base_delay = (domain_config.min_delay + domain_config.max_delay) / 2
            
            # 根据最近请求密度调整
            density = recent_requests / domain_config.requests_per_minute
            delay = base_delay * (1 + density)
            
            # 添加随机抖动
            delay *= random.uniform(0.8, 1.2)
        
        return max(0, delay)
    
    def _rotate_fingerprint(self):
        """轮换请求指纹"""
        self._current_fingerprint = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept-Language": random.choice(self.ACCEPT_LANGUAGES),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": random.choice(["none", "same-origin", "cross-site"]),
            "Sec-Fetch-User": "?1",
            "Cache-Control": random.choice(["max-age=0", "no-cache"]),
        }
        
        # 可选的额外 headers
        if random.random() > 0.5:
            self._current_fingerprint["DNT"] = "1"
        
        self._fingerprint_rotate_count = 0
        logger.debug("已轮换请求指纹")
    
    def get_headers(self, url: str = None, rotate: bool = False) -> Dict[str, str]:
        """获取随机化的请求头
        
        Args:
            url: 请求 URL（用于设置 Referer）
            rotate: 是否强制轮换指纹
        """
        with self._lock:
            # 定期轮换指纹（每 10-20 次请求）
            self._fingerprint_rotate_count += 1
            if rotate or self._fingerprint_rotate_count > random.randint(10, 20):
                self._rotate_fingerprint()
            
            headers = self._current_fingerprint.copy()
            
            # 设置 Referer
            if url:
                domain = self._extract_domain(url)
                referer_options = [
                    f"https://{domain}/",
                    f"https://www.google.com/search?q={domain}",
                    f"https://www.bing.com/search?q={domain}",
                    None  # 无 Referer
                ]
                referer = random.choice(referer_options)
                if referer:
                    headers["Referer"] = referer
            
            return headers
    
    def wait_before_request(self, url: str) -> float:
        """请求前等待（阻塞）
        
        Args:
            url: 请求 URL
            
        Returns:
            实际等待的时间（秒）
        """
        domain = self._extract_domain(url)
        
        with self._lock:
            config = self._get_domain_config(domain)
            
            # 计算需要等待的时间
            now = time.time()
            time_since_last = now - config.last_request
            delay = self._calculate_delay(config)
            
            # 如果距离上次请求时间不够，需要额外等待
            if time_since_last < delay:
                actual_delay = delay - time_since_last
            else:
                actual_delay = 0
        
        # 执行等待（在锁外进行，避免阻塞其他线程）
        if actual_delay > 0:
            logger.debug(f"请求 {domain} 等待 {actual_delay:.2f}s")
            time.sleep(actual_delay)
        
        # 更新请求记录
        with self._lock:
            now = time.time()
            config.last_request = now
            config.request_history.append(now)
            self._global_history.append(now)
        
        return actual_delay
    
    def record_response(
        self,
        url: str,
        success: bool,
        status_code: int = 200,
        response_time: float = 0
    ):
        """记录响应结果（用于自适应调整）
        
        Args:
            url: 请求 URL
            success: 是否成功
            status_code: HTTP 状态码
            response_time: 响应时间
        """
        if not self._enable_adaptive:
            return
        
        domain = self._extract_domain(url)
        
        with self._lock:
            config = self._get_domain_config(domain)
            
            # 根据响应调整延迟
            if not success or status_code == 429:  # Too Many Requests
                # 被限制，增加延迟
                config.min_delay *= 1.5
                config.max_delay *= 1.5
                config.requests_per_minute = max(1, config.requests_per_minute // 2)
                logger.warning(f"域名 {domain} 检测到限制，增加延迟")
                
            elif status_code == 503:  # Service Unavailable
                # 服务不可用，大幅增加延迟
                config.min_delay *= 2
                config.max_delay *= 2
                logger.warning(f"域名 {domain} 服务不可用，大幅增加延迟")
                
            elif success and response_time < 1:
                # 响应正常且快速，可以适当减少延迟
                config.min_delay = max(self._default_min_delay * 0.8, config.min_delay * 0.95)
                config.max_delay = max(self._default_max_delay * 0.8, config.max_delay * 0.95)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            now = time.time()
            
            # 全局统计
            recent_global = sum(1 for t in self._global_history if now - t < 60)
            
            # 域名统计
            domain_stats = {}
            for domain, config in self._domain_configs.items():
                recent = sum(1 for t in config.request_history if now - t < 60)
                domain_stats[domain] = {
                    "requests_last_minute": recent,
                    "limit_per_minute": config.requests_per_minute,
                    "min_delay": f"{config.min_delay:.2f}s",
                    "max_delay": f"{config.max_delay:.2f}s",
                    "last_request": time.strftime("%H:%M:%S", time.localtime(config.last_request)) if config.last_request else "never"
                }
            
            return {
                "pattern": self._pattern.value,
                "global_requests_last_minute": recent_global,
                "global_rate_limit": self._global_rate_limit,
                "fingerprint_rotations": self._fingerprint_rotate_count,
                "domains": domain_stats
            }


class ScatteredRequest:
    """分散请求的上下文管理器
    
    使用示例:
    ```python
    scatterer = RequestScatterer()
    
    with ScatteredRequest(scatterer, url) as headers:
        response = requests.get(url, headers=headers)
    ```
    """
    
    def __init__(self, scatterer: RequestScatterer, url: str):
        self.scatterer = scatterer
        self.url = url
        self.start_time = 0
        self.headers = {}
    
    def __enter__(self) -> Dict[str, str]:
        # 等待
        self.scatterer.wait_before_request(self.url)
        # 获取 headers
        self.headers = self.scatterer.get_headers(self.url)
        self.start_time = time.time()
        return self.headers
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        response_time = time.time() - self.start_time
        self.scatterer.record_response(
            self.url,
            success=success,
            response_time=response_time
        )


def scattered_request(scatterer: RequestScatterer):
    """请求分散装饰器
    
    使用示例:
    ```python
    scatterer = RequestScatterer()
    
    @scattered_request(scatterer)
    def fetch_page(url: str, headers: dict = None):
        return requests.get(url, headers=headers)
    ```
    """
    def decorator(func: Callable):
        def wrapper(url: str, *args, **kwargs):
            with ScatteredRequest(scatterer, url) as headers:
                # 合并 headers
                if "headers" in kwargs:
                    kwargs["headers"].update(headers)
                else:
                    kwargs["headers"] = headers
                return func(url, *args, **kwargs)
        return wrapper
    return decorator


# 预设配置
PRESETS = {
    # 搜索引擎配置
    "google.com": {
        "min_delay": 2.0,
        "max_delay": 8.0,
        "requests_per_minute": 5
    },
    "bing.com": {
        "min_delay": 1.5,
        "max_delay": 5.0,
        "requests_per_minute": 10
    },
    "duckduckgo.com": {
        "min_delay": 1.0,
        "max_delay": 3.0,
        "requests_per_minute": 15
    },
    "baidu.com": {
        "min_delay": 1.0,
        "max_delay": 4.0,
        "requests_per_minute": 10
    },
    # 通用网站
    "default": {
        "min_delay": 1.0,
        "max_delay": 5.0,
        "requests_per_minute": 20
    }
}


def create_scatterer_with_presets(
    pattern: RequestPattern = RequestPattern.HUMAN,
    **kwargs
) -> RequestScatterer:
    """创建带有预设配置的请求分散器"""
    scatterer = RequestScatterer(pattern=pattern, **kwargs)
    
    for domain, config in PRESETS.items():
        if domain != "default":
            scatterer.set_domain_config(domain, **config)
    
    return scatterer


# 全局实例
_global_scatterer: Optional[RequestScatterer] = None


def get_scatterer() -> RequestScatterer:
    """获取全局请求分散器实例"""
    global _global_scatterer
    if _global_scatterer is None:
        _global_scatterer = create_scatterer_with_presets()
    return _global_scatterer


def init_scatterer(
    pattern: RequestPattern = RequestPattern.HUMAN,
    **kwargs
) -> RequestScatterer:
    """初始化全局请求分散器"""
    global _global_scatterer
    _global_scatterer = RequestScatterer(pattern=pattern, **kwargs)
    return _global_scatterer
