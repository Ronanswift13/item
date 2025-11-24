from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class LineZone(str, Enum):
    """
    Classification result for a single point relative to the yellow safety line.

    - OUTSIDE_SAFE: point is on the safe side, outside the line band.
    - ON_LINE_SAFE: point is inside the tolerance band around the line
                    (stepping on the line is allowed, still SAFE).
    - INSIDE_DANGER: point is on the dangerous side of the line.
    """
    OUTSIDE_SAFE = "OUTSIDE_SAFE"
    ON_LINE_SAFE = "ON_LINE_SAFE"
    INSIDE_DANGER = "INSIDE_DANGER"


@dataclass
class YellowLineModel:
    """
    Mathematical model of the yellow safety line.

    The line equation is: a * x + b * y + c = 0

    The coefficients (a, b, c) will be normalized so that sqrt(a^2 + b^2) = 1.
    After normalization, the value  d = a * x + b * y + c  is the signed distance
    (in pixels) from a point (x, y) to the line.

    safe_side_positive:
        - True  => d > 0 is considered the SAFE side (outside the danger zone).
        - False => d < 0 is considered the SAFE side.
    epsilon:
        Distance tolerance for "on the line" (ON_LINE_SAFE).
    """
    a: float
    b: float
    c: float
    epsilon: float = 2.0
    safe_side_positive: bool = True

    def normalize(self) -> None:
        """Normalize (a, b, c) so that sqrt(a^2 + b^2) == 1."""
        import math

        norm = math.hypot(self.a, self.b)
        if norm == 0:
            raise ValueError("Invalid yellow line parameters: a and b cannot both be zero.")

        self.a /= norm
        self.b /= norm
        self.c /= norm


def classify_point(
    model: YellowLineModel,
    x: float,
    y: float,
) -> Tuple[LineZone, float, bool]:
    """
    Classify a point (x, y) relative to the yellow line.

    Returns:
        zone:     LineZone enum indicating OUTSIDE_SAFE / ON_LINE_SAFE / INSIDE_DANGER
        dist:     signed distance on the "safe coordinate" ( >0 safe side, <0 danger side )
        is_safe:  True if the point is considered safe (OUTSIDE_SAFE or ON_LINE_SAFE)
    """
    # raw signed distance with respect to the model line
    raw_d = model.a * x + model.b * y + model.c

    # Re-orient distance so that dist > 0 always means "safe side"
    dist = raw_d if model.safe_side_positive else -raw_d

    if -model.epsilon <= dist <= model.epsilon:
        zone = LineZone.ON_LINE_SAFE
        is_safe = True
    elif dist > model.epsilon:
        zone = LineZone.OUTSIDE_SAFE
        is_safe = True
    else:
        zone = LineZone.INSIDE_DANGER
        is_safe = False

    return zone, dist, is_safe


def _demo() -> None:
    """
    Simple CLI demo so you can run this file directly to check behavior:

        python yellow_line_logic.py
    """
    # Example: horizontal line y = 100 in image coordinates
    line = YellowLineModel(a=0.0, b=1.0, c=-100.0, epsilon=3.0, safe_side_positive=True)
    line.normalize()

    test_points = [
        ("outside_safe", 100, 120),  # far above the line (safe side)
        ("on_line_safe", 100, 101),  # close to line, within epsilon
        ("inside_danger", 100, 90),  # below the line (danger side)
    ]

    print("Yellow line demo (y = 100, safe side is y > 100)")
    for name, x, y in test_points:
        zone, dist, is_safe = classify_point(line, x, y)
        print(
            f"{name:>12}: point=({x:5.1f},{y:5.1f}) -> "
            f"zone={zone.value:>13} | dist={dist:6.2f} | safe={is_safe}"
        )


if __name__ == "__main__":
    _demo()
