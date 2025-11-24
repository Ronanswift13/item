#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time vision safety demo for pic_compare.

This script wires together:
  - core.camera_driver.CameraDriver
  - core.image_comparator.ImageComparator
  - core.vision_safety_logic.VisionSafetyLogic

It shows:
  - live video
  - detected person boxes
  - safety zone / target box
  - textual HUD with SAFE / CAUTION / DANGER

Run from PythonCode directory:

  /usr/bin/python3 demo/demo_vision_realtime.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import cv2

# ---------------------------------------------------------------------------
# sys.path 修复：必须放在 import core.xxx 之前
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # .../PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.camera_driver import CameraDriver
from core.image_comparator import ImageComparator
from core.vision_safety_logic import VisionSafetyLogic


@dataclass
class VisionStatus:
    level: str
    zone: str
    motion_score: float
    num_boxes: int
    boxes: List[Tuple[int, int, int, int]]


def _draw_hud(frame, vs: VisionStatus, target_box: Optional[Tuple[int, int, int, int]]) -> None:
    """在画面上叠加安全信息和框线。"""
    h, w = frame.shape[:2]

    # 颜色定义
    COLOR_SAFE = (0, 200, 0)
    COLOR_WARN = (0, 200, 255)
    COLOR_DANGER = (0, 0, 255)
    COLOR_TARGET = (255, 255, 0)

    if vs.level == "SAFE":
        main_color = COLOR_SAFE
    elif vs.level == "CAUTION":
        main_color = COLOR_WARN
    else:
        main_color = COLOR_DANGER

    # 1) 画目标区域框（代表授权机柜区域）——现在允许 None 就不画
    if target_box is not None:
        tx, ty, tw, th = target_box
        cv2.rectangle(frame, (tx, ty), (tx + tw, ty + th), COLOR_TARGET, 2)
        cv2.putText(
            frame,
            "TARGET AREA",
            (tx, max(ty - 10, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            COLOR_TARGET,
            2,
            cv2.LINE_AA,
        )

    # 2) 人物检测框
    for (x, y, bw, bh) in vs.boxes:
        if vs.level == "DANGER":
            color = COLOR_DANGER
        elif vs.level == "CAUTION":
            color = COLOR_WARN
        else:
            color = COLOR_SAFE
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)

    # 3) 画顶部 HUD 条
    bar_h = 40
    cv2.rectangle(frame, (0, 0), (w, bar_h), (0, 0, 0), -1)

    text = f"LEVEL: {vs.level} | zone={vs.zone} | motion={vs.motion_score:.4f} | boxes={vs.num_boxes}"
    cv2.putText(
        frame,
        text,
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        main_color,
        2,
        cv2.LINE_AA,
    )


def main() -> None:
    print("=== demo_vision_realtime.py ===")
    print("Press 'q' to quit.")

    # 初始化组件
    cam = CameraDriver()
    if not cam.open():
        print("[VISION_RT] ERROR: cannot open camera.")
        return

    # 先抓取一帧用于确定画面尺寸
    first_frame = cam.get_frame()
    if first_frame is None:
        print("[VISION_RT] ERROR: failed to read initial frame for size.")
        cam.close()
        return
    fh, fw = first_frame.shape[:2]

    comparator = ImageComparator(mode="frame_diff")
    # 使用实际画面尺寸初始化安全逻辑
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

            # 获取运动检测结果
            comp_result = comparator.compare(frame)
            motion_score = float(comp_result.get("motion_score", 0.0))
            boxes = comp_result.get("bboxes", [])

            # 用 VisionSafetyLogic 根据 bbox 判定 SAFE / CAUTION / DANGER
            h, w = frame.shape[:2]
            line_result = safety_logic.evaluate(frame_shape=(h, w, 3), bboxes=boxes)

            primary_bbox = getattr(line_result, "primary_bbox", None)
            if primary_bbox is not None:
                boxes_to_draw = [primary_bbox]
            else:
                boxes_to_draw = []

            vs = VisionStatus(
                level=line_result.level.name if hasattr(line_result.level, "name") else str(line_result.level),
                zone=line_result.zone.name if hasattr(line_result.zone, "name") else str(line_result.zone),
                motion_score=motion_score,
                num_boxes=len(boxes_to_draw),
                boxes=boxes_to_draw,
            )

            # 使用返回的 target_box（如无则跳过）
            target_box = getattr(line_result, "target_box", None)

            # 叠加 HUD & 框线
            _draw_hud(frame, vs, target_box)

            # 控制台日志
            print(
                f"[VISION_RT] frame={frame_counter:04d} "
                f"level={vs.level} zone={vs.zone} "
                f"motion={vs.motion_score:.4f} boxes={vs.num_boxes}"
            )

            # 显示窗口
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
