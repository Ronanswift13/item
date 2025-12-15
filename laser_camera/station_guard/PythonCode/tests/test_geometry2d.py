"""
geometry2d 模块单元测试

测试所有几何计算函数的正确性，这是整个系统的数学基础。
"""

import pytest
import sys
from pathlib import Path

# 添加父目录到路径以便导入模块
sys.path.insert(0, str(Path(__file__).parents[1]))

from core.geometry2d import (
    point_in_polygon,
    distance_to_point,
    distance_point_to_segment,
    distance_to_polygon_edge,
    point_in_linear_buffer,
    validate_polygon
)


class TestPointInPolygon:
    """测试点在多边形内判定"""
    
    def test_point_inside_square(self):
        """测试点在正方形内部"""
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        assert point_in_polygon((0.5, 0.5), square) == True
    
    def test_point_outside_square(self):
        """测试点在正方形外部"""
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        assert point_in_polygon((1.5, 0.5), square) == False
    
    def test_point_on_vertex(self):
        """测试点在顶点上"""
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        # 顶点应该被认为是在内部
        assert point_in_polygon((0, 0), square) == True
    
    def test_point_on_edge(self):
        """测试点在边上"""
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        # 边上的点应该被认为是在内部
        assert point_in_polygon((0.5, 0), square) == True
    
    def test_concave_polygon(self):
        """测试凹多边形"""
        # L形凹多边形
        l_shape = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
        assert point_in_polygon((0.5, 0.5), l_shape) == True
        assert point_in_polygon((1.5, 1.5), l_shape) == False


class TestDistanceCalculations:
    """测试距离计算"""
    
    def test_distance_between_points(self):
        """测试两点距离"""
        assert distance_to_point((0, 0), (3, 4)) == 5.0
        assert distance_to_point((1, 1), (1, 1)) == 0.0
    
    def test_distance_point_to_segment(self):
        """测试点到线段距离"""
        # 点在线段垂直方向
        segment = ((0, 0), (1, 0))
        assert abs(distance_point_to_segment((0.5, 1), segment) - 1.0) < 0.001
        
        # 点的投影在线段延长线上
        assert abs(distance_point_to_segment((2, 1), segment) - 1.414) < 0.01
    
    def test_distance_to_polygon_edge_inside(self):
        """测试内部点到多边形边界距离（应为负）"""
        square = [(0, 0), (0, 2), (2, 2), (2, 0)]
        # 中心点距离最近边界1米
        dist = distance_to_polygon_edge((1, 1), square)
        assert dist < 0  # 内部点距离为负
        assert abs(dist) == pytest.approx(1.0, rel=0.01)
    
    def test_distance_to_polygon_edge_outside(self):
        """测试外部点到多边形边界距离（应为正）"""
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        dist = distance_to_polygon_edge((2, 0.5), square)
        assert dist > 0
        assert dist == pytest.approx(1.0, rel=0.01)


class TestLinearBuffer:
    """测试线性缓冲区检测"""
    
    def test_point_in_buffer(self):
        """测试点在缓冲区内"""
        line = ((0, 0), (1, 0))
        buffer_width = 0.2
        
        # 线段上方0.1米的点应该在缓冲区内
        assert point_in_linear_buffer((0.5, 0.1), line, buffer_width) == True
        
        # 线段下方0.1米的点应该在缓冲区内
        assert point_in_linear_buffer((0.5, -0.1), line, buffer_width) == True
    
    def test_point_outside_buffer(self):
        """测试点在缓冲区外"""
        line = ((0, 0), (1, 0))
        buffer_width = 0.2
        
        # 线段上方0.3米的点应该在缓冲区外
        assert point_in_linear_buffer((0.5, 0.3), line, buffer_width) == False


class TestPolygonValidation:
    """测试多边形验证"""
    
    def test_valid_triangle(self):
        """测试有效三角形"""
        triangle = [(0, 0), (1, 0), (0.5, 1)]
        is_valid, msg = validate_polygon(triangle)
        assert is_valid == True
    
    def test_invalid_two_points(self):
        """测试无效多边形（只有两个点）"""
        invalid = [(0, 0), (1, 1)]
        is_valid, msg = validate_polygon(invalid)
        assert is_valid == False
        assert "at least 3 vertices" in msg
    
    def test_degenerate_polygon(self):
        """测试退化多边形（面积为零）"""
        # 三点共线
        degenerate = [(0, 0), (1, 0), (2, 0)]
        is_valid, msg = validate_polygon(degenerate)
        assert is_valid == False


class TestRealWorldScenarios:
    """测试实际场景"""
    
    def test_cabinet_zone_detection(self):
        """测试机柜区域检测（模拟实际配置）"""
        # 模拟1号机柜区域
        cabinet_1 = [(1.8, -0.4), (2.2, -0.4), (2.2, 0.4), (1.8, 0.4)]
        
        # 机柜中心位置应该在区域内
        assert point_in_polygon((2.0, 0.0), cabinet_1) == True
        
        # 机柜外侧应该不在区域内
        assert point_in_polygon((1.5, 0.0), cabinet_1) == False
        assert point_in_polygon((2.5, 0.0), cabinet_1) == False
    
    def test_yellow_line_buffer(self):
        """测试黄线缓冲区（模拟实际配置）"""
        # 黄线位于4.0米处，纵向穿过走廊
        yellow_line = ((4.0, -1.0), (4.0, 1.0))
        buffer = 0.2
        
        # 距离黄线0.1米应该触发ON_LINE警告
        assert point_in_linear_buffer((3.9, 0.0), yellow_line, buffer) == True
        assert point_in_linear_buffer((4.1, 0.0), yellow_line, buffer) == True
        
        # 距离黄线0.3米应该不在缓冲区
        assert point_in_linear_buffer((3.7, 0.0), yellow_line, buffer) == False
        assert point_in_linear_buffer((4.3, 0.0), yellow_line, buffer) == False


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v"])