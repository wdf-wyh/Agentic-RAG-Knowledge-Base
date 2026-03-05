# 腾讯云 CVM 部署完整指南

## 📋 前置要求

### 腾讯云资源
- ✅ CVM 云服务器（推荐配置：4核 8GB、16GB）
- ✅ 公网 IP（已自动分配或需要单独购买）
- 🔄 CDB PostgreSQL（推荐，生产环境）或使用 Docker 内置
- 🔄 Redis CDB（推荐，生产环境）或使用 Docker 内置
- 🔄 COS 对象存储（可选，用于文档备份）

### 本地工具
- SSH 客户端（putty、XShell、iTerm2、Terminal 等）
- 文本编辑器（用于修改配置文件）

---

## 🚀 第一步：初始化 CVM 服务器

### 1.1 连接到 CVM

```bash
# macOS/Linux
ssh -i /path/to/key.pem ubuntu@YOUR_CVM_PUBLIC_IP

# Windows (使用 PuTTY 或 XShell，参考腾讯云文档)
```

### 1.2 检查系统信息

```bash
# 查看操作系统
lsb_release -a

# 查看 CPU 和内存
cat /proc/cpuinfo | grep processor | wc -l
free -h

# 查看磁盘
df -h
```

**支持的操作系统：**
- Ubuntu 20.04 LTS 或更高版本（推荐）
- CentOS 8 或更高版本
- Debian 10 或更高版本

### 1.3 系统更新

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y curl wget git vim

# CentOS
sudo yum update -y
sudo yum install -y curl wget git vim
```

---

## 🐳 第二步：安装 Docker 和 Docker Compose

### 2.1 快速安装脚本（推荐）

腾讯云优化版本（使用腾讯云镜像源：

```bash
# 使用腾讯云官方脚本（CVM 预装）
wget https://mirrors.tencent.com/docker/install_docker.sh
bash install_docker.sh

# 或使用官方 Docker 脚本（国际源，可能较慢）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo bash get-docker.sh
```

### 2.2 配置 Docker 加速（腾讯云专用）

编辑 `/etc/docker/daemon.json`：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
    "registry-mirrors": [
        "https://mirror.ccs.tencentyun.com",
        "https://mirrors.cloud.tencent.com/docker-registry"
    ],
    "insecure-registries": [],
    "storage-driver": "overlay2",
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    }
}
EOF

# 重启 Docker
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 2.3 验证 Docker 安装

```bash
docker --version                    # 检查版本
docker run hello-world              # 测试运行
sudo usermod -aG docker $USER       # 添加用户权限
newgrp docker                       # 刷新权限
```

### 2.4 安装 Docker Compose

```bash
# 方式 1: 从腾讯云源安装
sudo apt-get install -y docker-compose

# 方式 2: 手动安装最新版本
sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

---

## 📦 第三步：克隆项目代码

### 3.1 克隆仓库

```bash
# 进入应用目录
cd /opt
mkdir -p rag-project
cd rag-project

# 克隆仓库（替换为您的仓库地址）
git clone https://github.com/YOUR_ORG/rag-knowledge-base.git .

# 如果使用 SSH：
# git clone git@github.com:YOUR_ORG/rag-knowledge-base.git .

# 如果使用私有仓库，可能需要设置 SSH 密钥
ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub
# 将公钥添加到 GitHub/GitLab
```

### 3.2 创建必要的目录

```bash
mkdir -p /opt/rag-project/{documents,vector_db,logs,backups}
chmod -R 755 /opt/rag-project
```

---

## ⚙️ 第四步：配置环境变量

### 4.1 创建 .env 文件

```bash
cp .env.tencent .env
nano .env    # 或使用 vim .env
```

### 4.2 配置选项 A：本地 Docker 数据库（测试/开发）

