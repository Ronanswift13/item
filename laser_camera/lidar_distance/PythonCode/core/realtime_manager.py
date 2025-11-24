from __future__ import annotations
import time
from typing import Optional
import sys
from pathlib import Path

# Use relative imports to connect to the driver and algorithm modules
if __package__:
    from .lidar_driver import LidarDriver
    from .zone_logic import LidarZoneTracker, CabinetZone, ZoneStatus
    from .app_config import CONFIG
else:
    # Allow running as a standalone script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lidar_driver import LidarDriver  # type: ignore
    from zone_logic import LidarZoneTracker, CabinetZone, ZoneStatus  # type: ignore
    from app_config import CONFIG  # type: ignore

# Normalize cabinet configuration as CABINETS mapping
CABINETS = getattr(CONFIG, "cabinet", getattr(CONFIG, "CABINETS", {})).cabinets  # type: ignore[attr-defined]

class RealtimeManager:
    """
    High-level manager that orchestrates the LidarDriver and LidarZoneTracker
    to provide real-time status updates with dynamic sampling.
    """
    HIGH_FREQ_INTERVAL = 0.05  # 20 Hz for active monitoring
    LOW_FREQ_INTERVAL = 0.5    # 2 Hz for idle monitoring

    def __init__(self):
        # Initialize the driver (will auto-detect or go into simulation)
        self.driver = LidarDriver()

        # Initialize the tracker with zones from the app configuration
        self.zones = [CabinetZone(str(k), v[0], v[1]) for k, v in CABINETS.items()]
        self.tracker = LidarZoneTracker(authorized_zones=self.zones)

        self._is_high_frequency = False
        self._last_update_time = 0
        self.last_status: Optional[ZoneStatus] = None

    def set_high_frequency(self, enabled: bool):
        """
        Switches between fast reading (active) and slow reading (idle).
        
        Args:
            enabled: True for high frequency, False for low frequency.
        """
        self._is_high_frequency = enabled
        print(f"Info: Sampling frequency set to {'high' if enabled else 'low'}.")

    def tick(self) -> Optional[ZoneStatus]:
        """
        Performs one update cycle (tick).
        It reads from the driver, passes it to the tracker, and returns the status.
        The actual read operation is gated by the sampling frequency.
        """
        current_time = time.time()
        interval = self.HIGH_FREQ_INTERVAL if self._is_high_frequency else self.LOW_FREQ_INTERVAL
        
        if current_time - self._last_update_time < interval:
            return self.last_status # Not time yet, return last known status

        self._last_update_time = current_time
        
        measurement = self.driver.read()

        if measurement:
            distance_m = measurement.distance_cm / 100.0
            self.last_status = self.tracker.update(distance_m)
            return self.last_status
        
        return None

    def close(self):
        """Closes the Lidar driver connection."""
        self.driver.close()
        print("Info: RealtimeManager closed.")

    def __enter__(self) -> RealtimeManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    print("--- RealtimeManager Test ---")
    
    status_map = {
        ZoneStatus.STABLE: "SAFE",
        ZoneStatus.DANGER: "DANGER",
        ZoneStatus.TRANSIT: "TRANSIT"
    }

    with RealtimeManager() as manager:
        print(f"Manager initialized. Driver simulated: {manager.driver.simulated}")
        try:
            for i in range(150): # Run for 15 seconds
                # Simulate external logic toggling frequency
                if i == 20:
                    manager.set_high_frequency(True)
                if i == 80:
                    manager.set_high_frequency(False)

                status = manager.tick()
                
                if status:
                    # Get current distance from the driver for logging
                    # In a real app, this might come from the tracker or driver directly
                    current_dist_m = manager.driver.read().distance_cm / 100.0
                    
                    print(
                        f"Time: {i*0.1:.1f}s | "
                        f"Distance: {current_dist_m:.2f}m -> "
                        f"Status: {status_map.get(status, 'UNKNOWN')}",
                        end="\r"
                    )
                
                time.sleep(0.1) # Main loop delay
        except KeyboardInterrupt:
            pass
        finally:
            print("\n--- Test Finished ---")
