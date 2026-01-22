# Playwright 无头浏览器搜索部署指南

Playwright 使用真实浏览器模拟人类搜索行为，可以绑过反爬虫机制。

## 为什么选择 Playwright？

| 特性 | Playwright | DuckDuckGo API | SearXNG |
|------|------------|----------------|---------|
| 绕过反爬虫 | ✅ 模拟真人 | ❌ 容易被封 | ⚠️ 依赖源 |
| 动态内容 | ✅ JS 渲染 | ❌ | ❌ |
| 多引擎支持 | ✅ Google/Bing/百度 | ❌ | ✅ |
| 无需部署服务 | ✅ | ✅ | ❌ 需要 Docker |
| 速度 | ⚠️ 较慢 | ✅ 快 | ✅ 快 |

## 安装

```bash
# 1. 安装 Python 包
pip install playwright

# 2. 安装浏览器（必须）
playwright install chromium

# 或者安装所有浏览器
playwright install
```

## 快速使用

### 方式一：通过 WebSearchTool

```python
from src.agent.tools.web_tools import WebSearchTool

# 使用 Google 搜索
search = WebSearchTool(
    provider="playwright",
    playwright_engine="google",  # google, bing, duckduckgo, baidu
    playwright_headless=True     # 无头模式
)

result = search.execute(query="Python 机器学习", max_results=10)
print(result.output)
```

### 方式二：多引擎聚合搜索

```python
from src.agent.tools.web_tools import WebSearchTool

# 同时搜索多个引擎，聚合结果
search = WebSearchTool(provider="playwright_multi")

result = search.execute(query="大语言模型最新进展", max_results=10)
print(result.output)
```

### 方式三：直接使用 PlaywrightSearch

```python
from src.agent.tools.search_proxy import PlaywrightSearch, SearchEngine

# 单引擎搜索
searcher = PlaywrightSearch(
    engine=SearchEngine.GOOGLE,
    headless=True,
    slow_mo=100  # 操作延迟，更像人类
)

# 同步搜索
results = searcher.search("Python 教程", max_results=10)

for r in results:
    print(f"{r.title}")
    print(f"  {r.url}")
    print(f"  {r.snippet[:100]}...")
    print()

# 异步搜索（推荐，性能更好）
import asyncio

async def main():
    results = await searcher.search_async("机器学习入门")
    return results

results = asyncio.run(main())
```

### 方式四：多引擎并行搜索

```python
from src.agent.tools.search_proxy import MultiEnginePlaywrightSearch, SearchEngine

# 同时搜索 Google、Bing、DuckDuckGo
searcher = MultiEnginePlaywrightSearch(
    engines=[
        SearchEngine.GOOGLE,
        SearchEngine.BING,
        SearchEngine.DUCKDUCKGO
    ],
    headless=True
)

# 结果会自动去重和排序
results = searcher.search("RAG 技术", max_results=15)
```

## 抓取网页内容

Playwright 还可以抓取 JavaScript 渲染的动态页面：

```python
import asyncio
from src.agent.tools.search_proxy import PlaywrightSearch

searcher = PlaywrightSearch()

async def fetch_content():
    content = await searcher.fetch_page_content(
        url="https://example.com/dynamic-page",
        max_length=10000
    )
    print(content["title"])
    print(content["content"])

asyncio.run(fetch_content())
```

## 支持的搜索引擎

| 引擎 | 枚举值 | 说明 |
|------|--------|------|
| Google | `SearchEngine.GOOGLE` | 最全面，但需翻墙 |
| Bing | `SearchEngine.BING` | 国内可用 |
| DuckDuckGo | `SearchEngine.DUCKDUCKGO` | 隐私友好 |
| 百度 | `SearchEngine.BAIDU` | 中文最优 |

## 配置选项

```python
PlaywrightSearch(
    engine=SearchEngine.GOOGLE,  # 搜索引擎
    headless=True,               # 无头模式（不显示浏览器窗口）
    slow_mo=100,                 # 操作延迟（毫秒），模拟人类
    proxy="http://proxy:8080",   # 代理服务器
    cache_enabled=True,          # 启用结果缓存
    cache_ttl=3600               # 缓存有效期（秒）
)
```

## 浏览器指纹随机化

Playwright 搜索自动随机化浏览器指纹，包括：

- User-Agent（随机桌面浏览器）
- 视口大小（1920x1080, 1366x768 等）
- 语言和时区
- 鼠标滚动行为

## 性能优化建议

### 1. 启用缓存

```python
searcher = PlaywrightSearch(cache_enabled=True, cache_ttl=3600)
# 相同查询不会重复搜索
```

### 2. 使用异步

```python
# 异步搜索性能更好
results = await searcher.search_async(query)
```

### 3. 控制结果数量

```python
# 只获取需要的结果数
results = searcher.search(query, max_results=5)
```

### 4. 复用搜索器实例

```python
# 不要每次创建新实例
searcher = PlaywrightSearch()  # 创建一次

# 多次使用
results1 = searcher.search("query1")
results2 = searcher.search("query2")
```

## 故障排除

### 问题：浏览器启动失败

```bash
# 重新安装浏览器
playwright install chromium --force

# 检查依赖
playwright install-deps
```

### 问题：搜索超时

1. 检查网络连接
2. 增加超时时间
3. 使用代理

### 问题：被搜索引擎封禁

1. 增加 `slow_mo` 值
2. 使用代理池
3. 切换到其他搜索引擎

## 与其他方案对比

```
场景                          推荐方案
─────────────────────────────────────────
需要最新信息，网络稳定         → Playwright (Google)
国内环境，中文搜索             → Playwright (百度/Bing)
大量请求，需要稳定性           → SearXNG
需要 AI 优化的搜索             → Tavily
简单测试，快速使用             → DuckDuckGo API
```

## 参考链接

- [Playwright Python 文档](https://playwright.dev/python/)
- [Playwright GitHub](https://github.com/microsoft/playwright-python)
