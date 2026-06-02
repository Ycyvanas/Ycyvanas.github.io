#!/usr/bin/env python3
"""
视频循环录制模块 - 循环存储最近1小时的视频
使用 FFmpeg 编码 H.264 MP4，浏览器原生支持
"""
import os
import time
import threading
import cv2
import numpy as np
from collections import deque
import glob
import subprocess
import signal

class VideoRecorder:
    def __init__(self, 
                 video_dir="recordings", 
                 segment_duration=60,  # 每个视频片段时长（秒），默认1分钟
                 max_storage_duration=3600,  # 最大存储时长（秒），默认1小时
                 fps=15,  # 录制帧率
                 resolution=(640, 480)):
        
        self.video_dir = video_dir
        self.segment_duration = segment_duration
        self.max_storage_duration = max_storage_duration
        self.fps = fps
        self.resolution = resolution
        
        # 视频变换设置（与web端同步）
        self.flip_h = False   # 水平翻转
        self.flip_v = False   # 垂直翻转
        self.rotate = 0       # 旋转角度 0/90/180/270
        
        # 确保视频目录存在
        os.makedirs(video_dir, exist_ok=True)
        
        # 视频写入相关
        self.current_ffmpeg = None
        self.current_segment_start = 0
        self.current_filename = ""
        
        # 帧缓冲区
        self.frame_buffer = deque(maxlen=100)
        self.buffer_lock = threading.Lock()
        
        # 录制状态
        self.recording = False
        self.recorder_thread = None
        self.stop_event = threading.Event()
        
        # 统计信息
        self.total_frames_written = 0
        self.segment_frames = 0
        self.last_fps_calc = time.time()
        self.fps_calc_frames = 0
        
        self.stats = {
            'total_recordings': 0,
            'current_segment': '',
            'segments_stored': 0,
            'total_storage_size': 0,
            'recording_fps': 0,
            'encoder': 'H.264 MP4 (所有浏览器支持)'
        }
        
        print(f"[Recorder] 视频存储目录: {os.path.abspath(video_dir)}")
        print(f"[Recorder] 分段时长: {segment_duration} 秒")
        print(f"[Recorder] 最大存储: {max_storage_duration} 秒 ({max_storage_duration/3600:.1f} 小时)")
        print(f"[Recorder] 录制分辨率: {resolution}, 帧率: {fps}")
        print(f"[Recorder] 编码器: {self.stats['encoder']}")
    
    def set_transform(self, flip_h=False, flip_v=False, rotate=0):
        """设置视频变换参数（与web端同步）"""
        self.flip_h = flip_h
        self.flip_v = flip_v
        self.rotate = rotate
        print(f"[Recorder] 变换设置已更新: 水平翻转={flip_h}, 垂直翻转={flip_v}, 旋转={rotate}°")
    
    def add_frame(self, jpeg_data):
        """添加一帧JPEG数据到录制缓冲区"""
        if not self.recording:
            return
        
        try:
            with self.buffer_lock:
                self.frame_buffer.append((time.time(), jpeg_data))
        except Exception as e:
            print(f"[Recorder] 添加帧失败: {e}")
    
    def _close_current_segment(self):
        """关闭当前分段并确保文件完整"""
        if self.current_ffmpeg is not None:
            try:
                # 关闭stdin管道，让FFmpeg正常结束
                self.current_ffmpeg.stdin.close()
            except:
                pass
            
            try:
                # 等待最多5秒让FFmpeg完成写入索引
                ret = self.current_ffmpeg.wait(timeout=5)
                print(f"[Recorder] 分段 {self.current_filename} 完成，写入 {self.segment_frames} 帧，退出码: {ret}")
            except:
                # 超时则强制杀死
                try:
                    self.current_ffmpeg.terminate()
                    self.current_ffmpeg.wait(timeout=2)
                    print(f"[Recorder] 分段 {self.current_filename} 强制关闭，写入 {self.segment_frames} 帧")
                except:
                    pass
            
            self.current_ffmpeg = None
    
    def _create_new_segment(self):
        """创建新的视频分段"""
        try:
            # 先关闭当前分段
            self._close_current_segment()
            
            # 生成文件名: yyyymmdd_HHMMSS.mp4
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}.mp4"
            filepath = os.path.join(self.video_dir, filename)
            
            # 使用FFmpeg编码H.264，通过管道接收原始帧
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-s', f'{self.resolution[0]}x{self.resolution[1]}',
                '-pix_fmt', 'bgr24',
                '-r', str(self.fps),
                '-i', '-',  # 从标准输入读取
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',  # 优化网络播放
                '-f', 'mp4',
                filepath
            ]
            
            self.current_ffmpeg = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=1024*1024  # 1MB缓冲区
            )
            
            self.current_segment_start = time.time()
            self.current_filename = filename
            self.segment_frames = 0
            self.stats['current_segment'] = filename
            self.stats['total_recordings'] += 1
            print(f"[Recorder] 开始新分段: {filename}")
            return True
                
        except Exception as e:
            print(f"[Recorder] 创建分段异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _cleanup_old_segments(self):
        """清理过期的视频分段"""
        try:
            now = time.time()
            cutoff_time = now - self.max_storage_duration
            
            # 获取所有视频文件
            video_files = glob.glob(os.path.join(self.video_dir, "video_*.mp4")) + \
                         glob.glob(os.path.join(self.video_dir, "video_*.avi"))
            
            deleted_count = 0
            for filepath in video_files:
                try:
                    filename = os.path.basename(filepath)
                    # 格式: video_YYYYMMDD_HHMMSS.ext
                    time_str = filename[6:21]  # 提取 YYYYMMDD_HHMMSS
                    file_time = time.mktime(time.strptime(time_str, "%Y%m%d_%H%M%S"))
                    
                    if file_time < cutoff_time:
                        os.remove(filepath)
                        deleted_count += 1
                        print(f"[Recorder] 删除过期视频: {filename}")
                except Exception as e:
                    try:
                        mtime = os.path.getmtime(filepath)
                        if mtime < cutoff_time:
                            os.remove(filepath)
                            deleted_count += 1
                    except:
                        pass
            
            if deleted_count > 0:
                print(f"[Recorder] 清理完成，删除了 {deleted_count} 个过期文件")
                
            self._update_storage_stats()
            
        except Exception as e:
            print(f"[Recorder] 清理过期文件异常: {e}")
    
    def _update_storage_stats(self):
        """更新存储统计信息"""
        try:
            video_files = glob.glob(os.path.join(self.video_dir, "video_*.mp4")) + \
                         glob.glob(os.path.join(self.video_dir, "video_*.avi"))
            total_size = 0
            for f in video_files:
                total_size += os.path.getsize(f)
            
            self.stats['segments_stored'] = len(video_files)
            self.stats['total_storage_size'] = total_size
        except:
            pass
    
    def _recorder_loop(self):
        """录制主循环 - 严格按真实时钟采样，确保时间平滑流动"""
        last_cleanup_time = time.time()
        last_write_time = 0
        frame_interval = 1.0 / self.fps  # 每帧间隔时间
        
        print("[Recorder] 录制线程已启动")
        
        while not self.stop_event.is_set():
            try:
                now = time.time()
                
                # 检查是否需要创建新分段
                if (self.current_segment_start == 0 or 
                    now - self.current_segment_start >= self.segment_duration):
                    self._create_new_segment()
                    self._cleanup_old_segments()
                    last_cleanup_time = now
                    last_write_time = now
                
                # 严格按固定帧率采样，确保视频时间和真实时间一致
                if now - last_write_time < frame_interval:
                    time.sleep(0.001)
                    continue
                
                # 从缓冲区获取最新帧（只取最新的，丢弃所有旧帧）
                latest_frame = None
                with self.buffer_lock:
                    if len(self.frame_buffer) > 0:
                        # 取队列中最新的帧（最右边）
                        while len(self.frame_buffer) > 1:
                            self.frame_buffer.popleft()  # 丢弃旧帧
                        timestamp, jpeg_data = self.frame_buffer.popleft()
                        latest_frame = (timestamp, jpeg_data)
                
                if latest_frame is None:
                    # 没有新帧，等会儿再试
                    time.sleep(0.002)
                    continue
                
                timestamp, jpeg_data = latest_frame
                
                # 解码JPEG
                nparr = np.frombuffer(jpeg_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None and self.current_ffmpeg is not None:
                    # 确保尺寸正确
                    if img.shape[0] != self.resolution[1] or img.shape[1] != self.resolution[0]:
                        img = cv2.resize(img, self.resolution)
                    
                    # 应用视频变换（与web端同步）
                    if self.flip_h:
                        img = cv2.flip(img, 1)  # 水平翻转
                    if self.flip_v:
                        img = cv2.flip(img, 0)  # 垂直翻转
                    if self.rotate == 90:
                        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                    elif self.rotate == 180:
                        img = cv2.rotate(img, cv2.ROTATE_180)
                    elif self.rotate == 270:
                        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                    # 确保最终尺寸正确（旋转后宽高可能交换）
                    if img.shape[0] != self.resolution[1] or img.shape[1] != self.resolution[0]:
                        img = cv2.resize(img, self.resolution)
                    
                    # 添加时间戳水印 - 显示当前录制时间
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
                    cv2.putText(img, time_str, (10, self.resolution[1] - 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
                    
                    # 写入FFmpeg管道
                    try:
                        self.current_ffmpeg.stdin.write(img.tobytes())
                    except BrokenPipeError:
                        print(f"[Recorder] FFmpeg管道断开，重启分段")
                        self._create_new_segment()
                        continue
                    except Exception as e:
                        print(f"[Recorder] 写入失败: {e}")
                        continue
                    
                    self.segment_frames += 1
                    self.total_frames_written += 1
                    self.fps_calc_frames += 1
                    last_write_time = now  # 更新最后一帧写入时间
                
                # 计算FPS
                if now - self.last_fps_calc >= 2.0:
                    self.stats['recording_fps'] = self.fps_calc_frames / (now - self.last_fps_calc)
                    self.fps_calc_frames = 0
                    self.last_fps_calc = now
                
                # 定期清理
                if now - last_cleanup_time >= 300:
                    self._cleanup_old_segments()
                    last_cleanup_time = now
                
            except Exception as e:
                print(f"[Recorder] 录制循环异常: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
        
        # 清理 - 关闭最后一个分段
        self._close_current_segment()
        print("[Recorder] 录制线程已停止")
    
    def start(self):
        """启动录制"""
        if self.recording:
            print("[Recorder] 录制已在运行中")
            return
        
        self.stop_event.clear()
        self.recording = True
        self.recorder_thread = threading.Thread(target=self._recorder_loop, daemon=True)
        self.recorder_thread.start()
        print("[Recorder] 录制已启动")
    
    def stop(self):
        """停止录制"""
        if not self.recording:
            return
        
        self.stop_event.set()
        self.recording = False
        if self.recorder_thread:
            self.recorder_thread.join(timeout=10)
        print("[Recorder] 录制已停止")
    
    def get_stats(self):
        """获取录制统计信息"""
        self._update_storage_stats()
        result = self.stats.copy()
        result['recording'] = self.recording
        result['buffer_size'] = len(self.frame_buffer)
        result['video_dir'] = os.path.abspath(self.video_dir)
        result['total_storage_size_mb'] = result['total_storage_size'] / (1024 * 1024)
        result['total_frames'] = self.total_frames_written
        return result
    
    def get_video_list(self):
        """获取已录制的视频列表"""
        try:
            video_files = sorted(
                glob.glob(os.path.join(self.video_dir, "video_*.mp4")) + 
                glob.glob(os.path.join(self.video_dir, "video_*.avi")),
                reverse=True
            )
            result = []
            for filepath in video_files:
                filename = os.path.basename(filepath)
                size = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)
                result.append({
                    'filename': filename,
                    'size_bytes': size,
                    'size_mb': size / (1024 * 1024),
                    'modified': mtime,
                    'modified_str': time.strftime("%Y-%m-%d %H:%M:%S", 
                                                  time.localtime(mtime))
                })
            return result
        except Exception as e:
            print(f"[Recorder] 获取视频列表失败: {e}")
            return []
    
    def get_video_path(self, filename):
        """获取视频文件的完整路径，带安全检查"""
        if '..' in filename or '/' in filename or '\\' in filename:
            return None
        
        filepath = os.path.join(self.video_dir, filename)
        if os.path.exists(filepath) and filename.startswith('video_'):
            return filepath
        return None


# 单例实例
_recorder_instance = None

def get_recorder(**kwargs):
    """获取录制器单例"""
    global _recorder_instance
    if _recorder_instance is None:
        _recorder_instance = VideoRecorder(**kwargs)
    return _recorder_instance


if __name__ == "__main__":
    recorder = get_recorder()
    recorder.start()
    
    try:
        while True:
            time.sleep(2)
            stats = recorder.get_stats()
            print(f"\r录制中: {stats['recording']}, FPS: {stats['recording_fps']:.1f}, "
                  f"分段: {stats['segments_stored']}, 存储: {stats['total_storage_size_mb']:.2f} MB, "
                  f"总帧数: {stats['total_frames']}",
                  end='')
    except KeyboardInterrupt:
        print("\n")
        recorder.stop()
