#!/bin/bash
# ycycam-udp Docker管理脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NAME="ycycam-udp-server"

case "$1" in
    build)
        echo "🔨 构建Docker镜像..."
        docker build -t ycycam-udp-server:latest .
        echo "✅ 构建完成!"
        ;;

    up)
        echo "🚀 启动容器..."
        docker-compose up -d
        echo "✅ 容器已启动!"
        echo "🌐 Web地址: http://localhost:8000"
        ;;

    down)
        echo "⏹️  停止容器..."
        docker-compose down
        echo "✅ 容器已停止"
        ;;

    restart)
        echo "🔄 重启容器..."
        docker-compose restart
        echo "✅ 重启完成"
        ;;

    logs)
        echo "📋 查看日志..."
        docker-compose logs -f
        ;;

    status)
        echo "📊 容器状态..."
        docker-compose ps
        ;;

    shell)
        echo "🐚 进入容器Shell..."
        docker-compose exec ycycam-server bash
        ;;

    test)
        echo "🧪 测试服务..."
        curl -s http://localhost:8000/status | head -c 200
        echo ""
        ;;

    clean)
        echo "🧹 清理..."
        docker-compose down -v
        docker rmi ycycam-udp-server:latest 2>/dev/null || true
        echo "✅ 清理完成"
        ;;

    *)
        echo "📋 ycycam-udp Docker管理脚本"
        echo ""
        echo "用法: $0 <命令>"
        echo ""
        echo "命令列表:"
        echo "  build    - 构建Docker镜像"
        echo "  up       - 启动容器"
        echo "  down     - 停止容器"
        echo "  restart  - 重启容器"
        echo "  logs     - 查看实时日志"
        echo "  status   - 查看容器状态"
        echo "  shell    - 进入容器Shell"
        echo "  test     - 测试服务接口"
        echo "  clean    - 清理容器和镜像"
        echo ""
        echo "示例:"
        echo "  $0 build && $0 up"
        echo "  $0 logs"
        ;;
esac
