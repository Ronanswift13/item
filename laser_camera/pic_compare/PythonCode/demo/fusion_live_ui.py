#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fusion live UI demo:
- Reads camera frames, runs motion comparator to extract bboxes and geometry.
- Reads LiDAR distance via core.lidar_bridge.
- Fuses vision + LiDAR using core.vision_lidar_fusion and overlays HUD.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Tuple

import cv2

DOWNSCALE_FACTOR = 0.4  # e.g. 1920x1080 -> 768x432
# Adjust sys.path to include project root for imports
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # PythonCode 目录
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core import config  # noqa: E402
from core.camera_driver import CameraDriver  # noqa: E402
from core.image_comparator import ImageComparator  # noqa: E402
from core.distance_compare_geometry import (  # noqa: E402
    build_line_points_from_config,
    foot_from_bbox,
    signed_distance_to_line,
    classify_distance_zone,
)
from core.lidar_bridge import read_lidar_once  # noqa: E402
from core.vision_lidar_fusion import fuse_vision_and_lidar, FusionLevel  # noqa: E402
from core.vision_safety_logic import (  # noqa: E402
    VisionSafetyResult,
    SafetyLevel,
    SafetyZone,
)

_last_lidar_snapshot = None
_last_lidar_time = 0.0


def pick_main_bbox(bboxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int] | None:
    """从多个 bbox 中挑一个“主目标”：y+h 最大（画面最低的那个）。"""

    if not bboxes:
        return None
    return max(bboxes, key=lambda b: b[1] + b[3])


