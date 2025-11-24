from __future__ import annotations

import time

import cv2

# Replace with your actual RTSP URL
RTSP_URL = "rtsp://admin:admin@192.168.1.64:554/h264/ch1/main/av_stream"


def main() -> None:
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print(f"Error: cannot open RTSP stream: {RTSP_URL}")
        return

    win_name = "IP Camera"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    frame_count = 0
    last_ts = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Error: failed to read frame from RTSP stream.")
                break

            frame_count += 1
            now = time.time()
            elapsed = now - last_ts
            if elapsed >= 2.0:
                fps = frame_count / elapsed
                print(f"FPS: {fps:.1f}")
                frame_count = 0
                last_ts = now

            cv2.imshow(win_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
