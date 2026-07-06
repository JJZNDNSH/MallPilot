#!/bin/bash

# MallPilot 镜像构建脚本
# 做什么：统一构建开发、测试、生产镜像；为什么：让本地和部署环境使用同一套入口。
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

IMAGE_NAME="mallpilot"
REGISTRY=""
VERSION=${VERSION:-latest}
BUILD_ARGS=""
NO_CACHE=false
PLATFORMS=""

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

show_help() {
    cat << EOF
MallPilot Docker 镜像构建工具

用法: ./build-image.sh [命令] [选项]

命令:
    build           构建默认镜像
    build-prod      构建生产镜像
    build-dev       构建开发镜像
    build-test      构建测试镜像
    push            推送镜像到仓库
    tag             为镜像添加标签
    clean           清理构建缓存
    help            显示帮助

选项:
    --no-cache      禁用缓存构建
    --platform      指定平台，例如 linux/amd64
    --registry      指定镜像仓库前缀
    --version       指定镜像版本

示例:
    ./build-image.sh build-prod
    ./build-image.sh build --no-cache
    ./build-image.sh build --platform linux/amd64,linux/arm64
    ./build-image.sh push --registry my-registry.com
    ./build-image.sh tag --version v2.0.0
EOF
}

build_image() {
    local target=$1
    print_step "开始构建镜像 ${IMAGE_NAME}:${VERSION}"

    local command="docker build"
    if [ -n "$target" ]; then
        command="$command --target $target"
    fi
    if [ "$NO_CACHE" = true ]; then
        command="$command --no-cache"
        print_warn "本次构建已禁用缓存"
    fi
    if [ -n "$PLATFORMS" ]; then
        command="$command --platform $PLATFORMS"
        print_info "构建平台: $PLATFORMS"
    fi
    if [ -n "$BUILD_ARGS" ]; then
        command="$command $BUILD_ARGS"
    fi

    local full_tag="${REGISTRY}${IMAGE_NAME}:${VERSION}"
    command="$command -t $full_tag -t ${REGISTRY}${IMAGE_NAME}:latest ."
    print_info "执行命令: $command"
    eval "$command"
    print_info "镜像构建完成: $full_tag"
}

push_image() {
    local registry=$1
    if [ -n "$registry" ]; then
        REGISTRY="$registry/"
    fi
    print_step "开始推送镜像"
    docker push "${REGISTRY}${IMAGE_NAME}:${VERSION}"
    docker push "${REGISTRY}${IMAGE_NAME}:latest"
    print_info "镜像推送完成"
}

tag_image() {
    local new_version=$1
    if [ -z "$new_version" ]; then
        print_error "请通过 --version 指定新标签"
        exit 1
    fi
    print_step "添加镜像标签: $new_version"
    docker tag "${REGISTRY}${IMAGE_NAME}:${VERSION}" "${REGISTRY}${IMAGE_NAME}:${new_version}"
    print_info "标签添加完成"
}

clean_build_cache() {
    print_step "清理 Docker 构建缓存"
    docker builder prune -f
    print_info "缓存清理完成"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-cache)
                NO_CACHE=true
                shift
                ;;
            --platform)
                PLATFORMS="$2"
                shift 2
                ;;
            --registry)
                REGISTRY="$2/"
                shift 2
                ;;
            --version)
                VERSION="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
}

main() {
    local command=${1:-help}
    shift || true
    parse_args "$@"

    case $command in
        build)
            build_image ""
            ;;
        build-prod)
            build_image "production"
            ;;
        build-dev)
            build_image "development"
            ;;
        build-test)
            build_image "test"
            ;;
        push)
            push_image "${REGISTRY%/}"
            ;;
        tag)
            tag_image "$VERSION"
            ;;
        clean)
            clean_build_cache
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
