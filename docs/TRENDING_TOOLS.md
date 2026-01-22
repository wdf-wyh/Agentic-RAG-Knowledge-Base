# 热搜工具使用指南

## 简介

新增的热搜工具可以帮助Agent获取实时的热搜、热榜数据，目前支持百度热搜。

## 可用工具

### 1. BaiduTrendingTool（百度热搜工具）

获取百度热搜实时排行数据。

**参数：**
- `category` (可选): 热搜分类
  - `'all'`: 综合热搜（默认）
  - `'news'`: 新闻热榜
  - `'entertainment'`: 娱乐热榜
- `max_results` (可选): 最大返回结果数，默认10

**使用示例：**
```python
from src.agent.tools.trending_tools import BaiduTrendingTool

tool = BaiduTrendingTool()

# 获取综合热搜前10条
result = tool.execute(category="all", max_results=10)
if result.success:
    for item in result.data:
        print(f"【{item['rank']}】 {item['title']}")
        print(f"  热度: {item['hot_value']}")
        print(f"  链接: {item['url']}")
```

**返回数据结构：**
```python
{
    "rank": 1,              # 排名
    "title": "热搜标题",    # 标题
    "url": "https://...",   # 搜索链接
    "hot_value": 12345,     # 热度值
    "description": "",      # 描述
    "source": "baidu",      # 数据来源
    "category": "all"       # 分类
}
```

### 2. TrendingNewsAggregatorTool（热门新闻聚合工具）

聚合多个来源的热门新闻和热搜话题。

**参数：**
- `sources` (可选): 数据来源，逗号分隔，默认 'baidu'
  - 目前仅支持 'baidu'
- `max_results` (可选): 最大返回结果数，默认15

**使用示例：**
```python
from src.agent.tools.trending_tools import TrendingNewsAggregatorTool

agg_tool = TrendingNewsAggregatorTool()

# 聚合百度热搜
result = agg_tool.execute(sources="baidu", max_results=15)
if result.success:
    print(f"共获取 {len(result.data)} 条热门新闻")
```

## 在Agent中使用

这些工具已经自动注册到RAG Agent中，可以直接使用：

```python
from src.agent.rag_agent import RAGAgent

agent = RAGAgent(enable_web_search=True)

# Agent会自动使用热搜工具
response = agent.run("今天的热搜是什么？")
```

## 问题排查

### 问题1: 获取不到热搜数据

**可能原因：**
- 网络连接问题
- 百度网站结构变化

**解决方案：**
1. 检查网络连接
2. 查看日志中的错误信息
3. 如果百度网站HTML结构变化，可能需要更新选择器

### 问题2: 数据与实际不符

**原因分析：**
- 缓存问题：工具有缓存机制，刷新缓存后重试
- 渲染问题：百度热搜涉及动态内容，某些情况下可能不完整

**解决方案：**
1. 刷新浏览器查看实际热搜
2. 检查是否有网络延迟导致数据不完整
3. 尝试多次请求以确保数据准确性

## 数据准确性

**当前实现的特点：**
- ✅ 支持实时获取百度热搜
- ✅ 自动去重和过滤
- ✅ 提供搜索链接
- ✅ 支持多个热搜分类
- ⚠️ 热度值提取可能不完整（取决于页面结构）

**建议用法：**
1. 用于获取最新的热点话题
2. 用于分析当前的社会热点
3. 用于信息检索和新闻研究

## 扩展计划

未来可能添加的功能：
- [ ] 微博热搜支持
- [ ] 头条热榜支持
- [ ] 抖音热榜支持
- [ ] 热搜历史数据
- [ ] 热搜趋势分析
