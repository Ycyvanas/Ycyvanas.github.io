# A7-Lite LED+UART+FLASH

FPGA: **MicroPhase A7-Lite** (Xilinx Artix-7 XC7A35T-2FGG484L)  
工具链: **Vivado 2024.2** + **openFPGALoader**  
功能: 板载两路 LED 以不同频率闪烁 + USB UART 回显通信（115200 8N1）+烧录在flash

## 项目结构

```
a7lite_project/
├── README.md                  # 本文件
├── src/
│   └── top.v                  # RTL 顶层模块
├── constraints/
│   └── constraints.xdc        # 引脚与时钟约束
├── scripts/
│   ├── build.tcl              # Vivado 批量构建脚本（含 SPIx4 配置）
│   ├── program.tcl            # Vivado JTAG 烧录脚本（临时运行）
│   ├── program_qspi.tcl       # Vivado QSPI Flash 烧录脚本（⚠️ Vivado 2024.2 有 bug，见下文）
│   ├── uart_monitor.py        # 🐍 UART 实时监测（时间戳/hex/落盘日志/自动检测 CH340）
│   └── uart_echo_test.py      # 🐍 UART echo 测试（分块/节流/突发/重复运行）
└── output/                    # 构建产物
    ├── top.bit                # 比特流文件
    └── top.bin                # bin 文件（用于烧 Flash）
```

## RTL 设计 (`src/top.v`)

- **输入**: `clk_50mhz`（50MHz 板载时钟）, `rst_n`（复位，低电平有效）
- **输出**: `led[1:0]`（2 个板载 LED）
- **逻辑**: 27 位计数器在主时钟上升沿递增，复位时清零

LED 由计数器的不同比特位驱动，实现不同闪烁频率：

| LED    | 位置  | 颜色  | 驱动信号 | 分频比       | 闪烁频率     | 特性        |
|--------|-------|-------|----------|--------------|-------------|-------------|
| led[0] | D6    | 🟢 绿 | cnt[23]  | 50MHz / 2²⁴ | **~2.98Hz** | **快闪** ✨ |
| led[1] | D5    | 🟢 绿 | cnt[26]  | 50MHz / 2²⁷ | **~0.37Hz** | **慢闪**    |

> 快闪的 LED0 每约 168ms 切换一次（半周期 84ms）；慢闪的 LED1 每约 2.68s 切换一次（半周期 1.34s），视觉效果差异显著。


## USB UART 通信

A7-Lite 板载 **CH340 USB-UART**，可通过独立的 UART USB 口连接主机 PC。

当前 RTL 实现为 **UART Echo 回显测试**：PC 发送任意字节，FPGA 接收后原样回送。

参数：

| 参数 | 值 |
|------|----|
| 波特率 | 115200 bps |
| 数据位 | 8 bit |
| 校验 | None |
| 停止位 | 1 bit |
| 流控 | None |

引脚：

| 信号 | FPGA 引脚 | 官方引脚名称 | 方向 | 说明 |
|------|-----------|--------------|------|------|
| `uart_tx` | V2 | IO_L2N_T0_34 | FPGA → PC | UART 数据输出 |
| `uart_rx` | U2 | IO_L2P_T0_34 | PC → FPGA | UART 数据输入 |

实现说明：

- `uart_rx.v`：8N1 接收器，起始位中点确认，LSB first
- `uart_tx.v`：8N1 发送器，`tx_start` 单周期触发，`tx_busy` 指示忙状态。
  **2026-06-02 优化**：`S_STOP` 倒数第二拍提前释放 `tx_busy`，最后一拍直接跳 `S_START` 实现 back-to-back，每字节固定 10 bit time（之前 11 bit），FPGA 端不再有 idle 间隙。
- `top.v`：接收字节进入 **1024-byte BRAM FIFO**，发送器空闲时依次回显
  （**2026-06-02 升级**：16 → 1024，并改成无异步 reset 的同步块，Vivado 推断为 1 个 RAMB18E1，资源代价极小）
- LED：未收到数据时保持原闪烁；收到数据后显示最后接收字节的低 2 位

### ⚠️ CH340 USB-UART 实测瓶颈

PC ↔ FPGA 全双工 115200 时，CH340 在 USB bulk 调度间隙会丢字节，
**周期性每 ~220 字节丢 1 字节**（~0.4%）。已实测排除：FPGA RTL、PC 软件、
波特率（9600/38400/57600/115200 同样丢，纯 `cat`/`dd` 测试也丢）。
这是 CH340 芯片硬件限制，与 FPGA 端无关。

#### ✅ 推荐使用方法（多轮稳定 PASS）

