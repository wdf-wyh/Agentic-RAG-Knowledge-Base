"""网页搜索工具 - 让 Agent 能够搜索互联网获取最新信息"""

import os
from typing import List, Dict, Any, Optional

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory


class WebSearchTool(BaseTool):
    """网页搜索工具
    
    支持多个搜索引擎：
    - Tavily (推荐，专为 AI 设计的搜索 API)
    - DuckDuckGo (免费，无需 API Key)
    - SerpAPI (Google 搜索)
    """
    
    def __init__(self, provider: str = "duckduckgo", api_key: str = None):
        """
        Args:
            provider: 搜索提供者 ('tavily', 'duckduckgo', 'serpapi')
            api_key: API 密钥（tavily/serpapi 需要）
        """
        self._provider = provider.lower()
        self._api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY", "")
        super().__init__()
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "搜索互联网获取最新信息。当本地知识库信息不足或需要最新数据时使用。"
    
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
                "required": True
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "最大返回结果数，默认 5",
                "required": False
            },
            {
                "name": "search_type",
                "type": "string",
                "description": "搜索类型: 'general'(通用), 'news'(新闻), 'academic'(学术)，默认 'general'",
                "required": False
            }
        ]
    
    def _search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """使用 DuckDuckGo 搜索（免费）"""
        try:
            from duckduckgo_search import DDGS
            import logging
            
            # 禁用过于详细的日志
            logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
            
            # 添加代理支持用于网络限制的地区
            ddgs_kwargs = {}
            try:
                # 如果在受限地区，尝试使用代理
                with DDGS(timeout=10, **ddgs_kwargs) as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
            except Exception as e:
                # 第一次尝试失败，尝试使用备选参数
                import time
                time.sleep(1)  # 避免频繁请求被限制
                with DDGS(timeout=20) as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                # 如果没有结果，返回空列表而不是抛出异常
                return []
            
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                }
                for r in results
            ]
        except ImportError:
            raise ImportError("请安装 duckduckgo-search: pip install duckduckgo-search")
        except Exception as e:
            # DuckDuckGo 可能在某些地区被限制，返回空列表而不是抛出异常
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"DuckDuckGo 搜索失败: {str(e)}")
            return []
    
    def _search_tavily(self, query: str, max_results: int = 5, search_type: str = "general") -> List[Dict]:
        """使用 Tavily 搜索（需要 API Key，专为 AI 优化）"""
        if not self._api_key:
            raise ValueError("Tavily 搜索需要 API Key，请设置 TAVILY_API_KEY 环境变量")
        
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self._api_key)
            
            # Tavily 支持的搜索深度
            search_depth = "advanced" if search_type == "academic" else "basic"
            
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True  # 获取 AI 生成的摘要
            )
            
            results = []
            
            # 如果有 AI 生成的答案，放在最前面
            if response.get("answer"):
                results.append({
                    "title": "AI 摘要",
                    "url": "",
                    "snippet": response["answer"],
                    "is_summary": True
                })
            
            # 添加搜索结果
            for r in response.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "score": r.get("score", 0)
                })
            
            return results
            
        except ImportError:
            raise ImportError("请安装 tavily-python: pip install tavily-python")
    
    def _search_serpapi(self, query: str, max_results: int = 5) -> List[Dict]:
        """使用 SerpAPI 搜索（Google 搜索，需要 API Key）"""
        if not self._api_key:
            raise ValueError("SerpAPI 需要 API Key，请设置 SERPAPI_API_KEY 环境变量")
        
        try:
            import requests
            
            params = {
                "engine": "google",
                "q": query,
                "api_key": self._api_key,
                "num": max_results
            }
            
            response = requests.get("https://serpapi.com/search", params=params)
            data = response.json()
            
            results = []
            for r in data.get("organic_results", [])[:max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", "")
                })
            
            return results
            
        except ImportError:
            raise ImportError("请安装 requests: pip install requests")
    
    def execute(self, **kwargs) -> ToolResult:
        """执行网页搜索"""
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        search_type = kwargs.get("search_type", "general")
        
        if not query:
            return ToolResult(success=False, output="", error="搜索查询不能为空")
        
        try:
            results = []
            error_msg = None
            
            # 根据提供者选择搜索方法
            if self._provider == "tavily":
                try:
                    results = self._search_tavily(query, max_results, search_type)
                except Exception as e:
                    error_msg = str(e)
            elif self._provider == "serpapi":
                try:
                    results = self._search_serpapi(query, max_results)
                except Exception as e:
                    error_msg = str(e)
            else:  # DuckDuckGo as primary, with fallback
                try:
                    results = self._search_duckduckgo(query, max_results)
                except Exception as e:
                    error_msg = str(e)
                    # 如果 DuckDuckGo 失败，尝试使用必应搜索作为备选
                    if not results:
                        try:
                            results = self._search_bing_fallback(query, max_results)
                            error_msg = None
                        except:
                            pass
            
            if not results:
                # 如果所有搜索方法都失败，返回有意义的错误信息
                if error_msg:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"搜索失败: {error_msg}。可能是网络连接问题或搜索服务不可用。"
                    )
                return ToolResult(
                    success=True,
                    output=f"未找到关于 '{query}' 的搜索结果",
                    data=[]
                )
            
            # 格式化输出
            output_parts = [f"搜索 '{query}' 找到 {len(results)} 个结果:\n"]
            
            for i, r in enumerate(results, 1):
                if r.get("is_summary"):
                    output_parts.append(f"**AI 摘要**: {r['snippet']}\n")
                else:
                    output_parts.append(f"**{i}. {r['title']}**")
                    if r.get("url"):
                        output_parts.append(f"   链接: {r['url']}")
                    output_parts.append(f"   {r['snippet'][:200]}...")
                    output_parts.append("")
            
            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data=results,
                metadata={
                    "provider": self._provider,
                    "query": query,
                    "result_count": len(results)
                }
            )
            
        except ImportError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {str(e)}")
    
    def _search_bing_fallback(self, query: str, max_results: int = 5) -> List[Dict]:
        """使用必应搜索作为备选（通过网页爬虫）"""
        try:
            import requests
            from bs4 import BeautifulSoup
            import logging
            
            logger = logging.getLogger(__name__)
            
            # 必应搜索 URL
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            url = f"https://cn.bing.com/search?q={query}&count={max_results}"
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # 尝试多种选择器来获取搜索结果
            search_items = (
                soup.find_all('div', class_='b_algo') +  # 标准结果
                soup.find_all('li', class_='b_algo') +    # 列表格式
                soup.find_all('div', class_='b_res')      # 其他格式
            )
            
            for item in search_items[:max_results * 2]:
                try:
                    # 查找标题和链接
                    title_elem = item.find('h2')
                    if not title_elem:
                        title_elem = item.find(['h1', 'h3'])
                    
                    url_elem = item.find('a')
                    if not url_elem:
                        continue
                    
                    # 查找摘要
                    snippet_elem = item.find('p')
                    if not snippet_elem:
                        # 尝试查找其他描述文本
                        desc_divs = item.find_all('div', class_=['b_caption', 'b_factrow'])
                        if desc_divs:
                            snippet_elem = desc_divs[0]
                    
                    if title_elem and url_elem:
                        title = title_elem.get_text(strip=True)
                        item_url = url_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True)[:200] if snippet_elem else ''
                        
                        # 过滤掉不相关的结果（如知乎问题页面作为搜索结果）
                        # 但保留知乎的具体答案页面
                        if not _is_irrelevant_result(title, snippet, item_url):
                            results.append({
                                "title": title,
                                "url": item_url,
                                "snippet": snippet
                            })
                            
                            if len(results) >= max_results:
                                break
                except Exception as e:
                    logger.debug(f"解析单个结果失败: {str(e)}")
                    continue
            
            return results[:max_results]
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"必应搜索备选方案失败: {str(e)}")
            return []


