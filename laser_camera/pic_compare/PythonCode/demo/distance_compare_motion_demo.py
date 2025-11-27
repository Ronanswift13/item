#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
distance_compare_motion_demo.py

实时 OpenCV demo:
- 使用 config.CAMERA 打开摄像头（USB / RTSP 都可）
- 每帧画出配置里的斜黄线
- 利用运动检测得到 bbox，取每个 bbox 的“脚底点”
- 计算脚到底线的带符号距离，判别安全区域：
    OUTSIDE_SAFE / ON_LINE / INSIDE_DANGER / NEAR_LINE
- 在画面左上角 HUD + 终端打印结果
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import time
from typing import List, Tuple

import cv2

# ---------------------------------------------------------------------------
# sys.path 修复 —— 一定要在 from core ... 之前
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # PythonCode 目录
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core import config  # noqa: E402
from core.camera_driver import CameraDriver  # noqa: E402
from core.image_comparator import ImageComparator  # noqa: E402
from core.distance_compare_geometry import build_line_points_from_config  # noqa: E402
from core.lidar_bridge import read_lidar_once, LidarSnapshot  # noqa: E402
from core.vision_lidar_fusion import fuse_vision_and_lidar, FusionLevel  # noqa: E402
from core.vision_safety_logic import SafetyLevel, SafetyZone, VisionSafetyResult  # noqa: E402


# ---------------------------------------------------------------------------
# 几何工具（和 static_demo 保持同一套约定）
# ---------------------------------------------------------------------------

def signed_distance_to_line(px: Tuple[float, float],
                            p1: Tuple[float, float],
                            p2: Tuple[float, float]) -> float:
    """
    计算点 P 到有向直线 P1->P2 的带符号距离。

    约定：
    - 线的“右侧”（走廊侧）为 SAFE，d > 0
    - 线的“左侧”（机柜侧）为 DANGER，d < 0
    """
    x0, y0 = px
    x1, y1 = p1
    x2, y2 = p2

    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return 0.0

    # (dx, dy) 的左法向量 (-dy, dx)
    nx = -dy
    ny = dx
    norm = math.hypot(nx, ny)
    if norm == 0:
        return 0.0

    nx /= norm
    ny /= norm

    vx = x0 - x1
    vy = y0 - y1

    d = vx * nx + vy * ny
    return d


def classify_distance_zone(d: float, cfg) -> str:
    """
    使用 config.DISTANCE_COMPARE 中的阈值进行区域判别。
    """
    tol = cfg.on_line_tolerance_px
    danger_thr = cfg.danger_inside_threshold_px
    safe_thr = cfg.safe_far_threshold_px

    if abs(d) <= tol:
        return "ON_LINE"
    if d < -danger_thr:
        return "INSIDE_DANGER"
    if d > safe_thr:
        return "OUTSIDE_SAFE"
    return "NEAR_LINE"


