#!/bin/bash
# ycycam-udp 编译脚本

set -e

cd "$(dirname "$0")"

echo "========================================"
echo "  ycycam-udp - 编译开始"
echo "========================================"

# 激活ESP-IDF环境
if [ -d "$HOME/esp/esp-idf" ]; then
    . "$HOME/esp/esp-idf/export.sh"
elif [ -d "$HOME/esp-idf" ]; then
    . "$HOME/esp-idf/export.sh"
else
    echo "错误: 找不到ESP-IDF环境"
    exit 1
fi

echo "ESP-IDF环境已激活"

# 编译
echo "开始编译..."
idf.py build

echo ""
echo "========================================"
echo "  编译成功!"
echo "========================================"
echo ""
echo "烧录命令: idf.py -p /dev/ttyUSB0 flash"
echo "监控命令: idf.py -p /dev/ttyUSB0 monitor"
echo ""
echo "接收端: python3 receiver.py"
