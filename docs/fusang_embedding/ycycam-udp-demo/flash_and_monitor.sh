#!/bin/bash
# ycycam-udp 烧录并监控脚本

set -e

cd "$(dirname "$0")"

echo "========================================"
echo "  ycycam-udp - 烧录开始"
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

# 检查串口设备
SERIAL_PORT=""
if [ -c "/dev/ttyUSB0" ]; then
    SERIAL_PORT="/dev/ttyUSB0"
elif [ -c "/dev/ttyACM0" ]; then
    SERIAL_PORT="/dev/ttyACM0"
else
    echo "警告: 未找到串口设备，请手动指定端口"
    echo "用法: $0 [串口端口]"
    exit 1
fi

echo "使用串口: $SERIAL_PORT"

# 设置串口权限
sudo chmod 666 $SERIAL_PORT 2>/dev/null || true

# 烧录固件
echo "开始烧录..."
idf.py -p $SERIAL_PORT flash

echo ""
echo "========================================"
echo "  烧录成功!"
echo "========================================"
echo ""
echo "启动串口监控..."
echo "按 Ctrl+] 退出监控"
echo ""

idf.py -p $SERIAL_PORT monitor
