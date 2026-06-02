#!/usr/bin/env python3
"""ycycam-udp 灰度模式接收端"""
import socket
import struct
import time
import signal
import sys

UDP_PORT = 5000
HEADER_SIZE = 12  # 4+2+2+4

frames = 0
packets = 0
bytes_recv = 0
start_time = time.time()

def signal_handler(sig, frame):
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  运行时间: {elapsed:.1f} 秒")
    print(f"  接收帧数: {frames}")
    print(f"  接收包数: {packets}")
    print(f"  数据总量: {bytes_recv/1024/1024:.1f} MB")
    print(f"  平均帧率: {frames/elapsed:.1f} FPS")
    print(f"  平均带宽: {bytes_recv*8/1024/1024/elapsed:.2f} Mbps")
    print(f"{'='*60}")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', UDP_PORT))
sock.settimeout(0.5)

print(f"监听 UDP 端口 {UDP_PORT}... (按 Ctrl+C 退出)")
print(f"{'FPS':>6} {'Frames':>8} {'Packets':>8} {'Mbps':>8}")
print("-" * 35)

last_print = time.time()
last_frame_id = -1

while True:
    try:
        data, addr = sock.recvfrom(1500)
    except socket.timeout:
        continue

    packets += 1
    bytes_recv += len(data)

    # 解析头部
    if len(data) >= HEADER_SIZE:
        frame_id, packet_id, total_packets, frame_size = struct.unpack('!IHHI', data[:HEADER_SIZE])

        # 检测新帧
        if packet_id == 0 and frame_id != last_frame_id:
            frames += 1
            last_frame_id = frame_id

    # 每秒打印一次
    now = time.time()
    if now - last_print >= 1.0:
        elapsed = now - start_time
        fps = frames / elapsed if elapsed > 0 else 0
        mbps = (bytes_recv * 8 / 1024 / 1024) / elapsed if elapsed > 0 else 0

        print(f"\r{fps:6.1f} {frames:8d} {packets:8d} {mbps:8.2f}", end='', flush=True)
        last_print = now
