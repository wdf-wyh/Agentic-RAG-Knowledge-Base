"""热搜趋势工具 - 获取各平台的热搜、热榜数据
这个模块定义了用于获取热搜数据的工具类
主要包括百度热搜工具和新闻聚合工具
"""

# 导入日志模块，用于记录程序运行信息和错误
import logging
# typing模块提供类型注解功能，增强代码可读性和IDE提示
from typing import List, Dict, Any, Optional
# dataclass装饰器可以自动生成__init__等方法，简化数据类定义
from dataclasses import dataclass
# datetime用于处理时间戳
from datetime import datetime

# 从基础工具模块导入必需的类
# BaseTool: 所有工具的基类
# ToolResult: 工具执行结果的封装类
# ToolCategory: 工具分类枚举
from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

# 创建当前模块的logger实例，用于日志记录
# __name__会自动获取当前模块名称，便于日志跟踪
logger = logging.getLogger(__name__)


# @dataclass 装饰器：Python 3.7+ 引入的语法糖
# 作用：自动为类生成 __init__(), __repr__(), __eq__() 等魔术方法
# 好处：减少样板代码，让数据类定义更简洁
@dataclass
class TrendingItem:
    """热搜项目数据类
    
    用途：定义热搜项目的数据结构，统一各平台的热搜数据格式
    使用示例：
        item = TrendingItem(
            rank=1, 
            title="某个热搜",
            url="https://...",
            hot_value=1000000,
            description="详细描述",
            source="baidu",
            category="news",
            timestamp="2026-01-26T10:00:00"
        )
    """
    rank: int          # 排名：热搜在榜单中的位置（1表示第一名）
    title: str         # 标题：热搜话题的标题文本
    url: str           # 链接：点击热搜后跳转的目标URL
    hot_value: int     # 热度值：量化的热度指标（如搜索次数、点赞数等）
    description: str   # 描述/摘要：热搜的简要说明或相关内容
    source: str        # 来源：数据来源平台（如 baidu、weibo、toutiao）
    category: str      # 分类：热搜的类别（如 news、entertainment、tech）
    timestamp: str     # 时间戳：热搜数据获取的时间（ISO 8601格式）


