#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LiDAR zone tracker: maps 1D distance samples to cabinet zones and motion status.

The objective is to provide an engineering-friendly interpretation of raw LiDAR
data so that higher-level safety logic can reason about “where the worker is”
and “what the worker is doing” (standing still in a cabinet zone, walking, or
out of range).  This module focuses strictly on LiDAR-side logic, so it can be
unit-tested without any UI or vision dependencies.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Deque, Iterable, Optional
import time


@dataclass(frozen=True)
class CabinetZone:
    """Distance interval describing a single cabinet zone."""

    cabinet_index: int  # 1-based index
    d_min_m: float      # inclusive
    d_max_m: float      # inclusive

    def contains(self, distance_m: float) -> bool:
        return self.d_min_m <= distance_m <= self.d_max_m


class LidarStatus(Enum):
    IDLE = auto()
    WALKING = auto()
    STABLE_AUTH = auto()
    STABLE_UNAUTH = auto()
    OUT_OF_RANGE = auto()


@dataclass
class LidarDecision:
    distance_m: float | None
    cabinet_index: int | None
    status: LidarStatus
    is_safe: bool
    reason: str


class LidarZoneTracker:
    """Tracks recent LiDAR samples to infer cabinet zones and motion state."""

    def __init__(
        self,
        zones: Iterable[CabinetZone],
        movement_threshold_m: float = 0.25,
        static_threshold_m: float = 0.20,
        static_window_s: float = 2.5,
        walk_window_s: float = 2.0,
    ) -> None:
        self._zones: list[CabinetZone] = sorted(zones, key=lambda z: z.cabinet_index)
        self.movement_threshold_m = movement_threshold_m
        self.static_threshold_m = static_threshold_m
        self.static_window_s = static_window_s
        self.walk_window_s = walk_window_s
        self._history: Deque[tuple[float, float, Optional[int]]] = deque()
        self._max_window = max(static_window_s, walk_window_s)

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------
    def _trim_history(self, now: float) -> None:
        """Remove samples that are outside the longest window."""
        while self._history and now - self._history[0][0] > self._max_window:
            self._history.popleft()

    def _classify_distance(self, distance_m: float | None) -> Optional[int]:
        if distance_m is None or distance_m <= 0:
            return None
        for zone in self._zones:
            if zone.contains(distance_m):
                return zone.cabinet_index
        return None

    def _recent_entries(self, window_s: float, now: float) -> list[tuple[float, float, Optional[int]]]:
        cutoff = now - window_s
        return [entry for entry in self._history if entry[0] >= cutoff]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update(
        self,
        distance_m: float | None,
        authorized_cabinets: set[int],
        now: float | None = None,
    ) -> LidarDecision:
        """Ingest a new sample and return the inferred LiDAR state."""

        timestamp = now if now is not None else time.time()
        cabinet_index = self._classify_distance(distance_m)

        if distance_m is None or distance_m <= 0:
            # No usable measurement: do not append to history but clear stale data.
            self._trim_history(timestamp)
            return LidarDecision(
                distance_m=None,
                cabinet_index=None,
                status=LidarStatus.IDLE,
                is_safe=True,
                reason="no data",
            )

        # Append the valid measurement.
        self._history.append((timestamp, distance_m, cabinet_index))
        self._trim_history(timestamp)

        recent_for_walk = self._recent_entries(self.walk_window_s, timestamp)
        recent_for_static = self._recent_entries(self.static_window_s, timestamp)

        def distance_spread(entries: list[tuple[float, float, Optional[int]]]) -> float:
            distances = [d for _, d, _ in entries]
            if len(distances) < 2:
                return 0.0
            return max(distances) - min(distances)

        def cabinet_consensus(entries: list[tuple[float, float, Optional[int]]]) -> Optional[int]:
            cabinets = {idx for _, _, idx in entries if idx is not None}
            if len(cabinets) == 1:
                return next(iter(cabinets))
            return None

        # 1) Detect walking: large distance variation within walk window.
        if (
            len(recent_for_walk) >= 2
            and distance_spread(recent_for_walk) >= self.movement_threshold_m
        ):
            return LidarDecision(
                distance_m=distance_m,
                cabinet_index=cabinet_index,
                status=LidarStatus.WALKING,
                is_safe=True,
                reason="walking between cabinets",
            )

        # 2) Detect stable presence in a cabinet zone.
        consensus_cabinet = cabinet_consensus(recent_for_static)
        if (
            consensus_cabinet is not None
            and distance_spread(recent_for_static) <= self.static_threshold_m
        ):
            if consensus_cabinet in authorized_cabinets:
                return LidarDecision(
                    distance_m=distance_m,
                    cabinet_index=consensus_cabinet,
                    status=LidarStatus.STABLE_AUTH,
                    is_safe=True,
                    reason=f"stable at authorized cabinet {consensus_cabinet}",
                )
            return LidarDecision(
                distance_m=distance_m,
                cabinet_index=consensus_cabinet,
                status=LidarStatus.STABLE_UNAUTH,
                is_safe=False,
                reason=f"stable at UNAUTHORIZED cabinet {consensus_cabinet}",
            )

        # 3) Valid distance but not inside any zone -> OUT_OF_RANGE.
        if cabinet_index is None:
            return LidarDecision(
                distance_m=distance_m,
                cabinet_index=None,
                status=LidarStatus.OUT_OF_RANGE,
                is_safe=True,
                reason="out of configured cabinet zones",
            )

        # 4) Otherwise we treat it as IDLE (waiting for stability).
        return LidarDecision(
            distance_m=distance_m,
            cabinet_index=cabinet_index,
            status=LidarStatus.IDLE,
            is_safe=True,
            reason="awaiting stable reading",
        )


