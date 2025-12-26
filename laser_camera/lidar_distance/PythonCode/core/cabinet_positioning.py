#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 TOF 激光雷达的简易机位判定脚本。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from collections import deque
from typing import Deque, Optional

import serial

if __package__:
    from .lidar_tof import ToFLidar, _default_port, ToFLidarClass
else:
    # 允许直接脚本运行：python core/cabinet_positioning.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.lidar_tof import ToFLidar, _default_port, ToFLidarClass  # type: ignore

lidar: Optional[ToFLidarClass] = None


SerialException = getattr(serial, "SerialException", Exception)

# 机位编号 -> (距离下限, 距离上限)；
# 以下为示例值，现场部署需按实测调整
CABINETS: dict[int, tuple[float, float]] = {
    1: (1.8, 2.2),
    2: (3.3, 3.7),
    3: (4.8, 5.2),
    
    
}

# 滑动平均窗口长度，平滑距离波动
WINDOW_SIZE = 5


def distance_to_cabinet(distance_m: float) -> Optional[int]:
    """
    根据距离值匹配机位编号。

    Args:
        distance_m: 以米为单位的距离，通常来自滑动平均结果。
    Returns:
        命中的机位编号，若距离不在任何区间内则返回 None。
    """
    for cabinet_id, (d_min, d_max) in CABINETS.items():
        if d_min <= distance_m <= d_max:
            return cabinet_id
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="TOF 雷达机位判定脚本")
    parser.add_argument("--port", default=_default_port(), help="串口名，例如 COM5 或 /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=115200, help="串口波特率，默认 115200")
    parser.add_argument("--timeout", type=float, default=1.0, help="串口读超时（秒），默认 1.0")
    args = parser.parse_args()

    measurements: Deque[float] = deque(maxlen=WINDOW_SIZE)
    lidar: Optional[ToFLidarClass] = None

    try:
        lidar = ToFLidar(args.port, baudrate=args.baudrate, timeout=args.timeout)
        print("开始机位监测（Ctrl+C 退出）")

        while True:
            measurement = lidar.read_measurement() if lidar else None
            if measurement is None:
                print("未读取到有效距离")
                time.sleep(0.1)
                continue

            distance_m, strength = measurement
            measurements.append(distance_m)
            avg_distance = sum(measurements) / len(measurements)
            cabinet_id = distance_to_cabinet(avg_distance)
            cabinet_display = cabinet_id if cabinet_id is not None else "None"

            print(
                f"原始距离: {distance_m:.3f} m | 平均距离: {avg_distance:.3f} m | 机位: {cabinet_display} | 强度: {strength}"
            )
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("退出程序")
    except SerialException as exc:
        print(f"串口错误：{exc}")
    except Exception as exc:
        print(f"运行异常：{exc}")
    finally:
        if lidar is not None:
            lidar.close()
        print("串口已关闭")


if __name__ == "__main__":
    main()
