#!/bin/bash

# MallPilot 综合电商导购助手 - Docker 部署脚本
# 做什么：统一安装、启动、健康检查、备份和恢复；为什么：让部署与演示验收流程更稳定。
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_NAME="mallpilot"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_info "检查依赖中..."
    command -v docker >/dev/null 2>&1 || { print_error "Docker 未安装"; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { print_error "Docker Compose 未安装"; exit 1; }
    print_info "依赖检查完成"
}

create_directories() {
    print_info "创建必要目录"
    mkdir -p data/chroma
    mkdir -p data/sqlite
    mkdir -p data/eval
    mkdir -p logs
    mkdir -p config/nginx/ssl
    mkdir -p config/grafana/provisioning
    mkdir -p config/grafana/dashboards
    mkdir -p config/alerts
}

check_env_file() {
    if [ -f "$ENV_FILE" ]; then
        print_info "环境变量文件已存在"
        return
    fi
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_warn "已按示例创建 .env，请补充真实配置"
        return
    fi
    print_error "未找到 .env 或 .env.example"
    exit 1
}

build_images() {
    print_info "开始构建镜像"
    docker-compose build --no-cache
}

start_services() {
    print_info "启动服务"
    docker-compose up -d
}

stop_services() {
    print_info "停止服务"
    docker-compose down
}

restart_services() {
    print_info "重启服务"
    docker-compose restart
}

status_services() {
    docker-compose ps
}

view_logs() {
    local service=$1
    if [ -n "$service" ]; then
        docker-compose logs -f "$service"
    else
        docker-compose logs -f
    fi
}

health_check() {
    print_info "执行健康检查"
    sleep 10
    curl -sf http://localhost:8000/health >/dev/null && print_info "主应用健康" || print_error "主应用不健康"
    docker-compose exec -T redis redis-cli ping | grep -q PONG && print_info "Redis 健康" || print_error "Redis 不健康"
    curl -sf http://localhost:8001/api/v1/heartbeat >/dev/null && print_info "ChromaDB 健康" || print_error "ChromaDB 不健康"
    curl -sf http://localhost:9090/-/healthy >/dev/null && print_info "Prometheus 健康" || print_error "Prometheus 不健康"
}

cleanup() {
    print_warn "即将清理服务和卷数据"
    read -p "确认继续？这会删除本地卷数据 (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down -v
        print_info "清理完成"
    else
        print_info "已取消清理"
    fi
}

backup_data() {
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    print_info "开始备份到 $backup_dir"
    mkdir -p "$backup_dir"

    docker-compose exec -T redis redis-cli SAVE
    docker cp mallpilot-redis:/data/dump.rdb "$backup_dir/"
    docker cp mallpilot-chromadb:/chroma/chroma "$backup_dir/"
    cp .env "$backup_dir/"
    cp -r config "$backup_dir/"
    print_info "备份完成: $backup_dir"
}

restore_data() {
    local backup_dir=$1
    if [ -z "$backup_dir" ] || [ ! -d "$backup_dir" ]; then
        print_error "请提供有效备份目录"
        exit 1
    fi

    print_warn "即将从 $backup_dir 恢复数据"
    read -p "确认继续？这会覆盖当前数据 (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "已取消恢复"
        return
    fi

    docker-compose stop
    docker cp "$backup_dir/dump.rdb" mallpilot-redis:/data/
    docker cp "$backup_dir/chroma" mallpilot-chromadb:/chroma/
    cp "$backup_dir/.env" .env
    rm -rf config
    cp -r "$backup_dir/config" config
    docker-compose start
    print_info "恢复完成"
}

show_help() {
    cat << EOF
MallPilot 综合电商导购助手 - Docker 部署脚本

用法: ./docker-deploy.sh [命令]

命令:
    install     初始化安装
    start       启动所有服务
    stop        停止所有服务
    restart     重启所有服务
    status      查看服务状态
    logs        查看服务日志，可追加服务名
    health      执行健康检查
    build       重新构建镜像
    cleanup     清理服务和卷
    backup      备份数据
    restore     恢复数据，需要追加备份目录
    help        显示帮助

示例:
    ./docker-deploy.sh install
    ./docker-deploy.sh start
    ./docker-deploy.sh logs mallpilot
    ./docker-deploy.sh backup
    ./docker-deploy.sh restore backups/20260706_120000
EOF
}

main() {
    case "${1:-help}" in
        install)
            check_dependencies
            check_env_file
            create_directories
            build_images
            print_info "安装完成，运行 './docker-deploy.sh start' 启动服务"
            ;;
        start)
            check_env_file
            start_services
            health_check
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            status_services
            ;;
        logs)
            view_logs "$2"
            ;;
        health)
            health_check
            ;;
        build)
            build_images
            ;;
        cleanup)
            cleanup
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
