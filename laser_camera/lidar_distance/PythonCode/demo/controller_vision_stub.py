#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""带视觉逻辑的安全监控仿真控制器：VisionState + LiDAR + 安全告警。"""

from __future__ import annotations


import sys
import os
# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itertools
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional, Tuple

from demo.controller_stub import LidarSource


from core.safety_logic import (
    AlarmResult,
    SafetyState,
    alarm_level_to_color,
    evaluate_safety_state,
    format_alarm_for_log,
)
from core.vision_logic import (
    ActionStatus,
    BodyOrientation,
    GestureCode,
    GestureTracker,
    LinePosition,
    VisionState,
    is_cross_line,
    should_activate_lidar,
)


@dataclass
class VisionSource:
    """模拟摄像头输出的 VisionState 序列，用于仿真调试。"""

    states_sequence: Iterable[VisionState]

    def stream(self) -> Iterator[VisionState]:
        """
        返回一个无限迭代器，循环输出 VisionState。

        在真实系统中，这里会被实时摄像头检测逻辑替换。
        """

        return itertools.cycle(self.states_sequence)


DEFAULT_VISION_SEQUENCE = [
    VisionState(False, LinePosition.SAFE_ZONE, BodyOrientation.TURNED_AWAY, GestureCode.NONE),
    VisionState(True, LinePosition.SAFE_ZONE, BodyOrientation.TURNED_AWAY, GestureCode.NONE),
    VisionState(True, LinePosition.ON_LINE, BodyOrientation.SIDEWAYS, GestureCode.NONE),
    VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
    VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
    VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.AUTHORIZED),
    VisionState(True, LinePosition.ON_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
    VisionState(True, LinePosition.BEYOND_LINE, BodyOrientation.FACING_CABINET, GestureCode.NONE),
]


@dataclass
class VisionSafetyController:
    """
    带视觉信息的安全控制器。

    - 从 VisionSource 读取 VisionState；
    - 使用 GestureTracker 评估当前动作状态；
    - 在需要时从 LiDAR 数据源读取机位；
    - 将状态送入安全逻辑，并在结果中附加视觉/动作信息。
    """

    lidar_source: LidarSource
    vision_source: VisionSource
    target_cabinet: Optional[int] = None
    tracker: GestureTracker = field(default_factory=GestureTracker)

    def __post_init__(self) -> None:
        self._lidar_iter = self.lidar_source.stream()
        self._vision_iter = self.vision_source.stream()

    def set_target_cabinet(self, cabinet: Optional[int]) -> None:
        """设置/修改授权机位，None 表示当前不授权任何机位。"""

        self.target_cabinet = cabinet
        self.tracker.reset()

    def step(self) -> Tuple[AlarmResult, VisionState, ActionStatus]:
        """
        执行一步安全评估，返回告警结果、当前视觉状态与动作状态。
        """

        vision_state = next(self._vision_iter)
        cross_line = is_cross_line(vision_state)
        target_active = self.target_cabinet is not None
        action_status = self.tracker.update(vision_state, target_active)

        if should_activate_lidar(vision_state):
            current_cabinet = next(self._lidar_iter)
        else:
            current_cabinet = None

        state = SafetyState(
            target_cabinet=self.target_cabinet,
            current_cabinet=current_cabinet,
            cross_line=cross_line,
        )
        alarm = evaluate_safety_state(state)

        alarm.details["action_status"] = action_status.name
        alarm.details["person_present"] = vision_state.person_present
        alarm.details["line_position"] = vision_state.line_position.name
        alarm.details["orientation"] = vision_state.orientation.name
        alarm.details["gesture"] = vision_state.gesture.name

        return alarm, vision_state, action_status


def run_simulation(steps: int = 20, interval_s: float = 0.5) -> None:
    """运行一段时间的仿真，打印融合后的告警与视觉状态。"""

    vision_source = VisionSource(DEFAULT_VISION_SEQUENCE)
    DEFAULT_CABINET_SEQUENCE = [None, None, 1, 1, 1, 1, 1, 1]
    lidar_source = LidarSource(DEFAULT_CABINET_SEQUENCE)
    controller = VisionSafetyController(
        lidar_source=lidar_source,
        vision_source=vision_source,
        target_cabinet=1,
    )

    for step in range(steps):
        alarm, vision_state, action_status = controller.step()
        log_line = format_alarm_for_log(alarm)
        color = alarm_level_to_color(alarm.level)
        vision_info = (
            f"action_status={action_status.name} "
            f"person_present={vision_state.person_present} "
            f"line={vision_state.line_position.name} "
            f"orient={vision_state.orientation.name} "
            f"gesture={vision_state.gesture.name}"
        )
        print(f"[{color}] {log_line}")
        print(f"  {vision_info}")
        time.sleep(interval_s)


def main() -> None:
    """使用模拟视觉 + 模拟 LiDAR 运行一段时间，演示融合控制器效果。"""

    run_simulation()


if __name__ == "__main__":
    main()