| 模式 | chunk | gap | 速率 | 稳定性 |
|---|---|---|---|---|
| **默认** | 150 B | 25 ms | **4.33 KB/s** | ⭐ 64KB 3/3 PASS |
| 保守 | 100 B | 20 ms | 3.75 KB/s | 64KB 3/3 PASS |
| per-byte | — | 100 µs | 5.91 KB/s | 4KB PASS（最快） |
| 全速 burst | — | — | — | ❌ 必丢 ~0.4% |

---

## 🐍 Python 脚本使用指南

两个脚本位于 `scripts/`，都基于 `pyserial`（首次使用：`pip install pyserial`）。
默认串口 `/dev/ttyUSB1`（板载 CH340），波特率 115200。

### `scripts/uart_monitor.py` — UART 实时监测

只接收 FPGA 输出，带时间戳/hex/落盘日志，适合**只看 FPGA 上行**的场景
（日志、调试打印、状态汇报）。

```bash
# 基础：监听 /dev/ttyUSB1 @ 115200，带时间戳，按行打印
python3 scripts/uart_monitor.py

# 自动检测 CH340（多串口设备时省事）
python3 scripts/uart_monitor.py --auto

# 同时落盘日志（追加写）
python3 scripts/uart_monitor.py --log logs/uart_$(date +%Y%m%d_%H%M%S).log

# Hex + ASCII 双栏显示（调字节级时序时用）
python3 scripts/uart_monitor.py --hex

# 自定义串口/波特率/无时间戳
python3 scripts/uart_monitor.py -p /dev/ttyUSB0 -b 9600 --no-ts
```

完整参数：

| 选项 | 说明 |
|---|---|
| `-p, --port`  | 串口设备（默认 `/dev/ttyUSB1`） |
| `-b, --baud`  | 波特率（默认 115200） |
| `--hex`       | 16 字节一组 hex+ASCII 显示 |
| `--no-ts`     | 不打印时间戳 |
| `--log PATH`  | 同时追加写入日志文件（自动建父目录） |
| `--auto`      | 自动检测 CH340 (VID=0x1A86, PID=0x7523) |

按 `Ctrl+C` 退出，会自动 flush 残留缓冲。

### `scripts/uart_echo_test.py` — UART echo 回显测试

往 FPGA 发数据 + 收回显比对，自动定位丢字节位置。适合**全双工压测**、
**回归验证**、**找参数甜点**。

```bash
# 默认：chunk=150 + gap=25ms，4096 字节
python3 scripts/uart_echo_test.py

# 指定数据量，重复 3 次验证稳定性
python3 scripts/uart_echo_test.py --bytes 65536 --repeat 3

# 短文本回显
python3 scripts/uart_echo_test.py -t "Hello A7-Lite UART!"

# per-byte 节流模式（最快，5.91 KB/s @ 4KB）
python3 scripts/uart_echo_test.py --bytes 4096 --gap-per-byte 100

# 全速突发模式（必丢字节，调试 CH340 问题用）
python3 scripts/uart_echo_test.py --bytes 1024 --burst

# 自定义 chunk/gap 探索参数
python3 scripts/uart_echo_test.py --bytes 16384 --chunk 100 --gap 20
```

完整参数：

| 选项 | 默认 | 说明 |
|---|---|---|
| `-p, --port`         | `/dev/ttyUSB1` | 串口设备 |
| `-b, --baud`         | 115200 | 波特率 |
| `-t, --text TEXT`    | — | 发送字符串（与 `--bytes` 互斥） |
| `--bytes N`          | 4096 | 随机发 N 字节 |
| `--chunk N`          | 150 | 分块大小（字节），0 = 一次写完 |
| `--gap MS`           | 25 | 每个 chunk 之间间隔（毫秒） |
| `--gap-per-byte US`  | 0 | 每字节间隔（微秒），覆盖 chunk/gap |
| `--burst`            | — | 等价 `--chunk 0 --gap 0`，调试用 |
| `--repeat N`         | 1 | 重复 N 次，最后输出 PASS 总结 |
| `--timeout SEC`      | 自动 | 收齐回显的最大等待时间 |

退出码：全部 PASS = 0，有 FAIL = 1。失败时会打印**丢字节数、百分比、首处丢失位置**，
方便定位 CH340 调度问题。

### 快速回归示例

```bash
# 一键完整回归（1KB / 16KB / 64KB 各 3 轮）
for n in 1024 16384 65536; do
  python3 scripts/uart_echo_test.py --bytes $n --repeat 3 || break
done
```

