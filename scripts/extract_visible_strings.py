#!/usr/bin/env python3
"""Extract likely visible strings from Unity IL2CPP serialized files.

This script uses UnityPy only for object boundaries and standard object headers.
Custom IL2CPP MonoBehaviour fields are stripped, so visible text fields are
identified from their serialized byte layout.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

try:
    import UnityPy
except ImportError as exc:  # pragma: no cover - user-facing dependency check
    raise SystemExit(
        "UnityPy is required. Create a venv and install it with: "
        "python3 -m venv .venv && .venv/bin/pip install UnityPy"
    ) from exc


DEFAULT_FILES = (
    "level0",
    "level1",
    "level2",
    "level3",
    "level4",
    "level5",
    "resources.assets",
    "sharedassets0.assets",
    "sharedassets1.assets",
    "sharedassets2.assets",
    "sharedassets3.assets",
    "sharedassets4.assets",
    "sharedassets5.assets",
)

TMP_TEXT_SCRIPTS = {
    "Unity.TextMeshPro:TMPro.TextMeshProUGUI",
    "Unity.TextMeshPro:TMPro.TextMeshPro",
}


def valid_utf8_string(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text)
    if printable != len(text):
        return None
    return text


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
    text = valid_utf8_string(raw[start:end])
    if text is None:
        return None
    return size, text


def iter_len_prefixed_strings(raw: bytes) -> Iterable[tuple[int, int, str]]:
    for rel_len_offset in range(0, max(0, len(raw) - 4)):
        parsed = read_len_prefixed(raw, rel_len_offset)
        if parsed is None:
            continue
        size, text = parsed
        yield rel_len_offset, size, text


def likely_visible_candidate(text: str) -> bool:
    if len(text.strip()) < 2:
        return False
    if "_" in text and " " not in text:
        return False
    if len(text) > 1 and text.islower() and " " not in text:
        return False
    if all(ch.isdigit() or ch in ".:%xX- " for ch in text):
        return False
    return any(ch.isalpha() for ch in text)


def get_script_map(env) -> dict[int, str]:
    scripts: dict[int, str] = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript" or obj.assets_file.name != "globalgamemanagers.assets":
            continue
        data = obj.read()
        namespace = data.m_Namespace
        class_name = f"{namespace}.{data.m_ClassName}" if namespace else data.m_ClassName
        scripts[obj.path_id] = f"{data.m_AssemblyName}:{class_name}"
    return scripts


def get_gameobject_names(env) -> dict[tuple[str, int], str]:
    names: dict[tuple[str, int], str] = {}
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        try:
            data = obj.read_typetree(check_read=False)
        except Exception:
            continue
        names[(obj.assets_file.name, obj.path_id)] = data.get("m_Name", "")
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="game_work/DontSleepWithTheFishes_Data")
    parser.add_argument("--out", default="extracted/visible_strings.tsv")
    parser.add_argument("--files", nargs="*", default=list(DEFAULT_FILES))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    env = UnityPy.load(str(data_dir))
    script_map = get_script_map(env)
    gameobject_names = get_gameobject_names(env)
    wanted_files = {name for name in args.files if (data_dir / name).exists()}

    rows: list[dict[str, object]] = []
    seen: set[tuple[str, int, int, str]] = set()

    for obj in env.objects:
        file_name = obj.assets_file.name
        if file_name not in wanted_files or obj.type.name != "MonoBehaviour":
            continue
        try:
            header = obj.read_typetree(check_read=False)
        except Exception:
            continue
        script_path_id = header.get("m_Script", {}).get("m_PathID")
        script = script_map.get(script_path_id, f"unknown:{script_path_id}")
        gameobject_path_id = header.get("m_GameObject", {}).get("m_PathID", 0)
        gameobject_name = gameobject_names.get((file_name, gameobject_path_id), "")
        raw = obj.get_raw_data()

        if script in TMP_TEXT_SCRIPTS:
            parsed = read_len_prefixed(raw, 88)
            if parsed is not None:
                size, text = parsed
                rows.append(
                    {
                        "source": text,
                        "file": file_name,
                        "byte_offset": obj.byte_start + 92,
                        "length": size,
                        "object_path_id": obj.path_id,
                        "script": script,
                        "gameobject_path_id": gameobject_path_id,
                        "gameobject_name": gameobject_name,
                        "kind": "tmp_m_text",
                    }
                )
            continue

        for rel_len_offset, size, text in iter_len_prefixed_strings(raw):
            if rel_len_offset < 28 or not likely_visible_candidate(text):
                continue
            key = (file_name, obj.path_id, obj.byte_start + rel_len_offset + 4, text)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source": text,
                    "file": file_name,
                    "byte_offset": obj.byte_start + rel_len_offset + 4,
                    "length": size,
                    "object_path_id": obj.path_id,
                    "script": script,
                    "gameobject_path_id": gameobject_path_id,
                    "gameobject_name": gameobject_name,
                    "kind": "mono_string_candidate",
                }
            )

    rows.sort(key=lambda row: (str(row["file"]), int(row["byte_offset"]), str(row["source"])))
    fieldnames = [
        "source",
        "file",
        "byte_offset",
        "length",
        "object_path_id",
        "script",
        "gameobject_path_id",
        "gameobject_name",
        "kind",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    unique = len({row["source"] for row in rows})
    print(f"wrote {len(rows)} rows ({unique} unique strings) to {out_path}")


if __name__ == "__main__":
    main()
