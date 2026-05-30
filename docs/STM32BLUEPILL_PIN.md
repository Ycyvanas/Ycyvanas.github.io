# STM32F103小蓝片 
为了方便查阅，引脚分为 **左侧排针** 和 **右侧排针** 两部分，并附带颜色图例说明。

## 1. 图例说明（Legend）

| 颜色     | 含义                        |
| ------ | ------------------------- |
| 🎯 红色 | POWER（电源） |
| ⬛ 黑色   | GROUND（接地）                |
| 🟦 浅蓝  | PHYSICAL PIN（物理引脚）        |
| 🟡 浅黄 | PIN NAME（引脚名称）            |
| 🟨 黄色  | CONTROL（控制）               |
| 🟩 绿色  | ANALOG（模拟）                |
| 🩷 粉色  | TIMER & CHANNEL（定时器 / 通道） |
| 🟦 蓝色  | USART（串口）                 |
| 🟣 紫色  | SPI                       |
| ⚪ 银色   | I2C                       |
|  🟥深粉 | CAN BUS                   |
| 🟩 浅绿色 | USB                       |
| ⚪ 白色   | MISC（杂项）                  |
| 🟧 橙色  | BOARD HARDWARE（板载硬件）      |
| ●─── | 5V TOLERANT（可承受 5V 输入） |
| ○─── | NOT 5V TOLERANT（不可承受 5V 输入） |
| ～ | PWM PIN（支持 PWM 输出的引脚） |


## 2. 左侧排针 (Left Header)

| 物理编号 | 引脚名称 | 功能1 | 功能2 | 功能3 | 功能4 |
|----------|----------|-------|-------|-------|-------|
| 25 | PB12 | I2C2_SMBAI | SPI2_NSS | TIM1_BKIN | USART3_CK |
| 26 | PB13 | - | SPI2_SCK | TIM1_CH1N | USART3_CTS |
| 27 | PB14 | - | SPI2_MISO | TIM1_CH2N | USART3_RTS |
| 28 | PB15 | - | SPI2_MOSI | TIM1_CH3N | - |
| 29 | PA8  | - | USART1_CK | TIM1_CH1 | MCO |
| 30 | PA9  | - | USART1_TX | TIM1_CH2 | - |
| 31 | PA10 | - | USART1_RX | TIM1_CH3 | - |
| 32 | PA11 | USB- | USART1_CTS | TIM1_CH4 | CAN_RX |
| 33 | PA12 | USB+ | USART1_RTS | TIM1_ETR | CAN_TX |
| 38 | PA15 | JTDI | SPI1_NSS | TIM2_C1E | - |
| 39 | PB3  | JTDO | SPI1_SCK | TIM2_CH2 | TRACE SWO |
| 40 | PB4  | JTRST | SPI1_MISO | TIM3_CH1 | - |
| 41 | PB5  | I2C1_SMBAI | SPI1_MOSI | TIM2_CH2 | - |
| 42 | PB6  | - | I2C1_SCL | TIM4_CH1 | USART1_TX |
| 43 | PB7  | - | I2C1_SDA | TIM4_CH2 | USART1_RX |
| 45 | PB8  | TIM4_CH3 | I2C1_SCL | - | CAN_RX |
| 46 | PB9  | TIM4_CH4 | I2C1_SDA | - | CAN_TX |
| -  | 5V   | - | - | - | - |
| -  | GND  | - | - | - | - |
| -  | 3V3  | - | - | - | - |





## 3. 右侧排针 (Right Header)

| 物理编号 | 引脚名称 | 功能1 | 功能2 | 功能3 | 功能4 | 
|----------|----------|-------|-------|-------|-------|
| -  | GND   | - | - | - | - | 
| -  | GND   | - | - | - | - | 
| -  | 3V3   | - | - | - | - |
| 7  | NRST  | RESET | - | - | - |
| 22 | PB11  | I2C2_SDA | USART3_RX | - | TIM2_CH4N |
| 21 | PB10  | I2C2_SCL | USART3_TX | - | TIM2_CH3N | 
| 19 | PB1   | ADC9 |   -   | TIM3_CH4 | TIM1_CH3N |
| 18 | PB0   | ADC8 |   -   |  TIM3_CH3 | TIM1_CH2N |
| 17 | PA7   | ADC7 | SPI1_MOSI | TIM3_CH2 | TIM1_CH1N |
| 16 | PA6   | ADC6 | SPI1_MISO | TIM3_CH1 | TIM1_BKIN |
| 15 | PA5   | ADC5 | SPI1_SCK | - | - |
| 14 | PA4   | ADC4 | SPI1_NSS | USART2_CK | - |
| 13 | PA3   | ADC3 | USART2_RX | TIM2_CH4 | - |
| 12 | PA2   | ADC2 | USART2_TX | TIM2_CH3 | - | 
| 11 | PA1   | ADC1 | USART2_RTS | TIM2_CH2 | - |
| 10 | PA0   | ADC0 | USART2_CTS | TIM2_C1E | WKUP |
| 4  | PC15  | OSC32_OUT| - | - | - |
| 3  | PC14  | OSC32_IN| - | - | - |
| 2  | PC13  | TAMPER RTC| PC13 LED | - | - | 
| 1  | VBAT  | Backup Power | - | - | - |






## 板载 LED（PC13）

| 项目 | 说明 |
|------|------|
| LED引脚 | PC13 |


## 调试常用接口
| USB转TTL模块 | STM32F1 引脚 | 说明 |
|---|---|---|
| TX | PA10 (RX) | 模块发 → STM32收 |
| RX | PA9 (TX) | 模块收 ← STM32发 |
| GND | GND | ⚠️ 必须共地 |
| 3.3V | 3.3V | 可选 |


## 🖥️ SPI LCD 显示屏（ST7789）

| 信号 | STM32 GPIO | 模块引脚 | 方向 | 功能说明 | 电气特性 |
|-----|---------------|---------|------|---------|---------|
| SCK | PA5 | SCK / SCLK | STM32 → LCD | SPI 时钟 | 3.3V CMOS, ≤80 MHz |
| MOSI | PA7 | SDA / MOSI | STM32 → LCD | SPI 数据输出 | 3.3V CMOS |
| CS | PA4 | CS / SS | STM32 → LCD | 片选（低有效） | 3.3V CMOS |
| DC | PA6 | DC / RS | STM32 → LCD | 数据 / 命令选择 | 3.3V CMOS |
| RST | PB0 | RST / RES | STM32 → LCD | 硬件复位（低有效） | 3.3V CMOS |
| BL | PB1 | BL / LED | STM32 → LCD | 背光控制（PWM） | 3.3V CMOS |


## PCF8574+LCD1602A（I2C模块）接线说明

| 引脚 | 功能 | STM32 GPIO | 方向 | 说明 |
|------|------|------------|------|------|
| VCC | 电源 | 5V（或3.3V） | 电源 | LCD 模块供电 |
| GND | 地 | GND | 电源 | 共地 |
| SDA | I²C 数据线 | PB11 | 双向 | I2C1 SDA |
| SCL | I²C 时钟线 | PB10 | STM32 → LCD | I2C1 SCL |


## DS1302时钟模块
| 模块引脚 | DS1302内部引脚 | 说明                   |
| ---- | ---------- | -------------------- |
| VCC  | VCC2       | 主电源输入（实测可接 3.3V） |
| GND  | GND        | 地                    |
| CLK  | SCLK       | 串行时钟                 |
| DAT  | IO         | 数据线（双向）              |
| RST  | CE         | 片选 / 使能信号            |
| BAT  | VCC1       | 备用电池输入（接 CR2032）     |