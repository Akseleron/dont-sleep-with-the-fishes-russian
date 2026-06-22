#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import UnityPy  # type: ignore
except ImportError as exc:
    raise SystemExit(
        "UnityPy is required. Use .venv-tools/bin/python scripts/inventory_unity_textures.py "
        "or install UnityPy in the active environment."
    ) from exc

try:
    from PIL import Image  # type: ignore
except ImportError as exc:
    raise SystemExit("Pillow is required for PNG inventory.") from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "game_runtime_test" / "DontSleepWithTheFishes_Data"
DEFAULT_OUT = ROOT / "debug_reports" / "unity_texture_asset_inventory.tsv"
PNG_RE = re.compile(r"^(?P<asset>sharedassets\d+)__(?P<type>Texture2D|Sprite)__(?P<path_id>\d+)__(?P<name>.+)\.png$")


@dataclass(frozen=True)
class ReplacementPng:
    path: Path
    asset_stem: str
    object_type: str
    path_id: int
    name: str
    width: int
    height: int
    mode: str
    alpha_min: int | str
    alpha_max: int | str
    transparent_pixels: int | str
    semi_transparent_pixels: int | str
    opaque_pixels: int | str
    sha256: str


def find_default_replacement_dir() -> Path | None:
    candidates = [
        Path.home() / "Downloads" / "fish3",
        Path.home() / "Загрузки" / "fish3",
        ROOT / "_manual" / "fish3",
        ROOT / "_manual" / "fish2",
    ]
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("*.png")):
            return candidate
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def png_alpha_stats(path: Path) -> tuple[int, int, int, int, int]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        values = list(alpha.getdata())
    transparent = sum(1 for value in values if value == 0)
    opaque = sum(1 for value in values if value == 255)
    semi = len(values) - transparent - opaque
    return min(values), max(values), transparent, semi, opaque


def load_replacements(directory: Path) -> dict[tuple[str, str, int], ReplacementPng]:
    rows: dict[tuple[str, str, int], ReplacementPng] = {}
    for path in sorted(directory.glob("*.png")):
        match = PNG_RE.match(path.name)
        if not match:
            continue
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
        alpha_min: int | str
        alpha_max: int | str
        transparent: int | str
        semi: int | str
        opaque: int | str
        if "A" in Image.open(path).getbands() or mode in {"LA", "RGBA"}:
            alpha_min, alpha_max, transparent, semi, opaque = png_alpha_stats(path)
        else:
            alpha_min, alpha_max, transparent, semi, opaque = "", "", "", "", width * height
        repl = ReplacementPng(
            path=path,
            asset_stem=match.group("asset"),
            object_type=match.group("type"),
            path_id=int(match.group("path_id")),
            name=match.group("name"),
            width=width,
            height=height,
            mode=mode,
            alpha_min=alpha_min,
            alpha_max=alpha_max,
            transparent_pixels=transparent,
            semi_transparent_pixels=semi,
            opaque_pixels=opaque,
            sha256=sha256_file(path),
        )
        rows[(repl.asset_stem, repl.object_type, repl.path_id)] = repl
    return rows


def texture_format_name(value: object) -> str:
    if value is None:
        return ""
    try:
        name = getattr(value, "name")
        if name:
            return f"{int(value)}:{name}"
    except Exception:
        pass
    return str(value)


def stream_info(data: object) -> tuple[str, str, str]:
    stream = getattr(data, "m_StreamData", None)
    if not stream:
        return "", "", ""
    return str(getattr(stream, "path", "") or ""), str(getattr(stream, "offset", "") or ""), str(getattr(stream, "size", "") or "")


