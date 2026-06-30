#!/usr/bin/env python3

from pathlib import Path
import csv
import re
import sys

import UnityPy

if len(sys.argv) != 3:
    raise SystemExit("usage: export_unity_textures.py <DontSleepWithTheFishes_Data> <out_dir>")

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
IMG_DIR = OUT / "images"
MANIFEST = OUT / "manifest.tsv"
LEGACY_INDEX = OUT / "texture_index.tsv"

IMG_DIR.mkdir(parents=True, exist_ok=True)

def safe_name(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9А-Яа-яЁё._-]+", "_", s)
    return s[:160] or "unnamed"

def texture_format(data: object) -> str:
    for attr in ("m_TextureFormat", "texture_format", "format"):
        value = getattr(data, attr, None)
        if value is None:
            continue
        name = getattr(value, "name", "")
        if name:
            return name
        return str(value)
    return ""

asset_files = set()
for pattern in ("*.assets", "*.bundle", "level*"):
    for path in ROOT.rglob(pattern):
        if path.is_file():
            asset_files.add(path)

rows = []
exported = 0
failed = 0

for asset_path in sorted(asset_files):
    source_asset_file = str(asset_path.relative_to(ROOT))
    try:
        env = UnityPy.load(str(asset_path))
    except Exception as e:
        rows.append({
            "exported_file": "",
            "source_asset_file": source_asset_file,
            "asset_name": "",
            "path_id": "",
            "type": "LOAD_FAILED",
            "width": "",
            "height": "",
            "format": "",
            "notes": f"LOAD_FAILED: {e}",
        })
        continue

    for obj in env.objects:
        type_name = obj.type.name
        if type_name not in {"Texture2D", "Sprite"}:
            continue

        try:
            data = obj.read()
        except Exception as e:
            failed += 1
            rows.append({
                "exported_file": "",
                "source_asset_file": source_asset_file,
                "asset_name": "",
                "path_id": str(obj.path_id),
                "type": type_name,
                "width": "",
                "height": "",
                "format": "",
                "notes": f"READ_FAILED: {e}",
            })
            continue

        name = getattr(data, "name", "") or f"unnamed_{obj.path_id}"
        width = getattr(data, "width", "")
        height = getattr(data, "height", "")
        fmt = texture_format(data)

        out_path = ""
        notes = ""

        try:
            img = getattr(data, "image", None)
            if img:
                if not width or not height:
                    width, height = img.size
                filename = f"{safe_name(asset_path.stem)}__{type_name}__{obj.path_id}__{safe_name(name)}.png"
                target = IMG_DIR / filename
                img.save(target)
                out_path = str(target.relative_to(OUT))
                exported += 1
            else:
                notes = "NO_IMAGE"
        except Exception as e:
            failed += 1
            notes = f"EXPORT_FAILED: {e}"

        rows.append({
            "exported_file": out_path,
            "source_asset_file": source_asset_file,
            "asset_name": name,
            "path_id": str(obj.path_id),
            "type": type_name,
            "width": width,
            "height": height,
            "format": fmt,
            "notes": notes,
        })

fieldnames = ["exported_file", "source_asset_file", "asset_name", "path_id", "type", "width", "height", "format", "notes"]
for index_path in (MANIFEST, LEGACY_INDEX):
    with index_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
        )
        w.writeheader()
        w.writerows(rows)

print(f"asset_files={len(asset_files)}")
print(f"rows={len(rows)}")
print(f"exported={exported}")
print(f"failed={failed}")
print(f"manifest={MANIFEST}")
print(f"legacy_index={LEGACY_INDEX}")
print(f"images={IMG_DIR}")
