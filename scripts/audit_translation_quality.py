#!/usr/bin/env python3
"""Report likely quality issues in Russian queue/resource translations."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "translations/source_queue.tsv"
RESOURCE_CACHE = ROOT / "translations/resources_textasset_translations.tsv"
RESOURCE_STRINGS = ROOT / "extracted/resources_dialogue_strings.tsv"
OUT = ROOT / "extracted/translation_quality_report.tsv"
SUPPRESSIONS = ROOT / "translations/quality_suppressions.tsv"
SUPPRESSED_FINDINGS: set[tuple[str, str]] = set()

FIELDS = [
    "source",
    "final_russian",
    "status",
    "kind",
    "context",
    "issue_type",
    "evidence",
    "recommendation",
]

ENGLISH_WORD_RE = re.compile(r"\b(?:tonight|okay|ok|weird|sorry|please|maybe|right|left|food|weight|settings|resume|happy|bored|unwell|peckish)\b", re.I)

BAD_PATTERNS = {
    "Шоколадка пробежала по спине": "bad idiom; likely should be about a shiver/chill down the spine",
    "Пetal": "mixed Latin/Cyrillic typo",
    "гагар": "bad bird term; if source is seagull, use чайка/чаек by context",
    "контрактант": "unnatural word choice",
    "Муи": "likely mistranscribed name/word",
    "ущемить": "unnatural verb in monster/fish context",
    "Я свяжусь с ним": "bad translation for face/vision context",
}

MIXED_GENDER_PATTERNS = [
    (re.compile(r"обещала.+справился", re.I | re.S), "mixed feminine обещала with masculine справился"),
    (re.compile(r"могла.+проснулся", re.I | re.S), "mixed feminine могла with masculine проснулся"),
    (re.compile(r"был.+сделала", re.I | re.S), "mixed masculine был with feminine сделала"),
    (re.compile(r"обещал.+смогла", re.I | re.S), "mixed masculine обещал with feminine смогла"),
]

FIRST_PERSON_SOURCE_RE = re.compile(r"\b(?:I|I'm|I've|I'd|my|me)\b", re.I)
GENDERED_RU_RE = re.compile(r"\b(?:сделал[аи]?|смогл[аи]?|обещал[аи]?|проснул[аи]с[ья]|был[аи]?|пош[её]л|устал[аи]?)\b", re.I)


def load_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_suppressions() -> set[tuple[str, str]]:
    suppressions: set[tuple[str, str]] = set()
    for row in load_tsv(SUPPRESSIONS):
        issue_type = row.get("issue_type", "")
        source = row.get("source", "")
        if issue_type and source:
            suppressions.add((issue_type, source))
    return suppressions


def resource_context_by_source() -> dict[str, list[str]]:
    contexts: dict[str, list[str]] = {}
    for row in load_tsv(RESOURCE_STRINGS):
        source = row.get("source", "")
        if not source:
            continue
        contexts.setdefault(source, []).append(
            f"{row.get('object_name', '')}:{row.get('field_path', '')}:{row.get('offset_or_location', '')}"
        )
    return contexts


def add_issue(
    issues: list[dict[str, str]],
    row: dict[str, str],
    issue_type: str,
    evidence: str,
    recommendation: str,
    extra_context: str = "",
) -> None:
    if (issue_type, row.get("source", "")) in SUPPRESSED_FINDINGS:
        return

    issues.append(
        {
            "source": row.get("source", ""),
            "final_russian": row.get("final_russian", ""),
            "status": row.get("status", ""),
            "kind": row.get("kind", ""),
            "context": "; ".join(filter(None, [row.get("context", ""), extra_context]))[:1000],
            "issue_type": issue_type,
            "evidence": evidence,
            "recommendation": recommendation,
        }
    )


def audit_row(row: dict[str, str], issues: list[dict[str, str]], resource_contexts: dict[str, list[str]]) -> None:
    source = row.get("source", "")
    final = row.get("final_russian", "")
    status = row.get("status", "")
    kind = row.get("kind", "")
    if status == "skip" or not final:
        return

    final_without_tags = re.sub(r"<[^>]+>", " ", final)
    english_hit = ENGLISH_WORD_RE.search(final_without_tags)
    if english_hit:
        add_issue(issues, row, "english_word_in_russian", english_hit.group(0), "review whether the English word is intentional")

    for pattern, reason in BAD_PATTERNS.items():
        if pattern.casefold() in final.casefold():
            add_issue(issues, row, "known_bad_machine_translation", pattern, reason)

    for regex, reason in MIXED_GENDER_PATTERNS:
        if regex.search(final):
            add_issue(issues, row, "mixed_gender", reason, "fix speaker gender consistency using dialogue field/context")

    source_lower = source.casefold()
    if ("lifeboat" in source_lower or re.search(r"\bboat\b", source_lower)) and "корабл" in final.casefold():
        add_issue(issues, row, "boat_term_risk", "source mentions lifeboat/boat but translation uses корабль", "prefer лодка or спасательная шлюпка by context")

    if kind.startswith("resource_textasset_journal"):
        final_len = len(final)
        ratio = final_len / max(len(source), 1)
        if final_len > 450 or final.count("<br>") >= 5 or ratio > 1.25:
            add_issue(issues, row, "journal_layout_risk", f"final_len={final_len}; ratio={ratio:.2f}; br={final.count('<br>')}", "manual journal editing/layout review")

    resource_ctx = " | ".join(resource_contexts.get(source, []))
    if kind == "resource_textasset_dialogue" and FIRST_PERSON_SOURCE_RE.search(source) and GENDERED_RU_RE.search(final):
        if any(marker in resource_ctx for marker in [".MAN", ".WOMAN", ".WHO"]):
            add_issue(
                issues,
                row,
                "dialogue_gender_review",
                resource_ctx[:500],
                "review first-person gender against MAN/WOMAN/WHO speaker context",
                resource_ctx,
            )


def main() -> int:
    global SUPPRESSED_FINDINGS

    SUPPRESSED_FINDINGS = load_suppressions()
    issues: list[dict[str, str]] = []
    resource_contexts = resource_context_by_source()

    queue_rows = load_tsv(QUEUE)
    for row in queue_rows:
        audit_row(row, issues, resource_contexts)

    # Also audit the resource cache as a cache, but mark its origin in context.
    queue_sources = {row.get("source", "") for row in queue_rows}
    for row in load_tsv(RESOURCE_CACHE):
        if row.get("source", "") in queue_sources:
            continue
        cache_row = {
            "source": row.get("source", ""),
            "final_russian": row.get("final_russian", ""),
            "status": row.get("status", ""),
            "kind": "resources_textasset_translation_cache",
            "context": "translations/resources_textasset_translations.tsv",
        }
        audit_row(cache_row, issues, resource_contexts)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(issues)

    print(f"wrote {len(issues)} quality findings to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
