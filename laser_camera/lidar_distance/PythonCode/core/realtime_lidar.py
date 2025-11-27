#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 TOF 激光雷达的实时机位数据源适配器。"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from collections import deque
from typing import Iterable, Iterator, Optional, Set
from pathlib import Path

import serial

if __package__:
    from .cabinet_positioning import CABINETS
    from .lidar_tof import ToFLidar, SerialException
    from .lidar_zone_logic import CabinetZone, LidarDecision, LidarZoneTracker
else:
    # Allow running as a standalone script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cabinet_positioning import CABINETS  # type: ignore
    from lidar_tof import ToFLidar, SerialException  # type: ignore
    from lidar_zone_logic import CabinetZone, LidarDecision, LidarZoneTracker  # type: ignore

@dataclass
class LidarMeasurement:
    """单次雷达测量结果，包含距离与机位信息。"""

    distance_m: float                  # 当前平均距离（米），无效时可为负数
    cabinet_index: Optional[int]       # 映射后的机位编号，未知或无效时为 None
    raw_valid: bool                    # 原始测量是否有效
    timestamp: float                   # Unix 时间戳（秒）

# 记录当前配置中可用的机位编号，供调试参考
AVAILABLE_CABINETS: Iterable[int] = tuple(CABINETS.keys())


class RealtimeLidarSource:
    """将 TOF 激光雷达测距结果转换为机位编号的实时数据源。"""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
        window_size: int = 5,
    ) -> None:
        """
        Args:
            port: 串口名，例如 COM5、/dev/tty.usbserial-1120、/dev/tty./dev/tty.usbserial-1110	 等。
            baudrate: 串口波特率，默认 9600。
            timeout: 串口读取超时时间（秒）。
            window_size: 滑动平均窗口长度，用于平滑距离抖动。
        """

        self._lidar = ToFLidar(port, baudrate=baudrate, timeout=timeout)
        self._window: deque[float] = deque(maxlen=max(1, window_size))
        self._last_average: Optional[float] = None
        zones = [CabinetZone(idx, bounds[0], bounds[1]) for idx, bounds in sorted(CABINETS.items())]
        self._zone_tracker = LidarZoneTracker(zones)
        self._authorized_cabinets: Set[int] = set()
        self._last_decision: Optional[LidarDecision] = None

    def close(self) -> None:
        """关闭内部雷达实例，释放串口资源。"""

        try:
            self._lidar.close()
        except Exception:
            pass

    def __enter__(self) -> "RealtimeLidarSource":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _read_average_distance(self) -> Optional[float]:
        """从雷达读取一次数据并更新滑动平均，返回当前平均距离（米）。"""

        try:
            measurement = self._lidar.read_measurement()
        except serial.SerialException as exc:  # type: ignore[attr-defined]
            print(f"串口读取异常：{exc}")
            return None

        if measurement is None:
            return None

        distance_m, _strength = measurement
        if distance_m > 0:
            self._window.append(distance_m)

        if not self._window:
            return None

        avg = sum(self._window) / len(self._window)
        self._last_average = avg
        return avg

    @property
    def last_average_distance(self) -> Optional[float]:
        """返回最近一次计算得到的平均距离（米）。"""

        return self._last_average

    def set_authorized_cabinets(self, cabinet_ids: Iterable[int]) -> None:
        """更新允许检修的机位集合，供后续扩展更丰富的 LiDAR 决策。"""

        self._authorized_cabinets = set(cabinet_ids)

    @property
    def last_decision(self) -> Optional[LidarDecision]:
        """最近一次 LiDAR 决策结果（未被 UI 使用，但便于未来扩展）。"""

        return self._last_decision

    def read_measurement_once(self) -> LidarMeasurement:
        """读取一次测量并封装为 LidarMeasurement。

        该方法会调用内部的 `_read_average_distance` 更新滑动平均，并通过
        `LidarZoneTracker` 推断出当前对应的机位索引。
        """
        avg_distance = self._read_average_distance()
        ts = time.time()

        if avg_distance is None or avg_distance <= 0:
            self._last_decision = self._zone_tracker.update(
                None,
                authorized_cabinets=self._authorized_cabinets,
                now=ts,
            )
            # 无有效距离时，用负数占位，并将机位号标记为 None
            return LidarMeasurement(
                distance_m=-1.0,
                cabinet_index=None,
                raw_valid=False,
                timestamp=ts,
            )

        self._last_decision = self._zone_tracker.update(
            avg_distance,
            authorized_cabinets=self._authorized_cabinets,
            now=ts,
        )
        cabinet_id = self._last_decision.cabinet_index
        return LidarMeasurement(
            distance_m=avg_distance,
            cabinet_index=cabinet_id,
            raw_valid=True,
            timestamp=ts,
        )

    def stream_measurements(self, interval_sec: float = 0.1) -> Iterator[LidarMeasurement]:
        """构造一个无限迭代器，每次迭代返回一条完整的测量结果。"""

        while True:
            measurement = self.read_measurement_once()
            yield measurement
            time.sleep(interval_sec)

    def stream(self, interval_sec: float = 0.1) -> Iterator[Optional[int]]:
        """
        构造一个无限迭代器，每次迭代返回一个机位编号（或 None）。

        Args:
            interval_sec: 连续两次测量之间的休眠时间（秒），用于控制轮询频率。
        """

        while True:
            measurement = self.read_measurement_once()
            yield measurement.cabinet_index
            time.sleep(interval_sec)


def main() -> None:
    """简单示例：读取串口并打印 20 次机位判断结果。"""

    port = input("串口名（如 COM5 / /dev/ttyUSB0）: ").strip()
    if not port:
        print("未提供串口名，退出。")
        return

    source = RealtimeLidarSource(port)
    generator = source.stream_measurements(interval_sec=0.1)

    print(f"当前配置机位: {list(AVAILABLE_CABINETS)}")
    print("开始读取（Ctrl+C 结束）...")
    try:
        for step in range(1, 21):
            try:
                measurement = next(generator)
            except serial.SerialException as exc:  # type: ignore[attr-defined]
                print(f"串口异常：{exc}")
                break

            if measurement.raw_valid:
                distance_text = f"{measurement.distance_m:.3f} m"
                cabinet_text = (
                    str(measurement.cabinet_index)
                    if measurement.cabinet_index is not None
                    else "None"
                )
            else:
                distance_text = "无有效距离"
                cabinet_text = "None"

            print(
                f"[{step:02d}] 机位: {cabinet_text} | "
                f"平均距离: {distance_text} | "
                f"时间戳: {measurement.timestamp:.3f}"
            )
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n用户中断，结束采集。")
    finally:
        source.close()
        print("串口已关闭。")


if __name__ == "__main__":
    main()