def _is_irrelevant_result(title: str, snippet: str, url: str) -> bool:
    """判断搜索结果是否不相关"""
    # 过滤掉纯粹的问题列表页面
    irrelevant_patterns = [
        'zhihu.com/question/',  # 知乎问题列表
        '/search',               # 搜索结果页面
        'sorry',                 # 错误页面
        '404',                   # 不存在页面
    ]
    
    for pattern in irrelevant_patterns:
        if pattern in url.lower():
            return True
    
    # 如果标题是搜索查询本身或很短，可能不是真实内容
    if len(title) < 5:
        return True
    
    return False


class FetchWebpageTool(BaseTool):
    """网页内容抓取工具 - 获取指定 URL 的内容"""
    
    @property
    def name(self) -> str:
        return "fetch_webpage"
    
    @property
    def description(self) -> str:
        return "获取指定网页的内容。用于深入阅读搜索结果中的页面。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_SEARCH
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "url",
                "type": "string",
                "description": "网页 URL",
                "required": True
            },
            {
                "name": "max_length",
                "type": "integer",
                "description": "最大内容长度（字符），默认 5000",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """抓取网页内容"""
        url = kwargs.get("url", "")
        max_length = kwargs.get("max_length", 5000)
        
        if not url:
            return ToolResult(success=False, output="", error="URL 不能为空")
        
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # 发送请求
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # 获取标题
            title = soup.title.string if soup.title else "无标题"
            
            # 获取正文
            text = soup.get_text(separator='\n', strip=True)
            
            # 清理多余空行
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            content = '\n'.join(lines)
            
            # 截断
            if len(content) > max_length:
                content = content[:max_length] + "\n\n[内容已截断...]"
            
            return ToolResult(
                success=True,
                output=f"**{title}**\n\n{content}",
                data={"title": title, "content": content, "url": url},
                metadata={"url": url, "length": len(content)}
            )
            
        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="请安装依赖: pip install requests beautifulsoup4"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"获取网页失败: {str(e)}")
