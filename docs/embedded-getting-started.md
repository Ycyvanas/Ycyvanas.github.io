# 🌳 Agent 时代的嵌入式开发入门

> 扶桑 · 神木成林 · 智能物联网开发指南

---

## 📋 目录

1. [开发全流程：编译→烧录→监测](#1-开发全流程编译烧录监测)
2. [开发板纵览](#2-开发板纵览)
3. [传感器速查](#3-传感器速查)
4. [通讯协议图谱](#4-通讯协议图谱)
5. [调试工具链](#5-调试工具链)
6. [端侧 AI / TinyML 入门](#6-端侧-ai--tinyml-入门)
7. [AI Agent 辅助开发](#7-ai-agent-辅助开发)
8. [版本管理与 CI/CD](#8-版本管理与-cicd)
9. [推荐学习路径](#9-推荐学习路径)

---

## 1. 开发全流程：编译→烧录→监测

### 1.1 STC89C52（经典 51）

| 步骤 | 工具 | 说明 |
|------|------|------|
| 编译 | Keil C51 / SDCC | 推荐 Keil μVision 或开源 SDCC |
| 烧录 | STC-ISP (Windows) | 串口下载，需冷启动（断电→上电） |
| 监测 | 串口助手 (SSCOM/Putty) | 波特率通常 9600/115200，通过 UART 输出调试信息 |

**典型命令（SDCC 编译链）：**
```bash
sdcc main.c
packihx main.ihx > main.hex
# 再用 STC-ISP 烧录
```

### 1.2 STM32F103（ARM Cortex-M3）

| 步骤 | 工具 | 说明 |
|------|------|------|
| 编译 | ARM GCC / Keil MDK / STM32CubeIDE | 推荐 ARM GCC + Makefile / STM32CubeIDE |
| 烧录 | OpenOCD + ST-Link / J-Link | SWD 接口，4 线（SWDIO, SWCLK, GND, 3.3V） |
| 监测 | OpenOCD 终端 / 串口输出 | HAL 库 `printf` 重定向到 UART / ITM 数据跟踪 |

**快速上手：**
```bash
# 编译
arm-none-eabi-gcc -c main.c -o main.o
# 烧录（ST-Link）
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg -c "program build/firmware.hex verify reset exit"
# 或使用 STM32CubeProgrammer GUI
```

### 1.3 ESP32-S3（WiFi/BLE SoC）

| 步骤 | 工具 | 说明 |
|------|------|------|
| 编译 | ESP-IDF / Arduino-ESP32 / PlatformIO | 推荐 ESP-IDF v5.x + CMake |
| 烧录 | esptool.py / ESP-IDF 内建 | USB-UART 自动下载，无需冷启动 |
| 监测 | idf.py monitor / minicom / screen | 默认波特率 115200，支持日志分级 |

**快速上手：**
```bash
# 安装 ESP-IDF
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3 && . ./export.sh

# 创建项目
idf.py create-project my_project
cd my_project
idf.py set-target esp32s3
idf.py menuconfig    # 配置
idf.py build         # 编译
idf.py -p /dev/ttyUSB0 flash   # 烧录
idf.py -p /dev/ttyUSB0 monitor  # 监测
```

### 1.4 Luckfox-Pico（微型 Linux）

| 步骤 | 工具 | 说明 |
|------|------|------|
| 编译 | 交叉编译链 (arm-linux-gnueabihf-gcc) | SDK 内建 buildroot 系统 |
| 烧录 | SDK 烧录脚本 / USB 烧录模式 | 按住 BOOT 键上电进入烧录模式 |
| 监测 | SSH / 串口终端 | 板载 UART 调试串口，波特率 115200 |

### 1.5 A7-Lite（全志 A7 核心板）

| 步骤 | 工具 | 说明 |
|------|------|------|
| 编译 | Buildroot / Yocto / 交叉编译 | 生成完整 Linux 根文件系统 |
| 烧录 | PhoenixCard / fastboot / dd | SD 卡烧录或 NAND Flash 写入 |
| 监测 | SSH / 串口 / ADB | Linux 标准调试手段 |

---

## 2. 开发板纵览

### 对比矩阵

| 开发板 | 架构 | 主频 | RAM | 存储 | 网络 | 定位 |
|--------|------|------|-----|------|------|------|
| STC89C52 | 8051 | 12MHz | 512B | 8KB Flash | ✗ | 基础入门、教学 |
| STM32F103 | Cortex-M3 | 72MHz | 20-64KB | 64-256KB Flash | ✗ | 工业控制、传感器采集 |
| RP2040 | Cortex-M0+×2 | 133MHz | 264KB | 2MB Flash | ✗ | 灵活外设、PIO、低成本 |
| ESP32-S3 | Xtensa LX7×2 | 240MHz | 512KB | 16MB Flash | WiFi 4 + BLE 5 | AIoT 边缘智能、无线 |
| Luckfox-Pico | ARM Cortex-A7 | 1.2GHz | 256MB DDR | 16MB SPI Flash + TF | 百兆以太网 | 微型 Linux、轻量边缘计算 |
| Xilinx Artix7 | FPGA | - | - | - | - | 硬件可编程逻辑、高速信号 |
| A7-Lite | ARM Cortex-A7 | 1.2GHz | 512MB DDR3 | 8GB eMMC | 百兆以太网 | Linux 应用、全方位 AIoT 网关 |

### 选型建议

- **入门学习** → STC89C52 → STM32F103（循序渐进理解 MCU 架构）
- **日常外设实验** → RP2040（PIO 独一无二，性价比高）
- **无线 IoT 项目** → ESP32-S3（生态最完善，支持 ESP-NOW/MQTT/HTTP）
- **Linux 边缘计算** → Luckfox-Pico → A7-Lite（从微 Linux 到完整 Linux）
- **高速/并行/定制逻辑** → Xilinx Artix7（FPGA，适合图像处理、高速 ADC）
- **生产级 AIoT 网关** → A7-Lite（全功能 Linux + 丰富外设接口）

---

## 3. 传感器速查

[📄 完整传感器手册 →](sensors.md)（已驱动 40+ 种传感器）

### 传感器分类

| 类别 | 代表传感器 | 主要接口 |
|------|-----------|----------|
| 🌡️ 环境感知 | DHT11、DS18B20、光敏电阻、火焰传感器 | GPIO / 1-Wire |
| 📐 运动与姿态 | MPU6050、HC-SR04、红外避障 | I2C / GPIO |
| 🎮 人机交互 | 按键、旋转编码器、摇杆、触摸、红外遥控 | GPIO / ADC / I2C |
| ⚡ 执行与指示 | 蜂鸣器、LED、激光、继电器 | GPIO / PWM |
| 🧲 磁场与霍尔 | SS49E、A3144、霍尔开关模块 | GPIO / 模拟 |
| 💾 存储与时钟 | SD/TF 卡模块、DS1302 RTC | SPI / GPIO |

---

## 4. 通讯协议图谱

### 4.1 板级通讯（芯片间/模块间）

| 协议 | 速度 | 引脚数 | 特点 | 适用场景 |
|------|------|--------|------|----------|
| **UART** | 最高数 Mbps | 2 (TX, RX) | 异步、全双工、点对点 | 调试输出、GPS/蓝牙模块、串口屏 |
| **I2C** | 100/400 kHz~3.4 MHz | 2 (SDA, SCL) | 同步、多主多从、地址寻址 | 传感器(MPU6050)、OLED、RTC(DS3231) |
| **SPI** | 最高数十 MHz | 4 (CS, SCK, MOSI, MISO) | 同步、全双工、主从、高速 | SD/TF卡、显示屏、Flash芯片、ADC |
| **1-Wire** | ~16 kbps | 1 (DQ) | 半双工、寄生供电 | DS18B20温度传感器、iButton |
| **I2S** | 标准音频速率 | 3~5 (BCK, WS, DATA) | 数字音频总线 | 数字麦克风(INMP441)、音频DAC/ADC |

### 4.2 网络级通讯（设备间/云端）

| 协议 | 频段/介质 | 传输距离 | 功耗 | 数据速率 | 适用场景 |
|------|-----------|----------|------|---------|----------|
| **WiFi** | 2.4/5 GHz | ~100m | 中高 | 最高数百 Mbps | 摄像头传输、云端连接、OTA |
| **BLE** | 2.4 GHz | ~100m | 低 | 1~2 Mbps | 传感器数据采集、手机互联 |
| **LoRa** | 868/915 MHz | 2~15 km | 极低 | 0.3~50 kbps | 远距离传感器网络、农业/环境监测 |
| **Zigbee** | 2.4 GHz | ~100m | 极低 | 250 kbps | 智能家居、Mesh网络 |
| **ESP-NOW** | 2.4 GHz | ~200m | 极低 | 最高 1 Mbps | ESP32间快速通信、无需WiFi AP |
| **Ethernet** | 有线 | 100m | 无 | 10/100 Mbps | 网关、Linux开发板首选 |

### 4.3 Agent 时代的新维度：协议即 API

在 Agent 时代，通讯协议的边界在模糊化：

- **MQTT**：物联网标准的发布/订阅协议，天然适合 Agent 事件驱动架构
- **HTTP/REST**：Agent 与云端交互的标准语言
- **WebSocket**：Agent 需要实时双向通讯时的最佳选择
- **gRPC**：高性能微服务间通讯，适合 Agent 内部模块调用
- **protobuf/FlatBuffers**：高效序列化格式，Agent 间结构化的数据传输

**实战建议**：从 ESP32+MQTT 入手，连接 Agent 与物理世界，这是 AIoT 最典型的入口。

---

## 5. 调试工具链

> 调试是嵌入式开发中最费时但也最重要的能力。

### 5.1 硬件调试工具

| 工具 | 用途 | 推荐型号 |
|------|------|---------|
| **逻辑分析仪** | 抓取数字信号时序（UART/I2C/SPI） | Saleae Logic 8/16, DSLogic |
| **示波器** | 模拟/数字信号波形分析 | 普源 DS1054Z, Hantek |
| **JTAG/SWD 调试器** | MCU 单步调试、断点、寄存器查看 | ST-Link V2, J-Link EDU, DAPLink |
| **USB 转串口模块** | UART 调试输出 | CH340G, CP2102, FT232 |
| **万用表** | 电压/电流/通断测量 | 任意品牌（优利德/胜利） |

### 5.2 软件调试工具

| 工具 | 用途 |
|------|------|
| **OpenOCD** | 开源调试器（JTAG/SWD 桥接 GDB） |
| **GDB (arm-none-eabi-gdb)** | 源代码级调试 |
| **STM32CubeMonitor** | STM32 运行时变量监测 |
| **ESP-IDF Monitor** | ESP32 日志+GDB 一站式终端 |
| **Wireshark** | 抓包分析（WiFi/BLE/以太网协议） |
| **Bus Pirate** | 通用总线调试神器（I2C/SPI/1-Wire/UART 等） |

### 5.3 调试黄金法则

1. **先硬件后软件**：电压量了 -> 时钟看了 -> 再查代码
2. **善用 LED/串口 **：没有调试器的时候，LED 闪烁和串口 printf 是最可靠的
3. **逻辑分析仪是你的眼睛**：通讯问题九成可以用逻辑分析仪一眼看穿
4. **分而治之**：断开所有外设，逐外设调试，确认一个再接一个

---

## 6. 端侧 AI / TinyML 入门

Agent 时代，MCU 上跑 AI 不再是幻想。

### 6.1 端侧推理框架对比

| 框架 | 支持硬件 | 模型格式 | 内存需求 | 难度 |
|------|---------|---------|---------|------|
| **TensorFlow Lite Micro** | ARM Cortex-M, ESP32, RP2040 | TFLite | ~16 KB RAM | ⭐⭐ |
| **ESP-DL** | ESP32-S3 (支持向量指令) | TensorFlow/PyTorch | ~384 KB RAM | ⭐⭐⭐ |
| **CMSIS-NN** | ARM Cortex-M4/M7/M33 | 优化算子库 | 与TFLite配合 | ⭐⭐⭐ |
| **EloquentTinyML** | 通用 MCU | TFLite | 极小 | ⭐ |
| **Edge Impulse** | 多平台 | 自研 | 依硬件 | ⭐（有GUI） |

### 6.2 推荐实践路径

1. **入门**：在 PC 上训练一个小模型（手势识别/关键词唤醒）
2. **转换**：用 TFLite Converter 转为 `.tflite` 并量化（int8）
3. **部署**：TFLite Micro 推理引擎 + ESP32-S3 或 STM32F4
4. **优化**：利用 ESP-DL 或 CMSIS-NN 加速推理
5. **端到端**：传感器采集 → 端侧推理 → WiFi/BLE 上报 Agent

### 6.3 Agent 时代的 AIoT 推理模式

```
传感器 → [MCU推理] → 本地决策（低延迟、不联网）
                ↓ (仅关键事件/抽象结果)
         [Agent服务] → 云端大模型 → 深度分析 → 反馈
```

- **端侧**：做轻量推理（唤醒词、异常检测、分类）
- **云端/Agent**：做复杂推理（语义理解、多模态分析、策略规划）
- **关键**：端侧只传"语义"不传"原始数据"，带宽省了，隐私也保了

---

## 7. AI Agent 辅助开发

Agent 时代，嵌入式开发者的工作流正在被重塑。

### 7.1 代码生成与补全

| 场景 | 典型 Prompt |
|------|------------|
| 外设驱动 | "生成 STM32F103 基于 HAL 库的 MPU6050 I2C 驱动代码" |
| 协议实现 | "写一个 ESP32 的 MQTT 发布客户端，连接 emqx 服务器" |
| 算法移植 | "把这段 Python 的卡尔曼滤波移植为 C 语言，适配 STM32" |
| 调试诊断 | "我的 I2C 一直 NACK，可能的原因有哪些？" |

### 7.2 自动化测试与验证

- Agent 生成单元测试用例，固化到 CI 流水线
- 用 Agent 分析逻辑分析仪抓取的时序，自动匹配协议
- Agent 辅助生成设备树、Kconfig 配置、CMakeLists.txt

### 7.3 文档自动生成

- 根据代码注释 + 硬件引脚定义，Agent 自动生成文档
- pinmap 可视化、传感器接线图 Markdown 版

### 7.4 DIY：给扶桑添加 Agent 能力

```
扶桑 Agent（嵌入式助手）
├── 📚 开发板知识图谱（各芯片 Datasheet 索引）
├── 🔧 代码生成器（根据需求生成驱动模板）
├── 🧪 调试诊断（常见问题库+排查流程）
└── 📖 传感器库自然语言查询（"有哪些 I2C 温湿度传感器？"）
```

---

## 8. 版本管理与 CI/CD

### 8.1 代码管理

```bash
# 推荐结构
my_embedded_project/
├── firmware/           # 固件源码
│   ├── src/            # 源代码
│   ├── inc/            # 头文件
│   └── test/           # 测试代码
├── hardware/           # 硬件原理图、PCB、BOM
├── docs/               # 文档
├── scripts/           # 编译/烧录/测试脚本
├── .github/           # CI 配置
└── README.md
```

### 8.2 GitHub Actions 自动化

```yaml
# .github/workflows/build.yml（示例）
name: Firmware Build
on: [push, pull_request]
jobs:
  build-stm32:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install ARM GCC
        run: sudo apt install gcc-arm-none-eabi
      - name: Build
        run: cd firmware && make all
  build-esp32:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build ESP32
        uses: espressif/gh-actions@main
        with:
          esp_idf_version: v5.2
          target: esp32s3
          path: './firmware/esp32/'
```

### 8.3 自动化烧录测试（有硬件条件时）

- **Jenkins + 烧录架**：自动烧录 + 上电自检
- **Pytest + pyserial**：对固件进行自动化黑盒测试
- **GitHub Actions + 自建 Runner**：连接本地硬件做实际烧录验证

---

## 9. 推荐学习路径

### 🎯 目标：从零到 AIoT 全栈

```
第一阶段 · 基本功（1~2 个月）
├── 👣 C语言基础 + 指针/位运算/结构体
├── 👣 数字电路基础（高低电平、上拉下拉、中断、定时器）
├── 👣 STC89C52 跑马灯→按键→中断→定时器→数码管
└── 👣 用逻辑分析仪看 UART 波形

第二阶段 · ARM 与 RTOS（2~3 个月）
├── 📚 STM32F103：GPIO→中断→定时器→ADC→DMA→I2C→SPI
├── 📚 FreeRTOS：任务/队列/信号量/互斥量
├── 📚 使用 HAL 库 + CubeMX 生成工程
└── 📚 学会用 OpenOCD + GDB 调试

第三阶段 · 无线互联（1~2 个月）
├── 🛜 ESP32-S3：WiFi 扫描→HTTP→MQTT→BLE
├── 🛜 ESP-NOW 快速组网
├── 🛜 数据上报 MQTT Broker → 可视化
└── 🛜 OTA 固件升级

第四阶段 · Agent 时代（持续）
├── 🤖 端侧推理：TFLite Micro + 传感器数据分类
├── 🤖 Agent 辅助开发：代码生成 + 调试诊断
├── 🤖 全端打通：传感器→MCU推理→Agent分析→云反馈
└── 🤖 持续集成：GitHub Actions 自动编译+测试
```

### 📚 推荐资源

| 资源 | 类型 | 说明 |
|------|------|------|
| [ESP-IDF 编程指南](https://docs.espressif.com/projects/esp-idf/zh_CN/latest/) | 官方文档 | ESP32 开发权威指南 |
| [STM32Cube 生态](https://www.st.com.cn/ecosystems/stm32cube) | 官方工具链 | HAL 库 + CubeMX + CubeProgrammer |
| [TinyML 官方书](https://tinymlbook.com/) | 书籍 | 嵌入式机器学习的经典入门 |
| [FreeRTOS 官方文档](https://www.freertos.org/) | 文档 | 最流行的 MCU RTOS |
| [嵌入式编译器基础 (GCC)](https://gcc.gnu.org/onlinedocs/gcc/ARM-Options.html) | 文档 | ARM GCC 选项详解 |
| [Colab Training + TFLite Micro](https://colab.research.google.com/) | 在线工具 | 免费 GPU 训练，转 TFLite 部署 |
| [Logic 2 (Saleae)](https://www.saleae.com/downloads/) | 软件 | 逻辑分析仪上位机 |
| [Wokwi 在线仿真](https://wokwi.com/) | 在线工具 | ESP32/STM32/Arduino 在线模拟 |

---

> **扶桑寄语**：Embedding 开发从不是捷径，但 Agent 时代让它不再是孤军奋战。Compiler→Flashing→Monitor 是基本功，开发板与传感器是武器库，通讯协议是经脉，而 AI Agent 是外挂的大脑。愿你神木成林，枝繁叶茂。🌳
