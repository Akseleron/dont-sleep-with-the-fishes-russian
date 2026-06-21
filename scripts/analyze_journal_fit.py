#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "translations/source_queue.tsv"
OUT = ROOT / "extracted/journal_fit_report.tsv"

BR_RE = re.compile(r"<br\s*/?>", re.I)
TAG_RE = re.compile(r"<[^>]+>")

FIELDS = [
    "risk_type",
    "source_len",
    "final_len",
    "ratio",
    "estimated_lines",
    "max_wrapped_line",
    "kind",
    "context",
    "source",
    "final_russian",
]


def load_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def plain_text(text: str) -> str:
    text = BR_RE.sub("\n", text)
    text = TAG_RE.sub(" ", text)
    text = text.replace("\r", "")
    return text


def visible_len(text: str) -> int:
    return len(re.sub(r"\s+", "", plain_text(text)))


def estimate_lines(text: str, width: int) -> tuple[int, int]:
    total = 0
    max_line = 0

    for part in plain_text(text).split("\n"):
        part = re.sub(r"\s+", " ", part).strip()

        if not part:
            total += 1
            continue

        wrapped = textwrap.wrap(
            part,
            width=width,
            break_long_words=False,
            replace_whitespace=False,
        )

        if not wrapped:
            total += 1
            continue

        total += len(wrapped)
        max_line = max(max_line, *(len(line) for line in wrapped))

    return total, max_line


def row_scope(row: dict[str, str]) -> str:
    kind = row.get("kind", "")
    context = row.get("context", "")

    if kind.startswith("resource_textasset_title") or " field title" in context:
        return "title"

    if kind.startswith("resource_textasset_journal") or "journals row" in context:
        return "journal"

    return ""


def risk_for(row: dict[str, str]) -> str:
    source = row.get("source", "")
    final = row.get("final_russian", "")

    if not final or row.get("status", "") == "skip":
        return ""

    scope = row_scope(row)
    if not scope:
        return ""

    src_len = max(visible_len(source), 1)
    fin_len = visible_len(final)
    ratio = fin_len / src_len

    if scope == "title":
        lines, _ = estimate_lines(final, 22)
        risks = []

        if lines > 2:
            risks.append("title_lines")
        if fin_len > 42:
            risks.append("title_length")

        return ",".join(risks)

    lines, _ = estimate_lines(final, 24)
    risks = []

    if lines > 12:
        risks.append("body_lines")
    if fin_len > 320:
        risks.append("body_length")
    if ratio > 1.35 and fin_len > 220:
        risks.append("expanded_translation")

    return ",".join(risks)


def main() -> int:
    findings: list[dict[str, str]] = []

    for row in load_tsv(QUEUE):
        risk = risk_for(row)
        if not risk:
            continue

        source = row.get("source", "")
        final = row.get("final_russian", "")
        src_len = max(visible_len(source), 1)
        fin_len = visible_len(final)
        ratio = fin_len / src_len

        width = 22 if row_scope(row) == "title" else 24
        lines, max_line = estimate_lines(final, width)

        findings.append({
            "risk_type": risk,
            "source_len": str(src_len),
            "final_len": str(fin_len),
            "ratio": f"{ratio:.2f}",
            "estimated_lines": str(lines),
            "max_wrapped_line": str(max_line),
            "kind": row.get("kind", ""),
            "context": row.get("context", ""),
            "source": source,
            "final_russian": final,
        })

    findings.sort(
        key=lambda row: (
            int(row["estimated_lines"]),
            int(row["final_len"]),
        ),
        reverse=True,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(findings)

    print(f"wrote {len(findings)} journal fit findings to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