# ----------------------------------------------------------------------
# CLI demonstration
# ----------------------------------------------------------------------
def _demo_cli() -> None:
    zones = [
        CabinetZone(1, 1.00, 1.30),
        CabinetZone(2, 1.40, 1.70),
        CabinetZone(3, 1.80, 2.10),
    ]
    tracker = LidarZoneTracker(
        zones,
        movement_threshold_m=0.20,
        static_threshold_m=0.08,
        static_window_s=2.0,
        walk_window_s=1.5,
    )
    authorized = {1, 3}

    sequence = [
        # Stable at cabinet 1
        (0.0, 1.05),
        (0.4, 1.07),
        (0.8, 1.06),
        (1.2, 1.05),
        (1.6, 1.04),
        # Walking towards cabinet 3 (quick succession)
        (2.0, 1.20),
        (2.4, 1.35),
        (2.8, 1.50),
        (3.2, 1.70),
        (3.6, 1.85),
        (4.0, 1.95),
        # Pause long enough for filters to forget walking samples
        (5.6, 1.92),
        (6.0, 1.91),
        (6.4, 1.93),
        (6.8, 1.92),
        # Move to unauthorized cabinet 2 and settle there
        (7.2, 1.70),
        (7.6, 1.55),
        (8.0, 1.54),
        (8.4, 1.53),
        (8.8, 1.54),
        (9.2, 1.53),
        (10.0, 1.54),
        (10.4, 1.55),
        (10.8, 1.55),
    ]

    base = time.time()
    print("t(s)  dist(m)  idx  status         safe  reason")
    print("-" * 70)
    for dt, dist in sequence:
        decision = tracker.update(dist, authorized_cabinets=authorized, now=base + dt)
        idx_display = decision.cabinet_index if decision.cabinet_index is not None else "-"
        dist_display = f"{decision.distance_m:.2f}" if decision.distance_m is not None else "None"
        print(
            f"{dt:4.1f}  {dist_display:>7}  {idx_display!s:>3}  "
            f"{decision.status.name:<13} {str(decision.is_safe):<5}  {decision.reason}"
        )


if __name__ == "__main__":
    _demo_cli()