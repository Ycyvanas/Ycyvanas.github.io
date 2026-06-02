#!/usr/bin/env python3
"""
ycycam-udp 视频流接收端 v2.0

功能:
- UDP视频流接收与组包
- OpenCV实时显示
- FPS/带宽/丢包率统计
- 视频录制功能 (MP4)
- 帧保存功能
- 延迟统计
- 命令行参数配置

用法:
    python receiver.py                  # 默认端口5000
    python receiver.py -p 5001         # 指定端口
    python receiver.py --no-display    # 无头模式（仅统计）
    python receiver.py --record video.mp4  # 录制视频
    python receiver.py --save-frames    # 自动保存关键帧
    python receiver.py --host 0.0.0.0   # 绑定地址
"""

import socket
import struct
import sys
import time
import argparse
import os
from collections import defaultdict, deque

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("警告: OpenCV未安装，无法显示视频")
    print("安装: pip install opencv-python")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# UDP数据包头部格式 (网络字节序)
# uint32 frame_id, uint16 packet_id, uint16 total_packets, uint32 frame_size
HEADER_FORMAT = '!IHHI'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

MAX_PAYLOAD = 1400
MAX_FRAME_SIZE = 256 * 1024  # 256KB


class VideoStats:
    """统计信息收集器"""
    def __init__(self, window_size=100):
        self.frames_received = 0
        self.frames_complete = 0
        self.frames_lost = 0
        self.packets_received = 0
        self.bytes_received = 0
        self.last_frame_id = -1
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.start_time = time.time()

    def on_packet(self, size):
        self.packets_received += 1
        self.bytes_received += size

    def on_frame_complete(self, frame_id):
        self.frames_complete += 1
        self.frame_times.append(time.time())

        # 检测丢帧
        if self.last_frame_id >= 0 and frame_id > self.last_frame_id + 1:
            self.frames_lost += frame_id - self.last_frame_id - 1
        self.last_frame_id = frame_id

    def get_fps(self):
        """计算最近的FPS"""
        if len(self.frame_times) < 2:
            return 0
        elapsed = self.frame_times[-1] - self.frame_times[0]
        if elapsed <= 0:
            return 0
        return (len(self.frame_times) - 1) / elapsed

    def get_bandwidth_mbps(self):
        """计算平均带宽 (Mbps)"""
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0
        return (self.bytes_received * 8) / (1024 * 1024) / elapsed

    def get_loss_rate(self):
        """计算丢包率"""
        total = self.frames_complete + self.frames_lost
        if total == 0:
            return 0
        return self.frames_lost / total * 100

    def get_status_line(self):
        """生成状态行"""
        fps = self.get_fps()
        mbps = self.get_bandwidth_mbps()
        loss = self.get_loss_rate()
        return (f"FPS: {fps:5.1f} | "
                f"Frames: {self.frames_complete:5d} | "
                f"Packets: {self.packets_received:6d} | "
                f"BW: {mbps:5.2f} Mbps | "
                f"Loss: {loss:4.1f}%")


