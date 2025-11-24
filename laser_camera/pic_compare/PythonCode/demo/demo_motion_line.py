from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import cv2

# Ensure the project root (PythonCode) is on sys.path so we can import the sibling core package
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.vision_core import YellowLineVision, VisionConfig
from core.yellow_line_logic import YellowLineModel
from core.yellow_line_tracker import TrackerConfig, LineState, LineZone


def build_yellow_line_model(frame_size: Tuple[int, int]) -> YellowLineModel:
    """
    Construct a simple yellow-line model for the demo.

    For now we assume a horizontal line near the bottom of the image:
        y = const

    You can adjust 'line_y' based on your real scene.
    """
    width, height = frame_size
    # Example: line at 70% of frame height
    line_y = int(height * 0.7)

    # Line equation: y = line_y  ->  0 * x + 1 * y - line_y = 0
    model = YellowLineModel(
        a=0.0,
        b=1.0,
        c=-float(line_y),
        epsilon=5.0,
        safe_side_positive=True,  # y > line_y is SAFE side (farther from the cabinet)
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

    print("Starting motion + yellow-line demo. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from camera.")
            break

        result = vision.process_frame(frame)

        # Draw yellow line (for visualization)
        # The line is horizontal: y = -c/b  after normalization
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

        cv2.imshow("motion_line_demo", frame)

        # Also print to console for debugging
        print(
            f"state={result.line_state.value}, "
            f"zone={result.line_zone.value}, "
            f"dist={result.dist:.2f}, "
            f"has_motion={result.has_motion}, "
            f"SAFE={result.is_safe}"
        )

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
