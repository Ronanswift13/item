from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sys

CURRENT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT.parent.parent  # .../PythonCode
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import LIDAR_FUSION
from core.vision_safety_logic import VisionSafetyResult, SafetyLevel, SafetyZone


class FusionLevel:
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGER = "DANGER"


@dataclass
class FusionResult:
    level: str           # FusionLevel.*
    reason: str          # 简短文字说明级别
    vision: VisionSafetyResult
    lidar_cm: Optional[float]


def _vision_level_to_fusion(level: SafetyLevel) -> str:
    if level == SafetyLevel.DANGER:
        return FusionLevel.DANGER
    if level == SafetyLevel.CAUTION:
        return FusionLevel.CAUTION
    return FusionLevel.SAFE


def fuse_vision_and_lidar(vision: VisionSafetyResult, lidar_cm: Optional[float]) -> FusionResult:
    """
    根据视觉 zone / d(px) + 雷达距离(厘米) 得出融合后的安全等级。
    规则简洁，所有厘米阈值来自 LIDAR_FUSION。
    """
    cfg = LIDAR_FUSION

    # 雷达缺失或超出可信范围：退化为纯视觉
    if lidar_cm is None or lidar_cm > cfg.max_valid_cm:
        return FusionResult(
            level=_vision_level_to_fusion(vision.level),
            reason="vision-only (lidar missing or invalid)",
            vision=vision,
            lidar_cm=lidar_cm,
        )

    # 雷达有效
    if lidar_cm <= cfg.danger_cm:
        return FusionResult(
            level=FusionLevel.DANGER,
            reason="lidar too close",
            vision=vision,
            lidar_cm=lidar_cm,
        )

    if lidar_cm <= cfg.caution_cm:
        if vision.zone == SafetyZone.INSIDE_DANGER:
            return FusionResult(
                level=FusionLevel.DANGER,
                reason="vision inside danger and lidar caution range",
                vision=vision,
                lidar_cm=lidar_cm,
            )
        return FusionResult(
            level=FusionLevel.CAUTION,
            reason="lidar caution range",
            vision=vision,
            lidar_cm=lidar_cm,
        )

    # lidar_cm > caution_cm
    if vision.zone == SafetyZone.OUTSIDE_SAFE:
        return FusionResult(
            level=FusionLevel.SAFE,
            reason="lidar safe distance and vision outside safe",
            vision=vision,
            lidar_cm=lidar_cm,
        )

    # 其他情况：沿用视觉等级
    return FusionResult(
        level=_vision_level_to_fusion(vision.level),
        reason="vision-driven level",
        vision=vision,
        lidar_cm=lidar_cm,
    )


if __name__ == "__main__":
    # 简单自测：构造几组 Vision + LiDAR 组合
    scenarios = [
        ("vision_safe_no_lidar", VisionSafetyResult(SafetyLevel.SAFE, SafetyZone.OUTSIDE_SAFE), None),
        ("vision_caution_no_lidar", VisionSafetyResult(SafetyLevel.CAUTION, SafetyZone.ON_LINE), None),
        ("lidar_too_close", VisionSafetyResult(SafetyLevel.SAFE, SafetyZone.OUTSIDE_SAFE), 90.0),
        ("lidar_caution_and_vision_danger", VisionSafetyResult(SafetyLevel.DANGER, SafetyZone.INSIDE_DANGER), 150.0),
        ("lidar_safe_and_vision_safe", VisionSafetyResult(SafetyLevel.SAFE, SafetyZone.OUTSIDE_SAFE), 250.0),
        ("lidar_safe_but_vision_caution", VisionSafetyResult(SafetyLevel.CAUTION, SafetyZone.ON_LINE), 250.0),
        ("lidar_invalid_far", VisionSafetyResult(SafetyLevel.SAFE, SafetyZone.OUTSIDE_SAFE), 700.0),
    ]

    for name, vision_res, lidar_val in scenarios:
        fused = fuse_vision_and_lidar(vision_res, lidar_val)
        print(f"[TEST] {name:28s} -> level={fused.level:7s} reason={fused.reason} lidar={fused.lidar_cm}")
