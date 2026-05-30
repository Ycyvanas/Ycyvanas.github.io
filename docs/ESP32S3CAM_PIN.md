# ESP32-S3-CAM 官方引脚说明整理

为了方便查阅，引脚分为 **左侧排针** 和 **右侧排针** 两部分，并附带颜色图例说明。

---

# 1. 颜色图例说明（Legend）

| 颜色 / 标记 | 含义 |
|---|---|
| 🔴 红色 (PWR) | 电源引脚，例如 **3V3、5V、VIN** |
| ⚫ 黑色 (GND) | 接地 |
| 🔵 靛色 (SERIAL) | 串口通信接口，例如 **TX / RX / UART** |
| 🟢 绿色 (ADCx_CH) | 模数转换器通道（ADC） |
| 🟡 黄色 (RESET) | 复位引脚 |
| 🌸 粉色 (GPIOx) | 通用输入输出引脚（GPIO） |
| 🟣 紫色 (TOUCHx) | 触摸传感器输入 |
| 🟧 橙色 (STRAP) | 启动配置引脚 |
| 🟦 青色 (SD) | SD 卡接口 |
| 💎 浅蓝色 (LED) | 板载 LED 引脚 |
| 🧡 粉橘色 (WS2812) | 板载 **WS2812 RGB LED** 控制引脚 |
| 🔴 深红色 (PSRAM) | PSRAM 占用引脚 |
| 🌿 浅绿色 (USB) | USB 接口信号 |
| 🔷 蓝色 (Camera) | 摄像头接口 |
| 🟩 深绿色 (JTAG) | JTAG 调试接口 |
| ～ 曲线标记 | 支持 **PWM（Pulse Width Modulation）** 输出的引脚 |

---

# 2. 左侧引脚定义 (Left Side Pins)



| 序号 | 丝印 | GPIO编号 | 功能1 | 功能2 | 功能3 |
|---|---|---|---|---|---|
| 1 | 3V3 | 3V3 | Power | - | - |
| 2 | EN | RST | Reset | - | - |
| 3 | G4 | GPIO4 | ADC1_CH3 | CAM_SIOD | T4 |
| 4 | G5 | GPIO5 | ADC1_CH4 | CAM_SIOC | T5 |
| 5 | G6 | GPIO6 | ADC1_CH5 | CAM_VSYNC | T6 |
| 6 | G7 | GPIO7 | ADC1_CH6 | CAM_HREF | T7 |
| 7 | G15 | GPIO15 | ADC2_CH4 | CAM_XCLK | U0RTS |
| 8 | G16 | GPIO16 | ADC2_CH5 | CAM_Y9 | U0CTS |
| 9 | G17 | GPIO17 | ADC2_CH6 | CAM_Y8 | U1TXD |
| 10 | G18 | GPIO18 | ADC2_CH7 | CAM_Y7 | U1RXD |
| 11 | G8 | GPIO8 | ADC1_CH7 | CAM_Y4 | T8 |
| 12 | G3 | GPIO3 | ADC1_CH2 | JTAG_EN (STRAP) | T3 |
| 13 | G46 | GPIO46 | - | LOG (STRAP) | - |
| 14 | G9 | GPIO9 | ADC1_CH8 | CAM_Y3 | T9 |
| 15 | G10 | GPIO10 | ADC1_CH9 | CAM_Y5 | T10 |
| 16 | G11 | GPIO11 | ADC2_CH0 | CAM_Y2 | T11 |
| 17 | G12 | GPIO12 | ADC2_CH1 | CAM_Y6 | T12 |
| 18 | G13 | GPIO13 | ADC2_CH2 | CAM_PCLK | T13 |
| 19 | G14 | GPIO14 | ADC2_CH3 | - | T14 |
| 20 | 5V | 5V | Power | - | - |
> 注：**从上到下顺序，部分引脚具有多重功能**


---

# 3. 右侧引脚定义 (Right Side Pins)

| 序号 | 丝印 | GPIO编号 | 功能1  | 功能2 | 功能3 |
|---|---|---|---|---|---|
| 1 | TX0 | GPIO43 | U0TXD |  LED TX | - |
| 2 | RX0 | GPIO44 | U0RXD |  LED RX | - |
| 3 | G1 | GPIO1 |  ADC1_CH0 | - | T1 |
| 4 | G2 | GPIO2 |  ADC1_CH1 | LED ON | T2|
| 5 | G42 | GPIO42 | - | MTMS | - |
| 6 | G41 | GPIO41 | - | MTDI | - |
| 7 | G40 | GPIO40 | SD_DATA | MTDO | - |
| 8 | G39 | GPIO39 |  SD_CLK | MTCK | - |
| 9 | G38 | GPIO38 |  SD_CMD | - | - |
| 10 | G37 | GPIO37 |  PSRAM | - | - |
| 11 | G36 | GPIO36 |  PSRAM | - | - |
| 12 | G35 | GPIO35 |  PSRAM | - | - |
| 13 | G0 | GPIO0 |  Boot（STRAP） | -| - |
| 14 | G45 | GPIO45 |  VSPI（STRAP） | -| - |
| 15 | G48 | GPIO48 |  WS2812 | -| - |
| 16 | G47 | GPIO47 | - | - | - |
| 17 | G21 | GPIO21 | - | - | - |
| 18 | G20 | GPIO20 | USB D- | ADC2_CH9 | U1CTS |
| 19 | G19 | GPIO19 | USB D+ | ADC2_CH8 | U1RTS |
| 20 | GND | GND | Ground | - | - |
> 注：**从上到下顺序，部分引脚具有多重功能**

