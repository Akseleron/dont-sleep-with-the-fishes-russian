#!/usr/bin/env python3
"""Import a local runtime visible-English audit sample into review docs."""

from __future__ import annotations

import csv
import re
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "game_runtime_test_v1_1_3/BepInEx/visible_english_audit.tsv"
OUT_TSV = ROOT / "docs/v1_1_3_runtime_visible_english_review.tsv"
OUT_REPORT = ROOT / "docs/v1_1_3_runtime_visible_english_audit_report.md"

TECHNICAL_RE = re.compile(
    r"^(?:DopplerGhost|SEED:?.*|v?\d+\.\d+(?:\.\d+)?|[A-Z]|[A-Za-z]:\\.*|/.*)$",
    re.I,
)


def normalize(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def has_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text or ""))


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04ff]", text or ""))


def is_technical(text: str) -> bool:
    return bool(TECHNICAL_RE.match(text or ""))


def main() -> None:
    rows: list[dict[str, str]] = []
    if DEFAULT_INPUT.exists():
        with DEFAULT_INPUT.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))

    dedup: OrderedDict[str, dict[str, str]] = OrderedDict()
    ignored = 0
    for row in rows:
        text = normalize(row.get("normalized_text") or row.get("current_text") or "")
        if not text:
            continue
        if is_technical(text):
            ignored += 1
            continue
        key = "\u001f".join([row.get("scene", ""), row.get("full_transform_path", ""), text])
        if key not in dedup:
            latin = has_latin(text)
            cyr = has_cyrillic(text)
            dedup[key] = {
                "scene": row.get("scene", ""),
                "block_guess": row.get("parent_path_block_guess") or row.get("block_guess", ""),
                "full_transform_path": row.get("full_transform_path", ""),
                "current_text": row.get("current_text", ""),
                "normalized_text": text,
                "has_latin": str(latin),
                "has_cyrillic": str(cyr),
                "is_mixed_ru_en": str(latin and cyr),
                "status": "needs-translation" if latin and not cyr else ("needs-mixed-review" if latin and cyr else "review-layout-only"),
                "recommended_translation": "",
                "notes": "imported from local runtime visible English audit",
            }

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "scene",
        "block_guess",
        "full_transform_path",
        "current_text",
        "normalized_text",
        "has_latin",
        "has_cyrillic",
        "is_mixed_ru_en",
        "status",
        "recommended_translation",
        "notes",
    ]
    with OUT_TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(dedup.values())

    found = {row["normalized_text"] for row in dedup.values()}
    exact_interesting = [
        text
        for text in sorted(found, key=str.casefold)
        if "Shipmates sunk with the ship" in text
        or "Runs:" in text
        or "Record:" in text
        or "kidnapped" in text
        or "friends" in text
        or "debts" in text
        or "visible" in text
        or "rescue" in text
        or "exploration tools" in text
        or "time management" in text
        or "bad choices" in text
    ]
    report = [
        "# v1.1.3 Runtime Visible English Audit Report",
        "",
        f"Input present: `{DEFAULT_INPUT.exists()}`",
        f"Raw audit rows count: {len(rows)}",
        f"Deduped rows count: {len(dedup)}",
        f"Ignored technical rows count: {ignored}",
        f"Player-facing rows found: {sum(1 for r in dedup.values() if r['has_latin'] == 'True')}",
        "",
        "## Runtime-Visible English Found",
        "",
    ]
    if exact_interesting:
        report.extend(f"- `{text}`" for text in exact_interesting)
    else:
        report.append("- No high-priority seeded strings found in the local sample.")
    report.extend(
        [
            "",
            "## Notes",
            "",
            "- Raw `visible_english_audit.tsv` is intentionally not committed.",
            "- `Company's Note` mixed RU/EN forms need the improved all-text/mixed audit pass.",
            "- Technical rows such as `DopplerGhost`, `SEED`, and version-only text are ignored here.",
        ]
    )
    OUT_REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"wrote {len(dedup)} rows to {OUT_TSV}")
    print(f"wrote report to {OUT_REPORT}")


if __name__ == "__main__":
    main()
