"""
apps/minimal_demo.py

Minimal working example showing complete pipeline:
Adapters → Projection → Status Classification → Alarm

This demonstrates the architecture with your actual hardware.
Run this to verify the system works end-to-end.
"""

import time
import sys
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parents[1]))


# Import the modules we created
from core.geometry2d import point_in_polygon, distance_to_polygon_edge, point_in_linear_buffer
from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter, RangeMeasurement


# ============================================================================
# Configuration (hardcoded for this minimal demo)
# In full system, this comes from YAML file
# ============================================================================

class DemoConfig:
    """
    Simplified configuration for demo.
    
    This represents a corridor with:
    - 3 cabinets at distances 1.5m, 2.5m, 3.5m
    - Yellow warning line at 4.0m distance
    - Danger zone (high voltage area) at cabinet 3
    """
    
    # Corridor dimensions
    corridor_width_m = 2.0  # 2 meters wide
    corridor_length_m = 6.0  # 6 meters long
    
    # Cabinet zones (polygons on ground plane)
    # Format: [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
    cabinet_zones = {
        1: [(1.3, -0.4), (1.7, -0.4), (1.7, 0.4), (1.3, 0.4)],  # Cabinet 1 at 1.5m
        2: [(2.3, -0.4), (2.7, -0.4), (2.7, 0.4), (2.3, 0.4)],  # Cabinet 2 at 2.5m
        3: [(3.3, -0.4), (3.7, -0.4), (3.7, 0.4), (3.3, 0.4)],  # Cabinet 3 at 3.5m (DANGER)
    }
    
    # Yellow warning line (perpendicular to corridor at 4m distance)
    yellow_line_segment = ((4.0, -1.0), (4.0, 1.0))
    yellow_line_buffer_m = 0.2  # 20cm buffer zone
    
    # Danger zone (cabinet 3 + surrounding area)
    danger_zone = [(3.2, -0.5), (3.8, -0.5), (3.8, 0.5), (3.2, 0.5)]
    danger_distance_threshold_m = 0.3  # Alert if within 30cm of danger zone
    
    # Authorization (in real system, this comes from database)
    authorized_cabinets = {1, 2}  # Person is allowed in cabinets 1 and 2, not 3


# ============================================================================
# Simple status classification (core logic)
# ============================================================================

class PersonStatus(Enum):
    """Five-state classification for safety monitoring."""
    NORMAL = 0          # In authorized area, no violations
    ON_LINE = 1         # Within buffer zone of yellow line
    CROSS_LINE = 2      # Crossed yellow line into forbidden area
    MISPLACED = 3       # In unauthorized cabinet zone
    HIGH_RISK = 4       # In or near danger zone


class AlarmLevel(Enum):
    """Three-color lamp states."""
    GREEN = 0   # All clear
    YELLOW = 1  # Warning
    RED = 2     # Violation


def classify_position(x: float, y: float, person_id: Optional[str] = None) -> PersonStatus:
    """
    Classify a person's position into one of 5 states.
    
    Args:
        x: Longitudinal position (distance along corridor) in meters
        y: Lateral position (width across corridor) in meters
        person_id: Optional person identifier for authorization check
    
    Returns:
        PersonStatus enum indicating classification
    """
    position = (x, y)
    config = DemoConfig
    
    # PRIORITY 1: Check HIGH_RISK (most severe)
    if point_in_polygon(position, config.danger_zone):
        return PersonStatus.HIGH_RISK
    
    dist_to_danger = distance_to_polygon_edge(position, config.danger_zone)
    if 0 < dist_to_danger < config.danger_distance_threshold_m:
        return PersonStatus.HIGH_RISK
    
    # PRIORITY 2: Check CROSS_LINE (crossed into forbidden area)
    # If beyond yellow line and not in any authorized zone
    if x > config.yellow_line_segment[0][0]:  # Past the line
        in_any_zone = False
        for zone_polygon in config.cabinet_zones.values():
            if point_in_polygon(position, zone_polygon):
                in_any_zone = True
                break
        
        if not in_any_zone:
            # Not in buffer and not in any zone = crossed line
            if not point_in_linear_buffer(position, config.yellow_line_segment, 
                                         config.yellow_line_buffer_m):
                return PersonStatus.CROSS_LINE
    
    # PRIORITY 3: Check ON_LINE (in buffer zone)
    if point_in_linear_buffer(position, config.yellow_line_segment, 
                             config.yellow_line_buffer_m):
        return PersonStatus.ON_LINE
    
    # PRIORITY 4: Check MISPLACED (in unauthorized cabinet)
    for cabinet_id, zone_polygon in config.cabinet_zones.items():
        if point_in_polygon(position, zone_polygon):
            if cabinet_id not in config.authorized_cabinets:
                return PersonStatus.MISPLACED
    
    # PRIORITY 5: NORMAL (no violations)
    return PersonStatus.NORMAL


