#!/usr/bin/env python3
"""
ycycam-udp Web视频接收服务 + 实时物品识别 + 循环录像
"""
import socket
import struct
import time
import threading
import os
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import json
from urllib.parse import parse_qs

# 导入视频录制模块
from video_recorder import get_recorder

# 识别模块（可选加载）
try:
    import cv2
    import numpy as np
    from ultralytics import YOLO
    DETECTOR_ENABLED = True
except ImportError as e:
    print(f"[Info] 识别模块未加载: {e}")
    DETECTOR_ENABLED = False

UDP_PORT = 5000
HTTP_PORT = 8000
MAX_PAYLOAD = 1472

latest_frame = None
stream_enabled = True

# UDP命令发送（到ESP32的5001端口）
udp_cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ESP32_IP = None  # 自动从视频流来源获取

stats = {
    'frames_received': 0,
    'packets_received': 0,
    'bytes_received': 0,
    'fps': 0.0,
    'bandwidth_mbps': 0.0,
    'stream_enabled': True
}

frame_times = deque(maxlen=50)

# ==================== 检测模块 ====================
_detection_lock = threading.Lock()
_latest_detections = {"timestamp": 0, "objects": [], "faces": []}
_object_buffer = {}  # 检测结果缓存，用于平滑显示
_object_ttl = 1.0   # 检测框保留时间（秒）
_yolo_model = None
_face_cascade = None
_detect_running = False

# 视频变换状态 - 与前端同步
_flip_h = False  # 水平翻转
_flip_v = False  # 垂直翻转
_rotate = 0      # 旋转角度 0/90/180/270
_detection_enabled = True  # 物体检测开关

def _detect_thread():
    """后台检测线程"""
    global _yolo_model, _face_cascade, _latest_detections
    
    print("[Detector] 正在加载 YOLOv8m 模型...")
    _yolo_model = YOLO('yolov8m.pt')
    print("[Detector] YOLO 模型加载完成")
    
    _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    print("[Detector] 人脸分类器加载完成")
    
    frame_count = 0
    while _detect_running:
        try:
            f = latest_frame
            if f is None or not _detection_enabled:
                time.sleep(0.05)
                continue
            
            # 每隔 6 帧检测一次，降低抖动和 CPU 占用
            frame_count += 1
            if frame_count % 6 != 0:
                time.sleep(0.02)
                continue
            
            # JPEG 转 numpy
            nparr = np.frombuffer(f, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            
            # 应用与前端一致的图像变换
            img_h, img_w = img.shape[:2]
            if _flip_h:
                img = cv2.flip(img, 1)  # 水平翻转
            if _flip_v:
                img = cv2.flip(img, 0)  # 垂直翻转
            if _rotate == 90:
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif _rotate == 180:
                img = cv2.rotate(img, cv2.ROTATE_180)
            elif _rotate == 270:
                img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # YOLO 物品检测 - 降低检测灵敏度，减少误报
            results = _yolo_model(img, verbose=False, conf=0.6, iou=0.3)
            
            now = time.time()
            current_objects = {}
            
            # 收集当前检测结果
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(float, box.xyxy[0])
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = _yolo_model.names[cls_id]
                    
                    # 使用中心点作为物体标识的一部分
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    # 只保留主要类别，减少杂乱
                    if label not in ['person', 'cell phone', 'laptop', 'car', 'bottle', 'cup', 
                                     'chair', 'dog', 'cat', 'tv', 'mouse', 'keyboard']:
                        continue
                    
                    # 搜索缓冲区内的同一物体（简单距离匹配）
                    obj_key = None
                    for key, cached in _object_buffer.items():
                        if key.startswith(label + "_"):
                            c_x, c_y = cached['center']
                            dist = ((center_x - c_x)**2 + (center_y - c_y)**2)**0.5
                            if dist < 80:  # 80像素内认为是同一物体
                                obj_key = key
                                break
                    
                    if obj_key is None:
                        obj_key = f"{label}_{int(center_x)}_{int(center_y)}"
                    
                    # 更新或添加到缓冲区
                    current_objects[obj_key] = {
                        "label": label,
                        "confidence": round(conf, 3),
                        "box": [round(x1, 1), round(y1, 1), round(x2-x1, 1), round(y2-y1, 1)],
                        "center": (center_x, center_y),
                        "last_seen": now
                    }
            
            # 合并新旧检测结果，保留 TTL 内的物体
            for key in list(_object_buffer.keys()):
                if now - _object_buffer[key]['last_seen'] < _object_ttl:
                    if key not in current_objects:
                        current_objects[key] = _object_buffer[key]
                        
            _object_buffer.clear()
            _object_buffer.update(current_objects)
            
            # 人脸检测
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = _face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(50, 50))
            face_list = []
            for (x, y, w, h) in faces:
                face_list.append({
                    "label": "face",
                    "confidence": 0.95,
                    "box": [float(x), float(y), float(w), float(h)]
                })
            
            # 更新结果
            with _detection_lock:
                _latest_detections = {
                    "timestamp": now,
                    "objects": [{"label": o["label"], "confidence": o["confidence"], "box": o["box"]} 
                               for o in _object_buffer.values()],
                    "faces": face_list
                }
                
        except Exception as e:
            time.sleep(0.1)


