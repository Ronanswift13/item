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

from core.distance_compare_geometry import (
    YellowLineZone,
    GeometryResult,
    evaluate_feet_against_line,
)


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

    Delegates the core geometry to distance_compare_geometry:
    - Only cares about the closest foot in the bottom part of the image.
    - Maps YellowLineZone to SAFE / CAUTION / DANGER.
    """

    def __init__(self, frame_width: int, frame_height: int) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height

    def evaluate(
        self,
        frame_shape: Tuple[int, int, int],
        bboxes: List[Tuple[int, int, int, int]],
    ) -> VisionSafetyResult:
        """
        Decide safety level based on:
        - Foot position vs. yellow line (via evaluate_feet_against_line)
        - Geometry zone: OUTSIDE_SAFE / ON_LINE / INSIDE_DANGER
        """
        geom: GeometryResult = evaluate_feet_against_line(frame_shape, bboxes)

        # No useful person found -> treat as SAFE / OUTSIDE_SAFE
        if geom.foot is None:
            level = SafetyLevel.SAFE
            zone = SafetyZone.OUTSIDE_SAFE
            primary_bbox = None
        else:
            # Map geometry zone to SafetyLevel + SafetyZone
            if geom.zone == YellowLineZone.OUTSIDE_SAFE:
                level = SafetyLevel.SAFE
                zone = SafetyZone.OUTSIDE_SAFE
            elif geom.zone == YellowLineZone.ON_LINE:
                level = SafetyLevel.CAUTION
                zone = SafetyZone.ON_LINE
            else:
                # YellowLineZone.INSIDE_DANGER
                level = SafetyLevel.DANGER
                zone = SafetyZone.INSIDE_DANGER

            primary_bbox = geom.foot.bbox

        # UI can decide whether to draw any extra box; we keep target_box=None for now.
        return VisionSafetyResult(
            level=level,
            zone=zone,
            target_box=None,
            geom_distance_px=geom.distance_px,
            primary_bbox=primary_bbox,
        )


# ---------------------------------------------------------------------------
# Simple self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Synthetic frame shape
    frame_shape = (1080, 1920, 3)
    h = frame_shape[0]

    # Yellow line at 90% height (must match your distance_compare_geometry config)
    y_line = int(h * 0.90)

    # Build three synthetic test cases: far above, near line, below line
    safe_far_boxes = [(100, int(y_line - 0.10 * h) - 100, 80, 100)]
    on_line_boxes = [(200, int(y_line - 0.02 * h) - 100, 80, 100)]
    danger_boxes = [(300, int(y_line + 0.05 * h) - 100, 80, 100)]

    logic = VisionSafetyLogic(frame_width=1920, frame_height=1080)

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
