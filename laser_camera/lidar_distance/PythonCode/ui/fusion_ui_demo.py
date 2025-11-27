from __future__ import annotations

import csv
import threading
import time
from datetime import datetime
from pathlib import Path

import sys
import importlib.util

# Ensure we can import sibling `core` package when running this file directly
CURRENT_FILE = Path(__file__).resolve()
PYTHONCODE_ROOT = CURRENT_FILE.parent.parent  # .../lidar_distance/PythonCode
if str(PYTHONCODE_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHONCODE_ROOT))

import flet as ft

try:
    from flet import colors
except ImportError:
    class _FallbackColors:
        GREY_200 = "#eeeeee"
        RED = "#ff0000"
        GREEN = "#00ff00"
    colors = _FallbackColors()

# Python找到 pic_compare/PythonCode/core（为 vision_bridge 提供环境）
LASER_CAMERA_ROOT = CURRENT_FILE.parents[3]       # .../laser_camera
PIC_PYTHONCODE = LASER_CAMERA_ROOT / "pic_compare" / "PythonCode"
if str(PIC_PYTHONCODE) not in sys.path:
    sys.path.insert(0, str(PIC_PYTHONCODE))

VISION_BRIDGE_PATH = PIC_PYTHONCODE / "core" / "vision_bridge.py"
spec = importlib.util.spec_from_file_location("pic_vision_bridge", VISION_BRIDGE_PATH)
pic_vision_bridge = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
if spec and spec.loader:
    sys.modules[spec.name] = pic_vision_bridge  # type: ignore[index]
    spec.loader.exec_module(pic_vision_bridge)  # type: ignore[arg-type]
    VisionBridge = pic_vision_bridge.VisionBridge  # type: ignore[attr-defined]
    VisionSnapshot = pic_vision_bridge.VisionSnapshot  # type: ignore[attr-defined]
else:
    raise ImportError(f"Cannot load vision_bridge from {VISION_BRIDGE_PATH}")

# Ensure lidar_distance core has priority for LiDAR imports
LIDAR_NEW_LIDAR_PATH = PYTHONCODE_ROOT / "core" / "new_lidar.py"
LIDAR_ZONE_LOGIC_PATH = PYTHONCODE_ROOT / "core" / "lidar_zone_logic.py"

lidar_new_spec = importlib.util.spec_from_file_location("lidar_new_lidar", LIDAR_NEW_LIDAR_PATH)
lidar_new_mod = importlib.util.module_from_spec(lidar_new_spec)  # type: ignore[arg-type]
if lidar_new_spec and lidar_new_spec.loader:
    sys.modules[lidar_new_spec.name] = lidar_new_mod  # type: ignore[index]
    lidar_new_spec.loader.exec_module(lidar_new_mod)  # type: ignore[arg-type]
    get_lidar_distance_cm = lidar_new_mod.get_lidar_distance_cm  # type: ignore[attr-defined]
    NewLidarError = lidar_new_mod.NewLidarError  # type: ignore[attr-defined]
else:
    raise ImportError(f"Cannot load new_lidar from {LIDAR_NEW_LIDAR_PATH}")

lidar_zone_spec = importlib.util.spec_from_file_location("lidar_zone_logic_mod", LIDAR_ZONE_LOGIC_PATH)
lidar_zone_mod = importlib.util.module_from_spec(lidar_zone_spec)  # type: ignore[arg-type]
if lidar_zone_spec and lidar_zone_spec.loader:
    sys.modules[lidar_zone_spec.name] = lidar_zone_mod  # type: ignore[index]
    lidar_zone_spec.loader.exec_module(lidar_zone_mod)  # type: ignore[arg-type]
    CabinetZone = lidar_zone_mod.CabinetZone  # type: ignore[attr-defined]
    LidarZoneTracker = lidar_zone_mod.LidarZoneTracker  # type: ignore[attr-defined]
    LidarStatus = lidar_zone_mod.LidarStatus  # type: ignore[attr-defined]
    LidarDecision = lidar_zone_mod.LidarDecision  # type: ignore[attr-defined]
else:
    raise ImportError(f"Cannot load lidar_zone_logic from {LIDAR_ZONE_LOGIC_PATH}")

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
    image_view = ft.Image(width=640, height=360, fit=ft.ImageFit.CONTAIN, src=placeholder_src)
    placeholder_text = ft.Text(
        "No camera frame (frame_base64 is None)",
        size=14,
        text_align=ft.TextAlign.CENTER,
        weight=ft.FontWeight.BOLD,
    )
    image_container = ft.Container(
        width=640,
        height=360,
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

    record_state = {"enabled": False}
    tracker, authorized_default = build_tracker()
    authorized_state = {"ids": set(authorized_default)}

    # 共享视觉状态（由摄像线程更新）
    vision_state = {
        "snapshot": None,       # type: VisionSnapshot | None
        "frame_b64": None,      # type: str | None
        "has_frame": False,
    }

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

    info_column = ft.Column(
        [
            title_text,
            distance_text,
            warning_text,
            checkbox_row,
            cabinet_label,
            status_label,
            reason_label,
            record_switch,
            ft.Text("Event log:"),
            log_view,
        ],
        expand=1,
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )

    image_column = ft.Column(
        [image_container],
        expand=2,
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    page.add(
        ft.Row(
            [
                image_column,
                ft.VerticalDivider(width=1),
                info_column,
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )

    csv_path = Path(__file__).with_name("fusion_log.csv")

    # --- Vision thread: continuously grab frames from VisionBridge ---

    vision_bridge = VisionBridge()

    def vision_loop() -> None:
        while True:
            snap = vision_bridge.read_once()
            vision_state["snapshot"] = snap

            if snap is not None and snap.frame is not None:
                try:
                    import cv2
                    import base64

                    frame = snap.frame
                    h, w = frame.shape[:2]
                    scale = 240.0 / max(w, h)
                    if scale < 1.0:
                        frame = cv2.resize(
                            frame,
                            (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    ok, buf = cv2.imencode(".jpg", frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ok:
                        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                        vision_state["frame_b64"] = b64
                        vision_state["has_frame"] = True
                    else:
                        vision_state["frame_b64"] = None
                        vision_state["has_frame"] = False
                except Exception as ex:  # noqa: BLE001
                    vision_state["frame_b64"] = None
                    vision_state["has_frame"] = False
                    log_add(f"[vision_ui] encode error: {ex}")
            else:
                vision_state["frame_b64"] = None
                vision_state["has_frame"] = False

            time.sleep(0.08)  # 控制帧率，避免卡顿 / CPU 过高

    threading.Thread(target=vision_loop, daemon=True).start()
    
    
    # --- Main update loop ---
    
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
            # --- 从 vision_state 读取最新图像（已在 vision 线程编码完毕） ---

            frame_b64 = vision_state.get("frame_b64")
            has_frame = vision_state.get("has_frame")

            if frame_b64:
                image_view.src_base64 = frame_b64
                placeholder_text.value = ""
            else:
                placeholder_text.value = "No camera frame (frame_base64 is None)"

            page.update()
            time.sleep(0.1)

    threading.Thread(target=update_loop, daemon=True).start()

def run_ui() -> None:
    ft.app(target=main)


if __name__ == "__main__":
    run_ui()