def start_detection():
    """启动检测线程"""
    global _detect_running
    if not DETECTOR_ENABLED or _detect_running:
        return
    _detect_running = True
    t = threading.Thread(target=_detect_thread, daemon=True)
    t.start()
    print("[Detector] 检测线程已启动")


def get_latest_detections():
    """获取最新检测结果"""
    if not DETECTOR_ENABLED:
        return {"timestamp": 0, "objects": [], "faces": [], "info": "detection disabled"}
    if not _detection_enabled:
        return {"timestamp": 0, "objects": [], "faces": [], "info": "detection paused", "enabled": False}
    with _detection_lock:
        result = _latest_detections.copy()
        result["enabled"] = True
        return result
# ====================================================


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_index()
        elif self.path.startswith('/stream'):
            self.send_stream()
        elif self.path.startswith('/status'):
            self.send_status()
        elif self.path.startswith('/detections'):
            self.send_detections()
        elif self.path == '/start':
            self.set_stream(True)
        elif self.path == '/stop':
            self.set_stream(False)
        elif self.path.startswith('/set_transform'):
            self.set_transform()
        elif self.path.startswith('/detection_on'):
            self.set_detection(True)
        elif self.path.startswith('/detection_off'):
            self.set_detection(False)
        elif self.path.startswith('/led_cmd'):
            self.handle_led_cmd()
        elif self.path.startswith('/camera_cmd'):
            self.handle_camera_cmd()
        # 录像相关API
        elif self.path.startswith('/recorder_status'):
            self.send_recorder_status()
        elif self.path.startswith('/video_list'):
            self.send_video_list()
        elif self.path.startswith('/video/'):
            self.serve_video_file()
        elif self.path.startswith('/recordings'):
            self.send_recordings_page()
        else:
            self.send_error(404)
    
    def set_transform(self):
        """设置视频变换状态（翻转/旋转）"""
        global _flip_h, _flip_v, _rotate, recorder
        try:
            # 解析查询参数
            import urllib.parse
            query = self.path.split('?', 1)[1] if '?' in self.path else ''
            params = urllib.parse.parse_qs(query)
            
            _flip_h = params.get('flip_h', ['false'])[0].lower() == 'true'
            _flip_v = params.get('flip_v', ['false'])[0].lower() == 'true'
            _rotate = int(params.get('rotate', ['0'])[0])
            
            # 同步更新录像器的变换设置
            if recorder:
                recorder.set_transform(_flip_h, _flip_v, _rotate)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "flip_h": _flip_h, "flip_v": _flip_v, "rotate": _rotate}).encode())
        except Exception as e:
            self.send_response(400)
            self.end_headers()
    
    def set_detection(self, enable):
        """设置物体检测开关"""
        global _detection_enabled
        _detection_enabled = enable
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "detection_enabled": _detection_enabled}).encode())
    
    def handle_led_cmd(self):
        """处理LED控制命令，通过UDP转发到ESP32"""
        global ESP32_IP, udp_cmd_socket
        try:
            import urllib.parse
            query = self.path.split('?', 1)[1] if '?' in self.path else ''
            params = urllib.parse.parse_qs(query)
            
            if ESP32_IP is None:
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "msg": "ESP32 not connected"}).encode())
                return
            
            # 转发命令到ESP32的5001端口
            if 'period' in params:
                cmd = f"period={params['period'][0]}"
                udp_cmd_socket.sendto(cmd.encode(), (ESP32_IP, 5001))
            elif 'enable' in params:
                cmd = f"enable={params['enable'][0]}"
                udp_cmd_socket.sendto(cmd.encode(), (ESP32_IP, 5001))
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "cmd": cmd if 'cmd' in locals() else None}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "msg": str(e)}).encode())
    
    def handle_camera_cmd(self):
        """处理相机控制命令，通过UDP转发到ESP32"""
        global ESP32_IP, udp_cmd_socket
        try:
            import urllib.parse
            query = self.path.split('?', 1)[1] if '?' in self.path else ''
            params = urllib.parse.parse_qs(query)
            
            if ESP32_IP is None:
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "msg": "ESP32 not connected"}).encode())
                return
            
            # 处理所有相机控制命令
            cmd = None
            
            # 白平衡模式
            if 'wb_mode' in params:
                cmd = f"wb_mode={params['wb_mode'][0]}"
            
            # 自动白平衡开关
            if 'whitebal' in params:
                cmd = f"whitebal={params['whitebal'][0]}"
            
            # AWB增益
            if 'awb_gain' in params:
                cmd = f"awb_gain={params['awb_gain'][0]}"
            
            # 发送命令到ESP32
            if cmd:
                udp_cmd_socket.sendto(cmd.encode(), (ESP32_IP, 5001))
                print(f"[Camera] 发送命令: {cmd} 到 {ESP32_IP}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "cmd": cmd}).encode())
        except Exception as e:
            print(f"[Camera] 命令发送失败: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "msg": str(e)}).encode())
    
    def send_recorder_status(self):
        """返回录像器状态"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if recorder is None:
            self.wfile.write(json.dumps({"status": "not_initialized"}).encode())
        else:
            self.wfile.write(json.dumps(recorder.get_stats()).encode())
    
    def send_video_list(self):
        """返回已录制视频列表"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if recorder is None:
            self.wfile.write(json.dumps({"videos": []}).encode())
        else:
            videos = recorder.get_video_list()
            self.wfile.write(json.dumps({"videos": videos}).encode())
    
    def serve_video_file(self):
        """提供视频文件下载/播放"""
        try:
            # 从路径提取文件名 /video/filename.mp4
            filename = self.path[7:]  # 去掉 '/video/'
            
            if recorder is None:
                self.send_error(404, "Recorder not initialized")
                return
            
            filepath = recorder.get_video_path(filename)
            if filepath is None or not os.path.exists(filepath):
                self.send_error(404, "Video not found")
                return
            
            file_size = os.path.getsize(filepath)
            
            # 根据文件扩展名设置正确的Content-Type
            if filename.endswith('.avi'):
                content_type = 'video/x-msvideo'
            else:
                content_type = 'video/mp4'
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            
            # 发送文件内容
            with open(filepath, 'rb') as f:
                chunk_size = 64 * 1024  # 64KB chunks
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    
        except Exception as e:
            self.send_error(500, str(e))
    
    def send_recordings_page(self):
        """返回录像管理页面"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ycycam-udp 录像管理</title>
    <style>
        body { background: #0a0a0f; color: #fff; font-family: Arial; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { color: #0f0; text-align: center; }
        .nav { text-align: center; margin-bottom: 20px; }
        .nav a { color: #0af; text-decoration: none; margin: 0 15px; }
        .nav a:hover { text-decoration: underline; }
        
        .status-card { background: #1a1a2e; padding: 25px; border-radius: 12px; margin-bottom: 20px; }
        .status-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 15px; }
        .status-item { background: #16213e; padding: 15px; border-radius: 8px; text-align: center; }
        .status-val { font-size: 28px; font-weight: bold; color: #0f0; font-family: monospace; }
        .status-label { color: #888; font-size: 12px; margin-top: 5px; }
        
        .video-list { background: #1a1a2e; padding: 25px; border-radius: 12px; }
        .video-item { 
            display: flex; justify-content: space-between; align-items: center;
            padding: 15px; background: #16213e; border-radius: 8px; margin-bottom: 10px;
            transition: transform 0.2s;
        }
        .video-item:hover { transform: translateX(5px); background: #1f2a4e; }
        .video-info { flex: 1; }
        .video-name { font-size: 16px; font-weight: bold; color: #0af; }
        .video-meta { color: #888; font-size: 13px; margin-top: 5px; }
        .video-actions { display: flex; gap: 10px; }
        .btn { 
            padding: 8px 20px; border: none; border-radius: 6px; 
            font-size: 14px; font-weight: bold; cursor: pointer; text-decoration: none;
            display: inline-block; text-align: center;
        }
        .btn-play { background: #4caf50; color: white; }
        .btn-download { background: #2196f3; color: white; }
        .btn-refresh { background: #ff9800; color: white; }
        .empty-state { text-align: center; padding: 50px; color: #666; }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 录像管理</h1>
        <div class="nav">
            <a href="/">← 返回监控页面</a>
        </div>
        
        <div class="status-card">
            <div class="header-row">
                <h2 style="margin: 0; color: #0af;">📊 录制状态</h2>
                <button class="btn btn-refresh" onclick="refreshStatus()">🔄 刷新</button>
            </div>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-val" id="rec-status">--</div>
                    <div class="status-label">录制状态</div>
                </div>
                <div class="status-item">
                    <div class="status-val" id="rec-fps">0.0</div>
                    <div class="status-label">录制 FPS</div>
                </div>
                <div class="status-item">
                    <div class="status-val" id="rec-count">0</div>
                    <div class="status-label">视频分段</div>
                </div>
                <div class="status-item">
                    <div class="status-val" id="rec-size">0.00 MB</div>
                    <div class="status-label">存储空间</div>
                </div>
            </div>
            <div style="margin-top: 15px; color: #888; font-size: 13px;">
                <strong>循环存储:</strong> 自动保留最近1小时的视频，每10分钟一个分段
            </div>
        </div>
        
        <div class="video-list">
            <div class="header-row">
                <h2 style="margin: 0; color: #0af;">📼 已录制视频</h2>
                <button class="btn btn-refresh" onclick="refreshList()">🔄 刷新列表</button>
            </div>
            <div id="videoList">
                <div class="empty-state">加载中...</div>
            </div>
        </div>
    </div>
    
    <script>
        function refreshStatus() {
            fetch('/recorder_status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('rec-status').textContent = 
                        data.recording ? '✅ 录制中' : '⏸️ 已停止';
                    document.getElementById('rec-status').style.color = 
                        data.recording ? '#0f0' : '#f80';
                    document.getElementById('rec-fps').textContent = 
                        data.recording_fps ? data.recording_fps.toFixed(1) : '0.0';
                    document.getElementById('rec-count').textContent = 
                        data.segments_stored || 0;
                    document.getElementById('rec-size').textContent = 
                        (data.total_storage_size_mb || 0).toFixed(2) + ' MB';
                })
                .catch(e => console.error(e));
        }
        
        function refreshList() {
            fetch('/video_list')
                .then(r => r.json())
                .then(data => {
                    const listEl = document.getElementById('videoList');
                    if (!data.videos || data.videos.length === 0) {
                        listEl.innerHTML = '<div class="empty-state">暂无录像文件<br>请等待系统生成第一个视频分段（约需10分钟）</div>';
                        return;
                    }
                    
                    let html = '';
                    data.videos.forEach(v => {
                        html += `
                            <div class="video-item">
                                <div class="video-info">
                                    <div class="video-name">📹 ${v.filename}</div>
                                    <div class="video-meta">
                                        📅 ${v.modified_str} | 📦 ${v.size_mb.toFixed(2)} MB
                                    </div>
                                </div>
                                <div class="video-actions">
                                    <a href="/video/${v.filename}" target="_blank" class="btn btn-play">▶️ 播放</a>
                                    <a href="/video/${v.filename}" download="${v.filename}" class="btn btn-download">⬇️ 下载</a>
                                </div>
                            </div>
                        `;
                    });
                    listEl.innerHTML = html;
                })
                .catch(e => {
                    document.getElementById('videoList').innerHTML = 
                        '<div class="empty-state">加载失败: ' + e.message + '</div>';
                });
        }
        
        // 页面加载时刷新
        refreshStatus();
        refreshList();
        
        // 自动刷新状态
        setInterval(refreshStatus, 5000);
    </script>
</body>
</html>
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def send_detections(self):
        """返回识别结果API"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        result = get_latest_detections()
        self.wfile.write(json.dumps(result).encode())

    def send_index(self):
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ycycam-udp</title>
    <style>
        body { background: #0a0a0f; color: #fff; font-family: Arial; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #0f0; text-align: center; }
        .video-box { background: #111; padding: 20px; border-radius: 12px; text-align: center; }
        #video { max-width: 100%; border-radius: 8px; }
        .stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 15px; margin-top: 20px; }
        .stat { background: #1a1a2e; padding: 15px; border-radius: 8px; text-align: center; }
        .val { font-size: 32px; font-weight: bold; color: #0f0; font-family: monospace; }
        .label { color: #888; font-size: 12px; margin-top: 5px; }
        .btn { margin-top: 20px; padding: 15px 40px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; color: white; }
        .btn-stop { background: #f44336; }
        .btn-start { background: #4caf50; }
        .status { margin-top: 15px; color: #0f0; }
        .stopped { color: #ffa726; }
        
        /* 视频控制按钮组 */
        .controls-group {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        .ctrl-btn {
            padding: 10px 16px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            background: #2d3748;
            color: white;
            transition: all 0.2s;
        }
        .ctrl-btn:hover { background: #4a5568; transform: translateY(-1px); }
        .ctrl-btn.active { background: #00b894; box-shadow: 0 2px 8px rgba(0,184,148,0.3); }
        
        /* 视频变换效果 */
        .flip-h { transform: scaleX(-1); }
        .flip-v { transform: scaleY(-1); }
        .rotate-90 { transform: rotate(90deg); }
        .rotate-180 { transform: rotate(180deg); }
        .rotate-270 { transform: rotate(270deg); }
        
        /* 检测框文字反向变换 - 保持文字正常显示 */
        .box-flip-h { transform: scaleX(-1); }
        .box-flip-v { transform: scaleY(-1); }
        .box-rotate-90 { transform: rotate(-90deg); }
        .box-rotate-180 { transform: rotate(-180deg); }
        .box-rotate-270 { transform: rotate(-270deg); }
        
        /* 识别框样式 */
        .video-wrapper { position: relative; display: inline-block; }
        .detection-overlay {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none;
        }
        .detection-box {
            position: absolute;
            border: 2px solid;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            padding: 2px 6px;
            background: rgba(0,0,0,0.6);
            text-shadow: 1px 1px 2px black;
        }
        .detection-label {
            color: white;
            font-size: 11px;
        }
        /* 常用物品颜色 */
        .color-person { border-color: #ff4444; color: #ff4444; }
        .color-car { border-color: #ff8800; color: #ff8800; }
        .color-dog { border-color: #aa66cc; color: #aa66cc; }
        .color-cat { border-color: #cc0099; color: #cc0099; }
        .color-bird { border-color: #00c851; color: #00c851; }
        .color-default { border-color: #00ff00; color: #00ff00; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ycycam-udp Video Monitor</h1>
        <div class="video-box">
            <div class="video-wrapper">
                <img id="video" src="/stream">
                <div id="detectionOverlay" class="detection-overlay"></div>
            </div>
            <div id="status" class="status">LIVE - Playing</div>
            <button id="btn" class="btn btn-stop" onclick="toggle()">Stop Stream</button>
            
            <!-- 视频控制按钮组 -->
            <div class="controls-group">
                <button class="ctrl-btn" onclick="toggleFlipH()">↔️ 水平翻转</button>
                <button class="ctrl-btn" onclick="toggleFlipV()">↕️ 垂直翻转</button>
                <button class="ctrl-btn" onclick="rotate90()">🔄 旋转90°</button>
                <button class="ctrl-btn" onclick="resetTransform()">🔄 重置</button>
                <button class="ctrl-btn" onclick="snapshot()" style="background: #e74c3c;">📸 拍照</button>
                <button id="detectBtn" class="ctrl-btn active" onclick="toggleDetection()" style="background: #27ae60;">🔍 检测开</button>
                <a href="/recordings" target="_blank" style="text-decoration:none;">
                    <button class="ctrl-btn" style="background: #9b59b6;">🎥 录像管理</button>
                </a>
            </div>

            <!-- 白平衡控制 -->
            <div class="wb-controls" style="margin-top:20px;padding:15px;background:#1a1a2e;border-radius:8px;">
                <h3 style="color:#0af;margin:0 0 15px 0;text-align:left;">🎨 白平衡控制</h3>
                <div class="controls-group" style="justify-content:flex-start;">
                    <button id="wb-btn-0" class="ctrl-btn" onclick="setWBMode(0)" title="自动" style="background:#0af;">🏠 自动</button>
                    <button id="wb-btn-1" class="ctrl-btn" onclick="setWBMode(1)" title="晴天">☀️ 晴天</button>
                    <button id="wb-btn-2" class="ctrl-btn" onclick="setWBMode(2)" title="阴天">☁️ 阴天</button>
                    <button id="wb-btn-3" class="ctrl-btn" onclick="setWBMode(3)" title="白炽灯">💡 白炽灯</button>
                    <button id="wb-btn-4" class="ctrl-btn" onclick="setWBMode(4)" title="荧光灯">💡 荧光灯</button>
                    <button id="wb-btn-5" class="ctrl-btn" onclick="setWBMode(5)" title="夜间" style="background:#4a148c;">🌙 夜间</button>
                </div>
            </div>

            <!-- LED 闪烁控制 -->
            <div class="led-controls" style="margin-top:20px;padding:15px;background:#1a1a2e;border-radius:8px;">
                <h3 style="color:#f50;margin:0 0 15px 0;text-align:left;">💡 LED 闪烁控制</h3>
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:15px;">
                    <span style="color:#888;">LED闪烁</span>
                    <label class="switch">
                        <input type="checkbox" id="led_enable" checked onchange="setLEDEnable(this.checked)">
                        <span class="slider" style="position:relative;width:50px;height:26px;background:#555;border-radius:26px;display:inline-block;cursor:pointer;"></span>
                    </label>
                </div>
                <div style="text-align:left;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px;color:#0af;">
                        <span>闪烁周期</span>
                        <span id="period_value">1000 ms</span>
                    </div>
                    <input type="range" id="period_range" min="50" max="10000" value="1000" step="50" 
                           style="width:100%;height:8px;background:#222;border-radius:4px;outline:none;"
                           oninput="updatePeriod(this.value)">
                </div>
                <div class="preset-buttons" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:15px;">
                    <button class="ctrl-btn" onclick="setPreset(100)">极快 100ms</button>
                    <button class="ctrl-btn" onclick="setPreset(500)">快 500ms</button>
                    <button class="ctrl-btn" onclick="setPreset(1000)">正常 1s</button>
                    <button class="ctrl-btn" onclick="setPreset(2000)">慢 2s</button>
                    <button class="ctrl-btn" onclick="setPreset(5000)">很慢 5s</button>
                    <button class="ctrl-btn" onclick="setPreset(10000)">极慢 10s</button>
                </div>
                <div id="led-status" style="margin-top:10px;color:#f50;font-size:12px;text-align:left;">当前周期: 1000 ms</div>
            </div>

            <div id="snapshot-status" style="margin-top: 10px; color: #aaa; font-size: 12px;"></div>
        </div>
        <div class="stats">
            <div class="stat"><div class="val" id="fps">0.0</div><div class="label">FPS</div></div>
            <div class="stat"><div class="val" id="frames">0</div><div class="label">Frames</div></div>
            <div class="stat"><div class="val" id="bw">0.00</div><div class="label">Mbps</div></div>
            <div class="stat"><div class="val">640x480</div><div class="label">Resolution</div></div>
        </div>
    </div>
    <script>
        var running = true;
        var initialized = false;
        var fpsEl = document.getElementById('fps');
        var framesEl = document.getElementById('frames');
        var bwEl = document.getElementById('bw');
        var videoEl = document.getElementById('video');
        var statusEl = document.getElementById('status');
        var btnEl = document.getElementById('btn');

        // 只用XMLHttpRequest，更可靠
        function refresh() {
            var xhr = new XMLHttpRequest();
            xhr.onload = function() {
                try {
                    var data = JSON.parse(xhr.responseText);
                    fpsEl.textContent = data.fps.toFixed(1);
                    framesEl.textContent = data.frames_received;
                    bwEl.textContent = data.bandwidth_mbps.toFixed(2);
                    
                    if (!initialized || data.stream_enabled !== running) {
                        running = data.stream_enabled;
                        updateUI();
                        initialized = true;
                    }
                } catch(err) {}
            };
            xhr.open('GET', '/status?r=' + Math.random(), true);
            xhr.timeout = 1000;
            xhr.send();
        }

        function updateUI() {
            if (running) {
                videoEl.src = '/stream?r=' + Date.now();
                videoEl.style.display = 'block';
                // 强制重新加载，确保视频流立即显示
                videoEl.decoding = 'sync';
                videoEl.loading = 'eager';
                // 触发图片重新加载
                videoEl.removeAttribute('srcset');
                // 强制浏览器重新渲染
                setTimeout(function() {
                    videoEl.style.opacity = '0.99';
                    setTimeout(function() {
                        videoEl.style.opacity = '1';
                    }, 10);
                }, 10);
                statusEl.className = 'status';
                statusEl.textContent = 'LIVE - Playing';
                btnEl.className = 'btn btn-stop';
                btnEl.textContent = 'Stop Stream';
            } else {
                videoEl.src = '';
                videoEl.style.display = 'none';
                statusEl.className = 'status stopped';
                statusEl.textContent = 'Paused';
                btnEl.className = 'btn btn-start';
                btnEl.textContent = 'Start Stream';
            }
        }

        function toggle() {
            running = !running;
            updateUI();
            var x = new XMLHttpRequest();
            x.open('GET', running ? '/start' : '/stop', true);
            x.send();
        }

        // ========== 视频控制功能 ==========
        var flipH = false;  // 水平翻转
        var flipV = false;  // 垂直翻转
        var rotation = 0;   // 旋转角度 0/90/180/270
        
        function applyTransform() {
            var transform = '';
            if (flipH) transform += ' scaleX(-1)';
            if (flipV) transform += ' scaleY(-1)';
            if (rotation != 0) transform += ' rotate(' + rotation + 'deg)';
            videoEl.style.transform = transform.trim();
            
            // 检测框和文字不跟随变换，保持正常显示
            // 后端检测时已应用相同变换，返回的坐标是变换后的正确位置
        }
        
        // 同步变换状态到后端
        function syncTransform() {
            var x = new XMLHttpRequest();
            x.open('GET', '/set_transform?flip_h=' + flipH + '&flip_v=' + flipV + '&rotate=' + rotation, true);
            x.send();
        }
        
        function toggleFlipH() {
            flipH = !flipH;
            applyTransform();
            syncTransform();
            event.target.classList.toggle('active', flipH);
        }
        
        function toggleFlipV() {
            flipV = !flipV;
            applyTransform();
            syncTransform();
            event.target.classList.toggle('active', flipV);
        }
        
        function rotate90() {
            rotation = (rotation + 90) % 360;
            applyTransform();
            syncTransform();
        }
        
        function resetTransform() {
            flipH = false;
            flipV = false;
            rotation = 0;
            applyTransform();
            syncTransform();
            document.querySelectorAll('.ctrl-btn').forEach(b => {
                if (!b.id || !b.id.includes('detect')) {
                    b.classList.remove('active');
                }
            });
        }
        
        var detectionEnabled = true;
        
        function toggleDetection() {
            detectionEnabled = !detectionEnabled;
            var btn = document.getElementById('detectBtn');
            var x = new XMLHttpRequest();
            x.open('GET', detectionEnabled ? '/detection_on' : '/detection_off', true);
            x.send();
            
            if (detectionEnabled) {
                btn.textContent = '🔍 检测开';
                btn.style.background = '#27ae60';
                btn.classList.add('active');
            } else {
                btn.textContent = '🔍 检测关';
                btn.style.background = '#7f8c8d';
                btn.classList.remove('active');
                // 清除现有检测框
                var overlay = document.getElementById('detectionOverlay');
                if (overlay) overlay.innerHTML = '';
            }
        }
        
        // ========== 白平衡控制 ==========
        var currentWBMode = 0;
        const wbModes = ['自动', '晴天', '阴天', '白炽灯', '荧光灯', '夜间'];
        
        function sendCameraCmd(params, endpoint) {
            // 通过HTTP代理发送命令到ESP32
            var x = new XMLHttpRequest();
            var url = (endpoint === 'led_ctrl') ? '/led_cmd' : '/camera_cmd';
            x.open('GET', url + '?' + params, true);
            x.onload = function() {
                // 发送成功
            };
            x.send();
        }
        
        function setWBMode(mode) {
            currentWBMode = mode;
            // 清除所有按钮高亮
            for (let i = 0; i < 6; i++) {
                const btn = document.getElementById('wb-btn-' + i);
                if (btn) {
                    if (i === 5) {
                        // 夜间按钮保持紫色基色
                        btn.style.background = '#4a148c';
                    } else {
                        btn.style.background = '';
                    }
                }
            }
            // 高亮当前选中按钮
            const currentBtn = document.getElementById('wb-btn-' + mode);
            if (currentBtn) {
                currentBtn.style.background = '#0af';
            }
            sendCameraCmd('wb_mode=' + mode);
        }

        // LED 控制功能
        function updatePeriod(val) {
            document.getElementById('period_value').textContent = val + ' ms';
            document.getElementById('led-status').textContent = '✓ 周期已设置: ' + val + ' ms';
            sendCameraCmd('period=' + val, 'led_ctrl');
        }
        
        function setLEDEnable(enable) {
            document.getElementById('led-status').textContent = '✓ LED已' + (enable?'开启':'关闭');
            sendCameraCmd('enable=' + (enable?1:0), 'led_ctrl');
        }
        
        function setPreset(period) {
            document.getElementById('period_range').value = period;
            updatePeriod(period);
        }
        
        // 拍照功能
        function snapshot() {
            var video = document.getElementById('video');
            if (!video || video.src === '') {
                alert('请先开启视频流');
                return;
            }
            
            // 创建canvas进行截图
            var canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            
            var ctx = canvas.getContext('2d');
            
            // 应用当前的变换效果
            ctx.save();
            if (flipH) {
                ctx.translate(canvas.width, 0);
                ctx.scale(-1, 1);
            }
            if (flipV) {
                ctx.translate(0, canvas.height);
                ctx.scale(1, -1);
            }
            if (rotation != 0) {
                ctx.translate(canvas.width / 2, canvas.height / 2);
                ctx.rotate(rotation * Math.PI / 180);
                ctx.translate(-canvas.width / 2, -canvas.height / 2);
            }
            
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            ctx.restore();
            
            // 添加时间戳水印
            ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
            ctx.fillRect(10, canvas.height - 35, 280, 25);
            ctx.fillStyle = '#00ff00';
            ctx.font = '16px monospace';
            var now = new Date();
            var timestamp = now.getFullYear() + '-' + 
                           String(now.getMonth() + 1).padStart(2, '0') + '-' + 
                           String(now.getDate()).padStart(2, '0') + ' ' + 
                           String(now.getHours()).padStart(2, '0') + ':' + 
                           String(now.getMinutes()).padStart(2, '0') + ':' + 
                           String(now.getSeconds()).padStart(2, '0');
            ctx.fillText('📷 ' + timestamp, 20, canvas.height - 17);
            
            // 下载图片
            var link = document.createElement('a');
            link.download = 'ycycam_' + now.getTime() + '.jpg';
            link.href = canvas.toDataURL('image/jpeg', 0.95);
            link.click();
            
            // 显示状态
            var statusEl = document.getElementById('snapshot-status');
            statusEl.textContent = '✅ 照片已保存: ' + link.download;
            setTimeout(function() {
                statusEl.textContent = '';
            }, 3000);
        }
        // =================================

        // 获取物品颜色
        function getColor(label) {
            var colors = {
                'person': '#ff4444',
                'car': '#ff8800',
                'dog': '#aa66cc',
                'cat': '#cc0099',
                'bird': '#00c851',
                'bottle': '#33b5e5',
                'cup': '#0099cc',
                'chair': '#ffbb33',
                'laptop': '#880e4f',
                'cell phone': '#ff00ff'
            };
            return colors[label] || '#00ff00';
        }

        // 更新识别框
        function updateDetections() {
            var xhr = new XMLHttpRequest();
            xhr.onload = function() {
                try {
                    var data = JSON.parse(xhr.responseText);
                    var overlay = document.getElementById('detectionOverlay');
                    if (!overlay) return;
                    
                    // 清空旧的
                    overlay.innerHTML = '';
                    
                    // 物品识别框
                    if (data.objects && data.objects.length > 0) {
                        // 640x480 相对坐标
                        var imgW = 640, imgH = 480;
                        
                        data.objects.forEach(function(obj) {
                            var box = document.createElement('div');
                            box.className = 'detection-box';
                            
                            var x = (obj.box[0] / imgW * 100).toFixed(2);
                            var y = (obj.box[1] / imgH * 100).toFixed(2);
                            var w = (obj.box[2] / imgW * 100).toFixed(2);
                            var h = (obj.box[3] / imgH * 100).toFixed(2);
                            
                            var color = getColor(obj.label);
                            box.style.left = x + '%';
                            box.style.top = y + '%';
                            box.style.width = w + '%';
                            box.style.height = h + '%';
                            box.style.borderColor = color;
                            box.style.color = color;
                            
                            var confPct = Math.round(obj.confidence * 100);
                            box.innerHTML = '<span class="detection-label">' + obj.label + ' ' + confPct + '%</span>';
                            overlay.appendChild(box);
                        });
                    }
                } catch(e) {}
            };
            xhr.open('GET', '/detections?r=' + Math.random(), true);
            xhr.timeout = 1000;
            xhr.send();
        }

        // 立即启动
        refresh();
        // 确保页面加载后自动显示视频流
        window.addEventListener('load', function() {
            setTimeout(updateUI, 100);
        });
        // 页面加载完成后立即显示视频流
        if (document.readyState === 'complete') {
            updateUI();
        } else {
            document.addEventListener('DOMContentLoaded', updateUI);
        }
        updateDetections();
        // 使用更短间隔，确保更新
        setInterval(refresh, 200);
        setInterval(updateDetections, 200);
    </script>
</body>
</html>
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_status(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(stats).encode())

    def set_stream(self, enable):
        global stream_enabled
        stream_enabled = enable
        stats['stream_enabled'] = enable
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'stream_enabled': stream_enabled}).encode())

    def send_stream(self):
        global stream_enabled
        if not stream_enabled:
            self.send_error(503)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()

        # 禁用TCP Nagle算法，减少延迟
        try:
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except:
            pass

        last_frame_id = 0
        frame_interval = 1.0 / 60  # 60FPS
        last_send_time = 0
        
        try:
            while True:
                if not stream_enabled:
                    break
                
                f = latest_frame
                now = time.time()
                
                # 关键：只发送比上次新的帧，且限制帧率
                # 如果f是None，或者和上次发送的是同一个对象，等待
                if f is None or id(f) == last_frame_id or (now - last_send_time < frame_interval):
                    time.sleep(0.001)
                    continue
                
                # 发送最新一帧
                last_frame_id = id(f)
                last_send_time = now
                
                # 发送帧
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + f + b'\r\n')
                # 立即flush确保不缓冲
                try:
                    self.wfile.flush()
                except:
                    pass
        except Exception as e:
            pass

    def log_message(self, format, *args):
        pass


def udp_thread():
    global latest_frame
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', UDP_PORT))
    sock.settimeout(0.1)
    print(f"[UDP] Listening on port {UDP_PORT}")

    frame_buffer = defaultdict(dict)

    global ESP32_IP
    while True:
        try:
            data, addr = sock.recvfrom(MAX_PAYLOAD)
            # 记录ESP32的IP地址用于发送命令
            if ESP32_IP is None:
                ESP32_IP = addr[0]
                print(f"[Info] ESP32 IP detected: {ESP32_IP}")
        except socket.timeout:
            continue

        if len(data) < 12:
            continue

        frame_id = struct.unpack('!I', data[:4])[0]
        packet_id = struct.unpack('!H', data[4:6])[0]
        total_packets = struct.unpack('!H', data[6:8])[0]
        frame_size = struct.unpack('!I', data[8:12])[0]
        packet_data = data[12:]

        stats['packets_received'] += 1
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
                    latest_frame = full_data
                    
                    # 添加到录像（仅在有新帧时添加）
                    add_frame_to_recorder(full_data)
                    
                    stats['frames_received'] += 1
                    stats['bytes_received'] += frame_size
                    
                    now = time.time()
                    frame_times.append((now, frame_size))
                    if len(frame_times) >= 10:
                        elapsed = frame_times[-1][0] - frame_times[0][0]
                        if elapsed > 0:
                            stats['fps'] = (len(frame_times) - 1) / elapsed
                            total_bytes = sum(t[1] for t in frame_times)
                            stats['bandwidth_mbps'] = (total_bytes * 8 / 1024 / 1024) / elapsed

            del frame_buffer[frame_id]


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """多线程HTTP服务器，允许同时处理视频流和统计请求"""
    daemon_threads = True


# ==================== 录像模块 ====================
recorder = None

def init_recorder():
    """初始化录像器"""
    global recorder
    try:
        recorder = get_recorder(
            video_dir="recordings",
            segment_duration=60,  # 1分钟一个分段
            max_storage_duration=3600,  # 总共保留1小时
            fps=15,
            resolution=(640, 480)
        )
        # 同步初始变换设置
        recorder.set_transform(_flip_h, _flip_v, _rotate)
        recorder.start()
        print("[Recorder] 循环录像已启动 (保留最近1小时, 每分钟一个分段)")
        print("[Recorder] 视频格式: MP4 + mp4v 编码")
        print(f"[Recorder] 初始变换: 水平翻转={_flip_h}, 垂直翻转={_flip_v}, 旋转={_rotate}°")
    except Exception as e:
        print(f"[Recorder] 启动失败: {e}")
        import traceback
        traceback.print_exc()

def add_frame_to_recorder(frame_data):
    """添加帧到录像器"""
    if recorder and frame_data:
        recorder.add_frame(frame_data)
# ====================================================


def main():
    print("=" * 50)
    print("  ycycam-udp Web Video Receiver + 循环录像")
    print("=" * 50)

    threading.Thread(target=udp_thread, daemon=True).start()
    
    # 启动物品识别线程
    if DETECTOR_ENABLED:
        start_detection()
    else:
        print(f"[Detector] 识别模块未启用")
    
    # 启动循环录像
    init_recorder()

    # 使用多线程服务器，视频流和统计请求互不阻塞
    server = ThreadedHTTPServer(('0.0.0.0', HTTP_PORT), MJPEGHandler)
    print(f"[HTTP] http://127.0.0.1:{HTTP_PORT}")
    print("=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        if recorder:
            recorder.stop()
        server.server_close()


if __name__ == "__main__":
    main()