---


# 4. 默认接口与对应引脚

## ESP32S3CAM与ov3660默认对应引脚

| OV3660引脚 | ESP32-S3 GPIO | 图中标注      | 作用说明             | ESP-IDF `camera_config_t` 字段 |
| -------- | ------------- | --------- | ---------------- | ---------------------------- |
| SIOD     | GPIO4         | CAM_SIOD  | 摄像头 SCCB/I2C 数据线 | `pin_sccb_sda`               |
| SIOC     | GPIO5         | CAM_SIOC  | 摄像头 SCCB/I2C 时钟线 | `pin_sccb_scl`               |
| VSYNC    | GPIO6         | CAM_VSYNC | 帧同步信号            | `pin_vsync`                  |
| HREF     | GPIO7         | CAM_HREF  | 行同步信号            | `pin_href`                   |
| XCLK     | GPIO15        | CAM_XCLK  | ESP32 输出摄像头主时钟   | `pin_xclk`                   |
| D7       | GPIO16        | CAM_Y9    | 像素数据 bit7        | `pin_d7`                     |
| D6       | GPIO17        | CAM_Y8    | 像素数据 bit6        | `pin_d6`                     |
| D5       | GPIO18        | CAM_Y7    | 像素数据 bit5        | `pin_d5`                     |
| D4       | GPIO12        | CAM_Y6    | 像素数据 bit4        | `pin_d4`                     |
| D3       | GPIO10        | CAM_Y5    | 像素数据 bit3        | `pin_d3`                     |
| D2       | GPIO8         | CAM_Y4    | 像素数据 bit2        | `pin_d2`                     |
| D1       | GPIO9         | CAM_Y3    | 像素数据 bit1        | `pin_d1`                     |
| D0       | GPIO11        | CAM_Y2    | 像素数据 bit0        | `pin_d0`                     |
| PCLK     | GPIO13        | CAM_PCLK  | 像素采样时钟           | `pin_pclk`                   |
| PWDN     | GPIO2         | LED ON    | 摄像头电源控制          | `pin_pwdn`                   |
| RESET    | -1            | 未连接       | 摄像头复位            | `pin_reset`                  |



## 🖥️ SPI LCD 显示屏（ST7789）

| 信号 | ESP32-S3 GPIO | 模块引脚 | 方向 | 功能说明 | 电气特性 |
|-----|---------------|---------|------|---------|---------|
| SCK | GPIO21 | SCK / SCLK | ESP32 → LCD | SPI 时钟 | 3.3V CMOS, ≤80 MHz |
| MOSI | GPIO47 | SDA / MOSI | ESP32 → LCD | SPI 数据输出 | 3.3V CMOS |
| CS | GPIO41 | CS / SS | ESP32 → LCD | 片选（低有效） | 3.3V CMOS |
| DC | GPIO40 | DC / RS | ESP32 → LCD | 数据 / 命令选择 | 3.3V CMOS |
| RST | GPIO45 | RST / RES | ESP32 → LCD | 硬件复位（低有效） | 3.3V CMOS |
| BL | GPIO42 | BL / LED | ESP32 → LCD | 背光控制（PWM） | 3.3V CMOS |

## ❤️ 系统心跳指示 （led）

| 信号 | ESP32-S3 GPIO | 模块引脚 | 方向 | 功能说明 | 电气特性 |
|-----|---------------|---------|------|---------|---------|
| HEARTBEAT | GPIO38 | LED / TEST | ESP32 → LED | 系统心跳指示（周期闪烁，用于系统运行状态检测） | 3.3V CMOS |

# 5. 关键接口总结

### 摄像头 (Camera)

主要使用以下引脚：


## 说明

### PWM capable pin
带有 **曲线标记（～）** 的引脚表示该 GPIO 支持 **PWM 输出**。
PWM（Pulse Width Modulation，脉冲宽度调制）常用于：

- LED 亮度调节  
- 电机速度控制  
- 舵机控制  
- 蜂鸣器驱动  

在 **ESP32 / ESP32-S3** 中，大多数 GPIO 都可以通过 **LEDC 控制器**实现 PWM 输出。

---

### STRAP 引脚
STRAP（Strapping Pins）是 **启动模式配置引脚**，在芯片 **上电或复位时读取电平状态**，用于决定启动模式。

如果外部电路连接不当，可能导致：

- 无法正常启动  
- 无法进入下载模式  
- Boot 配置错误  

---

### PSRAM 引脚
标记为 **PSRAM** 的引脚通常已经被 **外部 PSRAM 芯片占用**，因此：

- 不建议作为普通 GPIO 使用  
- 可能无法重新配置为其他功能  

---

### Camera 引脚
标记为 **Camera** 的 GPIO 通常用于摄像头接口（例如 **OV2640 / OV3660**），包括：

- 数据线（D0–D7）  
- 像素时钟（PCLK）  
- 行同步（HREF）  
- 帧同步（VSYNC）  
- 时钟输入（XCLK）  

这些引脚通常已经被摄像头模块占用，建议不要复用。

---

| INMP441 | ESP32-S3-CAM | 说明 |
|---|---|---|
| VDD | 3.3V | 电源 |
| GND | GND | 共地 |
| L/R | GND | 接地选择左声道 |
| SD  | GPIO 39 | I2S 数据输入 |
| WS  | GPIO 1 | 字选择（LRCLK） |
| SCK | GPIO 2 | 位时钟（BCLK） |