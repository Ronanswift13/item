# new_lidar_driver.py
"""
激光测距模块驱动：
提供一个函数 get_lidar_distance_cm()，返回距离（单位：cm，float）。
"""

from pathlib import Path
import sys
from typing import Optional

import serial
from time import sleep

if __package__:
    from .config import LIDAR
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import LIDAR  # type: ignore

BAUD = LIDAR.baudrate
DEFAULT_TIMEOUT = LIDAR.timeout

# 单次测距指令
SINGLE_MEASURE_CMD = bytes([0x80, 0x06, 0x02, 0x78])


class NewLidarError(Exception):
    """激光测距模块返回错误或通讯异常"""
    pass


def _read_one_frame(ser: serial.Serial) -> bytes:
    """
    从串口读一帧数据（最多 32 字节），原样返回。
    这里使用 read_until 以 'N' 作为结束符（协议结尾），避免只读到半帧。
    """
    data = ser.read_until(expected=b"N", size=32)
    if not data:
        raise NewLidarError("no data from device")

    # 简单长度检查：协议典型是 11 字节左右
    if len(data) < 5:
        raise NewLidarError(f"frame too short: {data!r}")
    return data


def _parse_distance_from_frame(frame: bytes) -> float:
    """
    从返回帧中解析距离（单位：米），再返回 float。
    约定：有效 ASCII 区间是 frame[3:-1]
    """
    ascii_part = frame[3:-1].decode(errors="ignore").strip()

    if ascii_part.startswith("ERR--"):
        raise NewLidarError(f"module error: {ascii_part}")

    # 正常情况如 "002.384"
    try:
        dist_m = float(ascii_part)
    except ValueError as e:
        raise NewLidarError(f"cannot parse distance from {ascii_part!r}") from e

    return dist_m


def _resolve_port(port: Optional[str]) -> str:
    """如果显式传入 port 则直接使用；否则使用配置中的默认端口。"""

    return port or LIDAR.port


def get_lidar_distance_cm(port: Optional[str] = None, baud: int = BAUD, timeout: float = DEFAULT_TIMEOUT) -> float:
    """
    对外暴露的主函数：发送单次测距命令，返回距离（厘米）。
    每次调用会打开串口 -> 测一次 -> 关闭串口。
    内部会做多次尝试，以提高在偶发超时时的鲁棒性。
    """
    resolved_port = _resolve_port(port)
    resolved_baud = baud if baud is not None else LIDAR.baudrate
    resolved_timeout = timeout if timeout is not None else LIDAR.timeout

    try:
        ser = serial.Serial(resolved_port, resolved_baud, timeout=resolved_timeout)
    except Exception as e:  # pyserial may not expose SerialException on all platforms
        print(f"[LIDAR] failed to open {LIDAR.port}: {e}")
        raise
    try:
        last_err: Optional[NewLidarError] = None
        for attempt in range(5):
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # 发命令
            ser.write(SINGLE_MEASURE_CMD)
            ser.flush()

            try:
                frame = _read_one_frame(ser)
                dist_m = _parse_distance_from_frame(frame)
                return dist_m * 100.0  # 转成 cm 返回
            except NewLidarError as e:
                last_err = e
                # 小睡一下再重试，避免设备忙碌
                sleep(0.1)
                continue

        if last_err is not None:
            raise last_err
        raise NewLidarError("unknown error in get_lidar_distance_cm()")
    finally:
        ser.close()


if __name__ == "__main__":
    # 连测 5 次
    print("Self-test: get_lidar_distance_cm() 5 times")
    for i in range(5):
        try:
            d_cm = get_lidar_distance_cm()
            print(f"{i+1}: {d_cm:.1f} cm")
        except NewLidarError as e:
            print(f"{i+1}: ERROR -> {e}")
