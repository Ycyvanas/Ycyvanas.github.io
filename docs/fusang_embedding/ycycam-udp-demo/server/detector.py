#!/usr/bin/env python3
"""
ycycam-udp 物品/人脸检测模块
独立线程运行，不阻塞视频流
"""
import time
import threading
from collections import deque
import numpy as np
import cv2

# 全局配置
ENABLE_OBJECT_DETECTION = True   # 物品识别开关
ENABLE_FACE_DETECTION = True     # ✅ 人脸识别开关已启用
DETECTION_FPS = 10               # 识别帧率

# 全局识别结果
_detection_lock = threading.Lock()
_latest_detections = {
    "timestamp": 0,
    "objects": [],
    "faces": []
}

# 全局变量
_latest_frame = None
_model = None
_face_cascade = None
_running = False


def init_model():
    """初始化模型（懒加载）"""
    global _model, _face_cascade, ENABLE_OBJECT_DETECTION
    
    if ENABLE_OBJECT_DETECTION and _model is None:
        try:
            from ultralytics import YOLO
            print("[Detector] 加载 YOLOv8n 物品检测模型...")
            _model = YOLO('yolov8n.pt')  # 轻量模型，仅3.8MB
            print("[Detector] YOLOv8n 模型加载完成")
        except Exception as e:
            print(f"[Detector] YOLO加载失败: {e}")
            print("[Detector] 物品识别已禁用")
            ENABLE_OBJECT_DETECTION = False
    
    if ENABLE_FACE_DETECTION and _face_cascade is None:
        try:
            print("[Detector] 加载人脸检测模型...")
            _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            print("[Detector] 人脸检测模型加载完成")
        except Exception as e:
            print(f"[Detector] 人脸检测加载失败: {e}")


def update_frame(frame):
    """更新最新帧（由web_receiver.py调用）"""
    global _latest_frame
    _latest_frame = frame


def get_latest_detections():
    """获取最新识别结果"""
    with _detection_lock:
        return _latest_detections.copy()


def detection_thread():
    """独立识别线程"""
    global _running, _latest_detections
    
    if _running:
        return
    
    _running = True
    init_model()
    
    frame_count = 0
    last_time = time.time()
    
    print(f"[Detector] 识别线程已启动 (目标FPS: {DETECTION_FPS})")
    
    while _running:
        try:
            now = time.time()
            
            # 控制识别帧率
            frame_interval = 1.0 / DETECTION_FPS
            if now - last_time < frame_interval:
                time.sleep(0.001)
                continue
            
            f = _latest_frame
            if f is None:
                time.sleep(0.01)
                continue
            
            last_time = now
            frame_count += 1
            
            # JPEG转numpy
            nparr = np.frombuffer(f, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            
            results = {
                "timestamp": now,
                "objects": [],
                "faces": []
            }
            
            # YOLO物品识别
            if ENABLE_OBJECT_DETECTION and _model is not None:
                try:
                    # 识别（速度优先，缩小图片）
                    outputs = _model(img, verbose=False, conf=0.4, iou=0.45)
                    
                    for r in outputs:
                        for box in r.boxes:
                            x1, y1, x2, y2 = map(float, box.xyxy[0])
                            cls_id = int(box.cls[0])
                            conf = float(box.conf[0])
                            
                            results["objects"].append({
                                "label": _model.names[cls_id],
                                "confidence": round(conf, 3),
                                "box": [round(x1, 1), round(y1, 1), round(x2-x1, 1), round(y2-y1, 1)]
                            })
                except Exception as e:
                    pass
            
            # 人脸检测
            if ENABLE_FACE_DETECTION and _face_cascade is not None:
                try:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    faces = _face_cascade.detectMultiScale(gray, 1.1, 4)
                    for (x, y, w, h) in faces:
                        results["faces"].append({
                            "label": "face",
                            "confidence": 1.0,
                            "box": [float(x), float(y), float(w), float(h)]
                        })
                except Exception as e:
                    pass
            
            # 更新结果
            with _detection_lock:
                _latest_detections = results
                
        except Exception as e:
            print(f"[Detector] 识别异常: {e}")
            time.sleep(0.1)


def start():
    """启动识别线程"""
    if not ENABLE_OBJECT_DETECTION and not ENABLE_FACE_DETECTION:
        print("[Detector] 所有识别功能已禁用")
        return
    
    t = threading.Thread(target=detection_thread, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # 测试用
    start()
    while True:
        time.sleep(1)
        det = get_latest_detections()
        print(f"检测到 {len(det['objects'])} 个物品")
