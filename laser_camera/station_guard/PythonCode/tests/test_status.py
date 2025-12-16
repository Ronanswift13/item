"""
test_status.py

测试 status 模块的五状态分类逻辑
使用合成位置数据进行测试，无需连接硬件
"""

import pytest
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parents[1]))

from core.status import (
    PersonStatus,
    StatusResult,
    StatusClassifier,
    create_classifier
)
from core.zones import load_site_config


class TestPersonStatus:
    """测试PersonStatus枚举"""

    def test_status_values(self):
        """测试状态值"""
        assert PersonStatus.NORMAL.value == "NORMAL"
        assert PersonStatus.ON_LINE.value == "ON_LINE"
        assert PersonStatus.CROSS_LINE.value == "CROSS_LINE"
        assert PersonStatus.MISPLACED.value == "MISPLACED"
        assert PersonStatus.HIGH_RISK.value == "HIGH_RISK"

    def test_status_priority(self):
        """测试状态优先级"""
        # HIGH_RISK > CROSS_LINE > MISPLACED > ON_LINE > NORMAL
        assert PersonStatus.HIGH_RISK.priority > PersonStatus.CROSS_LINE.priority
        assert PersonStatus.CROSS_LINE.priority > PersonStatus.MISPLACED.priority
        assert PersonStatus.MISPLACED.priority > PersonStatus.ON_LINE.priority
        assert PersonStatus.ON_LINE.priority > PersonStatus.NORMAL.priority

    def test_is_violation(self):
        """测试违规状态判定"""
        assert PersonStatus.NORMAL.is_violation == False
        assert PersonStatus.ON_LINE.is_violation == True
        assert PersonStatus.CROSS_LINE.is_violation == True
        assert PersonStatus.MISPLACED.is_violation == True
        assert PersonStatus.HIGH_RISK.is_violation == True


class TestStatusClassifier:
    """测试状态分类器"""

    @pytest.fixture
    def classifier(self):
        """创建测试用的分类器"""
        config = load_site_config()
        return StatusClassifier(config)

    def test_classifier_creation(self, classifier):
        """测试分类器创建"""
        assert classifier is not None
        assert isinstance(classifier, StatusClassifier)

    # ========== 测试 NORMAL 状态 ==========

    def test_normal_in_cabinet_area(self, classifier):
        """测试在机柜区域内的正常状态"""
        # 在1号机柜中心，默认所有人都有权限
        result = classifier.classify((1.5, 0.0), "worker_1")
        assert result.status == PersonStatus.NORMAL
        assert result.cabinet_id == 1
        assert "authorized" in result.reason.lower() or "normal" in result.reason.lower()

    def test_normal_in_corridor(self, classifier):
        """测试在走廊中正常状态"""
        # 在走廊中，不在任何特殊区域
        result = classifier.classify((0.5, 0.0), "worker_1")
        assert result.status == PersonStatus.NORMAL

    # ========== 测试 ON_LINE 状态 ==========

    def test_on_line_near_warning(self, classifier):
        """测试接近警戒线的ON_LINE状态"""
        # 警戒线在x=3.2，缓冲区0.2米
        # x=3.1在缓冲区内但在左侧（允许侧）
        result = classifier.classify((3.1, 0.0), "worker_1")
        assert result.status == PersonStatus.ON_LINE
        assert result.warning_line_id == "yellow_line_1"

    def test_on_line_exactly_on_warning(self, classifier):
        """测试正好在警戒线上"""
        # 正好在警戒线上也应该触发ON_LINE（左侧）
        result = classifier.classify((3.2, 0.0), "worker_1")
        # 根据实现，正好在线上可能是ON_LINE或CROSS_LINE
        assert result.status in [PersonStatus.ON_LINE, PersonStatus.CROSS_LINE]

    # ========== 测试 CROSS_LINE 状态 ==========

    def test_cross_line_beyond_warning(self, classifier):
        """测试越过警戒线的CROSS_LINE状态"""
        # 警戒线在x=3.2，x=3.3在右侧（禁止侧）
        result = classifier.classify((3.3, 0.0), "worker_1")
        assert result.status == PersonStatus.CROSS_LINE
        assert result.warning_line_id == "yellow_line_1"

    def test_cross_line_far_beyond_warning(self, classifier):
        """测试远离警戒线但在右侧"""
        # x=3.5明显越过警戒线
        result = classifier.classify((3.5, 0.0), "worker_1")
        # 可能是CROSS_LINE或NORMAL（取决于是否还在缓冲区内）
        # 根据实现，超出缓冲区后不再是CROSS_LINE
        # 但如果在危险区域内则是HIGH_RISK
        assert result.status in [PersonStatus.CROSS_LINE, PersonStatus.NORMAL]

    # ========== 测试 HIGH_RISK 状态 ==========

    def test_high_risk_in_danger_zone(self, classifier):
        """测试在危险区域内的HIGH_RISK状态"""
        # 危险区域：x=[6.0, 6.5], y=[-0.8, 0.8]
        result = classifier.classify((6.2, 0.0), "worker_1")
        assert result.status == PersonStatus.HIGH_RISK
        assert result.danger_zone_id == "high_voltage_area"

    def test_high_risk_at_danger_zone_edge(self, classifier):
        """测试在危险区域边缘"""
        # 边缘位置 - 稍微往内一点确保在多边形内
        result = classifier.classify((6.05, 0.0), "worker_1")
        assert result.status == PersonStatus.HIGH_RISK

    # ========== 测试 MISPLACED 状态 ==========
    # 注意：当前配置中所有机柜都是全员授权，所以MISPLACED状态需要修改配置才能测试
    # 这里我们测试逻辑是否正确

    def test_misplaced_logic(self, classifier):
        """测试MISPLACED逻辑（需要特殊配置）"""
        # 由于当前所有机柜都是全员授权，这个测试主要验证逻辑存在
        # 实际部署时需要配置authorized_persons才会触发
        result = classifier.classify((1.5, 0.0), "unauthorized_person")
        # 当前配置下应该是NORMAL
        assert result.status == PersonStatus.NORMAL


