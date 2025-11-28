from __future__ import annotations

from pathlib import Path
import sys

CURRENT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT.parents[3]  # .../laser_camera
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from env_local import SERIAL, FUSION

if __package__:
    from .app_config import LIDAR, CABINETS, AUTHORIZED_CABINET_ID
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app_config import LIDAR, CABINETS, AUTHORIZED_CABINET_ID  # type: ignore

LIDAR.port = SERIAL.lidar_port
LIDAR.baudrate = SERIAL.lidar_baudrate

__all__ = ["LIDAR", "CABINETS", "AUTHORIZED_CABINET_ID"]
