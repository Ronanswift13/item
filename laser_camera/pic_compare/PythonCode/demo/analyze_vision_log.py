from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


# ------------------------------------------------------
# 1) Fix sys.path BEFORE any "from core.xxx import ..."
#    (even though this script doesn't import core,
#     we keep the same pattern for consistency)
# ------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # go up to PythonCode
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# PythonCode as root
ROOT_DIR = project_root
DATA_DIR = ROOT_DIR / "data"
LOG_PATH = DATA_DIR / "vision_log.csv"


def analyze_vision_log() -> None:
    if not LOG_PATH.exists():
        print(f"[ERROR] vision_log.csv not found at: {LOG_PATH}")
        print("Please run demo_vision_safety_log.py first to generate some data.")
        return

    total_records = 0
    level_counter: Counter[str] = Counter()
    zone_counter: Counter[str] = Counter()

    with LOG_PATH.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            total_records += 1
            level = row.get("safety_level", "UNKNOWN")
            zone = row.get("zone", "UNKNOWN")
            level_counter[level] += 1
            zone_counter[zone] += 1

    if total_records == 0:
        print("[INFO] vision_log.csv is empty.")
        return

    print("=== Vision Safety Log Analysis ===")
    print(f"Log path     : {LOG_PATH}")
    print(f"Total records: {total_records}")
    print()

    print("Safety level distribution:")
    for level, count in level_counter.most_common():
        pct = 100.0 * count / total_records
        print(f"  - {level:10s}: {count:5d}  ({pct:5.1f}%)")

    print()
    print("Zone distribution:")
    for zone, count in zone_counter.most_common():
        pct = 100.0 * count / total_records
        print(f"  - {zone:12s}: {count:5d}  ({pct:5.1f}%)")


if __name__ == "__main__":
    analyze_vision_log()
