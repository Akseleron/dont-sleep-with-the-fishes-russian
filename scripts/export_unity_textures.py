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
INDEX = OUT / "texture_index.tsv"

IMG_DIR.mkdir(parents=True, exist_ok=True)

def safe_name(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9А-Яа-яЁё._-]+", "_", s)
    return s[:160] or "unnamed"

asset_files = []
for pattern in ("*.assets", "*.bundle"):
    asset_files.extend(ROOT.rglob(pattern))

rows = []
exported = 0
failed = 0

for asset_path in sorted(asset_files):
    try:
        env = UnityPy.load(str(asset_path))
    except Exception as e:
        rows.append({
            "asset_file": str(asset_path),
            "type": "LOAD_FAILED",
            "name": "",
            "path_id": "",
            "width": "",
            "height": "",
            "exported": "",
            "error": str(e),
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
                "asset_file": str(asset_path),
                "type": type_name,
                "name": "",
                "path_id": str(obj.path_id),
                "width": "",
                "height": "",
                "exported": "",
                "error": f"READ_FAILED: {e}",
            })
            continue

        name = getattr(data, "name", "") or f"unnamed_{obj.path_id}"
        width = getattr(data, "width", "")
        height = getattr(data, "height", "")

        out_path = ""
        error = ""

        try:
            img = getattr(data, "image", None)
            if img:
                filename = f"{safe_name(asset_path.stem)}__{type_name}__{obj.path_id}__{safe_name(name)}.png"
                target = IMG_DIR / filename
                img.save(target)
                out_path = str(target)
                exported += 1
        except Exception as e:
            failed += 1
            error = f"EXPORT_FAILED: {e}"

        rows.append({
            "asset_file": str(asset_path),
            "type": type_name,
            "name": name,
            "path_id": str(obj.path_id),
            "width": width,
            "height": height,
            "exported": out_path,
            "error": error,
        })

with INDEX.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(
        f,
        fieldnames=["asset_file", "type", "name", "path_id", "width", "height", "exported", "error"],
        delimiter="\t",
    )
    w.writeheader()
    w.writerows(rows)

print(f"asset_files={len(asset_files)}")
print(f"rows={len(rows)}")
print(f"exported={exported}")
print(f"failed={failed}")
print(f"index={INDEX}")
print(f"images={IMG_DIR}")