def status_to_alarm(status: PersonStatus) -> AlarmLevel:
    """Convert person status to alarm level (for lamp control)."""
    if status == PersonStatus.NORMAL:
        return AlarmLevel.GREEN
    elif status == PersonStatus.ON_LINE:
        return AlarmLevel.YELLOW
    else:  # CROSS_LINE, MISPLACED, HIGH_RISK
        return AlarmLevel.RED


# ============================================================================
# Main demonstration loop
# ============================================================================

def print_status_report(distance_m: float, status: PersonStatus, alarm: AlarmLevel):
    """Print formatted status report."""
    
    # Color codes for terminal output
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    
    # Choose color based on alarm level
    if alarm == AlarmLevel.GREEN:
        color = GREEN
        lamp = "🟢"
    elif alarm == AlarmLevel.YELLOW:
        color = YELLOW
        lamp = "🟡"
    else:
        color = RED
        lamp = "🔴"
    
    print(f"{color}{lamp} Distance: {distance_m:5.2f}m  |  "
          f"Status: {status.name:12s}  |  "
          f"Alarm: {alarm.name}{RESET}")


def main():
    """
    Main demonstration:
    1. Read distance from LiDAR
    2. Project to ground plane (simplified: distance = x, y = 0)
    3. Classify status
    4. Display alarm state
    """
    
    print("=" * 70)
    print("Station Guard System - Minimal Demo")
    print("=" * 70)
    print()
    print("This demo shows the complete pipeline:")
    print("  1. Read distance from your TOF LiDAR")
    print("  2. Project to ground plane coordinates (x, y)")
    print("  3. Classify person status using zone geometry")
    print("  4. Display alarm level (GREEN/YELLOW/RED)")
    print()
    print("Configuration:")
    print(f"  - Corridor: {DemoConfig.corridor_length_m}m long, {DemoConfig.corridor_width_m}m wide")
    print(f"  - Cabinets: {len(DemoConfig.cabinet_zones)} zones defined")
    print(f"  - Yellow line: {DemoConfig.yellow_line_segment[0][0]}m distance")
    print(f"  - Danger zone: Cabinet 3 area")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()
    
    # Initialize LiDAR adapter
    try:
        lidar = ToFLidarAdapter(port=None)  # Auto-detect port
        print(f"✓ LiDAR connected on port {lidar.port}")
    except Exception as e:
        print(f"✗ ERROR: Cannot connect to LiDAR: {e}")
        print()
        print("TROUBLESHOOTING:")
        print("  1. Check LiDAR is plugged in")
        print("  2. Check serial port permissions")
        print("  3. Try specifying port manually: ToFLidarAdapter(port='/dev/ttyUSB0')")
        return
    
    print()
    print("Reading measurements...")
    print()
    
    measurement_count = 0
    last_status = None
    last_alarm = None
    
    try:
        while True:
            # Step 1: Read from LiDAR adapter
            measurements = lidar.read_measurement()
            
            if measurements is None:
                print("  [Waiting for measurement...]")
                time.sleep(0.1)
                continue
            
            measurement = measurements[0]  # Single-point LiDAR
            distance_m = measurement.distance_m
            confidence = measurement.confidence
            
            # Step 2: Project to ground plane
            # Simplified: assume person is at distance x, centered at y=0
            # In full system, we'd use camera to get lateral position y
            x = distance_m
            y = 0.0  # Centered in corridor (we'd get this from vision)
            
            # Step 3: Classify status
            status = classify_position(x, y)
            
            # Step 4: Determine alarm level
            alarm = status_to_alarm(status)
            
            # Print status (only when it changes to reduce clutter)
            if status != last_status or alarm != last_alarm:
                print_status_report(distance_m, status, alarm)
                last_status = status
                last_alarm = alarm
            
            measurement_count += 1
            time.sleep(0.1)  # 10 Hz
    
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 70)
        print(f"Demo stopped. Processed {measurement_count} measurements.")
    
    finally:
        lidar.close()
        print("LiDAR connection closed.")
        print("=" * 70)


if __name__ == "__main__":
    main()