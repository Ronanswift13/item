from __future__ import annotations

import sys
import os
from pathlib import Path

# ==========================================
# 确保项目根目录 (PythonCode) 在 sys.path 中，以便导入 core 包
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # 向上两级找到 PythonCode
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# ==========================================

import cv2


try:
    from core.image_comparator import ImageComparator
except ImportError as e:
    print("错误: 无法导入 core 模块。")
    print(f"当前 sys.path: {sys.path}")
    print("请确认 'PythonCode/core/image_comparator.py' 文件是否存在。")
    raise e


def main() -> None:
    # 尝试打开摄像头 (索引 0 通常是内置，1 是外置)
    # 如果你用的是 USB 摄像头且没反应，尝试改成 1
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: cannot open camera 0.")
        print("提示: 如果是外接摄像头，请尝试修改代码中的 cv2.VideoCapture(1)")
        return

    # 初始化对比器
    # diff_threshold: 灵敏度 (0.01 非常灵敏, 0.05 比较迟钝)
    comparator = ImageComparator(mode="frame_diff", diff_threshold=0.02)

    print("Starting Vision Motion Demo. Press 'q' or ESC to quit.")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Error: failed to read frame from camera.")
            break

        # 核心算法处理
        result = comparator.compare(frame)

        display = frame.copy()

        # 绘制差异框 (如果有)
        if "bboxes" in result:
            for (x, y, w, h) in result["bboxes"]:
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # 绘制状态文字
        score = result.get("motion_score", 0.0)
        is_alarm = result.get("alarm", False)
        
        text = f"Score={score:.4f} Alarm={is_alarm}"
        color = (0, 0, 255) if is_alarm else (0, 255, 0) # 红色报警，绿色正常
        
        cv2.putText(
            display,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
        )

        # 显示画面
        cv2.imshow("Vision Motion Demo", display)

        # 按 Q 或 ESC 退出
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()