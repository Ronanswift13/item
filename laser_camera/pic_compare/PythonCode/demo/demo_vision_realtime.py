#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time vision safety demo for pic_compare.

Uses:
  - core.camera_driver.CameraDriver
  - core.image_comparator.ImageComparator
  - core.vision_safety_logic.VisionSafetyLogic

Displays:
  - live video
  - primary bbox from safety logic
  - yellow line position
  - HUD with SAFE / CAUTION / DANGER
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2

# ---------------------------------------------------------------------------
# sys.path fix – MUST be before any "from core ..." imports
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # /PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.camera_driver import CameraDriver
from core.image_comparator import ImageComparator
from core.vision_safety_logic import VisionSafetyLogic
from core.distance_compare_config import YELLOW_LINE_Y_RATIO


@dataclass
class VisionStatus:
    level: str
    zone: str
    motion_score: float
    geom_distance_px: float
    primary_bbox: Optional[Tuple[int, int, int, int]] = None


def _draw_overlay(
    frame,
    status: VisionStatus,
    y_line: int,
) -> None:
    """Draw yellow line, primary bbox, and HUD text."""
    h, w = frame.shape[:2]

    # Draw yellow line
    cv2.line(frame, (0, y_line), (w, y_line), (0, 255, 255), 2)

    # Draw primary bbox if present
    if status.primary_bbox is not None:
        x, y, bw, bh = status.primary_bbox
        if status.level == "DANGER":
            color = (0, 0, 255)
        elif status.level == "CAUTION":
            color = (0, 255, 255)
        else:
            color = (0, 200, 0)
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)

    # HUD bar
    bar_h = 40
    if status.level == "DANGER":
        bar_color = (0, 0, 255)
    elif status.level == "CAUTION":
        bar_color = (0, 255, 255)
    else:
        bar_color = (0, 200, 0)

    cv2.rectangle(frame, (0, 0), (w, bar_h), bar_color, thickness=-1)
    text = f"LEVEL={status.level} ZONE={status.zone} d={status.geom_distance_px:.1f}px motion={status.motion_score:.4f}"
    cv2.putText(
        frame,
        text,
        (10, int(bar_h * 0.7)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )


def main() -> None:
    print("=== demo_vision_realtime.py ===")
    print("Press 'q' to quit.")

    cam = CameraDriver()
    if not cam.open():
        print("[VISION_RT] ERROR: cannot open camera.")
        return

    # Read one frame to get dimensions
    first_frame = cam.get_frame()
    if first_frame is None:
        print("[VISION_RT] ERROR: failed to read initial frame for size.")
        cam.close()
        return
    fh, fw = first_frame.shape[:2]

    comparator = ImageComparator(mode="frame_diff")
    safety_logic = VisionSafetyLogic(frame_width=fw, frame_height=fh)

    frame_counter = 0
    try:
        while True:
            frame = cam.get_frame()
            if frame is None:
                print("[VISION_RT] WARNING: failed to read frame.")
                time.sleep(0.05)
                continue

            frame_counter += 1

            # Motion detection
            comp_result = comparator.compare(frame)
            motion_score = float(comp_result.get("motion_score", 0.0))
            bboxes = comp_result.get("bboxes", [])

            # Safety evaluation
            result = safety_logic.evaluate(frame.shape, bboxes)
            primary_bbox = getattr(result, "primary_bbox", None)

            status = VisionStatus(
                level=result.level.name if hasattr(result.level, "name") else str(result.level),
                zone=result.zone.name if hasattr(result.zone, "name") else str(result.zone),
                motion_score=motion_score,
                geom_distance_px=getattr(result, "geom_distance_px", 0.0),
                primary_bbox=primary_bbox,
            )

            y_line = int(YELLOW_LINE_Y_RATIO * frame.shape[0])
            _draw_overlay(frame, status, y_line)

            # Log
            print(
                f"[VISION_RT] frame={frame_counter:04d} "
                f"level={status.level} zone={status.zone} "
                f"d={status.geom_distance_px:.1f}px bbox={status.primary_bbox}"
            )

            cv2.imshow("Vision Safety (Realtime)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()
        print("=== demo_vision_realtime.py finished ===")


if __name__ == "__main__":
    main()
