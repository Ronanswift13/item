#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无硬件仿真的主控框架，用于串联机位判定与安全告警逻辑。"""

from __future__ import annotations

import sys
import os
# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itertools
import time
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

from core.safety_logic import (
    AlarmResult,
    SafetyState,
    alarm_level_to_color,
    evaluate_safety_state,
    format_alarm_for_log,
)

# 可自由修改以下序列以模拟不同人员站位与越线场景
DEFAULT_CABINET_SEQUENCE = [1, 1, 2, 2, 3, None]
DEFAULT_CROSS_LINE_SEQUENCE = [False, False, True, False, True, False]


@dataclass
class LidarSource:
    """模拟激光雷达机位输出的简单数据源（仿真 stub，可替换为真实实现）。"""

    cabinets_sequence: Iterable[Optional[int]]

    def stream(self) -> Iterator[Optional[int]]:
        """返回一个无限迭代器，循环输出机位编号。"""

        return itertools.cycle(self.cabinets_sequence)


@dataclass
class CameraSource:
    """模拟摄像头越线检测输出的简单数据源（仿真 stub，可替换为真实实现）。"""

    cross_line_sequence: Iterable[bool]

    def stream(self) -> Iterator[bool]:
        """返回一个无限迭代器，循环输出越线布尔值。"""

        return itertools.cycle(self.cross_line_sequence)


class SafetyController:
    """主控逻辑（仿真版）：汇总传感器状态并调用安全策略模块。"""

    def __init__(
        self,
        lidar_source: LidarSource,
        camera_source: CameraSource,
        target_cabinet: Optional[int] = None,
    ) -> None:
        self.lidar_iter = lidar_source.stream()
        self.camera_iter = camera_source.stream()
        self.target_cabinet = target_cabinet

    def set_target_cabinet(self, cabinet: Optional[int]) -> None:
        """动态修改授权机位，可在运行中响应操作票变更。"""

        self.target_cabinet = cabinet

    def step(self) -> AlarmResult:
        """执行一步：读取传感器状态并返回告警结果。"""

        current_cabinet = next(self.lidar_iter)
        cross_line = next(self.camera_iter)
        state = SafetyState(
            target_cabinet=self.target_cabinet,
            current_cabinet=current_cabinet,
            cross_line=cross_line,
        )
        return evaluate_safety_state(state)


def run_simulation(
    target_plan: Iterable[Optional[int]],
    lidar_source: LidarSource,
    camera_source: CameraSource,
    interval_s: float = 0.5,
    iterations: Optional[int] = None,
) -> None:
    """
    主循环：综合仿真源并驱动安全逻辑。

    Args:
        target_plan: 允许的机位序列，将被循环使用，模拟操作票变更。
        lidar_source: 激光雷达机位编号数据源。
        camera_source: 越线检测数据源。
        interval_s: 循环间隔，模拟实时刷新。
        iterations: 限定循环次数；None 时表示持续运行。
    """

    target_iter = itertools.cycle(target_plan)
    controller = SafetyController(lidar_source=lidar_source, camera_source=camera_source)

    step = 0
    try:
        while iterations is None or step < iterations:
            controller.set_target_cabinet(next(target_iter))
            result: AlarmResult = controller.step()
            print(format_alarm_for_log(result))
            print(f"UI color: {alarm_level_to_color(result.level)}")

            step += 1
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print("\n收到中断信号，停止仿真。")


def build_demo_sources() -> tuple[Iterable[Optional[int]], LidarSource, CameraSource]:
    """构建一组示例序列，便于主程序直接运行。"""

    target_plan = [None, 1, 1, 2, 2, None, None]
    lidar_sequence = [None, 1, 1, 2, 3, 2, None]
    camera_sequence = [False, False, True, False, True, False, False]
    return target_plan, LidarSource(lidar_sequence), CameraSource(camera_sequence)


def main() -> None:
    """主入口：使用默认序列驱动仿真控制器，验证安全逻辑。"""

    lidar = LidarSource(DEFAULT_CABINET_SEQUENCE)
    camera = CameraSource(DEFAULT_CROSS_LINE_SEQUENCE)
    controller = SafetyController(lidar, camera, target_cabinet=1)

    print(
        "启动仿真主控：修改 DEFAULT_CABINET_SEQUENCE / DEFAULT_CROSS_LINE_SEQUENCE 可模拟不同场景（Ctrl+C 结束）"
    )
    try:
        while True:
            result = controller.step()
            log_line = format_alarm_for_log(result)
            color = alarm_level_to_color(result.level)
            print(f"[{color}] {log_line}")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n仿真结束。")


if __name__ == "__main__":
    main()