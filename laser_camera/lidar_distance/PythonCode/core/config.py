from __future__ import annotations

import sys
from pathlib import Path

if __package__:
    from .app_config import LIDAR, CABINETS, AUTHORIZED_CABINET_ID
else:
    # Allow running as a standalone script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app_config import LIDAR, CABINETS, AUTHORIZED_CABINET_ID  # type: ignore

__all__ = ["LIDAR", "CABINETS", "AUTHORIZED_CABINET_ID"]
