from __future__ import annotations
import sys
import time
import math
import serial
import serial.tools.list_ports
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Use relative import to get configuration
if __package__:
    from .app_config import CONFIG
else:
    # Allow running as a standalone script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app_config import CONFIG  # type: ignore

@dataclass
class LidarMeasurement:
    distance_cm: float
    strength: int

class LidarDriver:
    """
    A robust driver for TOF Lidar, combining logic from different implementations.
    It supports auto-detection, graceful error handling, and a simulation mode.
    """
    FRAME_HEADER = 0x59
    FRAME_SIZE = 9

    def __init__(self, port: Optional[str] = None, baudrate: Optional[int] = None, timeout: Optional[float] = None):
        self.port = port or CONFIG.serial.port
        self.baudrate = baudrate or CONFIG.serial.baudrate
        self.timeout = timeout if timeout is not None else CONFIG.serial.timeout
        self.simulated = False
        self._serial: Optional[serial.Serial] = None

        try:
            # If no port is specified, try to find one automatically
            if self.port is None:
                self.port = self._resolve_port()
                if self.port is None:
                    raise serial.SerialException("No suitable Lidar port found.")
            
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
        except serial.SerialException as e:
            print(f"Warning: Lidar not found on port '{self.port}' ({e}). Entering Simulation Mode.")
            self.simulated = True

    @staticmethod
    def _resolve_port() -> Optional[str]:
        """Find a suitable serial port, prioritizing USB-serial adapters."""
        ports = serial.tools.list_ports.comports()
        if sys.platform == "darwin":
            usb_ports = [p.device for p in ports if "usb" in p.device.lower()]
            if usb_ports:
                return usb_ports[0]
        # Add more platform-specific logic if needed (e.g., for Linux/Windows)
        if ports:
            return ports[0].device
        return None

    def read(self) -> Optional[LidarMeasurement]:
        """
        Reads one measurement frame from the Lidar.
        Returns a LidarMeasurement object or None on failure.
        In simulation mode, it returns a generated value.
        """
        if self.simulated:
            # Generate a fake distance oscillating between 50cm and 250cm
            sim_dist_cm = 150.0 + 100.0 * math.sin(time.time())
            sim_strength = 200 + 50 * math.cos(time.time())
            time.sleep(0.05) # Simulate read delay
            return LidarMeasurement(distance_cm=sim_dist_cm, strength=int(sim_strength))

        if not self._serial or not self._serial.is_open:
            return None

        while True:
            # Find frame headers
            if self._serial.read(1) != b'\x59':
                continue
            if self._serial.read(1) != b'\x59':
                continue

            # Read the rest of the frame
            payload = self._serial.read(self.FRAME_SIZE - 2)
            if len(payload) != self.FRAME_SIZE - 2:
                continue

            # Verify checksum
            checksum = sum(payload[:-1]) & 0xFF
            if checksum != payload[-1]:
                continue

            # Unpack data
            distance_cm = payload[0] + (payload[1] << 8)
            strength = payload[2] + (payload[3] << 8)
            
            return LidarMeasurement(distance_cm=distance_cm, strength=strength)

    def close(self):
        """Closes the serial connection if it's open."""
        if self._serial and self._serial.is_open:
            self._serial.close()

    def __enter__(self) -> LidarDriver:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

if __name__ == '__main__':
    print("--- LidarDriver Test ---")
    # Initialize driver (will auto-detect port or enter simulation)
    with LidarDriver() as lidar:
        print(f"Driver Initialized. Port: {lidar.port}, Simulated: {lidar.simulated}")
        try:
            while True:
                measurement = lidar.read()
                if measurement:
                    print(
                        f"Distance: {measurement.distance_cm / 100.0:.3f} m "
                        f"({measurement.distance_cm:.1f} cm) | "
                        f"Strength: {measurement.strength}   ",
                        end="\r"
                    )
                else:
                    print("Failed to read data from Lidar.", end="\r")
                
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n--- Test Finished ---")
