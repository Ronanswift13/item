"""
core/status.py

Person status classifier - the core decision engine.
Classifies each person's position into one of five safety states.

This module is purely functional - given a position and person ID,
it returns a status classification based on geometry and authorization rules.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .geometry2d import Point
from .zones import SiteConfiguration, CabinetZone, WarningLine, DangerZone


class PersonStatus(Enum):
    """
    五状态分类

    优先级从高到低：HIGH_RISK > CROSS_LINE > MISPLACED > ON_LINE > NORMAL
    """
    NORMAL = "NORMAL"           # 正常：在授权区域内，无违规
    ON_LINE = "ON_LINE"         # 压线：进入警戒线缓冲区
    CROSS_LINE = "CROSS_LINE"   # 越线：跨越警戒线进入禁区
    MISPLACED = "MISPLACED"     # 错位：在未授权的机柜区域
    HIGH_RISK = "HIGH_RISK"     # 高危：进入或接近危险区域

    def __str__(self) -> str:
        return self.value

    @property
    def priority(self) -> int:
        """状态优先级，数值越大越严重"""
        priority_map = {
            PersonStatus.NORMAL: 0,
            PersonStatus.ON_LINE: 1,
            PersonStatus.MISPLACED: 2,
            PersonStatus.CROSS_LINE: 3,
            PersonStatus.HIGH_RISK: 4,
        }
        return priority_map[self]

    @property
    def is_violation(self) -> bool:
        """是否为违规状态"""
        return self != PersonStatus.NORMAL


@dataclass
class StatusResult:
    """状态分类结果"""
    status: PersonStatus
    reason: str  # 分类原因说明
    cabinet_id: Optional[int] = None  # 如果在机柜区域，记录机柜ID
    warning_line_id: Optional[str] = None  # 如果触发警戒线，记录警戒线ID
    danger_zone_id: Optional[str] = None  # 如果在危险区域，记录危险区域ID

    def __str__(self) -> str:
        parts = [f"{self.status.value}: {self.reason}"]
        if self.cabinet_id is not None:
            parts.append(f"(Cabinet {self.cabinet_id})")
        if self.warning_line_id:
            parts.append(f"(Warning: {self.warning_line_id})")
        if self.danger_zone_id:
            parts.append(f"(Danger: {self.danger_zone_id})")
        return " ".join(parts)


class StatusClassifier:
    """
    状态分类器

    基于几何规则和授权信息对人员位置进行分类
    """

    def __init__(self, site_config: SiteConfiguration):
        """
        初始化状态分类器

        Args:
            site_config: 场地配置对象
        """
        self.site_config = site_config

    def classify(self, point: Point, person_id: str = "unknown") -> StatusResult:
        """
        对人员位置进行状态分类

        分类逻辑（按优先级顺序检查）：
        1. HIGH_RISK: 在危险区域内
        2. CROSS_LINE: 跨越警戒线（在警戒线一侧且未授权）
        3. MISPLACED: 在机柜区域但未授权
        4. ON_LINE: 在警戒线缓冲区内
        5. NORMAL: 默认正常状态

        Args:
            point: 人员位置坐标 (x, y)
            person_id: 人员ID，用于权限验证

        Returns:
            StatusResult对象
        """

        # 1. 最高优先级：检查是否在危险区域
        in_danger, danger_zone = self.site_config.is_point_in_danger_zone(point)
        if in_danger:
            return StatusResult(
                status=PersonStatus.HIGH_RISK,
                reason=f"In danger zone: {danger_zone.description}",
                danger_zone_id=danger_zone.id
            )

        # 2. 检查是否跨越警戒线
        # 警戒线的"跨越"定义：
        # - 在3号机柜前的警戒线（x=3.2）右侧（x > 3.2）为跨越
        # - 这是一个简化的实现，实际可能需要更复杂的逻辑
        in_warning_buffer, warning_line = self.site_config.is_point_in_warning_buffer(point)
        if in_warning_buffer:
            # 检查是否在警戒线的"禁止"一侧
            # 对于垂直警戒线（x=3.2），检查是否在右侧（更深入的区域）
            if warning_line and len(self.site_config.warning_lines) > 0:
                # 获取警戒线的x坐标
                line_x = warning_line.segment[0][0]
                if point[0] > line_x:  # 在警戒线右侧视为越线
                    return StatusResult(
                        status=PersonStatus.CROSS_LINE,
                        reason=f"Crossed warning line: {warning_line.description}",
                        warning_line_id=warning_line.id
                    )

        # 3. 检查是否在未授权的机柜区域
        cabinet = self.site_config.get_cabinet_at_point(point)
        if cabinet is not None:
            if not cabinet.is_authorized(person_id):
                return StatusResult(
                    status=PersonStatus.MISPLACED,
                    reason=f"Unauthorized access to cabinet {cabinet.id}",
                    cabinet_id=cabinet.id
                )

        # 4. 检查是否在警戒线缓冲区（但在允许的一侧）
        if in_warning_buffer and warning_line:
            return StatusResult(
                status=PersonStatus.ON_LINE,
                reason=f"Near warning line: {warning_line.description}",
                warning_line_id=warning_line.id
            )

        # 5. 默认正常状态
        reason = "Normal position"
        if cabinet:
            reason = f"In authorized cabinet {cabinet.id} area"

        return StatusResult(
            status=PersonStatus.NORMAL,
            reason=reason,
            cabinet_id=cabinet.id if cabinet else None
        )

    def classify_batch(self, positions: dict) -> dict:
        """
        批量分类多个人员的位置

        Args:
            positions: {person_id: (x, y)} 字典

        Returns:
            {person_id: StatusResult} 字典
        """
        results = {}
        for person_id, point in positions.items():
            results[person_id] = self.classify(point, person_id)
        return results

    def get_violations(self, positions: dict) -> dict:
        """
        获取所有违规人员

        Args:
            positions: {person_id: (x, y)} 字典

        Returns:
            {person_id: StatusResult} 字典，仅包含违规状态
        """
        all_results = self.classify_batch(positions)
        return {
            person_id: result
            for person_id, result in all_results.items()
            if result.status.is_violation
        }

    def get_highest_risk_status(self, positions: dict) -> Optional[StatusResult]:
        """
        获取所有人员中风险最高的状态

        Args:
            positions: {person_id: (x, y)} 字典

        Returns:
            风险最高的StatusResult，如果没有人则返回None
        """
        if not positions:
            return None

        all_results = self.classify_batch(positions)
        return max(all_results.values(), key=lambda r: r.status.priority)


def create_classifier(site_config: Optional[SiteConfiguration] = None) -> StatusClassifier:
    """
    创建状态分类器的便捷函数

    Args:
        site_config: 场地配置，如果为None则加载默认配置

    Returns:
        StatusClassifier对象
    """
    if site_config is None:
        from .zones import load_site_config
        site_config = load_site_config()

    return StatusClassifier(site_config)


if __name__ == "__main__":
    # 简单测试
    from .zones import load_site_config

    print("Creating status classifier...")
    config = load_site_config()
    classifier = create_classifier(config)

    print("\nTest status classification:")

    # 测试用例
    test_cases = [
        ("person_1", (1.5, 0.0), "Cabinet 1 center"),
        ("person_2", (3.0, 0.0), "Between cabinets"),
        ("person_3", (3.15, 0.0), "Near warning line (left)"),
        ("person_4", (3.25, 0.0), "Near warning line (right)"),
        ("person_5", (4.5, 0.0), "Cabinet 4 center"),
        ("person_6", (6.3, 0.0), "In danger zone"),
    ]

    for person_id, point, description in test_cases:
        result = classifier.classify(point, person_id)
        print(f"\n  {description}")
        print(f"    Position: {point}")
        print(f"    Result: {result}")

    # 批量测试
    print("\n" + "=" * 50)
    print("Batch classification test:")
    positions = {
        "worker_1": (1.5, 0.0),
        "worker_2": (3.25, 0.0),
        "worker_3": (6.3, 0.0),
    }

    violations = classifier.get_violations(positions)
    print(f"\nFound {len(violations)} violations:")
    for person_id, result in violations.items():
        print(f"  {person_id}: {result}")

    highest_risk = classifier.get_highest_risk_status(positions)
    print(f"\nHighest risk: {highest_risk}")
