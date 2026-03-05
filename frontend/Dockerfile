# 前端 + Nginx 服务器 Dockerfile
# 构建过程：编译前端，复制到 Nginx

# 第一阶段：构建前端应用
FROM node:20-alpine AS builder

WORKDIR /app

# 复制 package 文件
COPY package*.json ./

# 安装依赖（使用镜像加速，腾讯云内网快）
RUN npm ci --prefer-offline --no-audit

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 验证构建产物
RUN test -d dist || (echo "Build failed: dist directory not found" && exit 1)

# 第二阶段：运行 Nginx
FROM nginx:alpine

# 设置时区
RUN apk add --no-cache tzdata
ENV TZ=Asia/Shanghai

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/nginx.conf

# 复制前端构建产物到 Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 创建日志目录
RUN mkdir -p /var/log/nginx && \
    touch /var/log/nginx/access.log /var/log/nginx/error.log

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

# 暴露端口
EXPOSE 80 443

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