```env
# 数据库 - 使用 Docker 内置
DB_ENGINE=postgres
DB_HOST=postgres
DB_PORT=5432
DB_USER=rag_user
DB_PASSWORD=your_secure_password_here
DB_NAME=rag_db

# Redis - 使用 Docker 内置
REDIS_URL=redis://redis:6379/0

# Ollama - 本地推理
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=nomic-embed-text,llama2

# 日志级别
LOG_LEVEL=info
```

### 4.3 配置选项 B：腾讯云托管服务（生产推荐）

#### 创建 CDB PostgreSQL

```bash
# 在 CVM 上测试 CDB 连接
# 先在腾讯云控制台创建 CDB 实例，获取内网 IP 和用户名

psql -h cdb-xxxxx.postgres.tencentcdb.com \
     -U postgres \
     -W \
     -c "CREATE USER rag_user WITH PASSWORD 'password';"

psql -h cdb-xxxxx.postgres.tencentcdb.com \
     -U postgres \
     -W \
     -c "CREATE DATABASE rag_db OWNER rag_user;"
```

更新 .env 文件：

```env
# 数据库 - 使用腾讯云 CDB PostgreSQL
DB_ENGINE=postgres
DB_HOST=cdb-xxxxx.postgres.tencentcdb.com  # 替换为实际 CDB IP
DB_PORT=5432
DB_USER=rag_user
DB_PASSWORD=your_secure_password_here
DB_NAME=rag_db

# Redis - 使用腾讯云 Redis CDB
REDIS_URL=redis://:password@redis-xxxxx.redis.tencentcdb.com:6379/0
# 注意：腾讯云 Redis 的内网地址加密，使用公网地址需要白名单

# Ollama - 本地或专用 GPU 主机
OLLAMA_BASE_URL=http://ollama:11434  # 或 http://gpu-server-ip:11434
OLLAMA_MODEL=nomic-embed-text,llama2

LOG_LEVEL=info
```

#### CDB 连接测试

```bash
# 安装 PostgreSQL 客户端
sudo apt-get install -y postgresql-client

# 测试连接
psql -h your-cdb-ip \
     -U rag_user \
     -d rag_db \
     -c "SELECT version();"
```

#### Redis 连接测试

```bash
# 安装 Redis 客户端
sudo apt-get install -y redis-tools

# 测试连接
redis-cli -h your-redis-ip -a your-password ping
```

### 4.4 可选配置：腾讯云 COS

```env
# 文档存储 - 腾讯云对象存储 COS
# 在腾讯云控制台创建 Bucket 和 API 密钥

TENCENT_COS_BUCKET=your-bucket-name
TENCENT_COS_REGION=ap-beijing  # 替换为您的地域
TENCENT_SECRET_ID=your_secret_id
TENCENT_SECRET_KEY=your_secret_key
TENCENT_COS_PREFIX=rag-documents/
```

---

## 🔐 第五步：安全配置

### 5.1 配置安全组（防火墙）

在腾讯云控制台配置入站规则：

```
协议   端口       来源           说明
TCP    22        0.0.0.0/0      SSH（限制 IP 更安全）
TCP    80        0.0.0.0/0      HTTP
TCP    443       0.0.0.0/0      HTTPS（如已配置）
TCP    8000      内网/私有 IP   API（不对外）
```

### 5.2 配置 UFW 防火墙（CVM 内部）

```bash
sudo ufw enable
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 8000/tcp    # API（仅用于调试）
sudo ufw status
```

### 5.3 设置 SSL/TLS 证书（生产必需）

#### 方式 1：使用腾讯云 SSL 证书

```bash
# 在腾讯云控制台申请证书
# 下载证书到本地，上传到服务器

# 证书应放在：
mkdir -p /opt/rag-project/certs
# 上传 Nginx 证书（fullchain.crt 和 private.key）
```

#### 方式 2：使用 Let's Encrypt（免费）

```bash
# 安装 Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# 生成证书（需要先停止 Nginx）
sudo certbot certonly --standalone -d your-domain.com

# 证书位置：/etc/letsencrypt/live/your-domain.com/
```

