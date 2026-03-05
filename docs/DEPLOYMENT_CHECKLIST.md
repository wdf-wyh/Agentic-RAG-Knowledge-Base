# 部署验证清单（Deployment Checklist）

用于验证腾讯云 CVM 上的部署是否成功完成。

## ⚠️ 部署前检查

### 基础环境
- [ ] CVM 实例已创建并运行（SSH 联通）
- [ ] 公网 IP 已分配或已购买
- [ ] 安全组入站规则已配置（22、80、443）
- [ ] 系统已更新：`sudo apt-get update && sudo apt-get upgrade -y`
- [ ] 必要工具已安装：`curl wget git vim`

### 腾讯云服务（如使用托管服务）
- [ ] CDB PostgreSQL 已创建，能从 CVM 内网连接
- [ ] Redis CDB 已创建，能从 CVM 内网连接
- [ ] COS Bucket 已创建（可选）
- [ ] API 密钥已获取（COS 用）

---

## 🔧 部署步骤验证

### 第 1-2 步：Docker 安装

```bash
# 验证步骤
docker --version
# 预期：Docker version XX.XX.XX, build xxxxxxx

docker run hello-world
# 预期：Hello from Docker! 信息

docker-compose --version
# 预期：Docker Compose version XX.XX.XX, build xxxxxxx
```

验证结果：
- [ ] Docker 已安装
- [ ] Docker Compose 已安装
- [ ] 镜像加速已配置（检查 /etc/docker/daemon.json）

### 第 3 步：代码克隆

```bash
# 验证步骤
cd /opt/rag-project
ls -la

# 预期输出包含：
# deploy/
# frontend/
# src/
# docker-compose.prod.yml
# Dockerfile
# .env.tencent
```

验证结果：
- [ ] 项目代码已克隆
- [ ] 所有必要文件都存在
- [ ] 目录结构正确

### 第 4 步：环境配置

```bash
# 验证步骤
cd /opt/rag-project
test -f .env && echo "✅ .env 文件存在" || echo "❌ .env 文件缺失"

# 检查关键变量
grep "DB_PASSWORD" .env
grep "REDIS_URL" .env
grep "OLLAMA_BASE_URL" .env
```

验证结果：
- [ ] .env 文件已创建（从 .env.tencent 复制）
- [ ] 数据库密码已修改为强密码
- [ ] 数据库连接信息正确配置
- [ ] Redis 连接信息正确配置

### 本地数据库连接测试（如使用 Docker 内置）

```bash
cd /opt/rag-project

# 测试 PostgreSQL 连接
docker-compose -f deploy/docker-compose.prod.yml --env-file .env \
  run --rm -T postgres psql -h postgres -U rag_user -d rag_db -c "SELECT version();"
# 预期：显示 PostgreSQL 版本信息

# 测试 Redis 连接
docker-compose -f deploy/docker-compose.prod.yml --env-file .env \
  run --rm -T redis redis-cli -h redis ping
# 预期：PONG
```

验证结果：
- [ ] PostgreSQL 连接成功（如使用 Docker）
- [ ] Redis 连接成功（如使用 Docker）
- [ ] 或 CDB 连接成功（如使用腾讯云托管）

---

## 🚀 启动应用

### 启动服务

```bash
cd /opt/rag-project

# 赋予脚本权限
chmod +x deploy/deploy.sh

# 启动服务
bash deploy/deploy.sh start
# 预期：等待 30-60 秒构建镜像和启动容器

# 查看输出示例：
# ✅ ===
# ✅ 服务启动完成！
# ✅ ===
# [INFO] 前端访问地址: http://YOUR_SERVER_IP
# [INFO] API 地址: http://YOUR_SERVER_IP/api
```

验证结果：
- [ ] 开始构建 Docker 镜像
- [ ] 容器成功启动
- [ ] 没有明显错误信息

### 验证容器运行状态

```bash
# 命令
docker ps

# 预期输出：应该看到 6 个容器都在运行
# rag-frontend    (web service - Nginx)
# rag-api         (FastAPI backend)
# rag-postgres    (PostgreSQL)
# rag-redis       (Redis cache)
# rag-ollama      (LLM inference)
# rag-searxng     (optional - Search)

# 命令
bash deploy/deploy.sh status

# 预期：显示 "Up" 状态
```

验证结果：
- [ ] 所有核心容器都在运行（至少 5 个）：
  - [ ] rag-frontend
  - [ ] rag-api
  - [ ] rag-postgres
  - [ ] rag-redis
  - [ ] rag-ollama

---

## 🌐 网络和连接验证

### 本地连接测试（在 CVM 上）

```bash
# 查看开放的端口
sudo netstat -tulpn | grep LISTEN

# 预期：应该看到：
# 0.0.0.0:80 (Nginx)
# 0.0.0.0:443 (Nginx - 如果配置了 HTTPS)
```

验证结果：
- [ ] 端口 80 已开放（HTTP）
- [ ] 端口 443 已开放（HTTPS，如配置）

### 前端 Web UI 测试

