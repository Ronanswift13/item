#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys
import cv2

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core import config


def main() -> None:
    cam_cfg = config.CAMERA
    if cam_cfg.use_rtsp:
        source = cam_cfg.rtsp_url
        print(f"[TEST] Try open RTSP: {source}")
    else:
        source = cam_cfg.device_index
        print(f"[TEST] Try open USB device index: {source}")

    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[TEST] Open failed! Source: {source}")
        raise SystemExit(1)

    print("[TEST] Open OK, start showing frames. Press 'q' to quit.")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[TEST] Read frame failed.")
            break

        cv2.imshow("rtsp_test", frame)
        # Poll keyboard every 1ms, press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