class BaiduTrendingTool(BaseTool):
    """百度热搜榜工具
    
    功能说明：获取百度热搜实时排行数据
    工作原理：通过爬虫技术抓取百度热搜页面的HTML，解析提取热搜数据
    继承关系：继承自BaseTool，实现统一的工具接口
    """
    
    def __init__(self):
        """构造函数：初始化百度热搜工具
        
        调用父类的构造函数进行基础初始化
        super()是Python的内置函数，用于调用父类的方法
        """
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称属性
        
        @property装饰器：将方法转换为只读属性，使用时无需加括号
        返回值：字符串类型的工具唯一标识符
        用途：用于在系统中注册和调用此工具
        """
        return "baidu_trending"
    
    @property
    def description(self) -> str:
        """工具描述属性
        
        返回值：工具功能的自然语言描述
        用途：帮助AI理解何时应该使用这个工具
        """
        return "获取百度热搜实时排行榜数据。返回当前最热的搜索话题和排名。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类属性
        
        返回值：ToolCategory枚举值
        用途：将工具归类，便于管理和筛选
        """
        return ToolCategory.WEB_SEARCH
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """工具参数定义
        
        返回值：参数列表，每个参数是一个字典
        字典结构：
            - name: 参数名称
            - type: 参数类型（string, integer, boolean等）
            - description: 参数说明
            - required: 是否必需（True/False）
        用途：定义工具接受哪些参数，供AI理解和调用
        """
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
        """执行工具的主方法
        
        参数说明：
            **kwargs: 可变关键字参数，接收任意数量的命名参数
                     例如：execute(category="news", max_results=5)
        
        返回值：ToolResult对象，包含执行结果、数据和元信息
        
        工作流程：
            1. 提取参数（使用get方法提供默认值）
            2. 调用内部方法获取数据
            3. 格式化输出
            4. 返回结果对象
        """
        # 使用dict.get()方法安全获取参数，如果不存在则使用默认值
        category = kwargs.get("category", "all")
        max_results = kwargs.get("max_results", 10)
        
        try:
            # 调用内部方法获取百度热搜数据
            results = self._fetch_baidu_trending(category, max_results)
            
            # 判断是否获取到数据
            if not results:
                # 返回空结果（success=True表示执行成功，只是没有数据）
                return ToolResult(
                    success=True,
                    output=f"未找到 {category} 分类的热搜数据",
                    data=[]
                )
            
            # 格式化输出：构建用户友好的文本展示
            output_parts = [f"百度热搜 ({category}) - 共 {len(results)} 条\n"]
            
            # 遍历每个热搜项，格式化为易读文本
            for item in results:
                # 【排名】标题
                output_parts.append(f"【{item['rank']}】 {item['title']}")
                # 如果有热度值，显示热度
                if item.get('hot_value'):
                    output_parts.append(f"   热度: {item['hot_value']}")
                # 如果有描述，截取前100字符
                if item.get('description'):
                    output_parts.append(f"   {item['description'][:100]}...")
                # 添加空行分隔
                output_parts.append("")
            
            # 返回成功结果
            return ToolResult(
                success=True,                              # 执行成功标志
                output="\n".join(output_parts),            # 格式化的文本输出
                data=results,                              # 原始数据（列表）
                metadata={                                 # 元数据（附加信息）
                    "category": category,
                    "count": len(results),
                    "timestamp": datetime.now().isoformat()  # ISO格式时间戳
                }
            )
            
        except Exception as e:
            # 异常处理：捕获所有异常，记录日志并返回失败结果
            logger.error(f"获取百度热搜失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"获取百度热搜失败: {str(e)}"
            )

    
    def _fetch_baidu_trending(self, category: str = "all", max_results: int = 10) -> List[Dict[str, Any]]:
        """获取百度热搜数据（内部方法）
        
        参数说明：
            category: 热搜分类（all/news/entertainment）
            max_results: 最大返回结果数
        
        返回值：热搜数据列表，每项是一个字典
        
        工作原理：
            1. 使用requests库发送HTTP请求
            2. 用BeautifulSoup解析HTML页面
            3. 查找包含热搜数据的DOM元素
            4. 提取标题、链接、热度等信息
            5. 返回结构化数据
        """
        try:
            # 动态导入：只在需要时导入，避免启动时的依赖问题
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urlparse, parse_qs, unquote
            
            # 定义URL映射：不同分类对应不同的百度热搜URL
            urls = {
                "all": "https://top.baidu.com/board?tab=realtime",
                "news": "https://top.baidu.com/board?tab=news",
                "entertainment": "https://top.baidu.com/board?tab=entertainment"
            }
            
            # 使用dict.get()安全获取URL，如果category不存在则使用默认值
            url = urls.get(category, urls["all"])
            
            # 请求头，模拟浏览器访问（防止被服务器拒绝）
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://top.baidu.com/",          # 来源页面
                "Accept-Language": "zh-CN,zh;q=0.9",          # 接受中文
            }
            
            # 发送GET请求，timeout=10表示10秒超时
            response = requests.get(url, headers=headers, timeout=10)
            # 设置正确的编码，确保中文不乱码
            response.encoding = 'utf-8'
            
            # 使用BeautifulSoup解析HTML
            # 'html.parser'是Python内置的解析器
            soup = BeautifulSoup(response.text, 'html.parser')
            # 初始化结果列表
            results = []
            
            # 策略：找到所有包含 /s?wd= 的链接（百度搜索链接）
            # 这是热搜链接的标准格式
            # lambda x: 是一个匿名函数，用于过滤href属性
            search_links = soup.find_all('a', href=lambda x: x and 'baidu.com/s?wd=' in x)
            
            # 记录日志：帮助调试
            logger.info(f"找到 {len(search_links)} 个搜索链接")
            
            # 去重和过滤：我们需要找出真正的热搜项（不是"查看更多"等）
            seen_titles = set()  # 使用集合进行去重，set的查找是O(1)时间复杂度
            
            # enumerate()函数：同时获取索引和元素
            for idx, link in enumerate(search_links):
                # 检查是否已达到最大结果数
                if len(results) >= max_results:
                    break
                
                try:
                    # 提取标题文本
                    # strip=True 会移除前后的空白字符
                    title = link.get_text(strip=True)
                    
                    # 过滤掉空标题、导航项和"查看更多"等
                    if not title or len(title) < 2 or title in ['查看更多>', '下一页']:
                        continue
                    
                    # 去重：跳过已经见过的标题
                    if title in seen_titles:
                        continue
                    
                    # 将标题加入已见集合
                    seen_titles.add(title)
                    
                    # 提取URL
                    url_href = link.get('href', '')
                    
                    # 从URL中提取搜索词（URL参数解析）
                    if 'wd=' in url_href:
                        try:
                            # urlparse: 解析URL结构
                            parsed = urlparse(url_href)
                            # parse_qs: 解析查询字符串为字典
                            params = parse_qs(parsed.query)
                            # 获取wd参数（搜索词）
                            search_term = params.get('wd', [''])[0]
                            if search_term:
                                # unquote: URL解码（如 %20 转为空格）
                                search_term = unquote(search_term)
                        except:
                            # 如果解析失败，使用标题作为搜索词
                            search_term = title
                    else:
                        search_term = title
                    
                    # 提取热度信息（可能在link的兄弟元素中）
                    hot_value = 0  # 默认热度为0
                    parent = link.parent  # 获取父元素
                    if parent:
                        # 查找同级的热度span或数字
                        # class_参数使用lambda函数进行模糊匹配
                        hot_span = parent.find(class_=lambda x: x and any(k in (x or '') for k in ['hot', 'num', 'value', 'sc-dot-light']))
                        if hot_span:
                            hot_text = hot_span.get_text(strip=True)
                            # 调用辅助方法解析热度值
                            hot_value = self._parse_hot_value(hot_text)
                    
                    # 确保有有效的热搜数据
                    if search_term or title:
                        # 构建结果字典
                        results.append({
                            "rank": len(results) + 1,  # 排名从1开始
                            "title": search_term if search_term else title,
                            # 如果URL不是完整的，则补全为完整URL
                            "url": url_href if url_href.startswith('http') else f"https://www.baidu.com{url_href}",
                            "hot_value": hot_value,
                            "description": "",  # 百度热搜通常没有描述
                            "source": "baidu",
                            "category": category
                        })
                        
                except Exception as e:
                    # 处理单个链接失败不影响整体
                    logger.debug(f"处理链接失败: {e}")
                    continue
            
            # 记录成功信息
            logger.info(f"成功提取 {len(results)} 条热搜数据")
            return results
            
        except ImportError as e:
            # 缺少依赖库时的错误处理
            logger.error(f"缺少依赖: {e}. 请运行: pip install requests beautifulsoup4")
            return []
        except requests.exceptions.RequestException as e:
            # 网络请求异常（超时、连接失败等）
            logger.error(f"网络请求失败: {e}")
            return []
        except Exception as e:
            # 其他未预期的异常
            logger.error(f"爬取百度热搜失败: {e}")
            import traceback
            traceback.print_exc()  # 打印完整的异常堆栈，便于调试
            return []
    
    def _parse_hot_value(self, text: str) -> int:
        """解析热度值（辅助方法）
        
        参数说明：
            text: 热度文本，如 "100万"、"1.5K"、"999999"
        
        返回值：整数类型的热度值
        
        工作原理：
            1. 使用正则表达式提取数字
            2. 识别单位（万、K、M等）
            3. 转换为整数
        """
        # 空值检查
        if not text:
            return 0
        
        # 移除非数字字符，提取数值
        import re
        # \d+ 匹配一个或多个数字
        # findall 返回所有匹配的字符串列表
        numbers = re.findall(r'\d+', text)
        
        if numbers:
            # 将第一个匹配的数字字符串转为整数
            value = int(numbers[0])
            # 如果文本包含 'K' 或 '万'，乘以 1000
            # 'K' 表示千（Kilo），常用于社交媒体
            if 'K' in text or '万' in text:
                value *= 1000
            # 'M' 表示百万（Million）
            elif 'M' in text or '百万' in text:
                value *= 1000000
            return value
        
        # 如果没有找到数字，返回0
        return 0


