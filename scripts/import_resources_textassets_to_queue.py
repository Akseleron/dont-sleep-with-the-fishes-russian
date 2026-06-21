#!/usr/bin/env python3
"""Import resources.assets TextAsset strings into the XUnity source queue.

The script is additive: it appends missing source keys and leaves existing queue
rows unchanged. Translation cache entries are stored separately so the import is
reproducible after local review.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESOURCES_TSV = ROOT / "extracted/resources_dialogue_strings.tsv"
DEFAULT_QUEUE = ROOT / "translations/source_queue.tsv"
DEFAULT_CACHE = ROOT / "translations/resources_textasset_translations.tsv"

QUEUE_FIELDS = [
    "source",
    "context",
    "file",
    "kind",
    "machine_russian",
    "final_russian",
    "status",
    "notes",
]

CACHE_FIELDS = ["source", "final_russian", "status", "notes"]

RICH_TAG_RE = re.compile(r"<[^>]+>")

MANUAL_TRANSLATIONS: dict[str, str] = {
    "ENGLISH": "",
    "…": "…",
    "…!": "…!",
    "...": "...",
    ".. Whatever. Look. We might end up using this, take it.": ".. Да плевать. Смотри. Нам это ещё может пригодиться, держи.",
}

FISHING_ENTRIES: list[tuple[str, str, str]] = [
    ("Red Snapper (+1 Food!)", "Красный луциан (+1 еда!)", "observed fishing result plain form"),
    ("Weight:", "Вес:", "observed fishing result label"),
    ("Weight: 3.3kg", "Вес: 3,3 кг", "observed fishing result exact dynamic value"),
    ("(+1 Food!)", "(+1 еда!)", "observed fishing result suffix"),
    ("<b>Weight:</b>", "<b>Вес:</b>", "rich text fishing label prefix"),
    ("<b>Weight:</b> 3.3kg", "<b>Вес:</b> 3,3 кг", "rich text fishing exact dynamic value"),
    ("<b>Red Snapper</b> <i>(+1 Food!)</i>", "<b>Красный луциан</b> <i>(+1 еда!)</i>", "rich text fishing result"),
]


@dataclass
class ImportCandidate:
    source: str
    context: str
    file: str
    kind: str
    status: str
    notes: str
    object_name: str
    field_path: str


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_field_path(field_path: str) -> tuple[str, str]:
    match = re.match(r"m_Script\[(?P<row_id>[^\]]*)\]\.(?P<field>[^.]+)$", field_path)
    if not match:
        return "", ""
    return match.group("row_id"), match.group("field")


def candidate_kind(object_name: str, field: str) -> str:
    if object_name == "dialogues" and field in {"MAN", "WOMAN", "WHO"}:
        return "resource_textasset_dialogue"
    if object_name == "journals" and field == "text":
        return "resource_textasset_journal"
    if object_name == "journals" and field == "title":
        return "resource_textasset_title"
    return ""


def default_status(kind: str, source: str, notes: str) -> str:
    if "manual" in notes:
        return "approved"
    if kind == "resource_textasset_journal":
        return "needs_review"
    if len(source) > 220:
        return "needs_review"
    return "approved"


def candidate_from_resource_row(row: dict[str, str]) -> ImportCandidate | None:
    if row.get("object_type") != "TextAsset":
        return None
    object_name = row.get("object_name", "")
    if object_name not in {"dialogues", "journals"}:
        return None
    source = row.get("source", "")
    if not source or source == "ENGLISH":
        return None
    row_id, field = parse_field_path(row.get("field_path", ""))
    kind = candidate_kind(object_name, field)
    if not kind:
        return None
    context = (
        f"resources.assets {object_name} row {row_id or '?'} field {field}; "
        f"path_id={row.get('path_id', '')}; location={row.get('offset_or_location', '')}"
    )
    notes = "imported from resources TextAsset scan"
    return ImportCandidate(
        source=source,
        context=context,
        file="resources.assets",
        kind=kind,
        status=default_status(kind, source, notes),
        notes=notes,
        object_name=object_name,
        field_path=row.get("field_path", ""),
    )


def load_candidates(resources_tsv: Path) -> list[ImportCandidate]:
    rows = load_tsv(resources_tsv)
    by_source: dict[str, ImportCandidate] = {}
    for row in rows:
        candidate = candidate_from_resource_row(row)
        if candidate and candidate.source not in by_source:
            by_source[candidate.source] = candidate
    return list(by_source.values())


def load_cache(cache_path: Path) -> dict[str, dict[str, str]]:
    if not cache_path.exists():
        return {}
    rows = load_tsv(cache_path)
    cache: dict[str, dict[str, str]] = {}
    for row in rows:
        source = row.get("source", "")
        if source:
            cache[source] = {
                "final_russian": row.get("final_russian", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
    return cache


def save_cache(cache_path: Path, cache: dict[str, dict[str, str]]) -> None:
    rows = [
        {
            "source": source,
            "final_russian": data.get("final_russian", ""),
            "status": data.get("status", ""),
            "notes": data.get("notes", ""),
        }
        for source, data in sorted(cache.items(), key=lambda item: item[0].casefold())
    ]
    write_tsv(cache_path, CACHE_FIELDS, rows)


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def translate_batch_ollama(model: str, batch: list[ImportCandidate], timeout: int) -> dict[str, str]:
    payload = {str(index): item.source for index, item in enumerate(batch)}
    prompt = (
        "Translate each English game localization string to Russian.\n"
        "Return only a JSON object with the same numeric keys and translated string values.\n"
        "No markdown, no comments.\n"
        "Style: natural Russian, survival / sea horror / isolation mood, casual speech stays casual.\n"
        "Preserve exactly any <br> tags, rich text tags, placeholders, line breaks, and leading punctuation such as .. or ….\n"
        "Glossary: Dorothy=Дороти; Row=Роу; Frederik=Фредерик; Laurel=Лорел; lifeboat=спасательная шлюпка; "
        "Food=еда; Bait=наживка; Weight=вес; Red Snapper=Красный луциан.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.15},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.load(response)["response"]
    except (urllib.error.URLError, TimeoutError, KeyError) as exc:
        raise RuntimeError(f"ollama request failed: {exc}") from exc

    try:
        parsed = json.loads(strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ollama returned non-JSON response: {raw[:500]!r}") from exc

    result: dict[str, str] = {}
    for key, source in payload.items():
        translated = str(parsed.get(key, "")).strip()
        if not translated:
            raise RuntimeError(f"ollama response missing key {key}")
        result[source] = translated
    return result


def rich_tags(text: str) -> list[str]:
    return RICH_TAG_RE.findall(text)


def validate_translation(source: str, translation: str) -> str:
    source_tags = rich_tags(source)
    missing = [tag for tag in source_tags if tag not in translation]
    if missing:
        return f"missing rich tags: {missing}"
    if "<br>" in source and "<br>" not in translation:
        return "missing <br>"
    return ""


def fill_cache_with_ollama(
    cache: dict[str, dict[str, str]],
    candidates: list[ImportCandidate],
    model: str,
    batch_size: int,
    timeout: int,
    cache_path: Path | None = None,
) -> int:
    missing = [
        candidate
        for candidate in candidates
        if candidate.source not in cache or not cache[candidate.source].get("final_russian")
    ]
    for candidate in missing:
        if candidate.source in MANUAL_TRANSLATIONS and MANUAL_TRANSLATIONS[candidate.source]:
            cache[candidate.source] = {
                "final_russian": MANUAL_TRANSLATIONS[candidate.source],
                "status": "approved",
                "notes": "manual translation",
            }
    missing = [
        candidate
        for candidate in candidates
        if candidate.source not in cache or not cache[candidate.source].get("final_russian")
    ]
    translated_count = 0
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        try:
            translations = translate_batch_ollama(model, batch, timeout)
        except RuntimeError as exc:
            if len(batch) == 1:
                raise
            print(f"batch {start // batch_size + 1} failed ({exc}); retrying one-by-one", flush=True)
            translations = {}
            for single in batch:
                translations.update(translate_batch_ollama(model, [single], timeout))
        for candidate in batch:
            translated = translations[candidate.source]
            warning = validate_translation(candidate.source, translated)
            status = default_status(candidate.kind, candidate.source, "ollama local draft")
            notes = f"local ollama draft: {model}"
            if warning:
                status = "needs_review"
                notes += f"; {warning}"
            cache[candidate.source] = {
                "final_russian": translated,
                "status": status,
                "notes": notes,
            }
            translated_count += 1
        if cache_path is not None:
            save_cache(cache_path, cache)
        print(f"translated {min(start + batch_size, len(missing))}/{len(missing)} missing TextAsset strings", flush=True)
    return translated_count


def add_manual_cache_entries(cache: dict[str, dict[str, str]]) -> None:
    for source, final in MANUAL_TRANSLATIONS.items():
        if not final:
            continue
        cache.setdefault(
            source,
            {"final_russian": final, "status": "approved", "notes": "manual translation"},
        )


def queue_row(candidate: ImportCandidate, cache_entry: dict[str, str]) -> dict[str, str]:
    final = cache_entry.get("final_russian", "")
    status = cache_entry.get("status") or candidate.status
    notes = candidate.notes
    cache_notes = cache_entry.get("notes", "")
    if cache_notes:
        notes = f"{notes}; {cache_notes}"
    return {
        "source": candidate.source,
        "context": candidate.context,
        "file": candidate.file,
        "kind": candidate.kind,
        "machine_russian": "",
        "final_russian": final,
        "status": status,
        "notes": notes,
    }


def fishing_rows(existing_sources: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source, final, note in FISHING_ENTRIES:
        if source in existing_sources:
            continue
        rows.append(
            {
                "source": source,
                "context": "manual fishing result runtime gap",
                "file": "manual_runtime",
                "kind": "manual_runtime",
                "machine_russian": "",
                "final_russian": final,
                "status": "approved",
                "notes": note,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resources", default=str(DEFAULT_RESOURCES_TSV))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--ollama-model", default="")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    resources_tsv = Path(args.resources)
    queue_path = Path(args.queue)
    cache_path = Path(args.cache)
    queue_rows = load_tsv(queue_path)
    missing_fields = set(QUEUE_FIELDS) - set(queue_rows[0].keys() if queue_rows else QUEUE_FIELDS)
    if missing_fields:
        raise SystemExit(f"{queue_path} missing required columns: {sorted(missing_fields)}")

    existing_sources = {row["source"] for row in queue_rows}
    candidates = load_candidates(resources_tsv)
    add_manual_cache_entries(cache := load_cache(cache_path))

    if args.ollama_model:
        translated = fill_cache_with_ollama(
            cache,
            candidates,
            args.ollama_model,
            args.batch_size,
            args.timeout,
            None if args.dry_run else cache_path,
        )
        print(f"added/updated {translated} local Ollama cache translations")
        if not args.dry_run:
            save_cache(cache_path, cache)

    missing_translations = [
        candidate.source
        for candidate in candidates
        if candidate.source not in existing_sources
        and (candidate.source not in cache or not cache[candidate.source].get("final_russian"))
    ]
    if missing_translations:
        print(f"missing cached translations for {len(missing_translations)} TextAsset strings", file=sys.stderr)
        print("run with --ollama-model <local-model> or add translations/resources_textasset_translations.tsv", file=sys.stderr)
        for source in missing_translations[:10]:
            print(f"- {source[:160]!r}", file=sys.stderr)
        raise SystemExit(1)

    appended: list[dict[str, str]] = []
    for candidate in candidates:
        if candidate.source in existing_sources:
            continue
        row = queue_row(candidate, cache[candidate.source])
        appended.append(row)
        existing_sources.add(candidate.source)

    fish_rows = fishing_rows(existing_sources)
    appended.extend(fish_rows)
    existing_sources.update(row["source"] for row in fish_rows)

    if not args.dry_run:
        with queue_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=QUEUE_FIELDS, delimiter="\t", lineterminator="\n")
            writer.writerows(appended)
        save_cache(cache_path, cache)

    by_kind = Counter(row["kind"] for row in appended)
    by_status = Counter(row["status"] for row in appended)
    print(f"TextAsset candidates: {len(candidates)}")
    print(f"appended rows: {len(appended)}")
    print(f"appended by kind: {dict(sorted(by_kind.items()))}")
    print(f"appended by status: {dict(sorted(by_status.items()))}")


if __name__ == "__main__":
    main()
