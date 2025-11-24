#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全策略逻辑模块，仅根据外部输入的状态评估告警等级。"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

__all__ = [
    "AlarmLevel",
    "SafetyState",
    "AlarmResult",
    "evaluate_safety_state",
    "evaluate_safety",
    "format_alarm_for_log",
    "alarm_level_to_color",
]


class AlarmLevel(enum.Enum):
    """告警等级划分。"""

    NORMAL = "normal"
    WRONG_CABINET = "wrong_cabinet"
    CROSS_LINE = "cross_line"
    MULTIPLE_VIOLATIONS = "multiple_violations"
    NO_PERMISSION = "no_permission"


@dataclass
class SafetyState:
    """当前安全状态（由其它子系统汇总后传入）。"""

    target_cabinet: Optional[int]
    current_cabinet: Optional[int]
    cross_line: bool


@dataclass
class AlarmResult:
    """告警评估结果。"""

    level: AlarmLevel
    message: str
    timestamp: datetime
    details: Dict[str, Any]


def evaluate_safety_state(state: SafetyState) -> AlarmResult:
    """
    根据安全状态判断告警等级，并生成可记录的描述信息。

    Args:
        state: 来自雷达、视觉等模块的综合状态。
    Returns:
        AlarmResult，包含等级、中文提示、时间戳及原始状态详情。
    """

    timestamp = datetime.now()
    message: str

    # 情况 A：未配置目标机位，表示当前不允许任何检修操作
    if state.target_cabinet is None:
        if state.current_cabinet is None and not state.cross_line:
            # 无人站在机位且视觉未检测越线，视为安全待命
            level = AlarmLevel.NORMAL
            message = "当前未配置检修机位，未检测到人员活动。"
        else:
            # 检测到有人靠近或越线，属于禁止操作状态
            level = AlarmLevel.NO_PERMISSION
            message = "当前未配置检修机位，但检测到人员靠近或越线，请立即制止。"
    else:
        # 情况 B：已配置允许的机位
        if state.current_cabinet is None:
            # 人员未落在任何机位，可视为提醒但仍安全
            level = AlarmLevel.NORMAL
            message = f"授权机位为 {state.target_cabinet}，人员不在任何机位。"
        elif state.current_cabinet == state.target_cabinet:
            if state.cross_line:
                # 机位正确但越线，需要黄色告警
                level = AlarmLevel.CROSS_LINE
                message = f"机位 {state.target_cabinet} 正确，但人员越过黄线，请注意安全距离。"
            else:
                # 机位正确且未越线，状态正常
                level = AlarmLevel.NORMAL
                message = f"机位 {state.target_cabinet} 正确且未越线，状态正常。"
        else:
            # 人员站错机位
            if state.cross_line:
                # 站错机位且越线，判定为多重违规
                level = AlarmLevel.MULTIPLE_VIOLATIONS
                message = (
                    f"授权机位为 {state.target_cabinet}，检测到人员在 {state.current_cabinet} 且越线，存在多重违规！"
                )
            else:
                # 仅站错机位
                level = AlarmLevel.WRONG_CABINET
                message = (
                    f"授权机位为 {state.target_cabinet}，但人员站在 {state.current_cabinet}，请指引到正确机位。"
                )

    details: Dict[str, Any] = {**asdict(state), "evaluated_at": timestamp.isoformat()}
    return AlarmResult(level=level, message=message, timestamp=timestamp, details=details)


def evaluate_safety(state: SafetyState) -> AlarmResult:
    """保持向后兼容的别名。"""

    return evaluate_safety_state(state)


def format_alarm_for_log(result: AlarmResult) -> str:
    """
    将告警结果格式化为一行日志，方便写入文件或终端。

    格式示例：
        [2024-05-01T12:00:00] level=NORMAL target=1 current=1 cross_line=False message=xxx
    """

    details = result.details
    target = details.get("target_cabinet")
    current = details.get("current_cabinet")
    cross_line = details.get("cross_line")
    return (
        f"[{result.timestamp.isoformat()}] level={result.level.name} "
        f"target={target} current={current} cross_line={cross_line} message={result.message}"
    )


def alarm_level_to_color(level: AlarmLevel) -> str:
    """
    将告警等级映射为 UI 颜色建议。

    - NORMAL 返回 green
    - CROSS_LINE、WRONG_CABINET 返回 yellow
    - MULTIPLE_VIOLATIONS、NO_PERMISSION 返回 red
    """

    if level is AlarmLevel.NORMAL:
        return "green"
    if level in (AlarmLevel.CROSS_LINE, AlarmLevel.WRONG_CABINET):
        return "yellow"
    return "red"


if __name__ == "__main__":
    # 简易自检：当模块独立运行时展示一个示例结果，便于快速手动验证。
    demo_state = SafetyState(target_cabinet=1, current_cabinet=2, cross_line=True)
    result = evaluate_safety_state(demo_state)
    print(result)
    print(format_alarm_for_log(result))