配置 Nginx 使用证书，编辑 `frontend/nginx.conf`：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
}

# HTTP 自动重定向到 HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

---

## 🚀 第六步：启动应用

### 6.1 首次启动

```bash
cd /opt/rag-project

# 赋予执行权限
chmod +x deploy/deploy.sh

# 启动服务（自动构建镜像）
bash deploy/deploy.sh start

# 查看服务状态
bash deploy/deploy.sh status
```

### 6.2 验证服务启动

```bash
# 查看所有容器
docker ps

# 查看日志
bash deploy/deploy.sh logs api
bash deploy/deploy.sh logs

# 测试 API
curl http://localhost/api/health
curl http://localhost/health
```

### 6.3 首次初始化（创建数据库表）

```bash
# 进入 API 容器
bash deploy/deploy.sh shell api

# 运行数据库迁移（如果使用 Alembic）
# python -m alembic upgrade head

# 或直接初始化
# python src/scripts/init_db.py

exit
```

---

## ✅ 第七步：验证部署

### 7.1 前端访问验证

```bash
# 使用浏览器访问
http://YOUR_CVM_PUBLIC_IP

# 应该看到 Vue 3 前端界面
```

### 7.2 API 接口验证

```bash
# 健康检查
curl http://YOUR_CVM_PUBLIC_IP/api/health

# 示例响应：
# {"status":"ok","timestamp":"2024-01-15T10:30:00"}

# 搜索文档（需要先上传文档）
curl -X POST http://YOUR_CVM_PUBLIC_IP/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"什么是 RAG","top_k":5}'
```

### 7.3 无 CORS 问题验证

```bash
# 从浏览器控制台运行
fetch('/api/health')
  .then(r => r.json())
  .then(d => console.log(d))

# 不应该有跨域错误（因为 Nginx 代理了所有请求）
```

### 7.4 日志检查

```bash
# 应用日志
bash deploy/deploy.sh logs api | tail -20

# Nginx 日志
docker logs rag-frontend 2>&1 | tail -20

# 数据库日志
bash deploy/deploy.sh logs postgres | tail -10
```

---

## 📊 第八步：性能优化

### 8.1 启用 Nginx 缓存

在 `frontend/nginx.conf` 中添加缓存配置：

```nginx
# 在 http 块中添加
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g inactive=60m;

# 在 location /api/ 块中添加
proxy_cache api_cache;
proxy_cache_valid 200 10m;
proxy_cache_key "$scheme$request_method$host$request_uri";
add_header X-Cache-Status $upstream_cache_status;
```

### 8.2 启用 Gzip 压缩

已在 `frontend/nginx.conf` 中配置：

```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
gzip_min_length 1024;
gzip_vary on;
```

### 8.3 调整 API Worker 进程数

编辑 `.env`：

```env
# 根据 CPU 核心数调整（通常为核心数 * 2 + 1）
API_WORKERS=8    # 4核 CPU 建议设置为 8-10
API_TIMEOUT=60   # API 超时时间（秒）
```

需要重启服务：

```bash
bash deploy/deploy.sh restart
```

### 8.4 数据库性能调优

```bash
# 进入 PostgreSQL
bash deploy/deploy.sh shell postgres

# 连接到数据库
psql -U rag_user -d rag_db

# 创建索引
CREATE INDEX idx_documents_text ON documents USING gin(content);
CREATE INDEX idx_vectors_similarity ON embeddings USING ivfflat(embedding vector_ip_ops) WITH (lists=100);

# 分析表
ANALYZE documents;
ANALYZE embeddings;

exit
```

---

## 📅 第九步：日常维护

### 9.1 自动备份

创建定时备份脚本 `backup.sh`：

```bash
#!/bin/bash
cd /opt/rag-project
bash deploy/deploy.sh backup
```

配置 crontab：

