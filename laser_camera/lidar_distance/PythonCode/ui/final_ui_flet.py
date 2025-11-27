#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flet 实时监控界面：登录 + 授权机位 + 摄像头状态 + 报警日志。"""
from __future__ import annotations

import sys 
import os
# 添加项目根目录到 sys.path 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    

import itertools
import threading
import time
from pathlib import Path
from typing import Optional

import flet as ft

from core.user_auth import (
    User,
    Role,
    authenticate,
    user_can_set_target_cabinet,
    user_can_view_logs,
    user_is_admin,
    get_user,
    hash_password,
)
import core.user_auth as auth
from core.app_config import CONFIG
from core.realtime_lidar import RealtimeLidarSource, LidarMeasurement
from core.vision_logic import VisionState, LinePosition, BodyOrientation, GestureCode
from core.vision_realtime_canmv import CanMVVisionSource
from demo.controller_vision_stub import VisionSafetyController
from core.safety_logic import format_alarm_for_log, alarm_level_to_color

ROOM_COUNT = 8
BOXES_PER_ROOM = 14
MAX_SELECTED_BOXES = 20
CARD_BG_COLOR = "#263238"
COLOR_GREY = "#9E9E9E"
COLOR_GREEN = "#4CAF50"
COLOR_RED = "#F44336"
COLOR_YELLOW = "#FDD835"
VIDEO_PANEL_BG_COLOR = "#1c1c1c"
PLACEHOLDER_BASE64 = "R0lGODlhAQABAPAAAAAAAAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="


def resolve_color(value: Optional[str]) -> Optional[str]:
    """将 alarm_level_to_color / 默认颜色名转换为十六进制，兼容老版本 Flet。"""

    if not value:
        return value
    lookup = {
        "green": COLOR_GREEN,
        "yellow": COLOR_YELLOW,
        "red": COLOR_RED,
        "orange": "#FF9800",
        "blue": "#2196F3",
    }
    return lookup.get(value.lower(), value)


class _DummyLidarSource:
    """提供恒定 None 的简易 LiDAR 数据源。"""

    def stream(self):
        return itertools.repeat(None)


class _StaticVisionSource:
    """用于初始化控制器的静态 VisionSource。"""

    def stream(self):
        while True:
            yield VisionState(False, LinePosition.UNKNOWN, BodyOrientation.UNKNOWN, GestureCode.NONE)


