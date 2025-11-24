#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 CanMV 摄像头串口读取视觉状态，并转换为 VisionState（带调试打印版）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
import time
from typing import Iterator, Optional

import serial  # 需要 pyserial

if __package__:
    from .vision_logic import (
        VisionState,
        LinePosition,
        BodyOrientation,
        GestureCode,
    )
else:
    # 允许作为独立脚本运行：python core/vision_realtime_canmv.py
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.vision_logic import (  # type: ignore
        VisionState,
        LinePosition,
        BodyOrientation,
        GestureCode,
    )

# ======== 串口默认配置 ========

DEFAULT_PORT = "/dev/tty.usbserial-1110"
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 1.0  # 秒


def parse_vision_line(line: str) -> Optional[VisionState]:
    """解析一行 'VISION ...' 文本，成功则返回 VisionState，失败返回 None。"""
    line = line.strip()
    if not line:
        return None

    parts = line.split()
    if len(parts) != 5 or parts[0] != "VISION":
        # 调试时可以观察到收到的原始行
        print(">>> [parse] 非VISION行:", repr(line))
        return None

    _, person_str, line_str, orient_str, gesture_str = parts

    try:
        person_present = (person_str == "1")
        line_position = LinePosition[line_str]
        orientation = BodyOrientation[orient_str]
        gesture = GestureCode[gesture_str]
    except KeyError as e:
        print(">>> [parse] 枚举解析失败:", e, "原始行:", repr(line))
        return None

    return VisionState(
        person_present=person_present,
        line_position=line_position,
        orientation=orientation,
        gesture=gesture,
        timestamp=datetime.now(),
    )



