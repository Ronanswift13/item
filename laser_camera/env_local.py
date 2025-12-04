from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SerialConfig:
    lidar_port: str
    lidar_baudrate: int


@dataclass
class CameraConfig:
    use_rtsp: bool
    rtsp_url: str
    usb_index: int


@dataclass
class VisionLineConfig:
    line1_p1_norm: tuple[float, float]
    line1_p2_norm: tuple[float, float]
    line2_p1_norm: tuple[float, float]
    line2_p2_norm: tuple[float, float]


@dataclass
class FusionConfig:
    enabled: bool
    authorized_cabinets: list[int]


SERIAL = SerialConfig(
    lidar_port="/dev/tty.usbserial-1110",
    lidar_baudrate=9600,
)

CAMERA = CameraConfig(
    use_rtsp=True,
    rtsp_url="rtsp://admin:admin123@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0",
    usb_index=0,
)

VISION_LINE = VisionLineConfig(
    line1_p1_norm=(0.43, 0.96),
    line1_p2_norm=(0.52, 0.60),
    line2_p1_norm=(0.43, 0.96),
    line2_p2_norm=(0.52, 0.60),
)

FUSION = FusionConfig(
    enabled=True,
    authorized_cabinets=[1],
)
