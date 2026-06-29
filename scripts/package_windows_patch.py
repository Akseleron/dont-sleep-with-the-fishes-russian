#!/usr/bin/env python3
"""Build a Windows patch ZIP from the tracked payload, without game files."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "dist/dswf-rus-patcher/payload"
BUILD = ROOT / "build"
STAGING = BUILD / "dswf-rus-v1.1.3-windows-patch"
OUT_ZIP = BUILD / "dswf-rus-v1.1.3-windows-patch.zip"

GAME_FILE_NAMES = {"DontSleepWithTheFishes.exe", "UnityPlayer.dll", "GameAssembly.dll"}
GAME_DIR_NAMES = {"DontSleepWithTheFishes_Data"}

README = """DSWF Russian patch v1.1.3 - Windows

This archive is not the game. Use it only with your own copy of Dont Sleep With The Fishes v1.1.3.

Install:
1. Close the game.
2. Extract this archive into the folder containing DontSleepWithTheFishes.exe.
3. Run DontSleepWithTheFishes.exe normally.

Included:
- BepInEx / XUnity AutoTranslator files
- Russian text dictionary and regexes
- DSWF Russian Runtime Fix plugin and safe config

Not included:
- DontSleepWithTheFishes.exe
- DontSleepWithTheFishes_Data/
- UnityPlayer.dll
- GameAssembly.dll
- texture replacements that are still under manual review

Troubleshooting:
- BepInEx/LogOutput.log contains runtime plugin and XUnity logs.
- Do not enable runtime texture replacement unless a maintainer asks you to test it.
"""


def copy_tree(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def ensure_safe_release_config(staging: Path) -> None:
    cfg = staging / "BepInEx/config/ru.dswf.runtimefix.cfg"
    text = cfg.read_text(encoding="utf-8")
    required = [
        "EnableVisibleTextAudit = false",
        "EnableTextureFix = false",
        "EnableRuntimeTextReapply = true",
    ]
    missing = [line for line in required if line not in text]
    if missing:
        raise SystemExit("unsafe runtime config for release package: " + ", ".join(missing))


def ensure_no_game_files(path: Path) -> None:
    for item in path.rglob("*"):
        if item.name in GAME_FILE_NAMES:
            raise SystemExit(f"refusing to package game file: {item}")
        if item.is_dir() and item.name in GAME_DIR_NAMES:
            raise SystemExit(f"refusing to package game directory: {item}")


def ensure_no_game_files_in_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            parts = Path(name).parts
            if Path(name).name in GAME_FILE_NAMES or any(part in GAME_DIR_NAMES for part in parts):
                raise SystemExit(f"zip contains forbidden game file/path: {name}")


def build(out_zip: Path, include_textures: bool) -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    copy_tree(PAYLOAD / "bepinex", STAGING)
    copy_tree(PAYLOAD / "text", STAGING)
    copy_tree(PAYLOAD / "runtime", STAGING)
    if include_textures:
        copy_tree(PAYLOAD / "textures", STAGING)
    (STAGING / "README_DSWF_RUS_WINDOWS.txt").write_text(README, encoding="utf-8", newline="\r\n")
    ensure_safe_release_config(STAGING)
    ensure_no_game_files(STAGING)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(STAGING.rglob("*")):
            if item.is_file():
                zf.write(item, item.relative_to(STAGING).as_posix())
    ensure_no_game_files_in_zip(out_zip)
    print(f"wrote {out_zip}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_ZIP))
    parser.add_argument("--include-textures", action="store_true", help="Include tracked final texture payloads when they exist.")
    args = parser.parse_args()
    build(Path(args.out), args.include_textures)


if __name__ == "__main__":
    main()