def inventory(data_dir: Path, replacement_dir: Path, out_path: Path) -> list[dict[str, str]]:
    replacements = load_replacements(replacement_dir)
    rows: list[dict[str, str]] = []
    target_asset_files = sorted({f"{asset}.assets" for asset, typ, _ in replacements if typ == "Texture2D"})
    for asset_file in target_asset_files:
        asset_path = data_dir / asset_file
        if not asset_path.exists():
            rows.append({
                "assets_file": asset_file,
                "asset_type": "Texture2D",
                "path_id": "",
                "unity_name": "",
                "width": "",
                "height": "",
                "texture_format": "",
                "image_data_size": "",
                "stream_path": "",
                "stream_offset": "",
                "stream_size": "",
                "matching_replacement_png": "",
                "replacement_width": "",
                "replacement_height": "",
                "replacement_mode": "",
                "replacement_alpha_min": "",
                "replacement_alpha_max": "",
                "replacement_transparent_pixels": "",
                "replacement_semi_transparent_pixels": "",
                "replacement_opaque_pixels": "",
                "replacement_sha256": "",
                "status": "missing_assets_file",
            })
            continue
        env = UnityPy.load(str(asset_path))
        seen: set[tuple[str, str, int]] = set()
        for obj in env.objects:
            if obj.type.name != "Texture2D":
                continue
            key = (asset_path.stem, "Texture2D", int(obj.path_id))
            if key not in replacements:
                continue
            seen.add(key)
            repl = replacements[key]
            try:
                data = obj.read()
                width = int(getattr(data, "m_Width", 0) or 0)
                height = int(getattr(data, "m_Height", 0) or 0)
                stream_path, stream_offset, stream_size = stream_info(data)
                image_data = getattr(data, "image_data", b"") or b""
                status = "match" if (width, height) == (repl.width, repl.height) else "size_mismatch"
                rows.append({
                    "assets_file": asset_file,
                    "asset_type": "Texture2D",
                    "path_id": str(obj.path_id),
                    "unity_name": str(getattr(data, "m_Name", "") or ""),
                    "width": str(width),
                    "height": str(height),
                    "texture_format": texture_format_name(getattr(data, "m_TextureFormat", "")),
                    "image_data_size": str(len(image_data)),
                    "stream_path": stream_path,
                    "stream_offset": stream_offset,
                    "stream_size": stream_size,
                    "matching_replacement_png": str(repl.path),
                    "replacement_width": str(repl.width),
                    "replacement_height": str(repl.height),
                    "replacement_mode": repl.mode,
                    "replacement_alpha_min": str(repl.alpha_min),
                    "replacement_alpha_max": str(repl.alpha_max),
                    "replacement_transparent_pixels": str(repl.transparent_pixels),
                    "replacement_semi_transparent_pixels": str(repl.semi_transparent_pixels),
                    "replacement_opaque_pixels": str(repl.opaque_pixels),
                    "replacement_sha256": repl.sha256,
                    "status": status,
                })
            except Exception as exc:
                rows.append({
                    "assets_file": asset_file,
                    "asset_type": "Texture2D",
                    "path_id": str(obj.path_id),
                    "unity_name": "",
                    "width": "",
                    "height": "",
                    "texture_format": "",
                    "image_data_size": "",
                    "stream_path": "",
                    "stream_offset": "",
                    "stream_size": "",
                    "matching_replacement_png": str(repl.path),
                    "replacement_width": str(repl.width),
                    "replacement_height": str(repl.height),
                    "replacement_mode": repl.mode,
                    "replacement_alpha_min": str(repl.alpha_min),
                    "replacement_alpha_max": str(repl.alpha_max),
                    "replacement_transparent_pixels": str(repl.transparent_pixels),
                    "replacement_semi_transparent_pixels": str(repl.semi_transparent_pixels),
                    "replacement_opaque_pixels": str(repl.opaque_pixels),
                    "replacement_sha256": repl.sha256,
                    "status": "read_error:" + type(exc).__name__ + ":" + str(exc),
                })
        for key, repl in replacements.items():
            asset, typ, path_id = key
            if typ != "Texture2D" or asset_file != f"{asset}.assets" or key in seen:
                continue
            rows.append({
                "assets_file": asset_file,
                "asset_type": "Texture2D",
                "path_id": str(path_id),
                "unity_name": "",
                "width": "",
                "height": "",
                "texture_format": "",
                "image_data_size": "",
                "stream_path": "",
                "stream_offset": "",
                "stream_size": "",
                "matching_replacement_png": str(repl.path),
                "replacement_width": str(repl.width),
                "replacement_height": str(repl.height),
                "replacement_mode": repl.mode,
                "replacement_alpha_min": str(repl.alpha_min),
                "replacement_alpha_max": str(repl.alpha_max),
                "replacement_transparent_pixels": str(repl.transparent_pixels),
                "replacement_semi_transparent_pixels": str(repl.semi_transparent_pixels),
                "replacement_opaque_pixels": str(repl.opaque_pixels),
                "replacement_sha256": repl.sha256,
                "status": "missing_target",
            })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "assets_file", "asset_type", "path_id", "unity_name", "width", "height",
        "texture_format", "image_data_size", "stream_path", "stream_offset", "stream_size",
        "matching_replacement_png", "replacement_width", "replacement_height", "replacement_mode",
        "replacement_alpha_min", "replacement_alpha_max", "replacement_transparent_pixels",
        "replacement_semi_transparent_pixels", "replacement_opaque_pixels", "replacement_sha256", "status",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    default_replacement_dir = find_default_replacement_dir()
    parser = argparse.ArgumentParser(description="Inventory DSWF Unity Texture2D replacement targets.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--replacement-dir", type=Path, default=default_replacement_dir)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.replacement_dir is None:
        raise SystemExit("replacement directory not found; pass --replacement-dir")
    rows = inventory(args.data_dir, args.replacement_dir, args.out)
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    print(f"wrote {len(rows)} rows to {args.out}")
    for status, count in sorted(statuses.items()):
        print(status, count)


if __name__ == "__main__":
    main()
