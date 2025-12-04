#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys
import cv2
import time

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core import config


def main() -> None:
    cam_cfg = config.CAMERA
    if cam_cfg.use_rtsp:
        source = cam_cfg.rtsp_url
        print(f"[TEST] Using RTSP: {source}")
    else:
        source = cam_cfg.device_index
        print(f"[TEST] Using USB index: {source}")

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print("[TEST] Failed to open source:", source)
        raise SystemExit(1)

    frame_id = 0
    last_print = time.time()

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("[TEST] Failed to read frame")
            break

        frame_id += 1
        cv2.imshow("rtsp_live_test", frame)

        now = time.time()
        if now - last_print >= 1.0:
            fps = frame_id / (now - last_print)
            print(f"[TEST] frames={frame_id}, approx fps={fps:.1f}")
            frame_id = 0
            last_print = now

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
