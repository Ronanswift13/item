from __future__ import annotations

import csv
from pathlib import Path
import sys

# Ensure project root is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.yellow_line_tracker import LineZone
from core.vision_safety_controller import evaluate_vision_safety


def replay_vision_safety(csv_path: Path) -> None:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Support both "zone" and "line_zone" headers.
                zone_key = "zone" if "zone" in row else "line_zone"
                zone = LineZone[row[zone_key]]
                dist = float(row["dist"])
                has_motion = row["has_motion"].lower() in ("1", "true", "yes")
                decision = evaluate_vision_safety(zone, dist, has_motion)
                timestamp = row.get("timestamp", "")
                print(
                    f"[REPLAY] t={timestamp} zone={zone.name} dist={dist:.2f} "
                    f"motion={has_motion} -> level={decision.level.name}, "
                    f"output_enabled={decision.output_enabled}, "
                    f"is_safe={decision.is_safe}, reason={decision.reason}"
                )
            except Exception as exc:
                print(f"[ERROR] Failed to process row {row}: {exc}")


def main() -> None:
    csv_path = ROOT_DIR / "data" / "vision_line_log.csv"
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        return
    print("=== vision_safety_replay: analyzing vision_line_log.csv ===")
    replay_vision_safety(csv_path)


if __name__ == "__main__":
    main()
