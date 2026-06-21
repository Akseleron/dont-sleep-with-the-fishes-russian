from pathlib import Path
import csv
import shutil
import sys


KEYWORDS = (
    "menu",
    "main",
    "button",
    "btn",
    "journal",
    "diary",
    "book",
    "paper",
    "page",
    "note",
    "junk",
    "item",
    "found",
    "title",
    "logo",
    "cursor",
    "hand",
    "map",
    "back",
    "yes",
    "no",
    "close",
    "ui",
)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: select_texture_candidates.py <texture_index.tsv> <out_dir>")

    index = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not index.exists():
        raise SystemExit(f"missing index: {index}")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "candidate_index.tsv"

    copied = 0
    rows_out = []
    exported_rows = []
    with index.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            exported = row.get("exported", "")
            if not exported:
                continue
            exported_rows.append(row)
            haystack = " ".join(
                [
                    row.get("asset_file", ""),
                    row.get("type", ""),
                    row.get("name", ""),
                    exported,
                ]
            ).casefold()
            matched = [keyword for keyword in KEYWORDS if keyword in haystack]
            if not matched:
                continue

            rows_out.append((row, matched))

    if not rows_out:
        # Some Unity exports have mostly unnamed textures. In that case, prepare
        # a usable redraw bundle by copying the full PNG export and marking it as
        # a fallback selection in the manifest.
        rows_out = [(row, ["fallback_all_unnamed_export"]) for row in exported_rows]

    manifest_rows = []
    for row, matched in rows_out:
        src = Path(row.get("exported", ""))
        if not src.exists():
            continue
        dst = out_dir / src.name
        if dst.exists():
            stem = dst.stem
            suffix = dst.suffix
            i = 2
            while dst.exists():
                dst = out_dir / f"{stem}__dup{i}{suffix}"
                i += 1
        shutil.copy2(src, dst)
        copied += 1
        manifest_rows.append(
            {
                "candidate_file": str(dst),
                "matched_keywords": ",".join(matched),
                "asset_file": row.get("asset_file", ""),
                "type": row.get("type", ""),
                "name": row.get("name", ""),
                "path_id": row.get("path_id", ""),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "source_png": row.get("exported", ""),
            }
        )

    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_file",
                "matched_keywords",
                "asset_file",
                "type",
                "name",
                "path_id",
                "width",
                "height",
                "source_png",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"candidates={copied}")
    print(f"manifest={manifest}")
    print(f"out_dir={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
