#!/usr/bin/env python3
"""Merge returned tester audit ZIPs or extracted audit folders."""

from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TECHNICAL_RE = re.compile(
    r"^(?:DopplerGhost|SEED:?.*|v?\d+\.\d+(?:\.\d+)?|[A-Z]|[A-Za-z]:\\.*|/.*)$",
    re.I,
)
FIELDS = [
    "first_seen_tester",
    "seen_testers_count",
    "seen_sessions_count",
    "seen_count",
    "scene",
    "block_guess",
    "full_transform_path",
    "normalized_text",
    "sample_current_text",
    "has_latin",
    "has_cyrillic",
    "is_english_likely",
    "is_mixed_ru_en",
    "is_layout_risk",
    "status",
    "recommended_translation",
    "notes",
]


class Merged:
    def __init__(self, row: dict[str, str]) -> None:
        self.first_seen_tester = row.get("tester_id") or row.get("first_seen_tester") or ""
        self.testers = set(filter(None, [self.first_seen_tester]))
        self.sessions = set(filter(None, [row.get("session_id") or row.get("first_seen_session") or ""]))
        self.seen_count = int(row.get("seen_count") or 1)
        self.scene = row.get("scene", "")
        self.block_guess = row.get("block_guess", "")
        self.full_transform_path = row.get("full_transform_path", "")
        self.normalized_text = row.get("normalized_text", "")
        self.sample_current_text = row.get("current_text") or row.get("sample_current_text") or self.normalized_text
        self.has_latin = truthy(row.get("has_latin"))
        self.has_cyrillic = truthy(row.get("has_cyrillic"))
        self.is_english_likely = truthy(row.get("is_english_likely"))
        self.is_mixed_ru_en = truthy(row.get("is_mixed_ru_en"))
        self.is_layout_risk = truthy(row.get("is_layout_risk"))
        self.notes = row.get("notes", "")

    def update(self, row: dict[str, str]) -> None:
        tester = row.get("tester_id") or row.get("first_seen_tester") or row.get("last_seen_tester") or ""
        session = row.get("session_id") or row.get("first_seen_session") or row.get("last_seen_session") or ""
        if tester:
            self.testers.add(tester)
        if session:
            self.sessions.add(session)
        self.seen_count += int(row.get("seen_count") or 1)
        self.has_latin = self.has_latin or truthy(row.get("has_latin"))
        self.has_cyrillic = self.has_cyrillic or truthy(row.get("has_cyrillic"))
        self.is_english_likely = self.is_english_likely or truthy(row.get("is_english_likely"))
        self.is_mixed_ru_en = self.is_mixed_ru_en or truthy(row.get("is_mixed_ru_en"))
        self.is_layout_risk = self.is_layout_risk or truthy(row.get("is_layout_risk"))
        note = row.get("notes", "")
        if note and note not in self.notes:
            self.notes = "|".join(part for part in [self.notes, note] if part)

    def status(self) -> str:
        if is_technical(self.normalized_text):
            return "ignore-technical"
        if self.is_layout_risk:
            return "layout-risk-review"
        if self.is_mixed_ru_en:
            return "mixed-ru-en-review"
        if self.is_english_likely or (self.has_latin and not self.has_cyrillic):
            return "todo-translate"
        return "review"

    def row(self) -> dict[str, str]:
        return {
            "first_seen_tester": self.first_seen_tester,
            "seen_testers_count": str(len(self.testers)),
            "seen_sessions_count": str(len(self.sessions)),
            "seen_count": str(self.seen_count),
            "scene": self.scene,
            "block_guess": self.block_guess,
            "full_transform_path": self.full_transform_path,
            "normalized_text": self.normalized_text,
            "sample_current_text": self.sample_current_text,
            "has_latin": str(self.has_latin),
            "has_cyrillic": str(self.has_cyrillic),
            "is_english_likely": str(self.is_english_likely),
            "is_mixed_ru_en": str(self.is_mixed_ru_en),
            "is_layout_risk": str(self.is_layout_risk),
            "status": self.status(),
            "recommended_translation": "",
            "notes": self.notes,
        }


def truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() == "true"


def is_technical(text: str) -> bool:
    return bool(TECHNICAL_RE.match(text or ""))


def normalize_row(row: dict[str, str]) -> dict[str, str] | None:
    text = row.get("normalized_text", "").strip()
    if not text:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", row.get("current_text") or row.get("sample_current_text") or "")).strip()
    if not text:
        return None
    row = dict(row)
    row["normalized_text"] = text
    if "block_guess" not in row and "parent_path_block_guess" in row:
        row["block_guess"] = row["parent_path_block_guess"]
    return row


def iter_tsvs(input_path: Path):
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(input_path) as zf:
            for name in zf.namelist():
                if name.endswith(".tsv") and "dswf_audit" in name:
                    with zf.open(name) as handle:
                        yield input_path.name, name, io.TextIOWrapper(handle, encoding="utf-8", newline="")
    elif input_path.is_dir():
        for zip_path in sorted(input_path.rglob("*.zip")):
            yield from iter_tsvs(zip_path)
        for tsv in sorted(input_path.rglob("*.tsv")):
            if "dswf_audit" in tsv.as_posix() or "visible_text" in tsv.name:
                yield input_path.name, str(tsv), tsv.open("r", encoding="utf-8", newline="")


def merge(input_path: Path) -> tuple[dict[str, Merged], dict[str, Merged], int]:
    by_location: dict[str, Merged] = {}
    by_text: dict[str, Merged] = {}
    files = 0
    for tester_source, _name, handle in iter_tsvs(input_path):
        files += 1
        with handle:
            for raw in csv.DictReader(handle, delimiter="\t"):
                row = normalize_row(raw)
                if row is None or is_technical(row["normalized_text"]):
                    continue
                if not row.get("tester_id"):
                    row["tester_id"] = tester_source
                loc_key = "\u001f".join([row.get("scene", ""), row.get("full_transform_path", ""), row["normalized_text"]])
                text_key = row["normalized_text"]
                if loc_key in by_location:
                    by_location[loc_key].update(row)
                else:
                    by_location[loc_key] = Merged(row)
                if text_key in by_text:
                    by_text[text_key].update(row)
                else:
                    by_text[text_key] = Merged(row)
    return by_location, by_text, files


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default="tester_audits")
    args = parser.parse_args()
    input_path = Path(args.input)
    by_location, by_text, files = merge(input_path)
    loc_rows = [row.row() for row in by_location.values()]
    text_rows = [row.row() for row in by_text.values()]
    loc_rows.sort(key=lambda r: (r["status"], r["block_guess"], r["normalized_text"].casefold()))
    text_rows.sort(key=lambda r: (r["status"], r["normalized_text"].casefold()))
    english_rows = [r for r in text_rows if r["status"] in {"todo-translate", "mixed-ru-en-review"}]
    layout_rows = [r for r in loc_rows if r["is_layout_risk"] == "True"]
    write_rows(DOCS / "v1_1_3_merged_runtime_visible_text_by_location.tsv", loc_rows)
    write_rows(DOCS / "v1_1_3_merged_runtime_visible_text_by_text.tsv", text_rows)
    write_rows(DOCS / "v1_1_3_merged_runtime_english_review.tsv", english_rows)
    write_rows(DOCS / "v1_1_3_merged_runtime_layout_risk.tsv", layout_rows)
    report = [
        "# v1.1.3 Tester Audit Merge Report",
        "",
        f"Input: `{input_path}`",
        f"TSV files read: {files}",
        f"Unique by location rows: {len(loc_rows)}",
        f"Unique by text rows: {len(text_rows)}",
        f"English/mixed review rows: {len(english_rows)}",
        f"Layout-risk rows: {len(layout_rows)}",
        "",
        "Technical/branding rows such as `DopplerGhost`, `SEED`, pure paths, and version-only strings are ignored.",
    ]
    (DOCS / "v1_1_3_tester_audit_merge_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"merged {files} TSV files")


if __name__ == "__main__":
    main()
