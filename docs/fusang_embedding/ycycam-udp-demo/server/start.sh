#!/bin/bash
# ycycam-udp 接收端服务器启动脚本
cd "$(dirname "$0")"

# 激活conda环境
source /home/dx1991/anaconda3/etc/profile.d/conda.sh
conda activate ycyserver

# 启动web服务器
python web_receiver.py
