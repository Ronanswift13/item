from __future__ import annotations

"""
Basic motion detection and yellow-line crossing logic for a single camera.

This module is intentionally self-contained so that it can be tested
independently from the rest of the project.

Algorithm (high-level pseudocode):

1. Convert current frame to grayscale + blur to reduce noise.
2. If we don't have a background yet, store this frame as background and return "no motion".
3. Compute absolute difference between current frame and background.
4. Threshold + morphological opening to obtain a clean binary motion mask.
5. Find contours on the motion mask, pick the largest one as the operator's body.
6. Use the bottom-center point of the bounding box as an approximate "foot point".
7. Feed the foot point into the YellowLineTracker to obtain:
   - line_state  (TRANSITION / SAFE_STABLE / DANGER_STABLE)
   - line_zone   (OUTSIDE_SAFE / ON_LINE_SAFE / INSIDE_DANGER)
   - is_safe     (True / False).
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from .yellow_line_logic import YellowLineModel, LineZone
from .yellow_line_tracker import YellowLineTracker, LineState, TrackerConfig


@dataclass
class VisionConfig:
    """Configuration parameters for motion detection."""
    blur_ksize: int = 5
    diff_threshold: int = 25
    min_contour_area: int = 800  # ignore very small blobs
    morph_kernel_size: int = 3


@dataclass
class MotionResult:
    """Intermediate result of motion detection."""
    has_motion: bool
    bbox: Optional[Tuple[int, int, int, int]]
    foot_point: Optional[Tuple[int, int]]
    mask: Optional[np.ndarray]


@dataclass
class LineCheckResult:
    """Final result that combines motion and yellow-line logic."""
    line_state: LineState
    line_zone: LineZone
    is_safe: bool
    dist: float
    foot_point: Optional[Tuple[int, int]]
    has_motion: bool


class MotionDetector:
    """Simple frame-difference based motion detector."""

    def __init__(self, config: VisionConfig | None = None) -> None:
        self.config = config or VisionConfig()
        self._bg_gray: Optional[np.ndarray] = None

    def reset_background(self) -> None:
        self._bg_gray = None

    def _preprocess(self, frame_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(
            gray,
            (self.config.blur_ksize, self.config.blur_ksize),
            0,
        )
        return gray

    def detect_motion(self, frame_bgr: np.ndarray) -> MotionResult:
        """Return motion mask, bounding box and approximate foot point."""
        gray = self._preprocess(frame_bgr)

        if self._bg_gray is None:
            # First frame: initialize background and report no motion
            self._bg_gray = gray.copy()
            return MotionResult(
                has_motion=False,
                bbox=None,
                foot_point=None,
                mask=np.zeros_like(gray),
            )

        # Compute absolute difference between background and current frame
        diff = cv2.absdiff(self._bg_gray, gray)
        _, mask = cv2.threshold(
            diff,
            self.config.diff_threshold,
            255,
            cv2.THRESH_BINARY,
        )

        # Morphological opening to remove noise
        kernel = np.ones(
            (self.config.morph_kernel_size, self.config.morph_kernel_size),
            dtype=np.uint8,
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return MotionResult(
                has_motion=False,
                bbox=None,
                foot_point=None,
                mask=mask,
            )

        # Pick the largest contour as the operator
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < self.config.min_contour_area:
            return MotionResult(
                has_motion=False,
                bbox=None,
                foot_point=None,
                mask=mask,
            )

        x, y, w, h = cv2.boundingRect(largest)
        # Bottom-center as approximate "foot point"
        foot_x = int(x + w / 2)
        foot_y = int(y + h)
        foot_point = (foot_x, foot_y)

        return MotionResult(
            has_motion=True,
            bbox=(x, y, w, h),
            foot_point=foot_point,
            mask=mask,
        )


class YellowLineVision:
    """
    Wraps MotionDetector + YellowLineTracker into a single object.

    Usage:
        model = YellowLineModel(a=..., b=..., c=..., epsilon=..., safe_side_positive=True)
        model.normalize()
        vision = YellowLineVision(model)
        result = vision.process_frame(frame_bgr)
    """

    def __init__(
        self,
        line_model: YellowLineModel,
        motion_cfg: VisionConfig | None = None,
        tracker_cfg: TrackerConfig | None = None,
    ) -> None:
        self.motion = MotionDetector(motion_cfg)
        self.tracker = YellowLineTracker(
            line_model,
            tracker_cfg or TrackerConfig(stable_frames=3),
        )
        self.line_model = line_model

    def process_frame(self, frame_bgr: np.ndarray) -> LineCheckResult:
        """
        Main entry point: given a BGR frame, detect motion and evaluate safety.

        If there is no motion or we cannot find a valid foot point, we treat
        the frame as SAFE, but in TRANSITION state.
        """
        motion = self.motion.detect_motion(frame_bgr)

        if not motion.has_motion or motion.foot_point is None:
            # No reliable motion: keep TRANSITION, but is_safe=True by default
            return LineCheckResult(
                line_state=LineState.TRANSITION,
                line_zone=LineZone.OUTSIDE_SAFE,
                is_safe=True,
                dist=0.0,
                foot_point=None,
                has_motion=False,
            )

        fx, fy = motion.foot_point
        state, zone, dist, is_safe = self.tracker.update(fx, fy)

        return LineCheckResult(
            line_state=state,
            line_zone=zone,
            is_safe=is_safe,
            dist=dist,
            foot_point=motion.foot_point,
            has_motion=True,
        )
