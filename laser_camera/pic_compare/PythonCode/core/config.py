from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]  # .../laser_camera
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from env_local import CAMERA as ENV_CAMERA, VISION_LINE

RTSP_URL: str = ENV_CAMERA.rtsp_url
USE_RTSP: bool = ENV_CAMERA.use_rtsp
USB_DEVICE_INDEX: int = ENV_CAMERA.usb_index


@dataclass
class DistanceCompareConfig:
    image_path: str = (
        "/Users/ronan/Desktop/item/laser_camera/pic_compare/PythonCode/data/"
        "distance_capture_20251125_105203.jpg"
    )
    line_p1_norm: tuple[float, float] = VISION_LINE.line1_p1_norm
    line_p2_norm: tuple[float, float] = VISION_LINE.line1_p2_norm
    line2_p1_norm: tuple[float, float] = VISION_LINE.line2_p1_norm
    line2_p2_norm: tuple[float, float] = VISION_LINE.line2_p2_norm
    test_foot_point_norm: tuple[float, float] = (0.50, 0.85)
    on_line_tolerance_px: float = 20.0
    danger_inside_threshold_px: float = 80.0
    safe_far_threshold_px: float = 130.0


DISTANCE_COMPARE = DistanceCompareConfig()


@dataclass
class CameraConfig:
    rtsp_url: str = ENV_CAMERA.rtsp_url
    use_rtsp: bool = ENV_CAMERA.use_rtsp
    device_index: int = ENV_CAMERA.usb_index


@dataclass
class VisionThresholds:
    motion_score_threshold: float = 0.03
    min_height_ratio: float = 0.10


@dataclass
class LidarFusionConfig:
    danger_cm: float = 120.0
    caution_cm: float = 180.0
    max_valid_cm: float = 600.0


CAMERA = CameraConfig()
VISION = VisionThresholds()
LIDAR_FUSION = LidarFusionConfig()

__all__ = [
    "RTSP_URL",
    "USE_RTSP",
    "USB_DEVICE_INDEX",
    "CameraConfig",
    "VisionThresholds",
    "LidarFusionConfig",
    "CAMERA",
    "VISION",
    "LIDAR_FUSION",
    "DISTANCE_COMPARE",
]