```bash
# 从 CVM 本地测试
curl -I http://localhost/

# 预期输出：
# HTTP/1.1 200 OK
# Server: nginx
# Content-Type: text/html; charset=utf-8
```

验证结果：
- [ ] 前端 Web 服务响应成功（200 OK）
- [ ] Server 头显示 nginx

### 健康检查

```bash
# API 健康检查
curl http://localhost/api/health

# 预期输出（JSON 格式）：
# {"status":"ok","timestamp":"2024-01-15T10:30:00"}

# 也可能有其他字段，只需确保返回 200 OK
```

验证结果：
- [ ] API 健康检查返回 200 OK
- [ ] 响应是有效的 JSON 格式

### 从外部测试（从笔记本/PC）

```bash
# 替换 YOUR_CVM_PUBLIC_IP 为实际 IP
curl http://YOUR_CVM_PUBLIC_IP/api/health

# 预期：同上
```

验证结果：
- [ ] 能从外部网络访问（公网可达）
- [ ] 返回健康状态

---

## 🔒 无 CORS 验证

### 浏览器测试（最重要）

在浏览器地址栏访问：
```
http://YOUR_CVM_PUBLIC_IP
```

打开浏览器开发者工具（F12）→ 控制台（Console）：

```javascript
// 在控制台运行以下代码
fetch('/api/health')
  .then(r => r.json())
  .then(d => console.log('Success:', d))
  .catch(e => console.log('Error:', e))
```

验证结果：
- [ ] 控制台显示 `Success:` 和响应对象，**没有 CORS 错误**
- [ ] 如果看到 `Access to XMLHttpRequest has been blocked by CORS policy`，则 Nginx 代理配置有问题

### 检查 Nginx 配置

```bash
# 验证 Nginx 是否正确代理 API
docker logs rag-frontend 2>&1 | grep "proxy" | head -5

# 或进入容器检查配置
docker exec rag-frontend grep -n "proxy_pass" /etc/nginx/conf.d/default.conf
# 预期：显示 "proxy_pass http://api:8000;"
```

验证结果：
- [ ] Nginx 配置包含 `proxy_pass http://api:8000;`
- [ ] 没有 CORS 相关的错误日志

---

## 📊 日志检查

### API 日志

```bash
# 查看最近 20 行日志
bash deploy/deploy.sh logs api | tail -20

# 预期：应该看到启动信息，例如：
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

验证结果：
- [ ] API 服务成功启动
- [ ] 没有 ERROR 或 CRITICAL 级别的错误

### Nginx 日志

```bash
# 查看 Nginx 日志
docker logs rag-frontend | tail -20

# 预期：应该看到以下类似内容：
# 192.168.x.x - - [...] "GET / HTTP/1.1" 200 ...
```

验证结果：
- [ ] Nginx 接收到请求
- [ ] 大部分响应是 200 状态码

### 数据库日志

```bash
# 查看数据库日志
bash deploy/deploy.sh logs postgres | tail -20

# 预期：应该看到数据库已启动
# LOG:  database system is ready to accept connections
```

验证结果：
- [ ] 数据库成功启动
- [ ] 能接受连接

### 检查错误

```bash
# 查找所有日志中的错误
bash deploy/deploy.sh logs 2>&1 | grep -i "error" | head -10

# 如果没有输出，则没有错误
```

验证结果：
- [ ] 没有 ERROR 日志或错误数量可接受

---

## 📝 功能测试

### 文档上传测试（如果实现了）

```bash
# 上传文件
curl -X POST "http://YOUR_CVM_PUBLIC_IP/api/documents/upload" \
  -F "file=@/path/to/test.pdf"

# 预期：返回 200 或 201，包含文件 ID
```

验证结果：
- [ ] 能成功上传文档
- [ ] 返回成功状态码

### 搜索功能测试

```bash
# 搜索查询
curl -X POST "http://YOUR_CVM_PUBLIC_IP/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"测试查询","top_k":5}'

# 预期：返回 200，包含搜索结果
```

验证结果：
- [ ] 搜索接口可访问
- [ ] 返回正确的响应格式

### RAG 查询测试

```bash
# RAG 生成式回答
curl -X POST "http://YOUR_CVM_PUBLIC_IP/api/rag/generate" \
  -H "Content-Type: application/json" \
  -d '{"query":"请解释 RAG","top_k":3}'

# 预期：返回生成的答案
```

验证结果：
- [ ] RAG 生成接口可访问
- [ ] 能返回基于文档的回答

---

## 💾 数据持久化验证

### 检查数据是否持久化

```bash
# 停止容器
docker-compose -f deploy/docker-compose.prod.yml --env-file .env down

# 查看卷
docker volume ls | grep rag

# 预期：应该看到几个 rag 相关的卷
# rag-postgres-data
# rag-redis-data
# rag-ollama-data
```

验证结果：
- [ ] 数据卷已创建
- [ ] 卷名称正确

```bash
# 重新启动服务
bash deploy/deploy.sh start

