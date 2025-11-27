#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用配置：串口、机位、视觉与日志等参数聚合。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass
class SerialConfig:
    """串口参数配置。"""

    port: str = "/dev/tty.usbserial-1110"
    baudrate: int = 9600
    timeout: float = 0.5  # 单位：秒


@dataclass
class LidarConfig:
    """激光雷达串口参数配置。"""

    port: str = "/dev/cu.usbserial-1110"
    baudrate: int = 9600
    timeout: float = 1.0 # 单位：秒


@dataclass
class CabinetConfig:
    """单个机柜的站位距离配置。"""

    id: str
    name: str
    min_distance_cm: float
    max_distance_cm: float


CABINETS: Dict[str, CabinetConfig] = {
    "G01": CabinetConfig(
        id="G01",
        name="走廊左侧第一个机柜",
        min_distance_cm=80.0,
        max_distance_cm=120.0,
    ),
}

AUTHORIZED_CABINET_ID = "G01"


@dataclass
class VisionConfig:
    """视觉算法相关的控制参数。"""

    gesture_max_wait_frames: int = 15


@dataclass
class AppConfig:
    """应用总体配置，聚合串口、机位、视觉与日志参数。"""

    serial: SerialConfig = field(default_factory=SerialConfig)
    cabinet: CabinetConfig = field(default_factory=lambda: CABINETS[AUTHORIZED_CABINET_ID])
    vision: VisionConfig = field(default_factory=VisionConfig)
    log_path: str = "logs/app.log"


DEFAULT_CONFIG = AppConfig()
LIDAR = LidarConfig()


def _deep_update_dataclass(instance, data: dict):
    """递归更新 dataclass 实例中的字段。"""

    for key, value in data.items():
        if hasattr(instance, key):
            attr = getattr(instance, key)
            if isinstance(attr, (SerialConfig, CabinetConfig, VisionConfig, AppConfig)) and isinstance(value, dict):
                _deep_update_dataclass(attr, value)
            else:
                setattr(instance, key, value)


def load_config(path: Optional[Path] = None) -> AppConfig:
    """从 JSON 文件加载配置，若文件不存在则返回默认配置。"""

    config = AppConfig(
        serial=replace(DEFAULT_CONFIG.serial),
        cabinet=replace(DEFAULT_CONFIG.cabinet),
        vision=replace(DEFAULT_CONFIG.vision),
        log_path=DEFAULT_CONFIG.log_path,
    )

    if path is None:
        path = Path("config.json")

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _deep_update_dataclass(config, data)
        except Exception as exc:
            raise RuntimeError(f"无法解析配置文件 {path}: {exc}") from exc
    return config


def write_example_config(path: Path = Path("config_example.json")) -> None:
    """将默认配置写入示例文件，便于手工编辑。"""

    data = asdict(DEFAULT_CONFIG)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


CONFIG = load_config()


def main() -> None:
    """命令行入口：打印当前配置并生成示例文件。"""

    print("当前配置：")
    print(json.dumps(asdict(CONFIG), indent=2, ensure_ascii=False))
    example_path = Path("config_example.json")
    write_example_config(example_path)
    print(f"\n示例配置已写入：{example_path}")


if __name__ == "__main__":
    main()
