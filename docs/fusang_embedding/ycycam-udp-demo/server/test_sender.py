#!/usr/bin/env python3
"""
UDP测试发送器 - 用于测试接收端

用于在没有ESP32硬件时测试接收端功能
发送模拟JPEG帧数据
"""

import socket
import struct
import time
import argparse
import os
import random

try:
    from PIL import Image
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# UDP配置
DEFAULT_PORT = 5000
HEADER_FORMAT = '!IHHI'  # frame_id, packet_id, total_packets, frame_size
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD = 1400
PACKET_DATA_SIZE = MAX_PAYLOAD - HEADER_SIZE


def generate_test_frame(frame_id, width=640, height=480):
    """生成测试JPEG帧 - 动态变化的图像"""
    if not PIL_AVAILABLE:
        # 如果没有PIL，返回一个固定的小JPEG
        return (b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01'
                b'\x00\x00\xff\xdb\x00\x43\x00\x03\x02\x02\x03\x02\x02\x03\x03'
                b'\x03\x03\x04\x03\x03\x04\x05\x08\x05\x05\x04\x04\x05\n\x07'
                b'\x07\x06\x08\x0c\n\x0c\x0c\x0b\n\x0b\x0b\r\x0e\x12\x10\r\x0e'
                b'\x11\x0e\x0b\x0b\x10\x16\x10\x11\x13\x14\x15\x15\x15\x0c\x0f'
                b'\x17\x18\x16\x14\x18\x12\x14\x15\x14\xff\xc0\x00\x11\x08\x00'
                b'\x10\x00\x10\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4'
                b'\x00\x15\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                b'\x00\x00\x00\x00\x08\xff\xc4\x00\x15\x10\x01\x00\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00'
                b'\x0c\x03\x01\x00\x02\x10\x03\x10\x00\x05\x0c\x08\x085\x80\x01'
                b'\xff\xd9')

    # 生成动态变化的测试图像
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    # 随frame_id变化的颜色
    r = (frame_id * 7) % 256
    g = (frame_id * 13) % 256
    b = (frame_id * 23) % 256

    # 生成渐变+条纹图案
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (
                (r + x // 4) % 256,
                (g + y // 4) % 256,
                (b + (x + y) // 8) % 256
            )

    # 添加帧号文本
    try:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        text = f"Frame {frame_id}"
        draw.text((10, 10), text, fill=(255, 255, 255))
    except:
        pass

    # 保存为JPEG
    import io
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=60)
    return buf.getvalue()


def send_frame(sock, host, port, jpeg_data, frame_id):
    """发送一帧（自动分包）"""
    frame_size = len(jpeg_data)
    total_packets = (frame_size + PACKET_DATA_SIZE - 1) // PACKET_DATA_SIZE

    bytes_sent = 0
    for packet_id in range(total_packets):
        chunk_size = min(PACKET_DATA_SIZE, frame_size - bytes_sent)
        chunk = jpeg_data[bytes_sent:bytes_sent + chunk_size]

        # 构建数据包
        header = struct.pack(HEADER_FORMAT, frame_id, packet_id, total_packets, frame_size)
        packet = header + chunk

        sock.sendto(packet, (host, port))
        bytes_sent += chunk_size

    return total_packets


def main():
    parser = argparse.ArgumentParser(description='ycycam-udp 测试发送器')
    parser.add_argument('-H', '--host', default='127.0.0.1',
                        help='目标主机 (默认: 127.0.0.1)')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help=f'目标端口 (默认: {DEFAULT_PORT})')
    parser.add_argument('-f', '--fps', type=int, default=30,
                        help='帧率 (默认: 30)')
    parser.add_argument('-n', '--frames', type=int, default=0,
                        help='发送帧数 (0=无限)')
    parser.add_argument('--width', type=int, default=640,
                        help='帧宽度 (默认: 640)')
    parser.add_argument('--height', type=int, default=480,
                        help='帧高度 (默认: 480)')
    parser.add_argument('--loss', type=float, default=0.0,
                        help='模拟丢包率 0-1 (默认: 0)')
    parser.add_argument('--burst', action='store_true',
                        help='突发模式 (不延迟)')
    args = parser.parse_args()

    print("=" * 60)
    print("  ycycam-udp 测试发送器")
    print("=" * 60)
    print(f"目标: {args.host}:{args.port}")
    print(f"分辨率: {args.width}x{args.height}")
    print(f"目标FPS: {args.fps}")
    print(f"模拟丢包率: {args.loss*100:.1f}%")
    if args.frames > 0:
        print(f"发送帧数: {args.frames}")
    else:
        print("发送帧数: 无限 (按 Ctrl+C 停止)")
    print("=" * 60)

    # 创建UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print("\n开始发送... (按 Ctrl+C 停止)\n")

    frame_id = 0
    total_bytes = 0
    start_time = time.time()
    last_report = start_time

    try:
        while True:
            if args.frames > 0 and frame_id >= args.frames:
                break

            # 生成测试帧
            jpeg_data = generate_test_frame(frame_id, args.width, args.height)
            jpeg_size = len(jpeg_data)

            # 模拟随机丢包
            if args.loss > 0 and random.random() < args.loss:
                # 丢弃一整帧
                frame_id += 1
                continue

            # 发送帧
            packets = send_frame(sock, args.host, args.port, jpeg_data, frame_id)
            total_bytes += jpeg_size

            frame_id += 1

            # 每秒报告一次
            now = time.time()
            if now - last_report >= 1.0:
                elapsed = now - start_time
                fps = frame_id / elapsed
                mbps = (total_bytes * 8) / (1024 * 1024) / elapsed

                print(f"\r帧 {frame_id:5d} | "
                      f"FPS: {fps:5.1f} | "
                      f"帧大小: {jpeg_size:5d} bytes | "
                      f"带宽: {mbps:5.2f} Mbps", end='', flush=True)
                last_report = now

            # 控制帧率
            if not args.burst:
                target_time = start_time + frame_id / args.fps
                sleep_time = target_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\n正在停止...")
    finally:
        sock.close()

    # 最终统计
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("  发送统计")
    print("=" * 60)
    print(f"运行时间: {elapsed:.1f} 秒")
    print(f"发送帧数: {frame_id}")
    print(f"总数据量: {total_bytes / 1024 / 1024:.1f} MB")
    print(f"平均FPS: {frame_id / elapsed:.1f}")
    print(f"平均带宽: {total_bytes * 8 / 1024 / 1024 / elapsed:.2f} Mbps")
    print("=" * 60)


if __name__ == "__main__":
    main()
