#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CameraDriver for pic_compare project.

It reads global settings from core.config (RTSP_URL / USE_RTSP / USB_DEVICE_INDEX)
and provides a simple API:

    driver = CameraDriver()
    driver.open()
    frame = driver.get_frame()
    driver.close()

When run as a script, it will open the camera and print several frame shapes
for quick debugging.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import cv2

# Try to import config both when used as a package and as a standalone script.
try:
    from core import config  # type: ignore
except ImportError:  # running as "python core/camera_driver.py"
    import config  # type: ignore


class CameraDriver:
    """Unified camera driver: RTSP first, USB fallback."""

    def __init__(self, camera_cfg: Optional["config.CameraConfig"] = None) -> None:
        self.cfg = camera_cfg or config.CAMERA
        self.cap: Optional[cv2.VideoCapture] = None
        self.source_desc: str = "UNINITIALIZED"

    # ------------------------------------------------------------------
    # low-level open/close
    # ------------------------------------------------------------------
    def open(self) -> bool:
        """Open camera according to configuration.

        Returns:
            bool: True if camera is opened successfully.
        """
        # Close previous handle if needed
        if self.cap is not None:
            self.close()

        # 1) RTSP 优先
        if self.cfg.use_rtsp:
            print(f"[CameraDriver] Trying RTSP: {self.cfg.rtsp_url}")
            self.cap = cv2.VideoCapture(self.cfg.rtsp_url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self.cap.isOpened():
                self.source_desc = f"RTSP({self.cfg.rtsp_url})"
                print(f"[CameraDriver] RTSP opened OK: {self.source_desc}")
                return True
            else:
                print(f"[CameraDriver] RTSP open failed: {self.cfg.rtsp_url}")
                self.cap.release()
                self.cap = None
                return False

        # 2) USB 摄像头回退方案
        print(f"[CameraDriver] Trying USB device index={self.cfg.device_index}")
        self.cap = cv2.VideoCapture(self.cfg.device_index)
        if self.cap.isOpened():
            self.source_desc = f"USB(index={self.cfg.device_index})"
            print(f"[CameraDriver] USB camera opened OK: {self.source_desc}")
            return True

        print("[CameraDriver] ERROR: cannot open any camera source.")
        self.cap = None
        self.source_desc = "FAILED"
        return False

    def close(self) -> None:
        """Release camera resource."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            print("[CameraDriver] Camera released.")

    # ------------------------------------------------------------------
    # frame API
    # ------------------------------------------------------------------
    def get_frame(self) -> Optional["cv2.Mat"]:
        """Read one frame from camera.

        Returns:
            frame (np.ndarray) or None if failed.
        """
        if self.cap is None:
            return None

        ok, frame = self.cap.read()
        if not ok:
            return None
        return frame

    def get_frame_and_shape(self) -> Tuple[Optional["cv2.Mat"], Optional[Tuple[int, int, int]]]:
        """Convenience helper that returns frame and its shape."""
        frame = self.get_frame()
        if frame is None:
            return None, None
        return frame, frame.shape

    def read(self):
        """
        Read a frame from the underlying cv2.VideoCapture.
        Returns (ok, frame) like cap.read().
        If the camera is not opened, return (False, None).
        """
        if self.cap is None or not self.cap.isOpened():
            return False, None
        ok, frame = self.cap.read()
        return ok, frame

    def release(self) -> None:
        """Release camera resource (alias for close)."""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        self.cap = None

if __name__ == "__main__":
    print("=== CameraDriver self-test ===")
    print(
        f"Config: RTSP_URL={config.CAMERA.rtsp_url!r}, "
        f"USE_RTSP={config.CAMERA.use_rtsp}, USB_INDEX={config.CAMERA.device_index}"
    )

    driver = CameraDriver()
    if not driver.open():
        raise SystemExit(1)

    print(f"[CameraDriver] Source: {driver.source_desc}")
    print("[CameraDriver] Press 'q' to quit.")

    _counter = 0
    while True:
        frame, shape = driver.get_frame_and_shape()
        if frame is None:
            print("[CameraDriver] WARNING: failed to read frame.")
            time.sleep(0.05)
            continue

        _counter += 1
        if shape is not None:
            print(f"[CameraDriver] frame#{_counter:03d} shape={shape}")

        cv2.imshow("CameraDriver self-test", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    driver.close()
    cv2.destroyAllWindows()
    print("=== CameraDriver self-test finished ===")
