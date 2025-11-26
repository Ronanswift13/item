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
from core import config


@dataclass
class VisionStatus:
    level: str
    zone: str
    motion_score: float
    geom_distance_px: float
    num_boxes: int
    primary_bbox: Optional[Tuple[int, int, int, int]] = None


def _draw_overlay(
    frame,
    status: VisionStatus,
    line_p1: Tuple[float, float],
    line_p2: Tuple[float, float],
) -> None:
    """Draw yellow line, primary bbox, and HUD text."""
    h, w = frame.shape[:2]

    # Draw yellow line (can be slanted)
    cv2.line(
        frame,
        (int(line_p1[0]), int(line_p1[1])),
        (int(line_p2[0]), int(line_p2[1])),
        (0, 255, 255),
        2,
    )

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
        fx = int(x + bw / 2)
        fy = int(y + bh)
        cv2.circle(frame, (fx, fy), 6, (0, 0, 255), -1)

    # HUD bar
    bar_h = 40
    if status.level == "DANGER":
        bar_color = (0, 0, 255)
    elif status.level == "CAUTION":
        bar_color = (0, 255, 255)
    else:
        bar_color = (0, 200, 0)

    cv2.rectangle(frame, (0, 0), (w, bar_h), bar_color, thickness=-1)
    text = (
        f"LEVEL={status.level} ZONE={status.zone} "
        f"d={status.geom_distance_px:.2f}px "
        f"motion={status.motion_score:.4f} "
        f"boxes={status.num_boxes}"
    )
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

    cam = CameraDriver(config.CAMERA)
    if not cam.open():
        print("[VISION_RT] ERROR: cannot open camera.")
        return

    comparator = ImageComparator(mode="frame_diff")

    # Read one frame to get dimensions
    ok, first_frame = cam.read()
    if not ok or first_frame is None:
        print("[VISION_RT] ERROR: failed to read initial frame for size.")
        cam.close()
        return
    fh, fw = first_frame.shape[:2]

    safety_logic = VisionSafetyLogic(frame_width=fw, frame_height=fh)

    frame_counter = 0
    try:
        while True:
            ok, frame = cam.read()
            if not ok or frame is None:
                print("[VISION_RT] WARNING: failed to read frame.")
                time.sleep(0.05)
                continue

            frame_counter += 1

            # Motion detection
            result = comparator.compare(frame)

            # Robust parsing of comparator output (aligned with motion demo)
            bboxes: List[Tuple[int, int, int, int]] = []
            motion_score: float = 0.0
            if isinstance(result, (tuple, list)):
                if len(result) == 3:
                    bboxes, motion_score, _ = result
                elif len(result) == 2:
                    bboxes, motion_score = result
                elif len(result) == 1:
                    bboxes = result[0]
                else:
                    bboxes = result[0]
                    motion_score = result[1]
            elif isinstance(result, dict):
                bboxes = result.get("bboxes", []) or []
                motion_raw = result.get("motion_score", 0.0)
                try:
                    motion_score = float(motion_raw)
                except (TypeError, ValueError):
                    motion_score = 0.0
            elif result is None:
                bboxes = []
                motion_score = 0.0
            else:
                bboxes = result  # type: ignore[assignment]

            # Safety evaluation (distance-based)
            level, zone, d_px, primary_bbox = safety_logic.evaluate_distance(bboxes, motion_score)

            status = VisionStatus(
                level=level.name if hasattr(level, "name") else str(level),
                zone=zone.name if hasattr(zone, "name") else str(zone),
                motion_score=motion_score,
                geom_distance_px=d_px,
                num_boxes=len(bboxes),
                primary_bbox=primary_bbox,
            )

            # HUD overlay and drawing
            _draw_overlay(frame, status, safety_logic.line_p1, safety_logic.line_p2)

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
