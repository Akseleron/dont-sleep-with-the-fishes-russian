#!/usr/bin/env python3
"""Build a v1.1.3 player-facing English coverage report."""

from __future__ import annotations

import argparse
import csv
import re
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/v1_1_3_player_facing_english_coverage.tsv"
FIELDS = [
    "priority",
    "category",
    "source_text",
    "current_translation",
    "recommended_translation",
    "status",
    "evidence_source",
    "object_context",
    "neighbouring_strings",
    "safe_to_translate",
    "where_to_fix",
    "notes",
]

SCREENSHOT_FIXES = {
    "Visit the small island?": "Посетить островок?",
    "Get the Barrel!": "Достать бочку!",
    "Support?": "Помочь?",
    "Bait guarantees catches today.": "С наживкой улов гарантирован.",
    "Cause of Death:": "Причина смерти:",
    "Your boat fell apart.": "Шлюпка развалилась.",
    "Days Survived:": "Дней выжито:",
    "Food Eaten:": "Еды съедено:",
    "Fish Caught:": "Рыбы поймано:",
    "Items Used:": "Предметов использовано:",
    "Company's Note:": "Заметка компании:",
    "Calculated risk.": "Рассчитанный риск.",
    "Dragged to the seafloor.": "Утащило на дно.",
    "Everything under control.": "Всё под контролем.",
    "The End": "Конец",
    "Click to Cancel!": "Нажмите, чтобы отменить!",
    "Empty...": "Пусто...",
    "Nails Left:": "Гвоздей осталось:",
    "You are unprepared.": "Вы не готовы.",
    "Item Lost": "Потеряно",
    "Items Lost": "Потеряно",
    "You lost an item to the sea.": "Предмет унесло в море.",
    "Item Broken": "Предмет сломан",
    "Items Broken": "Сломано",
}

HIGH_CONFIDENCE_FIXES = {
    "Dead by the Sea.": "Погиб в море.",
    "Your friend is sleeping with the fishes.": "Ваш спутник спит с рыбами.",
    "Something broke during the night.": "Ночью что-то сломалось.",
    "You did not sleep very well.": "Вы плохо поспали.",
    "You feel weak.": "Вы ослабли.",
    "Help may be on the way...": "Возможно, помощь уже близко...",
    "Hand over diving gear?": "Отдать снаряжение?",
    "Give fishnet?": "Отдать сеть?",
    "Pick up chest?": "Подобрать сундук?",
    "Set foot on land?": "Ступить на сушу?",
    "Reached land.": "Добрался до суши.",
    "Eaten alive.": "Съеден заживо.",
    "Became chest loot.": "Стал добычей сундука.",
    "Mauled to death.": "Растерзан.",
    "The fog came.": "Пришёл туман.",
    "Sharing blood with the sea.": "Кровь смешалась с морем.",
    "Found by cargo ship.": "Найден грузовым судном.",
    "Found by the company.": "Найден компанией.",
    "Grabbed into stomatch.": "Затащен в желудок.",
    "Were being watched.": "За вами наблюдали.",
    "Torn into pieces.": "Разорван на части.",
    "Accept Trade?": "Принять обмен?",
    "Delusions became too strong.": "Бред стал слишком сильным.",
    "Trafficed to ghosts.": "Продан призракам.",
    "Debt Overdue.": "Долг просрочен.",
    "SLEEP": "СПАТЬ",
    "Stared at the moon for too long.": "Слишком долго смотрел на луну.",
    "Expected results.": "Ожидаемые результаты.",
    "Anticipated outcomes.": "Ожидаемые исходы.",
    "No impact noted.": "Последствий не выявлено.",
    "Critical financial hit.": "Критический финансовый удар.",
    "Heavy financial setback.": "Серьёзный финансовый ущерб.",
    "Severely reduced returns.": "Прибыль резко снижена.",
}

