
import sys
import os
import time
from typing import TYPE_CHECKING

# --- Critical Import Fix ---
# Add parent directory to path to find 'core'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now we can import from the 'core' module
from core.lidar_driver import LidarDriver
from core.app_config import CABINETS

# --- Type Hinting Fix for conditional imports ---
if TYPE_CHECKING:
    from core.lidar_driver import LidarMeasurement

def get_cabinet_id(distance_m: float) -> str:
    """
    Checks the given distance against the configured CABINETS.
    Returns the ID of the matching cabinet or 'N/A'.
    """
    for cabinet_id, (min_dist, max_dist) in CABINETS.items():
        if min_dist <= distance_m <= max_dist:
            return str(cabinet_id)
    return "N/A"

def main():
    """
    Main loop to run the CLI demonstration.
    It connects to the Lidar, reads data, and prints it to the console.
    """
    print("--- CLI Ranging Demonstration ---")
    print("Press Ctrl+C to exit.")
    
    # The LidarDriver will handle connection errors and simulation automatically
    with LidarDriver() as lidar:
        if lidar.simulated:
            print("Running in SIMULATION MODE.")
        else:
            print(f"Lidar connected on port {lidar.port}.")
            
        try:
            while True:
                measurement: 'LidarMeasurement' | None = lidar.read()
                
                if measurement:
                    distance_m = measurement.distance_cm / 100.0
                    strength = measurement.strength
                    cabinet_id = get_cabinet_id(distance_m)
                    
                    # Construct the output string and print on a single line
                    output = (
                        f"Distance: {distance_m:.2f} m | "
                        f"Strength: {strength:04d} | "
                        f"Cabinet ID: {cabinet_id}   "
                    )
                    print(output, end="\r")
                else:
                    # This might happen if the connection drops
                    print("Waiting for Lidar data...", end="\r")
                
                # Control the loop speed
                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\nExiting cleanly.")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
