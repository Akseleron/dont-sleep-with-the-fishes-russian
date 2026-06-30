#!/usr/bin/env python3
"""Build a Linux GUI patcher ZIP from the tracked payload, without game files."""

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


RUN_PATCHER_SH = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 not found. Install Python with tkinter, UnityPy and Pillow support." >&2
  exit 1
fi

exec "$PYTHON_BIN" ./dswf_rus_patcher.py
"""


README_TEMPLATE = """DSWF Russian GUI patcher v1.1.3 - Linux/Wine

This archive is not the game. Use it only with your own copy of Dont Sleep With The Fishes v1.1.3.

Install:
1. Close the game.
2. Extract this archive anywhere outside the game folder.
3. Run ./run_patcher_linux.sh
4. In the patcher window, choose the folder containing DontSleepWithTheFishes.exe.
5. Leave "Русский текст / BepInEx / XUnity" and "Русские текстуры offline" enabled.
6. Click "Установить".
7. Start the game with run_dswf_rus.sh created inside the game folder.

Linux dependency note:
- This source package requires Python with tkinter, UnityPy and Pillow.
- For developer testing you can run:
  PYTHON_BIN=/path/to/python ./run_patcher_linux.sh
- A standalone Linux build should be produced later so normal users do not install Python packages manually.

Included:
- Tkinter GUI patcher
- BepInEx / XUnity AutoTranslator payload
- Russian text dictionary and regexes
- DSWF Russian Runtime Fix plugin and safe config
- Offline Russian Texture2D payload
- Linux Wine launcher installed into the selected game folder

Not included:
- DontSleepWithTheFishes.exe
- DontSleepWithTheFishes_Data/
- UnityPlayer.dll
- GameAssembly.dll

Troubleshooting:
- The patcher writes install details into the log area in the window.
- Installed game logs are in BepInEx/LogOutput.log.
- Texture patch report is written to DontSleepWithTheFishes_Data/_dswf_rus_patch/texture_patch_report.tsv.
- Uninstall is available from the same patcher window.
- Do not enable runtime texture replacement unless a maintainer asks you to test it.
"""


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise SystemExit(f"required payload folder missing: {src}")
    shutil.copytree(src, dst, dirs_exist_ok=True)


def ensure_safe_release_config(root: Path) -> None:
    candidates = [
        root / "BepInEx/config/ru.dswf.runtimefix.cfg",
        root / "config/ru.dswf.runtimefix.cfg",
    ]
    cfg = next((path for path in candidates if path.is_file()), None)
    if cfg is None:
        raise SystemExit(
            "runtime config missing; checked: "
            + ", ".join(str(path) for path in candidates)
        )

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

    dst = staging / "payload" / "textures"
    copy_tree(texture_dir, dst)
    shutil.copy2(TEXTURE_MANIFEST, dst / "v1_1_3_texture_replacement_manifest.tsv")


def ensure_patcher_payload(staging: Path) -> None:
    required_files = [
        "dswf_rus_patcher.py",
        "run_patcher_linux.sh",
        "README_DSWF_RUS_LINUX.txt",
        "payload/runtime/BepInEx/config/ru.dswf.runtimefix.cfg",
        "payload/text/BepInEx/Translation/ru/Text/_AutoGeneratedTranslations.txt",
        "payload/runtime/BepInEx/plugins/DswfRusRuntimeFix/DswfRusRuntimeFix.dll",
    ]
    required_dirs = [
        "payload/bepinex",
        "payload/text",
        "payload/runtime",
        "payload/textures",
    ]

    missing_files = [name for name in required_files if not (staging / name).is_file()]
    missing_dirs = [name for name in required_dirs if not (staging / name).is_dir()]

    if missing_files or missing_dirs:
        msg = []
        if missing_files:
            msg.append("missing files: " + ", ".join(missing_files))
        if missing_dirs:
            msg.append("missing dirs: " + ", ".join(missing_dirs))
        raise SystemExit("patcher payload incomplete; " + "; ".join(msg))


def build(out_zip: Path, include_textures: bool) -> None:
    if not include_textures:
        raise SystemExit("Linux GUI patcher package requires --include-textures")

    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    shutil.copy2(
        ROOT / "dist/dswf-rus-patcher/dswf_rus_patcher.py",
        STAGING / "dswf_rus_patcher.py",
    )

    copy_tree(PAYLOAD / "bepinex", STAGING / "payload" / "bepinex")
    copy_tree(PAYLOAD / "text", STAGING / "payload" / "text")
    copy_tree(PAYLOAD / "runtime", STAGING / "payload" / "runtime")
    copy_texture_payload(STAGING)

    run_path = STAGING / "run_patcher_linux.sh"
    run_path.write_text(RUN_PATCHER_SH, encoding="utf-8", newline="\n")
    run_path.chmod(0o755)

    readme_path = STAGING / "README_DSWF_RUS_LINUX.txt"
    readme_path.write_text(README_TEMPLATE, encoding="utf-8", newline="\n")

    ensure_patcher_payload(STAGING)
    ensure_safe_release_config(STAGING / "payload" / "runtime")
    ensure_no_game_files(STAGING)

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(STAGING.rglob("*")):
            if item.is_file():
                arcname = item.relative_to(STAGING).as_posix()
                info = zipfile.ZipInfo.from_file(item, arcname)
                if arcname.endswith(".sh"):
                    info.external_attr = (0o100755 & 0xFFFF) << 16
                with item.open("rb") as handle:
                    zf.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED)

    ensure_no_game_files_in_zip(out_zip)
    print(f"wrote {out_zip}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_ZIP))
    parser.add_argument("--include-textures", action="store_true", help="Include tracked final texture payloads.")
    args = parser.parse_args()
    build(Path(args.out), args.include_textures)


if __name__ == "__main__":
    main()
