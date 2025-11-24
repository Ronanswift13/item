#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Global configuration for the pic_compare project.

This file centralises camera and basic vision thresholds so that
other modules only need to import from here, without doing any
sys.path hacks.
"""

from __future__ import annotations
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Low-level camera settings (single source of truth)
# ---------------------------------------------------------------------------

# RTSP 地址：根据实际设备修改用户名、密码和路径
RTSP_URL: str = "rtsp://admin:admin@192.168.1.64:554/h264/ch1/main/av_stream"

# 是否优先使用 RTSP 流；如果为 False，则退回本地 USB 摄像头
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


# ---------------------------------------------------------------------------
# 导出全局配置实例，其他模块只需要 `from core.config import CAMERA, VISION`
# ---------------------------------------------------------------------------

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