class TrendingNewsAggregatorTool(BaseTool):
    """热门新闻聚合工具
    
    功能说明：聚合多个来源的热门新闻，包括百度、微博等
    设计理念：提供统一接口访问多个热搜平台的数据
    扩展性：可以方便地添加更多数据源（如微博、今日头条等）
    """
    
    def __init__(self):
        """构造函数：初始化新闻聚合工具"""
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称：trending_news_aggregator"""
        return "trending_news_aggregator"
    
    @property
    def description(self) -> str:
        """工具描述：说明支持的平台和功能"""
        return "聚合多个来源的热门新闻和热搜话题。支持百度、微博等主要平台。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类：归类为网络搜索工具"""
        return ToolCategory.WEB_SEARCH
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义
        
        sources: 逗号分隔的数据源列表
        max_results: 每个源的最大结果数
        """
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
        """执行热门新闻聚合
        
        工作流程：
            1. 解析sources参数，获取数据源列表
            2. 遍历每个数据源，调用对应的工具
            3. 合并所有结果
            4. 按热度排序
            5. 返回Top N结果
        """
        # 解析sources参数：字符串按逗号分割成列表
        # 例如："baidu,weibo" -> ["baidu", "weibo"]
        sources = kwargs.get("sources", "baidu").split(",")
        max_results = kwargs.get("max_results", 15)
        
        try:
            # 初始化总结果列表
            all_results = []
            
            # 目前只支持百度（未来可以添加微博、今日头条等）
            if "baidu" in sources:
                # 创建百度热搜工具实例
                baidu_tool = BaiduTrendingTool()
                # 执行工具，获取结果
                baidu_result = baidu_tool.execute(category="all", max_results=max_results)
                # 如果执行成功，将数据添加到总结果
                if baidu_result.success:
                    all_results.extend(baidu_result.data)
            
            # TODO: 添加微博热搜支持
            # if "weibo" in sources:
            #     weibo_tool = WeiboTrendingTool()
            #     weibo_result = weibo_tool.execute(max_results=max_results)
            #     if weibo_result.success:
            #         all_results.extend(weibo_result.data)
            
            # 检查是否获取到任何数据
            if not all_results:
                return ToolResult(
                    success=True,
                    output="未获取到任何热门新闻",
                    data=[]
                )
            
            # 按热度排序：使用sorted()函数
            # key参数指定排序依据：lambda表达式提取hot_value
            # reverse=True表示降序排列（热度高的在前）
            all_results.sort(key=lambda x: x.get("hot_value", 0), reverse=True)
            
            # 格式化输出：构建用户友好的展示文本
            output_parts = [f"热门新闻聚合 - 共 {len(all_results)} 条\n"]
            
            # 遍历结果，但只显示前max_results条
            for item in all_results[:max_results]:
                # 输出格式：【排名】标题 (来源)
                output_parts.append(f"【{item['rank']}】 {item['title']} ({item['source']})")
                # 如果有热度值，显示热度
                if item.get('hot_value'):
                    output_parts.append(f"   热度: {item['hot_value']}")
                # 添加空行分隔
                output_parts.append("")
            
            # 返回成功结果
            return ToolResult(
                success=True,
                output="\n".join(output_parts),      # 文本展示
                data=all_results[:max_results],      # 数据数组（限制数量）
                metadata={                            # 元数据
                    "sources": sources,               # 实际使用的数据源
                    "count": len(all_results),        # 总结果数
                    "timestamp": datetime.now().isoformat()  # 时间戳
                }
            )
            
        except Exception as e:
            # 异常处理：记录错误日志并返回失败结果
            logger.error(f"热新闻聚合失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"热新闻聚合失败: {str(e)}"
            )