TECHNICAL_EXACT = {
    "AllVisualItems",
    "CRTSettings",
    "FishedInfoHolder",
    "FishedVisuals",
    "FishInfo",
    "FishOnHookCanvas",
    "ItemAndText",
    "ItemImg",
    "ItemName",
    "ItemsHolder",
    "ItemsUpdateCanvas",
    "ItemSlot1",
    "ItemSlot2",
    "ItemText",
    "ResultIconHolder",
    "ResultsItems",
    "ScubaGoggles",
    "ScubaImage",
    "ScubaSearchHud",
    "SearchAccepted",
    "SearchDenied",
    "SettingsCanvas",
}
TECHNICAL_RE = re.compile(
    r"^(?:mixamorig:|[A-Za-z]+(?:Controller|Canvas|Holder|Layer|Model|Pivot|Settings|Button|Icon|Image|Animator)$|"
    r".*\\.(?:dll|exe|png|assets?)$|[A-Fa-f0-9]{16,}|[A-Za-z]+\\([A-Za-z,0-9 ]+\\))"
)
OBJECT_HELPER_RE = re.compile(
    r"^(?:"
    r"[a-z][a-z0-9_]*(?: \([0-9]+\))?(?: N)?|"
    r"[A-Za-z0-9_ ]*(?:"
    r"Animation|Animator|Audio|BG|Button|Buttons|Canvas|Container|Controller|Debug|Fade|"
    r"GameObject|Holder|Icon|Image|Images|ItemIcon|ItemImage|Layer|Manager|Mask|Model|"
    r"Panel|Particle|Pivot|Prefab|Renderer|Root|Script|Settings|Slot|Spawner|Text|"
    r"Trigger|Visual|Visuals|Window"
    r")[A-Za-z0-9_ ]*|"
    r"(?:AllVisualItems|ChestFound|ClickToContinue|CloseWritingTask|FoundFlower|FoundLand|"
    r"GoToSleep|GoToSleepL|GoToSleepText|ItemGenerator|ItemName|TalkDialog|TryToSleep)"
    r")$"
)
RAW_FRAGMENT_RE = re.compile(r"^(?:m |t |s |[A-Za-z]$|.*\\bdon$|.*\\bstruc\\.\\.\\.|.*\\.{3}$)")


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def iter_tsv(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle, delimiter="\t")


