#!/usr/bin/env python3
"""Dump readable Unity object context for DSWF game versions.

The output is intentionally local and bulky. It belongs under .local_dumps/
and should not be committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import UnityPy  # type: ignore
except ImportError as exc:  # pragma: no cover - user-facing dependency check
    raise SystemExit(
        "UnityPy is required. Run with "
        "/home/akseleron/projects/dswf-rus/.venv-tools/bin/python"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR_NAME = "DontSleepWithTheFishes_Data"
DEFAULT_VERSIONS = {
    "v1_1_2": Path("/mnt/shared/Games/DontSleepWithTheFishes_v1_1_2"),
    "v1_1_3": Path(
        "/mnt/shared/Games/DontSleepWithTheFishes_v1_1_3/"
        "DontSleepWithTheFishes_v1_1_3_ItchRelease"
    ),
}
SCAN_FILES = {
    "globalgamemanagers.assets",
    "resources.assets",
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
}
INDEX_COLUMNS = [
    "version",
    "asset_file",
    "object_type",
    "path_id",
    "object_name",
    "script_name",
    "gameobject_name",
    "container",
    "byte_start",
    "byte_size",
    "dump_rel_path",
    "string_count",
    "notes",
]
READABLE_TYPES = {"MonoBehaviour", "ScriptableObject", "GameObject"}
TEXTMESH_SCRIPTS = {
    "Unity.TextMeshPro:TMPro.TextMeshPro",
    "Unity.TextMeshPro:TMPro.TextMeshProUGUI",
}


@dataclass
class DumpRow:
    version: str
    asset_file: str
    object_type: str
    path_id: str
    object_name: str = ""
    script_name: str = ""
    gameobject_name: str = ""
    container: str = ""
    byte_start: str = ""
    byte_size: str = ""
    dump_rel_path: str = ""
    string_count: str = "0"
    notes: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "asset_file": self.asset_file,
            "object_type": self.object_type,
            "path_id": self.path_id,
            "object_name": self.object_name,
            "script_name": self.script_name,
            "gameobject_name": self.gameobject_name,
            "container": self.container,
            "byte_start": self.byte_start,
            "byte_size": self.byte_size,
            "dump_rel_path": self.dump_rel_path,
            "string_count": self.string_count,
            "notes": self.notes,
        }


def slug(text: str, fallback: str = "unnamed") -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip())[:80].strip("._")
    return text or fallback


def safe_typetree(obj: Any) -> dict[str, Any] | None:
    try:
        tree = obj.read_typetree(check_read=False)
    except Exception:
        try:
            tree = obj.read_typetree()
        except Exception:
            return None
    return tree if isinstance(tree, dict) else None


def safe_name_from_tree(tree: dict[str, Any] | None) -> str:
    if not isinstance(tree, dict):
        return ""
    return str(tree.get("m_Name", "") or "")


def decode_text_asset_payload(obj: Any) -> str:
    try:
        data = obj.read()
    except Exception:
        return ""
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
        for key, item in value.items():
            yield from recursive_strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from recursive_strings(item, f"{path}[{index}]")


def valid_text(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text or "\x00" in text:
        return None
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text)
    if printable / max(len(text), 1) < 0.95:
        return None
    return text


def iter_len_prefixed_strings(raw: bytes, max_len: int = 4096) -> Iterable[dict[str, Any]]:
    for rel_len_offset in range(0, max(0, len(raw) - 4)):
        size = int.from_bytes(raw[rel_len_offset : rel_len_offset + 4], "little")
        if size <= 0 or size > max_len:
            continue
        start = rel_len_offset + 4
        end = start + size
        if end > len(raw):
            continue
        text = valid_text(raw[start:end])
        if text is None:
            continue
        yield {"relative_offset": start, "length": size, "string": text}


def sanitize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"__bytes_len__": len(value), "preview_hex": value[:64].hex()}
    if isinstance(value, dict):
        return {str(key): sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json(item) for item in value]
    if hasattr(value, "path_id"):
        return {"__unity_ref__": str(value), "path_id": getattr(value, "path_id", "")}
    return str(value)


def get_script_map(env: Any) -> dict[int, str]:
    scripts: dict[int, str] = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            data = obj.read()
        except Exception:
            continue
        namespace = getattr(data, "m_Namespace", "") or ""
        class_name = getattr(data, "m_ClassName", "") or ""
        assembly = getattr(data, "m_AssemblyName", "") or ""
        if not class_name:
            continue
        full_name = f"{namespace}.{class_name}" if namespace else class_name
        scripts[int(obj.path_id)] = f"{assembly}:{full_name}"
    return scripts


def get_gameobject_names(env: Any) -> dict[tuple[str, int], str]:
    names: dict[tuple[str, int], str] = {}
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        tree = safe_typetree(obj)
        names[(obj.assets_file.name, int(obj.path_id))] = safe_name_from_tree(tree)
    return names


def script_and_gameobject(
    obj: Any,
    tree: dict[str, Any] | None,
    script_map: dict[int, str],
    gameobject_names: dict[tuple[str, int], str],
) -> tuple[str, str]:
    if not isinstance(tree, dict):
        return "", ""
    script_name = ""
    script_ref = tree.get("m_Script", {})
    script_id = script_ref.get("m_PathID") if isinstance(script_ref, dict) else None
    if script_id:
        script_name = script_map.get(int(script_id), f"unknown:{script_id}")
    gameobject_name = ""
    gameobject_ref = tree.get("m_GameObject", {})
    gameobject_id = gameobject_ref.get("m_PathID") if isinstance(gameobject_ref, dict) else None
    if gameobject_id:
        gameobject_name = gameobject_names.get((obj.assets_file.name, int(gameobject_id)), "")
    return script_name, gameobject_name


def dump_path_for(out_dir: Path, obj: Any, object_name: str, suffix: str) -> Path:
    asset_part = slug(obj.assets_file.name)
    type_part = slug(obj.type.name)
    name_part = slug(object_name)
    return out_dir / asset_part / type_part / f"{obj.path_id}__{name_part}{suffix}"


def texture_metadata(obj: Any, tree: dict[str, Any] | None, object_name: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "object_type": obj.type.name,
        "path_id": obj.path_id,
        "name": object_name,
        "asset_file": obj.assets_file.name,
    }
    if isinstance(tree, dict):
        for key in ["m_Width", "m_Height", "m_TextureFormat", "m_IsReadable", "m_Rect", "m_RD"]:
            if key in tree:
                metadata[key] = sanitize_json(tree[key])
    return metadata


def dump_version(version: str, game_root: Path, out_root: Path) -> None:
    data_dir = game_root / DATA_DIR_NAME
    if not data_dir.exists():
        raise SystemExit(f"Unity data directory not found: {data_dir}")

    out_dir = out_root / version
    out_dir.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(data_dir))
    script_map = get_script_map(env)
    gameobject_names = get_gameobject_names(env)

    rows: list[DumpRow] = []
    wanted_files = {name for name in SCAN_FILES if (data_dir / name).exists()}
    for obj in env.objects:
        asset_file = obj.assets_file.name
        if asset_file not in wanted_files:
            continue
        object_type = obj.type.name
        tree = safe_typetree(obj)
        object_name = safe_name_from_tree(tree)
        script_name, gameobject_name = script_and_gameobject(obj, tree, script_map, gameobject_names)
        notes: list[str] = []
        dump_path: Path | None = None
        string_values: list[str] = []

        if tree is not None:
            string_values.extend(text for _path, text in recursive_strings(tree) if text)

        raw_strings: list[dict[str, Any]] = []
        if object_type == "MonoBehaviour":
            try:
                raw = obj.get_raw_data()
            except Exception:
                raw = b""
            raw_strings = list(iter_len_prefixed_strings(raw))
            string_values.extend(item["string"] for item in raw_strings)
            if raw_strings:
                notes.append(f"raw_length_prefixed_strings={len(raw_strings)}")

        if object_type == "TextAsset":
            payload = decode_text_asset_payload(obj)
            dump_path = dump_path_for(out_dir, obj, object_name, ".txt")
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(payload, encoding="utf-8", newline="\n")
            string_values.append(payload)
            notes.append("textasset_payload_dump")
        elif object_type in READABLE_TYPES or script_name in TEXTMESH_SCRIPTS:
            if tree is not None:
                dump_path = dump_path_for(out_dir, obj, object_name or gameobject_name, ".json")
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "_context": {
                        "version": version,
                        "asset_file": asset_file,
                        "object_type": object_type,
                        "path_id": obj.path_id,
                        "object_name": object_name,
                        "script_name": script_name,
                        "gameobject_name": gameobject_name,
                        "byte_start": getattr(obj, "byte_start", ""),
                        "byte_size": getattr(obj, "byte_size", ""),
                    },
                    "typetree": sanitize_json(tree),
                    "raw_length_prefixed_strings": sanitize_json(raw_strings),
                }
                dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                notes.append("typetree_json_dump")
            elif raw_strings:
                dump_path = dump_path_for(out_dir, obj, object_name or gameobject_name, ".json")
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "_context": {
                        "version": version,
                        "asset_file": asset_file,
                        "object_type": object_type,
                        "path_id": obj.path_id,
                        "object_name": object_name,
                        "script_name": script_name,
                        "gameobject_name": gameobject_name,
                    },
                    "raw_length_prefixed_strings": sanitize_json(raw_strings),
                }
                dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                notes.append("raw_strings_json_dump")
        elif object_type in {"Texture2D", "Sprite"}:
            dump_path = dump_path_for(out_dir, obj, object_name, ".metadata.json")
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(
                json.dumps(texture_metadata(obj, tree, object_name), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            notes.append("texture_sprite_metadata_only")

        rel_dump = ""
        if dump_path is not None:
            rel_dump = str(dump_path.relative_to(out_dir))

        rows.append(
            DumpRow(
                version=version,
                asset_file=asset_file,
                object_type=object_type,
                path_id=str(obj.path_id),
                object_name=object_name,
                script_name=script_name,
                gameobject_name=gameobject_name,
                container=str(getattr(obj, "container", "") or ""),
                byte_start=str(getattr(obj, "byte_start", "") or ""),
                byte_size=str(getattr(obj, "byte_size", "") or ""),
                dump_rel_path=rel_dump,
                string_count=str(sum(1 for value in string_values if isinstance(value, str) and value.strip())),
                notes="; ".join(notes),
            )
        )

    index_path = out_dir / "object_index.tsv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (item.asset_file, item.object_type, int(item.path_id))):
            writer.writerow(row.as_dict())
    print(f"{version}: indexed {len(rows)} objects -> {index_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(ROOT / ".local_dumps/unity_readable"))
    parser.add_argument("--v1-1-2", default=str(DEFAULT_VERSIONS["v1_1_2"]))
    parser.add_argument("--v1-1-3", default=str(DEFAULT_VERSIONS["v1_1_3"]))
    args = parser.parse_args()

    versions = {
        "v1_1_2": Path(args.v1_1_2),
        "v1_1_3": Path(args.v1_1_3),
    }
    out_root = Path(args.out_root)
    for version, root in versions.items():
        dump_version(version, root, out_root)


if __name__ == "__main__":
    main()
