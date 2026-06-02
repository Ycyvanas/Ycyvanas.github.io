#!/usr/bin/env python3
"""
调试用UDP接收端 - 打印所有接收到的UDP包
"""
import socket
import struct
import time

UDP_PORT = 5000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', UDP_PORT))
sock.settimeout(1.0)

print(f"监听UDP端口 {UDP_PORT}...")
print("等待ESP32发送数据...\n")

packet_count = 0
start_time = time.time()

while True:
    try:
        data, addr = sock.recvfrom(2048)
        packet_count += 1
        
        if len(data) >= 12:
            frame_id = struct.unpack('!I', data[:4])[0]
            packet_id = struct.unpack('!H', data[4:6])[0]
            total_packets = struct.unpack('!H', data[6:8])[0]
            frame_size = struct.unpack('!I', data[8:12])[0]
            
            elapsed = time.time() - start_time
            pps = packet_count / elapsed
            
            print(f"[{packet_count:5d}] 来自 {addr[0]}: 帧ID={frame_id}, 包ID={packet_id}/{total_packets}, 帧大小={frame_size}字节, 速率={pps:.1f}包/秒")
        else:
            print(f"收到无效数据包，长度={len(data)}字节")
            
    except socket.timeout:
        elapsed = time.time() - start_time
        if elapsed > 5 and packet_count == 0:
            print("\n⚠️  5秒内未收到任何UDP数据！")
            print("请检查：")
            print("1. ESP32是否已连接到同一网络")
            print("2. ESP32的UDP目标地址是否正确")
            print("3. 防火墙是否阻止了UDP 5000端口")
            break
        continue
    except KeyboardInterrupt:
        print("\n\n已停止")
        break
