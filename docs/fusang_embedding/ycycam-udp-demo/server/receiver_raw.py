#!/usr/bin/env python3
"""
ycycam-udp 原始RGB565接收端 (高速模式)
接收ESP32直接发送的RGB565像素，无JPEG编码延迟
"""
import socket
import struct
import time
import threading
from collections import defaultdict

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("WARNING: OpenCV not available - no display")

# UDP配置
UDP_PORT = 5000
HEADER_SIZE = 4  # 2字节frame_id + 1字节packet_id + 1字节total_packets
MAX_PAYLOAD = 1472  # 以太网MTU

# 帧配置
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 2  # RGB565 = 2字节/像素

# 全局统计
stats_lock = threading.Lock()
stats = {
    'frames_received': 0,
    'packets_received': 0,
    'bytes_received': 0,
    'fps': 0,
    'start_time': time.time()
}
last_frames = []

class FrameBuffer:
    """帧缓冲区 - 按frame_id组装包"""
    def __init__(self):
        self.buffers = defaultdict(dict)
        self.frame_info = {}  # {frame_id: total_packets}

    def add_packet(self, frame_id, packet_id, total_packets, data):
        """添加一个数据包，帧完整返回数据"""
        self.frame_info[frame_id] = total_packets
        self.buffers[frame_id][packet_id] = data

        if len(self.buffers[frame_id]) == total_packets:
            # 组装帧
            sorted_data = []
            for i in range(total_packets):
                if i not in self.buffers[frame_id]:
                    # 丢包，丢弃整个帧
                    del self.buffers[frame_id]
                    if frame_id in self.frame_info:
                        del self.frame_info[frame_id]
                    return None
                sorted_data.append(self.buffers[frame_id][i])

            full_data = b''.join(sorted_data)
            del self.buffers[frame_id]
            if frame_id in self.frame_info:
                del self.frame_info[frame_id]

            # 清理旧帧
            for fid in list(self.buffers.keys()):
                if fid < frame_id - 5:
                    del self.buffers[fid]
                    if fid in self.frame_info:
                        del self.frame_info[fid]

            return full_data
        return None


def udp_receiver_thread(buffer, host='0.0.0.0', port=UDP_PORT):
    """UDP接收线程"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.settimeout(0.1)

    print(f"[UDP] Listening on {host}:{port}")
    print(f"[UDP] Expecting QVGA 320x240 RGB565")

    while True:
        try:
            data, addr = sock.recvfrom(MAX_PAYLOAD)
        except socket.timeout:
            continue

        if len(data) < HEADER_SIZE:
            continue

        # 解析头部
        frame_id = (data[0] << 8) | data[1]
        packet_id = data[2]
        total_packets = data[3]
        packet_data = data[HEADER_SIZE:]

        with stats_lock:
            stats['packets_received'] += 1
            stats['bytes_received'] += len(data)

        # 添加到缓冲区
        frame_data = buffer.add_packet(frame_id, packet_id, total_packets, packet_data)

        if frame_data is not None and len(frame_data) == FRAME_SIZE:
            with stats_lock:
                stats['frames_received'] += 1
                last_frames.append((frame_id, frame_data))
                if len(last_frames) > 10:
                    last_frames.pop(0)


def stats_printer():
    """打印统计信息"""
    last_frames_count = 0
    last_bytes = 0
    last_time = time.time()

    while True:
        time.sleep(1.0)
        now = time.time()
        elapsed = now - last_time

        with stats_lock:
            frames = stats['frames_received'] - last_frames_count
            bytes_diff = stats['bytes_received'] - last_bytes
            stats['fps'] = frames / elapsed if elapsed > 0 else 0
            mbps = (bytes_diff * 8) / (1024 * 1024) / elapsed if elapsed > 0 else 0

            print(f"\rFPS: {stats['fps']:5.1f} | "
                  f"Frames: {stats['frames_received']:5d} | "
                  f"Packets: {stats['packets_received']:6d} | "
                  f"BW: {mbps:5.2f} Mbps", end='', flush=True)

            last_frames_count = stats['frames_received']
            last_bytes = stats['bytes_received']
            last_time = now


def display_thread():
    """OpenCV显示线程"""
    if not OPENCV_AVAILABLE:
        return

    print("\n[DISPLAY] Press ESC to exit\n")
    last_display_time = 0

    while True:
        if not last_frames:
            time.sleep(0.001)
            continue

        frame_id, frame_data = last_frames[-1]

        # RGB565转BGR
        try:
            # 将字节数据转换为uint16数组
            arr = np.frombuffer(frame_data, dtype=np.uint16).reshape(FRAME_HEIGHT, FRAME_WIDTH)

            # RGB565转RGB888
            r = ((arr >> 11) & 0x1F) * 255 // 31
            g = ((arr >> 5) & 0x3F) * 255 // 63
            b = (arr & 0x1F) * 255 // 31

            rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            # 缩放显示
            display = cv2.resize(bgr, (FRAME_WIDTH * 2, FRAME_HEIGHT * 2))

            # 叠加FPS信息
            with stats_lock:
                fps_text = f"FPS: {stats['fps']:.1f}"
            cv2.putText(display, fps_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display, "QVGA 320x240 RGB565", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            cv2.imshow("ycycam-udp Raw Mode", display)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
        except Exception as e:
            print(f"Display error: {e}")
            time.sleep(0.1)

    cv2.destroyAllWindows()


def main():
    print("=" * 60)
    print("  ycycam-udp - RAW RGB565 HIGH SPEED MODE")
    print("  Target: 40+ FPS @ QVGA 320x240")
    print("=" * 60)

    buffer = FrameBuffer()

    # 启动UDP接收线程
    udp_thread = threading.Thread(target=udp_receiver_thread, args=(buffer,), daemon=True)
    udp_thread.start()

    # 启动统计打印线程
    stats_thread = threading.Thread(target=stats_printer, daemon=True)
    stats_thread.start()

    # 主线程显示
    try:
        display_thread()
    except KeyboardInterrupt:
        pass

    print("\n\n" + "=" * 60)
    print("  Session Summary")
    print("=" * 60)
    elapsed = time.time() - stats['start_time']
    print(f"Uptime: {elapsed:.1f} seconds")
    print(f"Frames: {stats['frames_received']}")
    print(f"Packets: {stats['packets_received']}")
    print(f"Total data: {stats['bytes_received'] / 1024 / 1024:.1f} MB")
    print(f"Avg FPS: {stats['frames_received'] / elapsed:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
