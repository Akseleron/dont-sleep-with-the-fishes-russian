#!/usr/bin/env python3
"""Apply small high-confidence manual quality overrides to source_queue.tsv."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "translations/source_queue.tsv"
OUT = ROOT / "extracted/quality_overrides_report.tsv"

FIELDS = [
    "source",
    "context",
    "file",
    "kind",
    "machine_russian",
    "final_russian",
    "status",
    "notes",
]

REPORT_FIELDS = ["source", "old_final_russian", "new_final_russian", "action", "notes"]

OVERRIDES = {
    "I made a promise to protect them. I failed.": (
        "Я обещал защитить их. И не смог.",
        "visible gender consistency fix; early_days_06_01 WHO line treated as male/Row-context voice",
    )
}


def load_queue() -> list[dict[str, str]]:
    with QUEUE.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise SystemExit(f"{QUEUE} is empty")
    missing = set(FIELDS) - set(rows[0])
    if missing:
        raise SystemExit(f"{QUEUE} missing required columns: {sorted(missing)}")
    return rows


def append_note(existing: str, note: str) -> str:
    if note in existing:
        return existing
    return f"{existing}; {note}" if existing else note


def write_queue(rows: list[dict[str, str]]) -> None:
    with QUEUE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict[str, str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = load_queue()
    report_rows: list[dict[str, str]] = []
    by_source = {row["source"]: row for row in rows}

    for source, (new_final, note) in OVERRIDES.items():
        row = by_source.get(source)
        if not row:
            report_rows.append(
                {
                    "source": source,
                    "old_final_russian": "",
                    "new_final_russian": new_final,
                    "action": "not_found",
                    "notes": note,
                }
            )
            continue
        old_final = row["final_russian"]
        if old_final == new_final and row["status"] == "approved":
            action = "already_applied"
        else:
            row["final_russian"] = new_final
            row["status"] = "approved"
            row["notes"] = append_note(row["notes"], note)
            action = "updated"
        report_rows.append(
            {
                "source": source,
                "old_final_russian": old_final,
                "new_final_russian": new_final,
                "action": action,
                "notes": note,
            }
        )

    write_queue(rows)
    write_report(report_rows)
    print(f"quality overrides complete: {', '.join(row['action'] for row in report_rows)}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
