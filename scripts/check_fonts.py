#!/usr/bin/env python3
"""Report Unity and TextMeshPro font assets and their declared character ranges."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    import UnityPy
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "UnityPy is required. Create a venv and install it with: "
        "python3 -m venv .venv && .venv/bin/pip install UnityPy"
    ) from exc


TMP_FONT_ASSET_SCRIPT_ID = 1183


def len_prefixed_strings(raw: bytes) -> list[str]:
    strings: list[str] = []
    for offset in range(max(0, len(raw) - 4)):
        size = int.from_bytes(raw[offset : offset + 4], "little")
        if size <= 0 or size > 256 or offset + 4 + size > len(raw):
            continue
        data = raw[offset + 4 : offset + 4 + size]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if text and all(ch.isprintable() or ch in "\n\r\t" for ch in text):
            strings.append(text)
    return strings


def has_cyrillic_range(range_text: str) -> bool:
    # Cyrillic block starts at U+0400 (1024). TMP reports decimal ranges.
    return any(token.strip().startswith(("1024", "1025", "104", "105", "11")) for token in range_text.split(","))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="game_work/DontSleepWithTheFishes_Data")
    parser.add_argument("--out", default="extracted/font_report.tsv")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(args.data_dir)

    rows: list[dict[str, str]] = []
    for obj in env.objects:
        if obj.type.name == "Font":
            data = obj.read()
            font_data = getattr(data, "m_FontData", b"") or b""
            rows.append(
                {
                    "file": obj.assets_file.name,
                    "path_id": str(obj.path_id),
                    "type": "Font",
                    "name": data.m_Name,
                    "source_font": "",
                    "style": "",
                    "character_ranges": "",
                    "likely_cyrillic": "unknown" if font_data else "no embedded font data",
                    "embedded_font_bytes": str(len(font_data)),
                }
            )

        if obj.type.name != "MonoBehaviour":
            continue
        try:
            header = obj.read_typetree(check_read=False)
        except Exception:
            continue
        if header.get("m_Script", {}).get("m_PathID") != TMP_FONT_ASSET_SCRIPT_ID:
            continue
        strings = len_prefixed_strings(obj.get_raw_data())
        name = header.get("m_Name", "")
        source_font = strings[2] if len(strings) > 2 else ""
        style = strings[3] if len(strings) > 3 else ""
        ranges = next((s for s in strings if " - " in s and any(ch.isdigit() for ch in s)), "")
        rows.append(
            {
                "file": obj.assets_file.name,
                "path_id": str(obj.path_id),
                "type": "TMP_FontAsset",
                "name": name,
                "source_font": source_font,
                "style": style,
                "character_ranges": ranges,
                "likely_cyrillic": "yes" if has_cyrillic_range(ranges) else "no",
                "embedded_font_bytes": "",
            }
        )

    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file",
                "path_id",
                "type",
                "name",
                "source_font",
                "style",
                "character_ranges",
                "likely_cyrillic",
                "embedded_font_bytes",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} font rows to {out_path}")


if __name__ == "__main__":
    main()
