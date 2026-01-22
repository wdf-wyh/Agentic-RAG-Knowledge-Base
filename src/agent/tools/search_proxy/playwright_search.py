"""Playwright 无头浏览器搜索

使用 Playwright 模拟真人浏览器行为进行搜索，绕过反爬虫机制。
支持 Google、Bing、DuckDuckGo、百度等搜索引擎。
"""

import asyncio
import random
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .base import SearchProxyBase, SearchResult, SearchEngine

logger = logging.getLogger(__name__)


@dataclass
class BrowserFingerprint:
    """浏览器指纹配置"""
    user_agent: str
    viewport_width: int
    viewport_height: int
    locale: str
    timezone: str
    
    @classmethod
    def random_desktop(cls) -> "BrowserFingerprint":
        """生成随机桌面浏览器指纹"""
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        
        viewports = [
            (1920, 1080), (1366, 768), (1536, 864), 
            (1440, 900), (1280, 720), (2560, 1440)
        ]
        
        viewport = random.choice(viewports)
        
        return cls(
            user_agent=random.choice(user_agents),
            viewport_width=viewport[0],
            viewport_height=viewport[1],
            locale="zh-CN",
            timezone="Asia/Shanghai"
        )


class PlaywrightSearch(SearchProxyBase):
    """Playwright 无头浏览器搜索
    
    使用真实浏览器进行搜索，模拟人类行为，绑定反爬虫。
    
    安装:
        pip install playwright
        playwright install chromium
    
    使用示例:
        search = PlaywrightSearch()
        results = await search.search_async("Python 教程")
        # 或同步调用
        results = search.search("Python 教程")
    """
    
    # 搜索引擎配置
    ENGINE_CONFIGS = {
        SearchEngine.GOOGLE: {
            "url": "https://www.google.com/search?q={query}",
            "result_selector": "div.g",
            "title_selector": "h3",
            "link_selector": "a",
            "snippet_selector": "div[data-sncf], div.VwiC3b",
        },
        SearchEngine.BING: {
            "url": "https://www.bing.com/search?q={query}",
            "result_selector": "li.b_algo",
            "title_selector": "h2",
            "link_selector": "a",
            "snippet_selector": "p, div.b_caption p",
        },
        SearchEngine.DUCKDUCKGO: {
            "url": "https://duckduckgo.com/?q={query}",
            "result_selector": "article[data-testid='result']",
            "title_selector": "h2",
            "link_selector": "a[data-testid='result-title-a']",
            "snippet_selector": "span[data-result='snippet']",
        },
        SearchEngine.BAIDU: {
            "url": "https://www.baidu.com/s?wd={query}",
            "result_selector": "div.result, div.c-container",
            "title_selector": "h3",
            "link_selector": "a",
            "snippet_selector": "span.content-right_8Zs40",
        }
    }
    
    def __init__(
        self,
        engine: SearchEngine = SearchEngine.GOOGLE,
        headless: bool = True,
        slow_mo: int = 100,
        proxy: Optional[str] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Args:
            engine: 搜索引擎
            headless: 是否无头模式
            slow_mo: 操作延迟（毫秒），模拟人类行为
            proxy: 代理服务器地址
            cache_enabled: 是否启用缓存
            cache_ttl: 缓存有效期
        """
        super().__init__(cache_enabled, cache_ttl)
        self.engine = engine
        self.headless = headless
        self.slow_mo = slow_mo
        self.proxy = proxy
        self._browser = None
        self._playwright = None
    
    @property
    def name(self) -> str:
        return f"playwright_{self.engine.value}"
    
    async def _init_browser(self):
        """初始化浏览器"""
        if self._browser is not None:
            return
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "请安装 Playwright:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )
        
        self._playwright = await async_playwright().start()
        
        fingerprint = BrowserFingerprint.random_desktop()
        
        launch_options = {
            "headless": self.headless,
            "slow_mo": self.slow_mo,
        }
        
        if self.proxy:
            launch_options["proxy"] = {"server": self.proxy}
        
        self._browser = await self._playwright.chromium.launch(**launch_options)
        
        self._context = await self._browser.new_context(
            user_agent=fingerprint.user_agent,
            viewport={
                "width": fingerprint.viewport_width,
                "height": fingerprint.viewport_height
            },
            locale=fingerprint.locale,
            timezone_id=fingerprint.timezone
        )
    
    async def _close_browser(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    async def _human_like_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """模拟人类思考延迟"""
        delay = random.uniform(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)
    
    async def _scroll_page(self, page, scroll_count: int = 3):
        """模拟人类滚动页面"""
        for _ in range(scroll_count):
            await page.mouse.wheel(0, random.randint(300, 700))
            await self._human_like_delay(200, 500)
    
    async def search_async(
        self,
        query: str,
        max_results: int = 10,
        scroll: bool = True
    ) -> List[SearchResult]:
        """异步搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            scroll: 是否滚动页面加载更多结果
            
        Returns:
            搜索结果列表
        """
        await self._init_browser()
        
        config = self.ENGINE_CONFIGS[self.engine]
        search_url = config["url"].format(query=query)
        
        page = await self._context.new_page()
        results = []
        
        try:
            # 导航到搜索页面
            await page.goto(search_url, wait_until="domcontentloaded")
            await self._human_like_delay(1000, 2000)
            
            # 滚动加载更多结果
            if scroll:
                await self._scroll_page(page)
            
            # 提取搜索结果
            result_elements = await page.query_selector_all(config["result_selector"])
            
            for i, element in enumerate(result_elements[:max_results]):
                try:
                    # 提取标题
                    title_el = await element.query_selector(config["title_selector"])
                    title = await title_el.inner_text() if title_el else ""
                    
                    # 提取链接
                    link_el = await element.query_selector(config["link_selector"])
                    url = await link_el.get_attribute("href") if link_el else ""
                    
                    # 提取摘要
                    snippet_el = await element.query_selector(config["snippet_selector"])
                    snippet = await snippet_el.inner_text() if snippet_el else ""
                    
                    if title and url:
                        results.append(SearchResult(
                            title=title.strip(),
                            url=url,
                            snippet=snippet.strip(),
                            source=self.engine.value,
                            score=1.0 - (i * 0.05)
                        ))
                except Exception as e:
                    logger.debug(f"提取结果失败: {e}")
                    continue
            
            logger.info(f"Playwright 搜索 '{query}' ({self.engine.value}) 返回 {len(results)} 个结果")
            
        except Exception as e:
            logger.error(f"Playwright 搜索失败: {e}")
            raise
        finally:
            await page.close()
        
        return results
    
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """同步搜索（包装异步方法）"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.search_async(query, max_results, **kwargs)
        )
    
    def is_available(self) -> bool:
        """检查 Playwright 是否可用"""
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False
    
    async def fetch_page_content(self, url: str, max_length: int = 10000) -> Dict[str, Any]:
        """获取网页内容
        
        使用浏览器渲染页面，支持 JavaScript 动态内容。
        
        Args:
            url: 网页地址
            max_length: 最大内容长度
            
        Returns:
            包含标题、内容、截图等信息的字典
        """
        await self._init_browser()
        page = await self._context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle")
            await self._human_like_delay(500, 1500)
            
            # 获取标题
            title = await page.title()
            
            # 获取正文内容
            content = await page.evaluate("""
                () => {
                    // 移除不需要的元素
                    const removeSelectors = ['script', 'style', 'nav', 'header', 'footer', 'aside', '.ad', '.advertisement'];
                    removeSelectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });
                    
                    // 获取主要内容
                    const main = document.querySelector('main, article, .content, #content') || document.body;
                    return main.innerText;
                }
            """)
            
            # 截断内容
            if len(content) > max_length:
                content = content[:max_length] + "\n\n[内容已截断...]"
            
            return {
                "title": title,
                "content": content,
                "url": url
            }
            
        finally:
            await page.close()
    
    def __del__(self):
        """清理资源"""
        if self._browser:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_browser())
                else:
                    loop.run_until_complete(self._close_browser())
            except Exception:
                pass


