#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import UnityPy  # type: ignore
except ImportError as exc:
    raise SystemExit(
        "UnityPy is required. Use .venv-tools/bin/python scripts/patch_unity_textures.py "
        "or install UnityPy in the active environment."
    ) from exc

try:
    from PIL import Image  # type: ignore
except ImportError as exc:
    raise SystemExit("Pillow is required for PNG replacement.") from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "game_runtime_test" / "DontSleepWithTheFishes_Data"
DEFAULT_ORIGINAL_DIR = ROOT / "game_original" / "DontSleepWithTheFishes_Data"
DEFAULT_REPORT = ROOT / "debug_reports" / "unity_texture_patch_report.tsv"
PNG_RE = re.compile(r"^(?P<asset>sharedassets\d+)__(?P<type>Texture2D|Sprite)__(?P<path_id>\d+)__(?P<name>.+)\.png$")


def find_default_replacement_dir() -> Path | None:
    for candidate in [
        Path.home() / "Downloads" / "fish3",
        Path.home() / "Загрузки" / "fish3",
        ROOT / "_manual" / "fish3",
        ROOT / "_manual" / "fish2",
    ]:
        if candidate.is_dir() and any(candidate.glob("*.png")):
            return candidate
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_runtime_data_dir(data_dir: Path) -> None:
    resolved = data_dir.resolve()
    expected = DEFAULT_DATA_DIR.resolve()
    if resolved != expected:
        raise SystemExit(f"refusing to write outside runtime test data dir: {resolved}")


def parse_texture_pngs(replacement_dir: Path) -> dict[tuple[str, int], Path]:
    textures: dict[tuple[str, int], Path] = {}
    for path in sorted(replacement_dir.glob("*.png")):
        match = PNG_RE.match(path.name)
        if not match or match.group("type") != "Texture2D":
            continue
        textures[(match.group("asset"), int(match.group("path_id")))] = path
    return textures


def parse_targets(raw_targets: list[str], textures: dict[tuple[str, int], Path]) -> dict[tuple[str, int], Path]:
    if not raw_targets:
        return textures
    selected: dict[tuple[str, int], Path] = {}
    by_name = {path.name: key for key, path in textures.items()}
    for raw in raw_targets:
        target = raw.strip()
        if not target:
            continue
        key: tuple[str, int] | None = None
        if target in by_name:
            key = by_name[target]
        else:
            match = PNG_RE.match(Path(target).name)
            if match and match.group("type") == "Texture2D":
                key = (match.group("asset"), int(match.group("path_id")))
            elif ":" in target:
                asset, path_id = target.split(":", 1)
                key = (asset.replace(".assets", ""), int(path_id))
        if key is None or key not in textures:
            raise SystemExit(f"unknown Texture2D target: {raw}")
        selected[key] = textures[key]
    return selected


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


