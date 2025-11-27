#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quarantined LiDAR cabinet test.

- 只依赖 core.new_lidar 读距离，不改动任何现有逻辑文件
- 内部自带 CabinetZone 定义，不从 core.lidar_zone_logic 导入，避免“污染”
    1: 1.05 ~ 1.95 m
    2: 1.95 ~ 2.85 m
    3: 3.405 ~ 4.305 m
    4: 4.305 ~ 5.205 m
    5: 5.205 ~ 6.105 m
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

CURRENT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT.parent.parent  # .../PythonCode
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.new_lidar import get_lidar_distance_cm, NewLidarError

# 轮询间隔（秒）
POLL_INTERVAL_S: float = 0.3


@dataclass
class CabinetZone:
    """简单的机柜距离区间定义（完全本地，不依赖其他模块）"""
    index: int
    start_m: float
    end_m: float

    def contains(self, d_m: float) -> bool:
        return self.start_m <= d_m < self.end_m

CABINET_ZONES: List[CabinetZone] = [
    CabinetZone(1, 1.05, 1.95),   # cabinet 1: center 1.50 m, width 0.90 m
    CabinetZone(2, 1.95, 2.85),   # cabinet 2: center 2.40 m, width 0.90 m
    CabinetZone(3, 3.405, 4.305), # cabinet 3: center 3.855 m, width 0.90 m (after 0.555 m gap)
    CabinetZone(4, 4.305, 5.205), # cabinet 4: center 4.755 m, width 0.90 m
    CabinetZone(5, 5.205, 6.105), # cabinet 5: center 5.655 m, width 0.90 m
]

# 默认授权机柜（你可以按现场改，比如 {1, 3} 或 {2, 4, 5}）
AUTHORIZED_CABINETS = {1, 3}


def classify_cabinet(distance_m: float) -> Optional[CabinetZone]:
    """根据距离找到落在哪个机柜区间，没有则返回 None。"""
    for zone in CABINET_ZONES:
        if zone.contains(distance_m):
            return zone
    return None


def format_status(
    raw_cm: Optional[float],
    zone: Optional[CabinetZone],
    error: Optional[Exception] = None,
) -> str:
    """格式化一行输出，不写任何文件，只是打印。"""

    if raw_cm is None:
        dist_txt = "None"
    else:
        dist_txt = f"{raw_cm:.1f} cm"

    if zone is None:
        cabinet_idx = "-"
        cabinet_state = "NO_CABINET"
        authorized = "-"
    else:
        cabinet_idx = zone.index
        authorized = cabinet_idx in AUTHORIZED_CABINETS
        cabinet_state = "AUTHORIZED" if authorized else "UNAUTHORIZED"

    parts = [
        "[LIDAR_QTEST]",
        f"dist={dist_txt}",
        f"cabinet={cabinet_idx}",
        f"cabinet_state={cabinet_state}",
        f"authorized={authorized}",
    ]

    if error is not None:
        parts.append(f"sensor_error={repr(error)}")

    return " | ".join(str(p) for p in parts)


def main() -> None:
    print("Starting lidar_cabinet_quarantine_test... Ctrl+C to stop.")
    print("Zones:")
    for z in CABINET_ZONES:
        print(f"  - cabinet {z.index}: {z.start_m:.3f} m ~ {z.end_m:.3f} m")
    print(f"Authorized cabinets: {sorted(AUTHORIZED_CABINETS)}\n")

    try:
        while True:
            try:
                distance_cm = get_lidar_distance_cm()
                if distance_cm is None:
                    line = format_status(None, None)
                    print(line)
                    time.sleep(POLL_INTERVAL_S)
                    continue

                distance_m = distance_cm / 100.0
                zone = classify_cabinet(distance_m)
                line = format_status(distance_cm, zone)
                print(line)

            except NewLidarError as exc:
                # LiDAR 读失败：不更新任何外部状态，只打印出来
                line = format_status(None, None, error=exc)
                print(line)

            time.sleep(POLL_INTERVAL_S)

    except KeyboardInterrupt:
        print("\nStopping lidar_cabinet_quarantine_test...")


if __name__ == "__main__":
    main()
