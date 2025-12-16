"""
test_zones.py

测试 zones 模块的配置加载和区域查询功能
"""

import pytest
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parents[1]))

from core.zones import (
    SiteConfiguration,
    CabinetZone,
    WarningLine,
    DangerZone,
    load_site_config
)


class TestSiteConfiguration:
    """测试场地配置加载"""

    @pytest.fixture
    def config(self):
        """加载测试配置"""
        return load_site_config()

    def test_config_loads_successfully(self, config):
        """测试配置文件成功加载"""
        assert config is not None
        assert isinstance(config, SiteConfiguration)

    def test_corridor_dimensions(self, config):
        """测试走廊尺寸配置"""
        assert config.corridor_width_m == 2.0
        assert config.corridor_length_m == 6.5

    def test_cabinet_count(self, config):
        """测试机柜数量"""
        assert len(config.cabinets) == 5
        assert config.get_all_cabinet_ids() == [1, 2, 3, 4, 5]

    def test_cabinet_positions(self, config):
        """测试机柜位置配置"""
        # 验证机柜1的配置
        cabinet_1 = config.get_cabinet_by_id(1)
        assert cabinet_1 is not None
        assert cabinet_1.id == 1
        assert cabinet_1.x_range == (1.05, 1.95)
        assert cabinet_1.center_distance_m == 1.50

        # 验证机柜5的配置
        cabinet_5 = config.get_cabinet_by_id(5)
        assert cabinet_5 is not None
        assert cabinet_5.id == 5
        assert cabinet_5.x_range == (5.205, 6.105)
        assert cabinet_5.center_distance_m == 5.655

    def test_warning_lines_loaded(self, config):
        """测试警戒线配置"""
        assert len(config.warning_lines) >= 1
        yellow_line = config.warning_lines[0]
        assert yellow_line.id == "yellow_line_1"
        assert yellow_line.buffer_width_m == 0.2

    def test_danger_zones_loaded(self, config):
        """测试危险区域配置"""
        assert len(config.danger_zones) >= 1
        danger_zone = config.danger_zones[0]
        assert danger_zone.id == "high_voltage_area"


class TestCabinetZoneQueries:
    """测试机柜区域查询"""

    @pytest.fixture
    def config(self):
        return load_site_config()

    def test_point_in_cabinet_1(self, config):
        """测试点在1号机柜区域内"""
        # 1号机柜中心点
        cabinet = config.get_cabinet_at_point((1.5, 0.0))
        assert cabinet is not None
        assert cabinet.id == 1

    def test_point_in_cabinet_3(self, config):
        """测试点在3号机柜区域内"""
        # 3号机柜中心点
        cabinet = config.get_cabinet_at_point((3.855, 0.0))
        assert cabinet is not None
        assert cabinet.id == 3

    def test_point_between_cabinets(self, config):
        """测试点在机柜之间（不在任何机柜区域内）"""
        # 在1号和2号机柜之间，但不在任何机柜的front_zone内
        # 由于机柜的front_zone在y方向是[-0.5, 0.5]，测试点在外面
        cabinet = config.get_cabinet_at_point((3.0, 0.8))
        assert cabinet is None

    def test_point_outside_all_cabinets(self, config):
        """测试点在所有机柜外部"""
        cabinet = config.get_cabinet_at_point((0.5, 0.0))
        assert cabinet is None

    def test_point_at_cabinet_boundary(self, config):
        """测试点在机柜边界上"""
        # 1号机柜的右边界
        cabinet = config.get_cabinet_at_point((1.95, 0.0))
        # 边界点应该被某个机柜包含
        assert cabinet is not None


