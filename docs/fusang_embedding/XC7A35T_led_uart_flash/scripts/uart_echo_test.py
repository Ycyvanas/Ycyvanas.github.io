#!/usr/bin/env python3
"""
a7lite_project UART echo 测试 (CH340 友好版)

向 A7-Lite (CH340) 发送数据，读取回显并比对。

## CH340 已知瓶颈
PC↔FPGA 全双工 115200 时，CH340 USB-UART 在 USB bulk 调度间隙
会丢字节 (~0.4%, 每 ~220B 丢 1B)。这是 CH340 硬件限制，与 FPGA
和波特率无关。

## 推荐参数 (实测 100% PASS)
- 默认 --chunk=200 --gap=30 : 4.35 KB/s，64KB 也 PASS
- --chunk=64  --gap=20      : 3.07 KB/s
- --gap-per-byte=100        : 4.81 KB/s (per-byte 节流模式)
- --chunk=0 --gap=0         : 全速突发 (会丢字节，调试用)

## 用法
  python3 scripts/uart_echo_test.py                    # 默认: 安全模式
  python3 scripts/uart_echo_test.py --bytes 1024
  python3 scripts/uart_echo_test.py --burst            # 全速突发 (会丢)
  python3 scripts/uart_echo_test.py --bytes 65536 --chunk 100 --gap 30
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

try:
    import serial
except ImportError:
    sys.stderr.write("缺少 pyserial，请先安装: pip install pyserial\n")
    sys.exit(1)


def open_serial(port: str, baud: int, timeout: float = 1.0) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
        rtscts=False,
        dsrdtr=False,
        xonxoff=False,
    )


def analyze_diff(payload: bytes, rx: bytes) -> tuple[int, int]:
    """返回 (丢字节数, 首处丢失位置)。"""
    i = j = 0
    lost = 0
    first = -1
    while i < len(payload) and j < len(rx):
        if payload[i] == rx[j]:
            i += 1
            j += 1
        else:
            if first < 0:
                first = i
            lost += 1
            i += 1
    lost += len(payload) - i
    return lost, first


def main() -> int:
    ap = argparse.ArgumentParser(
        description="A7-Lite UART echo test (CH340 友好)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("-p", "--port", default="/dev/ttyUSB1",
                    help="串口设备 (默认 /dev/ttyUSB1)")
    ap.add_argument("-b", "--baud", type=int, default=115200,
                    help="波特率 (默认 115200)")
    ap.add_argument("-t", "--text", help="要发送的字符串")
    ap.add_argument("--bytes", type=int, default=4096,
                    help="随机发送 N 字节 (默认 4096，覆盖 --text)")

    # CH340 限速参数
    ap.add_argument("--chunk", type=int, default=150,
                    help="分块大小 (字节)；0 表示一次性写完 (默认 150)")
    ap.add_argument("--gap", type=float, default=25.0,
                    help="每个 chunk 之间的间隔 (毫秒，默认 25)")
    ap.add_argument("--gap-per-byte", type=float, default=0,
                    help="每字节间隔 (微秒)，覆盖 chunk/gap (默认 0)")
    ap.add_argument("--burst", action="store_true",
                    help="全速突发模式 (chunk=0 gap=0，会丢字节，调试用)")

    ap.add_argument("--timeout", type=float, default=0,
                    help="收齐回显的总超时 (秒, 0=自动)")
    ap.add_argument("--repeat", type=int, default=1, help="重复测试 N 次")
    args = ap.parse_args()

    if args.burst:
        args.chunk = 0
        args.gap = 0.0

    if not os.path.exists(args.port):
        print(f"[!] 串口不存在: {args.port}", file=sys.stderr)
        return 2

    # 准备 payload
    if args.text:
        base = args.text.encode("utf-8")
        payload = base
    else:
        payload = bytes(random.randint(0x20, 0x7E) for _ in range(args.bytes))
    n = len(payload)

    try:
        ser = open_serial(args.port, args.baud, timeout=1.0)
    except serial.SerialException as e:
        print(f"[!] 打开失败 ({args.port}): {e}", file=sys.stderr)
        return 2

    # 报告参数
    mode = "burst" if (args.chunk == 0 and args.gap_per_byte == 0) \
        else f"per-byte gap={args.gap_per_byte}us" if args.gap_per_byte > 0 \
        else f"chunk={args.chunk} gap={args.gap}ms"
    print(f"[i] {args.port} @ {args.baud}  n={n}  mode={mode}")

    fails = 0
    for run_idx in range(args.repeat):
        # drain
        ser.timeout = 0.05
        while ser.read(4096):
            pass
        ser.timeout = 1.0

        t0 = time.monotonic()

        if args.gap_per_byte > 0:
            gap = args.gap_per_byte / 1e6
            for b in payload:
                ser.write(bytes([b]))
                if gap > 0:
                    time.sleep(gap)
            ser.flush()
        elif args.chunk > 0:
            gap = args.gap / 1000.0
            for i in range(0, n, args.chunk):
                ser.write(payload[i:i + args.chunk])
                ser.flush()
                if gap > 0:
                    time.sleep(gap)
        else:
            ser.write(payload)
            ser.flush()

        # 收回显
        deadline = t0 + (args.timeout if args.timeout > 0 else max(3.0, n / 2500 + 2))
        rx = bytearray()
        while time.monotonic() < deadline and len(rx) < n:
            chunk = ser.read(n - len(rx))
            if chunk:
                rx.extend(chunk)
        elapsed = time.monotonic() - t0

        ok = bytes(rx) == payload
        rate = n / elapsed / 1024 if elapsed > 0 else 0
        tag = "✓ PASS" if ok else "✗ FAIL"
        extra = ""
        if not ok:
            lost, first = analyze_diff(payload, bytes(rx))
            extra = f"  丢={lost} ({lost / n * 100:.2f}%)  首位={first}"
            fails += 1

        prefix = f"[{run_idx + 1}/{args.repeat}] " if args.repeat > 1 else ""
        print(f"  {prefix}TX={n}  RX={len(rx)}  {elapsed * 1000:.1f}ms  "
              f"{rate:.2f} KB/s  {tag}{extra}")

        if args.repeat > 1:
            time.sleep(0.3)

    ser.close()

    if args.repeat > 1:
        print(f"\n[i] 总结: {args.repeat - fails}/{args.repeat} PASS")

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
