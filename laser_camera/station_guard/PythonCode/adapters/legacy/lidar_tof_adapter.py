"""
adapters/lidar_tof_adapter.py

Adapter that wraps your existing TOF LiDAR code to provide standardized
RangeMeasurement outputs for the station guard system.

This is a MINIMAL WRAPPER - your existing lidar_tof.py code is NOT modified.
"""

import sys
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

# ============================================================================
# Import your existing LiDAR code
# Adjust this path to match your actual project structure
# ============================================================================
LIDAR_CODE_PATH = Path(__file__).parents[3] / "lidar_distance" / "PythonCode"
sys.path.insert(0, str(LIDAR_CODE_PATH))

try:
    from laser_camera.lidar_distance.PythonCode.core.lidar_tof import ToFLidar, SerialException
except ImportError as e:
    print(f"ERROR: Cannot import your existing LiDAR code from {LIDAR_CODE_PATH}")
    print(f"Import error: {e}")
    print("Please adjust LIDAR_CODE_PATH in this file to point to your lidar_tof.py location")
    raise


# ============================================================================
# Standard data structures (hardware-agnostic)
# ============================================================================

@dataclass
class RangeMeasurement:
    """
    Standardized range measurement output.
    
    The core kernel only understands this format - it doesn't know about
    your specific LiDAR hardware.
    """
    distance_m: float                   # Distance in meters
    confidence: float                   # Quality metric [0.0-1.0]
    angle_or_sector: Optional[float]    # For scanning LiDAR (your ToF is single-point)
    timestamp: float                    # Unix timestamp (seconds)


# ============================================================================
# Adapter implementation
# ============================================================================

class ToFLidarAdapter:
    """
    Wraps your existing ToFLidar class to provide standardized output.
    
    Usage:
        adapter = ToFLidarAdapter(port="/dev/ttyUSB0")
        measurements = adapter.read_measurement()
        if measurements:
            for m in measurements:
                print(f"Distance: {m.distance_m:.2f}m, Confidence: {m.confidence:.2f}")
        adapter.close()
    """
    
    def __init__(self, 
                 port: Optional[str] = None, 
                 baudrate: int = 115200,
                 timeout: float = 1.0,
                 strength_normalization_factor: float = 1000.0):
        """
        Initialize adapter with your existing LiDAR.
        
        Args:
            port: Serial port (e.g., "/dev/ttyUSB0", "COM5", None for auto-detect)
            baudrate: Serial baudrate (your code uses 115200)
            timeout: Serial timeout in seconds
            strength_normalization_factor: Divide strength by this to get confidence
                Your LiDAR returns strength values, we normalize to [0,1] confidence
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.strength_normalization = strength_normalization_factor
        
        # Initialize your existing LiDAR object
        try:
            self.lidar = ToFLidar(port=port, baudrate=baudrate, timeout=timeout)
            print(f"[ToFLidarAdapter] Connected to LiDAR on port {self.lidar.port}")
        except SerialException as e:
            print(f"[ToFLidarAdapter] ERROR: Cannot open serial port: {e}")
            raise
    
    def read_measurement(self) -> Optional[List[RangeMeasurement]]:
        """
        Read one distance measurement from LiDAR.
        
        Returns:
            List containing single RangeMeasurement, or None if read failed
        """
        try:
            # Call your existing code's read_measurement method
            result = self.lidar.read_measurement()
            
            if result is None:
                return None
            
            distance_m, strength = result
            
            # Convert to standardized format
            # Your LiDAR returns (distance_m, strength)
            # We convert strength to confidence [0,1]
            confidence = min(strength / self.strength_normalization, 1.0)
            
            measurement = RangeMeasurement(
                distance_m=distance_m,
                confidence=confidence,
                angle_or_sector=None,  # Your ToF is single-point, not scanning
                timestamp=time.time()
            )
            
            return [measurement]
        
        except Exception as e:
            print(f"[ToFLidarAdapter] ERROR reading measurement: {e}")
            return None
    
    def close(self) -> None:
        """Release serial port resources."""
        if hasattr(self, 'lidar') and self.lidar is not None:
            self.lidar.close()
            print("[ToFLidarAdapter] LiDAR connection closed")


# ============================================================================
# Standalone test/demo
# ============================================================================

def main():
    """
    Standalone test to verify adapter works with your hardware.
    
    Run this to test:
        python adapters/lidar_tof_adapter.py
    """
    print("=" * 60)
    print("ToF LiDAR Adapter Test")
    print("=" * 60)
    print()
    
    # Initialize adapter (will use auto-detected port if port=None)
    try:
        adapter = ToFLidarAdapter(port=None)  # Change to your port if needed
    except Exception as e:
        print(f"FAILED to initialize adapter: {e}")
        return
    
    print("Reading measurements for 10 seconds...")
    print("Press Ctrl+C to stop early")
    print()
    
    start_time = time.time()
    measurement_count = 0
    
    try:
        while time.time() - start_time < 10.0:
            measurements = adapter.read_measurement()
            
            if measurements is None:
                print("  [No measurement]")
                time.sleep(0.1)
                continue
            
            for m in measurements:
                measurement_count += 1
                print(f"  {measurement_count:3d}. "
                      f"Distance: {m.distance_m:6.3f}m  "
                      f"Confidence: {m.confidence:4.2f}  "
                      f"Timestamp: {m.timestamp:.3f}")
            
            time.sleep(0.1)  # 10 Hz sampling
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        adapter.close()
        print()
        print(f"Test completed. Read {measurement_count} measurements.")
        print("=" * 60)


if __name__ == "__main__":
    main()