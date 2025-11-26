from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

if __package__:
    from .config import AUTHORIZED_CABINET_ID, CABINETS
    from .vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode
else:
    # Allow running as a standalone script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import AUTHORIZED_CABINET_ID, CABINETS  # type: ignore
    from vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode


@dataclass
class FusionState:
    timestamp: datetime
    distance_cm: Optional[float]
    vision: VisionState
    too_close: bool
    too_close_lidar: bool
    too_far_lidar: bool
    inside_range: bool
    warning_level: str  # "SAFE", "CAUTION", or "DANGER"


def fuse_sensors(distance_cm: Optional[float], vision: VisionState) -> FusionState:
    """
    Combine LiDAR distance and VisionState into a single FusionState.
    Rules (simple, deterministic):

    - If distance_cm is None:
        * too_close = False
        * warning_level:
            - if vision.person_present is True -> "CAUTION"
            - else -> "SAFE"

    - If distance_cm is not None:
        * if distance_cm < 30:  # cm
            too_close = True
            warning_level = "DANGER"
        * elif distance_cm < 80:
            too_close = False
            warning_level = "CAUTION"
        * else:
            too_close = False
            warning_level = "SAFE"

    - The timestamp should be `datetime.now()` when the FusionState is created.
    """

    cab = CABINETS[AUTHORIZED_CABINET_ID]
    vision_in_danger = vision.line_position == LinePosition.BEYOND_LINE

    if distance_cm is None:
        too_close_lidar = False
        too_far_lidar = False
        inside_range = False
        too_close = vision_in_danger
        warning_level = (
            "DANGER"
            if vision_in_danger
            else ("CAUTION" if vision.person_present else "SAFE")
        )
    else:
        too_close_lidar = distance_cm < cab.min_distance_cm
        too_far_lidar = distance_cm > cab.max_distance_cm
        inside_range = not too_close_lidar and not too_far_lidar
        too_close = too_close_lidar or vision_in_danger

        if too_close:
            warning_level = "DANGER"
        elif inside_range:
            warning_level = "SAFE"
        else:
            warning_level = "CAUTION" if vision.person_present else "SAFE"

    return FusionState(
        timestamp=datetime.now(),
        distance_cm=distance_cm,
        vision=vision,
        too_close=too_close,
        too_close_lidar=too_close_lidar,
        too_far_lidar=too_far_lidar,
        inside_range=inside_range,
        warning_level=warning_level,
    )


if __name__ == "__main__":
    dummy_vision_safe = VisionState(
        person_present=False,
        line_position=LinePosition.UNKNOWN,
        orientation=BodyOrientation.UNKNOWN,
        gesture=GestureCode.NONE,
        timestamp=datetime.now(),
    )
    dummy_vision_person = VisionState(
        person_present=True,
        line_position=LinePosition.BEYOND_LINE,
        orientation=BodyOrientation.FACING_CABINET,
        gesture=GestureCode.NONE,
        timestamp=datetime.now(),
    )

    print(fuse_sensors(None, dummy_vision_person))
    print(fuse_sensors(25, dummy_vision_safe))
    print(fuse_sensors(60, dummy_vision_person))
