from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time

# --- sys.path fix so we can import new_lidar from lidar_distance ---
CURRENT = Path(__file__).resolve()
# CURRENT = .../laser_camera/pic_compare/PythonCode/core/lidar_bridge.py
laser_camera_root = CURRENT.parents[3]  # .../laser_camera

lidar_core = laser_camera_root / "lidar_distance" / "PythonCode" / "core"

if str(lidar_core) not in sys.path:
    sys.path.insert(0, str(lidar_core))


class NewLidarError(Exception):
    """Fallback error type if new_lidar doesn't define its own."""
    pass

try:
    from new_lidar import get_lidar_distance_cm, NewLidarError # type: ignore
except Exception as e:
    print(f"[LIDAR_BRIDGE] import error from {lidar_core}: {e}")
    raise


@dataclass
class LidarSnapshot:
    ok: bool
    distance_cm: float | None
    error: str | None
    timestamp: float


def read_lidar_once() -> LidarSnapshot:
    """
    Call get_lidar_distance_cm() once and wrap the result into LidarSnapshot.
    - On success: ok=True, distance_cm set, error=None
    - On failure: ok=False, distance_cm=None, error=str(e)
    """

    ts = time.time()
    try:
        d_cm = get_lidar_distance_cm()
        return LidarSnapshot(ok=True, distance_cm=d_cm, error=None, timestamp=ts)
    except Exception as e:
        return LidarSnapshot(ok=False, distance_cm=None, error=str(e), timestamp=ts)


if __name__ == "__main__":
    print("[LIDAR_BRIDGE] self-test: call read_lidar_once() 3 times")
    for i in range(3):
        snap = read_lidar_once()
        print(f"{i+1}: {snap}")
        time.sleep(0.2)
