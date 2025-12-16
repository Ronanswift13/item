"""
adapters/base/range_base.py

测距传感器适配器抽象基类定义

支持各种测距传感器：
- 单点激光雷达（TOF、超声波）
- 扫描激光雷达（2D LiDAR）
- 深度相机（RealSense、Kinect等）

核心设计原则：
1. 适配器负责硬件访问和距离测量
2. 输出标准化的 RangeMeasurement 数据结构
3. 内核不需要知道具体的传感器类型
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
import time


@dataclass
class RangeMeasurement:
    """
    单次测距结果的标准化表示
    
    这是测距传感器与系统核心之间的数据契约。
    无论底层是激光雷达、超声波、还是深度相机，都必须转换为此格式。
    
    Attributes:
        distance_m: 距离测量值（米）
        confidence: 测量置信度 [0.0, 1.0]
        angle_or_sector: 测量角度（度）或扇区ID
                        - 单点传感器：None
                        - 扫描雷达：角度值（0-360度）
                        - 多区域传感器：扇区编号
        timestamp: 测量时间戳（Unix时间，秒）
        signal_strength: 可选的信号强度（原始值，范围取决于传感器）
    """
    distance_m: float
    confidence: float
    angle_or_sector: Optional[float]
    timestamp: float
    signal_strength: Optional[int] = None
    
    def is_valid(self, max_range_m: float = 10.0) -> bool:
        """
        检查测量是否有效
        
        Args:
            max_range_m: 最大有效距离（米）
        
        Returns:
            True if 测量有效且在合理范围内
        """
        return (
            self.confidence > 0.0 and
            0.0 < self.distance_m <= max_range_m and
            self.timestamp > 0
        )


class RangeType(Enum):
    """测距传感器类型"""
    SINGLE_POINT = "single_point"  # 单点测距（TOF激光、超声波）
    SCANNING_1D = "scanning_1d"    # 一维扫描（2D激光雷达）
    DEPTH_IMAGE = "depth_image"    # 深度图像（深度相机）


class RangeStatus(Enum):
    """测距传感器运行状态"""
    READY = "ready"
    INITIALIZING = "initializing"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    STOPPED = "stopped"


class RangeAdapter(ABC):
    """
    测距传感器适配器抽象基类
    
    所有具体的测距实现（ToFLidarAdapter, DepthCameraAdapter等）
    必须继承此类并实现所有抽象方法。
    
    使用示例：
        lidar = ToFLidarAdapter(port="/dev/ttyUSB0")
        
        try:
            while True:
                measurements = lidar.read_measurement()
                if measurements:
                    for m in measurements:
                        print(f"Distance: {m.distance_m:.2f}m, Confidence: {m.confidence:.2f}")
        finally:
            lidar.close()
    """
    
    @abstractmethod
    def read_measurement(self) -> Optional[List[RangeMeasurement]]:
        """
        读取一次距离测量
        
        此方法应该：
        1. 从传感器获取原始数据
        2. 转换为标准化的距离单位（米）
        3. 计算或提取置信度
        4. 返回标准化的 RangeMeasurement 列表
        
        Returns:
            测量结果列表，如果读取失败返回 None
            - 单点传感器：列表包含一个元素
            - 扫描雷达：列表包含多个元素（每个角度一个）
            - 深度相机：列表包含关键点或平均值
        
        注意：
            - 此方法应该是非阻塞的或有合理的超时
            - 无效测量应该被过滤掉，不包含在返回列表中
        """
        pass
    
    @abstractmethod
    def get_range_type(self) -> RangeType:
        """
        获取传感器类型
        
        Returns:
            RangeType 枚举值
        """
        pass
    
    @abstractmethod
    def get_status(self) -> RangeStatus:
        """
        获取传感器当前状态
        
        Returns:
            RangeStatus 枚举值
        """
        pass
    
    @abstractmethod
    def get_max_range(self) -> float:
        """
        获取传感器最大测量距离
        
        Returns:
            最大有效距离（米）
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """
        释放传感器资源
        
        应该释放：
        - 串口或USB设备句柄
        - 网络连接
        - 内存缓冲区
        """
        pass
    
    # 可选方法：高级功能
    
    def get_measurement_rate(self) -> float:
        """
        获取测量频率
        
        Returns:
            测量频率（Hz），如果无法计算返回 0.0
        """
        return 0.0
    
    def set_measurement_range(self, min_m: float, max_m: float) -> bool:
        """
        设置测量范围（如果传感器支持）
        
        Args:
            min_m: 最小距离（米）
            max_m: 最大距离（米）
        
        Returns:
            True if 设置成功，False if 不支持或失败
        """
        return False
    
    def calibrate(self, known_distance_m: float) -> bool:
        """
        使用已知距离进行校准（如果传感器支持）
        
        Args:
            known_distance_m: 已知的实际距离（米）
        
        Returns:
            True if 校准成功，False if 不支持或失败
        """
        return False
    
    def __enter__(self):
        """支持上下文管理器协议"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.close()


# 工具函数

def validate_measurement(measurement: RangeMeasurement,
                        max_range_m: float = 10.0,
                        min_confidence: float = 0.1) -> tuple[bool, str]:
    """
    验证测距结果的有效性
    
    Args:
        measurement: 待验证的测量结果
        max_range_m: 最大有效距离（米）
        min_confidence: 最低置信度阈值
    
    Returns:
        (is_valid, error_message)
    """
    # 检查置信度
    if not (0.0 <= measurement.confidence <= 1.0):
        return False, f"Invalid confidence: {measurement.confidence}"
    
    if measurement.confidence < min_confidence:
        return False, f"Confidence too low: {measurement.confidence:.2f} < {min_confidence:.2f}"
    
    # 检查距离范围
    if measurement.distance_m <= 0:
        return False, f"Invalid distance: {measurement.distance_m}"
    
    if measurement.distance_m > max_range_m:
        return False, f"Distance exceeds max range: {measurement.distance_m:.2f}m > {max_range_m:.2f}m"
    
    # 检查时间戳
    if measurement.timestamp <= 0:
        return False, f"Invalid timestamp: {measurement.timestamp}"
    
    # 检查时间戳是否过期（超过5秒认为是旧数据）
    current_time = time.time()
    if abs(current_time - measurement.timestamp) > 5.0:
        return False, f"Measurement too old: {current_time - measurement.timestamp:.1f}s"
    
    return True, ""


def filter_valid_measurements(measurements: List[RangeMeasurement],
                              max_range_m: float = 10.0,
                              min_confidence: float = 0.1) -> List[RangeMeasurement]:
    """
    过滤有效的测量结果
    
    Args:
        measurements: 原始测量列表
        max_range_m: 最大有效距离
        min_confidence: 最低置信度阈值
    
    Returns:
        过滤后的有效测量列表
    """
    valid_measurements = []
    for m in measurements:
        is_valid, _ = validate_measurement(m, max_range_m, min_confidence)
        if is_valid:
            valid_measurements.append(m)
    return valid_measurements


def compute_average_distance(measurements: List[RangeMeasurement],
                            weight_by_confidence: bool = True) -> Optional[float]:
    """
    计算平均距离（用于多点测量）
    
    Args:
        measurements: 测量列表
        weight_by_confidence: 是否使用置信度加权
    
    Returns:
        平均距离（米），如果列表为空返回 None
    """
    if not measurements:
        return None
    
    if weight_by_confidence:
        total_weighted = sum(m.distance_m * m.confidence for m in measurements)
        total_weight = sum(m.confidence for m in measurements)
        if total_weight > 0:
            return total_weighted / total_weight
        else:
            return None
    else:
        return sum(m.distance_m for m in measurements) / len(measurements)


def find_closest_measurement(measurements: List[RangeMeasurement]) -> Optional[RangeMeasurement]:
    """
    找到最近的测量点
    
    Args:
        measurements: 测量列表
    
    Returns:
        距离最近的测量，如果列表为空返回 None
    """
    if not measurements:
        return None
    
    return min(measurements, key=lambda m: m.distance_m)


class MovingAverageFilter:
    """
    移动平均滤波器（用于平滑距离测量）
    
    适用于单点传感器的噪声抑制。
    
    使用示例：
        filter = MovingAverageFilter(window_size=5)
        
        while True:
            raw_distance = lidar.read_distance()
            smoothed_distance = filter.update(raw_distance)
    """
    
    def __init__(self, window_size: int = 5):
        """
        初始化滤波器
        
        Args:
            window_size: 滑动窗口大小
        """
        self.window_size = window_size
        self.buffer = []
    
    def update(self, value: float) -> float:
        """
        添加新值并返回平均值
        
        Args:
            value: 新的距离测量值
        
        Returns:
            平滑后的距离值
        """
        self.buffer.append(value)
        
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)
        
        return sum(self.buffer) / len(self.buffer)
    
    def reset(self) -> None:
        """清空缓冲区"""
        self.buffer.clear()
    
    def is_full(self) -> bool:
        """检查缓冲区是否已满"""
        return len(self.buffer) >= self.window_size


if __name__ == "__main__":
    # 模块自检
    print("=" * 60)
    print("Range Adapter Base - 模块自检")
    print("=" * 60)
    
    # 测试数据结构
    print("\n测试 RangeMeasurement 数据类:")
    m1 = RangeMeasurement(
        distance_m=2.5,
        confidence=0.95,
        angle_or_sector=None,
        timestamp=time.time(),
        signal_strength=850
    )
    print(f"  Distance: {m1.distance_m:.2f}m")
    print(f"  Confidence: {m1.confidence:.2f}")
    print(f"  Valid: {m1.is_valid()}")
    
    # 测试验证函数
    print("\n测试测量验证:")
    is_valid, msg = validate_measurement(m1)
    print(f"  Valid: {is_valid}")
    if not is_valid:
        print(f"  Error: {msg}")
    
    # 测试平均计算
    print("\n测试多点平均:")
    measurements = [
        RangeMeasurement(2.0, 0.9, None, time.time()),
        RangeMeasurement(2.5, 0.8, None, time.time()),
        RangeMeasurement(2.3, 0.95, None, time.time()),
    ]
    avg_simple = compute_average_distance(measurements, weight_by_confidence=False)
    avg_weighted = compute_average_distance(measurements, weight_by_confidence=True)
    print(f"  简单平均: {avg_simple:.2f}m")
    print(f"  加权平均: {avg_weighted:.2f}m")
    
    # 测试移动平均滤波器
    print("\n测试移动平均滤波器:")
    filter = MovingAverageFilter(window_size=3)
    test_values = [2.0, 2.5, 2.3, 2.4, 2.2]
    print(f"  窗口大小: {filter.window_size}")
    for v in test_values:
        smoothed = filter.update(v)
        print(f"  输入: {v:.2f}m -> 输出: {smoothed:.2f}m")
    
    print("\n" + "=" * 60)
    print("所有自检完成")