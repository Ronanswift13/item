"""
core/geometry2d.py

Pure mathematical geometry functions for 2D ground plane analysis.
These functions form the "ground truth" for all safety decisions.

All coordinates are in meters on the ground plane (world coordinates).
No dependencies on sensors, configuration, or UI.
"""

import math
from typing import List, Tuple, Optional

Point = Tuple[float, float]
Polygon = List[Point]
LineSegment = Tuple[Point, Point]


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """
    Determine if a point is inside a polygon using ray-casting algorithm.
    
    Args:
        point: (x, y) coordinates in meters
        polygon: List of (x, y) vertices ordered clockwise or counterclockwise
    
    Returns:
        True if point is inside or on boundary, False otherwise
    
    Algorithm:
        Cast a ray from the point to infinity and count intersections with edges.
        Odd count = inside, even count = outside.
    """
    if len(polygon) < 3:
        return False
    
    x, y = point
    num_vertices = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    
    for i in range(1, num_vertices + 1):
        p2x, p2y = polygon[i % num_vertices]
        
        # Check if point is on horizontal edge
        if y == p1y == p2y:
            if min(p1x, p2x) <= x <= max(p1x, p2x):
                return True
        
        # Check if ray crosses edge
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        x_intersection = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    
                    if p1x == p2x or x <= x_intersection:
                        inside = not inside
        
        p1x, p1y = p2x, p2y
    
    return inside


def distance_to_point(p1: Point, p2: Point) -> float:
    """Euclidean distance between two points."""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def distance_point_to_segment(point: Point, segment: LineSegment) -> float:
    """
    Calculate minimum distance from a point to a line segment.
    
    Args:
        point: (x, y) coordinates
        segment: ((x1, y1), (x2, y2)) line segment endpoints
    
    Returns:
        Minimum distance in meters
    """
    px, py = point
    (x1, y1), (x2, y2) = segment
    
    # Vector from p1 to p2
    dx = x2 - x1
    dy = y2 - y1
    
    # Handle degenerate case (segment is a point)
    if dx == 0 and dy == 0:
        return distance_to_point(point, (x1, y1))
    
    # Parameter t represents projection of point onto line
    # t = 0 means closest to p1, t = 1 means closest to p2
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    
    # Clamp t to [0, 1] to stay within segment
    t = max(0, min(1, t))
    
    # Find closest point on segment
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return distance_to_point(point, (closest_x, closest_y))


def distance_to_polygon_edge(point: Point, polygon: Polygon) -> float:
    """
    Calculate minimum distance from a point to any edge of a polygon.
    
    Args:
        point: (x, y) coordinates
        polygon: List of vertices
    
    Returns:
        Minimum distance in meters (0 if point is on edge, negative if inside)
    """
    if len(polygon) < 2:
        return float('inf')
    
    min_distance = float('inf')
    
    for i in range(len(polygon)):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % len(polygon)]
        segment = (p1, p2)
        dist = distance_point_to_segment(point, segment)
        min_distance = min(min_distance, dist)
    
    # If point is inside polygon, return negative distance
    if point_in_polygon(point, polygon):
        return -min_distance
    
    return min_distance


def point_in_linear_buffer(point: Point, line_segment: LineSegment, 
                           buffer_width: float) -> bool:
    """
    Check if a point is within a rectangular buffer zone along a line segment.
    
    This is used for "yellow line" warning zones where we want to detect
    if someone is close to crossing a boundary.
    
    Args:
        point: (x, y) coordinates
        line_segment: ((x1, y1), (x2, y2)) line segment endpoints
        buffer_width: Width of buffer zone on each side of line (meters)
    
    Returns:
        True if point is within buffer zone, False otherwise
    """
    distance = distance_point_to_segment(point, line_segment)
    return distance <= buffer_width


def line_segments_intersect(seg1: LineSegment, seg2: LineSegment) -> bool:
    """
    Check if two line segments intersect.
    
    Useful for detecting line crossings (e.g., person trajectory crosses boundary).
    
    Args:
        seg1: ((x1, y1), (x2, y2)) first segment
        seg2: ((x3, y3), (x4, y4)) second segment
    
    Returns:
        True if segments intersect, False otherwise
    """
    (x1, y1), (x2, y2) = seg1
    (x3, y3), (x4, y4) = seg2
    
    # Calculate denominators for parametric line equations
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    # Parallel or coincident lines
    if abs(denom) < 1e-10:
        return False
    
    # Calculate intersection parameters
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    
    # Check if intersection is within both segments
    return 0 <= t <= 1 and 0 <= u <= 1


