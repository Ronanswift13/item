"""
adapters/legacy/lidar_tof_adapter.py

适配器：封装现有的 TOF 激光雷达代码
将 (distance_m, strength) 元组转换为标准化的 RangeMeasurement 对象

这是一个最小包装器 - 您的原有 lidar_tof.py 代码无需修改
"""

import sys
import time
import importlib.util
from pathlib import Path
from typing import Optional, List

# ============================================================================
# 导入基类和标准数据结构
# ============================================================================
from adapters.base.range_base import (
    RangeAdapter,
    RangeMeasurement,
    RangeType,
    RangeStatus
)

# 激光雷达代码的绝对路径
# /Users/ronan/Desktop/item/laser_camera/lidar_distance/PythonCode/core/lidar_tof.py
LIDAR_TOF_PATH = Path(__file__).parents[4] / "lidar_distance" / "PythonCode" / "core" / "lidar_tof.py"

# 延迟导入：仅在实际使用时导入，以支持测试模拟
_ToFLidar = None
_SerialException = None


def _import_lidar_classes():
    """延迟导入激光雷达类，支持测试模拟 - 使用绝对路径导入"""
    global _ToFLidar, _SerialException

    if _ToFLidar is not None:
        return _ToFLidar, _SerialException

    try:
        # 使用 importlib 直接从绝对路径导入模块
        spec = importlib.util.spec_from_file_location("lidar_tof_module", LIDAR_TOF_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module spec from {LIDAR_TOF_PATH}")

        lidar_tof_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lidar_tof_module)

        _ToFLidar = lidar_tof_module.ToFLidar
        _SerialException = lidar_tof_module.SerialException

        print(f"[ToFLidarAdapter] Successfully imported ToFLidar from {LIDAR_TOF_PATH}")
        return _ToFLidar, _SerialException
    except Exception as e:
        print(f"[ToFLidarAdapter] ERROR: Cannot import lidar_tof from {LIDAR_TOF_PATH}")
        print(f"[ToFLidarAdapter] Import error: {e}")
        print(f"[ToFLidarAdapter] Please ensure {LIDAR_TOF_PATH} exists")
        raise ImportError(f"Failed to import lidar_tof from {LIDAR_TOF_PATH}") from e


# ============================================================================
# 适配器实现
# ============================================================================

