# ycycam-udp - ESP32-S3 UDP视频流系统 + AI实时检测
注：ycyserver中的yolov8m.pt模型须自行下载。

低延迟、高帧率的WiFi视频传输方案，专为ESP32-S3设计，集成 **YOLOv8m** 实时物体检测和人脸检测功能。

---

## ✨ 最新特性 (2026-05-09)

- 🚀 **模型升级**: 从 YOLOv8n 升级为 **YOLOv8m**，检测精度大幅提升
- 🔘 **检测开关**: 新增物体检测开关按钮，可随时开启/关闭，节省CPU
- 🎯 **显示优化**: 检测框文字不跟随视频翻转/旋转，始终保持正立显示
- 📺 **自动显示**: 修复页面加载时需要手动刷新才能显示视频流的问题
- 📸 **截图功能**: 一键保存带时间戳的照片到本地

---

## 📁 项目结构

```
ycycam-udp/
├── ESP32端（摄像头采集 + UDP发送）
│   ├── main/
│   │   ├── main.c            # 主程序 - 采集、编码、发送
│   │   ├── udp_stream.c      # UDP流核心实现
│   │   ├── udp_stream.h      # UDP流接口
│   │   ├── camera_driver.c   # OV5640摄像头驱动
│   │   ├── wifi_handler.c    # WiFi AP+STA管理
│   │   ├── http_server.c     # Web配置服务器
│   │   └── CMakeLists.txt
│   └── components/esp32-camera/  # 官方摄像头组件
│
└── server/ 服务器端（所有接收方案都在这里）
    ├── web_receiver.py     # ✨ Web接收端 + AI检测（主推荐）
    ├── receiver.py         # Python接收端 (OpenCV显示)
    ├── receiver_raw.py     # 原始数据接收端
    ├── receiver_gray.py    # 灰度图接收端
    ├── receiver.cpp        # C++高性能接收端
    ├── test_sender.py      # 测试发送器（无需硬件）
    ├── monitor.py          # UDP监控工具
    ├── detector.py         # 独立检测模块
    ├── video_recorder.py   # 循环录像模块
    ├── yolov8m.pt          # YOLOv8m 模型 (49.7MB)
    ├── yolov8n.pt          # YOLOv8n 模型 (6.2MB)
    ├── requirements.txt    # Python依赖
    ├── Dockerfile          # Docker容器化
    ├── README.md           # server目录说明
    └── README_VIDEO_RECORDER.md  # 录像功能说明
│
├── 工具脚本
│   ├── Makefile              # C++编译配置
│   ├── quick_start.sh        # 快速开始向导
│   ├── build.sh              # ESP32编译脚本
│   └── flash_and_monitor.sh  # ESP32烧录脚本
│
├── CHANGELOG.md              # 详细更新日志
└── README.md                 # 本文档
```

---

## 🚀 快速开始

### 方式一：Web接收端（推荐，功能最全）

```bash
cd server
python3 web_receiver.py
```

浏览器访问: **http://localhost:8000**

### 方式二：OpenCV接收端

```bash
cd server
python3 receiver.py
```

### 方式三：一键快速开始（ESP32）

```bash
./quick_start.sh
```

---

## 🎮 Web接收端使用说明 (web_receiver.py)

这是功能最全的接收端，支持浏览器查看和AI检测。

### 启动方式

```bash
cd server
source /home/dx1991/anaconda3/etc/profile.d/conda.sh
conda activate ycyserver
python3 web_receiver.py
```

### 界面功能

| 按钮 | 功能 |
|------|------|
| ↔️ 水平翻转 | 视频左右镜像 |
| ↕️ 垂直翻转 | 视频上下镜像 |
| 🔄 旋转90° | 顺时针旋转90度 |
| 🔄 重置 | 恢复原始方向 |
| 📸 拍照 | 保存当前帧到本地（带时间戳） |
| 🔍 检测开/关 | 物体检测开关（绿色=开启，灰色=关闭） |
| Stop Stream / Start Stream | 暂停/恢复视频流 |

### 实时统计

- **FPS**: 当前帧率（通常 30-40 fps）
- **Frames**: 累计接收帧数
- **Bandwidth**: 实时带宽（Mbps）
- **Resolution**: 视频分辨率（默认 640x480）

### API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web界面 |
| `/stream` | GET | MJPEG视频流 |
| `/status` | GET | 状态信息 (JSON) |
| `/detections` | GET | 检测结果 (JSON) |
| `/start` | GET | 开始视频流 |
| `/stop` | GET | 停止视频流 |
| `/set_transform` | GET | 设置翻转/旋转 |
| `/detection_on` | GET | 开启物体检测 |
| `/detection_off` | GET | 关闭物体检测 |

---

## 🔍 AI检测功能

### 物体检测 (YOLOv8m)

**检测类别** (12种常见物体):
- 👤 person (人)
- 📱 cell phone (手机)
- 💻 laptop (笔记本电脑)
- 🚗 car (汽车)
- 🍼 bottle (瓶子)
- ☕ cup (杯子)
- 🪑 chair (椅子)
- 🐕 dog (狗)
- 🐱 cat (猫)
- 📺 tv (电视)
- 🖱️ mouse (鼠标)
- ⌨️ keyboard (键盘)

**检测配置**:
- 模型: **YOLOv8m** (精度更高，推荐)
- 置信度阈值: 0.6
- IoU阈值: 0.3
- 检测间隔: 每 6 帧检测一次（降低CPU占用）
- 结果缓存: 1 秒（减少检测框抖动）

### 人脸检测