### 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `Permission denied` | `sudo chmod 666 /dev/ttyUSB1` 或 `sudo usermod -aG dialout $USER`（需重新登录） |
| `串口不存在` | `dmesg \| tail -20` 看 CH340 是否枚举成功，换 USB 线/口 |
| `--burst` 总是丢 ~0.4% | 正常，CH340 硬件限制，用默认 chunk/gap 即可 |
| 数据完全错乱 | 板子 RTL 还是旧的，重烧 `output/top.bit` |

## 引脚约束 (`constraints/constraints.xdc`)

| 信号        | FPGA 引脚 | IOSTANDARD  | 板级功能          |
|-------------|-----------|-------------|-------------------|
| `clk_50mhz` | J19       | LVCMOS33    | 板载 50MHz 有源晶振 |
| `rst_n`     | AA1       | LVCMOS33    | KEY1 按钮（按下低电平） |
| `led[0]`    | M18       | LVCMOS33    | LED1（红色 D6）    |
| `led[1]`    | N18       | LVCMOS33    | LED2（绿色 D5）    |
| `uart_tx`   | V2        | LVCMOS33    | CH340 UART_TX（FPGA→PC） |
| `uart_rx`   | U2        | LVCMOS33    | CH340 UART_RX（PC→FPGA） |

> 所有 GPIO Bank 默认 3.3V 供电，使用 LVCMOS33 电平标准。

## 构建方法

### 一键构建（推荐）

```bash
cd a7lite_project
~/Xilinx/Vivado/2024.2/bin/vivado -mode batch -source scripts/build.tcl
```

构建流水线：
1. 创建工程（器件 `xc7a35tfgg484-2L`）
2. 添加 RTL 源码 `src/top.v`
3. 添加约束 `constraints/constraints.xdc`
4. 综合（`synth_1`，4 线程并行）
5. 设置 QSPI 启动配置：SPIx4、50MHz、压缩
6. 实现 → 布线 → 生成比特流（`write_bitstream`，同时生成 `.bit` + `.bin`）

### 交互式方式

```bash
vivado &
# 打开后: File → Open Project → output/a7lite_led_blink.xpr
# 或: Tools → Run Tcl Script → scripts/build.tcl
```

## 烧录验证

### ⭐ 方式 A：QSPI 启动（掉电不丢失，推荐）

将 bitstream 烧录到板载 Flash，重新上电后 FPGA 自动加载。

**⚠️ 重要提示：Vivado 2024.2 Linux 版对 FT232H 的 SPI Flash 烧录有 bug（`Labtools 27-3347`），请使用 openFPGALoader！**

```bash
cd a7lite_project
# 烧录到 Flash（永久保存，脱机运行）
sudo openFPGALoader --cable digilent_hs2 --fpga-part xc7a35tfgg484 -f output/top.bin
```

**工作流程：**
1. 加载 SPI over JTAG bridge 到 FPGA
2. 检测 Flash 型号：**ISSI IS25LP128**（128Mbit / 16MB）
3. 擦除 Flash → 写入 → 验证
4. 拔电重上电即可自动启动

> 烧录后**重新上电**即可从 Flash 自动加载，实现掉电不丢失。

### 方式 B：JTAG 直接烧录（临时运行，掉电丢失）

```bash
cd a7lite_project
~/Xilinx/Vivado/2024.2/bin/vivado -mode batch -source scripts/program.tcl
```

或用 openFPGALoader（更快）：
```bash
sudo openFPGALoader --cable digilent_hs2 --fpga-part xc7a35tfgg484 output/top.bin
```

## 硬件信息

| 组件 | 型号 | 规格 |
|------|------|------|
| FPGA | XC7A35T-2FGG484L | Artix-7 35T，484 引脚 BGA |
| Flash | IS25LP128F | ISSI 128Mbit (16MB) QSPI Flash |
| JTAG/UART | FT232H | 板载 USB-JTAG 电路 |
| 晶振 | 50MHz | 有源晶振 |

## 资源占用

| 资源    | 使用量 | 总量    | 占比    |
|---------|--------|---------|---------|
| LUT     | 42     | 20800   | 0.20%   |
| FF      | 64     | 41600   | 0.15%   |
| IO      | 4      | 250     | 1.60%   |
| BUFG    | 1      | 32      | 3.12%   |

## 常见问题

### Q: Vivado 烧 QSPI 时报 `Labtools 27-3347: Failure to set flash parameters`？

A: 这是 Vivado 2024.2 Linux 版对 FT232H 的 SPI bridge bug。**解决方法：用 openFPGALoader**（见方式 A），一次就成功。

