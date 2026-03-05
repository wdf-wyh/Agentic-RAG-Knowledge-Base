#!/bin/bash
# 腾讯云服务器自动化部署脚本
# 使用方式: bash deploy/deploy.sh [start|stop|restart|logs|backup|restore]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
PROJECT_NAME="rag"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${DEPLOY_DIR}/.env"
COMPOSE_FILE="${DEPLOY_DIR}/deploy/docker-compose.prod.yml"
BACKUP_DIR="${DEPLOY_DIR}/backups"

# ============================================================
# 日志函数
# ============================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================
# 检查环境
# ============================================================
check_environment() {
    log_info "检查环境..."
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    # 检查 Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    # 检查所需文件
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "docker-compose.prod.yml 不存在"
        exit 1
    fi
    
    # 检查 .env 文件
    if [ ! -f "${ENV_FILE}" ]; then
        log_warning ".env 文件不存在，复制 .env.tencent 作为模板"
        cp "${DEPLOY_DIR}/.env.tencent" "${ENV_FILE}"
        log_warning "请修改 ${ENV_FILE} 中的配置，然后重新运行脚本"
        exit 1
    fi
    
    log_success "环境检查通过"
}

# ============================================================
# 启动服务
# ============================================================
start_services() {
    log_info "启动服务..."
    
    cd "${DEPLOY_DIR}"
    
    # 构建镜像
    log_info "构建 Docker 镜像（首次部署会花费较长时间）..."
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build
    
    # 启动服务
    log_info "启动容器..."
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5
    
    # 检查服务状态
    log_info "检查服务状态..."
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps | grep -q "rag-backend.*Up"; then
        log_success "后端服务已启动"
    else
        log_error "后端服务启动失败"
        return 1
    fi
    
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps | grep -q "rag-frontend.*Up"; then
        log_success "前端服务已启动"
    else
        log_error "前端服务启动失败"
        return 1
    fi
    
    # 显示访问地址
    log_success "===================="
    log_success "服务启动完成！"
    log_success "===================="
    log_info "前端访问地址: http://YOUR_SERVER_IP"
    log_info "API 地址: http://YOUR_SERVER_IP/api"
    
    return 0
}

# ============================================================
# 停止服务
# ============================================================
stop_services() {
    log_info "停止服务..."
    
    cd "${DEPLOY_DIR}"
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
    
    log_success "服务已停止"
}

# ============================================================
# 重启服务
# ============================================================
restart_services() {
    log_info "重启服务..."
    
    stop_services
    sleep 2
    start_services
}

# ============================================================
# 查看日志
# ============================================================
show_logs() {
    local service=$1
    
    cd "${DEPLOY_DIR}"
    
    if [ -z "$service" ]; then
        log_info "显示所有服务日志（Ctrl+C 退出）..."
        docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs -f
    else
        log_info "显示 ${service} 服务日志（Ctrl+C 退出）..."
        docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs -f "$service"
    fi
}

# ============================================================
# 备份数据
# ============================================================
backup_data() {
    log_info "开始备份数据..."
    
    mkdir -p "${BACKUP_DIR}"
    
    local backup_time=$(date +%Y%m%d_%H%M%S)
    local backup_name="${BACKUP_DIR}/backup_${backup_time}"
    
    cd "${DEPLOY_DIR}"
    
    # 备份数据库
    log_info "备份 PostgreSQL 数据库..."
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T postgres \
        pg_dump -U "${DB_USER:-rag_user}" "${DB_NAME:-rag_db}" > "${backup_name}_db.sql"
    
    # 备份向量数据库和文档
    log_info "备份向量数据库和文档..."
    tar -czf "${backup_name}_data.tar.gz" vector_db/ documents/ 2>/dev/null || true
    
    # 保存配置
    log_info "备份配置文件..."
    cp "${ENV_FILE}" "${backup_name}_env.bak"
    
    log_success "备份完成: ${backup_name}_*"
    log_info "备份文件大小:"
    du -sh "${backup_name}"* 2>/dev/null | head -5
}

# ============================================================
# 恢复数据
# ============================================================
restore_data() {
    local backup_name=$1
    
    if [ -z "$backup_name" ]; then
        log_error "请指定备份文件名"
        log_info "可用备份:"
        ls -lh "${BACKUP_DIR}/" 2>/dev/null | tail -10
        return 1
    fi
    
    log_warning "警告：恢复数据将覆盖当前数据库！"
    read -p "确认恢复？(yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "已取消恢复"
        return
    fi
    
    cd "${DEPLOY_DIR}"
    
    log_info "停止服务..."
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
    
    log_info "恢复数据库..."
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d postgres
    sleep 5
    
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T postgres \
        psql -U "${DB_USER:-rag_user}" "${DB_NAME:-rag_db}" < "${backup_name}_db.sql"
    
    log_info "恢复数据文件..."
    rm -rf vector_db/ documents/
    tar -xzf "${backup_name}_data.tar.gz" 2>/dev/null || log_warning "数据文件解压失败"
    
    log_success "数据恢复完成，重新启动服务..."
    start_services
}

# ============================================================
# 显示帮助
# ============================================================
show_help() {
    cat << EOF
${BLUE}RAG 知识库 - 腾讯云部署脚本${NC}

${GREEN}使用方式:${NC}
    bash ${BASH_SOURCE[0]} [命令] [选项]

${GREEN}可用命令:${NC}
    start           启动服务
    stop            停止服务
    restart         重启服务
    logs [服务]     查看日志 (可选: api, web, postgres, redis, ollama)
    status          查看服务状态
    backup          备份数据库和文档
    restore [备份]  恢复备份数据
    ps              查看容器进程
    shell [服务]    进入容器 shell
    clean           清理停止的容器和镜像
    help            显示此帮助信息

${GREEN}示例:${NC}
    bash deploy/deploy.sh start              # 启动所有服务
    bash deploy/deploy.sh logs api           # 查看 API 日志
    bash deploy/deploy.sh backup             # 备份数据
    bash deploy/deploy.sh shell api          # 进入 API 容器

${YELLOW}注意事项:${NC}
    1. 首次部署前，请修改 .env 文件中的数据库密码等配置
    2. 建议定期备份数据
    3. 生产环境建议使用腾讯云 CDB 和 Redis，而不是本地容器
    4. 建议配置 SSL 证书，使用 HTTPS

EOF
}

# ============================================================
# 查看服务状态
# ============================================================
show_status() {
    log_info "服务状态:"
    cd "${DEPLOY_DIR}"
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps
}

# ============================================================
# 进入容器 shell
# ============================================================
enter_shell() {
    local service=$1
    
    if [ -z "$service" ]; then
        log_error "请指定服务名称"
        log_info "可用服务: api, web, postgres, redis, ollama, searxng"
        return 1
    fi
    
    cd "${DEPLOY_DIR}"
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec "$service" sh
}

# ============================================================
# 清理容器和镜像
# ============================================================
cleanup() {
    log_warning "清理停止的容器和镜像..."
    
    docker container prune -f
    docker image prune -f
    
    log_success "清理完成"
}

# ============================================================
# 主函数
# ============================================================
main() {
    local cmd=$1
    
    # 检查环境
    check_environment
    
    case "$cmd" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs "$2"
            ;;
        status)
            show_status
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "$2"
            ;;
        ps)
            show_status
            ;;
        shell)
            enter_shell "$2"
            ;;
        clean)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $cmd"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
