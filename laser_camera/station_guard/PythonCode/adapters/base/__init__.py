"""
adapters/base/__init__.py

适配器基类包 - 统一导出所有硬件接口定义

此包定义了系统与硬件之间的契约。
所有传感器适配器实现必须遵循这些接口。
"""

from .camera_base import (
    CameraDetection,
    CameraStatus,
    CameraAdapter,
    validate_detection,
    compute_footpoint_from_bbox
)

from .range_base import (
    RangeMeasurement,
    RangeType,
    RangeStatus,
    RangeAdapter,
    validate_measurement,
    filter_valid_measurements,
    compute_average_distance,
    find_closest_measurement,
    MovingAverageFilter
)

from .lamp_base import (
    AlarmLevel,
    LampStatus,
    LampAdapter,
    VirtualLampAdapter,
    AlarmLevelAggregator
)

__all__ = [
    # 相机适配器
    'CameraDetection',
    'CameraStatus',
    'CameraAdapter',
    'validate_detection',
    'compute_footpoint_from_bbox',
    
    # 测距适配器
    'RangeMeasurement',
    'RangeType',
    'RangeStatus',
    'RangeAdapter',
    'validate_measurement',
    'filter_valid_measurements',
    'compute_average_distance',
    'find_closest_measurement',
    'MovingAverageFilter',
    
    # 灯光适配器
    'AlarmLevel',
    'LampStatus',
    'LampAdapter',
    'VirtualLampAdapter',
    'AlarmLevelAggregator',
]