from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # 向上两级找到 PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
try:
    from core.image_comparator import ImageComparator
    from core.vision_safety_logic import VisionSafetyLogic
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

    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    log_path = data_dir / "vision_log.csv"

    with log_path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        # Write header if file is empty
        if log_path.stat().st_size == 0:
            writer.writerow(["timestamp_iso", "safety_level", "zone", "motion_score", "num_boxes"])

        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("Error: failed to read frame from camera.")
                    break

                result = comparator.compare(frame)
                bboxes = result.get("bboxes", [])
                motion_score = float(result.get("motion_score", 0.0))
                num_boxes = len(bboxes)

                safety = safety_logic.evaluate(frame.shape, bboxes)

                timestamp = datetime.now().isoformat()
                writer.writerow([
                    timestamp,
                    safety.level.name,
                    safety.zone.name,
                    f"{motion_score:.4f}",
                    num_boxes,
                ])
                csvfile.flush()

                print(
                    f"[VISION_LOG] t={timestamp} level={safety.level.name} "
                    f"zone={safety.zone.name} score={motion_score:.4f} boxes={num_boxes}"
                )

                time.sleep(0.1)  # avoid flooding the console
        except KeyboardInterrupt:
            print("\nInterrupted by user, exiting.")
        finally:
            cap.release()


if __name__ == "__main__":
    main()