```bash
# 每天凌晨 2 点执行备份
crontab -e

# 添加行：
0 2 * * * /opt/rag-project/backup.sh >> /var/log/rag-backup.log 2>&1
```

### 9.2 监控磁盘空间

```bash
# 检查磁盘使用
df -h /opt

# 检查数据库大小
bash deploy/deploy.sh shell postgres
psql -U rag_user -d rag_db -c "SELECT pg_size_pretty(pg_database_size('rag_db'));"

# 清理旧日志
docker exec rag-backend find /app/logs -mtime +30 -delete
```

### 9.3 定期更新

```bash
# 更新代码
cd /opt/rag-project
git pull origin main

# 重新构建镜像
bash deploy/deploy.sh restart

# 检查服务
bash deploy/deploy.sh status
```

### 9.4 监控服务健康

```bash
# 创建监控脚本 monitor.sh：
#!/bin/bash
while true; do
    if ! curl -f http://localhost/api/health > /dev/null 2>&1; then
        echo "API 服务异常，尝试重启..."
        systemctl restart docker
        cd /opt/rag-project && bash deploy/deploy.sh restart
    fi
    sleep 300  # 每 5 分钟检查一次
done

# 配置为系统服务
sudo systemctl enable monitor
sudo systemctl start monitor
```

---

## 🔧 故障排除

### 问题 1：CORS 错误

**症状：** 前端请求 API 返回 CORS 错误

**解决：** Nginx 应该代理所有请求，检查：

```bash
# 检查 Nginx 配置
docker logs rag-frontend | grep error

# 验证 API 可访问
curl http://localhost/api/health

# 检查网络连接
docker network ls
docker network inspect rag-network
```

### 问题 2：数据库连接失败

**症状：** `could not connect to database`

**解决：**

```bash
# 检查 PostgreSQL 服务
bash deploy/deploy.sh logs postgres

# 测试连接
docker exec rag-postgres psql -U rag_user -d rag_db -c "SELECT 1;"

# 如果使用 CDB，验证 VPC 白名单和安全组设置
```

### 问题 3：内存不足

**症状：** 容器频繁 kill（code 137）

**解决：**

```bash
# 检查内存使用
docker stats

# 减少 API workers
# 编辑 .env: API_WORKERS=4

# 减少 Ollama 并发
bash deploy/deploy.sh logs ollama

# 不在 Docker 中运行 Ollama，改用远程 Ollama
# OLLAMA_BASE_URL=http://ollama-server-ip:11434
```

### 问题 4：文件上传失败

**症状：** `413 Request Entity Too Large`

**解决：** Nginx 配置已包含：

```nginx
client_max_body_size 50M;
```

如需更大，编辑 `frontend/nginx.conf` 并重启。

### 问题 5：SSL 证书过期

**症状：** 浏览器显示证书不安全

**解决：**

```bash
# Let's Encrypt 自动续期
sudo certbot renew --dry-run   # 测试续期

# 或手动续期
sudo certbot certonly --force-renewal -d your-domain.com
```

---

## 📚 相关文档

- [Docker 官方文档](https://docs.docker.com/)
- [腾讯云 CVM 帮助](https://cloud.tencent.com/document/product/213)
- [腾讯云 CDB PostgreSQL](https://cloud.tencent.com/document/product/409)
- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Ollama 使用指南](https://ollama.ai)

---

## 🆘 获取帮助

如遇到问题，请：

1. 查看完整日志：`bash deploy/deploy.sh logs`
2. 检查系统资源：`docker stats`
3. 验证网络连接：`curl http://localhost/api/health`
4. 查看错误日志：`docker logs rag-api 2>&1 | grep error`
5. 提交 Issue 时附加：
   - 错误信息和完整日志
   - CVM 配置（CPU、内存、OS）
   - Docker 版本：`docker --version`
   - 部署配置（`.env` 文件，隐藏密码）

---

**最后更新：2024 年 1 月**

**版本：1.0**
