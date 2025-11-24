from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import sys
from typing import Tuple

import cv2

# Ensure the project root (PythonCode) is on sys.path so we can import the sibling core package.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.vision_core import YellowLineVision, VisionConfig
from core.yellow_line_logic import YellowLineModel
from core.yellow_line_tracker import TrackerConfig


def build_yellow_line_model(frame_size: Tuple[int, int]) -> YellowLineModel:
    """Construct a horizontal yellow-line model near the bottom of the frame."""
    width, height = frame_size
    line_y = int(height * 0.7)  # 70% of frame height
    model = YellowLineModel(
        a=0.0,
        b=1.0,
        c=-float(line_y),
        epsilon=5.0,
        safe_side_positive=True,  # y > line_y is SAFE side
    )
    model.normalize()
    return model


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Failed to open camera 0. Please check your webcam or use a different index.")
        return

    ret, frame = cap.read()
    if not ret:
        print("Could not read an initial frame from the camera.")
        return

    h, w = frame.shape[:2]
    line_model = build_yellow_line_model((w, h))
    vision = YellowLineVision(
        line_model=line_model,
        motion_cfg=VisionConfig(),
        tracker_cfg=TrackerConfig(stable_frames=3),
    )

    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    csv_path = data_dir / "vision_line_log.csv"

    print("Starting motion + yellow-line recording demo. Press 'q' to quit.")
    print(f"Logging to: {csv_path}")

    # Prepare CSV writer (append mode). Write header if file is new/empty.
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    csv_file = csv_path.open("a", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    if write_header:
        writer.writerow(["timestamp", "line_state", "line_zone", "is_safe", "has_motion", "dist", "foot_x", "foot_y"])

    prev_state: Tuple[str, str, bool] | None = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame from camera.")
                break

            result = vision.process_frame(frame)

            # Draw yellow line (horizontal)
            line_y = int(-line_model.c / line_model.b)
            cv2.line(frame, (0, line_y), (w, line_y), (0, 255, 255), 2)

            # Draw foot point if available
            if result.foot_point is not None:
                fx, fy = result.foot_point
                cv2.circle(frame, (fx, fy), 6, (0, 0, 255), -1)

            # Draw text info
            state_text = f"state: {result.line_state.value}"
            zone_text = f"zone: {result.line_zone.value}"
            safe_text = f"SAFE={result.is_safe}"
            cv2.putText(frame, state_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if result.is_safe else (0, 0, 255), 2)
            cv2.putText(frame, zone_text, (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, safe_text, (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if result.is_safe else (0, 0, 255), 2)

            cv2.imshow("motion_line_record", frame)

            # Log only when state/zone/safety changes to keep CSV compact.
            current_state = (result.line_state.value, result.line_zone.value, result.is_safe)
            if current_state != prev_state:
                timestamp = datetime.now().isoformat()
                foot_x, foot_y = ("", "")
                if result.foot_point is not None:
                    foot_x, foot_y = result.foot_point
                row = [
                    timestamp,
                    result.line_state.value,
                    result.line_zone.value,
                    result.is_safe,
                    result.has_motion,
                    round(result.dist, 2),
                    foot_x,
                    foot_y,
                ]
                try:
                    writer.writerow(row)
                    csv_file.flush()
                    print(
                        f"[LOG] t={timestamp} state={result.line_state.value} "
                        f"zone={result.line_zone.value} SAFE={result.is_safe} "
                        f"has_motion={result.has_motion} dist={round(result.dist, 2)} "
                        f"foot=({foot_x},{foot_y})"
                    )
                except Exception as exc:
                    print(f"[ERROR] Failed to write CSV row: {exc}")
                prev_state = current_state

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        csv_file.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
