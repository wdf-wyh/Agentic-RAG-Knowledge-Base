"""SearXNG 搜索客户端

SearXNG 是一个开源的元搜索引擎，可以自托管，聚合多个搜索引擎的结果。
官方文档: https://docs.searxng.org/
"""

import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import logging

from .base import SearchProxyBase, SearchResult, SearchEngine

logger = logging.getLogger(__name__)


class SearXNGClient(SearchProxyBase):
    """SearXNG 搜索客户端
    
    连接自托管的 SearXNG 实例，执行隐私友好的搜索。
    
    部署方式:
        docker run -d --name searxng -p 8080:8080 searxng/searxng
    
    使用示例:
        client = SearXNGClient("http://localhost:8080")
        results = client.search("Python 教程", max_results=10)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: int = 30,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Args:
            base_url: SearXNG 实例地址
            timeout: 请求超时时间（秒）
            cache_enabled: 是否启用缓存
            cache_ttl: 缓存有效期（秒）
        """
        super().__init__(cache_enabled, cache_ttl)
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session = requests.Session()
        
    @property
    def name(self) -> str:
        return "searxng"
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        categories: List[str] = None,
        engines: List[str] = None,
        language: str = "zh-CN",
        time_range: str = None,
        safe_search: int = 0
    ) -> List[SearchResult]:
        """执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            categories: 搜索类别 ['general', 'images', 'news', 'science', 'files', 'it']
            engines: 指定搜索引擎 ['google', 'bing', 'duckduckgo', 'wikipedia', etc.]
            language: 搜索语言
            time_range: 时间范围 ['day', 'week', 'month', 'year']
            safe_search: 安全搜索 (0=关闭, 1=中等, 2=严格)
            
        Returns:
            搜索结果列表
        """
        params = {
            "q": query,
            "format": "json",
            "language": language,
            "safesearch": safe_search,
        }
        
        if categories:
            params["categories"] = ",".join(categories)
        if engines:
            params["engines"] = ",".join(engines)
        if time_range:
            params["time_range"] = time_range
        
        try:
            response = self._session.get(
                urljoin(self.base_url, "/search"),
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for i, item in enumerate(data.get("results", [])[:max_results]):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source=item.get("engine", "searxng"),
                    score=1.0 - (i * 0.05),  # 简单的位置评分
                    metadata={
                        "engines": item.get("engines", []),
                        "parsed_url": item.get("parsed_url", {}),
                        "category": item.get("category", "")
                    }
                )
                results.append(result)
            
            logger.info(f"SearXNG 搜索 '{query}' 返回 {len(results)} 个结果")
            return results
            
        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到 SearXNG: {self.base_url}")
            raise ConnectionError(f"无法连接到 SearXNG 服务: {self.base_url}，请确保服务已启动")
        except requests.exceptions.Timeout:
            logger.error(f"SearXNG 搜索超时: {query}")
            raise TimeoutError(f"搜索超时，请重试")
        except Exception as e:
            logger.error(f"SearXNG 搜索失败: {e}")
            raise
    
    def search_images(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """搜索图片"""
        return self.search(query, max_results, categories=["images"])
    
    def search_news(self, query: str, max_results: int = 10, time_range: str = "week") -> List[SearchResult]:
        """搜索新闻"""
        return self.search(query, max_results, categories=["news"], time_range=time_range)
    
    def search_academic(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """搜索学术内容"""
        return self.search(
            query, 
            max_results, 
            categories=["science"],
            engines=["google scholar", "arxiv", "semantic scholar"]
        )
    
    def get_engines(self) -> Dict[str, Any]:
        """获取可用的搜索引擎列表"""
        try:
            response = self._session.get(
                urljoin(self.base_url, "/config"),
                timeout=self.timeout
            )
            response.raise_for_status()
            config = response.json()
            return config.get("engines", {})
        except Exception as e:
            logger.error(f"获取 SearXNG 引擎列表失败: {e}")
            return {}
    
    def is_available(self) -> bool:
        """检查 SearXNG 服务是否可用"""
        try:
            response = self._session.get(
                urljoin(self.base_url, "/healthz"),
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            # 尝试备用方式
            try:
                response = self._session.get(
                    self.base_url,
                    timeout=5
                )
                return response.status_code == 200
            except Exception:
                return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取 SearXNG 统计信息"""
        try:
            response = self._session.get(
                urljoin(self.base_url, "/stats"),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}


class SearXNGPoolClient(SearchProxyBase):
    """SearXNG 实例池
    
    管理多个 SearXNG 实例，实现负载均衡和故障转移。
    """
    
    def __init__(
        self,
        instances: List[str] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Args:
            instances: SearXNG 实例地址列表
            cache_enabled: 是否启用缓存
            cache_ttl: 缓存有效期
        """
        super().__init__(cache_enabled, cache_ttl)
        
        # 默认的公共 SearXNG 实例（备用）
        default_instances = [
            "https://searx.be",
            "https://search.bus-hit.me",
            "https://searx.tiekoetter.com",
        ]
        
        self.instances = instances or default_instances
        self._clients: Dict[str, SearXNGClient] = {}
        self._instance_status: Dict[str, bool] = {}
        
        # 初始化客户端
        for url in self.instances:
            self._clients[url] = SearXNGClient(url, cache_enabled=False)
            self._instance_status[url] = True
    
    @property
    def name(self) -> str:
        return "searxng_pool"
    
    def _get_available_client(self) -> Optional[SearXNGClient]:
        """获取可用的客户端"""
        for url, is_available in self._instance_status.items():
            if is_available:
                client = self._clients[url]
                if client.is_available():
                    return client
                else:
                    self._instance_status[url] = False
        
        # 所有实例不可用，重置状态重试
        for url in self._instance_status:
            self._instance_status[url] = True
        
        return None
    
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """在可用实例上执行搜索"""
        client = self._get_available_client()
        if not client:
            raise ConnectionError("所有 SearXNG 实例都不可用")
        
        try:
            return client.search(query, max_results, **kwargs)
        except Exception as e:
            # 标记当前实例为不可用
            self._instance_status[client.base_url] = False
            # 尝试下一个实例
            return self.search(query, max_results, **kwargs)
    
    def is_available(self) -> bool:
        """检查是否有可用实例"""
        return any(
            client.is_available() 
            for client in self._clients.values()
        )
    
    def refresh_status(self):
        """刷新所有实例的状态"""
        for url, client in self._clients.items():
            self._instance_status[url] = client.is_available()