- 模型: OpenCV Haar Cascade Classifier
- 模型文件: `haarcascade_frontalface_default.xml`
- 检测参数: scale=1.2, minNeighbors=5

---

## 📊 功能对比

| 功能 | Python (OpenCV) | C++ | Web (浏览器) |
|------|----------------|-----|-------------|
| 实时显示 | ✅ OpenCV | ✅ OpenCV | ✅ MJPEG |
| FPS统计 | ✅ | ✅ | ✅ |
| 带宽统计 | ✅ | ✅ | ✅ |
| 丢帧率统计 | ✅ | ✅ | ✅ |
| 视频录制 | ✅ MP4 | ❌ | ❌ |
| 帧保存 | ✅ | ❌ | ✅ 一键截图 |
| 无头模式 | ✅ | ✅ | ❌ |
| 命令行参数 | ✅ | ✅ | ❌ |
| **YOLOv8m物体检测** | ❌ | ❌ | ✅ |
| **人脸检测** | ❌ | ❌ | ✅ |
| 视频翻转 | ❌ | ❌ | ✅ 水平/垂直 |
| 视频旋转 | ❌ | ❌ | ✅ 90° |
| 流控制 | ❌ | ❌ | ✅ 开始/停止 |
| 检测开关 | ❌ | ❌ | ✅ 开关按钮 |

---

## 🎯 ESP32发送端功能

| 功能 | 说明 |
|------|------|
| 视频采集 | OV5640摄像头，支持QVGA~SVGA |
| JPEG编码 | 硬件编码，低CPU占用 |
| UDP传输 | 广播/单播，MTU自动分包 |
| 帧同步 | 帧序号 + 包序号，接收端重组 |
| WiFi模式 | AP+STA同时工作 |
| Web配置 | 网页配置WiFi和UDP目标 |
| 状态显示 | 实时FPS、带宽统计 |

### 编译烧录ESP32固件

```bash
# 激活ESP-IDF环境
. ~/esp-idf/export.sh

# 编译
idf.py build

# 烧录并监控
idf.py -p /dev/ttyUSB0 flash monitor
```

### 配置ESP32

1. 连接WiFi热点 `ycycam` (密码: `12345678`)
2. 访问 `http://192.168.4.1`
3. 配置STA WiFi（让ESP32连接你的局域网）
4. 可选：配置UDP目标IP（不配置则使用广播模式）

---

## 📡 UDP协议细节

### 数据包格式

每个UDP包 = 12字节头部 + JPEG数据

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         Frame ID (32位)                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|        Packet ID (16位)       |     Total Packets (16位)      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Frame Size (32位)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
|                       JPEG Data (可变)                        |
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

- **Frame ID**: 递增的帧序号，用于帧同步和丢帧检测
- **Packet ID**: 当前帧内的包序号 (0 ~ Total-1)
- **Total Packets**: 当前帧的总包数
- **Frame Size**: 完整JPEG帧的字节大小

### 性能参数

| 分辨率 | 典型帧大小 | 每帧UDP包数 | 目标FPS | 估算带宽 |
|--------|-----------|------------|---------|---------|
| QVGA (320x240) | ~10 KB | 8包 | 30 fps | ~2.4 Mbps |
| HVGA (480x320) | ~20 KB | 15包 | 30 fps | ~4.8 Mbps |
| VGA (640x480) | ~40 KB | 29包 | 20 fps | ~6.4 Mbps |
| SVGA (800x600) | ~70 KB | 51包 | 15 fps | ~8.4 Mbps |

### 延迟测试

| 方案 | 典型延迟 | 说明 |
|------|---------|------|
| UDP广播 | < 50 ms | 局域网内 |
| HTTP MJPEG | ~200 ms | TCP握手+重传开销 |

---

## 🌐 网络配置

### 模式一：广播模式（默认）

ESP32发送到 `255.255.255.255:5000`，同一局域网内所有设备都能接收。

- ✅ 优点：无需配置，多客户端同时接收
- ⚠️ 缺点：路由器可能限制广播带宽

### 模式二：单播模式

在Web配置页设置接收端的IP地址，ESP32直接发送到该IP。

- ✅ 优点：带宽更高，网络干扰小
- ⚠️ 缺点：需要提前配置IP，只支持单客户端

### 端口说明

- **UDP 5000**: 视频流接收端口
- **TCP 8000**: Web界面和MJPEG流端口

---

## 🔧 Python依赖

```bash
pip install opencv-python numpy ultralytics
```

或使用 requirements.txt:

```bash
cd server
pip install -r requirements.txt
```

---

## 🐳 Docker支持

```bash
cd server

# 构建镜像
docker build -t ycycam-udp .

# 运行容器
docker-compose up -d

# 或直接运行
docker run -p 8000:8000 -p 5000:5000/udp ycycam-udp
```

---

## 📝 更新日志

详细更新记录请查看 [CHANGELOG.md](./CHANGELOG.md)

---

## 🎉 当前状态

- ✅ UDP 服务: 端口 5000 监听中
- ✅ HTTP 服务: 端口 8000 监听中
- ✅ YOLOv8m 模型: 已加载 (49.7MB)
- ✅ 人脸检测: 已启用
- ✅ 检测开关功能: 已实现
- ✅ 视频流自动显示: 已修复
- ✅ 检测框文字正立: 已实现

---

## 📄 相关文档

- [server/README.md](./server/README.md) - Server目录详细说明
- [CHANGELOG.md](./CHANGELOG.md) - 完整更新日志

---

**项目维护者**: ycycam 团队
**最后更新**: 2026-05-09
