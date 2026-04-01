"""聚合搜索引擎工具 - 同时查询多个免费搜索引擎，交叉验证提高精准度"""

import logging
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse, urlunparse, unquote
from dataclasses import dataclass, field

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


@dataclass
class AggregatedResult:
    """聚合搜索结果"""
    title: str
    url: str
    snippet: str
    sources: List[str] = field(default_factory=list)  # 出现在哪些引擎
    source_ranks: Dict[str, int] = field(default_factory=dict)  # 各引擎中的排名
    relevance_score: float = 0.0  # 最终相关性分数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "sources": self.sources,
            "source_count": len(self.sources),
            "relevance_score": round(self.relevance_score, 3),
        }


def _normalize_url(url: str) -> str:
    """规范化 URL 用于去重"""
    try:
        parsed = urlparse(url.lower().rstrip("/"))
        # 去除 www. 前缀、tracking 参数等
        netloc = parsed.netloc.replace("www.", "")
        # 移除常见跟踪参数
        path = parsed.path.rstrip("/")
        return urlunparse(("", netloc, path, "", "", ""))
    except Exception:
        return url.lower().strip().rstrip("/")


class _SearchEngines:
    """各搜索引擎的实现"""

    @staticmethod
    def duckduckgo(query: str, max_results: int = 8) -> List[Dict]:
        """DuckDuckGo 搜索"""
        try:
            from duckduckgo_search import DDGS

            with DDGS(timeout=15) as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "DuckDuckGo",
                }
                for r in results
                if r.get("href")
            ]
        except Exception as e:
            logger.debug(f"DuckDuckGo 搜索失败: {e}")
            return []

    @staticmethod
    def bing(query: str, max_results: int = 8) -> List[Dict]:
        """必应搜索（网页抓取）"""
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            url = f"https://cn.bing.com/search?q={requests.utils.quote(query)}&count={max_results + 5}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            results = []
            for item in soup.find_all("li", class_="b_algo"):
                title_el = item.find("h2")
                link_el = item.find("a") if title_el else None
                snippet_el = item.find("p")
                if title_el and link_el and link_el.get("href"):
                    results.append(
                        {
                            "title": title_el.get_text(strip=True),
                            "url": link_el["href"],
                            "snippet": snippet_el.get_text(strip=True)[:300] if snippet_el else "",
                            "source": "Bing",
                        }
                    )
                    if len(results) >= max_results:
                        break
            return results
        except Exception as e:
            logger.debug(f"Bing 搜索失败: {e}")
            return []

    @staticmethod
    def brave(query: str, max_results: int = 8, api_key: str = "") -> List[Dict]:
        """Brave Search API（免费 2000 次/月）"""
        import os

        key = api_key or os.getenv("BRAVE_API_KEY", "")
        if not key:
            return []
        try:
            import requests

            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": key,
            }
            params = {"q": query, "count": max_results}
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=10,
            )
            data = resp.json()
            results = []
            for r in data.get("web", {}).get("results", []):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("description", ""),
                        "source": "Brave",
                    }
                )
            return results[:max_results]
        except Exception as e:
            logger.debug(f"Brave 搜索失败: {e}")
            return []

    @staticmethod
    def google(query: str, max_results: int = 8) -> List[Dict]:
        """Google 搜索（网页抓取）"""
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num={max_results + 5}&hl=zh-CN"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            results = []
            for g in soup.find_all("div", class_="g"):
                title_el = g.find("h3")
                link_el = g.find("a")
                snippet_el = g.find("div", class_="VwiC3b") or g.find("span", class_="aCOpRe")
                if not snippet_el:
                    # 备选 snippet 选择器
                    for div in g.find_all("div"):
                        text = div.get_text(strip=True)
                        if len(text) > 40:
                            snippet_el = div
                            break
                if title_el and link_el and link_el.get("href"):
                    href = link_el["href"]
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]
                        href = unquote(href)
                    if href.startswith("http"):
                        results.append(
                            {
                                "title": title_el.get_text(strip=True),
                                "url": href,
                                "snippet": snippet_el.get_text(strip=True)[:300] if snippet_el else "",
                                "source": "Google",
                            }
                        )
                        if len(results) >= max_results:
                            break
            return results
        except Exception as e:
            logger.debug(f"Google 搜索失败: {e}")
            return []

    @staticmethod
    def sogou(query: str, max_results: int = 8) -> List[Dict]:
        """搜狗搜索（网页抓取，中文搜索增强）"""
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            url = f"https://www.sogou.com/web?query={requests.utils.quote(query)}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            results = []
            for item in soup.find_all("div", class_="vrwrap") or soup.find_all("div", class_="rb"):
                title_el = item.find("h3") or item.find("a")
                link_el = item.find("a")
                snippet_el = item.find("p") or item.find("div", class_="str-text-info") or item.find("div", class_="ft")
                if title_el and link_el and link_el.get("href"):
                    href = link_el["href"]
                    results.append(
                        {
                            "title": title_el.get_text(strip=True),
                            "url": href,
                            "snippet": snippet_el.get_text(strip=True)[:300] if snippet_el else "",
                            "source": "Sogou",
                        }
                    )
                    if len(results) >= max_results:
                        break
            return results
        except Exception as e:
            logger.debug(f"搜狗搜索失败: {e}")
            return []

    @staticmethod
    def searxng(query: str, max_results: int = 8, instance_url: str = "") -> List[Dict]:
        """SearXNG 元搜索引擎（需要自部署或使用公共实例）"""
        import os

        base_url = instance_url or os.getenv("SEARXNG_URL", "")
        if not base_url:
            return []
        try:
            import requests

            params = {
                "q": query,
                "format": "json",
                "categories": "general",
                "language": "zh-CN",
            }
            resp = requests.get(
                f"{base_url.rstrip('/')}/search",
                params=params,
                timeout=15,
            )
            data = resp.json()
            results = []
            for r in data.get("results", []):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "source": f"SearXNG({r.get('engine', '')})",
                    }
                )
            return results[:max_results]
        except Exception as e:
            logger.debug(f"SearXNG 搜索失败: {e}")
            return []