def backup_asset_files(data_dir: Path, asset_files: list[str]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = data_dir / "_dswf_rus_backup" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    manifest_rows: list[dict[str, str]] = []
    for asset_file in asset_files:
        for rel in [asset_file, asset_file + ".resS"]:
            src = data_dir / rel
            if not src.exists():
                continue
            dst = backup_dir / rel
            shutil.copy2(src, dst)
            manifest_rows.append({
                "file": rel,
                "sha256": sha256_file(src),
                "size": str(src.stat().st_size),
            })
    with (backup_dir / "backup_manifest.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=["file", "sha256", "size"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    return backup_dir


def latest_backup(data_dir: Path) -> Path:
    root = data_dir / "_dswf_rus_backup"
    if not root.exists():
        raise SystemExit(f"no backup directory found: {root}")
    backups = sorted([p for p in root.iterdir() if p.is_dir()])
    if not backups:
        raise SystemExit(f"no backups found under {root}")
    return backups[-1]


def restore(data_dir: Path, backup: Path | None) -> None:
    assert_runtime_data_dir(data_dir)
    backup_dir = backup or latest_backup(data_dir)
    manifest = backup_dir / "backup_manifest.tsv"
    if not manifest.exists():
        raise SystemExit(f"backup manifest missing: {manifest}")
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rel = row["file"]
            src = backup_dir / rel
            dst = data_dir / rel
            if not src.exists():
                raise SystemExit(f"backup file missing: {src}")
            shutil.copy2(src, dst)
            restored_sha = sha256_file(dst)
            if restored_sha != row["sha256"]:
                raise SystemExit(f"restore SHA mismatch for {rel}: {restored_sha} != {row['sha256']}")
            print(f"restored {rel}")


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "mode", "assets_file", "path_id", "unity_name", "replacement_png",
        "asset_sha_before", "expected_sha", "asset_sha_after",
        "width", "height", "replacement_width", "replacement_height",
        "texture_format_before", "texture_format_after", "stream_path_before",
        "stream_size_before", "status", "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def patch(
    data_dir: Path,
    original_dir: Path,
    replacement_dir: Path,
    targets: dict[tuple[str, int], Path],
    report: Path,
    apply: bool,
    force: bool,
) -> list[dict[str, str]]:
    if apply:
        assert_runtime_data_dir(data_dir)
    rows: list[dict[str, str]] = []
    asset_groups: dict[str, dict[int, Path]] = {}
    for (asset_stem, path_id), png in targets.items():
        asset_groups.setdefault(asset_stem + ".assets", {})[path_id] = png
    if apply:
        backup_dir = backup_asset_files(data_dir, sorted(asset_groups))
        print(f"backup written to {backup_dir}")
    for asset_file, group in sorted(asset_groups.items()):
        asset_path = data_dir / asset_file
        original_path = original_dir / asset_file
        expected_sha = sha256_file(original_path) if original_path.exists() else ""
        before_sha = sha256_file(asset_path) if asset_path.exists() else ""
        if not asset_path.exists():
            for path_id, png in sorted(group.items()):
                rows.append(base_row("apply" if apply else "dry-run", asset_file, path_id, png, before_sha, expected_sha, "", "missing_assets_file", ""))
            continue
        if apply and expected_sha and before_sha != expected_sha and not force:
            for path_id, png in sorted(group.items()):
                rows.append(base_row("apply", asset_file, path_id, png, before_sha, expected_sha, "", "skipped_sha_mismatch", "use --force only after restoring/inspecting runtime assets"))
            continue
        env = UnityPy.load(str(asset_path))
        changed = False
        found: set[int] = set()
        for obj in env.objects:
            if obj.type.name != "Texture2D":
                continue
            path_id = int(obj.path_id)
            if path_id not in group:
                continue
            found.add(path_id)
            png = group[path_id]
            row = base_row("apply" if apply else "dry-run", asset_file, path_id, png, before_sha, expected_sha, "", "", "")
            try:
                data = obj.read()
                width = int(getattr(data, "m_Width", 0) or 0)
                height = int(getattr(data, "m_Height", 0) or 0)
                row["unity_name"] = str(getattr(data, "m_Name", "") or "")
                row["width"] = str(width)
                row["height"] = str(height)
                row["texture_format_before"] = texture_format_name(getattr(data, "m_TextureFormat", ""))
                stream = getattr(data, "m_StreamData", None)
                row["stream_path_before"] = str(getattr(stream, "path", "") or "") if stream else ""
                row["stream_size_before"] = str(getattr(stream, "size", "") or "") if stream else ""
                with Image.open(png) as img:
                    img = img.convert("RGBA")
                    row["replacement_width"] = str(img.width)
                    row["replacement_height"] = str(img.height)
                    if (img.width, img.height) != (width, height):
                        row["status"] = "skipped_size_mismatch"
                        rows.append(row)
                        continue
                    if apply:
                        original_format = getattr(data, "m_TextureFormat", None)
                        mip_count = int(getattr(data, "m_MipCount", 1) or 1)
                        data.set_image(img, target_format=original_format, mipmap_count=mip_count)
                        row["texture_format_after"] = texture_format_name(getattr(data, "m_TextureFormat", ""))
                        data.save()
                        changed = True
                        row["status"] = "applied"
                    else:
                        row["status"] = "dry_run_match"
                rows.append(row)
            except Exception as exc:
                row["status"] = "failed:" + type(exc).__name__
                row["notes"] = str(exc)
                rows.append(row)
        for path_id, png in sorted(group.items()):
            if path_id not in found:
                rows.append(base_row("apply" if apply else "dry-run", asset_file, path_id, png, before_sha, expected_sha, "", "skipped_missing_target", ""))
        if apply and changed:
            with tempfile.TemporaryDirectory() as td:
                out_dir = Path(td)
                env.save(out_path=str(out_dir))
                patched = out_dir / asset_file
                if not patched.exists():
                    raise SystemExit(f"UnityPy did not write patched asset: {asset_file}")
                shutil.copy2(patched, asset_path)
            after_sha = sha256_file(asset_path)
            for row in rows:
                if row["assets_file"] == asset_file and row["mode"] == "apply":
                    row["asset_sha_after"] = after_sha
    write_report(report, rows)
    return rows


def base_row(mode: str, asset_file: str, path_id: int, png: Path, before_sha: str, expected_sha: str, after_sha: str, status: str, notes: str) -> dict[str, str]:
    return {
        "mode": mode,
        "assets_file": asset_file,
        "path_id": str(path_id),
        "unity_name": "",
        "replacement_png": str(png),
        "asset_sha_before": before_sha,
        "expected_sha": expected_sha,
        "asset_sha_after": after_sha,
        "width": "",
        "height": "",
        "replacement_width": "",
        "replacement_height": "",
        "texture_format_before": "",
        "texture_format_after": "",
        "stream_path_before": "",
        "stream_size_before": "",
        "status": status,
        "notes": notes,
    }


def main() -> None:
    default_replacement_dir = find_default_replacement_dir()
    parser = argparse.ArgumentParser(description="Safely patch DSWF runtime test Unity Texture2D assets.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--restore", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--original-dir", type=Path, default=DEFAULT_ORIGINAL_DIR)
    parser.add_argument("--replacement-dir", type=Path, default=default_replacement_dir)
    parser.add_argument("--target", action="append", default=[], help="Texture2D target filename or sharedassetsN:PATH_ID. Repeatable.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--backup", type=Path, default=None, help="Backup directory for --restore. Defaults to latest backup.")
    parser.add_argument("--force", action="store_true", help="Allow apply when runtime asset SHA differs from game_original.")
    args = parser.parse_args()

    if args.restore:
        restore(args.data_dir, args.backup)
        return
    if args.replacement_dir is None:
        raise SystemExit("replacement directory not found; pass --replacement-dir")
    textures = parse_texture_pngs(args.replacement_dir)
    targets = parse_targets(args.target, textures)
    rows = patch(
        data_dir=args.data_dir,
        original_dir=args.original_dir,
        replacement_dir=args.replacement_dir,
        targets=targets,
        report=args.report,
        apply=args.apply,
        force=args.force,
    )
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    print(f"wrote {len(rows)} rows to {args.report}")
    for status, count in sorted(statuses.items()):
        print(status, count)


if __name__ == "__main__":
    main()