class MultiEnginePlaywrightSearch(SearchProxyBase):
    """多引擎 Playwright 搜索
    
    同时使用多个搜索引擎，聚合去重结果。
    """
    
    def __init__(
        self,
        engines: List[SearchEngine] = None,
        headless: bool = True,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        super().__init__(cache_enabled, cache_ttl)
        
        self.engines = engines or [
            SearchEngine.GOOGLE,
            SearchEngine.BING,
            SearchEngine.DUCKDUCKGO
        ]
        
        self._searchers = {
            engine: PlaywrightSearch(engine, headless, cache_enabled=False)
            for engine in self.engines
        }
    
    @property
    def name(self) -> str:
        return "playwright_multi"
    
    async def search_async(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """异步多引擎搜索"""
        tasks = [
            searcher.search_async(query, max_results)
            for searcher in self._searchers.values()
        ]
        
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 聚合结果
        merged = []
        seen_urls = set()
        
        for results in all_results:
            if isinstance(results, Exception):
                logger.warning(f"搜索失败: {results}")
                continue
            
            for result in results:
                # 去重
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    merged.append(result)
        
        # 按分数排序
        merged.sort(key=lambda x: x.score, reverse=True)
        
        return merged[:max_results]
    
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """同步搜索"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.search_async(query, max_results)
        )
    
    def is_available(self) -> bool:
        return any(s.is_available() for s in self._searchers.values())
