#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TOF LiDAR wrapper built on the shared LidarDriver."""

from __future__ import annotations

from typing import Optional
import sys
from pathlib import Path

import serial

if __package__:
    from .app_config import CONFIG
    from .lidar_driver import LidarDriver
else:
    # Allow running as a standalone script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app_config import CONFIG  # type: ignore
    from lidar_driver import LidarDriver  # type: ignore

# Expose SerialException for callers that want to catch pyserial errors.
SerialException = getattr(serial, "SerialException", Exception)


def _default_port() -> str:
    """Return the preferred serial port from configuration."""

    return CONFIG.serial.port


class ToFLidar:
    """
    Thin wrapper around LidarDriver that exposes a `read_measurement` method
    returning (distance_m, strength) to match legacy callers.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, timeout: float = 1.0) -> None:
        self.port = port or _default_port()
        self.baudrate = baudrate
        self.timeout = timeout
        self._driver = LidarDriver(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

    def read_measurement(self) -> Optional[tuple[float, int]]:
        measurement = self._driver.read()
        if measurement is None:
            return None
        return measurement.distance_cm / 100.0, measurement.strength

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "ToFLidar":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


ToFLidarClass = ToFLidar


__all__ = ["ToFLidar", "ToFLidarClass", "_default_port", "SerialException"]
