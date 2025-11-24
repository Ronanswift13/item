from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from core.yellow_line_tracker import LineZone


class SafetyLevel(Enum):
    SAFE = auto()
    CAUTION = auto()
    DANGER = auto()


@dataclass
class VisionSafetyDecision:
    level: SafetyLevel
    output_enabled: bool   # True -> trigger safety output/relay (alarm/cut-off)
    is_safe: bool          # High-level safe/unsafe flag for UI
    reason: str            # Human-readable explanation


def evaluate_vision_safety(
    zone: LineZone,
    dist_to_line: float,
    has_motion: bool,
) -> VisionSafetyDecision:
    """
    Decide safety level based on yellow-line zone, distance to line, and motion.
    """
    if zone == LineZone.INSIDE_DANGER:
        return VisionSafetyDecision(
            level=SafetyLevel.DANGER,
            output_enabled=True,
            is_safe=False,
            reason="Foot inside danger zone",
        )

    if zone == LineZone.ON_LINE_SAFE:
        if has_motion and dist_to_line < 10.0:
            return VisionSafetyDecision(
                level=SafetyLevel.CAUTION,
                output_enabled=True,
                is_safe=False,
                reason="Moving on yellow line: caution",
            )
        return VisionSafetyDecision(
            level=SafetyLevel.SAFE,
            output_enabled=False,
            is_safe=True,
            reason="On yellow line but stable/safe",
        )

    # zone == OUTSIDE_SAFE or any other value treated as safe
    return VisionSafetyDecision(
        level=SafetyLevel.SAFE,
        output_enabled=False,
        is_safe=True,
        reason="Outside safe zone, no danger",
    )


if __name__ == "__main__":
    # Simple self-test
    cases = [
        (LineZone.OUTSIDE_SAFE, 20.0, False),
        (LineZone.ON_LINE_SAFE, 5.0, True),
        (LineZone.ON_LINE_SAFE, 12.0, False),
        (LineZone.INSIDE_DANGER, 1.0, True),
    ]
    for zone, dist, motion in cases:
        decision = evaluate_vision_safety(zone, dist, motion)
        print(f"zone={zone.value:12} dist={dist:5.1f} motion={motion:<5} -> "
              f"level={decision.level.name} output={decision.output_enabled} safe={decision.is_safe} "
              f"reason='{decision.reason}'")
