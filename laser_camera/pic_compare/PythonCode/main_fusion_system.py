#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_fusion_system.py

功能：
1. 连接网络摄像头 (RTSP 流) 而非 USB 摄像头。
2. 连接激光雷达获取距离。
3. 在 OpenCV 窗口中实时展示融合结果（画框 + 距离显示）。
4. 暂时不使用 Flet UI，仅作为算法验证和展示工具。
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import cv2
import numpy as np
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


try:
    from lidar_distance.PythonCode.core.new_lidar import get_lidar_distance_cm
    LIDAR_AVAILABLE = True
except ImportError:
    print("[系统] 警告：未找到激光雷达驱动，将使用模拟数据。")
    LIDAR_AVAILABLE = False

try:
    from lidar_distance.PythonCode.core.vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode
    from lidar_distance.PythonCode.core.fusion_logic import fuse_sensors
    
except ImportError:
    # lidar_distance 导入
    lidar_distance_root = project_root.parent / "lidar_distance" / "PythonCode"
    core_dir = lidar_distance_root / "core"
    if str(core_dir) not in sys.path:
        sys.path.insert(0, str(core_dir))
    from vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode  # type: ignore
    from fusion_logic import fuse_sensors  # type: ignore

# --- 配置区域 ---

RTSP_URL = "rtsp://192.168.1.64:554/stream1"

# 模拟的黄线区域 (x, y, w, h)，实际应通过算法计算
YELLOW_LINE_BOX = (200, 300, 400, 200) 

def draw_hud(frame, fusion_state, fps):
    """在画面上绘制 HUD 信息"""
    h, w = frame.shape[:2]
    
    # 1. 绘制状态顶栏
    status_color = (0, 255, 0) # Green
    if fusion_state.warning_level == "DANGER":
        status_color = (0, 0, 255) # Red
    elif fusion_state.warning_level == "CAUTION":
        status_color = (0, 255, 255) # Yellow
        
    cv2.rectangle(frame, (0, 0), (w, 40), status_color, -1)
    
    # 2. 显示文字信息
    dist_str = f"{fusion_state.distance_cm:.1f}cm" if fusion_state.distance_cm else "N/A"
    info_text = (
        f"STATUS: {fusion_state.warning_level} | "
        f"DIST: {dist_str} | "
        f"FPS: {fps:.1f}"
    )
    cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # 3. 绘制模拟的黄线/机位区域 (蓝色框)
    # 这里只是演示，未来替换为 vision_logic 计算出的区域
    bx, by, bw, bh = YELLOW_LINE_BOX
    cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (255, 255, 0), 2)
    cv2.putText(frame, "Safety Zone", (bx, by-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    # 4. 如果有人（这里用 vision_state 模拟），画一个红框示意
    # 实际项目中，这里应该用 YOLO 或 运动检测的 bbox
    if fusion_state.vision.person_present:
        # 模拟一个人的框
        cv2.rectangle(frame, (300, 200), (500, 500), (0, 0, 255), 2)
        cv2.putText(frame, "Person Detected", (300, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    return frame

def main():
    print(f"[系统] 正在尝试连接摄像机 RTSP 流: {RTSP_URL}")
    print("[系统] 请确保电脑 IP 已设置为同网段 (例如 192.168.1.200)")
    
    # 打开 RTSP 流
    cap = cv2.VideoCapture(RTSP_URL)
    
    # 如果连接失败，尝试本地摄像头作为 fallback，或者直接报错
    if not cap.isOpened():
        print("[错误] 无法打开 RTSP 流。正在尝试本地摄像头 (index 0)...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[错误] 无法打开任何摄像头。退出。")
            return

    print("[系统] 摄像头已连接。按 'q' 退出。")

    # 模拟视觉状态 (在没有真实 AI 算法前)
    # 假设：有人，且越线
    dummy_vision = VisionState(
        person_present=True,
        line_position=LinePosition.BEYOND_LINE,
        orientation=BodyOrientation.FACING_CABINET,
        gesture=GestureCode.NONE
    )

    prev_time = time.time()
    
    try:
        while True:
            # 1. 读取图像帧
            ret, frame = cap.read()
            if not ret:
                print("[警告] 无法读取视频帧，正在重试...")
                time.sleep(0.1)
                continue

            # 缩放一下，避免 200万像素太大占满屏幕
            frame = cv2.resize(frame, (1024, 576))

            # 2. 获取激光雷达数据
            dist = None
            if LIDAR_AVAILABLE:
                try:
                    dist = get_lidar_distance_cm()
                except Exception as e:
                    pass # 忽略雷达读取错误，保持画面流畅

            # 3. 融合逻辑 (使用 core.fusion_logic)
            # 注意：这里目前传入的是 dummy_vision，未来要接入真实的 vision 算法输出
            current_vision = dummy_vision.with_timestamp()
            fusion_result = fuse_sensors(dist, current_vision)

            # 4. 计算 FPS
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if curr_time > prev_time else 0
            prev_time = curr_time

            # 5. 绘制 UI 并显示
            display_frame = draw_hud(frame, fusion_result, fps)
            cv2.imshow("Substation Safety Monitor (Dev Mode)", display_frame)

            # 按 Q 退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n[系统] 用户停止。")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
