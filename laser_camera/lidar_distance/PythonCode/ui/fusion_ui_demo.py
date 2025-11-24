from __future__ import annotations

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import threading
import time
from datetime import datetime
from pathlib import Path

import flet as ft

try:
    from flet import colors
except ImportError:
    class _FallbackColors:
        GREY_200 = "#eeeeee"
        RED = "#ff0000"
        GREEN = "#00ff00"
    colors = _FallbackColors()

from core.new_lidar import get_lidar_distance_cm, NewLidarError
from core.lidar_zone_logic  import (
    CabinetZone,
    LidarZoneTracker,
    LidarStatus,
    LidarDecision,
)


def build_tracker() -> tuple[LidarZoneTracker, set[int]]:
    zones = [
        CabinetZone(1, 1.50 - 0.45, 1.50 + 0.45),
        CabinetZone(2, 2.40 - 0.45, 2.40 + 0.45),
        CabinetZone(3, 3.855 - 0.45, 3.855 + 0.45),
        CabinetZone(4, 4.755 - 0.45, 4.755 + 0.45),
        CabinetZone(5, 5.655 - 0.45, 5.655 + 0.45),
    ]
    tracker = LidarZoneTracker(
        zones=zones,
        movement_threshold_m=0.20,
        static_threshold_m=0.08,
        static_window_s=2.0,
        walk_window_s=1.5,
    )
    authorized = {1, 3}
    return tracker, authorized


def main(page: ft.Page) -> None:
    page.title = "Fusion UI Demo"

    title_text = ft.Text("Fusion Monitor", size=24, weight=ft.FontWeight.BOLD)
    distance_text = ft.Text("distance: --", size=20)
    warning_text = ft.Text("warning: SAFE", size=22, weight=ft.FontWeight.BOLD)
    cabinet_label = ft.Text("cabinet: --", size=18)
    status_label = ft.Text("status: IDLE", size=18)
    reason_label = ft.Text("reason: --", size=14)
    log_view = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    placeholder_src = "data:image/gif;base64,R0lGODlhAQABAAAAACw="
    image_view = ft.Image(width=320, height=240, fit=ft.ImageFit.CONTAIN, src=placeholder_src)
    placeholder_text = ft.Text(
        "No camera frame (frame_base64 is None)",
        size=14,
        text_align=ft.TextAlign.CENTER,
        weight=ft.FontWeight.BOLD,
    )
    image_container = ft.Container(
        width=320,
        height=240,
        bgcolor=colors.GREY_200,
        content=ft.Stack(
            [
                image_view,
                ft.Container(content=placeholder_text, alignment=ft.alignment.center),
            ],
            expand=True,
        ),
    )

    record_state = {"enabled": False}
    tracker, authorized_default = build_tracker()
    authorized_state = {"ids": set(authorized_default)}

    def on_record_toggle(e: ft.ControlEvent) -> None:
        record_state["enabled"] = bool(e.control.value)
        page.update()

    record_switch = ft.Checkbox(label="Record to fusion_log.csv", value=False, on_change=on_record_toggle)

    def log_add(message: str) -> None:
        log_view.controls.append(ft.Text(message))
        if len(log_view.controls) > 50:
            del log_view.controls[0]

    def on_authorized_change(index: int, e: ft.ControlEvent) -> None:
        if e.control.value:
            authorized_state["ids"].add(index)
        else:
            authorized_state["ids"].discard(index)
        page.update()

    checkbox_row = ft.Row(
        [
            ft.Checkbox(
                label=f"Cab {idx}",
                value=(idx in authorized_state["ids"]),
                on_change=lambda e, i=idx: on_authorized_change(i, e),
            )
            for idx in range(1, 6)
        ],
        spacing=10,
    )

    page.add(
        ft.Column(
            [
                title_text,
                distance_text,
                warning_text,
                checkbox_row,
                cabinet_label,
                status_label,
                reason_label,
                record_switch,
                image_container,
                ft.Text("Event log:"),
                log_view,
            ],
            expand=True,
        )
    )

    csv_path = Path(__file__).with_name("fusion_log.csv")

    def append_csv_row(decision: LidarDecision, distance_cm: float | None) -> None:
        file_exists = csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            if not file_exists:
                writer.writerow(
                    [
                        "timestamp_iso",
                        "distance_cm",
                        "cabinet_index",
                        "status",
                        "is_safe",
                        "reason",
                    ]
                )
            writer.writerow(
                [
                    datetime.now().isoformat(),
                    distance_cm,
                    decision.cabinet_index,
                    decision.status.name,
                    decision.is_safe,
                    decision.reason,
                ]
            )

    def update_loop() -> None:
        while True:
            try:
                distance_cm = get_lidar_distance_cm()
            except NewLidarError as exc:
                decision = tracker.update(None, authorized_cabinets=authorized_state["ids"])
                distance_text.value = "distance: --"
                warning_text.value = "warning: SENSOR ERROR"
                warning_text.color = colors.RED
                cabinet_label.value = "cabinet: --"
                status_label.value = f"status: {decision.status.name}"
                reason_label.value = f"reason: sensor error: {exc}"
                log_add(
                    f"[zone_ui] dist=None | cabinet=-- | status={decision.status.name} | "
                    f"safe={decision.is_safe} | reason=sensor error: {exc}"
                )
                page.update()
                time.sleep(0.2)
                continue

            if distance_cm is None:
                decision = tracker.update(None, authorized_cabinets=authorized_state["ids"])
                distance_display = "--"
                distance_text_value = "distance: --"
                csv_distance = None
            else:
                distance_m = distance_cm / 100.0
                decision = tracker.update(distance_m, authorized_cabinets=authorized_state["ids"])
                distance_display = f"{distance_cm:.1f} cm"
                distance_text_value = f"distance: {distance_display}"
                csv_distance = distance_cm

            distance_text.value = distance_text_value
            cab = decision.cabinet_index if decision.cabinet_index is not None else "--"
            cabinet_label.value = f"cabinet: {cab}"
            status_label.value = f"status: {decision.status.name}"
            reason_label.value = f"reason: {decision.reason}"

            if decision.is_safe:
                warning_text.value = "warning: SAFE"
                warning_text.color = colors.GREEN
            else:
                if decision.status.name.startswith("STABLE_UNAUTH") or decision.status.name.endswith("UNAUTH"):
                    warning_text.value = "warning: UNAUTHORIZED"
                else:
                    warning_text.value = "warning: DANGER"
                warning_text.color = colors.RED

            log_add(
                f"[zone_ui] dist={distance_display} | cabinet={cab} | status={decision.status.name} | "
                f"safe={decision.is_safe} | reason={decision.reason}"
            )

            if record_state["enabled"]:
                append_csv_row(decision, csv_distance)

            page.update()
            time.sleep(0.2)

    threading.Thread(target=update_loop, daemon=True).start()


def run_ui() -> None:
    ft.app(target=main)


if __name__ == "__main__":
    run_ui()
