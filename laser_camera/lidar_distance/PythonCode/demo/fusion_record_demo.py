from __future__ import annotations

import csv
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time

from datetime import datetime
from core.new_lidar import get_lidar_distance_cm as get_lidar_distance
from core.vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode
from core.fusion_logic import fuse_sensors

def build_dummy_vision() -> VisionState:
    return VisionState(
        person_present=True,
        line_position=LinePosition.BEYOND_LINE,
        orientation=BodyOrientation.FACING_CABINET,
        gesture=GestureCode.NONE,
        timestamp=datetime.now(),
    )

def run_record_demo() -> None:
    csv_path = "fusion_log.csv"

    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                [
                    "timestamp_iso",
                    "distance_cm",
                    "person_present",
                    "line_position",
                    "orientation",
                    "gesture",
                    "too_close",
                    "warning_level",
                ]
            )

    while True:
        distance = get_lidar_distance()
        vision = build_dummy_vision()
        fused = fuse_sensors(distance, vision)

        with open(csv_path, "a", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                [
                    fused.timestamp.isoformat(),
                    fused.distance_cm,
                    vision.person_present,
                    vision.line_position.name,
                    vision.orientation.name,
                    vision.gesture.name,
                    fused.too_close,
                    fused.warning_level,
                ]
            )

        print(
            f"[record] {fused.timestamp} dist={fused.distance_cm} cm | "
            f"too_close={fused.too_close} | warning={fused.warning_level}"
        )
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        run_record_demo()
    except KeyboardInterrupt:
        print("\nfusion_record_demo stopped by user")