#!/usr/bin/env python3
"""
fusion_engine.py

Fuse LIDAR status + Vision safety result into a final safety state.

Interface contract used by main_fusion_system.py:

- Enum FusionState: IDLE, SAFE, WARNING, DANGER
- class FusionEngine:
    - __init__(authorized_cabinets: list[int])
    - update(lidar_status: dict, vision_result: Any) -> FusionResult

- FusionResult fields used by main_fusion_system.py:
    - state: FusionState
    - message: str
    - lidar: LidarSnapshot
        - distance_m: Optional[float]
        - cabinet_id: Optional[int]
        - status: str
    - vision: VisionSnapshot
        - person_detected: bool
        - is_on_target: bool
    - output_enabled: bool
        # This is the final "hardware output" flag.
        # SAFE + at authorized cabinet -> True
        # All other states -> False  (fail-safe)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Optional


class FusionState(Enum):
    IDLE = auto()
    SAFE = auto()
    WARNING = auto()
    DANGER = auto()


@dataclass
class LidarSnapshot:
    distance_m: Optional[float]
    cabinet_id: Optional[int]
    status: str  # "STABLE" | "TRANSIT" | "NO_DATA" | others


@dataclass
class VisionSnapshot:
    person_detected: bool
    is_on_target: bool


@dataclass
class FusionResult:
    state: FusionState
    message: str
    lidar: LidarSnapshot
    vision: VisionSnapshot
    output_enabled: bool


class FusionEngine:
    """
    Combine LIDAR + Vision into a final safety decision.

    Policy (engineering-oriented):

    - IDLE:
        No person detected AND no valid LIDAR data (status NO_DATA).

    - WARNING:
        Person is moving / cabinet unknown:
            - LIDAR status "TRANSIT" OR cabinet_id is None
          OR
            - Vision sees a person, but they are NOT on the cabinet target zone.

    - SAFE:
        - LIDAR:
            status == "STABLE"
            AND cabinet_id in authorized_cabinets
        - Vision:
            person_detected == True
            AND is_on_target == True

    - DANGER:
        - LIDAR:
            status == "STABLE"
            AND cabinet_id NOT in authorized_cabinets
          (Person is stably working at a NON-AUTHORIZED cabinet)
        OR
        - any other inconsistent situation that should be treated as unsafe.

    Hardware flag:
        output_enabled = True  only when state == SAFE
        output_enabled = False for all other states  (fail-safe)
    """

    def __init__(self, authorized_cabinets: List[int]) -> None:
        self.authorized_cabinets = set(authorized_cabinets)

    def _build_lidar_snapshot(self, lidar_status: dict) -> LidarSnapshot:
        return LidarSnapshot(
            distance_m=lidar_status.get("distance_m"),
            cabinet_id=lidar_status.get("cabinet_id"),
            status=str(lidar_status.get("status", "NO_DATA")),
        )

    def _build_vision_snapshot(self, vision_result: Any) -> VisionSnapshot:
        person_detected = bool(getattr(vision_result, "person_detected", False))
        is_on_target = bool(getattr(vision_result, "is_on_target", False))
        return VisionSnapshot(
            person_detected=person_detected,
            is_on_target=is_on_target,
        )

    def update(self, lidar_status: dict, vision_result: Any) -> FusionResult:
        lidar = self._build_lidar_snapshot(lidar_status)
        vision = self._build_vision_snapshot(vision_result)

        # --- Determine state ---
        # IDLE: no person + no LIDAR data
        if not vision.person_detected and (lidar.status == "NO_DATA" or lidar.cabinet_id is None):
            state = FusionState.IDLE
            message = "No person detected and no valid LIDAR data."
        else:
            # If LIDAR says "moving" or cabinet unknown -> WARNING
            if lidar.status == "TRANSIT" or lidar.cabinet_id is None:
                state = FusionState.WARNING
                message = "Person moving or cabinet unknown (TRANSIT)."
            else:
                # We treat anything else as STABLE / usable
                cab_id = lidar.cabinet_id
                is_authorized = cab_id in self.authorized_cabinets if cab_id is not None else False

                if lidar.status == "STABLE":
                    if is_authorized and vision.person_detected and vision.is_on_target:
                        state = FusionState.SAFE
                        message = f"Person working at authorized cabinet {cab_id}."
                    elif is_authorized and vision.person_detected and not vision.is_on_target:
                        # Authorized cabinet but not on target zone -> WARNING
                        state = FusionState.WARNING
                        message = (
                            f"Person detected but not on the target zone of authorized cabinet {cab_id}."
                        )
                    elif not is_authorized and cab_id is not None:
                        state = FusionState.DANGER
                        message = f"Person at NON-AUTHORIZED cabinet {cab_id}."
                    else:
                        # Fallback for weird states
                        state = FusionState.WARNING
                        message = "Inconsistent LIDAR/Vision state (treated as WARNING)."
                else:
                    # Any other LIDAR status we don't fully understand -> WARNING
                    state = FusionState.WARNING
                    message = f"Unexpected LIDAR status={lidar.status}, treated as WARNING."

        # --- Hardware output policy ---
        output_enabled = (state == FusionState.SAFE)

        return FusionResult(
            state=state,
            message=message,
            lidar=lidar,
            vision=vision,
            output_enabled=output_enabled,
        )