class ToFLidarAdapter(RangeAdapter):
    """
    TOF 激光雷达适配器

    封装您现有的 ToFLidar 类，提供标准化的 RangeMeasurement 输出。

    核心转换：
        lidar.read_measurement() -> (distance_m, strength)
        ↓
        RangeMeasurement(distance_m, confidence, angle_or_sector, timestamp)

    使用示例：
        adapter = ToFLidarAdapter(port="/dev/ttyUSB0")

        try:
            while True:
                measurements = adapter.read_measurement()
                if measurements:
                    for m in measurements:
                        print(f"Distance: {m.distance_m:.2f}m, Confidence: {m.confidence:.2f}")
        finally:
            adapter.close()

    或使用上下文管理器：
        with ToFLidarAdapter(port="/dev/ttyUSB0") as adapter:
            measurements = adapter.read_measurement()
    """

    def __init__(self,
                 port: Optional[str] = None,
                 baudrate: int = 115200,
                 timeout: float = 1.0,
                 strength_normalization_factor: float = 1000.0,
                 max_range_m: float = 10.0):
        """
        初始化激光雷达适配器

        Args:
            port: 串口路径（例如 "/dev/ttyUSB0"、"COM5"，None表示自动检测）
            baudrate: 波特率（您的代码使用 115200）
            timeout: 串口超时（秒）
            strength_normalization_factor: 信号强度归一化因子
                您的激光雷达返回原始强度值，我们除以此因子得到 [0,1] 的置信度
            max_range_m: 最大测量距离（米）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.strength_normalization = strength_normalization_factor
        self._max_range_m = max_range_m
        self._status = RangeStatus.INITIALIZING

        # 延迟导入激光雷达类
        ToFLidar, SerialException = _import_lidar_classes()

        # 初始化您现有的激光雷达对象
        try:
            self.lidar = ToFLidar(port=port, baudrate=baudrate, timeout=timeout)
            self._status = RangeStatus.READY
            print(f"[ToFLidarAdapter] Connected to LiDAR on port {self.lidar.port}")
        except SerialException as e:
            self._status = RangeStatus.ERROR
            print(f"[ToFLidarAdapter] ERROR: Cannot open serial port: {e}")
            raise
        except Exception as e:
            self._status = RangeStatus.ERROR
            print(f"[ToFLidarAdapter] ERROR: Unexpected error during initialization: {e}")
            raise

    def read_measurement(self) -> Optional[List[RangeMeasurement]]:
        """
        从激光雷达读取一次距离测量

        调用您现有代码的 read_measurement() 方法，将返回的
        (distance_m, strength) 元组转换为标准化的 RangeMeasurement 对象。

        Returns:
            包含单个 RangeMeasurement 的列表，如果读取失败返回 None
        """
        if self._status != RangeStatus.READY:
            print(f"[ToFLidarAdapter] WARNING: Sensor not ready (status: {self._status.value})")
            return None

        try:
            # 调用您现有代码的 read_measurement 方法
            # 返回值：Optional[tuple[float, int]] = (distance_m, strength)
            result = self.lidar.read_measurement()

            if result is None:
                return None

            distance_m, strength = result

            # 转换为标准化格式
            # 强度值转换为 [0,1] 的置信度
            confidence = min(strength / self.strength_normalization, 1.0)

            # 创建标准化的测量对象
            measurement = RangeMeasurement(
                distance_m=distance_m,
                confidence=confidence,
                angle_or_sector=None,  # TOF 是单点测距，不是扫描雷达
                timestamp=time.time(),
                signal_strength=strength  # 保留原始强度值供调试使用
            )

            return [measurement]  # 单点传感器返回包含一个元素的列表

        except Exception as e:
            # 检查是否是串口异常（使用类名检查以支持延迟导入）
            if _SerialException and isinstance(e, _SerialException):
                print(f"[ToFLidarAdapter] Serial error reading measurement: {e}")
                self._status = RangeStatus.ERROR
                return None
            else:
                print(f"[ToFLidarAdapter] Unexpected error reading measurement: {e}")
                return None

    def get_range_type(self) -> RangeType:
        """
        获取传感器类型

        Returns:
            RangeType.SINGLE_POINT（TOF 激光雷达是单点测距）
        """
        return RangeType.SINGLE_POINT

    def get_status(self) -> RangeStatus:
        """
        获取传感器当前状态

        Returns:
            当前状态枚举值
        """
        return self._status

    def get_max_range(self) -> float:
        """
        获取传感器最大测量距离

        Returns:
            最大有效距离（米）
        """
        return self._max_range_m

    def close(self) -> None:
        """
        释放串口资源
        """
        if hasattr(self, 'lidar') and self.lidar is not None:
            try:
                self.lidar.close()
                self._status = RangeStatus.STOPPED
                print("[ToFLidarAdapter] LiDAR connection closed")
            except Exception as e:
                print(f"[ToFLidarAdapter] Error closing LiDAR: {e}")

    # 可选的辅助方法

    def get_measurement_rate(self) -> float:
        """
        获取测量频率（估计值）

        TOF 激光雷达通常可以达到 10-20 Hz

        Returns:
            估计的测量频率（Hz）
        """
        return 10.0  # 典型值，实际频率取决于硬件和串口速度


# ============================================================================
# 独立测试/演示
# ============================================================================

def main():
    """
    独立测试程序：验证适配器是否能正常工作

    运行测试：
        cd /Users/ronan/Desktop/item/laser_camera/station_guard/PythonCode
        python -m adapters.legacy.lidar_tof_adapter
    """
    print("=" * 70)
    print("TOF 激光雷达适配器测试")
    print("=" * 70)
    print()

    # 初始化适配器（port=None 表示自动检测）
    print("正在初始化适配器...")
    try:
        adapter = ToFLidarAdapter(port=None)  # 如需指定端口，改为 port="/dev/ttyUSB0"
    except Exception as e:
        print(f"初始化失败: {e}")
        print("\n请检查：")
        print("  1. 激光雷达是否已连接")
        print("  2. 串口权限是否正确（可能需要 sudo）")
        print("  3. 是否有其他程序占用串口")
        return

    print(f"  状态: {adapter.get_status().value}")
    print(f"  类型: {adapter.get_range_type().value}")
    print(f"  最大量程: {adapter.get_max_range():.1f}m")
    print(f"  采样率: {adapter.get_measurement_rate():.1f} Hz")
    print()

    print("读取测量数据（10秒）...")
    print("按 Ctrl+C 可提前停止")
    print()
    print(f"{'序号':>4} {'距离(m)':>10} {'置信度':>8} {'强度':>8} {'时间戳':>12}")
    print("-" * 70)

    start_time = time.time()
    measurement_count = 0
    valid_count = 0

    try:
        while time.time() - start_time < 10.0:
            measurements = adapter.read_measurement()

            if measurements is None:
                print(f"{'':>4} {'[无数据]':>10}")
                time.sleep(0.1)
                continue

            for m in measurements:
                measurement_count += 1

                # 检查测量是否有效
                is_valid = m.is_valid(max_range_m=adapter.get_max_range())
                if is_valid:
                    valid_count += 1

                # 显示测量结果
                status_mark = "✓" if is_valid else "✗"
                print(f"{measurement_count:3d}{status_mark} "
                      f"{m.distance_m:9.3f}m "
                      f"{m.confidence:7.2f} "
                      f"{m.signal_strength:7d} "
                      f"{m.timestamp:11.3f}")

            time.sleep(0.1)  # 10 Hz 采样

    except KeyboardInterrupt:
        print("\n用户中断")

    finally:
        adapter.close()
        print()
        print("-" * 70)
        print(f"测试完成")
        print(f"  总测量次数: {measurement_count}")
        print(f"  有效测量: {valid_count}")
        if measurement_count > 0:
            print(f"  有效率: {100.0 * valid_count / measurement_count:.1f}%")
        print("=" * 70)


if __name__ == "__main__":
    main()