def foot_from_bbox(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
    """
    根据 bbox (x, y, w, h) 粗略估计“脚底点”：取 bbox 底边中点。
    """
    x, y, w, h = bbox
    fx = x + w / 2.0
    fy = y + h
    return fx, fy


def pick_main_bbox(bboxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int] | None:
    """
    从多个 bbox 中挑一个“主目标”：
    简单策略：y+h 最大（画面最低的那个），通常是离摄像头最近的人。
    """
    if not bboxes:
        return None
    return max(bboxes, key=lambda b: b[1] + b[3])


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== distance_compare_motion_demo ===")

    cam_cfg = config.CAMERA
    dist_cfg = config.DISTANCE_COMPARE

    # ---- 打开摄像头：优先看 use_rtsp 开关 ----
    if cam_cfg.use_rtsp:
        print(f"[INFO] Using RTSP camera: {cam_cfg.rtsp_url}")
    else:
        print(f"[INFO] Using USB camera index={cam_cfg.device_index}")

    camera = CameraDriver(cam_cfg)
    if not camera.open():
        print("[ERROR] Failed to open camera.")
        return

    comparator = ImageComparator()

    # 先抓一帧确定分辨率 & 画黄线端点
    ok, frame = camera.read()
    if not ok or frame is None:
        print("[ERROR] Cannot read first frame.")
        camera.release()
        return

    h, w = frame.shape[:2]
    p1, p2 = build_line_points_from_config(w, h, dist_cfg)
    print(f"[INFO] frame size = {w}x{h}")
    print(f"[INFO] yellow line p1={p1}, p2={p2}")

    cv2.namedWindow("distance_compare_motion_demo", cv2.WINDOW_NORMAL)

    last_lidar_ts: float = 0.0
    last_lidar: LidarSnapshot | None = None
    LIDAR_INTERVAL_SEC: float = 0.2  # 每 0.2 秒采一次雷达

    frame_id = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                print("[WARN] Failed to read frame, break.")
                break

            frame_id += 1

            # --- 1) 运动检测，拿到 bbox 列表 & motion_score ---
            result = comparator.compare(frame)

            # 默认值，防止后面使用时未定义
            bboxes: List[Tuple[int, int, int, int]] = []
            motion_score: float = 0.0

            # 常见情况：compare 返回 3 元组或 2 元组
            if isinstance(result, (tuple, list)):
                if len(result) == 3:
                    # e.g. (bboxes, motion_score, debug_frame)
                    bboxes, motion_score, _ = result
                elif len(result) == 2:
                    # e.g. (bboxes, motion_score)
                    bboxes, motion_score = result
                elif len(result) == 1:
                    # e.g. (bboxes,)
                    bboxes = result[0]
                else:
                    # 长度大于 3 时，只用前两个元素
                    bboxes = result[0]
                    motion_score = result[1]
            # 另一种实现风格：compare 返回 dict
            elif isinstance(result, dict):
                bboxes = result.get("bboxes", []) or []
                motion_raw = result.get("motion_score", 0.0)
                try:
                    motion_score = float(motion_raw)
                except (TypeError, ValueError):
                    motion_score = 0.0
            # compare 返回 None：直接认为当前无目标
            elif result is None:
                bboxes = []
                motion_score = 0.0
            else:
                # 最兜底：假设 result 本身就是 bbox 列表
                bboxes = result  # type: ignore[assignment]

            # --- 2) 从 bbox 中挑选主目标并计算脚底点 & 区域 ---
            zone_text = "NO_TARGET"
            dist_text = ""
            hud_color = (200, 200, 200)
            bbox_color = (200, 200, 200)
            vis = frame.copy()
            d_value: float | None = None
            vision_result = VisionSafetyResult(
                level=SafetyLevel.SAFE,
                zone=SafetyZone.OUTSIDE_SAFE,
                target_box=None,
                geom_distance_px=0.0,
                primary_bbox=None,
            )

            # 画黄线
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

            if bboxes:
                main_bbox = pick_main_bbox(bboxes)
                x, y, bw, bh = main_bbox

                # 估计脚底点
                fx, fy = foot_from_bbox(main_bbox)

                # 计算距离 & 区域
                d = signed_distance_to_line((fx, fy), p1, p2)
                zone = classify_distance_zone(d, dist_cfg)
                zone_text = zone
                dist_text = f"d = {d:.2f}px"
                d_value = d

                if zone_text == "OUTSIDE_SAFE":
                    bbox_color = (0, 255, 0)
                elif zone_text in ("ON_LINE", "NEAR_LINE"):
                    bbox_color = (0, 255, 255)
                elif zone_text == "INSIDE_DANGER":
                    bbox_color = (0, 0, 255)

                # 画出主 bbox（用 hud_color）
                cv2.rectangle(vis, (x, y), (x + bw, y + bh), bbox_color, 2)

                # 脚底点
                cv2.circle(vis, (int(fx), int(fy)), 8, (0, 0, 255), -1)
                cv2.putText(
                    vis,
                    "FOOT",
                    (int(fx) + 10, int(fy) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )

                vision_level = (
                    SafetyLevel.SAFE
                    if zone_text in ("OUTSIDE_SAFE", "NEAR_LINE")
                    else SafetyLevel.CAUTION
                    if zone_text == "ON_LINE"
                    else SafetyLevel.DANGER
                )
                vision_zone = (
                    SafetyZone.OUTSIDE_SAFE
                    if zone_text in ("OUTSIDE_SAFE", "NEAR_LINE")
                    else SafetyZone.ON_LINE
                    if zone_text == "ON_LINE"
                    else SafetyZone.INSIDE_DANGER
                )
                vision_result = VisionSafetyResult(
                    level=vision_level,
                    zone=vision_zone,
                    target_box=None,
                    geom_distance_px=d,
                    primary_bbox=main_bbox,
                )

            now = time.time()
            if now - last_lidar_ts > LIDAR_INTERVAL_SEC:
                last_lidar = read_lidar_once()
                last_lidar_ts = now

            lidar_value = (
                last_lidar.distance_cm
                if (last_lidar and last_lidar.ok and last_lidar.distance_cm is not None)
                else None
            )
            fusion = fuse_vision_and_lidar(vision_result, lidar_value)

            if fusion.level == FusionLevel.DANGER:
                hud_color = (0, 0, 255)
            elif fusion.level == FusionLevel.CAUTION:
                hud_color = (0, 255, 255)
            elif fusion.level == FusionLevel.SAFE:
                hud_color = (0, 255, 0)
            else:
                hud_color = (200, 200, 200)

            if lidar_value is not None:
                lidar_log = f"lidar_cm={lidar_value:.1f}"
                lidar_hud = f"lidar={lidar_value:.1f}cm"
            else:
                lidar_log = "lidar=None"
                lidar_hud = "lidar=None"

            if bboxes and d_value is not None:
                print(
                    f"[FRAME {frame_id}] zone={zone_text:>13} | "
                    f"d={d_value:7.2f}px | motion={motion_score:.4f} | boxes={len(bboxes)} | {lidar_log} | fusion={fusion.level}"
                )
            else:
                print(
                    f"[FRAME {frame_id}] zone=NO_TARGET   | "
                    f"d=   n/a  | motion={motion_score:.4f} | boxes=0 | {lidar_log} | fusion={fusion.level}"
                )

            # --- 3) HUD 叠加 ---
            hud = (
                f"LEVEL: {fusion.level} | "
                f"zone={fusion.vision.zone.name if fusion.vision and fusion.vision.zone else zone_text} | "
                f"d={fusion.vision.geom_distance_px:.1f}px | "
                f"{lidar_hud}"
            )

            cv2.putText(
                vis,
                hud,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                hud_color,
                2,
            )

            cv2.imshow("distance_compare_motion_demo", vis)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):  # ESC 或 q 退出
                print("[INFO] Quit by user.")
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
