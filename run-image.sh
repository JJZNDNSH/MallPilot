#!/bin/bash

# MallPilot 镜像运行脚本
# 做什么：统一本地容器运行、查看日志和进入容器；为什么：降低开发和验收成本。
set -e

IMAGE_NAME="mallpilot"
CONTAINER_NAME="mallpilot-app"
VERSION=${VERSION:-latest}
REGISTRY=""
API_PORT=8000
PROMETHEUS_PORT=9090
DATA_DIR="./data"
LOGS_DIR="./logs"
CONFIG_DIR="./config"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
MallPilot Docker 镜像运行工具

用法: ./run-image.sh [命令] [选项]

命令:
    run             运行容器
    run-dev         运行开发模式容器
    run-test        运行测试容器
    run-prod        运行生产模式容器
    stop            停止容器
    restart         重启容器
    logs            查看日志
    shell           进入容器 shell
    status          查看容器状态
    clean           清理容器
    help            显示帮助

选项:
    --detach        后台运行
    --env-file      指定环境变量文件
    --ports         追加端口映射
    --volume        追加卷映射
    --name          自定义容器名
    --restart       自定义重启策略
EOF
}

ensure_directories() {
    mkdir -p "$DATA_DIR" "$LOGS_DIR" "$CONFIG_DIR"
}

run_container() {
    local mode=$1
    shift || true

    local detach=false
    local env_file=".env"
    local custom_ports=""
    local custom_volumes=""
    local container_name="$CONTAINER_NAME"
    local restart_policy="no"

    while [[ $# -gt 0 ]]; do
        case $1 in
            --detach|-d)
                detach=true
                shift
                ;;
            --env-file)
                env_file="$2"
                shift 2
                ;;
            --ports|-p)
                custom_ports="$custom_ports -p $2"
                shift 2
                ;;
            --volume|-v)
                custom_volumes="$custom_volumes -v $2"
                shift 2
                ;;
            --name)
                container_name="$2"
                shift 2
                ;;
            --restart)
                restart_policy="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    ensure_directories

    if [ -f "$env_file" ]; then
        env_file="--env-file $env_file"
    else
        print_warn "环境文件不存在，改用默认环境"
        env_file=""
    fi

    local image_tag="${REGISTRY}${IMAGE_NAME}:${VERSION}"
    local default_ports="-p ${API_PORT}:8000 -p ${PROMETHEUS_PORT}:9090"
    local default_volumes="-v ${DATA_DIR}:/app/data -v ${LOGS_DIR}:/app/logs -v ${CONFIG_DIR}:/app/config"

    case $mode in
        dev)
            print_info "运行开发模式容器"
            default_ports="$default_ports -p 5678:5678"
            ;;
        test)
            print_info "运行测试容器"
            ;;
        prod)
            print_info "运行生产模式容器"
            restart_policy="unless-stopped"
            ;;
        *)
            print_info "运行标准容器"
            ;;
    esac

    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        print_warn "检测到同名容器，先移除旧容器"
        docker stop "$container_name" >/dev/null 2>&1 || true
        docker rm "$container_name" >/dev/null 2>&1 || true
    fi

    local command="docker run --name $container_name --restart $restart_policy"
    if [ "$detach" = true ]; then
        command="$command -d"
    fi
    command="$command $default_ports $custom_ports $default_volumes $custom_volumes $env_file $image_tag"
    eval "$command"

    print_info "容器已启动: $container_name"
    print_info "API 地址: http://localhost:${API_PORT}"
    print_info "Prometheus 地址: http://localhost:${PROMETHEUS_PORT}"
}

stop_container() {
    local name=${1:-$CONTAINER_NAME}
    docker stop "$name"
    print_info "容器已停止: $name"
}

restart_container() {
    local name=${1:-$CONTAINER_NAME}
    docker restart "$name"
    print_info "容器已重启: $name"
}

view_logs() {
    local name=${1:-$CONTAINER_NAME}
    local follow=${2:-true}
    if [ "$follow" = "true" ]; then
        docker logs -f "$name"
    else
        docker logs "$name"
    fi
}

enter_shell() {
    local name=${1:-$CONTAINER_NAME}
    docker exec -it "$name" /bin/bash
}

show_status() {
    local name=${1:-$CONTAINER_NAME}
    docker ps -a --filter "name=$name" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

clean_container() {
    local name=${1:-$CONTAINER_NAME}
    docker stop "$name" >/dev/null 2>&1 || true
    docker rm "$name" >/dev/null 2>&1 || true
    print_info "容器已清理: $name"
}

main() {
    local command=${1:-run}
    shift || true

    case $command in
        run)
            run_container "" "$@"
            ;;
        run-dev)
            run_container "dev" "$@"
            ;;
        run-test)
            run_container "test" "$@"
            ;;
        run-prod)
            run_container "prod" "$@"
            ;;
        stop)
            stop_container "$1"
            ;;
        restart)
            restart_container "$1"
            ;;
        logs)
            if [ "$1" = "--no-follow" ]; then
                view_logs "$2" "false"
            else
                view_logs "$1" "true"
            fi
            ;;
        shell)
            enter_shell "$1"
            ;;
        status)
            show_status "$1"
            ;;
        clean)
            clean_container "$1"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
