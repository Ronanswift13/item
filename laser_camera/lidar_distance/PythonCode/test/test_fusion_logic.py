from __future__ import annotations

from datetime import datetime

import sys
import os

# 添加父目录到 sys.path，以便能找到 'core' 包
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从 core 包导入
from core.vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode
from core.fusion_logic import fuse_sensors, FusionState


def build_vision(
    *,
    person_present: bool,
    line: LinePosition = LinePosition.UNKNOWN,
    orientation: BodyOrientation = BodyOrientation.UNKNOWN,
    gesture: GestureCode = GestureCode.NONE,
) -> VisionState:
    return VisionState(
        person_present=person_present,
        line_position=line,
        orientation=orientation,
        gesture=gesture,
        timestamp=datetime.now(),
    )


def check(expected_warning: str, expected_too_close: bool, fused: FusionState) -> None:
    assert (
        fused.warning_level == expected_warning
    ), f"Expected warning {expected_warning}, got {fused.warning_level}"
    assert fused.too_close == expected_too_close, (
        f"Expected too_close={expected_too_close}, got {fused.too_close}"
    )


def run_tests() -> None:
    scenarios = [
        {
            "name": "No person, far distance",
            "distance": 300.0,
            "vision": build_vision(person_present=False, line=LinePosition.UNKNOWN),
            "expected_warning": "SAFE",
            "expected_close": False,
        },
        {
            "name": "Person present but far",
            "distance": 250.0,
            "vision": build_vision(person_present=True, line=LinePosition.SAFE_ZONE),
            "expected_warning": "SAFE",
            "expected_close": False,
        },
        {
            "name": "Person very close",
            "distance": 20.0,
            "vision": build_vision(
                person_present=True,
                line=LinePosition.BEYOND_LINE,
                orientation=BodyOrientation.FACING_CABINET,
            ),
            "expected_warning": "DANGER",
            "expected_close": True,
        },
        {
            "name": "Person borderline distance",
            "distance": 70.0,
            "vision": build_vision(
                person_present=True,
                line=LinePosition.BEYOND_LINE,
                orientation=BodyOrientation.FACING_CABINET,
            ),
            "expected_warning": "CAUTION",
            "expected_close": False,
        },
    ]

    for scenario in scenarios:
        fused = fuse_sensors(scenario["distance"], scenario["vision"])
        check(scenario["expected_warning"], scenario["expected_close"], fused)
        print(f"[OK] {scenario['name']} -> warning={fused.warning_level}, too_close={fused.too_close}")


if __name__ == "__main__":
    print("Running fusion logic self-tests...")
    run_tests()
    print("All fusion tests passed ✅")