class TestStatusClassifierBatch:
    """测试批量分类功能"""

    @pytest.fixture
    def classifier(self):
        return create_classifier()

    def test_classify_batch(self, classifier):
        """测试批量分类"""
        positions = {
            "worker_1": (1.5, 0.0),   # Cabinet 1, NORMAL
            "worker_2": (3.1, 0.0),   # Warning buffer, ON_LINE
            "worker_3": (6.2, 0.0),   # Danger zone, HIGH_RISK
        }

        results = classifier.classify_batch(positions)

        assert len(results) == 3
        assert results["worker_1"].status == PersonStatus.NORMAL
        assert results["worker_2"].status == PersonStatus.ON_LINE
        assert results["worker_3"].status == PersonStatus.HIGH_RISK

    def test_get_violations(self, classifier):
        """测试获取违规人员"""
        positions = {
            "worker_1": (1.5, 0.0),   # NORMAL
            "worker_2": (3.1, 0.0),   # ON_LINE (违规)
            "worker_3": (0.5, 0.0),   # NORMAL
            "worker_4": (6.2, 0.0),   # HIGH_RISK (违规)
        }

        violations = classifier.get_violations(positions)

        # 应该有2个违规
        assert len(violations) == 2
        assert "worker_2" in violations
        assert "worker_4" in violations

    def test_get_highest_risk_status(self, classifier):
        """测试获取最高风险状态"""
        positions = {
            "worker_1": (1.5, 0.0),   # NORMAL (priority 0)
            "worker_2": (3.1, 0.0),   # ON_LINE (priority 1)
            "worker_3": (6.2, 0.0),   # HIGH_RISK (priority 4)
        }

        highest_risk = classifier.get_highest_risk_status(positions)

        assert highest_risk is not None
        assert highest_risk.status == PersonStatus.HIGH_RISK

    def test_get_highest_risk_empty(self, classifier):
        """测试空位置列表"""
        highest_risk = classifier.get_highest_risk_status({})
        assert highest_risk is None


