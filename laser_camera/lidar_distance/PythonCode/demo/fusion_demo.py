import sys
import os
# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from time import sleep

try:
    from core.new_lidar import get_lidar_distance_cm as get_lidar_distance
    # 指定当前 Mac 上的实际串口
    LIDAR_PORT = "/dev/tty.usbserial-1110"
except ImportError:
    # 仅作 fallback 提示，实际应确保 core.new_lidar 可用
    print("Warning: core.new_lidar not found, check paths.")
    raise


from core.vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode
from core.fusion_logic import fuse_sensors


def build_dummy_vision() -> VisionState:
    """
    For now we ignore the real camera bug and just use a fixed VisionState:
    - assume there is a person
    - already beyond the line
    - facing the cabinet
    - no special gesture
    """
    return VisionState(
        person_present=True,
        line_position=LinePosition.BEYOND_LINE,
        orientation=BodyOrientation.FACING_CABINET,
        gesture=GestureCode.NONE,
        timestamp=datetime.now(),
    )


def main() -> None:
    print("=== fusion_demo.py: start live fusion test (Ctrl+C to stop) ===")
    vision = build_dummy_vision()

    while True:
        # 1. read distance from LiDAR
        distance = get_lidar_distance(LIDAR_PORT)

        # 2. fuse sensors
        fused = fuse_sensors(distance, vision)

        # 3. print a short, human-readable line
        dist_str = "None" if fused.distance_cm is None else f"{fused.distance_cm:.1f} cm"
        print(
            f"[fusion_demo] "
            f"distance={dist_str} | "
            f"too_close={fused.too_close} | "
            f"warning_level={fused.warning_level}"
        )

        sleep(0.5)


if __name__ == "__main__":
    main() 
