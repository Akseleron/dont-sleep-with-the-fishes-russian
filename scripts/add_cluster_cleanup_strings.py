#!/usr/bin/env python3
"""Add/update targeted HUD, status, event, and settings cleanup strings."""

from __future__ import annotations

import csv
from collections import OrderedDict, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "translations/source_queue.tsv"
VISIBLE = ROOT / "extracted/visible_strings.tsv"
RESOURCES = ROOT / "extracted/resources_dialogue_strings.tsv"
STATIC_REPORT = ROOT / "extracted/static_string_cluster_report.tsv"
RUNTIME_REPORT = ROOT / "extracted/runtime_untranslated_strings.tsv"
OUT = ROOT / "extracted/cluster_cleanup_report.tsv"

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

REPORT_FIELDS = ["source", "cluster", "action", "final_russian", "evidence", "notes"]

HUD_STRINGS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("I'm hungry", "Хочу есть"),
        ("I am hungry", "Хочу есть"),
        ("Stomach's growling", "Живот урчит"),
        ("Satisfied", "Сыт"),
        ("I'm satisfied", "Сыт"),
        ("I am satisfied", "Сыт"),
        ("I'm well rested", "Я выспался"),
        ("I am well rested", "Я выспался"),
        ("I'm fully rested", "Я выспался"),
        ("I am fully rested", "Я выспался"),
        ("I still have energy", "Сил ещё хватает"),
        ("I still have energy!", "Сил ещё хватает!"),
        ("I'm tired a bit", "Я немного устал"),
        ("I am tired a bit", "Я немного устал"),
    ]
)

NPC_STATUS_STRINGS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("Happy", "Счастлив"),
        ("Bored", "Скучает"),
        ("Peckish", "Проголодался"),
        ("Unwell", "Плоховато"),
        ("Hungry", "Голоден"),
        ("Sick", "Болен"),
        ("Hurt", "Ранен"),
        ("Tired", "Устал"),
    ]
)

EVENT_STRINGS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("Which way?", "Куда?"),
        ("Left", "Налево"),
        ("Right", "Направо"),
        ("Reach for it?", "Дотянуться?"),
        ("What are you going to do?", "Что делать?"),
        ("Get the Crate!", "Достать ящик!"),
        ("Let Row handle it!", "Роу справится"),
        ("Let Row handle it", "Роу справится"),
        ("Let Frederik handle it!", "Фредерик справится"),
        ("Let Frederik handle it", "Фредерик справится"),
        ("Let Laurel handle it!", "Лорел справится"),
        ("Let Laurel handle it", "Лорел справится"),
        ("Cancel", "Отмена"),
        ("Continue", "Продолжить"),
        ("Inside found:", "Внутри найдено:"),
    ]
)

SETTINGS_STRINGS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("Resume", "Дальше"),
        ("Instant Clicking", "Клик"),
        ("(Removes the requirement of holding mouse button.)", "Без удержания мыши."),
    ]
)

SCOPED_OR_SKIPPED = {
    "Settings": (
        "Опции",
        "pause_settings_layout",
        "skipped: source key is shared by main menu and settings title; XUnity scoping is not enabled",
    )
}

ALWAYS_ADD_CLUSTERS = {"hud_player_status", "event_choice", "pause_settings_layout"}


def load_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_queue() -> list[dict[str, str]]:
    rows = load_tsv(QUEUE)
    if not rows:
        raise SystemExit(f"{QUEUE} is empty or missing")
    missing = set(QUEUE_FIELDS) - set(rows[0])
    if missing:
        raise SystemExit(f"{QUEUE} missing required columns: {sorted(missing)}")
    return rows


