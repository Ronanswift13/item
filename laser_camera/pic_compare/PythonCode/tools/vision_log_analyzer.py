#!/usr/bin/env python3
"""
Simple analysis tool for vision_line_log.csv produced by the vision demos.

Directory layout (relative to this file):

  canmv/
    core/
    data/
      vision_line_log.csv
    demo/
    tools/
      vision_log_analyzer.py   <-- this file

Run from project root with:
  cd pic_compare/PythonCode/canmv
  python tools/vision_log_analyzer.py
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Resolve log path relative to this file
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # PythonCode/

DEFAULT_LOG = PROJECT_ROOT / "data" / "vision_line_log.csv"


@dataclass
class LogStats:
    total_frames: int
    zone_counts: Counter
    state_counts: Counter
    safe_counts: Counter
    line_zone_field: str
    line_state_field: str
    safe_field: str


def _detect_field_name(row: dict, candidates: list[str]) -> Optional[str]:
    """
    Pick the first existing field from candidates.
    Returns None if none of them exists.
    """
    for name in candidates:
        if name in row:
            return name
    return None


def load_log(path: Path = DEFAULT_LOG) -> list[dict]:
    if not path.exists():
        print(f"[ERROR] vision log not found: {path}")
        return []

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"[WARN] vision log is empty: {path}")
        return []

    return rows


def compute_stats(rows: list[dict]) -> LogStats:
    # Try to be tolerant to slightly different column names
    sample = rows[0]

    line_zone_field = _detect_field_name(sample, ["line_zone", "zone"])
    line_state_field = _detect_field_name(sample, ["line_state", "state"])
    safe_field = _detect_field_name(sample, ["safe", "is_safe"])

    if line_zone_field is None or line_state_field is None or safe_field is None:
        raise RuntimeError(
            f"Could not detect expected fields in CSV header. "
            f"Got columns: {list(sample.keys())}"
        )

    zone_counts: Counter = Counter()
    state_counts: Counter = Counter()
    safe_counts: Counter = Counter()

    for row in rows:
        zone = row.get(line_zone_field, "").strip()
        state = row.get(line_state_field, "").strip()
        safe_raw = row.get(safe_field, "").strip()

        # Normalise safe value to 'True' / 'False'
        safe_norm = safe_raw
        if safe_raw.lower() in ("1", "true", "yes"):
            safe_norm = "True"
        elif safe_raw.lower() in ("0", "false", "no"):
            safe_norm = "False"

        zone_counts[zone] += 1
        state_counts[state] += 1
        safe_counts[safe_norm] += 1

    return LogStats(
        total_frames=len(rows),
        zone_counts=zone_counts,
        state_counts=state_counts,
        safe_counts=safe_counts,
        line_zone_field=line_zone_field,
        line_state_field=line_state_field,
        safe_field=safe_field,
    )


def estimate_crossings(rows: list[dict], zone_field: str) -> int:
    """
    Roughly estimate how many times the operator crossed into the danger zone,
    based on changes of line_zone.
    """
    prev_zone: Optional[str] = None
    crossings = 0

    for row in rows:
        zone = row.get(zone_field, "").strip()
        # You can adjust the definition of "danger zone" here if needed
        in_danger = zone.upper().startswith("INSIDE") or zone.upper() == "DANGER"
        prev_in_danger = (
            prev_zone is not None
            and (prev_zone.upper().startswith("INSIDE") or prev_zone.upper() == "DANGER")
        )

        if in_danger and not prev_in_danger and prev_zone is not None:
            crossings += 1

        prev_zone = zone

    return crossings


def print_report(path: Path, stats: LogStats, rows: list[dict]) -> None:
    print("=== Vision line log analysis ===")
    print(f"Log file      : {path}")
    print(f"Total frames  : {stats.total_frames}")
    print()

    def _print_counter(title: str, counter: Counter) -> None:
        print(title)
        total = stats.total_frames or 1
        for key, count in counter.items():
            pct = 100.0 * count / total
            print(f"  {key or '(empty)':<20} {count:6d}  ({pct:5.1f}%)")
        print()

    _print_counter("By line_zone:", stats.zone_counts)
    _print_counter("By line_state:", stats.state_counts)
    _print_counter("By safe flag:", stats.safe_counts)

    crossings = estimate_crossings(rows, stats.line_zone_field)
    print(f"Estimated danger crossings: {crossings}")
    print()
    print("Tip: if some fields look wrong, check the CSV header and, if needed,")
    print("     adjust field name candidates in vision_log_analyzer.py.")
    print()


def main() -> None:
    log_path = DEFAULT_LOG
    rows = load_log(log_path)
    if not rows:
        return

    stats = compute_stats(rows)
    print_report(log_path, stats, rows)


if __name__ == "__main__":
    main()
