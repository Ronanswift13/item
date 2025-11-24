from __future__ import annotations

import sys
import cv2
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # 向上两级找到 PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    
# Ensure project root (PythonCode) is on sys.path
from core.image_comparator import ImageComparator
from core.vision_safety_logic import VisionSafetyLogic, SafetyLevel

try:
    from core.image_comparator import ImageComparator
    from core.vision_safety_logic import VisionSafetyLogic, SafetyLevel
except ImportError as e:
    print("错误: 无法导入 core 模块。")
    print(f"当前 sys.path: {sys.path}")
    print(f"尝试加载的项目根目录: {project_root}")
    raise e

# Ensure project root (PythonCode) is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: cannot open camera 0.")
        return

    comparator = ImageComparator(mode="frame_diff", diff_threshold=0.02)
    safety_logic = VisionSafetyLogic(line_band_top_ratio=0.6, line_band_bottom_ratio=0.8)

    print("Starting Vision Safety Demo. Press 'q' or ESC to quit.")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Error: failed to read frame from camera.")
            break

        result = comparator.compare(frame)
        bboxes = result.get("bboxes", [])
        safety = safety_logic.evaluate(frame.shape, bboxes)

        display = frame.copy()

        # Draw all detected bounding boxes
        for (x, y, w, h) in bboxes:
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Highlight the chosen bbox, if any
        if safety.bbox is not None:
            x, y, w, h = safety.bbox
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 255), 3)

        # Determine status text and color
        if safety.level == SafetyLevel.SAFE:
            status_text = "SAFE"
            color = (0, 255, 0)
        elif safety.level == SafetyLevel.CAUTION:
            status_text = "CAUTION"
            color = (0, 255, 255)
        else:
            status_text = "DANGER"
            color = (0, 0, 255)

        motion_score = result.get("motion_score", 0.0)

        # Draw status bar
        bar_height = 40
        cv2.rectangle(display, (0, 0), (display.shape[1], bar_height), color, thickness=-1)
        cv2.putText(
            display,
            f"{status_text} | score={motion_score:.4f}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2,
        )

        cv2.imshow("Vision Safety Demo", display)

        # Print concise log
        print(
            f"[VISION] level={status_text} zone={safety.zone.name} "
            f"score={motion_score:.4f} num_boxes={len(bboxes)}"
        )

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
