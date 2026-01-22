"""本地搜索代理模块

提供多种搜索代理方案，绕过搜索引擎的限制：
1. SearXNG - 自托管元搜索引擎
2. Playwright - 无头浏览器模拟真人搜索
3. ProxyPool - 代理池管理，支持 HTTP/SOCKS 代理轮换
4. RequestScatterer - 请求分散，模拟人类行为防检测
"""

from .base import SearchProxyBase, SearchResult, SearchCache, SearchEngine
from .searxng_client import SearXNGClient
from .playwright_search import PlaywrightSearch
from .proxy_pool import (
    Proxy,
    ProxyPool,
    ProxyProtocol,
    ProxyStatus,
    ProxyPoolContext,
    get_proxy_pool,
    init_proxy_pool,
    with_proxy
)
from .request_scatterer import (
    RequestScatterer,
    RequestPattern,
    DomainConfig,
    ScatteredRequest,
    scattered_request,
    get_scatterer,
    init_scatterer,
    create_scatterer_with_presets,
    PRESETS as SCATTERER_PRESETS
)

__all__ = [
    # 基础类
    "SearchProxyBase",
    "SearchResult",
    "SearchCache",
    "SearchEngine",
    # 搜索客户端
    "SearXNGClient",
    "PlaywrightSearch",
    # 代理池
    "Proxy",
    "ProxyPool",
    "ProxyProtocol",
    "ProxyStatus",
    "ProxyPoolContext",
    "get_proxy_pool",
    "init_proxy_pool",
    "with_proxy",
    # 请求分散
    "RequestScatterer",
    "RequestPattern",
    "DomainConfig",
    "ScatteredRequest",
    "scattered_request",
    "get_scatterer",
    "init_scatterer",
    "create_scatterer_with_presets",
    "SCATTERER_PRESETS",
]
