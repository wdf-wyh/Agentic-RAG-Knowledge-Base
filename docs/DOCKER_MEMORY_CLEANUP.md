# Docker 内存占用问题排查与清理指南

本文档记录如何诊断和解决 Docker 占用过多磁盘空间的问题。

## 📋 目录

- [快速诊断](#快速诊断)
- [问题原因分析](#问题原因分析)
- [清理方案](#清理方案)
- [预防措施](#预防措施)
- [常用命令速查](#常用命令速查)

---

## 🔍 快速诊断

### 1. 查看 Docker 整体使用情况

```bash
docker system df
```

输出示例：
```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          15        4         39.41GB   16.15GB (40%)
Containers      4         0         486.3MB   486.3MB (100%)
Local Volumes   2         2         65.98MB   0B (0%)
Build Cache     134       10        47.01GB   8.329GB
```

**关键指标：**
- `TOTAL`：总数
- `ACTIVE`：正在使用的数量
- `SIZE`：总占用空间
- `RECLAIMABLE`：可回收空间

### 2. 查看镜像详情

```bash
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
```

### 3. 查看容器详情

```bash
docker container ls -a --format "table {{.Names}}\t{{.Image}}\t{{.Size}}\t{{.Status}}"
```

### 4. 查看构建缓存

```bash
docker buildx du 2>&1 | head -50
```

### 5. 查看项目文件占用

```bash
du -sh /path/to/project/* 2>/dev/null | sort -hr
```

---

## 📊 问题原因分析

### Docker 占用空间的四大来源

| 类型 | 说明 | 典型大小 | 清理风险 |
|------|------|----------|----------|
| **Images（镜像）** | 构建的镜像文件 | 几 GB ~ 几十 GB | ⚠️ 低（保留正在使用的） |
| **Containers（容器）** | 运行/停止的容器 | 几百 MB | ✅ 无（可安全删除停止的） |
| **Volumes（卷）** | 数据持久化 | 几 MB ~ 几 GB | ⚠️ 中（可能包含重要数据） |
| **Build Cache（构建缓存）** | 构建过程缓存 | 几 GB ~ 几十 GB | ✅ 无（可安全清理） |

### 常见问题场景

#### 场景 1：构建缓存累积（最常见）
- **症状**：每次 `docker compose build` 后空间减少
- **原因**：Docker 保留所有历史构建缓存
- **解决**：`docker builder prune`

#### 场景 2：镜像版本累积
- **症状**：同一镜像有多个版本
- **原因**：多次构建产生新旧版本
- **解决**：`docker image prune -a`

#### 场景 3：僵尸容器
- **症状**：大量 Exited 状态的容器
- **原因**：容器停止后未删除
- **解决**：`docker container prune`

#### 场景 4：悬空卷
- **症状**：未使用的数据卷
- **原因**：容器删除后卷残留
- **解决**：`docker volume prune`（⚠️ 先备份数据）

---

## 🧹 清理方案

### 方案 A：安全清理（推荐首选）

清理所有**安全可删除**的内容，不会影响正在运行的服务。

```bash
# 1. 清理停止的容器
docker container prune -f

# 2. 清理构建缓存
docker builder prune -f

# 3. 清理悬空镜像（标签为 <none>）
docker image prune -f

# 4. 查看清理后效果
docker system df
```

**预期效果**：可释放 5-20GB 空间

---

### 方案 B：彻底清理（无运行容器时）

当**没有容器在运行**时，可以执行彻底清理。

```bash
# 1. 停止所有容器
docker compose down

# 2. 删除所有容器
docker container prune -a -f

# 3. 删除所有未使用的镜像
docker image prune -a -f

# 4. 删除所有构建缓存
docker builder prune -a -f

# 5. （可选）删除未使用的卷
# ⚠️ 警告：会删除所有未被容器使用的卷
docker volume prune -a -f

# 6. 验证清理效果
docker system df
```

**预期效果**：可释放 20-50GB 空间

---

### 方案 C：选择性清理（精确控制）

只清理特定类型的内容。

```bash
# 只清理构建缓存
docker builder prune

# 只清理特定镜像
docker rmi <image_id>

# 只清理特定容器
docker rm <container_name>

# 只清理特定卷
docker volume rm <volume_name>
```

---

## 🛡️ 预防措施

### 1. 优化构建策略

```bash
# 构建时不使用缓存（避免缓存累积）
docker compose build --no-cache

# 或者构建前自动清理
docker builder prune -f && docker compose build
```

### 2. 优化 Dockerfile

```dockerfile
# ✅ 好的实践
# 合并 RUN 指令，减少层数
RUN apt-get update && apt-get install -y \
    package1 \
    package2 \
    && rm -rf /var/lib/apt/lists/*

# 使用 .dockerignore 排除不必要文件
# .dockerignore 内容：
.git
*.md
__pycache__
*.pyc
```

### 3. 定期维护计划

```bash
# 每周清理一次（添加到 crontab）
0 2 * * 0 docker builder prune -f

# 或者每次构建前清理
alias docker-build-clean='docker builder prune -f && docker compose build'
```

### 4. 监控脚本

创建监控脚本 `check_docker_space.sh`：

```bash
#!/bin/bash
echo "=== Docker 空间使用情况 ==="
docker system df
echo ""
echo "=== 可回收空间统计 ==="
docker system df --format "{{.Type}}\t{{.Reclaimable}}"
```

---

## ⚡ 常用命令速查

### 诊断命令

```bash
# 整体概况
docker system df

# 镜像列表
docker images

# 容器列表（包括停止的）
docker container ls -a

# 卷列表
docker volume ls

# 构建缓存
docker buildx du
```

### 清理命令

```bash
# 清理停止的容器
docker container prune -f

# 清理悬空镜像
docker image prune -f

# 清理所有未使用的镜像
docker image prune -a -f

# 清理构建缓存
docker builder prune -f

# 清理未使用的卷
docker volume prune -f

# 一键清理所有（慎用）
docker system prune -a -f
```

### 删除命令

```bash
# 删除特定镜像
docker rmi <image_id>

# 删除特定容器
docker rm <container_name>

# 删除特定卷
docker volume rm <volume_name>

# 强制删除
docker rmi -f <image_id>
docker rm -f <container_name>
```

---

## 📝 实战案例

### 案例：ai-platform 项目清理

**问题**：Docker 占用 50GB 空间

**诊断步骤**：

```bash
# 1. 查看整体情况
docker system df
# 发现：Images 39.41GB, Build Cache 47.01GB

# 2. 查看镜像详情
docker images
# 发现：ai-platform-backend 6.85GB，多个旧版本

# 3. 查看容器状态
docker container ls -a
# 发现：4 个容器都处于 Exited 状态
```

**清理步骤**：

```bash
# 1. 清理停止的容器（释放 486MB）
docker container prune -f

# 2. 清理构建缓存（释放 8.3GB）
docker builder prune -f

# 3. 清理未使用的镜像（释放 16GB）
docker image prune -a -f

# 4. 验证效果
docker system df
# 总计释放 ~25GB 空间
```

---

## ⚠️ 注意事项

### 清理前检查清单

- [ ] 确认没有重要容器在运行
- [ ] 备份重要数据卷
- [ ] 记录当前镜像版本
- [ ] 确认清理命令参数

### 数据备份

```bash
# 备份重要卷
docker run --rm -v ai-platform_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .

# 导出镜像
docker save -o backend_backup.tar ai-platform-backend:latest
```

### 恢复操作

```bash
# 导入镜像
docker load -i backend_backup.tar

# 恢复卷
docker run --rm -v ai-platform_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /data
```

---

## 📚 参考资源

- [Docker 官方文档 - 清理 Docker](https://docs.docker.com/config/pruning/)
- [Docker system prune](https://docs.docker.com/engine/reference/commandline/system_prune/)
- [Docker 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

---

**文档版本**：v1.0  
**最后更新**：2026-05-22  
**适用项目**：Agentic-RAG-Knowledge-Base
