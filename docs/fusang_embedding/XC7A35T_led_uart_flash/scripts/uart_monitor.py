#!/usr/bin/env python3
"""
a7lite_project UART monitor

监测 A7-Lite (CH340 USB-UART) 的串口输出，带时间戳、可选 hex 显示。

用法:
  python3 scripts/uart_monitor.py                       # 默认 /dev/ttyUSB1 @ 115200
  python3 scripts/uart_monitor.py -p /dev/ttyUSB1
  python3 scripts/uart_monitor.py -b 115200 --hex
  python3 scripts/uart_monitor.py --log logs/uart.log
  python3 scripts/uart_monitor.py --auto                # 自动识别 CH340

退出: Ctrl+C
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

try:
    import serial  # pyserial
    from serial.tools import list_ports
except ImportError:
    sys.stderr.write("缺少 pyserial，请先安装: pip install pyserial\n")
    sys.exit(1)


CH340_VID_PID = (0x1A86, 0x7523)  # QinHeng CH340


def autodetect_ch340() -> str | None:
    for p in list_ports.comports():
        if p.vid == CH340_VID_PID[0] and p.pid == CH340_VID_PID[1]:
            return p.device
    return None


def open_serial(port: str, baud: int) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
        rtscts=False,
        dsrdtr=False,
        xonxoff=False,
    )


def format_line(buf: bytes, show_hex: bool) -> str:
    if show_hex:
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in buf)
        hex_part = " ".join(f"{b:02X}" for b in buf)
        return f"{hex_part}    |{ascii_part}|"
    try:
        return buf.decode("utf-8", errors="replace").rstrip("\r\n")
    except Exception:
        return repr(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description="A7-Lite UART monitor")
    ap.add_argument("-p", "--port", default="/dev/ttyUSB1",
                    help="串口设备 (默认: /dev/ttyUSB1, CH340)")
    ap.add_argument("-b", "--baud", type=int, default=115200, help="波特率 (默认 115200)")
    ap.add_argument("--hex", action="store_true", help="按 hex+ASCII 显示")
    ap.add_argument("--no-ts", action="store_true", help="不显示时间戳")
    ap.add_argument("--log", help="同时写入日志文件 (追加)")
    ap.add_argument("--auto", action="store_true", help="自动检测 CH340 (覆盖 -p)")
    args = ap.parse_args()

    port = args.port
    if args.auto:
        detected = autodetect_ch340()
        if not detected:
            print("[!] 未检测到 CH340 (1A86:7523)，请确认 A7-Lite USB-UART 已连接", file=sys.stderr)
            return 2
        port = detected
        print(f"[i] 自动检测到 CH340: {port}")

    if not os.path.exists(port):
        print(f"[!] 串口不存在: {port}", file=sys.stderr)
        return 2

    try:
        ser = open_serial(port, args.baud)
    except serial.SerialException as e:
        print(f"[!] 打开失败 ({port}): {e}", file=sys.stderr)
        print("    提示: sudo chmod 666 " + port, file=sys.stderr)
        return 2

    log_fp = None
    if args.log:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        log_fp = open(args.log, "a", buffering=1, encoding="utf-8")
        log_fp.write(f"\n===== {dt.datetime.now().isoformat()} open {port} @ {args.baud} =====\n")

    print(f"[i] 监听 {port} @ {args.baud} 8N1 (Ctrl+C 退出)")
    line_buf = bytearray()
    last_rx = time.monotonic()

    def emit(payload: bytes) -> None:
        text = format_line(payload, args.hex)
        if not args.no_ts:
            ts = dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            line = f"[{ts}] {text}"
        else:
            line = text
        print(line, flush=True)
        if log_fp:
            log_fp.write(line + "\n")

    try:
        while True:
            chunk = ser.read(256)
            now = time.monotonic()
            if chunk:
                line_buf.extend(chunk)
                last_rx = now
                if args.hex:
                    # hex 模式按 16 字节一组刷出
                    while len(line_buf) >= 16:
                        emit(bytes(line_buf[:16]))
                        del line_buf[:16]
                else:
                    # 文本模式按行刷出
                    while True:
                        nl = line_buf.find(b"\n")
                        if nl < 0:
                            break
                        emit(bytes(line_buf[: nl + 1]))
                        del line_buf[: nl + 1]
            else:
                # 空闲超过 50ms 就把残留 flush 出来，避免半行卡住
                if line_buf and (now - last_rx) > 0.05:
                    emit(bytes(line_buf))
                    line_buf.clear()
    except KeyboardInterrupt:
        print("\n[i] 退出")
        return 0
    finally:
        try:
            if line_buf:
                emit(bytes(line_buf))
            ser.close()
        except Exception:
            pass
        if log_fp:
            log_fp.close()


if __name__ == "__main__":
    sys.exit(main())