# 验证文件是否恢复
curl http://YOUR_CVM_PUBLIC_IP/api/health

# 预期：应该返回成功
```

验证结果：
- [ ] 重启后数据完整
- [ ] 之前上传的文档仍然存在

---

## 🔄 自动重启验证（可选）

### 测试容器自动重启

```bash
# 停止 API 容器
docker stop rag-api

# 等待 30 秒
sleep 30

# 检查容器状态
docker ps | grep rag-api

# 预期：容器应该自动重启（UP ... (health: starting))
```

验证结果：
- [ ] 容器支持自动重启政策
- [ ] 服务故障时能自动恢复

---

## 🎯 完整性清单

### 核心功能
- [ ] 前端 Web UI 可正常访问
- [ ] 后端 API 可正常调用
- [ ] 没有 CORS 错误
- [ ] 健康检查正常
- [ ] 容器能自动重启

### 数据存储
- [ ] PostgreSQL 数据库运行正常
- [ ] Redis 缓存运行正常
- [ ] 文档存储正常
- [ ] 向量数据库正常
- [ ] 数据持久化正常

### 文件和日志
- [ ] 应用日志正常生成
- [ ] Nginx 日志正常生成
- [ ] 数据库日志正常生成
- [ ] 向量数据库文件存在
- [ ] 文档文件夹不为空（上传文档后）

### 安全和网络
- [ ] 防火墙规则正确配置
- [ ] HTTPS 安全证书已配置（生产环境）
- [ ] 只有必要的端口开放
- [ ] 数据库密码已修改

### 部署工具
- [ ] deploy.sh 脚本可执行
- [ ] 备份脚本可正常运行
- [ ] 日志轮转已配置

---

## 📋 部署后配置

### 配置定时备份

```bash
# 编辑 crontab
crontab -e

# 添加每日备份任务（凌晨 2 点）
0 2 * * * cd /opt/rag-project && bash deploy/deploy.sh backup >> /var/log/rag-backup.log 2>&1
```

验证结果：
- [ ] 备份计划已配置
- [ ] 能看到 /var/log/rag-backup.log

### 监控脚本配置（可选）

```bash
# 创建监控脚本
sudo tee /usr/local/bin/rag-monitor.sh > /dev/null << 'EOF'
#!/bin/bash
if ! curl -f http://localhost/api/health > /dev/null 2>&1; then
    systemctl restart docker
    cd /opt/rag-project && bash deploy/deploy.sh restart
fi
EOF

# 赋予执行权限
sudo chmod +x /usr/local/bin/rag-monitor.sh

# 添加到 crontab（每 5 分钟检查一次）
crontab -e
# 添加：*/5 * * * * /usr/local/bin/rag-monitor.sh >> /var/log/rag-monitor.log 2>&1
```

验证结果：
- [ ] 监控脚本已创建
- [ ] 已添加到定时任务

---

## ❌ 故障排查

如果任何检查失败，按以下步骤排查：

### 一般故障排查流程

1. **查看完整日志**
   ```bash
   bash deploy/deploy.sh logs
   ```

2. **重启服务**
   ```bash
   bash deploy/deploy.sh restart
   ```

3. **查看容器资源使用**
   ```bash
   docker stats
   ```

4. **检查网络连接**
   ```bash
   docker network inspect rag-network
   ```

5. **进入容器调试**
   ```bash
   bash deploy/deploy.sh shell api
   # 在容器内运行命令
   ```

### 常见问题速查表

| 问题 | 症状 | 解决方案 |
|------|------|--------|
| CORS 错误 | 浏览器控制台显示 CORS 错误 | 检查 Nginx 配置，确保 proxy_pass 设置正确 |
| 数据库连接失败 | API 日志显示 DB 连接错误 | 检查 .env 中的数据库配置和连接字符串 |
| 内存不足 | 容器频繁被 kill | 减少 API workers 数量，或增加服务器 RAM |
| 磁盘满 | 容器写入失败 | 清理 Docker 日志和临时文件 |
| 容器不启动 | `docker ps` 看不到容器 | 查看 `docker logs` 获取错误信息 |

---

## ✅ 最终验证

所有检查完成后，运行最终验证：

```bash
cd /opt/rag-project

# 运行完整诊断
echo "=== Docker 版本 ==="
docker --version

echo "=== 容器状态 ==="
bash deploy/deploy.sh status

echo "=== API 状态 ==="
curl -I http://localhost:80/

echo "=== 数据库连接 ==="
docker exec rag-postgres pg_isready -U rag_user -d rag_db

echo "=== Redis 连接 ==="
docker exec rag-redis redis-cli ping
```

如果所有命令都返回成功状态，部署就完成了！

---

**检查完成日期：** _________________

**检查人员：** _________________

**备注：** _____________________________________________________________

---

**下一步行动：**
- [ ] 配置 DNS 和域名解析（可选）
- [ ] 配置 SSL/TLS 证书（推荐）
- [ ] 配置日志聚合（可选）
- [ ] 配置监控告警（可选）
- [ ] 集成 CI/CD（可选）
