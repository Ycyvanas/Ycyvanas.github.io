# ycycam-udp Server - 接收端说明

本目录包含多种接收端实现，用于接收ESP32发送的UDP视频流。

---

## 📁 文件说明

| 文件 | 说明 | 推荐度 |
|------|------|--------|
| **web_receiver.py** | ✨ Web接收端 + AI实时检测 + 循环录像，功能最全 | ⭐⭐⭐⭐⭐ |
| **video_recorder.py** | 循环录像模块（MP4格式，自动保留最近1小时） | 模块 |
| **detector.py** | 独立的AI检测模块（YOLO + 人脸检测） | 模块 |
| **receiver.py** | 传统 OpenCV 显示接收端 | ⭐⭐⭐ |
| **receiver_raw.py** | 原始帧接收（无显示） | 调试用 |
| **receiver_gray.py** | 灰度显示接收端 | 优化性能 |
| **receiver.cpp** | C++高性能接收端（需编译） | 性能优先 |
| **debug_receiver.py** | 调试用接收端（详细日志） | 调试用 |
| **simple_test.py** | 最简单的测试接收端 | 测试用 |
| **test_sender.py** | 测试发送器（模拟ESP32发送，无需硬件） | 测试用 |
| **monitor.py** | UDP端口监控工具 | 调试用 |
| **yolov8m.pt** | YOLOv8m 模型文件 (49.7MB) | 精度优先 |
| **yolov8n.pt** | YOLOv8n 模型文件 (6.2MB) | 速度优先 |
| **requirements.txt** | Python依赖列表 | |
| **Dockerfile** | Docker容器化配置 | |
| **docker-compose.yml** | Docker Compose配置 | |
| **docker.sh** | Docker部署脚本 | |
| **start.sh** | 启动脚本 | |
| **README_VIDEO_RECORDER.md** | 循环录像功能详细说明 | 文档 |

---

## 🚀 快速启动

### Web接收端（推荐）

```bash
python3 web_receiver.py
```

浏览器访问: **http://localhost:8000**

### OpenCV接收端

```bash
python3 receiver.py
```

**快捷键:**
- `ESC` / `q` - 退出
- `空格` - 暂停/继续
- `s` - 保存当前帧
- `r` - 开始/停止录制

---

## 🎮 web_receiver.py 功能详解

### 核心功能

1. **MJPEG 视频流** - 浏览器直接查看，无需插件
2. **YOLOv8m 实时物体检测** - 12种常见物体识别
3. **人脸检测** - OpenCV Haar Cascade 算法
4. **视频变换控制** - 水平翻转、垂直翻转、旋转90°
5. **一键截图** - 保存带时间戳的照片
6. **流控制** - 开始/停止视频流
7. **检测开关** - 可随时开启/关闭AI检测，节省CPU
8. **实时统计** - FPS、帧数、带宽显示

### 检测框显示特性

✅ **检测框和文字不跟随视频翻转/旋转，始终保持正立显示**

后端检测时会应用与前端一致的图像变换，返回的坐标是变换后的正确位置，因此前端检测框和标签始终保持正常方向，易于阅读。

### 浏览器兼容性

- Chrome / Edge: ✅ 完美支持
- Firefox: ✅ 完美支持
- Safari: ✅ 支持
- 移动端浏览器: ✅ 支持

---

## 🔍 检测模块 (detector.py)

独立的检测模块，可单独使用或集成到其他项目中。

### 单独使用

```python
from detector import start, update_frame, get_latest_detections

# 启动检测线程
start()

# 循环更新帧
while True:
    # 更新最新帧（JPEG二进制数据）
    update_frame(jpeg_data)
    
    # 获取检测结果
    results = get_latest_detections()
    print(f"检测到 {len(results['objects'])} 个物体")
    print(f"检测到 {len(results['faces'])} 个人脸")
```

### 配置参数

```python
ENABLE_OBJECT_DETECTION = True   # 物品识别开关
ENABLE_FACE_DETECTION = True     # 人脸识别开关
DETECTION_FPS = 10               # 识别帧率（控制CPU占用）
```

---

## 📊 性能对比

### 模型对比

| 模型 | 大小 | 精度 | 速度 | CPU占用 | 适用场景 |
|------|------|------|------|---------|---------|
| YOLOv8m | 49.7MB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 中高 | 精度优先，PC端 |
| YOLOv8n | 6.2MB | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 低 | 速度优先，嵌入式 |

### 切换模型

