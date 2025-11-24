from __future__ import annotations

import csv
from typing import List


def run_analysis() -> None:
    path = "fusion_log.csv"
    rows: List[dict[str, str]] = []

    with open(path, "r", newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            rows.append(row)

    total_rows = len(rows)
    if total_rows == 0:
        print("No data rows found in fusion_log.csv")
        return

    distances = []
    warning_counts = {"SAFE": 0, "CAUTION": 0, "DANGER": 0}
    person_present_true = 0

    for row in rows:
        try:
            dist = float(row["distance_cm"]) if row["distance_cm"] not in ("", "None", None) else None
        except (ValueError, TypeError):
            dist = None

        if dist is not None:
            distances.append(dist)

        warning = row.get("warning_level", "").upper()
        if warning in warning_counts:
            warning_counts[warning] += 1

        if row.get("person_present", "False") == "True":
            person_present_true += 1

    min_dist = min(distances) if distances else None
    max_dist = max(distances) if distances else None
    avg_dist = sum(distances) / len(distances) if distances else None

    print(f"Total rows: {total_rows}")
    print(f"Minimum distance: {min_dist if min_dist is not None else 'N/A'} cm")
    print(f"Maximum distance: {max_dist if max_dist is not None else 'N/A'} cm")
    if avg_dist is not None:
        print(f"Average distance: {avg_dist:.1f} cm")
    else:
        print("Average distance: N/A")

    print("Warning level counts:")
    for level in ("SAFE", "CAUTION", "DANGER"):
        print(f"  {level}: {warning_counts[level]}")

    print(f"Rows with person_present=True: {person_present_true}")

    summary = (
        "Rows="
        f"{total_rows}"  # will be concatenated
        f" | avg_dist={avg_dist:.1f} cm" if avg_dist is not None else " | avg_dist=N/A"
    )

    if avg_dist is not None:
        summary = f"Rows={total_rows} | avg_dist={avg_dist:.1f} cm"
    else:
        summary = f"Rows={total_rows} | avg_dist=N/A"

    summary += (
        f" | SAFE={warning_counts['SAFE']}, "
        f"CAUTION={warning_counts['CAUTION']}, "
        f"DANGER={warning_counts['DANGER']}"
    )
    summary += f" | person_present_true={person_present_true}"
    print(summary)


def main() -> None:
    run_analysis()


if __name__ == "__main__":
    main()