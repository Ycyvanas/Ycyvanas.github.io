# 嵌入式开发流程（以 STC89C52RC + Windows 为例）

嵌入式开发的本质是将软件部署到硬件设备上运行。无论是 8051、STM32、ESP32 还是 FPGA SoC，其开发流程都可以抽象为：

```text
代码编写
    ↓
程序编译&固件生成
    ↓
设备烧录&运行验证
    ↓
日志监测
    ↓
迭代开发
```

对于初学者而言，建议首先打通这一完整闭环，而不是直接从复杂业务逻辑或驱动开发开始。

本例以 STC89C52RC 单片机为例，介绍基于 Windows、VSCode 和 PlatformIO 的开发流程。

## 一、开发环境

在嵌入式开发中，需要明确两个核心概念：

| 名称       | 说明                                             |
| -------- | ---------------------------------------------- |
| Platform | 开发平台或处理器架构，例如 8051、ARM Cortex-M、RISC-V 等       |
| Board    | 开发板或具体芯片型号，例如 STC89C52RC、STM32F103C8T6、ESP32 等 |

本例环境如下：

| 项目       | 配置                 |
| -------- | ------------------ |
| 操作系统     | Windows            |
| IDE      | VSCode             |
| Platform | Intel MCS-51（8051） |
| Board    | STC89C52RC         |
| 编译器      | SDCC               |
| 烧录工具     | stcgal             |
| 调试接口     | UART（USB-TTL）      |

---

## 二、创建 PlatformIO 工程

### 1. 安装开发环境

安装：

* VSCode
* PlatformIO IDE 插件

安装完成后，新建工程：

```text
PlatformIO
 └─ New Project
      ├─ Board: STC89C52RC
      └─ Framework: Bare Metal / SDCC
```

例如工程目录：

```powershell
C:\Users\dengx\Documents\PlatformIO\Projects\stc89
```

---

### 2. 编译工程

在项目目录执行：

```powershell
C:\Users\dengx\.platformio\penv\Scripts\platformio.exe run --environment STC89C52RC
```

编译成功后会生成：

```powershell
.pio\build\STC89C52RC\firmware.hex
```

该文件即最终烧录到单片机中的固件。

---

## 三、烧录固件

### 1. 安装 stcgal

STC 系列单片机采用 ISP（In-System Programming）串口下载协议。

由于 PlatformIO 对 STC 下载支持有限，因此推荐使用 stcgal。

安装方式：

```powershell
pip install stcgal
```

或：

```powershell
python -m pip install stcgal
```

---

### 2. USB-TTL 接线

| USB-TTL 模块 | STC89C52RC | 功能     |
| ---------- | ---------- | ------ |
| GND        | GND        | 共地     |
| TXD        | P3.0（RXD）  | 串口接收   |
| RXD        | P3.1（TXD）  | 串口发送   |
| VCC        | VCC（5V）    | 供电（可选） |

注意：

* TX 与 RX 必须交叉连接；
* 必须共地；
* 使用支持数据传输的 USB 数据线；
* 部分 Micro USB 线仅支持充电，无法识别串口。

---

### 3. 执行烧录

```powershell
python -m stcgal -p COM7 -P stc89 .\.pio\build\STC89C52RC\firmware.hex
```

参数说明：

| 参数             | 说明         |
| -------------- | ---------- |
| `-p COM7`      | 串口号        |
| `-P stc89`     | STC89 下载协议 |
| `firmware.hex` | 编译生成固件     |

查看串口：

```powershell
设备管理器 → 端口(COM 和 LPT)
```

例如：

```text
USB-SERIAL CH340 (COM7)
```

---

## 四、建立编译、烧录与监测闭环

完成环境搭建后，建议优先验证：

```text
编译是否正常
    ↓
烧录是否正常
    ↓
程序是否运行
    ↓
日志是否输出
```

形成最小开发闭环。

### 1. GPIO 点灯验证

最简单的验证方法是驱动 LED。

例如：

```text
VCC ── LED+
         │
        LED-
         │
        P2.0
```

P2.0 输出低电平时点亮 LED。

通过 LED 闪烁程序，可以快速验证：

* 编译是否成功；
* HEX 是否正确生成；
* ISP 是否正常；
* MCU 是否正常运行；
* GPIO 是否正常工作。

