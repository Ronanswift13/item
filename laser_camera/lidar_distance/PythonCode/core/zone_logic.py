from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass
import numpy as np
from enum import Enum, auto

class ZoneStatus(Enum):
    """Status of the Lidar zone detection."""
    STABLE = auto()     # Object is stationary inside an authorized zone.
    DANGER = auto()     # Object is stationary in an unauthorized (dangerous) area.
    TRANSIT = auto()    # Object is moving.

@dataclass
class CabinetZone:
    """Defines an authorized zone with a min and max distance."""
    zone_id: str
    min_dist_m: float
    max_dist_m: float

class LidarZoneTracker:
    """
    Implements the zone authorization algorithm using a history buffer
    to determine the object's state (STABLE, DANGER, TRANSIT).
    This is pure logic and does not depend on hardware or UI.
    """
    def __init__(self, authorized_zones: list[CabinetZone], k_seconds: float = 2.0, variance_threshold: float = 0.005):
        """
        Initializes the tracker.
        
        Args:
            authorized_zones: A list of CabinetZone objects defining safe areas.
            k_seconds: The time window in seconds for calculating movement variance.
            variance_threshold: The variance in distance (meters^2) above which
                                the object is considered to be in "TRANSIT".
        """
        if not authorized_zones:
            raise ValueError("authorized_zones cannot be empty.")
        self.authorized_zones = authorized_zones
        self.k_seconds = k_seconds
        self.variance_threshold = variance_threshold
        
        # A deque to store (timestamp, distance) tuples
        self.history: deque[tuple[float, float]] = deque()
        self.current_status = ZoneStatus.DANGER

    def _is_in_authorized_zone(self, dist: float) -> bool:
        """Checks if a distance is within any of the authorized zones."""
        return any(zone.min_dist_m <= dist <= zone.max_dist_m for zone in self.authorized_zones)

    def update(self, distance_m: float) -> ZoneStatus:
        """
        Updates the tracker with a new distance measurement and returns the current status.
        """
        current_time = time.time()
        
        self.history.append((current_time, distance_m))
        
        # Remove old measurements that are outside the k_seconds window
        while self.history and current_time - self.history[0][0] > self.k_seconds:
            self.history.popleft()

        # Require a minimum number of samples to make a stable decision
        if len(self.history) < 10:
            return self.current_status

        # Calculate variance over the last k_seconds
        distances_in_window = [item[1] for item in self.history]
        dist_variance = np.var(distances_in_window)

        # 1. Check for movement (high variance)
        if dist_variance > self.variance_threshold:
            self.current_status = ZoneStatus.TRANSIT
            return self.current_status
        
        # 2. If stationary (low variance), check position
        # Use the average of recent distances for a more stable position reading
        stable_distance = np.mean(distances_in_window)
        if self._is_in_authorized_zone(stable_distance):
            self.current_status = ZoneStatus.STABLE
        else:
            self.current_status = ZoneStatus.DANGER
            
        return self.current_status

if __name__ == '__main__':
    print("--- LidarZoneTracker Test ---")
    
    zones = [
        CabinetZone(zone_id="cab_A", min_dist_m=1.0, max_dist_m=1.2),
        CabinetZone(zone_id="cab_B", min_dist_m=2.5, max_dist_m=2.7),
    ]
    
    tracker = LidarZoneTracker(authorized_zones=zones, k_seconds=1.5)
    
    # Simulate a sequence of movements
    simulated_distances = (
        [0.5] * 20 +  # Start in DANGER
        list(np.linspace(0.5, 1.1, 30)) + # Move into cab_A -> TRANSIT
        [1.1] * 50 +  # Stay in cab_A -> STABLE
        list(np.linspace(1.1, 3.5, 40)) + # Move away -> TRANSIT
        [3.5] * 30    # Stay in DANGER
    )
    
    try:
        for i, dist in enumerate(simulated_distances):
            noisy_dist = dist + np.random.normal(0, 0.01)
            status = tracker.update(noisy_dist)
            print(f"Time {i*0.1:.1f}s | Dist: {noisy_dist:.3f}m | Status: {status.name}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n--- Test Finished ---")