@dataclass
class CanMVVisionSource:
    """
    从 CanMV 串口持续读取 VisionState 的数据源。

    VisionSafetyController 之前依赖的 stream() 仍旧可用，
    新增 stream_states() 与 get_latest_frame_base64()。
    """

    port: str = DEFAULT_PORT
    baudrate: int = DEFAULT_BAUDRATE
    timeout: float = DEFAULT_TIMEOUT
    auto_start: bool = True
    _latest_state: VisionState = field(
        default_factory=lambda: VisionState(
            person_present=False,
            line_position=LinePosition.UNKNOWN,
            orientation=BodyOrientation.UNKNOWN,
            gesture=GestureCode.NONE,
            timestamp=datetime.now(),
        )
    )

    def __post_init__(self) -> None:
        # 最近一帧的 Base64 图片缓存
        self._latest_frame_base64: Optional[str] = None

        # 收集多行 Base64 的 buffer
        self._frame_collecting: bool = False
        self._frame_buffer: list[str] = []

        self._serial: Optional[serial.Serial] = None
        self._states_queue: Queue[VisionState] = Queue()
        self._stop_event = Event()
        self._reader_thread: Optional[Thread] = None
        self._open_serial()
        if self.auto_start:
            self._start_reader_thread()

    def _open_serial(self) -> None:
        """尝试打开串口，如果失败则记录日志但不中断主线程。"""

        print(f">>> [CanMVVisionSource] 准备打开串口: {self.port}, {self.baudrate}bps")
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - 依赖硬件
            self._serial = None
            print(">>> [CanMVVisionSource] 打开串口失败:", repr(exc))
        else:
            print(">>> [CanMVVisionSource] 串口打开成功:", self._serial)

    def _start_reader_thread(self) -> None:
        if self._serial is None:
            print(">>> [CanMVVisionSource] 串口未打开，无法启动读取线程")
            return
        if self._reader_thread and self._reader_thread.is_alive():
            return
        self._reader_thread = Thread(target=self._reader_loop, name="CanMVVisionReader", daemon=True)
        self._reader_thread.start()
        print(">>> [CanMVVisionSource] 后台读取线程已启动")

    def _reader_loop(self) -> None:
        assert self._serial is not None  # 在启动线程前已检查
        while not self._stop_event.is_set():
            try:
                raw = self._serial.readline()
            except serial.SerialException as exc:  # type: ignore[attr-defined]
                print(">>> [CanMVVisionSource] 串口读取异常:", exc)
                try:
                    self._serial.close()
                except Exception:
                    pass
                time.sleep(1.0)
                self._open_serial()
                if self._serial is None:
                    break
                continue
            except Exception as exc:
                print(">>> [CanMVVisionSource] 串口未知异常:", exc)
                break

            if not raw:
                continue
            try:
                text = raw.decode("utf-8", errors="ignore").strip()
            except Exception as exc:
                print(">>> [CanMVVisionSource] 解码失败:", repr(exc), "原始raw:", raw)
                continue

            if not text:
                continue

            # 调试：打印每一行串口收到的内容
            print(">>> [RAW]", repr(text))

            # ========== 1. 处理 FRAME_BASE64 / JPEG Base64 相关 ==========
            if "FRAME_BASE64" in text or "/9j/" in text or self._frame_collecting:
                if "FRAME_BASE64" in text:
                    self._frame_collecting = True
                    self._frame_buffer.clear()
                    idx = text.find("/9j/")
                    if idx >= 0:
                        first_chunk = text[idx:].strip()
                    else:
                        marker = text.find("FRAME_BASE64")
                        first_chunk = text[marker + len("FRAME_BASE64") :].strip()
                    if first_chunk:
                        self._frame_buffer.append(first_chunk)
                        print(">>> [CanMVVisionSource] 开始收集图像数据，首段长度:",
                              len(first_chunk))
                    else:
                        print(">>> [CanMVVisionSource] FRAME_BASE64 行没有明显 Base64 负载:", repr(text))
                    continue

                if self._frame_collecting and not text.startswith("VISION "):
                    chunk = text.strip()
                    if chunk:
                        self._frame_buffer.append(chunk)
                        print(">>> [CanMVVisionSource] 追加图像数据，当前片段长度:",
                              len(chunk))
                    continue

                if text.startswith("VISION "):
                    if self._frame_collecting and self._frame_buffer:
                        payload = "".join(self._frame_buffer).replace(" ", "").replace("\\n", "")
                        if payload:
                            self._latest_frame_base64 = payload
                            print(">>> [CanMVVisionSource] 完成多行图像收集，总长度:",
                                  len(self._latest_frame_base64))
                        else:
                            print(">>> [CanMVVisionSource] 收集到的 Base64 为空")
                    self._frame_collecting = False
                    self._frame_buffer.clear()
                    # 不要 continue，VISION 行还需继续解析

                elif text.startswith("/9j/"):
                    payload = text.strip()
                    if payload:
                        self._latest_frame_base64 = payload
                        print(">>> [CanMVVisionSource] 收到单行图像数据，长度:",
                              len(self._latest_frame_base64))
                    else:
                        print(">>> [CanMVVisionSource] '/9j/' 行却没有有效内容:", repr(text))
                    continue

            # ========== 2. 处理 VISION 行 ==========
            state = parse_vision_line(text)
            if state:
                try:
                    setattr(state, "frame_base64", self._latest_frame_base64)
                except Exception as exc:
                    print(">>> [CanMVVisionSource] 无法为 VisionState 设置 frame_base64:", exc)

                print(
                    ">>> [CanMVVisionSource] 收到 VISION 状态，当前是否有缓存图像帧:",
                    bool(self._latest_frame_base64),
                )
                self._latest_state = state
                self._states_queue.put(state)
                continue

            # ========== 3. 其他行丢弃 ==========
            # parse_vision_line 已经打印过 "非VISION行" 日志了

    def stream_states(self) -> Iterator[VisionState]:
        """
        持续返回解析得到的 VisionState。

        如果串口未能打开，则立即结束生成器。
        """

        if self._serial is None or self._reader_thread is None:
            print(">>> [CanMVVisionSource] 没有活跃串口连接，无法提供状态流")
            return

        while True:
            if self._stop_event.is_set() and self._states_queue.empty():
                break
            try:
                state = self._states_queue.get(timeout=0.2)
            except Empty:
                continue
            yield state

    def stream(self) -> Iterator[VisionState]:
        """兼容旧接口，等价于 stream_states()."""

        return self.stream_states()

    def get_latest_frame_base64(self) -> Optional[str]:
        """返回最近一次收到的 FRAME_BASE64 数据。"""

        return self._latest_frame_base64

    def get_latest_state(self) -> VisionState:
        """提供最新状态快照，供同步轮询使用。"""

        return self._latest_state

    def close(self) -> None:
        """停止后台线程并关闭串口。"""

        self._stop_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception as exc:  # pragma: no cover
                print(">>> [CanMVVisionSource] 关闭串口失败:", exc)

    def __del__(self) -> None:  # pragma: no cover - 防御性清理
        try:
            self.close()
        except Exception:
            pass


def main() -> None:
    """独立测试入口：从串口读并打印 VisionState。"""
    from pprint import pprint

    print(">>> vision_realtime_canmv.main() 启动")
    source = CanMVVisionSource()
    for state in source.stream_states():
        print(">>> [main] 解析得到 VisionState：")
        pprint(state)


if __name__ == "__main__":
    main()
