#!/bin/bash
#
# ycycam-udp 快速开始脚本
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}>>> $1${NC}"
}

print_info() {
    echo -e "${YELLOW}--- $1${NC}"
}

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     ycycam-udp - 快速开始向导                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# 检查Python依赖
print_step "检查Python依赖..."
python3 -c "import cv2; import numpy; import PIL" 2>/dev/null && \
    echo "✓ Python依赖已安装" || \
    echo "✗ 需要安装Python依赖: pip install opencv-python pillow numpy"

echo ""

# 选择操作
echo "请选择操作:"
echo "  1) 编译ESP32固件"
echo "  2) 烧录ESP32固件 + 串口监控"
echo "  3) 启动测试模式 (测试发送器 + 接收器)"
echo "  4) 仅启动Python接收器"
echo "  5) 安装Python依赖"
echo "  6) 编译C++高性能接收器"
echo ""
read -p "请输入选项 [1-6]: " choice

case $choice in
    1)
        print_step "编译ESP32固件..."
        if [ ! -f "build/build.ninja" ]; then
            echo "首次编译，运行CMake配置..."
            . ~/esp-idf/export.sh
            idf.py build
        else
            cd build && ninja -j$(nproc)
        fi
        echo ""
        echo "✓ 编译完成! 固件位置: build/ycycam-udp.bin"
        ;;

    2)
        print_step "烧录ESP32固件..."
        . ~/esp-idf/export.sh
        idf.py flash monitor
        ;;

    3)
        print_step "启动测试模式..."
        echo ""
        echo "请在两个终端分别运行:"
        echo ""
        echo "终端1 (接收器):"
        echo "  python3 receiver.py"
        echo ""
        echo "终端2 (测试发送器):"
        echo "  python3 test_sender.py"
        echo ""
        echo "按任意键打开两个终端..."
        read -n 1

        # 尝试打开两个终端
        if command -v gnome-terminal &> /dev/null; then
            gnome-terminal -- bash -c "python3 receiver.py; exec bash" &
            sleep 1
            gnome-terminal -- bash -c "python3 test_sender.py; exec bash" &
        elif command -v xterm &> /dev/null; then
            xterm -e "python3 receiver.py" &
            sleep 1
            xterm -e "python3 test_sender.py" &
        else
            echo "请手动在两个终端运行上述命令"
        fi
        ;;

    4)
        print_step "启动Python接收器..."
        python3 receiver.py
        ;;

    5)
        print_step "安装Python依赖..."
        pip3 install opencv-python pillow numpy
        echo "✓ 安装完成"
        ;;

    6)
        print_step "编译C++高性能接收器..."
        make cpp
        echo ""
        echo "✓ 编译完成! 使用方法: ./receiver -p 5000"
        ;;

    *)
        echo "无效选项"
        exit 1
        ;;
esac

echo ""
echo "✓ 完成!"
