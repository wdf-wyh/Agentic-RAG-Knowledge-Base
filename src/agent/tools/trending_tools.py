"""热搜趋势工具 - 获取各平台的热搜、热榜数据"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


@dataclass
class TrendingItem:
    """热搜项目"""
    rank: int          # 排名
    title: str         # 标题
    url: str           # 链接
    hot_value: int     # 热度值
    description: str   # 描述/摘要
    source: str        # 来源
    category: str      # 分类
    timestamp: str     # 时间戳


class BaiduTrendingTool(BaseTool):
    """百度热搜榜工具
    
    获取百度热搜实时排行数据
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        return "baidu_trending"
    
    @property
    def description(self) -> str:
        return "获取百度热搜实时排行榜数据。返回当前最热的搜索话题和排名。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_SEARCH
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "category",
                "type": "string",
                "description": "热搜分类: 'all'(综合热搜), 'news'(新闻热榜), 'entertainment'(娱乐热榜)，默认 'all'",
                "required": False
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "最大返回结果数，默认 10",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行获取百度热搜"""
        category = kwargs.get("category", "all")
        max_results = kwargs.get("max_results", 10)
        
        try:
            results = self._fetch_baidu_trending(category, max_results)
            
            if not results:
                return ToolResult(
                    success=True,
                    output=f"未找到 {category} 分类的热搜数据",
                    data=[]
                )
            
            # 格式化输出
            output_parts = [f"百度热搜 ({category}) - 共 {len(results)} 条\n"]
            
            for item in results:
                output_parts.append(f"【{item['rank']}】 {item['title']}")
                if item.get('hot_value'):
                    output_parts.append(f"   热度: {item['hot_value']}")
                if item.get('description'):
                    output_parts.append(f"   {item['description'][:100]}...")
                output_parts.append("")
            
            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data=results,
                metadata={
                    "category": category,
                    "count": len(results),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"获取百度热搜失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"获取百度热搜失败: {str(e)}"
            )
    
    def _fetch_baidu_trending(self, category: str = "all", max_results: int = 10) -> List[Dict[str, Any]]:
        """获取百度热搜数据
        
        直接访问百度热搜页面，提取热搜项目
        """
        try:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urlparse, parse_qs, unquote
            
            # 定义URL
            urls = {
                "all": "https://top.baidu.com/board?tab=realtime",
                "news": "https://top.baidu.com/board?tab=news",
                "entertainment": "https://top.baidu.com/board?tab=entertainment"
            }
            
            url = urls.get(category, urls["all"])
            
            # 请求头，模拟浏览器
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://top.baidu.com/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # 策略：找到所有包含 /s?wd= 的链接（百度搜索链接）
            # 这是热搜链接的标准格式
            search_links = soup.find_all('a', href=lambda x: x and 'baidu.com/s?wd=' in x)
            
            logger.info(f"找到 {len(search_links)} 个搜索链接")
            
            # 去重和过滤：我们需要找出真正的热搜项（不是"查看更多"等）
            seen_titles = set()
            for idx, link in enumerate(search_links):
                if len(results) >= max_results:
                    break
                
                try:
                    # 提取标题
                    title = link.get_text(strip=True)
                    
                    # 过滤掉空标题、导航项和"查看更多"等
                    if not title or len(title) < 2 or title in ['查看更多>', '下一页']:
                        continue
                    
                    # 去重
                    if title in seen_titles:
                        continue
                    
                    seen_titles.add(title)
                    
                    # 提取URL和搜索词
                    url_href = link.get('href', '')
                    
                    # 从URL中提取搜索词
                    if 'wd=' in url_href:
                        try:
                            # 解析URL参数
                            parsed = urlparse(url_href)
                            params = parse_qs(parsed.query)
                            search_term = params.get('wd', [''])[0]
                            if search_term:
                                search_term = unquote(search_term)
                        except:
                            search_term = title
                    else:
                        search_term = title
                    
                    # 提取热度信息（可能在link的兄弟元素中）
                    hot_value = 0
                    parent = link.parent
                    if parent:
                        # 查找同级的热度span或数字
                        hot_span = parent.find(class_=lambda x: x and any(k in (x or '') for k in ['hot', 'num', 'value', 'sc-dot-light']))
                        if hot_span:
                            hot_text = hot_span.get_text(strip=True)
                            hot_value = self._parse_hot_value(hot_text)
                    
                    # 确保有有效的热搜数据
                    if search_term or title:
                        results.append({
                            "rank": len(results) + 1,
                            "title": search_term if search_term else title,
                            "url": url_href if url_href.startswith('http') else f"https://www.baidu.com{url_href}",
                            "hot_value": hot_value,
                            "description": "",
                            "source": "baidu",
                            "category": category
                        })
                        
                except Exception as e:
                    logger.debug(f"处理链接失败: {e}")
                    continue
            
            logger.info(f"成功提取 {len(results)} 条热搜数据")
            return results
            
        except ImportError as e:
            logger.error(f"缺少依赖: {e}. 请运行: pip install requests beautifulsoup4")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            return []
        except Exception as e:
            logger.error(f"爬取百度热搜失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_hot_value(self, text: str) -> int:
        """解析热度值"""
        if not text:
            return 0
        
        # 移除非数字字符，提取数值
        import re
        numbers = re.findall(r'\d+', text)
        
        if numbers:
            value = int(numbers[0])
            # 如果文本包含 'K' 或 '万'，乘以 1000
            if 'K' in text or '万' in text:
                value *= 1000
            elif 'M' in text or '百万' in text:
                value *= 1000000
            return value
        
        return 0


class TrendingNewsAggregatorTool(BaseTool):
    """热门新闻聚合工具
    
    聚合多个来源的热门新闻，包括百度、微博等
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        return "trending_news_aggregator"
    
    @property
    def description(self) -> str:
        return "聚合多个来源的热门新闻和热搜话题。支持百度、微博等主要平台。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_SEARCH
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "sources",
                "type": "string",
                "description": "数据来源，逗号分隔: 'baidu,weibo,toutiao' 等，默认 'baidu'",
                "required": False
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "最大返回结果数，默认 15",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行热新闻聚合"""
        sources = kwargs.get("sources", "baidu").split(",")
        max_results = kwargs.get("max_results", 15)
        
        try:
            all_results = []
            
            # 目前只支持百度
            if "baidu" in sources:
                baidu_tool = BaiduTrendingTool()
                baidu_result = baidu_tool.execute(category="all", max_results=max_results)
                if baidu_result.success:
                    all_results.extend(baidu_result.data)
            
            if not all_results:
                return ToolResult(
                    success=True,
                    output="未获取到任何热门新闻",
                    data=[]
                )
            
            # 按热度排序
            all_results.sort(key=lambda x: x.get("hot_value", 0), reverse=True)
            
            # 格式化输出
            output_parts = [f"热门新闻聚合 - 共 {len(all_results)} 条\n"]
            
            for item in all_results[:max_results]:
                output_parts.append(f"【{item['rank']}】 {item['title']} ({item['source']})")
                if item.get('hot_value'):
                    output_parts.append(f"   热度: {item['hot_value']}")
                output_parts.append("")
            
            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data=all_results[:max_results],
                metadata={
                    "sources": sources,
                    "count": len(all_results),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"热新闻聚合失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"热新闻聚合失败: {str(e)}"
            )
