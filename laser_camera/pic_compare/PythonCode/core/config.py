from __future__ import annotations

import sys  
from pathlib import Path
Current_file = Path(__file__).resolve()
Project_root = Current_file.parent.parent  # .../PythonCode
if str(Project_root) not in sys.path:
    sys.path.insert(0, str(Project_root))

from dataclasses import dataclass

@dataclass
class DistanceCompareConfig:
    # 使用的标定图片
    image_path: str = (
        "/Users/ronan/Desktop/item/laser_camera/pic_compare/PythonCode/data/"
        "distance_capture_20251125_105203.jpg"
    )
    # 归一化坐标 (x, y)，范围 0..1，相对于图像宽高
    line_p1_norm: tuple[float, float] = (0.43, 0.96)   # 箭头起点
    line_p2_norm: tuple[float, float] = (0.52, 0.60)   # 箭头指向处

# 测试脚点，用来在静态图上画一个“脚”
    test_foot_point_norm: tuple[float, float] = (0.50, 0.85)

    on_line_tolerance_px: float = 8.0      # 离线多少像素以内算“踩线”
   
    danger_inside_threshold_px: float = 5.0
    safe_far_threshold_px: float = -4.5
# 全局配置实例
    
DISTANCE_COMPARE = DistanceCompareConfig()

# Low‑level camera settings (single source of truth)

# RTSP 地址：根据实际设备修改用户名、密码和路径
RTSP_URL: str = "rtsp://admin:admin@192.168.1.64:554/h264/ch1/main/av_stream"

# 优先使用 RTSP 流；如果为 False，则退回本地 USB 摄像头
USE_RTSP: bool = True

# 本地 USB 摄像头的 OpenCV 设备索引（一般 0 或 1）
USB_DEVICE_INDEX: int = 0


@dataclass
class CameraConfig:
    """相机相关配置"""

    rtsp_url: str = RTSP_URL
    use_rtsp: bool = USE_RTSP
    device_index: int = USB_DEVICE_INDEX


@dataclass
class VisionThresholds:
    """视觉判定阈值配置"""

    # motion_score 阈值 (0.0 ~ 1.0)，超过则判定为有运动目标
    motion_score_threshold: float = 0.03

    # 目标 bbox 高度占整幅图像高度的最小比例，低于此值认为太远
    min_height_ratio: float = 0.10

# 导出全局配置实例，其他模块只需要 `from core.config import CAMERA, VISION`

CAMERA = CameraConfig()
VISION = VisionThresholds()

__all__ = [
    "RTSP_URL",
    "USE_RTSP",
    "USB_DEVICE_INDEX",
    "CameraConfig",
    "VisionThresholds",
    "CAMERA",
    "VISION",
]

