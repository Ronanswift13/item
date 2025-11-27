#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live LiDAR zone demo: streams real measurements with zone tracking feedback."""

from __future__ import annotations

import sys
import time
from pathlib import Path
import cv2

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from core.new_lidar import get_lidar_distance_cm, NewLidarError
from core.lidar_zone_logic  import (
    CabinetZone,
    LidarZoneTracker,
    LidwarStatus,
    LidarDecision,
)

POLL_INTERVAL_S = 0.2


def build_tracker() -> tuple[LidarZoneTracker, set[int]]:
    """Create the tracker and default authorized cabinet set."""

    zones = [
        CabinetZone(1, 1.05, 1.95),   # cabinet 1: center 1.50 m, width 0.90 m
        CabinetZone(2, 1.95, 2.85),   # cabinet 2: center 2.40 m, width 0.90 m
        CabinetZone(3, 3.405, 4.305), # cabinet 3: center 3.855 m, width 0.90 m (after 0.555 m gap)
        CabinetZone(4, 4.305, 5.205), # cabinet 4: center 4.755 m, width 0.90 m
        CabinetZone(5, 5.205, 6.105), # cabinet 5: center 5.655 m, width 0.90 m
    ]
    tracker = LidarZoneTracker(
        zones=zones,
        movement_threshold_m=0.20,
        static_threshold_m=0.08,
        static_window_s=2.0,
        walk_window_s=1.5,
    )
    authorized = {1, 3}
    return tracker, authorized


def format_decision(decision: LidarDecision) -> str:
    idx = decision.cabinet_index if decision.cabinet_index is not None else "-"
    if decision.distance_m is None:
        dist_text = "None"
    else:
        dist_text = f"{decision.distance_m * 100.0:.1f} cm"
    return (
        f"[zone_live] dist={dist_text} | cabinet={idx} | status={decision.status.name} | "
        f"safe={decision.is_safe} | reason={decision.reason}"
    )


def draw_fusion_hud(frame, fusion_level, vision_zone, d_px, lidar_cm, cabinet_idx, authorized, fusion_reason):
    """
    Draws a status HUD at top-left corner with color:
      - DANGER: red
      - CAUTION / NEAR_LINE / ON_LINE: yellow
      - SAFE / OUTSIDE_SAFE: green
    """

    level_upper = (fusion_level or "").upper()
    zone_upper = (vision_zone or "").upper()

    if level_upper == "DANGER":
        color = (0, 0, 255)
    elif level_upper == "CAUTION" or zone_upper in ("NEAR_LINE", "ON_LINE"):
        color = (0, 255, 255)
    else:
        color = (0, 255, 0)

    d_text = f"{d_px:.2f}px" if d_px is not None else "n/a"
    lidar_text = f"{lidar_cm:.1f}cm" if lidar_cm is not None else "None"
    cab_text = cabinet_idx if cabinet_idx is not None else "-"
    auth_text = authorized if authorized is not None else "-"

    line1 = f"FUSION={level_upper} | VISION_ZONE={zone_upper} | d={d_text}"
    line2 = f"LIDAR={lidar_text} | CAB={cab_text} | AUTH={auth_text} | {fusion_reason}"

    cv2.putText(frame, line1, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, line2, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return frame


def main() -> None:
    tracker, authorized = build_tracker()
    print("Starting lidar_zone_live_demo... Press Ctrl+C to stop.")

    try:
        while True:
            try:
                distance_cm = get_lidar_distance_cm()
            except NewLidarError as exc:
                decision = tracker.update(None, authorized_cabinets=authorized)
                print(f"{format_decision(decision)} | sensor_error={exc}")
                time.sleep(POLL_INTERVAL_S)
                continue

            if distance_cm is None:
                decision = tracker.update(None, authorized_cabinets=authorized)
            else:
                distance_m = distance_cm / 100.0
                decision = tracker.update(distance_m, authorized_cabinets=authorized)

            print(format_decision(decision))
            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping lidar_zone_live_demo...")


if __name__ == "__main__":
    main()
