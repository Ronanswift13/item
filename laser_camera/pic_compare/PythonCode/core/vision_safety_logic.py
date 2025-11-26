from __future__ import annotations

import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # .../PythonCode 
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple, Optional

try:
    from core.distance_compare_geometry import (
        build_line_points_from_config,
        foot_from_bbox,
        signed_distance_to_line,
        classify_distance_zone,
    )
except ImportError:
    from core.distance_compare_geometry import (  # type: ignore
        build_line_points_from_config,
        signed_distance_to_line,
        classify_distance_zone,
    )

    def foot_from_bbox(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x, y, w, h = bbox
        return x + w / 2.0, y + h
from core import config


class SafetyLevel(Enum):
    SAFE = auto()
    CAUTION = auto()
    DANGER = auto()


class SafetyZone(Enum):
    OUTSIDE_SAFE = auto()
    ON_LINE = auto()
    INSIDE_DANGER = auto()


@dataclass
class VisionSafetyResult:
    level: SafetyLevel
    zone: SafetyZone
    target_box: Optional[Tuple[int, int, int, int]] = None
    geom_distance_px: float = 0.0
    primary_bbox: Optional[Tuple[int, int, int, int]] = None


class VisionSafetyLogic:
    """
    High-level vision safety logic.

    Delegates geometry to distance_compare_geometry helpers.
    """

    def __init__(self, frame_width: int, frame_height: int) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.dist_cfg = config.DISTANCE_COMPARE
        self.line_p1, self.line_p2 = build_line_points_from_config(
            frame_width, frame_height, self.dist_cfg
        )

    def evaluate_distance(
        self,
        bboxes: List[Tuple[int, int, int, int]],
        motion_score: float,
    ) -> Tuple[SafetyLevel, SafetyZone, float, Optional[Tuple[int, int, int, int]]]:
        """Distance-based safety evaluation."""
        if not bboxes:
            return SafetyLevel.SAFE, SafetyZone.OUTSIDE_SAFE, 0.0, None

        # pick main bbox: lowest foot
        primary = max(bboxes, key=lambda b: b[1] + b[3])
        fx, fy = foot_from_bbox(primary)
        d = signed_distance_to_line((fx, fy), self.line_p1, self.line_p2)
        zone_text = classify_distance_zone(d, self.dist_cfg)

        if zone_text in ("OUTSIDE_SAFE", "NEAR_LINE"):
            level = SafetyLevel.SAFE
            zone = SafetyZone.OUTSIDE_SAFE
        elif zone_text == "ON_LINE":
            level = SafetyLevel.CAUTION
            zone = SafetyZone.ON_LINE
        else:
            level = SafetyLevel.DANGER
            zone = SafetyZone.INSIDE_DANGER

        return level, zone, d, primary

    def evaluate(
        self,
        frame_shape: Tuple[int, int, int],
        bboxes: List[Tuple[int, int, int, int]],
    ) -> VisionSafetyResult:
        """Public entry: wrapper around distance-based evaluation."""
        # motion_score currently unused in mapping, but passed for future use
        motion_score = 0.0
        level, zone, d, primary_bbox = self.evaluate_distance(bboxes, motion_score)
        return VisionSafetyResult(
            level=level,
            zone=zone,
            target_box=None,
            geom_distance_px=d,
            primary_bbox=primary_bbox,
        )


# ---------------------------------------------------------------------------
# Simple self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    frame_shape = (1080, 1920, 3)
    fw, fh = frame_shape[1], frame_shape[0]
    logic = VisionSafetyLogic(frame_width=fw, frame_height=fh)

    # Estimate y on the line at center x for synthetic boxes
    x_mid = fw * 0.5
    x1, y1 = logic.line_p1
    x2, y2 = logic.line_p2
    y_line_mid = y1 + (x_mid - x1) * (y2 - y1) / (x2 - x1) if x2 != x1 else (y1 + y2) / 2

    safe_far_boxes = [(int(x_mid - 40), int(y_line_mid - 0.15 * fh), 80, 120)]
    on_line_boxes = [(int(x_mid - 40), int(y_line_mid - 0.02 * fh), 80, 120)]
    danger_boxes = [(int(x_mid - 40), int(y_line_mid + 0.05 * fh), 80, 120)]

    print("=== VisionSafetyLogic self-test ===")
    for name, boxes in [
        ("safe_far", safe_far_boxes),
        ("on_line", on_line_boxes),
        ("danger_inside", danger_boxes),
    ]:
        res = logic.evaluate(frame_shape, boxes)
        print(
            f"[TEST] scenario={name:12s} "
            f"-> level={res.level.name} zone={res.zone.name} "
            f"d={res.geom_distance_px:6.2f}px bbox={res.primary_bbox}"
        )