class TestWarningLineQueries:
    """测试警戒线缓冲区查询"""

    @pytest.fixture
    def config(self):
        return load_site_config()

    def test_point_in_warning_buffer(self, config):
        """测试点在警戒线缓冲区内"""
        # 警戒线在x=3.2，缓冲区宽度0.2
        # x=3.1应该在缓冲区内
        in_buffer, warning_line = config.is_point_in_warning_buffer((3.1, 0.0))
        assert in_buffer == True
        assert warning_line is not None
        assert warning_line.id == "yellow_line_1"

    def test_point_outside_warning_buffer(self, config):
        """测试点在警戒线缓冲区外"""
        # x=2.5应该不在缓冲区内
        in_buffer, warning_line = config.is_point_in_warning_buffer((2.5, 0.0))
        assert in_buffer == False
        assert warning_line is None

    def test_point_on_warning_line(self, config):
        """测试点在警戒线上"""
        # 正好在警戒线上
        in_buffer, warning_line = config.is_point_in_warning_buffer((3.2, 0.0))
        assert in_buffer == True


class TestDangerZoneQueries:
    """测试危险区域查询"""

    @pytest.fixture
    def config(self):
        return load_site_config()

    def test_point_in_danger_zone(self, config):
        """测试点在危险区域内"""
        # 危险区域：x=[6.0, 6.5], y=[-0.8, 0.8]
        in_danger, danger_zone = config.is_point_in_danger_zone((6.2, 0.0))
        assert in_danger == True
        assert danger_zone is not None
        assert danger_zone.id == "high_voltage_area"

    def test_point_outside_danger_zone(self, config):
        """测试点在危险区域外"""
        in_danger, danger_zone = config.is_point_in_danger_zone((3.0, 0.0))
        assert in_danger == False
        assert danger_zone is None


class TestAuthorizationQueries:
    """测试授权查询"""

    @pytest.fixture
    def config(self):
        return load_site_config()

    def test_authorization_all_access(self, config):
        """测试默认全员访问授权"""
        # 默认配置中所有机柜的authorized_persons为空，表示所有人都可访问
        assert config.is_authorized_at_cabinet((1.5, 0.0), "person_1") == True
        assert config.is_authorized_at_cabinet((1.5, 0.0), "person_2") == True

    def test_authorization_outside_cabinet(self, config):
        """测试在机柜外的授权（应该总是True）"""
        # 不在任何机柜区域，默认有权限
        assert config.is_authorized_at_cabinet((0.5, 0.0), "person_1") == True


class TestRealWorldScenarios:
    """测试实际场景"""

    @pytest.fixture
    def config(self):
        return load_site_config()

    def test_worker_at_each_cabinet(self, config):
        """测试工人在每个机柜中心的查询"""
        expected_positions = [
            (1.50, 0.0, 1),   # Cabinet 1
            (2.40, 0.0, 2),   # Cabinet 2
            (3.855, 0.0, 3),  # Cabinet 3
            (4.755, 0.0, 4),  # Cabinet 4
            (5.655, 0.0, 5),  # Cabinet 5
        ]

        for x, y, expected_id in expected_positions:
            cabinet = config.get_cabinet_at_point((x, y))
            assert cabinet is not None, f"No cabinet found at ({x}, {y})"
            assert cabinet.id == expected_id, f"Expected cabinet {expected_id}, got {cabinet.id}"

    def test_approaching_warning_line(self, config):
        """测试接近警戒线的情况"""
        # 从左侧接近警戒线
        positions = [
            (2.8, 0.0),  # 远离警戒线
            (3.0, 0.0),  # 接近但未进入缓冲区
            (3.1, 0.0),  # 进入缓冲区
            (3.2, 0.0),  # 在警戒线上
            (3.3, 0.0),  # 越过警戒线
        ]

        for x, y in positions:
            in_buffer, _ = config.is_point_in_warning_buffer((x, y))
            print(f"Position ({x}, {y}): in_buffer={in_buffer}")

        # 验证缓冲区检测
        assert config.is_point_in_warning_buffer((2.8, 0.0))[0] == False
        assert config.is_point_in_warning_buffer((3.1, 0.0))[0] == True
        assert config.is_point_in_warning_buffer((3.3, 0.0))[0] == True

    def test_configuration_summary(self, config):
        """测试配置摘要生成"""
        summary = config.summary()
        assert "5" in summary  # 5个机柜
        assert "Cabinet" in summary
        assert "Corridor" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
