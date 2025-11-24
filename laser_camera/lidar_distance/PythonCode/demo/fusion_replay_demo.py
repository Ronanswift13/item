from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from typing import List, Dict


def replay_fusion_log(csv_path: str, speed: float = 1.0) -> None:
    with open(csv_path, "r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        rows: List[Dict[str, str]] = list(reader)

    if not rows:
        print("[fusion_replay_demo] No data rows found.")
        return

    parsed_rows = []
    for row in rows:
        timestamp_str = row.get("timestamp_iso")
        try:
            ts = datetime.fromisoformat(timestamp_str) if timestamp_str else None
        except Exception:
            ts = None
        parsed_rows.append((ts, row))

    for idx, (current_ts, row) in enumerate(parsed_rows):
        distance_str = row.get("distance_cm") or "None"
        try:
            distance_val = float(distance_str)
            distance_formatted = f"{distance_val:.1f}"
        except (ValueError, TypeError):
            distance_val = None
            distance_formatted = "None"

        line = row.get("line_position", "?")
        orient = row.get("orientation", "?")
        gesture = row.get("gesture", "?")
        too_close = row.get("too_close", "False")
        warning = row.get("warning_level", "?")
        person_present = row.get("person_present", "False")

        timestamp_display = current_ts.strftime("%Y-%m-%d %H:%M:%S") if current_ts else row.get("timestamp_iso", "?")

        print(
            f"[replay] t={timestamp_display} | dist={distance_formatted} cm | "
            f"too_close={too_close} | warning={warning} | "
            f"person_present={person_present} | line={line} | orient={orient}"
        )

        if idx + 1 < len(parsed_rows):
            next_ts = parsed_rows[idx + 1][0]
            if current_ts and next_ts:
                dt = (next_ts - current_ts).total_seconds() / speed if speed > 0 else 0.0
                if dt < 0:
                    dt = 0.0
            else:
                dt = 0.0
            time.sleep(dt)


def run_replay_demo(csv_path: str = "fusion_log.csv", speed: float = 1.0) -> None:
    print(f"=== fusion_replay_demo: replaying {csv_path} at {speed}x ===")

    try:
        replay_fusion_log(csv_path, speed)
    except KeyboardInterrupt:
        print("\n[fusion_replay_demo] stopped by user")


def main() -> None:
    csv_path = "fusion_log.csv"
    speed = 1.0

    if len(sys.argv) >= 2:
        csv_path = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            speed = float(sys.argv[2])
        except ValueError:
            print(f"Invalid speed value '{sys.argv[2]}', using default 1.0")
            speed = 1.0

    try:
        run_replay_demo(csv_path, speed)
    except KeyboardInterrupt:
        print("\n[fusion_replay_demo] stopped by user")


if __name__ == "__main__":
    main()