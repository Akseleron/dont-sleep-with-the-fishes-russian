#!/usr/bin/env python3
"""Audit player-facing Unity strings across DSWF game versions.

This script is report-only. It scans Unity serialized files and project
translation tables, then writes TSV inventories plus a port-status markdown
file for the v1.1.3 update.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import UnityPy  # type: ignore
except ImportError as exc:  # pragma: no cover - user-facing dependency check
    raise SystemExit(
        "UnityPy is required. Use /home/akseleron/projects/dswf-rus/.venv-tools/bin/python "
        "or install UnityPy in the active interpreter."
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V112 = Path("/mnt/shared/Games/DontSleepWithTheFishes_v1_1_2")
DEFAULT_V113 = Path(
    "/mnt/shared/Games/DontSleepWithTheFishes_v1_1_3/"
    "DontSleepWithTheFishes_v1_1_3_ItchRelease"
)

DATA_DIR_NAME = "DontSleepWithTheFishes_Data"
SCAN_FILES = [
    "resources.assets",
    "globalgamemanagers.assets",
    "sharedassets0.assets",
    "sharedassets1.assets",
    "sharedassets2.assets",
    "sharedassets3.assets",
    "sharedassets4.assets",
    "sharedassets5.assets",
    "level0",
    "level1",
    "level2",
    "level3",
    "level4",
    "level5",
]

REPORT_COLUMNS = [
    "version",
    "asset_file",
    "object_type",
    "path_id",
    "object_name",
    "field_path",
    "source_text",
    "normalized_source_text",
    "category",
    "status",
    "translation_guess",
    "context_before",
    "context_after",
    "notes",
]

ASCII_RE = re.compile(rb"[ -~]{3,260}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){3,260}")
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://|www\.", re.I)
EXT_RE = re.compile(
    r"\.(?:dll|exe|png|jpg|jpeg|assets|asset|resource|ress|json|ini|cfg|"
    r"shader|mat|prefab|cs|pdb|xml|bytes|bundle)\b",
    re.I,
)
PATH_RE = re.compile(r"(?:[A-Za-z]:)?[\\/][A-Za-z0-9_. -]+[\\/]")
GUID_RE = re.compile(r"^(?:[a-f0-9]{16,}|[a-f0-9]{8}-[a-f0-9-]{27,})$", re.I)
NAMESPACE_RE = re.compile(r"^[A-Z_a-z][\w`]*(?:\.[A-Z_a-z][\w`]*){1,}(?:,\s*[A-Z_a-z][\w.]*)?$")
CONFIG_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,}=(?:true|false|[-0-9.]+|[A-Za-z0-9_.:/\\-]+)$", re.I)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
WEIGHT_RE = re.compile(r"^(?:<b>)?Weight:(?:</b>)?\s*[0-9]+(?:\.[0-9]+)?kg$", re.I)
FOOD_RE = re.compile(r"^[A-Za-z][A-Za-z '’-]+ \(\+[0-9]+ Food!\)$")
EN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")

TECH_WORDS = {
    "Assembly-CSharp",
    "BepInEx",
    "CanvasRenderer",
    "GameObject",
    "Il2Cpp",
    "MonoBehaviour",
    "MonoScript",
    "RectTransform",
    "SpriteRenderer",
    "TextMeshPro",
    "TextMeshProUGUI",
    "TMP_FontAsset",
    "Transform",
    "UnityEngine",
    "XUnity",
    "m_GameObject",
    "m_Name",
    "m_Script",
    "m_Text",
}

TECH_OBJECT_TYPES = {
    "AnimationClip",
    "AnimatorController",
    "AudioClip",
    "ComputeShader",
    "Material",
    "Mesh",
    "MonoScript",
    "Shader",
}

PLAYER_HINTS = {
    "Accept",
    "Bait",
    "Broken",
    "Cancel",
    "Chest",
    "Click",
    "Close",
    "Condition",
    "Continue",
    "Damaged",
    "Day",
    "End",
    "Energy",
    "Fish",
    "Flare",
    "Food",
    "Found",
    "Give",
    "Health",
    "Hungry",
    "Item",
    "Journal",
    "Not enough",
    "Pick",
    "Scuba",
    "Search",
    "Settings",
    "Defaults",
    "Mode",
    "Restore",
    "Scenario",
    "Send",
    "Sleep",
    "Talk",
    "Tired",
    "Trade",
    "Use",
    "Weight",
    "You",
}

ITEM_HINTS = {
    "bait",
    "bar",
    "barrel",
    "chest",
    "compass",
    "duct",
    "energy",
    "fish",
    "flare",
    "food",
    "gun",
    "harpoon",
    "hook",
    "item",
    "key",
    "map",
    "net",
    "pistol",
    "scuba",
    "tape",
    "tool",
}

KNOWN_UI_BUGS = [
    (
        "manual_known_bug",
        "RESULT/SEARCH paper title",
        "result/search",
        "todo",
        "",
        "Known v1.1.2/v0.1.2 bug: result/search paper overlaps with `ПОИСКА`; do not change global UI layout blindly.",
    ),
    (
        "manual_known_bug",
        "Your search did not yield results.",
        "result/search",
        "todo",
        "Ничего не найдено.",
        "Known fix candidate: current `Поиск ничего...`/`Поиск ничего не дал.` should become `Ничего не найдено.`",
    ),
    (
        "manual_known_bug",
        "You found",
        "notification",
        "todo",
        "Найдено:",
        "Known fix candidate: `Вы нашли` should become `Найдено:` in result/notification context.",
    ),
    (
        "manual_known_bug",
        "Scuba set was damaged in the process.",
        "notification",
        "todo",
        "Акваланг повреждён.",
        "Known fix candidate: current `В процессе был поврежден акваланг.` is too long and has `е` instead of `ё`.",
    ),
    (
        "manual_known_bug",
        "Item Broken",
        "notification",
        "todo",
        "",
        "Known bug: `Item Broken` remains untranslated.",
    ),
    (
        "manual_known_bug",
        "Items Found",
        "notification",
        "todo",
        "",
        "Known bug: left notification `Найдено пре...` is clipped; review shorter wording and target UI bounds.",
    ),
]


@dataclass
class Candidate:
    version: str
    asset_file: str
    object_type: str
    path_id: str
    object_name: str
    field_path: str
    source_text: str
    order: int
    notes: str

    def object_key(self) -> tuple[str, str, str]:
        return (self.asset_file, self.object_type, self.path_id)


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("…", "...")
    text = TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def has_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text))


def is_probable_text(text: str) -> bool:
    if not text or "\x00" in text:
        return False
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\r\n\t")
    return printable / max(len(text), 1) > 0.95


def decode_text_asset_payload(data: Any) -> str:
    payload = getattr(data, "m_Script", b"")
    if isinstance(payload, str):
        return payload
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return ""


def recursive_strings(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from recursive_strings(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield from recursive_strings(child, child_path)


def read_len_prefixed(raw: bytes, rel_len_offset: int) -> tuple[int, str] | None:
    if rel_len_offset < 0 or rel_len_offset + 4 > len(raw):
        return None
    size = int.from_bytes(raw[rel_len_offset : rel_len_offset + 4], "little")
    if size <= 0 or size > 4096:
        return None
    start = rel_len_offset + 4
    end = start + size
    if end > len(raw):
        return None
    try:
        text = raw[start:end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not is_probable_text(text):
        return None
    return size, text


def iter_len_prefixed(raw: bytes) -> Iterable[tuple[int, int, str]]:
    for rel_len_offset in range(0, max(0, len(raw) - 4)):
        parsed = read_len_prefixed(raw, rel_len_offset)
        if parsed is None:
            continue
        size, text = parsed
        yield rel_len_offset, size, text


def safe_typetree(obj: Any) -> dict[str, Any] | None:
    try:
        return obj.read_typetree(check_read=False)
    except Exception:
        try:
            return obj.read_typetree()
        except Exception:
            return None


def safe_name(obj: Any) -> str:
    try:
        data = obj.read()
        return str(getattr(data, "m_Name", "") or "")
    except Exception:
        tree = safe_typetree(obj)
        if isinstance(tree, dict):
            return str(tree.get("m_Name", "") or "")
    return ""


def get_script_map(env: Any) -> dict[int, str]:
    scripts: dict[int, str] = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            data = obj.read()
        except Exception:
            continue
        namespace = getattr(data, "m_Namespace", "")
        class_name = getattr(data, "m_ClassName", "")
        assembly = getattr(data, "m_AssemblyName", "")
        full_name = f"{namespace}.{class_name}" if namespace else class_name
        if class_name:
            scripts[int(obj.path_id)] = f"{assembly}:{full_name}"
    return scripts


def get_gameobject_names(env: Any) -> dict[tuple[str, int], str]:
    names: dict[tuple[str, int], str] = {}
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        tree = safe_typetree(obj)
        if isinstance(tree, dict):
            names[(obj.assets_file.name, int(obj.path_id))] = str(tree.get("m_Name", "") or "")
    return names


def iter_textasset_values(payload: str) -> Iterable[tuple[str, str]]:
    text = payload.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines:
        return
    delimiters = [";", "\t", ","]
    delimiter = max(delimiters, key=lambda char: lines[0].count(char))
    if delimiter and lines[0].count(delimiter) > 0:
        try:
            rows = list(csv.DictReader(lines, delimiter=delimiter, quotechar='"'))
        except Exception:
            rows = []
        if rows and rows[0]:
            for row_index, row in enumerate(rows, 2):
                row_id = row.get("id") or row.get("ID") or row.get("key") or row.get("Key") or str(row_index)
                for key, value in row.items():
                    if value is None:
                        continue
                    for part_index, part in enumerate(split_text_value(value)):
                        yield f"m_Script[{row_id}].{key}[{part_index}]", part
            return
    for line_no, line in enumerate(lines, 1):
        for part_index, part in enumerate(split_text_value(line)):
            yield f"m_Script.line[{line_no}][{part_index}]", part


def split_text_value(value: str) -> list[str]:
    values: list[str] = []
    raw = value.strip().strip('"')
    if raw:
        values.append(raw)
    for chunk in re.split(r"<br>|\\n|\n|\r", raw):
        chunk = chunk.strip().strip('"')
        if chunk and chunk not in values:
            values.append(chunk)
    return values


def raw_candidate_interest(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 3 or len(stripped) > 260:
        return False
    if not has_latin(stripped):
        return False
    if is_technical(stripped):
        return False
    if not re.fullmatch(r"[A-Za-z0-9А-Яа-яЁё .,!?:;'’\"+()<>/\n\r-]+", stripped):
        return False
    letters = sum(1 for ch in stripped if ch.isalpha())
    symbols = sum(1 for ch in stripped if not ch.isalnum() and not ch.isspace())
    if letters / max(len(stripped), 1) < 0.45:
        return False
    if symbols / max(len(stripped), 1) > 0.22:
        return False
    words = EN_WORD_RE.findall(stripped)
    if len(words) >= 2:
        return True
    return any(hint.casefold() in stripped.casefold() for hint in PLAYER_HINTS)


def scan_raw_strings(version: str, asset_path: Path, asset_file: str, start_order: int) -> list[Candidate]:
    data = asset_path.read_bytes()
    rows: list[Candidate] = []
    order = start_order
    for method, regex, decoder in (
        ("raw_ascii", ASCII_RE, lambda raw: raw.decode("utf-8", errors="replace")),
        ("raw_utf16le", UTF16_RE, lambda raw: raw.decode("utf-16le", errors="replace")),
    ):
        hits = 0
        for match in regex.finditer(data):
            text = decoder(match.group(0)).strip()
            if not raw_candidate_interest(text):
                continue
            rows.append(
                Candidate(
                    version,
                    asset_file,
                    "raw_bytes",
                    "",
                    "",
                    f"{method}@{match.start()}",
                    text,
                    order,
                    "raw byte fallback candidate; inspect neighbouring Unity object if promoted",
                )
            )
            order += 1
            hits += 1
            if hits >= 900:
                break
    return rows


def scan_unity_file(version: str, data_dir: Path, asset_file: str, start_order: int) -> list[Candidate]:
    path = data_dir / asset_file
    if not path.exists():
        return []
    rows: list[Candidate] = []
    order = start_order
    try:
        env = UnityPy.load(str(path))
    except Exception as exc:
        return [
            Candidate(
                version,
                asset_file,
                "load_error",
                "",
                "",
                "",
                f"{type(exc).__name__}: {exc}",
                order,
                "UnityPy load failed",
            )
        ]

    script_map = get_script_map(env)
    gameobject_names = get_gameobject_names(env)

    for obj in env.objects:
        type_name = obj.type.name
        path_id = str(obj.path_id)
        obj_name = safe_name(obj)
        tree = safe_typetree(obj)
        if type_name == "TextAsset":
            try:
                data = obj.read()
                payload = decode_text_asset_payload(data)
            except Exception:
                payload = ""
            if payload:
                for field_path, text in iter_textasset_values(payload):
                    rows.append(
                        Candidate(
                            version,
                            asset_file,
                            "TextAsset",
                            path_id,
                            obj_name,
                            field_path,
                            text,
                            order,
                            "TextAsset payload/string-table cell",
                        )
                    )
                    order += 1

        if tree is not None:
            for field_path, text in recursive_strings(tree):
                if type_name == "TextAsset" and field_path == "m_Script":
                    continue
                rows.append(
                    Candidate(
                        version,
                        asset_file,
                        type_name,
                        path_id,
                        obj_name,
                        field_path,
                        text,
                        order,
                        "UnityPy typetree string",
                    )
                )
                order += 1

        if type_name == "MonoBehaviour":
            script = ""
            gameobject_name = obj_name
            if isinstance(tree, dict):
                script_id = tree.get("m_Script", {}).get("m_PathID")
                if script_id is not None:
                    script = script_map.get(int(script_id), f"unknown:{script_id}")
                gameobject_id = tree.get("m_GameObject", {}).get("m_PathID")
                if gameobject_id is not None:
                    gameobject_name = gameobject_names.get((asset_file, int(gameobject_id)), obj_name)
            try:
                raw = obj.get_raw_data()
            except Exception:
                raw = b""
            if script == "Unity.TextMeshPro:TMPro.TextMeshProUGUI" or script == "Unity.TextMeshPro:TMPro.TextMeshPro":
                parsed = read_len_prefixed(raw, 88)
                if parsed is not None:
                    size, text = parsed
                    rows.append(
                        Candidate(
                            version,
                            asset_file,
                            "MonoBehaviour",
                            path_id,
                            gameobject_name,
                            "m_Text",
                            text,
                            order,
                            f"TMP text; script={script}; byte_offset={obj.byte_start + 92}; length={size}",
                        )
                    )
                    order += 1

            for rel_offset, size, text in iter_len_prefixed(raw):
                if rel_offset < 24 or not raw_candidate_interest(text):
                    continue
                if script.startswith("Unity.TextMeshPro:") and rel_offset == 88:
                    continue
                rows.append(
                    Candidate(
                        version,
                        asset_file,
                        "MonoBehaviour",
                        path_id,
                        gameobject_name,
                        f"raw_length_prefixed@{obj.byte_start + rel_offset + 4}",
                        text,
                        order,
                        f"MonoBehaviour length-prefixed string; script={script}; length={size}",
                    )
                )
                order += 1

    rows.extend(scan_raw_strings(version, path, asset_file, order))
    return rows


def is_technical(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if URL_RE.search(stripped) or EXT_RE.search(stripped) or PATH_RE.search(stripped):
        return True
    if GUID_RE.fullmatch(stripped):
        return True
    if CONFIG_KEY_RE.fullmatch(stripped):
        return True
    if any(word in stripped for word in TECH_WORDS):
        return True
    if "Base Layer" in stripped or "AnyState" in stripped or "Entry ->" in stripped or " -> " in stripped:
        return True
    if re.search(r"\b(?:GravityWeight|BlendTree|Animator|Animation|Shader|Diffuse|Specular|Alpha Clip|Cubemap|Render|Texture)\b", stripped):
        return True
    if re.fullmatch(r"[a-z]+(?:-[a-z0-9]+)+", stripped):
        return True
    if NAMESPACE_RE.fullmatch(stripped) and " " not in stripped:
        return True
    if re.fullmatch(r"[A-Fa-f0-9]{8,}", stripped):
        return True
    if re.fullmatch(r"[-+]?[0-9]+(?:\.[0-9]+)?", stripped):
        return True
    if re.fullmatch(r"[A-Za-z0-9_.:/#-]{3,100}", stripped) and "." in stripped and " " not in stripped:
        return True
    if IDENTIFIER_RE.fullmatch(stripped):
        lowered = stripped.casefold()
        if "_" in stripped:
            return True
        if stripped.islower() and lowered not in {hint.casefold() for hint in PLAYER_HINTS}:
            return True
        if len(stripped) > 18:
            return True
    if stripped.startswith("[") and ("BepInEx" in stripped or "XUnity" in stripped or "Unity" in stripped):
        return True
    words = EN_WORD_RE.findall(stripped)
    if words and not any(re.search(r"[AEIOUYaeiouy]", word) for word in words):
        return True
    return False


def is_obvious_technical_candidate(candidate: Candidate, text: str) -> bool:
    if candidate.object_type in TECH_OBJECT_TYPES:
        return True
    if "Unity.RenderPipelines" in candidate.notes or "UnityEngine.Rendering" in candidate.notes:
        return True
    if text.startswith("Light Layer ") or candidate.object_name.startswith("URP-"):
        return True
    if candidate.object_type == "raw_bytes" and candidate.asset_file in {"globalgamemanagers.assets"}:
        return True
    if candidate.field_path.startswith("m_TOS[") or ".m_ParsedForm." in candidate.field_path:
        return True
    if candidate.object_type in {"GameObject", "Texture2D", "Sprite"}:
        lowered = text.casefold()
        if not any(hint.casefold() in lowered for hint in PLAYER_HINTS | {"junk", "journal"}):
            return True
        if " " not in text and not any(hint.casefold() == lowered for hint in PLAYER_HINTS):
            return True
    return False


def looks_player_facing(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2 or len(stripped) > 900:
        return False
    if not has_latin(stripped):
        return False
    if is_technical(stripped):
        return False
    if WEIGHT_RE.match(stripped) or FOOD_RE.match(stripped):
        return True
    if any(hint.casefold() in stripped.casefold() for hint in PLAYER_HINTS):
        return True
    words = EN_WORD_RE.findall(stripped)
    if len(words) >= 2 and any(mark in stripped for mark in [" ", "?", "!", ".", ":", ",", "...", "…"]):
        return True
    return False


def classify(candidate: Candidate) -> str:
    text = candidate.source_text.strip()
    context = " ".join([candidate.asset_file, candidate.object_type, candidate.object_name, candidate.field_path, candidate.notes]).casefold()
    lowered = text.casefold()
    if is_technical(text):
        return "technical"
    if "dialogue" in context or ".man" in candidate.field_path.casefold() or ".woman" in candidate.field_path.casefold():
        return "dialogue"
    if "journal" in context or (len(text) > 110 and "<br>" in text):
        return "event"
    if any(term in lowered for term in ["search", "found", "yield results", "result"]):
        return "result/search"
    if any(term in lowered for term in ["broken", "damaged", "not enough", "picked", "item "]):
        return "notification"
    if "Assembly-CSharp:Item" in candidate.notes or "CursorInfoMaker" in candidate.notes or any(term in context for term in ITEM_HINTS):
        return "item"
    if "tmp" in context or any(term in lowered for term in ["settings", "continue", "close", "end day", "talk", "sleep", "health", "food", "bait", "condition"]):
        return "ui"
    return "unknown"


def unescape_xunity(text: str) -> str:
    return text.replace("\\n", "\n").replace("\\r", "\r").replace("\\\\", "\\")


def escape_preview(text: str, limit: int = 180) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) > limit:
        return clean[: limit - 3] + "..."
    return clean


def parse_xunity_file(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line or line.startswith("#") or "=" not in line or line.startswith(("r:", "sr:")):
                continue
            source, target = line.split("=", 1)
            rows[unescape_xunity(source)] = unescape_xunity(target)
    return rows


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_translation_map() -> dict[str, str]:
    translations: dict[str, str] = {}
    for row in read_tsv(ROOT / "translations/source_queue.tsv"):
        source = row.get("source", "")
        target = row.get("final_russian", "") or row.get("machine_russian", "")
        if source and target and row.get("status") != "skip":
            translations[source] = target
    for row in read_tsv(ROOT / "translations/resources_textasset_translations.tsv"):
        source = row.get("source", "")
        target = row.get("russian", "") or row.get("final_russian", "") or row.get("translation", "")
        if source and target:
            translations.setdefault(source, target)
    for row in read_tsv(ROOT / "translations/ru.tsv"):
        source = row.get("source", "")
        target = row.get("russian", "")
        if source and target:
            translations.setdefault(source, target)
    translations.update(parse_xunity_file(ROOT / "patches/xunity_autotranslator/BepInEx/Translation/ru/Text/_AutoGeneratedTranslations.txt"))
    return translations


def normalized_translation_map(translations: dict[str, str]) -> dict[str, str]:
    by_norm: dict[str, str] = {}
    for source, target in translations.items():
        by_norm.setdefault(normalize(source), target)
    return by_norm


def translation_guess(text: str, translations: dict[str, str], by_norm: dict[str, str] | None = None) -> str:
    if text in translations:
        return translations[text]
    by_norm = by_norm if by_norm is not None else normalized_translation_map(translations)
    return by_norm.get(normalize(text), "")


def status_for(candidate: Candidate, category: str, guess: str) -> str:
    text = candidate.source_text.strip()
    if category == "technical":
        return "ignore-technical"
    if WEIGHT_RE.match(text):
        return "ignore-technical"
    if guess:
        return "done"
    if category == "unknown":
        return "needs-context"
    return "todo"


def make_report_rows(candidates: list[Candidate], translations: dict[str, str], by_norm: dict[str, str]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.object_key()].append(candidate)
    for values in grouped.values():
        values.sort(key=lambda item: item.order)

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for candidate in sorted(candidates, key=lambda item: (item.asset_file, item.order, item.path_id, item.field_path)):
        text = candidate.source_text.strip()
        if not text or has_cyrillic(text) or not has_latin(text):
            continue
        if is_technical(text) or is_obvious_technical_candidate(candidate, text):
            continue
        if not looks_player_facing(text):
            continue
        category = classify(candidate)
        if category == "technical":
            continue
        key = (candidate.asset_file, candidate.object_type, candidate.path_id, candidate.field_path, normalize(text))
        if key in seen:
            continue
        seen.add(key)
        group = grouped[candidate.object_key()]
        index = group.index(candidate)
        before = " | ".join(escape_preview(item.source_text, 90) for item in group[max(0, index - 3) : index] if item.source_text.strip())
        after = " | ".join(escape_preview(item.source_text, 90) for item in group[index + 1 : index + 4] if item.source_text.strip())
        guess = translation_guess(text, translations, by_norm)
        status = status_for(candidate, category, guess)
        rows.append(
            {
                "version": candidate.version,
                "asset_file": candidate.asset_file,
                "object_type": candidate.object_type,
                "path_id": candidate.path_id,
                "object_name": candidate.object_name,
                "field_path": candidate.field_path,
                "source_text": text,
                "normalized_source_text": normalize(text),
                "category": category,
                "status": status,
                "translation_guess": guess,
                "context_before": before,
                "context_after": after,
                "notes": candidate.notes,
            }
        )
    return rows


def scan_version(version: str, game_root: Path, translations: dict[str, str], by_norm: dict[str, str]) -> list[dict[str, str]]:
    data_dir = game_root / DATA_DIR_NAME
    if not data_dir.exists():
        raise SystemExit(f"Data dir does not exist: {data_dir}")
    candidates: list[Candidate] = []
    order = 0
    for asset_file in SCAN_FILES:
        asset_path = data_dir / asset_file
        if not asset_path.exists():
            continue
        found = scan_unity_file(version, data_dir, asset_file, order)
        candidates.extend(found)
        order += len(found) + 1
    return make_report_rows(candidates, translations, by_norm)


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def project_translation_rows(translations: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in [
        ROOT / "translations/source_queue.tsv",
        ROOT / "translations/resources_textasset_translations.tsv",
        ROOT / "translations/ru.tsv",
        ROOT / "patches/xunity_autotranslator/BepInEx/Translation/ru/Text/_AutoGeneratedTranslations.txt",
    ]:
        if path.suffix == ".txt":
            parsed = parse_xunity_file(path)
            for source, target in parsed.items():
                if has_latin(source) and looks_player_facing(source):
                    rows.append(manual_row("project", str(path.relative_to(ROOT)), source, classify_project_source(source), "done" if target else "todo", target, "project XUnity dictionary entry"))
            continue
        for row in read_tsv(path):
            source = row.get("source", "")
            target = row.get("final_russian", "") or row.get("russian", "") or row.get("translation", "")
            if has_latin(source) and looks_player_facing(source):
                rows.append(manual_row("project", str(path.relative_to(ROOT)), source, classify_project_source(source), "done" if target else "todo", target, "project translation table entry"))
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        key = (row["asset_file"], row["normalized_source_text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def classify_project_source(source: str) -> str:
    fake = Candidate("project", "project", "translation", "", "", "", source, 0, "")
    return classify(fake)


def manual_row(
    version: str,
    asset_file: str,
    source: str,
    category: str,
    status: str,
    guess: str,
    notes: str,
) -> dict[str, str]:
    return {
        "version": version,
        "asset_file": asset_file,
        "object_type": "manual",
        "path_id": "",
        "object_name": "",
        "field_path": "",
        "source_text": source,
        "normalized_source_text": normalize(source),
        "category": category,
        "status": status,
        "translation_guess": guess,
        "context_before": "",
        "context_after": "",
        "notes": notes,
    }


def make_untranslated_v113(rows113: list[dict[str, str]], translations: dict[str, str], by_norm: dict[str, str]) -> list[dict[str, str]]:
    out = [
        row
        for row in rows113
        if row["status"] in {"todo", "needs-context", "suspicious-mapping"}
        and row["category"] != "technical"
    ]
    for _kind, source, category, status, guess, notes in KNOWN_UI_BUGS:
        existing_guess = translation_guess(source, translations, by_norm) or guess
        out.append(manual_row("v1.1.3", "known_v1_1_2_v0_1_2_ui_bugs", source, category, status, existing_guess, notes))
    out.sort(key=lambda row: (row["status"], row["category"], row["asset_file"], row["source_text"].casefold()))
    return out


def item_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    for row in rows:
        haystack = " ".join([row["category"], row["source_text"], row["object_name"], row["field_path"], row["notes"]]).casefold()
        if row["category"] == "item" or any(hint in haystack for hint in ITEM_HINTS):
            if row["category"] != "technical":
                result.append(row)
    return result


def make_item_mapping_audit(
    rows112: list[dict[str, str]],
    rows113: list[dict[str, str]],
    translations: dict[str, str],
    by_norm: dict[str, str],
) -> list[dict[str, str]]:
    old_items = item_rows(rows112)
    new_items = item_rows(rows113)
    by_old_location = {(row["asset_file"], row["path_id"], row["field_path"]): row for row in old_items if row["path_id"]}
    by_new_location = {(row["asset_file"], row["path_id"], row["field_path"]): row for row in new_items if row["path_id"]}
    by_old_text: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_new_text: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in old_items:
        by_old_text[row["normalized_source_text"]].append(row)
    for row in new_items:
        by_new_text[row["normalized_source_text"]].append(row)

    audit: list[dict[str, str]] = []
    for key, old in sorted(by_old_location.items()):
        new = by_new_location.get(key)
        if not new:
            continue
        if old["normalized_source_text"] != new["normalized_source_text"]:
            note = (
                f"Same asset/path_id/field changed from v1.1.2 `{old['source_text']}` to v1.1.3 `{new['source_text']}`. "
                "Treat as unstable-order/path-id evidence, not as a safe mapping."
            )
            status = "suspicious-mapping"
            audit.append(mapping_row(new, status, translation_guess(new["source_text"], translations, by_norm), old, note))

    shared_texts = sorted(set(by_old_text) & set(by_new_text))
    for norm in shared_texts:
        old_locs = {(row["asset_file"], row["path_id"], row["field_path"]) for row in by_old_text[norm]}
        new_locs = {(row["asset_file"], row["path_id"], row["field_path"]) for row in by_new_text[norm]}
        if old_locs != new_locs:
            representative = by_new_text[norm][0]
            note = (
                "Same English item text exists in both versions but serialized locations differ. "
                f"v1.1.2 locations={format_locs(by_old_text[norm])}; "
                f"v1.1.3 locations={format_locs(by_new_text[norm])}. "
                "Use source text plus neighbouring object context, not path_id/list index."
            )
            moved_status = "suspicious-mapping" if representative["category"] == "item" else "needs-context"
            audit.append(mapping_row(representative, moved_status, translation_guess(representative["source_text"], translations, by_norm), None, note))

    for norm in sorted(set(by_new_text) - set(by_old_text)):
        representative = by_new_text[norm][0]
        note = f"New v1.1.3 item-like text absent from v1.1.2 item inventory. Locations={format_locs(by_new_text[norm])}."
        audit.append(mapping_row(representative, "todo" if not representative["translation_guess"] else "done", representative["translation_guess"], None, note))

    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in audit:
        key = (row["asset_file"], row["path_id"], row["field_path"], row["normalized_source_text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    unique.sort(key=lambda row: (row["status"] != "suspicious-mapping", row["asset_file"], row["path_id"], row["source_text"].casefold()))
    return unique


def mapping_row(new: dict[str, str], status: str, guess: str, old: dict[str, str] | None, note: str) -> dict[str, str]:
    row = dict(new)
    row["status"] = status
    row["translation_guess"] = guess
    row["notes"] = note
    if old:
        row["context_before"] = f"v1.1.2 same location: {old['source_text']} [{old['object_name']}; {old['notes']}]"
    return row


def format_locs(rows: list[dict[str, str]], limit: int = 5) -> str:
    parts = [
        f"{row['asset_file']}:{row['path_id']}:{row['field_path']}:{row['object_name']}"
        for row in rows[:limit]
    ]
    if len(rows) > limit:
        parts.append(f"+{len(rows) - limit} more")
    return "; ".join(parts)


def file_inventory(game_root: Path) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    data_dir = game_root / DATA_DIR_NAME
    for path in sorted(data_dir.glob("*")):
        if path.is_file():
            rows.append((path.name, path.stat().st_size))
    return rows


def sharedasset_hashes(game_root: Path) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    data_dir = game_root / DATA_DIR_NAME
    for path in sorted(data_dir.glob("sharedassets*.assets")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((path.name, path.stat().st_size, digest))
    return rows


def write_status(
    path: Path,
    v112_root: Path,
    v113_root: Path,
    rows112: list[dict[str, str]],
    rows113: list[dict[str, str]],
    untranslated: list[dict[str, str]],
    mapping: list[dict[str, str]],
    branch_status: str,
) -> None:
    game_rows112 = [row for row in rows112 if row["version"] == "v1.1.2" and row["category"] != "technical"]
    game_rows113 = [row for row in rows113 if row["version"] == "v1.1.3" and row["category"] != "technical"]
    set112 = {row["normalized_source_text"] for row in game_rows112}
    set113 = {row["normalized_source_text"] for row in game_rows113}
    new_norms = sorted(set113 - set112)
    removed_norms = sorted(set112 - set113)
    by_norm113 = {row["normalized_source_text"]: row["source_text"] for row in game_rows113}
    by_norm112 = {row["normalized_source_text"]: row["source_text"] for row in game_rows112}
    suspicious = [row for row in mapping if row["status"] == "suspicious-mapping"]

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# v1.1.3 Port Status\n\n")
        handle.write("Generated by `scripts/audit_unity_strings.py`.\n\n")
        handle.write("## Scope\n\n")
        handle.write("- Audit only; no broad translation/layout/runtime fixes were applied.\n")
        handle.write("- Runtime texture replacement remains disabled by design.\n")
        handle.write("- TMP/font replacement is not implemented and is not claimed fixed.\n")
        handle.write("- Dynamic fish weight strings are marked do-not-touch and should not be fixed with exact rows.\n\n")
        handle.write("## Environment Checks\n\n")
        handle.write(f"- Active branch check: `{branch_status}`.\n")
        handle.write(f"- v1.1.2 path: `{v112_root}`.\n")
        handle.write(f"- v1.1.3 path: `{v113_root}`.\n")
        handle.write(f"- v1.1.3 path exists: `{'yes' if v113_root.exists() else 'no'}`.\n")
        handle.write(f"- UnityPy version: `{getattr(UnityPy, '__version__', 'unknown')}`.\n\n")

        handle.write("## Sharedassets SHA256\n\n")
        handle.write("| File | v1.1.2 size | v1.1.2 sha256 | v1.1.3 size | v1.1.3 sha256 |\n")
        handle.write("| --- | ---: | --- | ---: | --- |\n")
        h112 = {name: (size, digest) for name, size, digest in sharedasset_hashes(v112_root)}
        h113 = {name: (size, digest) for name, size, digest in sharedasset_hashes(v113_root)}
        for name in sorted(set(h112) | set(h113)):
            size112, digest112 = h112.get(name, ("", ""))
            size113, digest113 = h113.get(name, ("", ""))
            handle.write(f"| `{name}` | {size112} | `{digest112}` | {size113} | `{digest113}` |\n")

        handle.write("\n## Asset File Size Changes\n\n")
        inv112 = dict(file_inventory(v112_root))
        inv113 = dict(file_inventory(v113_root))
        handle.write("| File | v1.1.2 bytes | v1.1.3 bytes | Delta |\n")
        handle.write("| --- | ---: | ---: | ---: |\n")
        for name in sorted(set(inv112) | set(inv113)):
            s112 = inv112.get(name)
            s113 = inv113.get(name)
            delta = "" if s112 is None or s113 is None else str(s113 - s112)
            handle.write(f"| `{name}` | {s112 if s112 is not None else ''} | {s113 if s113 is not None else ''} | {delta} |\n")

        handle.write("\n## Inventory Summary\n\n")
        handle.write(f"- Suspected player-facing English rows in v1.1.2 game assets: `{len(game_rows112)}`.\n")
        handle.write(f"- Suspected player-facing English rows in v1.1.3 game assets: `{len(game_rows113)}`.\n")
        handle.write("- Project translation rows are scanned and appended to the string inventories with `version=project`, but excluded from game-version counts.\n")
        handle.write(f"- New normalized strings in v1.1.3: `{len(new_norms)}`.\n")
        handle.write(f"- Removed normalized strings from v1.1.2: `{len(removed_norms)}`.\n")
        handle.write(f"- v1.1.3 untranslated/needs-context rows including known UI bugs: `{len(untranslated)}`.\n")
        handle.write(f"- Suspicious shifted item mappings: `{len(suspicious)}`.\n\n")

        handle.write("## New v1.1.3 Strings\n\n")
        for norm in new_norms[:80]:
            handle.write(f"- `{escape_preview(by_norm113.get(norm, norm), 220)}`\n")
        if len(new_norms) > 80:
            handle.write(f"- ... {len(new_norms) - 80} more in `docs/string_inventory_v1_1_3.tsv`.\n")

        handle.write("\n## Removed v1.1.2 Strings\n\n")
        for norm in removed_norms[:80]:
            handle.write(f"- `{escape_preview(by_norm112.get(norm, norm), 220)}`\n")
        if len(removed_norms) > 80:
            handle.write(f"- ... {len(removed_norms) - 80} more in `docs/string_inventory_v1_1_2.tsv`.\n")

        handle.write("\n## Mapping Audit\n\n")
        handle.write(
            "- Current translations are primarily source-text dictionary entries, which is safer than raw path_id replacement. "
            "However, existing offline texture payloads and any equal-length byte patch rows are path_id/offset-sensitive and must not be reused blindly for v1.1.3.\n"
        )
        handle.write(
            "- The safer strategy is to map by exact source English text plus neighbouring context: object type, script name, GameObject/object name, same-object nearby strings, and scene/asset file. "
            "Only use path_id/list index/order as diagnostics.\n"
        )
        if suspicious:
            handle.write("- Suspicious moved item mappings and unstable serialized locations:\n")
            for row in suspicious[:30]:
                handle.write(f"  - `{row['asset_file']}` path `{row['path_id']}` `{row['field_path']}`: {row['notes']}\n")
            if len(suspicious) > 30:
                handle.write(f"  - ... {len(suspicious) - 30} more in `docs/item_mapping_audit_v1_1_3.tsv`.\n")
        else:
            handle.write("- No same asset/path_id/field item text changes were found by this scanner; review `docs/item_mapping_audit_v1_1_3.tsv` for moved item locations.\n")

        flare_energy = [
            row for row in mapping
            if "flare" in row["source_text"].casefold()
            or "energy bar" in row["source_text"].casefold()
            or "flare" in row["notes"].casefold()
            or "energy bar" in row["notes"].casefold()
        ]
        if flare_energy:
            handle.write("\n### Flare Gun / Energy Bar Focus\n\n")
            for row in flare_energy[:20]:
                handle.write(f"- `{row['source_text']}` at `{row['asset_file']}` path `{row['path_id']}`: {row['notes']}\n")

        handle.write("\n## Known v0.1.2 UI Bugs Carried Into Audit\n\n")
        for _kind, source, _category, _status, guess, notes in KNOWN_UI_BUGS:
            suffix = f" Recommended text: `{guess}`." if guess else ""
            handle.write(f"- `{source}`: {notes}{suffix}\n")

        handle.write("\n## Recommended Next Translation Fixes\n\n")
        handle.write("- Review `docs/untranslated_inventory_v1_1_3.tsv` by grouped object/file/path_id before editing translations.\n")
        handle.write("- Fix source-text dictionary entries for `Energy Bar`, `Item Broken`, result/search wording, and scuba damage wording first; these do not require path_id assumptions.\n")
        handle.write("- Re-test on a clean v1.1.3 install before claiming v1.1.3 support.\n")
        handle.write("- Do not re-enable runtime texture replacement; keep offline texture work separate and re-audit texture IDs for v1.1.3.\n")


def git_branch_status() -> str:
    import subprocess

    def run(args: list[str]) -> str:
        try:
            return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return ""

    active = run(["git", "branch", "--show-current"])
    head = run(["git", "rev-parse", "HEAD"])
    target = run(["git", "rev-parse", "update-v1.1.3"])
    if active == "update-v1.1.3":
        return "ok: active branch is update-v1.1.3"
    if head and target and head == target:
        return "warning: detached HEAD at same commit as update-v1.1.3, not an active branch"
    return f"failed: active branch is {active or 'DETACHED/unknown'}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-1-2", default=str(DEFAULT_V112))
    parser.add_argument("--v1-1-3", default=str(DEFAULT_V113))
    args = parser.parse_args()

    v112_root = Path(args.v1_1_2)
    v113_root = Path(args.v1_1_3)
    translations = load_translation_map()
    by_norm = normalized_translation_map(translations)

    rows112 = scan_version("v1.1.2", v112_root, translations, by_norm)
    rows113 = scan_version("v1.1.3", v113_root, translations, by_norm)

    project_rows = project_translation_rows(translations)
    rows112.extend(project_rows)
    rows113.extend(project_rows)

    mapping = make_item_mapping_audit(rows112, rows113, translations, by_norm)
    untranslated = make_untranslated_v113(rows113, translations, by_norm)

    write_tsv(ROOT / "docs/string_inventory_v1_1_2.tsv", rows112)
    write_tsv(ROOT / "docs/string_inventory_v1_1_3.tsv", rows113)
    write_tsv(ROOT / "docs/untranslated_inventory_v1_1_3.tsv", untranslated)
    write_tsv(ROOT / "docs/item_mapping_audit_v1_1_3.tsv", mapping)
    write_status(
        ROOT / "docs/v1_1_3_port_status.md",
        v112_root,
        v113_root,
        rows112,
        rows113,
        untranslated,
        mapping,
        git_branch_status(),
    )

    print(f"v1.1.2 suspected rows: {len([row for row in rows112 if row['version'] == 'v1.1.2' and row['category'] != 'technical'])}")
    print(f"v1.1.3 suspected rows: {len([row for row in rows113 if row['version'] == 'v1.1.3' and row['category'] != 'technical'])}")
    print(f"v1.1.3 untranslated/needs-context rows: {len(untranslated)}")
    print(f"suspicious item mappings: {len([row for row in mapping if row['status'] == 'suspicious-mapping'])}")


if __name__ == "__main__":
    main()
