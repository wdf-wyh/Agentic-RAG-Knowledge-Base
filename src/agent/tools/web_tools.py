"""网页搜索工具 - 让 Agent 能够搜索互联网获取最新信息"""
# 这是一个模块级文档字符串，描述了这个文件的整体功能：提供网页搜索工具，让AI代理能够从互联网获取最新信息

import os
# 导入os模块，用于操作系统相关的功能，如获取环境变量

from typing import List, Dict, Any, Optional
# 从typing模块导入类型注解：List（列表）、Dict（字典）、Any（任意类型）、Optional（可选类型）

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
# 从项目中的base模块导入基础工具类：BaseTool（工具基类）、ToolResult（工具结果）、ToolCategory（工具类别）


class WebSearchTool(BaseTool):
    """网页搜索工具
    
    支持多个搜索引擎：
    - Tavily (推荐，专为 AI 设计的搜索 API)
    - DuckDuckGo (免费，无需 API Key)
    - SerpAPI (Google 搜索)
    """
    # 这是一个类文档字符串，说明这个工具支持的搜索引擎及其特点
    
    def __init__(self, provider: str = "duckduckgo", api_key: str = None):
        """
        Args:
            provider: 搜索提供者 ('tavily', 'duckduckgo', 'serpapi')
            api_key: API 密钥（tavily/serpapi 需要）
        """
        # 初始化方法，设置搜索提供者和API密钥
        # provider参数指定使用哪个搜索引擎，默认是duckduckgo
        # api_key参数是API密钥，对于某些搜索引擎是必需的
        self._provider = provider.lower()
        # 将provider转换为小写存储，避免大小写敏感问题
        self._api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY", "")
        # 设置API密钥：如果提供了api_key就用它，否则从环境变量中获取
        # 环境变量名格式为 PROVIDER_API_KEY，如 TAVILY_API_KEY
        super().__init__()
        # 调用父类BaseTool的初始化方法
    
    @property
    def name(self) -> str:
        # 这是一个属性装饰器，返回工具的名称
        return "web_search"
        # 返回工具名称字符串，用于标识这个工具
    
    @property
    def description(self) -> str:
        # 属性装饰器，返回工具的描述
        return "搜索互联网获取最新信息。当本地知识库信息不足或需要最新数据时使用。"
        # 返回工具的描述，说明其用途和使用场景
    
    @property
    def category(self) -> ToolCategory:
        # 属性装饰器，返回工具的类别
        return ToolCategory.WEB_SEARCH
        # 返回工具类别枚举值，表示这是网页搜索类工具
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        # 属性装饰器，返回工具的参数定义
        return [
            # 返回一个列表，包含所有参数的定义
            {
                "name": "query",
                # 参数名：搜索查询关键词
                "type": "string",
                # 参数类型：字符串
                "description": "搜索查询关键词",
                # 参数描述
                "required": True
                # 是否必需：是
            },
            {
                "name": "max_results",
                # 参数名：最大返回结果数
                "type": "integer",
                # 参数类型：整数
                "description": "最大返回结果数，默认 5",
                # 参数描述，包括默认值
                "required": False
                # 是否必需：否
            },
            {
                "name": "search_type",
                # 参数名：搜索类型
                "type": "string",
                # 参数类型：字符串
                "description": "搜索类型: 'general'(通用), 'news'(新闻), 'academic'(学术)，默认 'general'",
                # 参数描述，列出可选值和默认值
                "required": False
                # 是否必需：否
            }
        ]
        # 返回参数定义列表的结束
    
    def _search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """使用 DuckDuckGo 搜索（免费）"""
        # 这是一个私有方法（以下划线开头），实现DuckDuckGo搜索功能
        # 参数：query（搜索查询）、max_results（最大结果数，默认5）
        # 返回：字典列表，每个字典包含搜索结果
        try:
            # try块：尝试执行搜索，如果出错会进入except块
            from duckduckgo_search import DDGS
            # 导入DuckDuckGo搜索库
            import logging
            # 导入logging模块用于日志记录
            
            # 禁用过于详细的日志
            logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
            # 设置duckduckgo_search库的日志级别为WARNING，避免过多调试信息
            
            # 添加代理支持用于网络限制的地区
            ddgs_kwargs = {}
            # 初始化一个空字典，用于存储DDGS的参数
            try:
                # 第一次尝试使用DDGS
                with DDGS(timeout=10, **ddgs_kwargs) as ddgs:
                    # 创建DDGS实例，设置超时时间10秒
                    results = list(ddgs.text(query, max_results=max_results))
                    # 执行文本搜索，返回结果列表
            except Exception as e:
                # 如果第一次尝试失败，进入异常处理
                # 第一次尝试失败，尝试使用备选参数
                import time
                time.sleep(1)  # 避免频繁请求被限制
                # 导入time模块，休眠1秒避免被限制
                with DDGS(timeout=20) as ddgs:
                    # 再次创建DDGS实例，增加超时时间到20秒
                    results = list(ddgs.text(query, max_results=max_results))
                    # 再次执行搜索
            
            if not results:
                # 如果没有结果，返回空列表而不是抛出异常
                return []
                # 返回空列表，表示没有找到结果
            
            return [
                # 返回格式化的结果列表
                {
                    "title": r.get("title", ""),
                    # 提取结果的标题，如果没有则为空字符串
                    "url": r.get("href", ""),
                    # 提取结果的URL（href是链接）
                    "snippet": r.get("body", "")
                    # 提取结果的摘要（body是内容片段）
                }
                for r in results
                # 对每个结果进行格式化
            ]
        except ImportError:
            # 如果导入失败（库未安装），抛出ImportError
            raise ImportError("请安装 duckduckgo-search: pip install duckduckgo-search")
            # 提示用户安装所需的库
        except Exception as e:
            # DuckDuckGo 可能在某些地区被限制，返回空列表而不是抛出异常
            import logging
            logger = logging.getLogger(__name__)
            # 获取当前模块的日志记录器
            logger.warning(f"DuckDuckGo 搜索失败: {str(e)}")
            # 记录警告日志，说明搜索失败的原因
            return []
            # 返回空列表，避免程序崩溃
    
    def _search_tavily(self, query: str, max_results: int = 5, search_type: str = "general") -> List[Dict]:
        """使用 Tavily 搜索（需要 API Key，专为 AI 优化）"""
        # Tavily搜索方法，需要API密钥，专为AI优化的搜索API
        if not self._api_key:
            # 检查是否有API密钥
            raise ValueError("Tavily 搜索需要 API Key，请设置 TAVILY_API_KEY 环境变量")
            # 如果没有，抛出错误提示用户设置环境变量
        
        try:
            # 尝试执行搜索
            from tavily import TavilyClient
            # 导入Tavily客户端库
            
            client = TavilyClient(api_key=self._api_key)
            # 创建Tavily客户端实例，使用API密钥
            
            # Tavily 支持的搜索深度
            search_depth = "advanced" if search_type == "academic" else "basic"
            # 根据搜索类型设置搜索深度：学术搜索用advanced，其他用basic
            
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True  # 获取 AI 生成的摘要
            )
            # 调用搜索API，传入查询、最大结果数、搜索深度，并要求包含AI摘要
            
            results = []
            # 初始化结果列表
            
            # 如果有 AI 生成的答案，放在最前面
            if response.get("answer"):
                # 检查响应中是否有AI生成的答案
                results.append({
                    "title": "AI 摘要",
                    # 标题设为"AI 摘要"
                    "url": "",
                    # URL为空，因为这是生成的摘要
                    "snippet": response["answer"],
                    # 摘要内容
                    "is_summary": True
                    # 标记这是一个摘要
                })
            
            # 添加搜索结果
            for r in response.get("results", []):
                # 遍历搜索结果列表
                results.append({
                    "title": r.get("title", ""),
                    # 提取标题
                    "url": r.get("url", ""),
                    # 提取URL
                    "snippet": r.get("content", ""),
                    # 提取内容片段
                    "score": r.get("score", 0)
                    # 提取相关性分数
                })
            
            return results
            # 返回结果列表
            
        except ImportError:
            # 如果导入失败
            raise ImportError("请安装 tavily-python: pip install tavily-python")
            # 提示安装库
    
    def _search_serpapi(self, query: str, max_results: int = 5) -> List[Dict]:
        """使用 SerpAPI 搜索（Google 搜索，需要 API Key）"""
        # SerpAPI搜索方法，使用Google搜索，需要API密钥
        if not self._api_key:
            # 检查API密钥
            raise ValueError("SerpAPI 需要 API Key，请设置 SERPAPI_API_KEY 环境变量")
            # 提示设置环境变量
        
        try:
            # 尝试执行搜索
            import requests
            # 导入requests库用于HTTP请求
            
            params = {
                "engine": "google",
                # 指定搜索引擎为Google
                "q": query,
                # 查询关键词
                "api_key": self._api_key,
                # API密钥
                "num": max_results
                # 结果数量
            }
            
            response = requests.get("https://serpapi.com/search", params=params)
            # 发送GET请求到SerpAPI
            data = response.json()
            # 解析JSON响应
            
            results = []
            # 初始化结果列表
            for r in data.get("organic_results", [])[:max_results]:
                # 遍历有机搜索结果，限制数量
                results.append({
                    "title": r.get("title", ""),
                    # 提取标题
                    "url": r.get("link", ""),
                    # 提取链接
                    "snippet": r.get("snippet", "")
                    # 提取摘要
                })
            
            return results
            # 返回结果列表
            
        except ImportError:
            # 如果导入失败
            raise ImportError("请安装 requests: pip install requests")
            # 提示安装requests库
    
    def execute(self, **kwargs) -> ToolResult:
        """执行网页搜索"""
        # 这是工具的主要执行方法，接收关键字参数并返回ToolResult
        query = kwargs.get("query", "")
        # 从参数中获取查询关键词，默认空字符串
        max_results = kwargs.get("max_results", 5)
        # 获取最大结果数，默认5
        search_type = kwargs.get("search_type", "general")
        # 获取搜索类型，默认"general"
        
        if not query:
            # 检查查询是否为空
            return ToolResult(success=False, output="", error="搜索查询不能为空")
            # 如果为空，返回失败结果
        
        try:
            # 尝试执行搜索
            results = []
            # 初始化结果列表
            error_msg = None
            # 初始化错误消息
            
            # 根据提供者选择搜索方法
            if self._provider == "tavily":
                # 如果提供者是tavily
                try:
                    results = self._search_tavily(query, max_results, search_type)
                    # 调用tavily搜索方法
                except Exception as e:
                    error_msg = str(e)
                    # 记录错误消息
            elif self._provider == "serpapi":
                # 如果提供者是serpapi
                try:
                    results = self._search_serpapi(query, max_results)
                    # 调用serpapi搜索方法
                except Exception as e:
                    error_msg = str(e)
                    # 记录错误消息
            else:  # DuckDuckGo as primary, with fallback
                # 默认使用DuckDuckGo，并有备选方案
                try:
                    results = self._search_duckduckgo(query, max_results)
                    # 首先尝试DuckDuckGo
                except Exception as e:
                    error_msg = str(e)
                    # 记录错误
                    # 如果 DuckDuckGo 失败，尝试使用必应搜索作为备选
                    if not results:
                        # 如果没有结果
                        try:
                            results = self._search_bing_fallback(query, max_results)
                            # 尝试必应搜索作为备选
                            error_msg = None
                            # 清除错误消息，因为备选成功了
                        except:
                            pass
                            # 如果备选也失败，忽略异常
            
            if not results:
                # 如果所有搜索方法都失败
                # 如果所有搜索方法都失败，返回有意义的错误信息
                if error_msg:
                    # 如果有错误消息
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"搜索失败: {error_msg}。可能是网络连接问题或搜索服务不可用。"
                    )
                    # 返回失败结果，包含错误信息
                return ToolResult(
                    success=True,
                    output=f"未找到关于 '{query}' 的搜索结果",
                    data=[]
                )
                # 返回成功但无结果的结果
            
            # 格式化输出
            output_parts = [f"搜索 '{query}' 找到 {len(results)} 个结果:\n"]
            # 初始化输出部分，包含结果数量
            
            for i, r in enumerate(results, 1):
                # 遍历结果，i从1开始编号
                if r.get("is_summary"):
                    # 如果是AI摘要
                    output_parts.append(f"**AI 摘要**: {r['snippet']}\n")
                    # 添加摘要格式
                else:
                    output_parts.append(f"**{i}. {r['title']}**")
                    # 添加标题
                    if r.get("url"):
                        output_parts.append(f"   链接: {r['url']}")
                        # 添加链接
                    output_parts.append(f"   {r['snippet'][:200]}...")
                    # 添加摘要的前200字符
                    output_parts.append("")
                    # 添加空行
            
            return ToolResult(
                success=True,
                # 成功标志
                output="\n".join(output_parts),
                # 连接所有输出部分
                data=results,
                # 原始数据
                metadata={
                    "provider": self._provider,
                    # 使用的提供者
                    "query": query,
                    # 查询关键词
                    "result_count": len(results)
                    # 结果数量
                }
            )
            
        except ImportError as e:
            # 如果导入错误
            return ToolResult(success=False, output="", error=str(e))
            # 返回导入错误
        except Exception as e:
            # 其他异常
            return ToolResult(success=False, output="", error=f"搜索失败: {str(e)}")
            # 返回一般错误
    
    def _search_bing_fallback(self, query: str, max_results: int = 5) -> List[Dict]:
        """使用必应搜索作为备选（通过网页爬虫）"""
        # 必应搜索备选方法，当其他搜索失败时使用，通过网页爬虫获取结果
        try:
            # 尝试执行爬虫搜索
            import requests
            # 导入requests用于HTTP请求
            from bs4 import BeautifulSoup
            # 导入BeautifulSoup用于HTML解析
            import logging
            # 导入logging用于日志
            
            logger = logging.getLogger(__name__)
            # 获取当前模块的日志记录器
            
            # 必应搜索 URL
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                # 设置User-Agent模拟浏览器，避免被识别为爬虫
            }
            
            url = f"https://cn.bing.com/search?q={query}&count={max_results}"
            # 构造必应搜索URL，使用中文版，包含查询和结果数量
            response = requests.get(url, headers=headers, timeout=10)
            # 发送GET请求，设置超时10秒
            response.encoding = 'utf-8'
            # 设置响应编码为UTF-8
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # 使用BeautifulSoup解析HTML
            
            results = []
            # 初始化结果列表
            
            # 尝试多种选择器来获取搜索结果
            search_items = (
                soup.find_all('div', class_='b_algo') +  # 标准结果
                soup.find_all('li', class_='b_algo') +    # 列表格式
                soup.find_all('div', class_='b_res')      # 其他格式
            )
            # 使用多种CSS选择器查找搜索结果元素
            
            for item in search_items[:max_results * 2]:
                # 遍历搜索项，限制为max_results的两倍以防过滤
                try:
                    # 查找标题和链接
                    title_elem = item.find('h2')
                    # 查找h2标签作为标题
                    if not title_elem:
                        title_elem = item.find(['h1', 'h3'])
                        # 如果没有h2，尝试h1或h3
                    
                    url_elem = item.find('a')
                    # 查找a标签作为链接
                    if not url_elem:
                        continue
                        # 如果没有链接，跳过
                    
                    # 查找摘要
                    snippet_elem = item.find('p')
                    # 查找p标签作为摘要
                    if not snippet_elem:
                        # 尝试查找其他描述文本
                        desc_divs = item.find_all('div', class_=['b_caption', 'b_factrow'])
                        # 查找其他可能的摘要容器
                        if desc_divs:
                            snippet_elem = desc_divs[0]
                            # 使用第一个找到的
                    
                    if title_elem and url_elem:
                        # 如果找到了标题和链接
                        title = title_elem.get_text(strip=True)
                        # 提取标题文本并去除空白
                        item_url = url_elem.get('href', '')
                        # 提取链接的href属性
                        snippet = snippet_elem.get_text(strip=True)[:200] if snippet_elem else ''
                        # 提取摘要文本的前200字符，如果没有则为空
                        
                        # 过滤掉不相关的结果（如知乎问题页面作为搜索结果）
                        # 但保留知乎的具体答案页面
                        if not _is_irrelevant_result(title, snippet, item_url):
                            # 如果结果不不相关
                            results.append({
                                "title": title,
                                "url": item_url,
                                "snippet": snippet
                            })
                            
                            if len(results) >= max_results:
                                break
                                # 如果达到最大结果数，停止
                except Exception as e:
                    logger.debug(f"解析单个结果失败: {str(e)}")
                    # 记录调试日志，如果解析单个结果失败
                    continue
                    # 继续下一个结果
            
            return results[:max_results]
            # 返回结果列表，限制为max_results
            
        except Exception as e:
            # 如果整个方法失败
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"必应搜索备选方案失败: {str(e)}")
            # 记录警告日志
            return []
            # 返回空列表


