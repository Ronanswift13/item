#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool: distance_compare_capture_frame.py

Purpose
-------
Capture single frames from the current camera (USB or RTSP via CameraDriver)
and save them into the pic_compare/PythonCode/data folder.

Usage (run from the PythonCode directory):

  /usr/bin/python3 tools/distance_compare_capture_frame.py

Controls
--------
  q : quit
  c : capture current frame and save as JPEG

This tool is used to prepare static calibration images for the
distance_compare_* geometry/vision experiments.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

# ---------------------------------------------------------------------------
# sys.path fix – MUST be before any "from core.xxx import ..."
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # .../PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from core import config
    from core.camera_driver import CameraDriver
except ImportError as e:
    print("[CAPTURE] ERROR: failed to import core modules.")
    print(f"  project_root = {project_root}")
    print(f"  sys.path     = {sys.path}")
    raise e


def ensure_data_dir() -> Path:
    """
    Ensure that pic_compare/PythonCode/data exists and return its Path.
    """
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def build_filename(data_dir: Path) -> Path:
    """
    Build a timestamped JPEG filename inside data_dir.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return data_dir / f"distance_capture_{ts}.jpg"


def main() -> None:
    print("=== distance_compare_capture_frame.py ===")
    print("Press 'c' to capture a frame, 'q' to quit.")

    data_dir = ensure_data_dir()
    print(f"[CAPTURE] Save directory: {data_dir}")

    cam = CameraDriver()

    if not cam.open():
        print("[CAPTURE] ERROR: cannot open camera (check USB / RTSP config).")
        return

    try:
        last_print = 0.0
        while True:
            frame = cam.get_frame()
            if frame is None:
                # Avoid spamming if stream is temporarily unavailable
                now = time.time()
                if now - last_print > 2.0:
                    print("[CAPTURE] WARNING: failed to grab frame.")
                    last_print = now
                time.sleep(0.05)
                continue

            cv2.imshow("Capture for distance_compare", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("[CAPTURE] Quit requested by user.")
                break
            elif key == ord("c"):
                out_path = build_filename(data_dir)
                # Use CV2 to save
                success = cv2.imwrite(str(out_path), frame)
                if success:
                    print(f"[CAPTURE] Saved frame to: {out_path}")
                else:
                    print(f"[CAPTURE] ERROR: failed to save: {out_path}")

    finally:
        cam.close()
        cv2.destroyAllWindows()
        print("=== distance_compare_capture_frame.py finished ===")


if __name__ == "__main__":
    main()
