# core/__init__.py
"""核心算法模块（硬件无关）"""

from .geometry2d import (
    point_in_polygon,
    distance_to_polygon_edge,
    point_in_linear_buffer,
    validate_polygon
)

__all__ = [
    'point_in_polygon',
    'distance_to_polygon_edge', 
    'point_in_linear_buffer',
    'validate_polygon'
]