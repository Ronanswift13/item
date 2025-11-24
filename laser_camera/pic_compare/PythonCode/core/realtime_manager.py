#!/usr/bin/env python3
"""
realtime_manager.py

Simple demo LIDAR manager used by main_fusion_system.py.

Interface contract:

- class RealtimeManager:
    - __init__(self) -> None
    - tick(self) -> dict:
        returns {
            "distance_m": Optional[float],
            "cabinet_id": Optional[int],
            "status": str  # "STABLE", "TRANSIT", "NO_DATA"
        }

In this version we simulate cabinet IDs based on time,
so the fusion pipeline can work even without real LIDAR hardware.
Later you can replace this implementation with the real LIDAR logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class LidarState:
    distance_m: Optional[float]
    cabinet_id: Optional[int]
    status: str  # "STABLE" | "TRANSIT" | "NO_DATA"


class RealtimeManager:
    """
    Very simple demo implementation.

    - We simulate a person moving between 3 cabinets.
    - Each cabinet has a nominal distance in meters.
    - Status toggles between "TRANSIT" and "STABLE" over time.
    """

    def __init__(self) -> None:
        # Example: three cabinets at different distances
        self.cabinet_distances = {
            1: 1.5,
            2: 2.4,
            3: 3.3,
        }
        self._start_time = time.time()

    def _simulate(self) -> LidarState:
        """Return a simulated LidarState based on elapsed time."""
        t = time.time() - self._start_time

        # 0–10s: moving (TRANSIT, no valid cabinet)
        # 10–20s: stable at cabinet 1
        # 20–30s: stable at cabinet 2
        # >30s: stable at cabinet 3
        if t < 10:
            return LidarState(distance_m=None, cabinet_id=None, status="TRANSIT")
        elif t < 20:
            dist = self.cabinet_distances[1]
            return LidarState(distance_m=dist, cabinet_id=1, status="STABLE")
        elif t < 30:
            dist = self.cabinet_distances[2]
            return LidarState(distance_m=dist, cabinet_id=2, status="STABLE")
        else:
            dist = self.cabinet_distances[3]
            return LidarState(distance_m=dist, cabinet_id=3, status="STABLE")

    def tick(self) -> Dict[str, Any]:
        """
        Called repeatedly by main_fusion_system.get_lidar_status().

        Return a dict; get_lidar_status() will read:
        - "distance_m"
        - "cabinet_id"
        - "status"
        """
        state = self._simulate()
        return {
            "distance_m": state.distance_m,
            "cabinet_id": state.cabinet_id,
            "status": state.status,
        }

    def close(self) -> None:
        """Placeholder for cleaning any real resources (serial ports, etc.)."""
        pass