### Q: 烧完 Flash 后 LED 不亮？

A: 必须**完全拔电后重新上电**，FPGA 才会从 Flash 加载。JTAG 复位/`boot_hw_device` 不一定管用，硬重启最可靠。

### Q: openFPGALoader 报 `unable to open ftdi device`？

A: 需要 `sudo` 权限才能访问 USB 设备。加上 `sudo` 即可。

## 开发记录

| 日期 | 备注 |
|------|------|
| 2026-05-28 | 首次构建成功。原问题：器件型号误用 CSG324 封装、引脚约束未对齐 A7-Lite 板定义、IOSTANDARD 误设为 LVCMOS18。修正后使用 `xc7a35tfgg484-2L` + J19/M18/N18/AA1 + LVCMOS33，综合实现均通过。 |
| 2026-05-29 | 拆分 LED 驱动：LED0（红色 D6）使用 cnt[23] 实现 ~2.98Hz **快闪**，LED1（绿色 D5）保留 cnt[26] 实现 ~0.37Hz **慢闪**。添加 `scripts/program.tcl` 命令行烧录脚本。 |
| 2026-05-31 | ✅ QSPI 启动支持完成：<br>1. `build.tcl` 加入 SPIx4 配置（SPI_BUSWIDTH=4、CONFIGRATE=50MHz、COMPRESS=TRUE）<br>2. 确认板载 Flash 型号：ISSI IS25LP128F (128Mbit)<br>3. 踩坑：Vivado 2024.2 Linux 版对 FT232H 的 SPI Flash 烧录有 bug（`Labtools 27-3347`）<br>4. 解决方案：改用 openFPGALoader，一次烧录成功 |
| 2026-06-02 | ✅ 增加 USB UART 通信：按官方文档使用 CH340，`uart_tx=V2`、`uart_rx=U2`，实现 115200 8N1 echo 回显。初版因 TX 忙时丢字节，已加入 16-byte FIFO；实测 `A\r\n`、`ABCabc123\r\n`、`Hello A7-Lite UART!\r\n` 全部回显匹配。 |
| 2026-06-02 (P2) | ✅ **UART 全双工压力测试 + CH340 瓶颈定位**：<br>1. 新增 `scripts/uart_echo_test.py`（chunk/gap/burst/per-byte 多模式）和 `scripts/uart_monitor.py`（监测+日志+hex）<br>2. RTL 优化：`uart_tx.v` 改 back-to-back（每字节 10 bit time），`top.v` FIFO 16 → **1024 BRAM**（同步无 reset，Vivado 推断 1 个 RAMB18E1）<br>3. 测试发现连续突发每 ~220 字节稳定丢 1 字节，纯 `cat`/`dd` 测试同样丢，57600/115200 表现一致 → 排除 FPGA、Python、波特率因素<br>4. 根因：**CH340 USB-UART 双向全负载时 USB bulk 调度缺陷**（芯片限制，不可在 FPGA 端解决）<br>5. 工程化解决：测试脚本默认走 `chunk=150 gap=25ms`，多轮 16KB / 64KB 稳定 PASS @ 4.33 KB/s |
� A7-Lite 板定义、IOSTANDARD 误设为 LVCMOS18。修正后使用 `xc7a35tfgg484-2L` + J19/M18/N18/AA1 + LVCMOS33，综合实现均通过。 |
| 2026-05-29 | 拆分 LED 驱动：LED0（红色 D6）使用 cnt[23] 实现 ~2.98Hz **快闪**，LED1（绿色 D5）保留 cnt[26] 实现 ~0.37Hz **慢闪**。添加 `scripts/program.tcl` 命令行烧录脚本。 |
| 2026-05-31 | ✅ QSPI 启动支持完成：<br>1. `build.tcl` 加入 SPIx4 配置（SPI_BUSWIDTH=4、CONFIGRATE=50MHz、COMPRESS=TRUE）<br>2. 确认板载 Flash 型号：ISSI IS25LP128F (128Mbit)<br>3. 踩坑：Vivado 2024.2 Linux 版对 FT232H 的 SPI Flash 烧录有 bug（`Labtools 27-3347`）<br>4. 解决方案：改用 openFPGALoader，一次烧录成功 |
| 2026-06-02 | ✅ 增加 USB UART 通信：按官方文档使用 CH340，`uart_tx=V2`、`uart_rx=U2`，实现 115200 8N1 echo 回显。初版因 TX 忙时丢字节，已加入 16-byte FIFO；实测 `A\r\n`、`ABCabc123\r\n`、`Hello A7-Lite UART!\r\n` 全部回显匹配。 |