def _is_irrelevant_result(title: str, snippet: str, url: str) -> bool:
    """判断搜索结果是否不相关"""
    # 这个函数用于过滤掉不相关的搜索结果，如问题列表页面
    # 参数：title（标题）、snippet（摘要）、url（链接）
    # 返回：布尔值，True表示不相关，False表示相关
    # 过滤掉纯粹的问题列表页面
    irrelevant_patterns = [
        'zhihu.com/question/',  # 知乎问题列表
        '/search',               # 搜索结果页面
        'sorry',                 # 错误页面
        '404',                   # 不存在页面
    ]
    # 定义不相关模式的列表
    
    for pattern in irrelevant_patterns:
        # 遍历每个不相关模式
        if pattern in url.lower():
            # 如果URL包含不相关模式（忽略大小写）
            return True
            # 返回True，表示不相关
    
    # 如果标题是搜索查询本身或很短，可能不是真实内容
    if len(title) < 5:
        # 如果标题长度小于5
        return True
        # 返回True，表示不相关
    
    return False
    # 默认返回False，表示相关


class FetchWebpageTool(BaseTool):
    """网页内容抓取工具 - 获取指定 URL 的内容"""
    # 这是一个新的工具类，用于抓取指定网页的内容
    # 继承自BaseTool基类
    
    @property
    def name(self) -> str:
        # 属性：工具名称
        return "fetch_webpage"
        # 返回工具名称字符串
    
    @property
    def description(self) -> str:
        # 属性：工具描述
        return "获取指定网页的内容。用于深入阅读搜索结果中的页面。"
        # 返回工具描述，说明用途
    
    @property
    def category(self) -> ToolCategory:
        # 属性：工具类别
        return ToolCategory.WEB_SEARCH
        # 返回网页搜索类别
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        # 属性：工具参数定义
        return [
            {
                "name": "url",
                # 参数名：URL
                "type": "string",
                # 类型：字符串
                "description": "网页 URL",
                # 描述：网页URL
                "required": True
                # 必需：是
            },
            {
                "name": "max_length",
                # 参数名：最大长度
                "type": "integer",
                # 类型：整数
                "description": "最大内容长度（字符），默认 5000",
                # 描述：最大内容长度，默认5000字符
                "required": False
                # 必需：否
            }
        ]
        # 返回参数定义列表
    
    def execute(self, **kwargs) -> ToolResult:
        """抓取网页内容"""
        # 执行方法：抓取网页内容
        url = kwargs.get("url", "")
        # 获取URL参数，默认空字符串
        max_length = kwargs.get("max_length", 5000)
        # 获取最大长度参数，默认5000
        
        if not url:
            # 如果URL为空
            return ToolResult(success=False, output="", error="URL 不能为空")
            # 返回失败结果
        
        try:
            # 尝试抓取网页
            import requests
            # 导入requests库
            from bs4 import BeautifulSoup
            # 导入BeautifulSoup用于HTML解析
            
            # 发送请求
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                # 设置User-Agent模拟浏览器
            }
            response = requests.get(url, headers=headers, timeout=10)
            # 发送GET请求，设置超时10秒
            response.raise_for_status()
            # 检查响应状态，如果不是200会抛出异常
            
            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            # 创建BeautifulSoup对象解析HTML
            
            # 移除脚本和样式
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                # 移除脚本、样式、导航、页脚、页眉等不需要的元素
            
            # 获取标题
            title = soup.title.string if soup.title else "无标题"
            # 获取页面标题，如果没有则设为"无标题"
            
            # 获取正文
            text = soup.get_text(separator='\n', strip=True)
            # 提取所有文本，用换行符分隔，去除空白
            
            # 清理多余空行
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            # 分割成行，过滤掉空行
            content = '\n'.join(lines)
            # 重新连接成文本
            
            # 截断
            if len(content) > max_length:
                content = content[:max_length] + "\n\n[内容已截断...]"
                # 如果内容太长，截断并添加提示
            
            return ToolResult(
                success=True,
                # 成功标志
                output=f"**{title}**\n\n{content}",
                # 输出格式：标题 + 内容
                data={"title": title, "content": content, "url": url},
                # 数据包含标题、内容、URL
                metadata={"url": url, "length": len(content)}
                # 元数据包含URL和内容长度
            )
            
        except ImportError:
            # 如果导入失败
            return ToolResult(
                success=False,
                output="",
                error="请安装依赖: pip install requests beautifulsoup4"
                # 提示安装依赖
            )
        except Exception as e:
            # 其他异常
            return ToolResult(success=False, output="", error=f"获取网页失败: {str(e)}")
            # 返回错误信息