---

### 2. UART 日志监测

STC89C52RC 仅提供一组硬件 UART：

| 功能  | 引脚   |
| --- | ---- |
| RXD | P3.0 |
| TXD | P3.1 |

该 UART 同时承担：

* ISP 下载；
* 串口调试；
* 用户通信。

因此与 STM32 的 SWD + UART 双通道模式不同，STC 的下载与调试共用同一个串口。

---

### 3. 串口监测

烧录完成后，可启动串口监测：

```powershell
C:\Users\dengx\.platformio\penv\Scripts\platformio.exe device monitor --environment STC89C52RC
```

典型输出：

```text
BOOT OK
System Start
LED Blink
Counter = 1
Counter = 2
Counter = 3
```

---

## 4.自动化烧录与监测

由于 STC89C52RC 仅有一组 UART，因此烧录与串口监测无法同时占用，需要顺序执行。

推荐工作流：

```text
PlatformIO 编译
        ↓
生成 firmware.hex
        ↓
stcgal 烧录
        ↓
MCU 自动复位
        ↓
释放串口
        ↓
启动 UART Monitor
        ↓
接收运行日志
```

在实际工程中，可以通过 Python 脚本实现全流程自动化，包括：
- 一键编译
- 一键烧录
- 自动串口重连
- 实时日志输出
- 运行状态检测


进一步扩展后，可接入 OpenClaw、Hermes、Claude Code、Codex 等 Agent 系统，实现嵌入式设备的自动编译、自动烧录、自动测试与自动修复闭环。从而构建真正意义上的“AI 驱动嵌入式开发系统”。

# 参考代码
## led blink
```c
#include <mcs51/8052.h>
//led blink
// P2.0->led-, vcc->led+

void delay_ms(unsigned int ms)
{
    unsigned int i, j;
    for (i = 0; i < ms; i++)
        for (j = 0; j < 120; j++); //110592
}

void main(void)
{
    unsigned char led = 0xFE; // 1111 1110，P2.0 亮

    while (1)
    {
        P2 = led;             // 输出到 LED
        delay_ms(200);

        // 进位循环左移
        //led = (led << 1);
        led = (led << 1) | (led >> 7);
    }
}
```

## uart+blink

```c
#include <mcs51/8052.h>
#include <stdio.h>

/*================ 串口配置 ================*/
#define BAUD_RATE 9600
#define SYS_CLOCK 11059200UL

void UART_Init(void)
{
    TMOD &= 0x0F;
    TMOD |= 0x20;        // 定时器1：方式2，8位自动重装
    TH1 = 0xFD;          // 9600bps @ 11.0592MHz
    TL1 = 0xFD;
    SCON = 0x50;         // 串口方式1，允许接收
    PCON &= 0x7F;        // SMOD=0，波特率不倍增
    TR1 = 1;             // 启动定时器1
}

void UART_SendByte(unsigned char dat)
{
    SBUF = dat;
    while(!TI);          // 等待发送完成
    TI = 0;              // 清除标志
}

/* 🔧 修复：SDCC 兼容的 putchar */
int putchar(int c) __reentrant
{
    if(c == '\n') {
        UART_SendByte('\r');
    }
    UART_SendByte((unsigned char)c);
    return c;
}

/*================ 原有功能 ================*/
void delay_ms(unsigned int ms)
{
    unsigned int i, j;
    for(i = 0; i < ms; i++)
        for(j = 0; j < 120; j++);  // ≈1ms @11.0592MHz
}

/*================ 主函数 ================*/
void main(void)
{
    unsigned char led = 0xFE;
    unsigned char count = 0;
    
    UART_Init();
    delay_ms(100);
    
    // 🎯 启动日志
    printf("\r\n=== STC89C52RC Monitor ===\r\n");
    printf("Clock: %lu Hz | Baud: %d\r\n", SYS_CLOCK, BAUD_RATE);
    
    while(1)
    {
        P2 = led;
        
        count++;
        if(count >= 5)  // 约1秒打印一次
        {
            count = 0;
            printf("[LED] P2=0x%02X\r\n", led);
        }
        
        delay_ms(200);
        led = (led << 1) | (led >> 7);  // 循环左移
    }
}
```