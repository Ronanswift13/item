from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# sys.path fix to import core modules
# ---------------------------------------------------------------------------
CURRENT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT.parent.parent  # .../PythonCode
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core.camera_driver import CameraDriver
from core.image_comparator import ImageComparator
from core.distance_compare_geometry import build_line_points_from_config
from core.vision_safety_logic import VisionSafetyLogic, SafetyLevel, SafetyZone

DEFAULT_RTSP_URL = "rtsp://admin:admin123@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0"

@dataclass
class VisionSnapshot:
    ok: bool
    frame: Optional[np.ndarray]
    zone: Optional[str]
    level: Optional[str]
    d_px: Optional[float]
    motion: Optional[float]
    boxes: Optional[int]
    error: Optional[str]


class VisionBridge:
    """
    Bridge that reuses the logic from distance_compare_motion_demo.py:
    - CameraDriver for frames
    - ImageComparator for motion/bboxes
    - VisionSafetyLogic for line/zone/distance evaluation
    """

    def __init__(self) -> None:
        self.cam_cfg = config.CAMERA
        self.cam_cfg.rtsp_url = DEFAULT_RTSP_URL
        self.dist_cfg = config.DISTANCE_COMPARE
        self.camera = CameraDriver(self.cam_cfg)
        self.comparator = ImageComparator()
        self.logic: Optional[VisionSafetyLogic] = None
        self.p1: Tuple[float, float] | None = None
        self.p2: Tuple[float, float] | None = None

        opened = self.camera.open()
        if not opened:
            raise RuntimeError("VisionBridge: failed to open camera.")

        ok, frame = self.camera.read()
        if not ok or frame is None:
            raise RuntimeError("VisionBridge: cannot read initial frame.")

        h, w = frame.shape[:2]
        self.p1, self.p2 = build_line_points_from_config(w, h, self.dist_cfg)
        self.logic = VisionSafetyLogic(frame_width=w, frame_height=h)

    def _pick_main_bbox(self, bboxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int] | None:
        if not bboxes:
            return None
        return max(bboxes, key=lambda b: b[1] + b[3])

    def _draw_overlays(
        self,
        frame: np.ndarray,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        main_bbox: Optional[Tuple[int, int, int, int]],
        zone_text: str,
    ) -> np.ndarray:
        vis = frame.copy()
        cv2.line(
            vis,
            (int(p1[0]), int(p1[1])),
            (int(p2[0]), int(p2[1])),
            (0, 255, 255),
            3,
        )
        cv2.putText(
            vis,
            "YELLOW LINE",
            (int(p1[0]) + 10, int(p1[1]) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
        )
        if main_bbox:
            x, y, bw, bh = main_bbox
            cv2.rectangle(vis, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
        cv2.putText(
            vis,
            f"ZONE: {zone_text}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2,
        )
        return vis

    def read_once(self) -> VisionSnapshot:
        try:
            ok, frame = self.camera.read()
            if not ok or frame is None:
                return VisionSnapshot(
                    ok=False,
                    frame=None,
                    zone=None,
                    level=None,
                    d_px=None,
                    motion=None,
                    boxes=None,
                    error="Failed to read frame",
                )

            # 1) motion detection / bboxes
            result = self.comparator.compare(frame)
            bboxes: List[Tuple[int, int, int, int]] = []
            motion_score: float = 0.0
            if isinstance(result, (tuple, list)):
                if len(result) == 3:
                    bboxes, motion_score, _ = result
                elif len(result) == 2:
                    bboxes, motion_score = result
                elif len(result) == 1:
                    bboxes = result[0]
            elif isinstance(result, dict):
                bboxes = result.get("bboxes", []) or []
                motion_raw = result.get("motion_score", 0.0)
                try:
                    motion_score = float(motion_raw)
                except (TypeError, ValueError):
                    motion_score = 0.0
            elif result is None:
                bboxes = []
                motion_score = 0.0
            else:
                bboxes = result  # type: ignore[assignment]

            main_bbox = self._pick_main_bbox(bboxes)

            # 2) geometry + safety level
            zone_text = "NO_TARGET"
            d_px: float | None = None
            vision_level = SafetyLevel.SAFE
            if self.logic is None or self.p1 is None or self.p2 is None:
                raise RuntimeError("VisionBridge not initialized correctly.")

            if main_bbox:
                # VisionSafetyLogic.evaluate expects frame shape and list of boxes
                res = self.logic.evaluate(frame.shape, bboxes)
                zone_text = res.zone.name
                vision_level = res.level
                d_px = res.geom_distance_px
            else:
                # No target: keep SAFE defaults
                res = self.logic.evaluate(frame.shape, [])  # type: ignore[arg-type]
                zone_text = res.zone.name
                d_px = res.geom_distance_px
                vision_level = res.level

            level_text = vision_level.name

            # 3) draw overlays
            vis = self._draw_overlays(frame, self.p1, self.p2, main_bbox, zone_text)

            return VisionSnapshot(
                ok=True,
                frame=vis,
                zone=zone_text,
                level=level_text,
                d_px=d_px,
                motion=motion_score,
                boxes=len(bboxes),
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            return VisionSnapshot(
                ok=False,
                frame=None,
                zone=None,
                level=None,
                d_px=None,
                motion=None,
                boxes=None,
                error=str(exc),
            )


if __name__ == "__main__":
    vb = VisionBridge()
    for i in range(30):
        snap = vb.read_once()
        print(
            f"[VISION_BRIDGE] {i} ok={snap.ok} "
            f"zone={snap.zone} level={snap.level} d={snap.d_px} "
            f"motion={snap.motion} boxes={snap.boxes} err={snap.error}"
        )