def polygon_area(polygon: Polygon) -> float:
    """
    Calculate area of a polygon using shoelace formula.
    
    Useful for validating polygon definitions and detecting degenerate cases.
    """
    if len(polygon) < 3:
        return 0.0
    
    area = 0.0
    for i in range(len(polygon)):
        j = (i + 1) % len(polygon)
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    
    return abs(area) / 2.0


def polygon_centroid(polygon: Polygon) -> Point:
    """
    Calculate centroid (geometric center) of a polygon.
    
    Useful for displaying zone labels or computing representative points.
    """
    if len(polygon) < 3:
        return (0.0, 0.0)
    
    area = polygon_area(polygon)
    if area == 0:
        # Degenerate polygon, return average of vertices
        x_sum = sum(p[0] for p in polygon)
        y_sum = sum(p[1] for p in polygon)
        return (x_sum / len(polygon), y_sum / len(polygon))
    
    cx = 0.0
    cy = 0.0
    
    for i in range(len(polygon)):
        j = (i + 1) % len(polygon)
        factor = polygon[i][0] * polygon[j][1] - polygon[j][0] * polygon[i][1]
        cx += (polygon[i][0] + polygon[j][0]) * factor
        cy += (polygon[i][1] + polygon[j][1]) * factor
    
    area_factor = 6.0 * area
    return (cx / area_factor, cy / area_factor)


def expand_polygon(polygon: Polygon, distance: float) -> Polygon:
    """
    Expand (or shrink if distance is negative) a polygon by moving each edge
    outward by the specified distance.
    
    This is a simplified version that works for convex polygons and
    small expansions. For complex cases, use a proper offsetting algorithm.
    
    Args:
        polygon: List of vertices
        distance: Distance to expand (positive) or shrink (negative) in meters
    
    Returns:
        New polygon with expanded boundaries
    """
    if len(polygon) < 3:
        return polygon
    
    # Calculate centroid to determine inward/outward direction
    cx, cy = polygon_centroid(polygon)
    
    expanded = []
    for px, py in polygon:
        # Vector from centroid to vertex
        dx = px - cx
        dy = py - cy
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 1e-10:
            expanded.append((px, py))
            continue
        
        # Normalize and scale by distance
        dx = dx / length * distance
        dy = dy / length * distance
        
        expanded.append((px + dx, py + dy))
    
    return expanded


# ==============================================================================
# Validation and Debugging Utilities
# ==============================================================================

def validate_polygon(polygon: Polygon) -> Tuple[bool, str]:
    """
    Check if a polygon definition is valid.
    
    Returns:
        (is_valid, error_message)
    """
    if len(polygon) < 3:
        return False, f"Polygon must have at least 3 vertices, got {len(polygon)}"
    
    area = polygon_area(polygon)
    if area < 1e-6:
        return False, f"Polygon has near-zero area ({area:.6f} m²), may be degenerate"
    
    # Check for self-intersection (simplified check)
    for i in range(len(polygon)):
        seg1 = (polygon[i], polygon[(i + 1) % len(polygon)])
        for j in range(i + 2, len(polygon)):
            if j == len(polygon) - 1 and i == 0:
                continue  # Skip adjacent edges
            seg2 = (polygon[j], polygon[(j + 1) % len(polygon)])
            if line_segments_intersect(seg1, seg2):
                return False, f"Polygon has self-intersection between edges {i} and {j}"
    
    return True, ""


if __name__ == "__main__":
    # Quick self-test when run as standalone module
    print("Geometry2D Module Self-Test")
    print("=" * 50)
    
    # Test polygon
    square = [(0, 0), (0, 1), (1, 1), (1, 0)]
    
    # Test point-in-polygon
    print("\nTest 1: Point-in-polygon")
    print(f"  (0.5, 0.5) in square: {point_in_polygon((0.5, 0.5), square)}")  # True
    print(f"  (1.5, 0.5) in square: {point_in_polygon((1.5, 0.5), square)}")  # False
    
    # Test distance to edge
    print("\nTest 2: Distance to edge")
    print(f"  (0.5, 0.5) to square edge: {distance_to_polygon_edge((0.5, 0.5), square):.3f}m")
    print(f"  (1.5, 0.5) to square edge: {distance_to_polygon_edge((1.5, 0.5), square):.3f}m")
    
    # Test buffer zone
    print("\nTest 3: Buffer zone")
    line = ((0, 0), (1, 0))
    print(f"  (0.5, 0.1) in 0.2m buffer: {point_in_linear_buffer((0.5, 0.1), line, 0.2)}")
    print(f"  (0.5, 0.3) in 0.2m buffer: {point_in_linear_buffer((0.5, 0.3), line, 0.2)}")
    
    # Test validation
    print("\nTest 4: Polygon validation")
    valid, msg = validate_polygon(square)
    print(f"  Square valid: {valid}")
    
    print("\n" + "=" * 50)
    print("All tests completed. Review results above.")