def write_queue(rows: list[dict[str, str]]) -> None:
    with QUEUE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUEUE_FIELDS, delimiter="\t", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict[str, str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_note(existing: str, note: str) -> str:
    if note in existing:
        return existing
    return f"{existing}; {note}" if existing else note


def build_evidence() -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = defaultdict(list)

    for row in load_tsv(VISIBLE):
        source = row.get("source", "")
        if not source:
            continue
        evidence[source].append(
            f"visible:{row.get('file', '')}:byte {row.get('byte_offset', '')}; "
            f"object={row.get('object_path_id', '')}; gameobject={row.get('gameobject_name', '')}; kind={row.get('kind', '')}"
        )

    for row in load_tsv(RESOURCES):
        source = row.get("source", "")
        if source:
            evidence[source].append(
                f"resources:{row.get('asset_file', '')}; object={row.get('object_name', '')}; field={row.get('field_path', '')}"
            )

    for row in load_tsv(STATIC_REPORT):
        source = row.get("found_string", "")
        if source:
            evidence[source].append(
                f"static:{row.get('file', '')}:byte {row.get('byte_offset', '')}; seed={row.get('seed', '')}"
            )

    for row in load_tsv(RUNTIME_REPORT):
        source = row.get("source", "")
        if source:
            evidence[source].append(f"runtime:{row.get('origin', '')}; {row.get('log_context', '')[:120]}")

    return evidence


def add_or_update(
    rows: list[dict[str, str]],
    by_source: dict[str, dict[str, str]],
    evidence: dict[str, list[str]],
    source: str,
    final: str,
    cluster: str,
    require_evidence: bool,
) -> dict[str, str]:
    seen = evidence.get(source, [])
    if require_evidence and not seen and source not in by_source:
        return {
            "source": source,
            "cluster": cluster,
            "action": "not_added_no_evidence",
            "final_russian": final,
            "evidence": "",
            "notes": "not observed/found in current extracted reports",
        }

    note = f"targeted cluster cleanup: {cluster}"
    if source in by_source:
        row = by_source[source]
        changed = False
        if row["final_russian"] != final:
            row["final_russian"] = final
            changed = True
        if row["status"] != "approved":
            row["status"] = "approved"
            changed = True
        new_note = append_note(row["notes"], note)
        if new_note != row["notes"]:
            row["notes"] = new_note
            changed = True
        action = "updated" if changed else "already_present"
    else:
        row = {
            "source": source,
            "context": f"targeted cluster cleanup; cluster={cluster}",
            "file": "manual_runtime",
            "kind": "manual_runtime",
            "machine_russian": "",
            "final_russian": final,
            "status": "approved",
            "notes": note,
        }
        rows.append(row)
        by_source[source] = row
        action = "added"

    return {
        "source": source,
        "cluster": cluster,
        "action": action,
        "final_russian": final,
        "evidence": " | ".join(dict.fromkeys(seen))[:900],
        "notes": note,
    }


def main() -> int:
    rows = load_queue()
    by_source = {row["source"]: row for row in rows}
    evidence = build_evidence()
    report_rows: list[dict[str, str]] = []

    clusters = [
        ("hud_player_status", HUD_STRINGS, False),
        ("npc_status_card", NPC_STATUS_STRINGS, True),
        ("event_choice", EVENT_STRINGS, False),
        ("pause_settings_layout", SETTINGS_STRINGS, False),
    ]

    for cluster, mapping, require_evidence in clusters:
        for source, final in mapping.items():
            report_rows.append(add_or_update(rows, by_source, evidence, source, final, cluster, require_evidence))

    for source, (final, cluster, note) in SCOPED_OR_SKIPPED.items():
        report_rows.append(
            {
                "source": source,
                "cluster": cluster,
                "action": "skipped_scoping_needed",
                "final_russian": final,
                "evidence": " | ".join(dict.fromkeys(evidence.get(source, [])))[:900],
                "notes": note,
            }
        )

    write_queue(rows)
    write_report(report_rows)

    actions = defaultdict(int)
    for row in report_rows:
        actions[row["action"]] += 1
    summary = ", ".join(f"{action}={count}" for action, count in sorted(actions.items()))
    print(f"cluster cleanup complete: {summary}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