在 `web_receiver.py` 中修改:

```python
# 从 YOLOv8m (当前)
_model = YOLO('yolov8m.pt')

# 切换为 YOLOv8n
_model = YOLO('yolov8n.pt')
```

---

## 🐳 Docker部署

### 方式一：Docker Compose（推荐）

```bash
cd server
docker-compose up -d
```

### 方式二：手动构建运行

```bash
# 构建镜像
docker build -t ycycam-udp .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -p 5000:5000/udp \
  --name ycycam-server \
  ycycam-udp

# 查看日志
docker logs -f ycycam-server

# 停止容器
docker stop ycycam-server
```

### Docker 脚本

```bash
./docker.sh build   # 构建镜像
./docker.sh run     # 运行容器
./docker.sh stop    # 停止容器
./docker.sh logs    # 查看日志
```

---

## 🔧 Python依赖安装

```bash
# 使用 requirements.txt
pip install -r requirements.txt

# 或手动安装
pip install opencv-python numpy ultralytics
```

### Conda环境（推荐）

```bash
source /home/dx1991/anaconda3/etc/profile.d/conda.sh
conda activate ycyserver
python3 web_receiver.py
```

---

## 📡 端口说明

| 端口 | 协议 | 说明 |
|------|------|------|
| 5000 | UDP | 视频流接收端口 |
| 8000 | TCP | Web界面 + MJPEG流 |

---

## 🎯 使用场景

### 场景1：家庭监控

- ESP32摄像头放置在需要监控的位置
- PC运行 `web_receiver.py`
- 手机/平板通过浏览器查看实时画面和检测结果

### 场景2：机器人视觉

- ESP32安装在机器人上
- 上位机运行检测程序
- 检测结果通过API获取，用于机器人决策

### 场景3：人数统计

- 利用 person 类别检测
- 统计画面中的人数
- 可用于客流统计、人数超限告警等

### 场景4：物品识别演示

- 支持12种常见物品识别
- 适合AI教学演示
- 可扩展训练自定义模型

---

## 🔍 API接口说明

### 获取检测结果

```
GET /detections
```

响应示例:
```json
{
  "timestamp": 1715274000.123,
  "enabled": true,
  "objects": [
    {
      "label": "person",
      "confidence": 0.892,
      "box": [100.5, 50.2, 80.3, 120.7]
    }
  ],
  "faces": [
    {
      "label": "face",
      "confidence": 0.95,
      "box": [200.0, 100.0, 60.0, 60.0]
    }
  ]
}
```

### 获取状态

```
GET /status
```

响应示例:
```json
{
  "fps": 35.2,
  "frames_received": 12345,
  "bytes_received": 52345678,
  "bandwidth_mbps": 4.2,
  "stream_enabled": true
}
```

---

## 🐛 故障排查

### 问题1：看不到视频流

**检查项:**
1. ESP32和PC是否在同一局域网
2. ESP32是否正常启动（查看串口日志）
3. 防火墙是否开放UDP 5000端口
4. 访问 http://localhost:8000/status 查看是否有数据

### 问题2：检测框不显示

**检查项:**
1. 查看浏览器控制台是否有报错
2. 确认检测开关是否开启（绿色=开启）
3. 访问 http://localhost:8000/detections 查看检测结果

### 问题3：CPU占用过高

**解决方法:**
1. 关闭不需要的检测功能（点击检测开关）
2. 降低检测帧率（修改 `DETECTION_FPS` 参数）
3. 从 YOLOv8m 切换为 YOLOv8n

### 问题4：视频延迟高

**解决方法:**
1. 确保WiFi信号良好
2. 降低视频分辨率
3. 使用单播模式替代广播模式

---

## 📝 更新日志

### 2026-05-09
- ✅ YOLO模型从 v8n 升级为 v8m，检测精度大幅提升
- ✅ 新增检测开关按钮，可随时开启/关闭
- ✅ 检测框文字不跟随翻转旋转，始终正立
- ✅ 修复页面加载时需要手动刷新的问题
- ✅ 优化截图功能，添加时间戳水印

---

## 🎉 运行状态

当前服务默认使用 YOLOv8m 模型，支持所有检测功能。

启动后服务状态:
- 🟢 UDP 端口 5000: 监听中
- 🟢 HTTP 端口 8000: 监听中
- 🟢 YOLOv8m 模型: 已加载
- 🟢 人脸检测: 已启用
- 🟢 检测开关: 已启用（可随时关闭）
