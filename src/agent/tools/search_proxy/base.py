"""搜索代理基类和通用数据结构"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import time
import hashlib
import json
from pathlib import Path


class SearchEngine(Enum):
    """支持的搜索引擎"""
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"
    BAIDU = "baidu"
    SEARXNG = "searxng"
    

@dataclass
class SearchResult:
    """统一的搜索结果格式"""
    title: str
    url: str
    snippet: str
    source: str = ""  # 来源搜索引擎
    score: float = 0.0  # 相关性评分
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "score": self.score,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class ProxyConfig:
    """代理配置"""
    host: str
    port: int
    protocol: str = "http"  # http, https, socks5
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    last_used: float = 0
    fail_count: int = 0
    success_count: int = 0
    
    @property
    def url(self) -> str:
        """生成代理 URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.fail_count + self.success_count
        if total == 0:
            return 1.0
        return self.success_count / total


class SearchCache:
    """搜索结果缓存"""
    
    def __init__(self, cache_dir: str = "./cache/search", ttl: int = 3600):
        """
        Args:
            cache_dir: 缓存目录
            ttl: 缓存有效期（秒），默认 1 小时
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._memory_cache: Dict[str, Any] = {}
    
    def _get_cache_key(self, query: str, engine: str = "") -> str:
        """生成缓存键"""
        content = f"{query}:{engine}".encode()
        return hashlib.md5(content).hexdigest()
    
    def get(self, query: str, engine: str = "") -> Optional[List[SearchResult]]:
        """获取缓存的搜索结果"""
        cache_key = self._get_cache_key(query, engine)
        
        # 先检查内存缓存
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if time.time() - cached["timestamp"] < self.ttl:
                return cached["results"]
        
        # 检查文件缓存
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                if time.time() - cached["timestamp"] < self.ttl:
                    results = [SearchResult(**r) for r in cached["results"]]
                    # 加载到内存
                    self._memory_cache[cache_key] = {
                        "timestamp": cached["timestamp"],
                        "results": results
                    }
                    return results
            except Exception:
                pass
        
        return None
    
    def set(self, query: str, results: List[SearchResult], engine: str = ""):
        """缓存搜索结果"""
        cache_key = self._get_cache_key(query, engine)
        timestamp = time.time()
        
        # 内存缓存
        self._memory_cache[cache_key] = {
            "timestamp": timestamp,
            "results": results
        }
        
        # 文件缓存
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": query,
                    "engine": engine,
                    "timestamp": timestamp,
                    "results": [r.to_dict() for r in results]
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def clear(self, max_age: Optional[int] = None):
        """清理缓存
        
        Args:
            max_age: 清理超过指定秒数的缓存，None 表示清理全部
        """
        self._memory_cache.clear()
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                if max_age is None:
                    cache_file.unlink()
                else:
                    mtime = cache_file.stat().st_mtime
                    if time.time() - mtime > max_age:
                        cache_file.unlink()
            except Exception:
                pass


class SearchProxyBase(ABC):
    """搜索代理基类"""
    
    def __init__(self, cache_enabled: bool = True, cache_ttl: int = 3600):
        self.cache_enabled = cache_enabled
        self._cache = SearchCache(ttl=cache_ttl) if cache_enabled else None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """代理名称"""
        pass
    
    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            **kwargs: 其他参数
            
        Returns:
            搜索结果列表
        """
        pass
    
    def search_with_cache(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """带缓存的搜索"""
        if self._cache:
            cached = self._cache.get(query, self.name)
            if cached:
                return cached[:max_results]
        
        results = self.search(query, max_results, **kwargs)
        
        if self._cache and results:
            self._cache.set(query, results, self.name)
        
        return results
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查代理是否可用"""
        pass