class AggregatedSearchTool(BaseTool):
    """聚合搜索引擎工具

    同时查询多个免费搜索引擎（DuckDuckGo、Bing、Google、搜狗、Brave、SearXNG），
    通过交叉验证和共识排名算法提高搜索精准度：
    - 多引擎出现的结果获得更高可信度
    - 基于排名倒数融合 (RRF) 的评分算法
    - 自动去重、合并摘要
    """

    def __init__(
        self,
        engines: Optional[List[str]] = None,
        brave_api_key: str = "",
        searxng_url: str = "",
        timeout: int = 12,
    ):
        """
        Args:
            engines: 启用的搜索引擎列表，默认全部启用
                     可选: 'duckduckgo', 'bing', 'google', 'sogou', 'brave', 'searxng'
            brave_api_key: Brave Search API Key（可选，也可通过 BRAVE_API_KEY 环境变量）
            searxng_url: SearXNG 实例地址（可选，也可通过 SEARXNG_URL 环境变量）
            timeout: 每个引擎的超时时间（秒）
        """
        self._brave_api_key = brave_api_key
        self._searxng_url = searxng_url
        self._timeout = timeout

        # 默认启用的引擎（按可靠性排序）
        default_engines = ["duckduckgo", "bing", "google", "sogou", "brave", "searxng"]
        self._enabled_engines = engines or default_engines

        # 搜索结果缓存 {cache_key: (timestamp, results)}
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 600  # 10 分钟缓存

        super().__init__()

    @property
    def name(self) -> str:
        return "aggregated_search"

    @property
    def description(self) -> str:
        return (
            "聚合搜索引擎 - 同时查询多个搜索引擎（DuckDuckGo、Bing、Google、搜狗等），"
            "通过交叉验证和共识排名提高搜索精准度。"
            "适合需要精确、全面信息的搜索场景。比单一搜索引擎更准确可靠。"
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_SEARCH

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "query",
                "type": "string",
                "description": "搜索查询关键词",
                "required": True,
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "最大返回结果数，默认 8",
                "required": False,
            },
            {
                "name": "engines",
                "type": "string",
                "description": (
                    "指定使用的搜索引擎，逗号分隔。"
                    "可选: duckduckgo,bing,google,sogou,brave,searxng。"
                    "默认使用全部可用引擎"
                ),
                "required": False,
            },
            {
                "name": "category",
                "type": "string",
                "description": "搜索类型: 'general'(通用), 'news'(新闻), 'academic'(学术)，默认 'general'",
                "required": False,
            },
        ]

    def _get_engine_func(self, engine_name: str) -> Optional[Callable]:
        """获取搜索引擎函数"""
        mapping = {
            "duckduckgo": _SearchEngines.duckduckgo,
            "bing": _SearchEngines.bing,
            "google": _SearchEngines.google,
            "sogou": _SearchEngines.sogou,
        }
        if engine_name == "brave":
            return lambda q, n: _SearchEngines.brave(q, n, self._brave_api_key)
        if engine_name == "searxng":
            return lambda q, n: _SearchEngines.searxng(q, n, self._searxng_url)
        return mapping.get(engine_name)

    def _get_cache_key(self, query: str, engines: str) -> str:
        content = f"{query}:{engines}".encode()
        return hashlib.md5(content).hexdigest()

    def _merge_and_rank(
        self, all_results: Dict[str, List[Dict]], max_results: int
    ) -> List[AggregatedResult]:
        """合并去重并使用 RRF（排名倒数融合）算法排序

        RRF 公式: score = Σ (1 / (k + rank_i))
        其中 k=60 是平滑常数，rank_i 是在第 i 个引擎中的排名
        多引擎出现的结果自然获得更高分数
        """
        k = 60  # RRF 平滑常数
        url_map: Dict[str, AggregatedResult] = {}

        for engine_name, results in all_results.items():
            for rank, item in enumerate(results, 1):
                url = item.get("url", "")
                if not url:
                    continue
                norm_url = _normalize_url(url)

                if norm_url in url_map:
                    entry = url_map[norm_url]
                    entry.sources.append(engine_name)
                    entry.source_ranks[engine_name] = rank
                    # 合并摘要 - 取更长的
                    if len(item.get("snippet", "")) > len(entry.snippet):
                        entry.snippet = item["snippet"]
                    # 取更完整的标题
                    if len(item.get("title", "")) > len(entry.title):
                        entry.title = item["title"]
                else:
                    url_map[norm_url] = AggregatedResult(
                        title=item.get("title", ""),
                        url=url,  # 保留原始 URL
                        snippet=item.get("snippet", ""),
                        sources=[engine_name],
                        source_ranks={engine_name: rank},
                    )

        # 计算 RRF 分数
        num_engines = len(all_results)
        for entry in url_map.values():
            rrf_score = sum(1.0 / (k + r) for r in entry.source_ranks.values())
            # 多引擎出现奖励：每多一个引擎 +15% 加成
            cross_bonus = 1.0 + 0.15 * (len(entry.sources) - 1)
            entry.relevance_score = rrf_score * cross_bonus

        # 按分数降序排列
        ranked = sorted(url_map.values(), key=lambda x: x.relevance_score, reverse=True)
        return ranked[:max_results]

    def execute(self, **kwargs) -> ToolResult:
        """执行聚合搜索"""
        query = kwargs.get("query", "").strip()
        max_results = kwargs.get("max_results", 8)
        engines_str = kwargs.get("engines", "")
        category = kwargs.get("category", "general")

        if not query:
            return ToolResult(success=False, output="", error="搜索查询不能为空")

        # 确定使用哪些引擎
        if engines_str:
            engine_names = [e.strip().lower() for e in engines_str.split(",") if e.strip()]
        else:
            engine_names = list(self._enabled_engines)

        # 新闻类搜索优化关键词
        search_query = query
        if category == "news":
            search_query = f"{query} 最新新闻"
        elif category == "academic":
            search_query = f"{query} 学术论文 研究"

        # 检查缓存
        cache_key = self._get_cache_key(search_query, ",".join(sorted(engine_names)))
        if cache_key in self._cache:
            ts, cached_results = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                logger.info(f"[聚合搜索] 命中缓存: {query}")
                return self._format_output(query, cached_results, ["缓存"], from_cache=True)

        # 并发查询多个搜索引擎
        all_results: Dict[str, List[Dict]] = {}
        succeeded_engines = []
        failed_engines = []

        per_engine_max = max(max_results, 8)  # 每个引擎多取一些用于交叉验证

        with ThreadPoolExecutor(max_workers=min(len(engine_names), 5)) as executor:
            future_to_engine = {}
            for eng_name in engine_names:
                func = self._get_engine_func(eng_name)
                if func is None:
                    logger.debug(f"未知引擎: {eng_name}，跳过")
                    continue
                future = executor.submit(func, search_query, per_engine_max)
                future_to_engine[future] = eng_name

            for future in as_completed(future_to_engine, timeout=self._timeout + 5):
                eng_name = future_to_engine[future]
                try:
                    results = future.result(timeout=self._timeout)
                    if results:
                        all_results[eng_name] = results
                        succeeded_engines.append(eng_name)
                        logger.info(f"[聚合搜索] {eng_name}: {len(results)} 条结果")
                    else:
                        failed_engines.append(eng_name)
                except Exception as e:
                    logger.warning(f"[聚合搜索] {eng_name} 失败: {e}")
                    failed_engines.append(eng_name)

        if not all_results:
            return ToolResult(
                success=False,
                output="",
                error=f"所有搜索引擎均未返回结果。尝试的引擎: {', '.join(engine_names)}",
            )

        # 合并去重 + RRF 排名
        ranked_results = self._merge_and_rank(all_results, max_results)

        # 缓存结果
        self._cache[cache_key] = (time.time(), ranked_results)

        return self._format_output(query, ranked_results, succeeded_engines, failed_engines)

    def _format_output(
        self,
        query: str,
        results: List[AggregatedResult],
        succeeded: List[str],
        failed: Optional[List[str]] = None,
        from_cache: bool = False,
    ) -> ToolResult:
        """格式化输出"""
        parts = []

        # 标题
        cache_tag = " (缓存)" if from_cache else ""
        parts.append(f"🔍 聚合搜索{cache_tag} '{query}' — 共 {len(results)} 条精选结果")
        parts.append(f"   数据来源: {', '.join(succeeded)}")
        if failed:
            parts.append(f"   未响应: {', '.join(failed)}")
        parts.append("")

        for i, r in enumerate(results, 1):
            cross_tag = f" ✅×{len(r.sources)}" if len(r.sources) > 1 else ""
            parts.append(f"**{i}. {r.title}**{cross_tag}")
            parts.append(f"   链接: {r.url}")
            parts.append(f"   来源: {', '.join(r.sources)} | 评分: {r.relevance_score:.3f}")
            if r.snippet:
                parts.append(f"   {r.snippet[:250]}")
            parts.append("")

        return ToolResult(
            success=True,
            output="\n".join(parts),
            data=[r.to_dict() for r in results],
            metadata={
                "query": query,
                "result_count": len(results),
                "engines_succeeded": succeeded,
                "engines_failed": failed or [],
                "from_cache": from_cache,
            },
        )
