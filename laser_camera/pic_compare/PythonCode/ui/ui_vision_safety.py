from __future__ import annotations

from pathlib import Path
import sys

# Ensure project root is importable before importing core modules
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # PythonCode folder
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.image_comparator import ImageComparator
from core.vision_safety_logic import VisionSafetyLogic, SafetyLevel
from core.output_policy import OutputPolicy
import cv2
from typing import Tuple


def draw_status(
    image,
    text: str,
    color: Tuple[int, int, int],
) -> None:
    """Draw a filled bar with status text at the top-left."""
    bar_height = 40
    cv2.rectangle(image, (0, 0), (image.shape[1], bar_height), color, thickness=-1)
    cv2.putText(
        image,
        text,
        (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
    )


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: cannot open camera 0.")
        return

    comparator = ImageComparator(mode="frame_diff", diff_threshold=0.02)
    safety_logic = VisionSafetyLogic(line_band_top_ratio=0.6, line_band_bottom_ratio=0.8)
    output_policy = OutputPolicy()

    print("Starting Vision Safety UI. Press 'q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Error: failed to read frame from camera.")
                break

            compare_result = comparator.compare(frame)
            bboxes = compare_result.get("bboxes", [])
            motion_score = float(compare_result.get("motion_score", 0.0))
            safety = safety_logic.evaluate(frame.shape, bboxes)

            display = frame.copy()

            # Draw all bounding boxes
            for (x, y, w, h) in bboxes:
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Highlight chosen bbox if present
            if safety.bbox is not None:
                x, y, w, h = safety.bbox
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 255), 3)

            # Status text and color
            if safety.level == SafetyLevel.SAFE:
                status_text = "SAFE"
                color = (0, 255, 0)
            elif safety.level == SafetyLevel.CAUTION:
                status_text = "CAUTION"
                color = (0, 255, 255)
            else:
                status_text = "DANGER"
                color = (0, 0, 255)

            status_line = f"level={status_text} zone={safety.zone.name} score={motion_score:.3f} num_boxes={len(bboxes)}"
            draw_status(display, status_line, color)

            cv2.imshow("Vision Safety UI", display)

            print(
                f"[VISION_UI] level={status_text} zone={safety.zone.name} "
                f"score={motion_score:.4f} num_boxes={len(bboxes)}"
            )
            output_policy.apply(safety.level)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
