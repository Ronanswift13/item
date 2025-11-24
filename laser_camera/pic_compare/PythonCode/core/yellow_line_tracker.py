from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .yellow_line_logic import YellowLineModel, LineZone, classify_point


class LineState(str, Enum):
    """
    High-level state of the operator relative to the yellow safety line.

    - TRANSITION: recent frames are not consistent yet.
    - SAFE_STABLE: consistently on the safe side or on the line band.
    - DANGER_STABLE: consistently inside the danger zone.
    """
    TRANSITION = "TRANSITION"
    SAFE_STABLE = "SAFE_STABLE"
    DANGER_STABLE = "DANGER_STABLE"


@dataclass
class TrackerConfig:
    """
    Configuration for the yellow line state tracker.

    stable_frames:
        Number of consecutive frames required to consider a state "stable".
    """
    stable_frames: int = 3


@dataclass
class YellowLineTracker:
    """
    Simple tracker that consumes a stream of foot positions and produces
    a high-level state (SAFE_STABLE / DANGER_STABLE / TRANSITION).
    """
    model: YellowLineModel
    config: TrackerConfig = TrackerConfig()

    last_zone: Optional[LineZone] = None
    stable_count: int = 0
    state: LineState = LineState.TRANSITION

    def update(self, x: float, y: float) -> Tuple[LineState, LineZone, float, bool]:
        """
        Update the tracker with a new foot position.

        Returns:
            state:   LineState (TRANSITION / SAFE_STABLE / DANGER_STABLE)
            zone:    LineZone for the current frame
            dist:    signed distance on the safe coordinate
            is_safe: True if the current frame is safe
        """
        zone, dist, is_safe = classify_point(self.model, x, y)

        if self.last_zone == zone:
            self.stable_count += 1
        else:
            self.last_zone = zone
            self.stable_count = 1

        if self.stable_count >= self.config.stable_frames:
            if zone == LineZone.INSIDE_DANGER:
                self.state = LineState.DANGER_STABLE
            else:
                self.state = LineState.SAFE_STABLE
        else:
            self.state = LineState.TRANSITION

        return self.state, zone, dist, is_safe


def _demo_tracker() -> None:
    """
    Small demo so you can check the tracker behavior by running:

        python yellow_line_tracker.py
    """
    # Same example line y = 100
    model = YellowLineModel(a=0.0, b=1.0, c=-100.0, epsilon=3.0, safe_side_positive=True)
    model.normalize()

    tracker = YellowLineTracker(model, TrackerConfig(stable_frames=3))

    # Scenario 1: stay outside safe side
    print("Scenario 1: stay outside the line (SAFE)")
    safe_points = [(100, 120), (101, 121), (102, 119), (100, 118)]
    for i, (x, y) in enumerate(safe_points):
        state, zone, dist, is_safe = tracker.update(x, y)
        print(f"[S1] frame={i}, state={state.value}, zone={zone.value}, safe={is_safe}")

    # Scenario 2: cross into danger and stay there
    print("\nScenario 2: cross into danger and stay there")
    danger_points = [(100, 105), (100, 101), (100, 98), (100, 95), (100, 94)]
    tracker = YellowLineTracker(model, TrackerConfig(stable_frames=2))
    for i, (x, y) in enumerate(danger_points):
        state, zone, dist, is_safe = tracker.update(x, y)
        print(f"[S2] frame={i}, state={state.value}, zone={zone.value}, safe={is_safe}")


if __name__ == "__main__":
    _demo_tracker()
