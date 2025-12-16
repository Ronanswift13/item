"""
core/zones.py

Zone configuration loader and query functions.
Loads site configuration from YAML and provides geometric zone queries.

This module acts as the bridge between static configuration files
and runtime geometry calculations.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from .geometry2d import (
    Point, Polygon, LineSegment,
    point_in_polygon,
    point_in_linear_buffer,
    validate_polygon
)


@dataclass
class CabinetZone:
    """机柜区域定义"""
    id: int
    x_range: Tuple[float, float]
    center_distance_m: float
    front_zone: Polygon
    authorized_persons: List[str]

    def is_authorized(self, person_id: str) -> bool:
        """检查人员是否有权限访问此机柜区域"""
        # 空列表表示所有人都可以访问
        if not self.authorized_persons:
            return True
        return person_id in self.authorized_persons

    def contains_point(self, point: Point) -> bool:
        """检查点是否在机柜区域内"""
        return point_in_polygon(point, self.front_zone)


@dataclass
class WarningLine:
    """警戒线定义"""
    id: str
    description: str
    segment: LineSegment
    buffer_width_m: float

    def point_in_buffer(self, point: Point) -> bool:
        """检查点是否在警戒线缓冲区内"""
        return point_in_linear_buffer(point, self.segment, self.buffer_width_m)


@dataclass
class DangerZone:
    """危险区域定义"""
    id: str
    description: str
    polygon: Polygon

    def contains_point(self, point: Point) -> bool:
        """检查点是否在危险区域内"""
        return point_in_polygon(point, self.polygon)


class SiteConfiguration:
    """场地配置管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化场地配置

        Args:
            config_path: YAML配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径
            config_path = Path(__file__).parents[1] / "config" / "site_config.yaml"

        self.config_path = config_path
        self.raw_config: Dict[str, Any] = {}
        self.cabinets: List[CabinetZone] = []
        self.warning_lines: List[WarningLine] = []
        self.danger_zones: List[DangerZone] = []
        self.corridor_width_m: float = 0.0
        self.corridor_length_m: float = 0.0

        self._load_config()
        self._validate_config()

    def _load_config(self) -> None:
        """从YAML文件加载配置"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.raw_config = yaml.safe_load(f)

        # 加载走廊配置
        corridor = self.raw_config.get('corridor', {})
        self.corridor_width_m = corridor.get('width_m', 2.0)
        self.corridor_length_m = corridor.get('length_m', 6.0)

        # 加载机柜区域
        for cab_config in self.raw_config.get('cabinets', []):
            cabinet = CabinetZone(
                id=cab_config['id'],
                x_range=tuple(cab_config.get('x_range', [0, 1])),
                center_distance_m=cab_config.get('center_distance_m', 0.0),
                front_zone=[tuple(p) for p in cab_config['front_zone']],
                authorized_persons=cab_config.get('authorized_persons', [])
            )
            self.cabinets.append(cabinet)

        # 加载警戒线
        for line_config in self.raw_config.get('warning_lines', []):
            segment_raw = line_config['segment']
            warning_line = WarningLine(
                id=line_config['id'],
                description=line_config.get('description', ''),
                segment=(tuple(segment_raw[0]), tuple(segment_raw[1])),
                buffer_width_m=line_config.get('buffer_width_m', 0.2)
            )
            self.warning_lines.append(warning_line)

        # 加载危险区域
        for zone_config in self.raw_config.get('danger_zones', []):
            danger_zone = DangerZone(
                id=zone_config['id'],
                description=zone_config.get('description', ''),
                polygon=[tuple(p) for p in zone_config['polygon']]
            )
            self.danger_zones.append(danger_zone)

    def _validate_config(self) -> None:
        """验证配置的有效性"""
        # 验证机柜区域多边形
        for cabinet in self.cabinets:
            is_valid, msg = validate_polygon(cabinet.front_zone)
            if not is_valid:
                raise ValueError(f"Cabinet {cabinet.id} has invalid polygon: {msg}")

        # 验证危险区域多边形
        for zone in self.danger_zones:
            is_valid, msg = validate_polygon(zone.polygon)
            if not is_valid:
                raise ValueError(f"Danger zone {zone.id} has invalid polygon: {msg}")

    # ========== 查询方法 ==========

    def get_cabinet_at_point(self, point: Point, person_id: Optional[str] = None) -> Optional[CabinetZone]:
        """
        查询点所在的机柜区域

        Args:
            point: 查询点坐标
            person_id: 人员ID（可选，用于权限检查）

        Returns:
            机柜区域对象，如果不在任何机柜区域则返回None
        """
        for cabinet in self.cabinets:
            if cabinet.contains_point(point):
                return cabinet
        return None

    def is_point_in_warning_buffer(self, point: Point) -> Tuple[bool, Optional[WarningLine]]:
        """
        检查点是否在任何警戒线缓冲区内

        Returns:
            (是否在缓冲区, 警戒线对象或None)
        """
        for warning_line in self.warning_lines:
            if warning_line.point_in_buffer(point):
                return True, warning_line
        return False, None

    def is_point_in_danger_zone(self, point: Point) -> Tuple[bool, Optional[DangerZone]]:
        """
        检查点是否在危险区域内

        Returns:
            (是否在危险区域, 危险区域对象或None)
        """
        for danger_zone in self.danger_zones:
            if danger_zone.contains_point(point):
                return True, danger_zone
        return False, None

    def is_authorized_at_cabinet(self, point: Point, person_id: str) -> bool:
        """
        检查人员在指定位置是否有权限

        Args:
            point: 人员位置
            person_id: 人员ID

        Returns:
            是否有权限（如果不在机柜区域则返回True）
        """
        cabinet = self.get_cabinet_at_point(point)
        if cabinet is None:
            # 不在任何机柜区域，默认有权限
            return True
        return cabinet.is_authorized(person_id)

    def get_all_cabinet_ids(self) -> List[int]:
        """获取所有机柜ID列表"""
        return [cab.id for cab in self.cabinets]

    def get_cabinet_by_id(self, cabinet_id: int) -> Optional[CabinetZone]:
        """根据ID获取机柜区域"""
        for cabinet in self.cabinets:
            if cabinet.id == cabinet_id:
                return cabinet
        return None

    def summary(self) -> str:
        """返回配置摘要信息"""
        lines = [
            "Site Configuration Summary",
            "=" * 50,
            f"Corridor: {self.corridor_length_m}m × {self.corridor_width_m}m",
            f"Cabinets: {len(self.cabinets)}",
            f"Warning Lines: {len(self.warning_lines)}",
            f"Danger Zones: {len(self.danger_zones)}",
            "",
            "Cabinet Details:"
        ]

        for cabinet in self.cabinets:
            auth_str = f"{len(cabinet.authorized_persons)} persons" if cabinet.authorized_persons else "all"
            lines.append(f"  Cabinet {cabinet.id}: center={cabinet.center_distance_m:.2f}m, authorized={auth_str}")

        return "\n".join(lines)


# ==============================================================================
# Module-level convenience functions
# ==============================================================================

_default_config: Optional[SiteConfiguration] = None


def load_site_config(config_path: Optional[Path] = None) -> SiteConfiguration:
    """
    加载场地配置（单例模式）

    Args:
        config_path: 配置文件路径，如果为None则使用默认路径

    Returns:
        SiteConfiguration对象
    """
    global _default_config
    if _default_config is None or config_path is not None:
        _default_config = SiteConfiguration(config_path)
    return _default_config


def get_site_config() -> SiteConfiguration:
    """
    获取当前加载的场地配置

    Returns:
        SiteConfiguration对象

    Raises:
        RuntimeError: 如果配置尚未加载
    """
    global _default_config
    if _default_config is None:
        _default_config = load_site_config()
    return _default_config


if __name__ == "__main__":
    # 简单测试
    print("Loading site configuration...")
    config = load_site_config()
    print(config.summary())

    # 测试点查询
    print("\nTest point queries:")
    test_points = [
        (1.5, 0.0),   # Cabinet 1 center
        (2.4, 0.0),   # Cabinet 2 center
        (3.0, 0.0),   # Between cabinets
        (3.2, 0.0),   # On warning line
        (6.2, 0.0),   # In danger zone
    ]

    for point in test_points:
        cabinet = config.get_cabinet_at_point(point)
        in_warning, warning_line = config.is_point_in_warning_buffer(point)
        in_danger, danger_zone = config.is_point_in_danger_zone(point)

        print(f"  Point {point}:")
        print(f"    Cabinet: {cabinet.id if cabinet else 'None'}")
        print(f"    Warning: {warning_line.id if in_warning else 'No'}")
        print(f"    Danger: {danger_zone.id if in_danger else 'No'}")
