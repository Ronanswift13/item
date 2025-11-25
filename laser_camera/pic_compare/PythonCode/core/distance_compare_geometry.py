from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple, Optional

import numpy as np

import sys
from pathlib import Path
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent  # .../PythonCode
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.distance_compare_config import (
    YELLOW_LINE_Y_RATIO,
    ON_LINE_BAND_RATIO,
    INSIDE_MARGIN_RATIO,
    ROI_BOTTOM_RATIO,
)


@dataclass
class DistanceCompareConfig:
    # normalized endpoints of yellow line (0..1) relative to frame width/height
    line_p1_norm: Tuple[float, float]
    line_p2_norm: Tuple[float, float]
    safe_px: float
    danger_px: float


def build_line_points_from_config(frame_width: int,
                                  frame_height: int,
                                  cfg) -> tuple[tuple[float, float],
                                                tuple[float, float]]:
    """
    根据配置生成像素坐标下的直线两个端点。

    兼容两种写法：
    1）老版本：cfg.line_p1_norm, cfg.line_p2_norm   （两个归一化点）
    2）当前版本：cfg.line_y_norm, cfg.line_x_norm   （你现在 config 里这对）
    """

    if hasattr(cfg, "line_p1_norm") and hasattr(cfg, "line_p2_norm"):
        # 旧写法：直接拿来用
        p1_norm = cfg.line_p1_norm
        p2_norm = cfg.line_p2_norm
    else:
        # 你现在的写法：line_y_norm / line_x_norm 都是 (x, y) 归一化坐标
        p1_norm = cfg.line_y_norm
        p2_norm = cfg.line_x_norm

    x1 = p1_norm[0] * frame_width
    y1 = p1_norm[1] * frame_height
    x2 = p2_norm[0] * frame_width
    y2 = p2_norm[1] * frame_height

    return (x1, y1), (x2, y2)


def signed_distance_to_line(
    point: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
) -> float:
    """
    Given a point (x, y) and a line segment (p1, p2), compute the signed distance
    from the point to the *infinite* line defined by p1-p2.
    By convention:
      - positive d  => point is on the SAFE side (farther from the cabinet)
      - zero-ish d  => on the yellow line
      - negative d  => inside the cabinet side (danger zone)
    Return distance in pixels.
    """
    x0, y0 = point
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        raise ValueError("Line endpoints must not be identical.")
    a = dy
    b = -dx
    c = dx * y1 - dy * x1
    norm = np.hypot(a, b)
    a /= norm
    b /= norm
    c /= norm
    return a * x0 + b * y0 + c


def classify_point_zone(
    d_px: float,
    cfg: DistanceCompareConfig,
) -> str:
    """
    Classify the zone given the signed distance:
      - return "OUTSIDE_SAFE" if d_px >= cfg.safe_px
      - return "ON_LINE"      if abs(d_px) < (cfg.safe_px * 0.3)
      - return "INSIDE_DANGER" if d_px <= cfg.danger_px
      - otherwise you can interpolate between SAFE and ON_LINE as you wish.
    """
    if d_px >= cfg.safe_px:
        return "OUTSIDE_SAFE"
    if abs(d_px) < (cfg.safe_px * 0.3):
        return "ON_LINE"
    if d_px <= cfg.danger_px:
        return "INSIDE_DANGER"
    return "ON_LINE"


class YellowLineZone(Enum):
    """Which side of the yellow line the person is in."""
    OUTSIDE_SAFE = auto()   # online 之外，靠走廊一侧，安全
    ON_LINE = auto()        # 脚踩在线附近，预警
    INSIDE_DANGER = auto()  # 已经明显越线，危险区


@dataclass
class FootPoint:
    """Bottom-center of a person bbox."""
    x: int
    y: int
    bbox: Tuple[int, int, int, int]


@dataclass
class GeometryResult:
    """Result of the geometry evaluation."""
    distance_px: float                  # foot_y - y_line
    zone: YellowLineZone
    foot: Optional[FootPoint] = None    # None = no valid person in ROI


def _extract_feet(
    frame_shape: Tuple[int, int, int],
    bboxes: List[Tuple[int, int, int, int]],
) -> List[FootPoint]:
    """Pick feet points only in the bottom ROI."""
    h, w = frame_shape[:2]
    roi_y_min = int(h * ROI_BOTTOM_RATIO)

    feet: List[FootPoint] = []
    for (x, y, bw, bh) in bboxes:
        foot_x = int(x + bw / 2.0)
        foot_y = int(y + bh)
        # Only care about boxes in the bottom part of the image
        if foot_y < roi_y_min:
            continue
        feet.append(FootPoint(x=foot_x, y=foot_y, bbox=(x, y, bw, bh)))

    return feet


def evaluate_feet_against_line(
    frame_shape: Tuple[int, int, int],
    bboxes: List[Tuple[int, int, int, int]],
) -> GeometryResult:
    """
    Core geometry: use the closest foot to the camera to decide the zone.

    Returns:
        GeometryResult with:
          - distance_px = foot_y - y_line
          - zone = OUTSIDE_SAFE / ON_LINE / INSIDE_DANGER
          - foot = FootPoint or None if nothing useful
    """
    h, w = frame_shape[:2]
    y_line = YELLOW_LINE_Y_RATIO * h

    # No detections at all -> treat as safe / outside
    if not bboxes:
        return GeometryResult(distance_px=0.0, zone=YellowLineZone.OUTSIDE_SAFE, foot=None)

    feet = _extract_feet(frame_shape, bboxes)
    if not feet:
        # All boxes too high (e.g. only upper-body motion), still treat as safe
        return GeometryResult(distance_px=0.0, zone=YellowLineZone.OUTSIDE_SAFE, foot=None)

    # Pick the person closest to the camera: max foot_y
    primary = max(feet, key=lambda f: f.y)
    d = primary.y - y_line

    band = ON_LINE_BAND_RATIO * h
    inside_margin = INSIDE_MARGIN_RATIO * h

    if d < -band:
        zone = YellowLineZone.OUTSIDE_SAFE
    elif abs(d) <= band:
        zone = YellowLineZone.ON_LINE
    elif d > inside_margin:
        zone = YellowLineZone.INSIDE_DANGER
    else:
        # small positive d but not large enough -> still treat as ON_LINE
        zone = YellowLineZone.ON_LINE

    return GeometryResult(distance_px=float(d), zone=zone, foot=primary)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    frame_shape = (1080, 1920, 3)
    h = frame_shape[0]
    y_line = int(YELLOW_LINE_Y_RATIO * h)

    # Construct three synthetic test cases (one bbox each)
    safe_far = [(100, int(y_line - 0.10 * h) - 100, 80, 100)]      # clearly outside / safe
    on_line = [(200, int(y_line - 0.02 * h) - 100, 80, 100)]       # near the line
    danger_inside = [(300, int(y_line + 0.05 * h) - 100, 80, 100)] # clearly inside

    print("=== distance_compare_geometry self-test ===")
    for name, boxes in [
        ("safe_far", safe_far),
        ("on_line", on_line),
        ("danger_inside", danger_inside),
    ]:
        res = evaluate_feet_against_line(frame_shape, boxes)
        print(
            f"{name:12s} -> d={res.distance_px:6.2f}px "
            f"zone={res.zone.name} foot={res.foot}"
        )
