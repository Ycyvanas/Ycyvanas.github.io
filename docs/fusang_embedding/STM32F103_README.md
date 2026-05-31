# STM32F103C8T6(bluepill)开发入门

嵌入式开发的本质是将软件部署到硬件设备上运行。无论是 8051、STM32、ESP32 还是 FPGA SoC，其开发流程都可以抽象为：

```text
代码编写
    ↓
程序编译 & 固件生成
    ↓
设备烧录 & 运行验证
    ↓
日志监测
    ↓
迭代开发
```

对于初学者而言，建议优先打通这一完整闭环，而不是直接进入 RTOS、驱动框架或复杂业务逻辑开发。

---

# 一、开发环境

## 本例环境配置

| 项目        | 配置                        |
| --------- | ------------------------- |
| 操作系统      | Windows                   |
| IDE       | VSCode                    |
| Platform  | STM32                     |
| Board     | STM32F103C8T6 (Blue Pill) |
| Framework | STM32Cube HAL             |
| 编译器       | arm-none-eabi-gcc         |
| 烧录工具      | OpenOCD / ST-Link         |
| 调试接口      | SWD                       |
| 日志输出      | UART                      |

---

# 二、创建 PlatformIO 工程

## 1. 安装环境

安装：

* VSCode
* PlatformIO IDE 插件

---

## 2. 创建工程

```text
PlatformIO
 └── New Project
      ├── Board: BluePill F103C8
      └── Framework: STM32Cube
```

工程路径示例：

```powershell
C:\Users\xxx\Documents\PlatformIO\Projects\stm32-blink
```

---

## 3. 编译工程

```powershell
pio run
```

生成文件：

```text
.pio/build/bluepill_f103c8/
 ├── firmware.bin
 ├── firmware.elf
 └── firmware.map
```

---

# 三、烧录固件

STM32 常见下载方式：

| 方式               | 接口   | 推荐    |
| ---------------- | ---- | ----- |
| ST-Link          | SWD  | ⭐⭐⭐⭐⭐ |
| USART Bootloader | UART | ⭐⭐⭐   |
| J-Link           | SWD  | ⭐⭐⭐⭐⭐ |

---

## 1. SWD 接线（ST-Link）

| ST-Link | STM32 |
| ------- | ----- |
| SWDIO   | PA13  |
| SWCLK   | PA14  |
| GND     | GND   |
| 3.3V    | 3.3V  |

---

## 2. 烧录命令

```powershell
pio run -t upload
```

成功输出：

```text
Uploading firmware...
Verify OK
Resetting target...
```

---

# 四、最小验证闭环（LED Blink）

## 1. GPIO 点灯验证
STM32F103 Blue Pill 板载 LED：

```text
PC13
```

逻辑特点：

* 输出低电平 → LED 亮
* 输出高电平 → LED 灭

---

## 作用

LED Blink 用于验证：

* 编译链是否正常
* 下载是否正常
* MCU 是否运行
* GPIO 是否正常

---

## 2. UART 日志监测
### 串口引脚

| 功能 | 引脚   |
| -- | ---- |
| TX | PA9  |
| RX | PA10 |

---

### USB-TTL 连接

| USB-TTL | STM32 |
| ------- | ----- |
| TX      | PA10  |
| RX      | PA9   |
| GND     | GND   |

注意：

* TX ↔ RX 交叉连接
* 必须共地
* 使用 3.3V TTL

---

## 3.串口监控

```powershell
pio device monitor
```

---

### 示例输出

```text
STM32F103 Start
LED Blink Running
Counter = 1
Counter = 2
Counter = 3
```

---

## 4.自动化烧录与监测
STM32的烧录和UART端口独立，支持同时通过ST-LINK烧录和USB-TTL监测。

完整开发流程：

```text
编写代码
    ↓
编译生成 firmware
    ↓
ST-Link 烧录
    ↓
MCU 运行
    ↓
UART 输出日志
    ↓
问题分析
    ↓
修改代码
    ↓
循环迭代
```

在实际工程中，可以通过 Python 脚本实现全流程自动化，包括：
- 一键编译
- 一键烧录
- 自动串口重连
- 实时日志输出
- 运行状态检测


进一步扩展后，可接入 OpenClaw、Hermes、Claude Code、Codex 等 Agent 系统，实现嵌入式设备的自动编译、自动烧录、自动测试与自动修复闭环。从而构建真正意义上的“AI 驱动嵌入式开发系统”。

# 示例代码(led+uart)
```c
#include "stm32f1xx_hal.h"
#include <string.h>

#define LED_PIN                 GPIO_PIN_13
#define LED_GPIO_PORT           GPIOC
#define LED_GPIO_CLK_ENABLE()   __HAL_RCC_GPIOC_CLK_ENABLE()

UART_HandleTypeDef huart1;

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_Init(void);
static void Error_Handler(void);

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART1_Init();

    const char *msg = "Hello STM32, It is time to work!\r\n";
    uint16_t len = strlen(msg);

    while (1)
    {
        HAL_GPIO_TogglePin(LED_GPIO_PORT, LED_PIN);

        /* ✅ 坚持使用 HAL_UART_Transmit 的标准写法 */
        HAL_StatusTypeDef status = HAL_UART_Transmit(&huart1, (uint8_t*)msg, len, 100);
        
        /* 可选：生产环境建议捕获异常状态，防止一次超时后状态机锁死 */
        if (status != HAL_OK) {
            // 记录错误或恢复状态机（示例）
            // huart1.State = HAL_UART_STATE_READY; 
        }

        HAL_Delay(500);
    }
}

void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState       = RCC_HSE_ON;
    RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    RCC_OscInitStruct.PLL.PLLState   = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLMUL     = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) Error_Handler();

    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                                     | RCC_CLOCKTYPE_PCLK1  | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK) Error_Handler();

    /* 🔑 关键1：显式配置 SysTick，HAL_Delay 与 HAL_UART_Transmit 超时均依赖此时间基 */
    HAL_SYSTICK_Config(HAL_RCC_GetHCLKFreq() / 1000);
    HAL_SYSTICK_CLKSourceConfig(SYSTICK_CLKSOURCE_HCLK);
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    LED_GPIO_CLK_ENABLE();

    GPIO_InitStruct.Pin   = LED_PIN;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_GPIO_PORT, &GPIO_InitStruct);

    HAL_GPIO_WritePin(LED_GPIO_PORT, LED_PIN, GPIO_PIN_SET);
}

static void MX_USART1_Init(void)
{
    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};

    GPIO_InitStruct.Pin   = GPIO_PIN_9;
    GPIO_InitStruct.Mode  = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    GPIO_InitStruct.Pin  = GPIO_PIN_10;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    huart1.Instance        = USART1;
    huart1.Init.BaudRate   = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits   = UART_STOPBITS_1;
    huart1.Init.Parity     = UART_PARITY_NONE;
    huart1.Init.Mode       = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl  = UART_HWCONTROL_NONE;
    if (HAL_UART_Init(&huart1) != HAL_OK) Error_Handler();
}

static void Error_Handler(void)
{
    /* 错误指示：LED 常亮 */
    HAL_GPIO_WritePin(LED_GPIO_PORT, LED_PIN, GPIO_PIN_SET);
    __disable_irq();
    while (1){}
}

/* 🔑 关键2：SysTick 中断服务函数，维持 HAL 时间基 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
```