def main() -> None:
    print("=== fusion_live_ui ===")

    cam_cfg = config.CAMERA
    dist_cfg = config.DISTANCE_COMPARE

    if cam_cfg.use_rtsp:
        print(f"[INFO] Using RTSP camera: {cam_cfg.rtsp_url}")
    else:
        print(f"[INFO] Using USB camera index={cam_cfg.device_index}")

    camera = CameraDriver(cam_cfg)
    if not camera.open():
        print("[ERROR] Failed to open camera.")
        return

    comparator = ImageComparator()

    frame = camera.get_frame()
    if frame is None:
        print("[ERROR] Cannot read first frame.")
        camera.release()
        return

    def parse_compare(res):
        local_bboxes: List[Tuple[int, int, int, int]] = []
        local_motion: float = 0.0
        if isinstance(res, (tuple, list)):
            if len(res) == 3:
                local_bboxes, local_motion, _ = res
            elif len(res) == 2:
                local_bboxes, local_motion = res
            elif len(res) == 1:
                local_bboxes = res[0]
        elif isinstance(res, dict):
            local_bboxes = res.get("bboxes", []) or []
            motion_raw = res.get("motion_score", 0.0)
            try:
                local_motion = float(motion_raw)
            except (TypeError, ValueError):
                local_motion = 0.0
        elif res is None:
            local_bboxes = []
            local_motion = 0.0
        else:
            local_bboxes = res  # type: ignore[assignment]
        return local_bboxes, local_motion

    h_full, w_full = frame.shape[:2]
    w_small = int(w_full * DOWNSCALE_FACTOR)
    h_small = int(h_full * DOWNSCALE_FACTOR)
    frame_small = cv2.resize(frame, (w_small, h_small))

    h, w = frame_small.shape[:2]
    p1, p2 = build_line_points_from_config(w, h, dist_cfg)
    print(f"[INFO] frame size (small) = {w}x{h}")
    print(f"[INFO] yellow line p1={p1}, p2={p2}")

    cv2.namedWindow("fusion_live_ui", cv2.WINDOW_NORMAL)

    PRINT_INTERVAL = 10
    VISION_INTERVAL =2 # 每 2帧跑一次运动检测
    last_bboxes: List[Tuple[int, int, int, int]] = []
    last_motion_score: float = 0.0
    frame_id = 0
    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                print("[WARN] Failed to read frame, break.")
                break

            frame_id += 1
            h_full, w_full = frame.shape[:2]
            w_small = int(w_full * DOWNSCALE_FACTOR)
            h_small = int(h_full * DOWNSCALE_FACTOR)
            frame_small = cv2.resize(frame, (w_small, h_small))

            work = frame_small
            h, w = work.shape[:2]
            vis = work.copy()

            if frame_id % VISION_INTERVAL == 0:
                result = comparator.compare(work)
                last_bboxes, last_motion_score = parse_compare(result)

            bboxes = last_bboxes
            motion_score = last_motion_score
            has_person = len(bboxes) > 0

            # --- Geometry: yellow line & foot distance ---
            cv2.line(
                vis,
                (int(p1[0]), int(p1[1])),
                (int(p2[0]), int(p2[1])),
                (0, 255, 255),
                3,
            )
            cv2.putText(
                vis,
                "YELLOW LINE",
                (int(p1[0]) + 10, int(p1[1]) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

            main_bbox = pick_main_bbox(bboxes)
            d_px: float | None = None
            zone_text = "NO_TARGET"
            vision_result = VisionSafetyResult(
                level=SafetyLevel.SAFE,
                zone=SafetyZone.OUTSIDE_SAFE,
                target_box=None,
                geom_distance_px=0.0,
                primary_bbox=None,
            )

            if main_bbox:
                x, y, bw, bh = main_bbox
                fx, fy = foot_from_bbox(main_bbox)
                d_px = signed_distance_to_line((fx, fy), p1, p2)
                zone_text = classify_distance_zone(d_px, dist_cfg)

                if zone_text in ("OUTSIDE_SAFE", "NEAR_LINE"):
                    vision_level = SafetyLevel.SAFE
                    vision_zone = SafetyZone.OUTSIDE_SAFE
                elif zone_text == "ON_LINE":
                    vision_level = SafetyLevel.CAUTION
                    vision_zone = SafetyZone.ON_LINE
                else:
                    vision_level = SafetyLevel.DANGER
                    vision_zone = SafetyZone.INSIDE_DANGER

                vision_result = VisionSafetyResult(
                    level=vision_level,
                    zone=vision_zone,
                    target_box=None,
                    geom_distance_px=d_px,
                    primary_bbox=main_bbox,
                )

                cv2.rectangle(vis, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
                cv2.circle(vis, (int(fx), int(fy)), 6, (0, 0, 255), -1)

            # --- LiDAR sampling with simple cache ---
            now = time.time()
            global _last_lidar_snapshot, _last_lidar_time
            if now - _last_lidar_time >= 0.2 or _last_lidar_snapshot is None:
                _last_lidar_snapshot = read_lidar_once()
                _last_lidar_time = now

            lidar_snapshot = _last_lidar_snapshot
            lidar_cm = (
                lidar_snapshot.distance_cm
                if (lidar_snapshot and lidar_snapshot.ok and lidar_snapshot.distance_cm is not None)
                else None
            )

            fusion = fuse_vision_and_lidar(vision_result, lidar_cm)

            if fusion.level == FusionLevel.DANGER:
                hud_color = (0, 0, 255)
            elif fusion.level == FusionLevel.CAUTION:
                hud_color = (0, 255, 255)
            else:
                hud_color = (0, 255, 0)

            if lidar_cm is None:
                lidar_text = "None"
            else:
                lidar_text = f"{lidar_cm:.1f}cm"

            cab_idx = "-"
            authorized = "-"

            d_text = f"{d_px:.2f}px" if d_px is not None else "n/a"
            hud = (
                f"FUSION: {fusion.level} | "
                f"VISION_ZONE={zone_text} | "
                f"d={d_text} | "
                f"LIDAR={lidar_text} | CAB={cab_idx} | AUTH={authorized}"
            )

            cv2.putText(
                vis,
                hud,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                hud_color,
                2,
            )

            # 在左下角标出当前帧号，便于确认画面是否在更新
            cv2.putText(
                vis,
                f"frame={frame_id}",
                (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            if frame_id % PRINT_INTERVAL == 0:
                print(
                    f"[FUSION_UI] frame={frame_id:05d} "
                    f"zone={zone_text:>13} "
                    f"d_px={(d_px if d_px is not None else float('nan')):7.2f} "
                    f"motion={motion_score:.4f} boxes={len(bboxes)} "
                    f"lidar={lidar_text} fusion={fusion.level} reason={fusion.reason}"
                )

            cv2.imshow("fusion_live_ui", vis)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[INFO] Quit by user.")
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
