#!/usr/bin/env python3
"""Apply byte-length-preserving test translations to game_work only."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


OFFSET_RE = re.compile(r"(?:^|;)offset=(\d+)(?:;|$)")


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_offset(context: str) -> int:
    match = OFFSET_RE.search(context)
    if not match:
        raise ValueError(f"context lacks offset=<number>: {context!r}")
    return int(match.group(1))


def assert_inside(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents and resolved != root_resolved:
        raise ValueError(f"refusing to modify outside {root_resolved}: {resolved}")


def backup_file(target: Path, backup_root: Path, game_work: Path) -> Path:
    rel = target.resolve().relative_to(game_work.resolve())
    backup = backup_root / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(target, backup)
    return backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--translations", default="translations/ru.tsv")
    parser.add_argument("--game-work", default="game_work")
    parser.add_argument("--backup-root", default="patches/backups/game_work")
    parser.add_argument("--changelog", default="patches/changelog.tsv")
    parser.add_argument("--status", default="test")
    args = parser.parse_args()

    root = workspace_root()
    game_work = (root / args.game_work).resolve()
    backup_root = root / args.backup_root
    changelog = root / args.changelog
    translations = root / args.translations

    assert_inside(game_work, root / "game_work")
    rows: list[dict[str, str]] = []
    with translations.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"source", "russian", "context", "file", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"missing required columns in {translations}: {sorted(missing)}")
        for row in reader:
            if row.get("status") == args.status and row.get("russian"):
                rows.append(row)

    if not rows:
        raise SystemExit(f"no rows with status={args.status!r} found in {translations}")

    applied: list[dict[str, str]] = []
    for row in rows:
        target = (game_work / row["file"]).resolve()
        assert_inside(target, game_work)
        if not target.exists():
            raise FileNotFoundError(target)
        source_bytes = row["source"].encode("utf-8")
        russian_bytes = row["russian"].encode("utf-8")
        if len(source_bytes) != len(russian_bytes):
            raise ValueError(
                f"refusing non-equal byte length patch for {row['source']!r}: "
                f"{len(source_bytes)} != {len(russian_bytes)}"
            )
        offset = parse_offset(row["context"])
        data = bytearray(target.read_bytes())
        actual = bytes(data[offset : offset + len(source_bytes)])
        if actual != source_bytes:
            raise ValueError(
                f"source mismatch in {target} at {offset}: "
                f"expected {source_bytes!r}, found {actual!r}"
            )
        length_field = int.from_bytes(data[offset - 4 : offset], "little")
        if length_field != len(source_bytes):
            raise ValueError(
                f"length field mismatch in {target} at {offset - 4}: "
                f"expected {len(source_bytes)}, found {length_field}"
            )
        backup = backup_file(target, backup_root, game_work)
        data[offset : offset + len(source_bytes)] = russian_bytes
        target.write_bytes(data)
        applied.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "file": str(target.relative_to(root)),
                "backup": str(backup.relative_to(root)),
                "offset": str(offset),
                "source": row["source"],
                "russian": row["russian"],
                "method": "equal-length utf-8 in-place replacement",
            }
        )

    changelog.parent.mkdir(parents=True, exist_ok=True)
    write_header = not changelog.exists()
    with changelog.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp_utc", "file", "backup", "offset", "source", "russian", "method"],
            delimiter="\t",
        )
        if write_header:
            writer.writeheader()
        writer.writerows(applied)

    print(f"applied {len(applied)} patch row(s); changelog: {changelog}")


if __name__ == "__main__":
    main()
