#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉检测抽象层：黄线位置 + 动作识别 → 安全逻辑中间状态。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from datetime import datetime
from typing import Optional


class LinePosition(Enum):
    """相对黄线的位置状态。"""

    UNKNOWN = auto()
    SAFE_ZONE = auto()
    ON_LINE = auto()
    BEYOND_LINE = auto()


class BodyOrientation(Enum):
    """人体朝向枚举，用于判断是否面向机柜。"""

    UNKNOWN = auto()
    FACING_CABINET = auto()
    FACING_CAMERA = auto()
    TURNED_AWAY = auto()
    SIDEWAYS = auto()


class GestureCode(Enum):
    """识别到的手势/动作类型。"""

    NONE = auto()
    AUTHORIZED = auto()
    OTHER = auto()


class ActionStatus(Enum):
    """操作动作的当前状态。"""

    IDLE = auto()
    WAIT_GESTURE = auto()
    READY = auto()
    VIOLATION_NO_GESTURE = auto()


@dataclass
class VisionState:
    """单帧视觉检测状态：人是否存在、相对黄线位置、朝向和动作。"""

    person_present: bool
    line_position: LinePosition
    orientation: BodyOrientation
    gesture: GestureCode
    timestamp: Optional[datetime] = None
    frame_base64: Optional[str] = None

    def with_timestamp(self, ts: Optional[datetime] = None) -> "VisionState":
        """返回带时间戳的拷贝，如果 ts 为 None 则使用当前时间。"""

        return VisionState(
            person_present=self.person_present,
            line_position=self.line_position,
            orientation=self.orientation,
            gesture=self.gesture,
            timestamp=ts or datetime.now(),
        )


def is_cross_line(state: VisionState) -> bool:
    """判断当前帧是否越过黄线，供安全逻辑填充 cross_line 使用。"""

    return state.line_position == LinePosition.BEYOND_LINE


def should_activate_lidar(state: VisionState) -> bool:
    """判断是否需要激活激光雷达：有人且面向机柜时才需要精确测距。"""

    return state.person_present and state.orientation == BodyOrientation.FACING_CABINET


@dataclass
class GestureTracker:
    """
    在多帧之间跟踪“是否已完成授权动作”的状态，并给出当前操作状态。

    max_wait_frames 表示在固定帧率下等待授权动作的最大帧数。
    例如 10Hz 摄像头、max_wait_frames=20 对应约 2 秒。
    """

    max_wait_frames: int = 15
    frames_waiting: int = 0
    has_authorized_gesture: bool = False

    def reset(self) -> None:
        """清空等待计数与授权标记，在离开机位或取消授权时调用。"""

        self.frames_waiting = 0
        self.has_authorized_gesture = False

    def update(self, state: VisionState, target_cabinet_active: bool) -> ActionStatus:
        """
        根据当前视觉状态与授权机位配置评估动作状态。

        Args:
            state: 当前帧的视觉检测结果。
            target_cabinet_active: 是否存在授权的目标机位。
        """

        if not target_cabinet_active or not state.person_present:
            self.reset()
            return ActionStatus.IDLE

        if not should_activate_lidar(state):
            # 未面向机柜或姿态不对，认为还未进入操作流程
            self.reset()
            return ActionStatus.IDLE

        if self.has_authorized_gesture:
            # 已完成授权动作，保持 READY 状态
            return ActionStatus.READY

        if state.gesture == GestureCode.AUTHORIZED:
            self.has_authorized_gesture = True
            self.frames_waiting = 0
            return ActionStatus.READY

        # 有授权机位且姿态正确，但尚未完成动作
        self.frames_waiting += 1
        if self.frames_waiting >= self.max_wait_frames:
            return ActionStatus.VIOLATION_NO_GESTURE
        return ActionStatus.WAIT_GESTURE


def simulate_sequence() -> None:
    """构造一组示例视觉状态，展示 GestureTracker 的状态变化。"""

    tracker = GestureTracker(max_wait_frames=5)
    sequence = [
        VisionState(False, LinePosition.SAFE_ZONE, BodyOrientation.TURNED_AWAY, GestureCode.NONE),
        VisionState(False, LinePosition.SAFE_ZONE, BodyOrientation.TURNED_AWAY, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.SIDEWAYS, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.SIDEWAYS, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.AUTHORIZED),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
        VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
    ]

    for idx, state in enumerate(sequence):
        status = tracker.update(state, target_cabinet_active=True)
        cross = is_cross_line(state)
        activate = should_activate_lidar(state)
        print(
            f"t={idx:02d} line={state.line_position.name} orient={state.orientation.name} "
            f"gesture={state.gesture.name} -> status={status.name}, "
            f"cross_line={cross}, activate_lidar={activate}"
        )


def main() -> None:
    """简单演示 GestureTracker 与 VisionState 的配合效果。"""

    simulate_sequence()


if __name__ == "__main__":
    main()