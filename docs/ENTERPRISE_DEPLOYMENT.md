# 企业部署指南

本文档说明当前项目企业版能力的推荐部署方式、账号模型、监控接入和备份恢复方案。

## 当前已具备的企业能力

- `JWT + RBAC`：支持 `admin` / `auditor` / `user`
- `审计日志`：关键管理动作会写入审计事件
- `多租户路径隔离`：
  - `vector_db/<tenant_id>`
  - `conversations/<tenant_id>`
  - `data/traces/<tenant_id>`
- `企业回测`：支持检索效果 + 护栏通过率 + 上线门禁
- `Prometheus` 指标导出
- `Grafana` 租户看板
- `Docker Compose` 生产化基础编排

## 默认演示账号

- `admin / admin123`
- `auditor / audit123`
- `demo / demo123`

其中：

- `admin` 位于默认租户 `default`
- `demo` 位于演示租户 `tenant-demo`

## Docker 启动

```bash
cp .env.example .env
docker compose up -d --build
```

### 国内镜像加速

若 `prometheus` / `alertmanager` / `grafana` 镜像从 Docker Hub 拉取失败，在 `.env` 中取消注释以下变量：

```env
PROMETHEUS_IMAGE=docker.m.daocloud.io/prom/prometheus:v2.54.1
ALERTMANAGER_IMAGE=docker.m.daocloud.io/prom/alertmanager:v0.27.0
GRAFANA_IMAGE=docker.m.daocloud.io/grafana/grafana:11.1.0
```

也可在 Docker Desktop 的 `daemon.json` 配置 registry mirror，然后继续使用默认镜像名。

### 本地开发 + 监控栈

若使用 `start.ps1` 在宿主机启动 API，可单独拉起监控组件：

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

此模式会通过 `host.docker.internal:8000` 抓取本机 API 指标，无需构建后端镜像。

Grafana 默认映射到 `3100`（避免与常见本地服务冲突），可通过 `GRAFANA_PORT` 调整。

默认地址：

- Web: `http://localhost`
- API Docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

## 监控与告警

Prometheus 配置与告警规则：

- `deploy/prometheus/prometheus.yml`
- `deploy/prometheus/alert_rules.yml`

Grafana 自动加载：

- 数据源：`deploy/grafana/provisioning/datasources/prometheus.yml`
- Dashboard Provider：`deploy/grafana/provisioning/dashboards/default.yml`
- Dashboard：`deploy/grafana/dashboards/tenant-overview.json`

## 指标说明

当前导出的 Prometheus 指标包括：

- `rag_tenant_requests_total`
- `rag_tenant_errors_total`
- `rag_tenant_avg_latency_ms`
- `rag_tenant_p95_latency_ms`

## 企业 SSO（OIDC）

支持 Azure AD、Keycloak、Authentik 等标准 OIDC IdP。

1. 在 `.env` 中启用：

```env
ENABLE_OIDC=true
OIDC_ISSUER=https://login.microsoftonline.com/{tenant-id}/v2.0
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URI=http://localhost:8000/api/auth/oidc/callback
OIDC_FRONTEND_CALLBACK_URL=http://localhost:5175/
```

2. 在 IdP 中注册回调地址：`http://localhost:8000/api/auth/oidc/callback`
3. 前端登录面板会出现「企业 SSO 登录」按钮
4. IdP 角色通过 `OIDC_ADMIN_ROLES` / `OIDC_AUDITOR_ROLES` 映射到系统 `admin` / `auditor`

## 配额与成本治理

默认按租户按日统计：

- 查询次数
- 估算 token（输入字符/4 + 预留输出）
- 估算成本（按 provider 粗略单价）

```env
ENABLE_QUOTA_ENFORCEMENT=true
QUOTA_DAILY_QUERIES=1000
QUOTA_DAILY_TOKENS=500000
QUOTA_DAILY_COST_USD=20
```

超限返回 HTTP `429`，并触发 `quota.exceeded` Webhook。

管理接口：

- `GET /api/admin/quota`
- 企业管理台「配额与成本」卡片

## 企业 Webhook

```env
WEBHOOK_URL=https://hooks.example.com/rag-events
WEBHOOK_SECRET=change-me
WEBHOOK_EVENTS=auth.login,query.blocked,quota.exceeded,query.completed,build.completed,webhook.test
```

请求头：

- `X-RAG-Event`
- `X-RAG-Signature: sha256=...`（配置了 `WEBHOOK_SECRET` 时）

管理接口：

- `GET /api/admin/webhooks`
- `POST /api/admin/webhooks/test`

## PII 脱敏与 ABAC

默认开启：

```env
ENABLE_PII_REDACTION=true
ENABLE_ABAC=true
```

- 输出脱敏覆盖邮箱、中国大陆手机号、身份证号、常见银行卡号、IPv4
- ABAC 按 `action + resource + roles` 评估，叠加在原有 RBAC 之上
- `GET /api/admin/security` 可查看策略清单

## 数据保留与合规导出

```env
ENABLE_DATA_RETENTION=true
DATA_RETENTION_DAYS=90
```

- 清理范围：`conversations/<tenant>`、`data/traces/<tenant>`、审计 JSONL（按时间戳裁剪）
- `GET /api/admin/retention` 查看状态
- `POST /api/admin/retention/cleanup` 支持 `dry_run`
- `GET /api/admin/compliance-export` 导出 zip（会话 + Trace + 租户审计 + 配额快照）

## 备份与恢复

备份：

```bash
bash scripts/backup.sh
```

恢复：

```bash
bash scripts/restore.sh ./backups/backup_YYYYMMDD_HHMMSS
```

备份范围：

- `vector_db`
- `conversations`
- `logs`
- `data`
- `documents`

## 定时备份示例

### Linux cron

```cron
0 2 * * * cd /opt/agentic-rag && /bin/bash scripts/backup.sh /opt/agentic-rag/backups
```

### Windows 任务计划

可每天调用：

```powershell
bash scripts/backup.sh ./backups
```

## 生产建议

- 把 `.env` 放到受控环境，不要提交密钥
- 对外只暴露前端入口，API 建议走内网或反向代理
- 开启 `ENABLE_AUTH=true`
- 生产环境替换默认示例账号
- 为备份目录配置独立磁盘或对象存储同步
