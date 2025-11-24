#!/usr/bin/env python3
"""
core/output_policy.py

Map vision safety level (SAFE / CAUTION / DANGER) to
a set of "output actions" for relay / buzzer / alarm light.

Right now this is only a software stub:
- It prints the intended actions to console.
Later it can be replaced with real GPIO / PLC / relay control code.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class OutputState:
    level_name: str
    relay_enabled: bool
    buzzer_on: bool
    light_color: str  # "GREEN", "YELLOW", "RED"


class OutputPolicy:
    """
    Given a safety level, decide what the "outputs" should do.

    This class is designed to accept either:
    - an Enum-like value with `.name` (e.g. VisionLevel.SAFE), or
    - a plain string "SAFE" / "CAUTION" / "DANGER".
    """

    def __init__(self) -> None:
        # You can add hardware init here in the future (serial, GPIO, PLC, etc.)
        pass

    def _normalize_level_name(self, level: Any) -> str:
        """
        Convert level to upper-case string, e.g. VisionLevel.SAFE -> "SAFE".
        """
        if hasattr(level, "name"):
            return str(level.name).upper()
        return str(level).upper()

    def decide_state(self, level: Any) -> OutputState:
        name = self._normalize_level_name(level)

        if name == "DANGER":
            # Most strict: cut relay, red light, buzzer on.
            return OutputState(
                level_name=name,
                relay_enabled=False,
                buzzer_on=True,
                light_color="RED",
            )
        elif name == "CAUTION":
            # Medium: allow relay, yellow light, no buzzer (or slow beeps in future).
            return OutputState(
                level_name=name,
                relay_enabled=True,
                buzzer_on=False,
                light_color="YELLOW",
            )
        else:
            # Default SAFE: relay allowed, green light, no buzzer.
            return OutputState(
                level_name=name,
                relay_enabled=True,
                buzzer_on=False,
                light_color="GREEN",
            )

    def apply(self, level: Any) -> None:
        """
        Decide and "apply" the output.
        Currently it only prints to console.
        Later you can replace the print with:
        - GPIO write
        - serial command to PLC
        - Modbus/TCP packet, etc.
        """
        state = self.decide_state(level)

        # Software stub: just log the intended state.
        print(
            f"[OUTPUT] level={state.level_name} "
            f"relay_enabled={state.relay_enabled} "
            f"buzzer_on={state.buzzer_on} "
            f"light_color={state.light_color}"
        )
