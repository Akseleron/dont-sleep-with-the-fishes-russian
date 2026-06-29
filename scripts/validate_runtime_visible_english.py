#!/usr/bin/env python3
"""Fail if runtime visible text audit still contains unapproved English."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "game_runtime_test_v1_1_3" / "BepInEx" / "dswf_audit"
DEFAULT_ALLOWLIST = ROOT / "docs" / "v1_1_3_runtime_visible_english_allowlist.tsv"


@dataclass(frozen=True)
class AllowRule:
    kind: str
    pattern: str
    reason: str
    regex: re.Pattern[str] | None = None

    def matches(self, text: str) -> bool:
        if self.kind == "exact":
            return text == self.pattern
        if self.kind == "contains":
            return self.pattern in text
        if self.kind == "regex" and self.regex is not None:
            return bool(self.regex.search(text))
        return False


BUILTIN_RULES = [
    AllowRule("exact", "DopplerGhost", "developer branding/dev text"),
    AllowRule("regex", r"^SEED:?.*", "runtime seed/debug value", re.compile(r"^SEED:?.*", re.I)),
    AllowRule(
        "regex",
        r"^v?\d+\.\d+(?:\.\d+)?(?:[a-z0-9._-]*)?$",
        "version/dev value",
        re.compile(r"^v?\d+\.\d+(?:\.\d+)?(?:[a-z0-9._-]*)?$", re.I),
    ),
    AllowRule("regex", r"^\d{3,4}\s*x\s*\d{3,4}$", "screen resolution value", re.compile(r"^\d{3,4}\s*x\s*\d{3,4}$", re.I)),
    AllowRule("regex", r"^\[?[A-Z]\]?$", "isolated keybind label", re.compile(r"^\[?[A-Z]\]?$")),
    AllowRule("regex", r"^WASD$", "isolated keybind label", re.compile(r"^WASD$")),
    AllowRule("regex", r"^[A-Za-z]:\\.*$", "file path", re.compile(r"^[A-Za-z]:\\.*$")),
    AllowRule("regex", r"^/.*$", "file path", re.compile(r"^/.*$")),
]

PLAYER_FACING_HINTS = {
    "Company's Note": "company note ending line; add/verify source_queue and runtime reapply coverage",
    "fate is unknown": "ending friend fate line; add/verify exact combined variant",
    "Captain Whiskers": "ending friend fate line; add/verify exact combined variant",
    "Shipmates sunk": "ending friend fate line; add/verify exact combined variant",
    "Weight:": "dynamic fishing result; use narrow regex/runtime strategy",
    "Hurts": "health hover tooltip/status text",
    "Everything hurts": "health hover tooltip/status text",
}


def load_allowlist(path: Path) -> list[AllowRule]:
    rules = list(BUILTIN_RULES)
    if not path.exists():
        return rules
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            kind = (row.get("kind") or "").strip()
            pattern = (row.get("pattern") or "").strip()
            reason = (row.get("reason") or "").strip()
            if not kind or not pattern:
                continue
            if kind == "regex":
                rules.append(AllowRule(kind, pattern, reason, re.compile(pattern, re.I)))
            else:
                rules.append(AllowRule(kind, pattern, reason))
    return rules


def is_allowed(text: str, rules: list[AllowRule]) -> bool:
    return any(rule.matches(text) for rule in rules)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def normalized_text(row: dict[str, str]) -> str:
    text = (row.get("normalized_text") or row.get("sample_current_text") or row.get("current_text") or row.get("key") or "").strip()
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def suggestion_for(text: str) -> str:
    for hint, suggestion in PLAYER_FACING_HINTS.items():
        if hint in text:
            return suggestion
    if re.search(r"[A-Za-z][A-Za-z']{2,}", text):
        return "visible player-facing candidate; add source_queue entry or runtime reapply rule if assigned late"
    return ""


def collect_failures(audit_dir: Path, rules: list[AllowRule]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for name in ("all_unique_english_text.tsv", "all_unique_mixed_ru_en_text.tsv"):
        for row in read_rows(audit_dir / name):
            text = normalized_text(row)
            if not text or is_allowed(text, rules):
                continue
            failures.append(
                {
                    "source_file": name,
                    "scene": row.get("scene", ""),
                    "block_guess": row.get("block_guess", ""),
                    "full_transform_path": row.get("full_transform_path", ""),
                    "normalized_text": text,
                    "sample_current_text": row.get("sample_current_text") or row.get("current_text") or "",
                    "suggestion": suggestion_for(text),
                }
            )
    failures.sort(key=lambda row: (row["scene"], row["full_transform_path"], row["normalized_text"].casefold()))
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_dir", nargs="?", default=str(DEFAULT_AUDIT))
    parser.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST))
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    if not audit_dir.exists():
        raise SystemExit(f"audit folder not found: {audit_dir}")

    rules = load_allowlist(Path(args.allowlist))
    failures = collect_failures(audit_dir, rules)
    print(f"audit_dir={audit_dir}")
    print(f"allowlist_rules={len(rules)}")
    print(f"unapproved_visible_english={len(failures)}")
    if failures:
        print("normalized_text\tscene\tblock_guess\tfull_transform_path\tsuggestion")
        for row in failures:
            print(
                "\t".join(
                    [
                        row["normalized_text"],
                        row["scene"],
                        row["block_guess"],
                        row["full_transform_path"],
                        row["suggestion"],
                    ]
                )
            )
        raise SystemExit(1)
    print("runtime visible English validation passed")


if __name__ == "__main__":
    main()
