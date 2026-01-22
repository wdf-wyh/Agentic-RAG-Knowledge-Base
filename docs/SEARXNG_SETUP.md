# SearXNG 本地搜索代理部署指南

SearXNG 是一个开源的元搜索引擎，聚合多个搜索引擎的结果，是本项目**推荐的联网搜索方案**。

## 为什么选择 SearXNG？

| 特性 | SearXNG | DuckDuckGo | Tavily |
|------|---------|------------|--------|
| 免费 | ✅ | ✅ | ⚠️ 有限额 |
| 无需 API Key | ✅ | ✅ | ❌ |
| 不被限流 | ✅ | ❌ 容易被封 | ✅ |
| 隐私友好 | ✅ | ✅ | ❌ |
| 聚合多引擎 | ✅ | ❌ | ❌ |
| 可自托管 | ✅ | ❌ | ❌ |

## 快速部署

### 方式一：Docker Compose（推荐）

```bash
# 在项目根目录执行
docker-compose -f deploy/docker-compose.searxng.yml up -d

# 查看状态
docker-compose -f deploy/docker-compose.searxng.yml ps

# 查看日志
docker-compose -f deploy/docker-compose.searxng.yml logs -f
```

### 方式二：Docker 单容器

```bash
docker run -d \
  --name searxng \
  -p 8080:8080 \
  -v ./deploy/searxng:/etc/searxng:rw \
  searxng/searxng:latest
```

## 验证部署

1. **访问 Web 界面**
   打开浏览器访问 http://localhost:8080

2. **测试 API**
   ```bash
   curl "http://localhost:8080/search?q=Python&format=json" | jq
   ```

3. **健康检查**
   ```bash
   curl http://localhost:8080/healthz
   ```

## 配置项目使用 SearXNG

### 方式一：环境变量

```bash
# .env 文件
SEARXNG_URL=http://localhost:8080
```

### 方式二：代码配置

```python
from src.agent.tools.web_tools import WebSearchTool

# 创建使用 SearXNG 的搜索工具
search_tool = WebSearchTool(
    provider="searxng",
    searxng_url="http://localhost:8080",
    cache_enabled=True
)

# 执行搜索
result = search_tool.execute(query="Python 教程", max_results=10)
print(result.output)
```

### 方式三：直接使用 SearXNG 客户端

```python
from src.agent.tools.search_proxy import SearXNGClient

client = SearXNGClient("http://localhost:8080")

# 通用搜索
results = client.search("大语言模型", max_results=10)

# 新闻搜索
news = client.search_news("AI 最新进展", time_range="week")

# 学术搜索
papers = client.search_academic("Transformer architecture")

# 检查服务状态
if client.is_available():
    print("SearXNG 服务正常")
```

## 自定义配置

编辑 `deploy/searxng/settings.yml` 可以：

- 启用/禁用特定搜索引擎
- 设置默认语言和地区
- 配置安全搜索级别
- 启用 Redis 缓存提升性能

### 常用配置示例

```yaml
# 只启用特定搜索引擎
engines:
  - name: google
    disabled: false
  - name: bing
    disabled: true  # 禁用 Bing
    
# 设置默认语言为中文
search:
  default_lang: "zh-CN"
```

## 故障排除

### 问题：无法连接到 SearXNG

```bash
# 检查容器是否运行
docker ps | grep searxng

# 查看容器日志
docker logs rag-searxng

# 重启服务
docker-compose -f deploy/docker-compose.searxng.yml restart
```

### 问题：搜索结果为空

1. 检查网络连接（SearXNG 需要访问外部搜索引擎）
2. 查看日志确认搜索引擎是否正常响应
3. 尝试在 Web 界面手动搜索

### 问题：搜索速度慢

1. 启用 Redis 缓存（已在 docker-compose 中配置）
2. 减少启用的搜索引擎数量
3. 设置合理的超时时间

## 生产环境部署建议

1. **使用 HTTPS**
   配置 Nginx 反向代理并启用 SSL

2. **设置密钥**
   ```bash
   export SEARXNG_SECRET=$(openssl rand -hex 32)
   ```

3. **启用限流**
   在 `settings.yml` 中设置 `limiter: true`

4. **定期更新**
   ```bash
   docker-compose -f deploy/docker-compose.searxng.yml pull
   docker-compose -f deploy/docker-compose.searxng.yml up -d
   ```

## 参考链接

- [SearXNG 官方文档](https://docs.searxng.org/)
- [SearXNG GitHub](https://github.com/searxng/searxng)
- [SearXNG 公共实例列表](https://searx.space/)
