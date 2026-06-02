#!/usr/bin/env python3
"""测试视频录制功能"""
import cv2
import numpy as np
import os
import time

def test_video_write():
    print("=== 测试视频写入 ===")
    
    test_file = "test_output.mp4"
    resolution = (640, 480)
    fps = 15
    
    # 测试不同编码
    codecs = [
        ('XVID', 'XVID'),
        ('MJPG', 'MJPG'),
        ('mp4v', 'mp4v'),
        ('avc1', 'avc1'),
    ]
    
    for codec_name, codec_code in codecs:
        print(f"\n测试编码: {codec_name}")
        fourcc = cv2.VideoWriter_fourcc(*codec_code)
        writer = cv2.VideoWriter(test_file, fourcc, fps, resolution)
        
        if writer.isOpened():
            print(f"  ✓ VideoWriter 初始化成功")
            
            # 写入100帧测试数据（彩色渐变）
            for i in range(100):
                # 创建测试图像 - 彩色渐变
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                img[:, :, 0] = i * 2  # 蓝色通道
                img[:, :, 1] = 255 - i * 2  # 绿色通道
                img[:, :, 2] = 128  # 红色通道
                
                # 添加测试文字
                cv2.putText(img, f"Test Frame {i}", (50, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
                
                writer.write(img)
            
            writer.release()
            
            # 检查文件
            if os.path.exists(test_file):
                size = os.path.getsize(test_file)
                print(f"  ✓ 文件生成成功，大小: {size} 字节")
                
                # 尝试读取验证
                cap = cv2.VideoCapture(test_file)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        print(f"  ✓ 视频可正常读取，帧尺寸: {frame.shape}")
                        cap.release()
                        os.remove(test_file)
                        print(f"  ✓ 编码 {codec_name} 完全可用!")
                        return codec_code  # 返回可用的编码
                    else:
                        print(f"  ✗ 视频无法读取帧")
                    cap.release()
                else:
                    print(f"  ✗ 生成的视频无法打开")
            else:
                print(f"  ✗ 文件未生成")
        else:
            print(f"  ✗ VideoWriter 初始化失败")
        
        if os.path.exists(test_file):
            os.remove(test_file)
    
    print("\n=== 所有编码测试完成 ===")
    return None

if __name__ == "__main__":
    available_codec = test_video_write()
    if available_codec:
        print(f"\n推荐使用编码: {available_codec}")
    else:
        print("\n警告: 未找到可用的编码格式!")
