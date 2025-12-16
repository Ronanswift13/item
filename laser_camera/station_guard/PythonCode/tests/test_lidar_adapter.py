"""
tests/test_lidar_adapter.py

测试 TOF 激光雷达适配器的基本功能
使用模拟对象测试，无需连接实际硬件
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parents[1]))

from adapters.base.range_base import RangeMeasurement, RangeType, RangeStatus


class TestToFLidarAdapterStructure:
    """测试适配器结构和接口"""

    def test_adapter_import(self):
        """测试适配器能否成功导入"""
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter
        assert ToFLidarAdapter is not None

    def test_adapter_inherits_from_base(self):
        """测试适配器是否继承自 RangeAdapter 基类"""
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter
        from adapters.base.range_base import RangeAdapter

        assert issubclass(ToFLidarAdapter, RangeAdapter)

    def test_adapter_has_required_methods(self):
        """测试适配器是否实现了所有必需的方法"""
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

        required_methods = [
            'read_measurement',
            'get_range_type',
            'get_status',
            'get_max_range',
            'close'
        ]

        for method_name in required_methods:
            assert hasattr(ToFLidarAdapter, method_name), \
                f"Missing required method: {method_name}"


class TestToFLidarAdapterMocked:
    """使用模拟对象测试适配器功能"""

    @pytest.fixture
    def mock_lidar(self):
        """创建模拟的激光雷达对象"""
        mock = Mock()
        mock.port = "/dev/ttyUSB0"
        mock.read_measurement.return_value = (2.5, 850)  # (distance_m, strength)
        mock.close.return_value = None
        return mock

    @pytest.fixture
    def adapter(self, mock_lidar):
        """创建使用模拟激光雷达的适配器"""
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

        # 使用 patch 替换 _import_lidar_classes 函数以返回模拟类
        MockToFLidar = Mock(return_value=mock_lidar)
        MockSerialException = type('SerialException', (Exception,), {})

        with patch('adapters.legacy.lidar_tof_adapter._import_lidar_classes') as mock_import:
            mock_import.return_value = (MockToFLidar, MockSerialException)
            adapter = ToFLidarAdapter(port="/dev/ttyUSB0")
            yield adapter

    def test_read_measurement_success(self, adapter):
        """测试成功读取距离测量"""
        measurements = adapter.read_measurement()

        assert measurements is not None
        assert len(measurements) == 1

        m = measurements[0]
        assert isinstance(m, RangeMeasurement)
        assert m.distance_m == 2.5
        assert 0.0 <= m.confidence <= 1.0
        assert m.angle_or_sector is None  # 单点传感器
        assert m.timestamp > 0
        assert m.signal_strength == 850

    def test_read_measurement_confidence_calculation(self, adapter):
        """测试置信度计算"""
        # 模拟不同的强度值
        adapter.lidar.read_measurement.return_value = (2.0, 500)
        measurements = adapter.read_measurement()

        # 置信度 = strength / normalization_factor
        # 默认 normalization_factor = 1000.0
        expected_confidence = 500 / 1000.0
        assert measurements[0].confidence == pytest.approx(expected_confidence)

    def test_read_measurement_confidence_clamping(self, adapter):
        """测试置信度上限为 1.0"""
        # 强度值超过归一化因子
        adapter.lidar.read_measurement.return_value = (2.0, 1500)
        measurements = adapter.read_measurement()

        # 置信度应该被限制在 1.0
        assert measurements[0].confidence == 1.0

    def test_read_measurement_none_result(self, adapter):
        """测试读取失败的情况"""
        adapter.lidar.read_measurement.return_value = None
        measurements = adapter.read_measurement()

        assert measurements is None

    def test_get_range_type(self, adapter):
        """测试获取传感器类型"""
        range_type = adapter.get_range_type()
        assert range_type == RangeType.SINGLE_POINT

    def test_get_status_ready(self, adapter):
        """测试获取传感器状态"""
        status = adapter.get_status()
        assert status == RangeStatus.READY

    def test_get_max_range(self, adapter):
        """测试获取最大测距范围"""
        max_range = adapter.get_max_range()
        assert max_range > 0
        assert isinstance(max_range, float)

    def test_close(self, adapter):
        """测试关闭适配器"""
        adapter.close()
        adapter.lidar.close.assert_called_once()
        assert adapter.get_status() == RangeStatus.STOPPED

    def test_context_manager(self, mock_lidar):
        """测试上下文管理器协议"""
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

        MockToFLidar = Mock(return_value=mock_lidar)
        MockSerialException = type('SerialException', (Exception,), {})

        with patch('adapters.legacy.lidar_tof_adapter._import_lidar_classes') as mock_import:
            mock_import.return_value = (MockToFLidar, MockSerialException)

            # 使用 with 语句
            with ToFLidarAdapter(port="/dev/ttyUSB0") as adapter:
                measurements = adapter.read_measurement()
                assert measurements is not None

            # 退出 with 语句后应该调用 close()
            mock_lidar.close.assert_called()


class TestRangeMeasurementValidation:
    """测试 RangeMeasurement 对象的验证功能"""

    def test_valid_measurement(self):
        """测试有效的测量"""
        import time
        m = RangeMeasurement(
            distance_m=2.5,
            confidence=0.85,
            angle_or_sector=None,
            timestamp=time.time(),
            signal_strength=850
        )

        assert m.is_valid(max_range_m=10.0) == True

    def test_invalid_distance_too_far(self):
        """测试距离超出范围"""
        import time
        m = RangeMeasurement(
            distance_m=15.0,  # 超过最大范围
            confidence=0.85,
            angle_or_sector=None,
            timestamp=time.time()
        )

        assert m.is_valid(max_range_m=10.0) == False

    def test_invalid_confidence_zero(self):
        """测试置信度为 0"""
        import time
        m = RangeMeasurement(
            distance_m=2.5,
            confidence=0.0,  # 无效
            angle_or_sector=None,
            timestamp=time.time()
        )

        assert m.is_valid(max_range_m=10.0) == False


class TestAdapterIntegration:
    """测试适配器的集成场景"""

    @pytest.fixture
    def mock_lidar_sequence(self):
        """创建返回一系列测量值的模拟激光雷达"""
        mock = Mock()
        mock.port = "/dev/ttyUSB0"

        # 模拟一系列测量值
        measurements = [
            (2.0, 800),
            (2.5, 850),
            (3.0, 900),
            None,  # 读取失败
            (2.8, 820),
        ]
        mock.read_measurement.side_effect = measurements
        mock.close.return_value = None
        return mock

    def test_multiple_readings(self, mock_lidar_sequence):
        """测试连续多次读取"""
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

        MockToFLidar = Mock(return_value=mock_lidar_sequence)
        MockSerialException = type('SerialException', (Exception,), {})

        with patch('adapters.legacy.lidar_tof_adapter._import_lidar_classes') as mock_import:
            mock_import.return_value = (MockToFLidar, MockSerialException)

            adapter = ToFLidarAdapter(port="/dev/ttyUSB0")

            # 读取 5 次
            results = []
            for _ in range(5):
                measurement = adapter.read_measurement()
                results.append(measurement)

            # 验证结果
            assert results[0] is not None
            assert results[0][0].distance_m == 2.0

            assert results[1] is not None
            assert results[1][0].distance_m == 2.5

            assert results[2] is not None
            assert results[2][0].distance_m == 3.0

            assert results[3] is None  # 读取失败

            assert results[4] is not None
            assert results[4][0].distance_m == 2.8

            adapter.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
