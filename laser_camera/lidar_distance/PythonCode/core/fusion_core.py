from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class LidarMoveStatus(Enum):
    IDLE = auto()          # no valid reading / no person
    STABLE = auto()        # person is stably at some distance
    TRANSIT = auto()       # person is moving between cabinets


class VisionZone(Enum):
    OUTSIDE_SAFE = auto()  # far away from yellow line
    NEAR_LINE = auto()     # close to line, but still safe
    ON_LINE = auto()       # on the yellow line
    INSIDE_DANGER = auto() # beyond the yellow line


class FusionState(Enum):
    IDLE = auto()
    SAFE = auto()
    WARNING = auto()
    DANGER = auto()


@dataclass
class LidarStatus:
    ok: bool
    distance_cm: Optional[float]
    cabinet_id: Optional[int]
    move_status: LidarMoveStatus


@dataclass
class VisionStatus:
    has_person: bool
    zone: Optional[VisionZone]


@dataclass
class FusionDecision:
    state: FusionState
    message: str


def fuse_safety(
    lidar: LidarStatus,
    vision: VisionStatus,
    authorized_cabinets: Optional[list[int]] = None,
) -> FusionDecision:
    """
    Combine lidar status and vision status into a fused safety decision.
    Pure logic only; no I/O or hardware access.
    """

    authorized = authorized_cabinets or []

    # Case A: no person anywhere
    if (not vision.has_person) and (not lidar.ok or lidar.move_status is LidarMoveStatus.IDLE):
        return FusionDecision(
            state=FusionState.IDLE,
            message="IDLE: no person detected by lidar or vision.",
        )

    # Case B: lidar bad but vision sees a person
    if (not lidar.ok) and vision.has_person:
        return FusionDecision(
            state=FusionState.WARNING,
            message="WARNING: vision sees a person but lidar has no valid reading.",
        )

    # Case C: person is moving (TRANSIT)
    if lidar.move_status is LidarMoveStatus.TRANSIT:
        return FusionDecision(
            state=FusionState.WARNING,
            message="WARNING: person in transit between cabinets.",
        )

    # Case D: person is stable at some cabinet
    if lidar.move_status is LidarMoveStatus.STABLE and lidar.cabinet_id is not None:
        cab_id = lidar.cabinet_id

        if authorized and cab_id not in authorized:
            return FusionDecision(
                state=FusionState.DANGER,
                message=f"DANGER: person at unauthorized cabinet #{cab_id}.",
            )

        if (not vision.has_person) or (vision.zone is None):
            return FusionDecision(
                state=FusionState.WARNING,
                message=f"WARNING: lidar stable at cabinet #{cab_id} but vision sees no person.",
            )

        if vision.zone is VisionZone.INSIDE_DANGER:
            return FusionDecision(
                state=FusionState.DANGER,
                message=f"DANGER: person beyond yellow line at cabinet #{cab_id}.",
            )

        if vision.zone is VisionZone.ON_LINE:
            return FusionDecision(
                state=FusionState.WARNING,
                message=f"WARNING: person on yellow line at cabinet #{cab_id}.",
            )

        if vision.zone is VisionZone.NEAR_LINE:
            return FusionDecision(
                state=FusionState.WARNING,
                message=f"WARNING: person near yellow line at cabinet #{cab_id}.",
            )

        if vision.zone is VisionZone.OUTSIDE_SAFE:
            return FusionDecision(
                state=FusionState.SAFE,
                message=f"SAFE: person at authorized cabinet #{cab_id} and outside yellow line.",
            )

    # Default fallback
    return FusionDecision(
        state=FusionState.WARNING,
        message="WARNING: unexpected combination of lidar and vision status.",
    )


def _self_test() -> None:
    scenarios = [
        (
            "idle",
            LidarStatus(ok=False, distance_cm=None, cabinet_id=None, move_status=LidarMoveStatus.IDLE),
            VisionStatus(has_person=False, zone=None),
            [1],
        ),
        (
            "stable authorized safe zone",
            LidarStatus(ok=True, distance_cm=150.0, cabinet_id=1, move_status=LidarMoveStatus.STABLE),
            VisionStatus(has_person=True, zone=VisionZone.OUTSIDE_SAFE),
            [1],
        ),
        (
            "stable unauthorized",
            LidarStatus(ok=True, distance_cm=180.0, cabinet_id=2, move_status=LidarMoveStatus.STABLE),
            VisionStatus(has_person=True, zone=VisionZone.OUTSIDE_SAFE),
            [1],
        ),
        (
            "stable authorized inside danger",
            LidarStatus(ok=True, distance_cm=120.0, cabinet_id=1, move_status=LidarMoveStatus.STABLE),
            VisionStatus(has_person=True, zone=VisionZone.INSIDE_DANGER),
            [1],
        ),
        (
            "lidar bad vision person",
            LidarStatus(ok=False, distance_cm=None, cabinet_id=None, move_status=LidarMoveStatus.IDLE),
            VisionStatus(has_person=True, zone=VisionZone.NEAR_LINE),
            [1],
        ),
        (
            "transit",
            LidarStatus(ok=True, distance_cm=200.0, cabinet_id=None, move_status=LidarMoveStatus.TRANSIT),
            VisionStatus(has_person=True, zone=VisionZone.NEAR_LINE),
            [1],
        ),
    ]

    for name, lidar, vision, auth in scenarios:
        decision = fuse_safety(lidar, vision, auth)
        print(f"TEST {name:30s} -> state={decision.state.name:7s} msg={decision.message}")


if __name__ == "__main__":
    _self_test()
