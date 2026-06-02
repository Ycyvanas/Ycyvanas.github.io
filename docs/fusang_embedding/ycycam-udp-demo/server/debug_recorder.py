#!/usr/bin/env python3
"""调试视频录制问题"""
import cv2
import numpy as np
import socket
import struct
from collections import defaultdict

def test_decode_jpeg():
    """测试从UDP接收JPEG并解码"""
    print("=== 测试JPEG解码 ===")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 5000))
    sock.settimeout(5)
    
    frame_buffer = defaultdict(dict)
    frames_received = 0
    
    start_time = cv2.getTickCount()
    while frames_received < 10:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            print("超时，未收到数据")
            break
        
        if len(data) < 12:
            continue
        
        frame_id = struct.unpack('!I', data[:4])[0]
        packet_id = struct.unpack('!H', data[4:6])[0]
        total_packets = struct.unpack('!H', data[6:8])[0]
        frame_size = struct.unpack('!I', data[8:12])[0]
        packet_data = data[12:]
        
        frame_buffer[frame_id][packet_id] = packet_data
        
        if len(frame_buffer[frame_id]) == total_packets:
            sorted_data = []
            for i in range(total_packets):
                if i not in frame_buffer[frame_id]:
                    break
                sorted_data.append(frame_buffer[frame_id][i])
            else:
                full_data = b''.join(sorted_data)
                if len(full_data) == frame_size and full_data[:2] == b'\xff\xd8' and full_data[-2:] == b'\xff\xd9':
                    print(f"\n收到完整帧 {frames_received+1}:")
                    print(f"  JPEG大小: {len(full_data)} 字节")
                    
                    # 解码测试
                    nparr = np.frombuffer(full_data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        print(f"  ✓ 解码成功: {img.shape}")
                        print(f"  数据类型: {img.dtype}")
                        print(f"  像素范围: {img.min()} - {img.max()}")
                        
                        # 保存测试帧
                        if frames_received == 0:
                            cv2.imwrite("debug_frame.jpg", img)
                            print("  ✓ 已保存 debug_frame.jpg 用于检查")
                        
                        frames_received += 1
                    else:
                        print("  ✗ 解码失败!")
            
            del frame_buffer[frame_id]
    
    sock.close()
    print(f"\n共收到 {frames_received} 帧")
    return frames_received > 0

def test_write_video():
    """测试写入视频"""
    print("\n=== 测试视频写入 ===")
    
    # 先读取保存的测试帧
    img = cv2.imread("debug_frame.jpg")
    if img is None:
        print("没有测试帧，创建测试图像")
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "TEST VIDEO", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
    
    print(f"输入图像: {img.shape}")
    
    # 测试多种配置
    configs = [
        ("XVID.avi", cv2.VideoWriter_fourcc(*'XVID'), 15, (640, 480)),
        ("MJPG.avi", cv2.VideoWriter_fourcc(*'MJPG'), 15, (640, 480)),
        ("mp4v.mp4", cv2.VideoWriter_fourcc(*'mp4v'), 15, (640, 480)),
    ]
    
    for filename, fourcc, fps, res in configs:
        print(f"\n测试: {filename}")
        writer = cv2.VideoWriter(filename, fourcc, fps, res)
        
        if writer.isOpened():
            print(f"  ✓ Writer 打开成功")
            
            # 写入 50 帧
            for i in range(50):
                frame = img.copy()
                cv2.putText(frame, f"Frame {i}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                writer.write(frame)
            
            writer.release()
            print(f"  ✓ 已写入 50 帧")
            
            # 验证
            import os
            size = os.path.getsize(filename)
            print(f"  文件大小: {size} 字节")
            
            cap = cv2.VideoCapture(filename)
            if cap.isOpened():
                fps_read = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                duration = frame_count / fps_read if fps_read > 0 else 0
                print(f"  ✓ 可打开: FPS={fps_read:.1f}, 帧数={frame_count}, 时长={duration:.2f}s")
                
                ret, frame_read = cap.read()
                if ret:
                    print(f"  ✓ 可读取帧: {frame_read.shape}")
                else:
                    print(f"  ✗ 无法读取帧")
                cap.release()
            else:
                print(f"  ✗ 无法打开生成的视频")
        else:
            print(f"  ✗ Writer 打开失败")

if __name__ == "__main__":
    if test_decode_jpeg():
        test_write_video()
    print("\n=== 调试完成 ===")
