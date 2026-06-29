#!/usr/bin/env python3
"""Build a Linux/Wine patch ZIP from the tracked payload, without game files."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "dist/dswf-rus-patcher/payload"
BUILD = ROOT / "build"
STAGING = BUILD / "dswf-rus-v1.1.3-linux-patch"
OUT_ZIP = BUILD / "dswf-rus-v1.1.3-linux-patch.zip"
TEXTURE_MANIFEST = ROOT / "docs/v1_1_3_texture_replacement_manifest.tsv"

GAME_FILE_NAMES = {"DontSleepWithTheFishes.exe", "UnityPlayer.dll", "GameAssembly.dll"}
GAME_DIR_NAMES = {"DontSleepWithTheFishes_Data"}

RUN_SH = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f DontSleepWithTheFishes.exe ]]; then
  echo "Extract this patch into the folder containing DontSleepWithTheFishes.exe." >&2
  exit 1
fi
export WINEDLLOVERRIDES="winhttp=n,b"
wine DontSleepWithTheFishes.exe
"""

README_TEMPLATE = """DSWF Russian patch v1.1.3 - Linux/Wine

This archive is not the game. Use it only with your own copy of Dont Sleep With The Fishes v1.1.3.

Install:
1. Close the game.
2. Extract this archive into the folder containing DontSleepWithTheFishes.exe.
3. Run ./run_dswf_rus.sh

Included:
- BepInEx / XUnity AutoTranslator files
- Russian text dictionary and regexes
- DSWF Russian Runtime Fix plugin and safe config
- Wine launcher with WINEDLLOVERRIDES=winhttp=n,b
{texture_included}

Not included:
- DontSleepWithTheFishes.exe
- DontSleepWithTheFishes_Data/
- UnityPlayer.dll
- GameAssembly.dll

Troubleshooting:
- BepInEx/LogOutput.log contains runtime plugin and XUnity logs.
- If a maintainer asks for audit logs, enable visible audit in BepInEx/config/ru.dswf.runtimefix.cfg, play, then send BepInEx/dswf_audit/ and BepInEx/LogOutput.log.
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


def copy_texture_payload(staging: Path) -> None:
    texture_dir = PAYLOAD / "textures"
    if not texture_dir.exists() or not any(texture_dir.glob("*.png")):
        raise SystemExit(f"texture payload is empty: {texture_dir}")
    if not TEXTURE_MANIFEST.exists():
        raise SystemExit(f"texture manifest missing: {TEXTURE_MANIFEST}")
    dst = staging / "_dswf_rus_texture_payload"
    copy_tree(texture_dir, dst / "textures")
    shutil.copy2(TEXTURE_MANIFEST, dst / "v1_1_3_texture_replacement_manifest.tsv")


def build(out_zip: Path, include_textures: bool) -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    copy_tree(PAYLOAD / "bepinex", STAGING)
    copy_tree(PAYLOAD / "text", STAGING)
    copy_tree(PAYLOAD / "runtime", STAGING)
    if include_textures:
        copy_texture_payload(STAGING)
    run_path = STAGING / "run_dswf_rus.sh"
    run_path.write_text(RUN_SH, encoding="utf-8", newline="\n")
    run_path.chmod(0o755)
    texture_note = (
        "- approved static texture replacement payload under _dswf_rus_texture_payload/ for installer/manual validation; "
        "extracting this ZIP alone does not patch Unity asset files"
        if include_textures
        else "- no texture replacements; static texture patching must be applied by the dev/GUI installer"
    )
    (STAGING / "README_DSWF_RUS_LINUX.txt").write_text(
        README_TEMPLATE.format(texture_included=texture_note),
        encoding="utf-8",
        newline="\n",
    )
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