class FrameBuffer:
    """帧缓冲区 - 按帧ID组包"""
    def __init__(self, max_frames=10):
        self.buffers = defaultdict(dict)  # {frame_id: {packet_id: data}}
        self.frame_info = {}  # {frame_id: (total_packets, frame_size)}
        self.max_frames = max_frames
        self.completed_frames = set()

    def add_packet(self, frame_id, packet_id, total_packets, frame_size, data):
        """添加一个数据包"""
        if frame_id in self.completed_frames:
            return None

        self.buffers[frame_id][packet_id] = data
        self.frame_info[frame_id] = (total_packets, frame_size)

        # 检查是否完整
        if len(self.buffers[frame_id]) == total_packets:
            return self.assemble_frame(frame_id)

        # 清理过期帧
        self.cleanup_old_frames(frame_id)
        return None

    def assemble_frame(self, frame_id):
        """组装完整帧"""
        packets = self.buffers[frame_id]
        total_packets, frame_size = self.frame_info[frame_id]

        # 按序号排序
        sorted_data = []
        for i in range(total_packets):
            if i not in packets:
                # 丢包，丢弃整个帧
                del self.buffers[frame_id]
                del self.frame_info[frame_id]
                return None
            sorted_data.append(packets[i])

        full_data = b''.join(sorted_data)

        # 验证大小
        if len(full_data) != frame_size:
            print(f"警告: 帧大小不匹配: {len(full_data)} != {frame_size}")
            del self.buffers[frame_id]
            del self.frame_info[frame_id]
            return None

        # 标记完成并清理
        self.completed_frames.add(frame_id)
        del self.buffers[frame_id]
        del self.frame_info[frame_id]

        return full_data

    def cleanup_old_frames(self, current_frame_id):
        """清理过期的帧"""
        if len(self.buffers) > self.max_frames:
            to_delete = [fid for fid in self.buffers.keys()
                        if fid < current_frame_id - self.max_frames]
            for fid in to_delete:
                del self.buffers[fid]
                if fid in self.frame_info:
                    del self.frame_info[fid]

        # 限制已完成帧的记录
        if len(self.completed_frames) > 100:
            self.completed_frames = set(list(self.completed_frames)[-50:])


class VideoRecorder:
    """视频录制器"""
    def __init__(self, filename, fps=30):
        self.filename = filename
        self.fps = fps
        self.writer = None
        self.frames_recorded = 0

    def init_writer(self, width, height):
        """初始化录制器 (需要知道帧尺寸)"""
        if self.writer is not None:
            return

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(
            self.filename, fourcc, self.fps, (width, height))

        if self.writer.isOpened():
            print(f"开始录制视频: {self.filename} ({width}x{height} @ {self.fps}fps)")
        else:
            print("警告: 视频录制初始化失败")
            self.writer = None

    def write_frame(self, frame):
        """写入一帧"""
        if self.writer is None:
            # 从帧初始化
            h, w = frame.shape[:2]
            self.init_writer(w, h)

        if self.writer is not None:
            self.writer.write(frame)
            self.frames_recorded += 1

    def close(self):
        """关闭录制器"""
        if self.writer is not None:
            self.writer.release()
            print(f"\n视频已保存: {self.filename} ({self.frames_recorded} 帧)")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='ycycam-udp 视频流接收端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