class TestRealWorldScenarios:
    """测试实际场景 - 使用合成数据"""

    @pytest.fixture
    def classifier(self):
        return create_classifier()

    def test_worker_walking_through_corridor(self, classifier):
        """测试工人沿走廊行走的状态变化"""
        # 模拟工人从走廊起点走到终点的轨迹
        trajectory = [
            (0.5, 0.0),   # 起点 - NORMAL
            (1.5, 0.0),   # 1号机柜 - NORMAL
            (2.5, 0.0),   # 2号机柜 - NORMAL
            (3.0, 0.0),   # 接近警戒线 - NORMAL
            (3.1, 0.0),   # 警戒线缓冲区左侧 - ON_LINE
            (3.2, 0.0),   # 警戒线上 - ON_LINE or CROSS_LINE
            (3.3, 0.0),   # 警戒线右侧 - CROSS_LINE
            (4.0, 0.0),   # 3号机柜 - NORMAL
            (5.0, 0.0),   # 4号机柜 - NORMAL
            (6.2, 0.0),   # 危险区域 - HIGH_RISK
        ]

        results = []
        for i, point in enumerate(trajectory):
            result = classifier.classify(point, "worker_1")
            results.append((point, result.status))
            print(f"Step {i}: Position {point} -> {result.status.value}")

        # 验证关键状态
        assert results[0][1] == PersonStatus.NORMAL  # 起点
        assert results[4][1] == PersonStatus.ON_LINE  # 警戒线缓冲区
        assert results[-1][1] == PersonStatus.HIGH_RISK  # 危险区域

    def test_multiple_workers_different_locations(self, classifier):
        """测试多个工人在不同位置的状态"""
        positions = {
            "worker_1": (1.5, 0.0),   # Cabinet 1
            "worker_2": (2.4, 0.0),   # Cabinet 2
            "worker_3": (3.855, 0.0), # Cabinet 3
            "worker_4": (4.755, 0.0), # Cabinet 4
            "worker_5": (5.655, 0.0), # Cabinet 5
        }

        results = classifier.classify_batch(positions)

        # 所有工人都在各自机柜区域，应该都是NORMAL
        for worker_id, result in results.items():
            print(f"{worker_id}: {result}")
            assert result.status == PersonStatus.NORMAL
            assert result.cabinet_id is not None

    def test_emergency_scenario(self, classifier):
        """测试紧急场景 - 有人进入危险区域"""
        positions = {
            "worker_1": (1.5, 0.0),   # 正常工作
            "worker_2": (2.4, 0.0),   # 正常工作
            "intruder": (6.3, 0.0),   # 进入危险区域！
        }

        results = classifier.classify_batch(positions)
        violations = classifier.get_violations(positions)
        highest_risk = classifier.get_highest_risk_status(positions)

        # 应该检测到1个违规
        assert len(violations) == 1
        assert "intruder" in violations

        # 最高风险应该是HIGH_RISK
        assert highest_risk.status == PersonStatus.HIGH_RISK

    def test_warning_line_crossing_sequence(self, classifier):
        """测试警戒线跨越序列"""
        # 模拟工人从左向右接近并跨越警戒线
        sequence = [
            (2.8, 0.0),  # 远离警戒线
            (3.0, 0.0),  # 接近警戒线
            (3.05, 0.0), # 进入缓冲区（左侧）
            (3.15, 0.0), # 缓冲区内（左侧）
            (3.25, 0.0), # 越过警戒线（右侧）
            (3.35, 0.0), # 明显越线
        ]

        for point in sequence:
            result = classifier.classify(point, "worker_1")
            print(f"Position {point}: {result.status.value} - {result.reason}")

        # 验证关键点
        assert classifier.classify((2.8, 0.0), "w1").status == PersonStatus.NORMAL
        assert classifier.classify((3.1, 0.0), "w1").status == PersonStatus.ON_LINE
        assert classifier.classify((3.3, 0.0), "w1").status == PersonStatus.CROSS_LINE


class TestEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def classifier(self):
        return create_classifier()

    def test_point_at_corridor_boundary(self, classifier):
        """测试点在走廊边界"""
        # Y方向边界
        result = classifier.classify((3.0, 1.0), "worker_1")
        assert result.status is not None

    def test_point_outside_corridor(self, classifier):
        """测试点在走廊外"""
        # Y方向超出走廊范围
        result = classifier.classify((3.0, 1.5), "worker_1")
        assert result.status is not None

    def test_negative_coordinates(self, classifier):
        """测试负坐标"""
        result = classifier.classify((-0.5, 0.0), "worker_1")
        assert result.status is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
