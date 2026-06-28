#!/usr/bin/env python3
"""Prepare an ignored clean v1.1.3 runtime test copy.

This script copies the game files only. It does not install the localization and
does not launch the game.
"""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    "/mnt/shared/Games/DontSleepWithTheFishes_v1_1_3/"
    "DontSleepWithTheFishes_v1_1_3_ItchRelease"
)
TARGET = ROOT / "game_runtime_test_v1_1_3"
GAME_EXE = "DontSleepWithTheFishes.exe"
DATA_DIR = "DontSleepWithTheFishes_Data"


def verify_game_root(path: Path, label: str) -> None:
    if not path.is_dir():
        raise SystemExit(f"{label} does not exist or is not a directory: {path}")
    if not (path / GAME_EXE).is_file():
        raise SystemExit(f"{label} is missing {GAME_EXE}: {path}")
    if not (path / DATA_DIR).is_dir():
        raise SystemExit(f"{label} is missing {DATA_DIR}: {path}")


def assert_target_inside_repo(target: Path) -> None:
    root = ROOT.resolve()
    resolved = target.resolve()
    if resolved == root:
        raise SystemExit(f"Refusing to remove repository root: {resolved}")
    if root not in resolved.parents:
        raise SystemExit(f"Refusing to remove target outside repository: {resolved}")


def main() -> None:
    verify_game_root(SOURCE, "source")
    assert_target_inside_repo(TARGET)

    if TARGET.exists():
        shutil.rmtree(TARGET)
        print(f"Removed old test copy: {TARGET}")

    shutil.copytree(SOURCE, TARGET, symlinks=True)
    verify_game_root(TARGET, "target")

    print(f"Prepared clean v1.1.3 test copy: {TARGET}")
    print("Next install command:")
    print(".venv-tools/bin/python scripts/dev_install_to_game.py game_runtime_test_v1_1_3 --clean-bepinex --skip-textures")


if __name__ == "__main__":
    main()