def main(page: ft.Page) -> None:
    page.title = "变电站安全监控（实时摄像头版）"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.scroll = ft.ScrollMode.AUTO

    current_user: Optional[User] = None
    vision_controller: Optional[VisionSafetyController] = None
    vision_source: Optional[CanMVVisionSource] = None
    vision_thread: Optional[threading.Thread] = None
    vision_running = False
    lidar_source: Optional[RealtimeLidarSource] = None
    lidar_thread: Optional[threading.Thread] = None
    lidar_running = False
    video_thread: Optional[threading.Thread] = None
    video_thread_running = False
    monitoring_running = False
    log_history: list[str] = []
    recording = False
    record_start_time = 0.0
    record_data: list[str] = []
    RECORD_MAX_SECONDS = 59 * 60
    MAX_SELECTED_BOXES = 20
    current_role_label: Optional[str] = None
    authorized_cabinet: Optional[int] = None
    current_cabinet_from_lidar: Optional[int] = None
    select_all_ports_mode = False

    ROLE_USER_MAP = {
        "管理员": "Ronan",
        "操作员": "admin",
        "游客": "viewer",
    }
    ROLE_TIPS = {
        "管理员": "拥有所有权限，可进行账户管理与导出",
        "操作员": "可更改机房与机箱，无法导出",
        "游客": "仅可查看状态",
    }
    ROLE_LABELS = {
        "管理员": Role.ADMIN,
        "操作员": Role.OPERATOR,
        "游客": Role.VIEWER,
    }

    def reset_demo_passwords() -> None:
        for username in ROLE_USER_MAP.values():
            user = get_user(username)
            if user:
                user.password_hash = hash_password("123")

    reset_demo_passwords()

    # 登录控件
    role_dropdown = ft.Dropdown(
        label="身份",
        width=200,
        options=[ft.dropdown.Option(name) for name in ROLE_USER_MAP.keys()],
    )
    password_field = ft.TextField(label="密码", password=True, can_reveal_password=True, width=200)
    login_status = ft.Text(value="", color="red")

    # 主界面控件
    user_info = ft.Text("尚未登录", selectable=True)
    selected_boxes: set[tuple[int, int]] = set()
    box_checkboxes: dict[tuple[int, int], ft.Checkbox] = {}
    selected_summary_text = ft.Text(f"已选机箱：0 / {MAX_SELECTED_BOXES}")

    def update_selected_summary() -> None:
        labels = [f"机房{r}-机箱{c:02d}" for r, c in sorted(selected_boxes)]
        selected_summary_text.value = (
            f"已选机箱：{len(selected_boxes)} / {MAX_SELECTED_BOXES} | {('；'.join(labels)) if labels else '无'}"
        )

    def handle_box_toggle(room: int, box: int):
        def _handler(e: ft.ControlEvent) -> None:
            key = (room, box)
            if e.control.value:
                if len(selected_boxes) >= MAX_SELECTED_BOXES:
                    e.control.value = False
                    append_log_line(f"最多只能选择 {MAX_SELECTED_BOXES} 台机箱", "orange")
                else:
                    selected_boxes.add(key)
            else:
                selected_boxes.discard(key)
            update_selected_summary()
            page.update()

        return _handler

    def build_box_columns() -> ft.Control:
        containers: list[ft.Control] = []
        per_row = 4
        for room in range(1, ROOM_COUNT + 1):
            tiles: list[ft.Control] = []
            for box in range(1, BOXES_PER_ROOM + 1):
                checkbox = ft.Checkbox(value=False, scale=0.9, on_change=handle_box_toggle(room, box))
                box_checkboxes[(room, box)] = checkbox
                tiles.append(
                    ft.Column(
                        [
                            checkbox,
                            ft.Text(f"{box:02d}", size=11, text_align=ft.TextAlign.CENTER),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        width=48,
                    )
                )
            rows: list[ft.Control] = []
            for start in range(0, BOXES_PER_ROOM, per_row):
                rows.append(
                    ft.Row(
                        tiles[start : start + per_row],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.START,
                    )
                )
            grid = ft.Column(rows, spacing=6, height=150, scroll=ft.ScrollMode.AUTO)
            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"机房 {room}", weight=ft.FontWeight.BOLD),
                        grid,
                    ],
                    spacing=8,
                ),
                padding=8,
                border=ft.border.all(1, "#cccccc"),
                border_radius=8,
                col={"xs": 12, "sm": 6, "md": 3, "lg": 3} if hasattr(ft, "ResponsiveRow") else None,
                width=None if hasattr(ft, "ResponsiveRow") else 220,
            )
            containers.append(card)

        if hasattr(ft, "ResponsiveRow"):
            return ft.ResponsiveRow(containers, spacing=12, run_spacing=12)
        return ft.Row(containers, spacing=12, wrap=True)

    box_selector = build_box_columns()
    update_selected_summary()

    apply_cabinet_button = ft.ElevatedButton("应用机位", disabled=True)

    start_button = ft.ElevatedButton("开始", disabled=True)
    stop_button = ft.ElevatedButton("停止", disabled=True)
    serial_port_options = [
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "/dev/ttyUSB0",
        "/dev/tty.usbserial-1110",
        "/dev/tty.usbserial-1130",
        "/dev/tty.usbserial-1120",
    ]
    default_port = CONFIG.serial.port
    if default_port not in serial_port_options:
        serial_port_options.append(default_port)
    logout_button = ft.TextButton(
        content=ft.Text(
            "返回登录",
            color="black",
            style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
        ),
        disabled=True,
    )
    more_button = ft.ElevatedButton("更多", visible=False)

    vision_person_text = ft.Text("人员：未知")
    vision_line_text = ft.Text("黄线：未知")
    vision_orient_text = ft.Text("朝向：未知")
    vision_gesture_text = ft.Text("手势：未知")
    vision_time_text = ft.Text("时间：--")
    vision_alarm_text = ft.Text("告警：--")
    video_status_text = ft.Text(
        "当前状态：未开始",
        color="white",
        size=18,
        text_align=ft.TextAlign.CENTER,
    )

    vision_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("摄像头状态", weight=ft.FontWeight.BOLD),
                vision_person_text,
                vision_line_text,
                vision_orient_text,
                vision_gesture_text,
                vision_time_text,
                vision_alarm_text,
            ],
            spacing=4,
        ),
        padding=10,
        border_radius=8,
        bgcolor=CARD_BG_COLOR,
    )

    lidar_distance_text = ft.Text("距离：-- m")
    lidar_cabinet_text = ft.Text("当前机位：--")
    lidar_authorized_text = ft.Text("授权机位：--")
    lidar_match_text = ft.Text("站位状态：未知", color=COLOR_GREY)

    lidar_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("LiDAR 状态", weight=ft.FontWeight.BOLD),
            lidar_distance_text,
            lidar_cabinet_text,
            lidar_authorized_text,
            lidar_match_text,
            ],
            spacing=4,
        ),
        padding=10,
        border_radius=8,
        bgcolor=CARD_BG_COLOR,
    )

    if hasattr(ft, "ResponsiveRow"):
        status_cards = ft.ResponsiveRow(
            [
                ft.Container(content=vision_card, expand=1, col={"xs": 12, "sm": 6, "md": 6, "lg": 6}),
                ft.Container(content=lidar_card, expand=1, col={"xs": 12, "sm": 6, "md": 6, "lg": 6}),
            ],
            spacing=12,
            run_spacing=12,
        )
    else:
        status_cards = ft.Row(
            [
                ft.Container(content=vision_card, expand=1),
                ft.Container(content=lidar_card, expand=1),
            ],
            spacing=12,
            expand=True,
            wrap=True,
        )

    def update_lidar_match_text() -> None:
        """根据授权/当前机位刷新站位状态标签。"""

        if authorized_cabinet is None or current_cabinet_from_lidar is None:
            lidar_match_text.value = "站位状态：未知"
            lidar_match_text.color = COLOR_GREY
        elif authorized_cabinet == current_cabinet_from_lidar:
            lidar_match_text.value = "站位状态：站位正确"
            lidar_match_text.color = COLOR_GREEN
        else:
            lidar_match_text.value = (
                f"站位状态：机位不匹配（当前={current_cabinet_from_lidar}, 授权={authorized_cabinet}）"
            )
            lidar_match_text.color = COLOR_RED

    camera_slot_dropdowns: list[ft.Dropdown] = []
    camera_slot_images: list[ft.Image] = []
    camera_slot_panels: list[ft.Container] = []
    camera_slot_statuses: list[ft.Text] = []

    def handle_camera_port_change(slot_idx: int):
        def _handler(e: ft.ControlEvent) -> None:
            value = (e.control.value or "").strip()
            if select_all_ports_mode:
                for dropdown in camera_slot_dropdowns:
                    dropdown.value = value
            page.update()

        return _handler

    def _make_video_panel() -> tuple[ft.Image, ft.Container]:
        img = ft.Image(
            src=f"data:image/gif;base64,{PLACEHOLDER_BASE64}",
            fit=ft.ImageFit.CONTAIN,
            expand=True,
        )
        panel = ft.Container(
            content=ft.Column(
                [img],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            bgcolor=VIDEO_PANEL_BG_COLOR,
            height=260,
            alignment=ft.alignment.center,
            border_radius=8,
            border=ft.border.all(1, "#424242"),
            expand=True,
        )
        return img, panel

    select_all_checkbox = ft.Checkbox(label="选择全部串口同步", value=False)

    def on_select_all_toggle(_: ft.ControlEvent) -> None:
        nonlocal select_all_ports_mode
        select_all_ports_mode = bool(select_all_checkbox.value)
        if select_all_ports_mode and camera_slot_dropdowns:
            shared_value = camera_slot_dropdowns[0].value
            for dropdown in camera_slot_dropdowns:
                dropdown.value = shared_value
        page.update()

    select_all_checkbox.on_change = on_select_all_toggle

    slot_count = 8
    camera_columns: list[ft.Control] = []
    for idx in range(slot_count):
        image, panel = _make_video_panel()
        default_value = serial_port_options[idx % len(serial_port_options)]
        dropdown = ft.Dropdown(
            label="串口",
            width=260,
            value=default_value,
            options=[ft.dropdown.Option(p) for p in serial_port_options],
            on_change=handle_camera_port_change(idx),
        )
        status = ft.Text("待命", text_align=ft.TextAlign.CENTER)
        card_content = ft.Column(
            [
                ft.Text(f"机房 {idx + 1}", weight=ft.FontWeight.BOLD),
                dropdown,
                panel,
                status,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
        if hasattr(ft, "ResponsiveRow"):
            camera_columns.append(
                ft.Container(
                    content=card_content,
                    col={"xs": 12, "sm": 6, "md": 6, "lg": 6},
                    padding=6,
                )
            )
        else:
            camera_columns.append(
                ft.Container(content=card_content, padding=6, expand=True, width=360)
            )

        camera_slot_dropdowns.append(dropdown)
        camera_slot_images.append(image)
        camera_slot_panels.append(panel)
        camera_slot_statuses.append(status)
    # Arrange grid row
    if hasattr(ft, "ResponsiveRow"):
        video_cameras_row = ft.ResponsiveRow(camera_columns, spacing=12, run_spacing=12)
    else:
        video_cameras_row = ft.Row(camera_columns, spacing=12, wrap=True)

    active_slot_index = 0

    def refresh_camera_slot_statuses() -> None:
        for idx, label in enumerate(camera_slot_statuses):
            if monitoring_running and idx == active_slot_index:
                label.value = "监控中"
            else:
                label.value = "待命"
        for idx, panel in enumerate(camera_slot_panels):
            if monitoring_running and idx == active_slot_index:
                panel.border = ft.border.all(2, COLOR_GREEN)
            else:
                panel.border = ft.border.all(1, "#424242")

    refresh_camera_slot_statuses()
    record_button = ft.ElevatedButton("开始录制", disabled=True)
    export_record_button = ft.ElevatedButton("导出录制", disabled=True)
    record_format_dropdown = ft.Dropdown(
        width=120,
        value="mp4",
        options=[
            ft.dropdown.Option("mp4", "MP4"),
            ft.dropdown.Option("avi", "AVI"),
            ft.dropdown.Option("mkv", "MKV"),
        ],
    )
    record_status_text = ft.Text("录制：未开始")

    log_view = ft.ListView(expand=True, spacing=3, height=260)
    log_format_dropdown = ft.Dropdown(
        width=120,
        value="pdf",
        options=[
            ft.dropdown.Option("pdf", "PDF"),
            ft.dropdown.Option("word", "Word"),
            ft.dropdown.Option("excel", "Excel"),
        ],
    )
    export_log_button = ft.ElevatedButton("导出日志", disabled=True)

    admin_menu_dialog = ft.AlertDialog(modal=True)

    def close_admin_menu(_: Optional[ft.ControlEvent] = None) -> None:
        admin_menu_dialog.open = False
        page.update()

    def show_add_user_form(_: Optional[ft.ControlEvent] = None) -> None:
        username_input = ft.TextField(label="用户名")
        display_input = ft.TextField(label="显示名")
        role_select = ft.Dropdown(
            label="角色",
            value="操作员",
            options=[ft.dropdown.Option(label) for label in ROLE_LABELS.keys()],
        )
        password_input = ft.TextField(label="密码", password=True, can_reveal_password=True, value="123")
        status_text = ft.Text("", color="red")

        def submit(_: ft.ControlEvent) -> None:
            username = username_input.value.strip()
            display_name = display_input.value.strip() or username
            password = password_input.value or "123"
            role_label = role_select.value or "游客"
            if not username:
                status_text.value = "用户名不能为空"
                page.update()
                return
            if username in auth._USERS:
                status_text.value = "用户已存在"
                page.update()
                return
            role = ROLE_LABELS.get(role_label, Role.VIEWER)
            auth._USERS[username] = User(
                username=username,
                display_name=display_name,
                password_hash=hash_password(password),
                roles=[role],
            )
            append_log_line(f"管理员新增用户：{username}（{role_label}）", "blue")
            close_admin_menu()

        admin_menu_dialog.title = ft.Text("添加用户")
        admin_menu_dialog.content = ft.Column(
            [username_input, display_input, role_select, password_input, status_text],
            spacing=8,
            width=320,
        )
        admin_menu_dialog.actions = [
            ft.TextButton("返回", on_click=lambda _: open_admin_menu()),
            ft.ElevatedButton("确认", on_click=submit),
        ]
        page.update()

    def show_remove_user_form(_: Optional[ft.ControlEvent] = None) -> None:
        options = sorted(auth._USERS.keys())
        user_select = ft.Dropdown(label="选择用户", options=[ft.dropdown.Option(u) for u in options])
        status_text = ft.Text("", color="red")

        def submit(_: ft.ControlEvent) -> None:
            username = user_select.value
            if not username:
                status_text.value = "请选择用户"
                page.update()
                return
            if username == ROLE_USER_MAP["管理员"]:
                status_text.value = "不可移除内置管理员"
                page.update()
                return
            if username == (current_user.username if current_user else None):
                status_text.value = "不能移除当前登录用户"
                page.update()
                return
            if username in auth._USERS:
                del auth._USERS[username]
                append_log_line(f"管理员移除用户：{username}", "blue")
                close_admin_menu()
            else:
                status_text.value = "用户不存在"
                page.update()

        admin_menu_dialog.title = ft.Text("移除用户")
        admin_menu_dialog.content = ft.Column([user_select, status_text], spacing=8, width=280)
        admin_menu_dialog.actions = [
            ft.TextButton("返回", on_click=lambda _: open_admin_menu()),
            ft.ElevatedButton("确认", on_click=submit),
        ]
        page.update()

    def show_change_password_form(_: Optional[ft.ControlEvent] = None) -> None:
        options = sorted(auth._USERS.keys())
        user_select = ft.Dropdown(label="选择用户", options=[ft.dropdown.Option(u) for u in options])
        new_password_input = ft.TextField(label="新密码", password=True, can_reveal_password=True)
        status_text = ft.Text("", color="red")

        def submit(_: ft.ControlEvent) -> None:
            username = user_select.value
            new_password = new_password_input.value
            if not username or not new_password:
                status_text.value = "请选择用户并输入密码"
                page.update()
                return
            user = auth._USERS.get(username)
            if not user:
                status_text.value = "用户不存在"
                page.update()
                return
            user.password_hash = hash_password(new_password)
            append_log_line(f"管理员修改了用户 {username} 的密码", "blue")
            close_admin_menu()

        admin_menu_dialog.title = ft.Text("修改密码")
        admin_menu_dialog.content = ft.Column([user_select, new_password_input, status_text], spacing=8, width=320)
        admin_menu_dialog.actions = [
            ft.TextButton("返回", on_click=lambda _: open_admin_menu()),
            ft.ElevatedButton("确认", on_click=submit),
        ]
        page.update()

    def show_change_role_form(_: Optional[ft.ControlEvent] = None) -> None:
        options = sorted(auth._USERS.keys())
        user_select = ft.Dropdown(label="选择用户", options=[ft.dropdown.Option(u) for u in options])
        role_select = ft.Dropdown(
            label="新角色",
            options=[ft.dropdown.Option(label) for label in ROLE_LABELS.keys()],
        )
        status_text = ft.Text("", color="red")

        def submit(_: ft.ControlEvent) -> None:
            username = user_select.value
            role_label = role_select.value
            if not username or not role_label:
                status_text.value = "请选择用户与角色"
                page.update()
                return
            user = auth._USERS.get(username)
            if not user:
                status_text.value = "用户不存在"
                page.update()
                return
            new_role = ROLE_LABELS.get(role_label, Role.VIEWER)
            user.roles = [new_role]
            append_log_line(f"管理员将 {username} 权限调整为 {role_label}", "blue")
            if current_user and username == current_user.username:
                apply_role_permissions()
                refresh_user_info_display()
            close_admin_menu()

        admin_menu_dialog.title = ft.Text("权限升级 / 调整")
        admin_menu_dialog.content = ft.Column([user_select, role_select, status_text], spacing=8, width=320)
        admin_menu_dialog.actions = [
            ft.TextButton("返回", on_click=lambda _: open_admin_menu()),
            ft.ElevatedButton("确认", on_click=submit),
        ]
        page.update()

    def render_admin_menu() -> None:
        admin_menu_dialog.title = ft.Text("管理员更多操作")
        admin_menu_dialog.content = ft.Column(
            [
                ft.Text("请选择需要执行的操作："),
                ft.Row(
                    [
                        ft.ElevatedButton("添加用户", on_click=show_add_user_form),
                        ft.ElevatedButton("移除用户", on_click=show_remove_user_form),
                        ft.ElevatedButton("修改密码", on_click=show_change_password_form),
                        ft.ElevatedButton("权限升级", on_click=show_change_role_form),
                    ],
                    spacing=10,
                    wrap=True,
                ),
            ],
            spacing=10,
        )
        admin_menu_dialog.actions = [ft.TextButton("关闭", on_click=close_admin_menu)]

    def open_admin_menu(_: Optional[ft.ControlEvent] = None) -> None:
        render_admin_menu()
        admin_menu_dialog.open = True
        page.dialog = admin_menu_dialog
        page.update()

    def append_log_line(text: str, color: str = "black") -> None:
        log_history.append(text)
        log_view.controls.append(ft.Text(value=text, color=resolve_color(color), size=12))
        if len(log_history) > 500:
            log_history.pop(0)
        if len(log_view.controls) > 500:
            log_view.controls.pop(0)

    def refresh_user_info_display() -> None:
        if current_user is None or current_role_label is None:
            return
        user_info.value = "\n".join(
            [
                f"用户名：{current_user.username}",
                f"显示名：{current_user.display_name}",
                f"角色：{current_role_label}（{ROLE_TIPS.get(current_role_label, '')}）",
                f"管理员：{user_is_admin(current_user)}",
                f"可设置机位：{user_can_set_target_cabinet(current_user)}",
                f"可查看日志：{user_can_view_logs(current_user)}",
            ]
        )

    def update_vision_state_display(state: VisionState, alarm, action_status) -> None:
        nonlocal active_slot_index
        person_label = "有人" if state.person_present else "无人"
        vision_person_text.value = f"人员：{person_label}"
        vision_line_text.value = f"黄线：{state.line_position.name}"
        vision_orient_text.value = f"朝向：{state.orientation.name}"
        vision_gesture_text.value = f"手势：{state.gesture.name}"
        if state.timestamp:
            vision_time_text.value = f"时间：{state.timestamp.isoformat()}"
        else:
            vision_time_text.value = f"时间：{time.strftime('%H:%M:%S')}"
        vision_alarm_text.value = f"告警：{alarm.level.name} | 动作：{action_status.name}"
        if authorized_cabinet is not None and current_cabinet_from_lidar is not None:
            if authorized_cabinet == current_cabinet_from_lidar:
                cabinet_info = "机位：正确"
            else:
                cabinet_info = f"机位：错误(当前={current_cabinet_from_lidar}, 授权={authorized_cabinet})"
        else:
            cabinet_info = "机位：未知"

        video_status_text.value = (
            f"{person_label} | 线={state.line_position.name} | "
            f"朝向={state.orientation.name} | 手势={state.gesture.name} | "
            f"告警={alarm.level.name} | {cabinet_info}"
        )

        color_name = alarm_level_to_color(alarm.level)
        resolved_color = resolve_color(color_name)
        vision_card.bgcolor = resolved_color
        for idx, panel in enumerate(camera_slot_panels):
            if monitoring_running and idx == active_slot_index:
                panel.bgcolor = resolved_color
            else:
                panel.bgcolor = VIDEO_PANEL_BG_COLOR

    def apply_role_permissions() -> None:
        is_admin = current_role_label == "管理员"
        is_operator = current_role_label == "操作员"
        can_config = is_admin or is_operator
        can_control = is_admin

        apply_cabinet_button.disabled = not can_config
        for checkbox in box_checkboxes.values():
            checkbox.disabled = not can_config
        start_button.disabled = (not can_control) or monitoring_running
        stop_button.disabled = (not can_control) or (not monitoring_running)
        logout_button.disabled = current_role_label is None
        more_button.visible = is_admin
        more_button.disabled = not is_admin
        record_button.disabled = not can_control
        export_record_button.disabled = True
        export_log_button.disabled = not can_control
        select_all_checkbox.disabled = not is_admin

    def clear_box_selection() -> None:
        selected_boxes.clear()
        for checkbox in box_checkboxes.values():
            checkbox.value = False
        update_selected_summary()

    # 登录逻辑
    def on_login_clicked(_: ft.ControlEvent) -> None:
        nonlocal current_user, vision_controller, current_role_label, authorized_cabinet, vision_source, lidar_source
        role_choice = role_dropdown.value
        if not role_choice:
            login_status.value = "请选择身份"
            page.update()
            return
        username = ROLE_USER_MAP.get(role_choice)
        password = password_field.value
        user = authenticate(username, password)
        if user is None:
            login_status.value = "用户名或密码错误"
            page.update()
            return

        current_user = user
        current_role_label = role_choice
        authorized_cabinet = None
        vision_source = None
        lidar_source = None
        login_status.value = ""
        refresh_user_info_display()

        dummy_lidar = _DummyLidarSource()
        static_vision = _StaticVisionSource()
        vision_controller = VisionSafetyController(
            lidar_source=dummy_lidar,
            vision_source=static_vision,
            target_cabinet=None,
        )
        vision_controller._lidar_iter = dummy_lidar.stream()
        vision_controller._vision_iter = static_vision.stream()
        lidar_authorized_text.value = "授权机位：--"
        lidar_distance_text.value = "距离：-- m"
        lidar_cabinet_text.value = "当前机位：--"
        update_lidar_match_text()

        apply_role_permissions()
        login_container.visible = False
        main_panel.visible = True
        page.update()

    def on_logout(_: ft.ControlEvent) -> None:
        nonlocal current_user, monitoring_running, recording, current_role_label, vision_running, lidar_running, vision_controller, authorized_cabinet
        on_stop_monitor(None)
        monitoring_running = False
        vision_running = False
        lidar_running = False
        recording = False
        current_user = None
        current_role_label = None
        authorized_cabinet = None
        vision_controller = None
        log_view.controls.clear()
        log_history.clear()
        record_data.clear()
        record_status_text.value = "录制：未开始"
        record_button.text = "开始录制"
        vision_person_text.value = "人员：未知"
        vision_line_text.value = "黄线：未知"
        vision_orient_text.value = "朝向：未知"
        vision_gesture_text.value = "手势：未知"
        vision_time_text.value = "时间：--"
        vision_alarm_text.value = "告警：--"
        vision_card.bgcolor = CARD_BG_COLOR
        lidar_distance_text.value = "距离：-- m"
        lidar_cabinet_text.value = "当前机位：--"
        lidar_authorized_text.value = "授权机位：--"
        update_lidar_match_text()
        clear_box_selection()
        apply_role_permissions()
        login_container.visible = True
        main_panel.visible = False
        append_log_line("已返回登录界面", "blue")
        page.update()

    # 授权机位
    def on_apply_cabinet(_: ft.ControlEvent) -> None:
        nonlocal authorized_cabinet
        if current_user is None:
            return
        if not user_can_set_target_cabinet(current_user):
            append_log_line("当前账号无权设置机位", "red")
            page.update()
            return
        if not selected_boxes:
            append_log_line("请至少选择一个机箱", "orange")
            page.update()
            return
        first_room, first_box = sorted(selected_boxes)[0]
        target_id = (first_room - 1) * BOXES_PER_ROOM + first_box
        authorized_cabinet = target_id
        lidar_authorized_text.value = f"授权机位：{authorized_cabinet}"
        update_lidar_match_text()
        if vision_controller is not None:
            vision_controller.set_target_cabinet(target_id)
        labels = [f"机房{r}-机箱{c:02d}" for r, c in sorted(selected_boxes)]
        append_log_line(f"授权机位已切换到 {', '.join(labels)}", "blue")
        page.update()

    # 监控线程（摄像头）
    def vision_loop() -> None:
        nonlocal vision_running, monitoring_running, recording, record_data, lidar_running, active_slot_index
        if vision_controller is None:
            append_log_line("视觉控制器未初始化", "red")
            monitoring_running = False
            apply_role_permissions()
            page.update()
            return
        vision_running = True
        try:
            while vision_running and not getattr(page, "session_closed", False):
                try:
                    alarm, vision_state, action_status = vision_controller.step()
                except Exception as exc:
                    append_log_line(f"视觉线程异常：{exc}", "red")
                    break
                # Step 1: initialize frame_b64 = None
                frame_b64 = None
                # Step 2: try to get frame from vision_state if possible
                if hasattr(vision_state, "frame_base64") and vision_state.frame_base64:
                    frame_b64 = vision_state.frame_base64
                update_vision_state_display(vision_state, alarm, action_status)
                alarm_line = format_alarm_for_log(alarm)
                color = alarm_level_to_color(alarm.level)
                log_line = f"{alarm_line} | action={action_status.name}"
                append_log_line(log_line, color)
                if recording:
                    elapsed = time.time() - record_start_time
                    if elapsed >= RECORD_MAX_SECONDS:
                        recording = False
                        record_button.text = "开始录制"
                        record_status_text.value = "录制：已自动停止（59 分钟）"
                        export_record_button.disabled = not record_data
                    else:
                        record_data.append(log_line)
                # 优先使用 VisionState 携带的画面，如果没有则向视觉源拉取最新帧
                if frame_b64 is None and vision_source is not None and hasattr(vision_source, "get_latest_frame_base64"):
                    try:
                        frame_b64 = vision_source.get_latest_frame_base64()
                    except Exception as exc:
                        frame_b64 = None
                        append_log_line(f"获取视频帧失败：{exc}", "orange")

                page.update()
        finally:
            vision_running = False
            monitoring_running = False
            if lidar_running:
                lidar_running = False
            refresh_camera_slot_statuses()
            apply_role_permissions()
            page.update()

    def video_stream_loop() -> None:
        nonlocal video_thread_running, vision_source
        video_thread_running = True
        try:
            while video_thread_running and not getattr(page, "session_closed", False):
                if vision_source is None:
                    time.sleep(0.1)
                    continue
                frame_b64: Optional[str] = None
                try:
                    frame_b64 = vision_source.get_latest_frame_base64()
                except Exception as exc:
                    append_log_line(f"获取视频帧失败：{exc}", "orange")
                    time.sleep(0.2)
                    continue
                if not frame_b64:
                    time.sleep(0.05)
                    continue
                if isinstance(frame_b64, str) and frame_b64.startswith("FRAME_BASE64 "):
                    frame_b64 = frame_b64.split(" ", 1)[1].strip()
                target_image = camera_slot_images[0] if camera_slot_images else None
                if target_image is not None:
                    target_image.src_base64 = frame_b64
                    target_image.src = None
                    page.update()
                time.sleep(0.05)
        finally:
            video_thread_running = False

    # LiDAR 状态线程
    def lidar_loop() -> None:
        nonlocal lidar_running, current_cabinet_from_lidar, lidar_source
        if lidar_source is None:
            append_log_line("LiDAR 数据源未初始化", "orange")
            return
        lidar_running = True
        try:
            for measurement in lidar_source.stream_measurements(interval_sec=0.2):
                measurement_obj: LidarMeasurement = measurement
                if not lidar_running or getattr(page, "session_closed", False):
                    break
                if measurement_obj.raw_valid:
                    lidar_distance_text.value = f"距离：{measurement_obj.distance_m:.3f} m"
                    if measurement_obj.cabinet_index is not None:
                        current_cabinet_from_lidar = measurement_obj.cabinet_index
                        lidar_cabinet_text.value = f"当前机位：{measurement_obj.cabinet_index}"
                    else:
                        current_cabinet_from_lidar = None
                        lidar_cabinet_text.value = "当前机位：None"
                else:
                    current_cabinet_from_lidar = None
                    lidar_distance_text.value = "距离：无有效测量"
                    lidar_cabinet_text.value = "当前机位：None"
                update_lidar_match_text()
                page.update()
        except Exception as exc:
            append_log_line(f"LiDAR 线程异常：{exc}", "red")
        finally:
            lidar_running = False
            try:
                if lidar_source is not None:
                    lidar_source.close()
            except Exception:
                pass

    def on_start_monitor(_: ft.ControlEvent) -> None:
        nonlocal monitoring_running, vision_thread, lidar_thread, vision_source, lidar_source, vision_controller, active_slot_index, video_thread, video_thread_running
        if current_user is None:
            return
        if not user_can_view_logs(current_user):
            append_log_line("当前账号无权查看日志", "red")
            page.update()
            return
        if monitoring_running:
            append_log_line("监控已在运行中", "orange")
            return

        selected_port = default_port
        if camera_slot_dropdowns:
            selected_port = (camera_slot_dropdowns[active_slot_index].value or default_port).strip()
        else:
            selected_port = default_port

        try:
            vision_source = CanMVVisionSource(port=selected_port, auto_start=True)
        except Exception as exc:
            vision_source = None
            append_log_line(f"摄像头源初始化失败：{exc}", "red")
            return

        try:
            lidar_source = RealtimeLidarSource(port=selected_port)
        except Exception as exc:
            lidar_source = None
            append_log_line(f"LiDAR 初始化失败：{exc}", "red")
            return

        try:
            vision_controller = VisionSafetyController(
                lidar_source=lidar_source,
                vision_source=vision_source,
                target_cabinet=authorized_cabinet,
            )
        except Exception as exc:
            append_log_line(f"视觉控制器启动失败：{exc}", "red")
            if lidar_source is not None:
                try:
                    lidar_source.close()
                except Exception:
                    pass
                lidar_source = None
            return

        if authorized_cabinet is not None:
            vision_controller.set_target_cabinet(authorized_cabinet)

        monitoring_running = True
        apply_role_permissions()
        stop_button.disabled = False
        start_button.disabled = True
        refresh_camera_slot_statuses()

        vision_thread = threading.Thread(target=vision_loop, daemon=True)
        vision_thread.start()
        if lidar_source is not None:
            lidar_thread = threading.Thread(target=lidar_loop, daemon=True)
            lidar_thread.start()
        if not video_thread_running:
            video_thread = threading.Thread(target=video_stream_loop, daemon=True)
            video_thread.start()
        page.update()

    def on_stop_monitor(_: ft.ControlEvent) -> None:
        nonlocal monitoring_running, vision_running, lidar_running, vision_thread, lidar_thread, lidar_source, vision_source, recording, video_thread, video_thread_running
        monitoring_running = False
        vision_running = False
        lidar_running = False
        video_thread_running = False
        refresh_camera_slot_statuses()
        if recording:
            recording = False
            record_button.text = "开始录制"
            record_status_text.value = "录制：已停止"
            export_record_button.disabled = not record_data

        if vision_thread and vision_thread.is_alive():
            vision_thread.join(timeout=0.2)
        vision_thread = None
        if lidar_thread and lidar_thread.is_alive():
            lidar_thread.join(timeout=0.2)
        lidar_thread = None
        if video_thread and video_thread.is_alive():
            video_thread.join(timeout=0.2)
        video_thread = None

        if lidar_source is not None:
            try:
                lidar_source.close()
            except Exception:
                pass
            lidar_source = None
        vision_source = None
        if camera_slot_images:
            placeholder = f"data:image/gif;base64,{PLACEHOLDER_BASE64}"
            camera_slot_images[0].src = placeholder
            camera_slot_images[0].src_base64 = None
        apply_role_permissions()
        page.update()

    def on_export_logs(_: ft.ControlEvent) -> None:
        if not log_history:
            append_log_line("暂无日志可导出", "orange")
            page.update()
            return
        fmt = log_format_dropdown.value or "pdf"
        ext_map = {"pdf": "pdf", "word": "docx", "excel": "xlsx"}
        filename = f"log_export_{int(time.time())}.{ext_map.get(fmt, 'txt')}"
        Path(filename).write_text("\n".join(log_history), encoding="utf-8")
        append_log_line(f"日志已导出：{filename}", "blue")
        page.update()

    def on_toggle_record(_: ft.ControlEvent) -> None:
        nonlocal recording, record_start_time, record_data
        if vision_controller is None or not monitoring_running:
            append_log_line("需先开始监控才可录制", "orange")
            page.update()
            return
        recording = not recording
        if recording:
            record_start_time = time.time()
            record_data = []
            record_button.text = "停止录制"
            record_status_text.value = "录制：进行中"
            export_record_button.disabled = True
        else:
            record_button.text = "开始录制"
            record_status_text.value = "录制：已停止"
            export_record_button.disabled = not record_data
        page.update()

    def on_export_record(_: ft.ControlEvent) -> None:
        if not record_data:
            append_log_line("没有可导出的录制内容", "orange")
            page.update()
            return
        fmt = record_format_dropdown.value or "mp4"
        filename = f"record_{int(time.time())}.{fmt}"
        Path(filename).write_text("\n".join(record_data), encoding="utf-8")
        append_log_line(f"录制已导出：{filename}", "blue")
        export_record_button.disabled = True
        page.update()

    apply_cabinet_button.on_click = on_apply_cabinet
    start_button.on_click = on_start_monitor
    stop_button.on_click = on_stop_monitor
    logout_button.on_click = on_logout
    more_button.on_click = open_admin_menu
    record_button.on_click = on_toggle_record
    export_record_button.on_click = on_export_record
    export_log_button.on_click = on_export_logs

    login_button = ft.ElevatedButton("登录", on_click=on_login_clicked)
    login_panel = ft.Column(
        [
            ft.Text("请选择身份并输入密码（示例密码均为 123）", style=ft.TextThemeStyle.TITLE_MEDIUM),
            role_dropdown,
            password_field,
            ft.Row([login_button, login_status], alignment=ft.MainAxisAlignment.CENTER),
        ],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    login_card = ft.Container(
        content=login_panel,
        width=360,
        padding=20,
        bgcolor="white",
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=15, spread_radius=1, color="#22000000"),
    )
    login_container = ft.Container(
        content=login_card,
        alignment=ft.alignment.center,
        expand=True,
        bgcolor="#f5f5f5",
    )

    log_header = ft.Row(
        [
            ft.Text("报警日志", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Row([log_format_dropdown, export_log_button], spacing=8),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    video_controls = ft.Row(
        [
            record_button,
            export_record_button,
            record_format_dropdown,
            record_status_text,
        ],
        spacing=8,
        wrap=True,
    )

    control_column = ft.Column(
        [
            ft.Text("机房 1-4 / 每房 10 台机箱，可多选（最多 20 台）", style=ft.TextThemeStyle.TITLE_MEDIUM),
            selected_summary_text,
            box_selector,
            ft.Row([apply_cabinet_button], alignment=ft.MainAxisAlignment.START),
            ft.Row([start_button, stop_button], spacing=10),
            log_header,
            log_view,
        ],
        spacing=10,
        expand=1,
    )

    video_header_row = ft.Row(
        [ft.Text("视频流", style=ft.TextThemeStyle.TITLE_MEDIUM), select_all_checkbox],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    monitor_column = ft.Column(
        [
            ft.Text("当前用户信息", style=ft.TextThemeStyle.TITLE_MEDIUM),
            user_info,
            ft.Row([more_button, logout_button], spacing=8, alignment=ft.MainAxisAlignment.START),
            status_cards,
            video_header_row,
            video_cameras_row,
            video_status_text,
            video_controls,
        ],
        spacing=10,
        expand=1,
    )

    if hasattr(ft, "ResponsiveRow"):
        layout_row = ft.ResponsiveRow(
            [
                ft.Container(
                    content=control_column,
                    col={"xs": 12, "md": 6},
                    bgcolor="#f7f7f7",
                    padding=10,
                    border_radius=8,
                ),
                ft.Container(
                    content=monitor_column,
                    col={"xs": 12, "md": 6},
                    bgcolor="#f7f7f7",
                    padding=10,
                    border_radius=8,
                ),
            ],
            run_spacing=16,
            spacing=16,
        )
    else:
        layout_row = ft.Row(
            [
                ft.Container(content=control_column, width=360, bgcolor="#f7f7f7", padding=10, border_radius=8),
                ft.Container(content=monitor_column, width=360, bgcolor="#f7f7f7", padding=10, border_radius=8),
            ],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.START,
            wrap=True,
        )

    main_panel = ft.Column(
        [layout_row],
        spacing=12,
        visible=False,
        expand=True,
    )

    apply_role_permissions()
    layout_wrapper = ft.Column(
        [login_container, main_panel],
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    page.add(layout_wrapper)
    page.update()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)