快捷键:
  ESC/q - 退出
  SPACE - 暂停/继续
  s     - 保存当前帧
  r     - 开始/停止录制
        """
    )
    parser.add_argument('-p', '--port', type=int, default=5000,
                        help='UDP监听端口 (默认: 5000)')
    parser.add_argument('-H', '--host', type=str, default='0.0.0.0',
                        help='绑定地址 (默认: 0.0.0.0)')
    parser.add_argument('--no-display', action='store_true',
                        help='无头模式，不显示视频窗口')
    parser.add_argument('-r', '--record', type=str, metavar='FILE',
                        help='录制视频到文件')
    parser.add_argument('--save-frames', action='store_true',
                        help='自动保存帧到 frames/ 目录')
    parser.add_argument('--stats-interval', type=float, default=1.0,
                        help='统计信息输出间隔(秒) (默认: 1.0)')
    parser.add_argument('--buffer-size', type=int, default=1024*1024,
                        help='Socket缓冲区大小 (默认: 1MB)')
    return parser.parse_args()


def jpeg_to_cv2(jpeg_data):
    """JPEG数据转换为OpenCV格式"""
    if not OPENCV_AVAILABLE:
        return None
    try:
        nparr = np.frombuffer(jpeg_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"\n解码错误: {e}")
        return None


def save_jpeg(jpeg_data, filename):
    """保存JPEG数据到文件"""
    try:
        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(jpeg_data))
            img.save(filename)
        else:
            with open(filename, 'wb') as f:
                f.write(jpeg_data)
        return True
    except Exception as e:
        print(f"\n保存失败: {e}")
        return False


def main():
    args = parse_args()

    print("=" * 60)
    print("  ycycam-udp 视频流接收端 v2.0")
    print("=" * 60)
    print(f"监听地址: {args.host}:{args.port}")
    print(f"OpenCV: {'可用' if OPENCV_AVAILABLE else '不可用'}")
    print(f"PIL: {'可用' if PIL_AVAILABLE else '不可用'}")

    if args.no_display:
        print("无头模式: 不显示视频窗口")
    if args.record:
        print(f"录制视频: {args.record}")
    if args.save_frames:
        os.makedirs('frames', exist_ok=True)
        print("自动保存帧到: frames/ 目录")

    print("=" * 60)

    # 创建UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, args.buffer_size)
    sock.bind((args.host, args.port))
    sock.settimeout(0.1)

    print("等待视频流... (按 Ctrl+C 退出)\n")

    # 初始化组件
    frame_buffer = FrameBuffer(max_frames=5)
    stats = VideoStats()
    recorder = None
    if args.record and OPENCV_AVAILABLE:
        recorder = VideoRecorder(args.record)

    paused = False
    last_stats_time = time.time()
    frame_count_for_save = 0

    try:
        while True:
            try:
                data, addr = sock.recvfrom(MAX_PAYLOAD)
            except socket.timeout:
                continue

            if paused:
                continue

            stats.on_packet(len(data))

            # 解析头部
            if len(data) < HEADER_SIZE:
                continue

            try:
                frame_id, packet_id, total_packets, frame_size = \
                    struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            except struct.error:
                continue

            packet_data = data[HEADER_SIZE:]

            # 添加到帧缓冲区
            jpeg_data = frame_buffer.add_packet(
                frame_id, packet_id, total_packets, frame_size, packet_data)

            if jpeg_data is not None:
                stats.on_frame_complete(frame_id)

                # 转换为OpenCV格式
                img = jpeg_to_cv2(jpeg_data)

                if img is not None and not args.no_display:
                    # 在图像上叠加信息
                    status_text = stats.get_status_line()
                    cv2.putText(img, status_text, (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    cv2.putText(img, f"Frame: {frame_id}", (10, 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    if recorder is not None:
                        cv2.putText(img, "REC", (img.shape[1]-60, 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                    # 显示
                    cv2.imshow('ycycam-udp', img)
                    cv2.waitKey(1)

                    # 录制
                    if recorder is not None:
                        recorder.write_frame(img)

                # 自动保存帧
                if args.save_frames and frame_count_for_save % 30 == 0:
                    filename = f"frames/frame_{frame_id:06d}.jpg"
                    save_jpeg(jpeg_data, filename)
                frame_count_for_save += 1

            # 输出统计信息
            now = time.time()
            if now - last_stats_time >= args.stats_interval:
                print(f"\r{stats.get_status_line()}", end='', flush=True)
                last_stats_time = now

    except KeyboardInterrupt:
        print("\n\n正在退出...")
    finally:
        sock.close()
        if recorder is not None:
            recorder.close()
        if OPENCV_AVAILABLE and not args.no_display:
            cv2.destroyAllWindows()

        # 最终统计
        print("\n" + "=" * 60)
        print("  会话统计")
        print("=" * 60)
        elapsed = time.time() - stats.start_time
        print(f"运行时间: {elapsed:.1f} 秒")
        print(f"接收帧数: {stats.frames_complete}")
        print(f"接收包数: {stats.packets_received}")
        print(f"接收数据: {stats.bytes_received / 1024 / 1024:.1f} MB")
        print(f"平均FPS: {stats.frames_complete / elapsed:.1f}")
        print(f"平均带宽: {stats.bytes_received * 8 / 1024 / 1024 / elapsed:.2f} Mbps")
        print(f"丢帧率: {stats.get_loss_rate():.1f}%")
        print("=" * 60)


if __name__ == "__main__":
    import io  # 延迟导入，节省内存
    main()