def normalize(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def unescape_xunity(text: str) -> str:
    return text.replace("\\n", "\n").replace("\\r", "\r").replace("\\\\", "\\")


def parse_xunity(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw or raw.startswith("#") or "=" not in raw or raw.startswith(("r:", "sr:")):
            continue
        source, target = raw.split("=", 1)
        rows[unescape_xunity(source)] = unescape_xunity(target)
    return rows


def load_translations() -> tuple[dict[str, str], dict[str, str]]:
    translations: dict[str, str] = {}
    for row in read_tsv(ROOT / "translations/source_queue.tsv"):
        source = row.get("source", "")
        target = row.get("final_russian", "") or row.get("machine_russian", "")
        if source and target and row.get("status") != "skip":
            translations[source] = target
    translations.update(parse_xunity(ROOT / "patches/xunity_autotranslator/BepInEx/Translation/ru/Text/_AutoGeneratedTranslations.txt"))
    translations.update(parse_xunity(ROOT / "dist/dswf-rus-patcher/payload/text/BepInEx/Translation/ru/Text/_AutoGeneratedTranslations.txt"))
    normalized = {normalize(source): target for source, target in translations.items()}
    return translations, normalized


def translation_for(source: str, translations: dict[str, str], normalized_translations: dict[str, str]) -> str:
    if source in translations:
        return translations[source]
    return normalized_translations.get(normalize(source), "")


def source_from_row(row: dict[str, str]) -> str:
    return row.get("source_text") or row.get("string") or ""


def evidence_from_row(row: dict[str, str]) -> str:
    if row.get("source_location"):
        return row["source_location"]
    asset = row.get("asset_file") or row.get("source_file") or ""
    path_id = row.get("path_id", "")
    field = row.get("field_path") or row.get("offset") or ""
    if path_id:
        return f"{asset}:path_id={path_id}:{field}"
    return f"{asset}:{field}"


def context_from_row(row: dict[str, str]) -> str:
    if row.get("object_context"):
        return row["object_context"]
    parts = [
        f"type={row.get('object_type', '')}",
        f"name={row.get('object_name', '')}",
        f"category={row.get('category_guess', '')}",
    ]
    return "; ".join(part for part in parts if not part.endswith("="))


def neighbours_from_row(row: dict[str, str]) -> str:
    if row.get("neighbouring_strings"):
        return row["neighbouring_strings"]
    return " || ".join(part for part in [row.get("context_before", ""), row.get("context_after", "")] if part)


def classify(source: str, row: dict[str, str]) -> tuple[str, str, str]:
    evidence = evidence_from_row(row)
    context = context_from_row(row)
    object_type = row.get("object_type", "")
    if not source.strip():
        return "ignore-technical", "no", "empty source"
    if source in SCREENSHOT_FIXES or source in HIGH_CONFIDENCE_FIXES:
        return "todo-high-confidence", "yes", "complete screenshot/high-confidence source text"
    if source in TECHNICAL_EXACT or TECHNICAL_RE.match(source) or OBJECT_HELPER_RE.match(source):
        return "ignore-technical", "no", "internal Unity/helper/source name"
    if object_type == "raw_bytes" and RAW_FRAGMENT_RE.match(source):
        return "raw-fragment-do-not-translate", "no", "raw byte fragment is incomplete"
    if row.get("priority") == "9" or row.get("status") == "ignore-technical":
        return "ignore-technical", "no", "demoted by workset classifier"
    if "binary_strings" in evidence or object_type == "binary_string":
        return "needs-context", "no", "binary string only; does not reconstruct source"
    if object_type == "raw_bytes":
        return "needs-context", "maybe", "raw byte fallback needs complete structured source confirmation"
    if any(token in context for token in ("TextMeshPro", "TextAsset", "NightEventScript", "GameController", "EndingController", "dialogue_object")):
        return "needs-context", "yes", "complete readable Unity text context"
    if row.get("category") in {"event", "dialogue", "ui", "notification", "result/search", "item"}:
        return "needs-context", "maybe", "player-facing category but context still needs review"
    return "needs-context", "maybe", "unclassified candidate"


def priority_for(source: str, row: dict[str, str], status: str) -> str:
    if source in SCREENSHOT_FIXES:
        return "1"
    if source in HIGH_CONFIDENCE_FIXES:
        return "2"
    category = row.get("category", "")
    context = context_from_row(row)
    if status in {"ignore-technical", "raw-fragment-do-not-translate"}:
        return "9"
    if "EndingController" in context or "Cause of Death" in source or "Days Survived" in source:
        return "3"
    if "NightEventScript" in context or category in {"event", "dialogue"}:
        return "4"
    if category in {"notification", "result/search", "ui", "item"}:
        return "5"
    return "6"


def category_for(row: dict[str, str], source: str) -> str:
    category = row.get("category") or row.get("category_guess") or "unknown"
    if source in SCREENSHOT_FIXES:
        if any(token in source for token in ("Death", "Days", "Food Eaten", "Fish Caught", "Items Used", "Company", "The End")):
            return "end/death/stats"
        if any(token in source for token in ("Item", "lost", "Broken", "sea")):
            return "notification"
    return category


def add_candidate(candidates: OrderedDict[str, dict[str, str]], row: dict[str, str], source: str = "") -> None:
    source = source or source_from_row(row)
    if not source:
        return
    key = source
    if key not in candidates:
        candidates[key] = row


def include_binary_row(row: dict[str, str], source: str) -> bool:
    return source in SCREENSHOT_FIXES or source in HIGH_CONFIDENCE_FIXES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    translations, normalized_translations = load_translations()
    candidates: OrderedDict[str, dict[str, str]] = OrderedDict()

    for path in [
        ROOT / "docs/translation_workset_v1_1_3.tsv",
        ROOT / "docs/untranslated_inventory_v1_1_3.tsv",
        ROOT / "docs/string_inventory_v1_1_3.tsv",
        ROOT / "docs/item_mapping_audit_v1_1_3.tsv",
    ]:
        for row in read_tsv(path):
            add_candidate(candidates, row)

    binary_path = ROOT / ".local_dumps/binary_strings/v1_1_3/binary_strings.tsv"
    for row in iter_tsv(binary_path):
        source = source_from_row(row)
        if include_binary_row(row, source):
            add_candidate(candidates, row, source)

    for source in [*SCREENSHOT_FIXES, *HIGH_CONFIDENCE_FIXES]:
        add_candidate(
            candidates,
            {
                "asset_file": "manual_runtime_screenshot" if source in SCREENSHOT_FIXES else "manual_high_confidence",
                "object_type": "manual",
                "category": "runtime-confirmed" if source in SCREENSHOT_FIXES else "high-confidence",
                "source_text": source,
                "notes": "manual evidence seed",
            },
            source,
        )

    out_rows: list[dict[str, str]] = []
    for source, row in candidates.items():
        current = translation_for(source, translations, normalized_translations)
        recommended = SCREENSHOT_FIXES.get(source, HIGH_CONFIDENCE_FIXES.get(source, ""))
        status, safe, note = classify(source, row)
        if current and status not in {"ignore-technical", "raw-fragment-do-not-translate"}:
            status = "done"
        elif recommended and status == "done" and current != recommended:
            status = "todo-high-confidence"
        if recommended and current != recommended:
            status = "todo-high-confidence"
        priority = priority_for(source, row, status)
        out_rows.append(
            {
                "priority": priority,
                "category": category_for(row, source),
                "source_text": source,
                "current_translation": current,
                "recommended_translation": recommended,
                "status": status,
                "evidence_source": evidence_from_row(row),
                "object_context": context_from_row(row),
                "neighbouring_strings": neighbours_from_row(row),
                "safe_to_translate": safe,
                "where_to_fix": "translations/source_queue.tsv" if safe == "yes" else "review context before changing source queue",
                "notes": "; ".join(part for part in [note, row.get("notes", "")] if part),
            }
        )

    out_rows.sort(key=lambda row: (int(row["priority"]), row["status"], row["source_text"].casefold()))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"wrote {len(out_rows)} rows to {out}")


if __name__ == "__main__":
    main()
