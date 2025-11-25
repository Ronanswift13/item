#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
distance_compare_static_demo.py

交互式静态标定工具：
- 读取 config.DISTANCE_COMPARE.image_path 指定的标定图片
- 画出黄线（假想安全边界）
- 鼠标左键点击任意一点，当作“脚底点”
- 计算脚到底相对黄线的带符号距离 d（像素）
- 判别区域：OUTSIDE_SAFE / ON_LINE / INSIDE_DANGER / NEAR_LINE
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2

# ---------------------------------------------------------------------------
# sys.path fix – MUST be before any "from core ..." imports
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # PythonCode 目录
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core import config  # noqa: E402
from core.distance_compare_geometry import build_line_points_from_config  # noqa: E402

# ---------------------------------------------------------------------------
# 全局变量（给鼠标回调用）
# ---------------------------------------------------------------------------
BASE_IMG = None          # 原始图像
VIS_IMG = None           # 叠加绘制后的图像
LINE_P1 = None           # 黄线端点1 (x, y)
LINE_P2 = None           # 黄线端点2 (x, y)
CFG = None               # config.DISTANCE_COMPARE
FOOT_PT = None           # 当前“脚底点”(x, y)，由鼠标点击决定
ZONE_TEXT = "NO_FOOT"    # 当前区域
DIST_TEXT = ""           # 当前距离文本，例如 "d = 12.34px"


# ---------------------------------------------------------------------------
# 几何工具：点到有向直线的带符号距离 & 区域判别
# ---------------------------------------------------------------------------

def signed_distance_to_line(
    px: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """
    Compute signed distance from point P to the oriented line P1->P2.

    约定（非常重要）：
    - “线的右侧”（走廊一侧）当作 SAFE，记为 d > 0
    - “线的左侧”（机柜一侧）当作 DANGER，记为 d < 0
    """
    x0, y0 = px
    x1, y1 = p1
    x2, y2 = p2

    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return 0.0

    # (dx, dy) 的左法向量是 (-dy, dx)
    nx = -dy
    ny = dx
    norm = math.hypot(nx, ny)
    if norm == 0:
        return 0.0

    nx /= norm
    ny /= norm

    # 向量 P1->P
    vx = x0 - x1
    vy = y0 - y1

    # 带符号距离：向法向量投影
    d = vx * nx + vy * ny
    return d


def classify_distance_zone(d: float, cfg) -> str:
    """
    使用 config.DISTANCE_COMPARE 里的阈值进行区域判别。

    - d > 0  ：走廊一侧（SAFE 侧）
    - d < 0  ：机柜一侧（DANGER 侧）
    """
    tol = cfg.on_line_tolerance_px
    danger_thr = cfg.danger_inside_threshold_px
    safe_thr = cfg.safe_far_threshold_px

    if abs(d) <= tol:
        return "ON_LINE"
    if d < -danger_thr:
        return "INSIDE_DANGER"   # 机柜侧，离线较远，危险
    if d > safe_thr:
        return "OUTSIDE_SAFE"    # 走廊侧，离线较远，安全
    return "NEAR_LINE"           # 中间缓冲区，可视作 CAUTION


# ---------------------------------------------------------------------------
# 绘制 & 刷新窗口
# ---------------------------------------------------------------------------

def refresh_window() -> None:
    """根据当前全局状态重画图像并显示。"""
    global VIS_IMG

    if BASE_IMG is None or LINE_P1 is None or LINE_P2 is None:
        return

    vis = BASE_IMG.copy()

    # 画黄线
    cv2.line(
        vis,
        (int(LINE_P1[0]), int(LINE_P1[1])),
        (int(LINE_P2[0]), int(LINE_P2[1])),
        (0, 255, 255),
        3,
    )
    cv2.putText(
        vis,
        "YELLOW LINE",
        (int(LINE_P1[0]) + 10, int(LINE_P1[1]) - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
    )

    # 画“脚底点”
    if FOOT_PT is not None:
        fx, fy = FOOT_PT
        cv2.circle(vis, (int(fx), int(fy)), 8, (0, 0, 255), -1)
        cv2.putText(
            vis,
            "TEST FOOT",
            (int(fx) + 10, int(fy) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )

    # HUD
    hud = f"ZONE: {ZONE_TEXT}"
    if DIST_TEXT:
        hud += f" | {DIST_TEXT}"

    cv2.putText(
        vis,
        hud,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        2,
    )

    VIS_IMG = vis
    cv2.imshow("distance_compare_static_demo", VIS_IMG)


# ---------------------------------------------------------------------------
# 鼠标回调：左键点击设置脚底点
# ---------------------------------------------------------------------------

def on_mouse(event, x, y, flags, param) -> None:  # noqa: D401
    """鼠标左键点击：更新脚底点，重新计算距离 & 区域。"""
    global FOOT_PT, ZONE_TEXT, DIST_TEXT

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    FOOT_PT = (float(x), float(y))

    # 计算带符号距离
    d = signed_distance_to_line(FOOT_PT, LINE_P1, LINE_P2)
    zone = classify_distance_zone(d, CFG)

    ZONE_TEXT = zone
    DIST_TEXT = f"d = {d:.2f}px"

    print(f"[CLICK] foot=({x}, {y}) -> zone={zone}, distance={d:.2f}px")

    refresh_window()


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main() -> None:
    global BASE_IMG, LINE_P1, LINE_P2, CFG, ZONE_TEXT, DIST_TEXT

    print("=== distance_compare_static_demo (interactive) ===")

    CFG = config.DISTANCE_COMPARE

    img_path = Path(CFG.image_path).expanduser()
    if not img_path.exists():
        print(f"[ERROR] Image not found: {img_path}")
        return

    print(f"[INFO] Using image: {img_path}")
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"[ERROR] Failed to read image: {img_path}")
        return

    BASE_IMG = img
    h, w = img.shape[:2]

    # 根据归一化坐标构造黄线端点
    LINE_P1, LINE_P2 = build_line_points_from_config(w, h, CFG)

    ZONE_TEXT = "NO_FOOT"
    DIST_TEXT = ""

    cv2.namedWindow("distance_compare_static_demo", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("distance_compare_static_demo", on_mouse)

    # 初始只画一条线
    refresh_window()

    print("左键点击任意位置作为脚底点，按 q 或 ESC 退出。")
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (27, ord("q")):  # ESC or 'q'
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()