from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple, Optional

from core.distance_compare_config import (
    YELLOW_LINE_Y_RATIO,
    ON_LINE_BAND_RATIO,
    INSIDE_MARGIN_RATIO,
    ROI_BOTTOM_RATIO,
)


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
