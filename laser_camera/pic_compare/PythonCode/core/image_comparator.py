#!/usr/bin/env python3
"""
Reusable image comparison module for motion detection.

Supports frame-to-frame differencing and background subtraction (MOG2).
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import cv2
import numpy as np


class ImageComparator:
    def __init__(
        self,
        mode: str = "frame_diff",
        diff_threshold: float = 0.02,
        min_area: int = 800,
    ) -> None:
        if mode not in {"frame_diff", "bg_sub"}:
            raise ValueError(f"Unsupported mode: {mode}")

        self.mode = mode
        self.diff_threshold = diff_threshold
        self.min_area = min_area

        self._prev_gray: np.ndarray | None = None
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2() if mode == "bg_sub" else None
        logging.debug("ImageComparator initialized with mode=%s", mode)

    def compare(self, frame: np.ndarray) -> dict:
        """
        Compare the given frame to detect motion.

        Returns a dict with keys: mode, motion_mask, motion_score, bboxes, alarm.
        """
        if self.mode == "frame_diff":
            return self._compare_frame_diff(frame)
        return self._compare_bg_sub(frame)

    def _compare_frame_diff(self, frame: np.ndarray) -> dict:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            logging.debug("First frame received; initializing reference frame.")
            return {
                "mode": self.mode,
                "motion_mask": None,
                "motion_score": 0.0,
                "bboxes": [],
                "alarm": False,
            }

        diff = cv2.absdiff(self._prev_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bboxes: List[Tuple[int, int, int, int]] = []
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            bboxes.append((x, y, w, h))

        motion_mask = np.zeros_like(gray)
        cv2.drawContours(motion_mask, contours, -1, 255, thickness=cv2.FILLED)

        motion_score = float(np.count_nonzero(motion_mask)) / float(motion_mask.size)
        alarm = motion_score >= self.diff_threshold

        self._prev_gray = gray

        return {
            "mode": self.mode,
            "motion_mask": motion_mask,
            "motion_score": motion_score,
            "bboxes": bboxes,
            "alarm": alarm,
        }

    def _compare_bg_sub(self, frame: np.ndarray) -> dict:
        assert self._bg_subtractor is not None
        fg_mask = self._bg_subtractor.apply(frame)
        _, fg_mask = cv2.threshold(fg_mask, 25, 255, cv2.THRESH_BINARY)
        fg_mask = cv2.dilate(fg_mask, None, iterations=2)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bboxes: List[Tuple[int, int, int, int]] = []
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            bboxes.append((x, y, w, h))

        motion_mask = np.zeros_like(fg_mask)
        cv2.drawContours(motion_mask, contours, -1, 255, thickness=cv2.FILLED)

        motion_score = float(np.count_nonzero(motion_mask)) / float(motion_mask.size)
        alarm = motion_score >= self.diff_threshold

        return {
            "mode": self.mode,
            "motion_mask": motion_mask,
            "motion_score": motion_score,
            "bboxes": bboxes,
            "alarm": alarm,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cap = cv2.VideoCapture(0)
    comparator = ImageComparator(mode="frame_diff", diff_threshold=0.02)

    try:
        for i in range(200):
            ret, frame = cap.read()
            if not ret or frame is None:
                logging.warning("Failed to read frame; exiting.")
                break
            result = comparator.compare(frame)
            if i % 10 == 0:
                print(
                    f"mode={result['mode']}, "
                    f"motion_score={result['motion_score']:.4f}, "
                    f"alarm={result['alarm']}, "
                    f"num_boxes={len(result['bboxes'])}"
                )
    finally:
        cap.release()
