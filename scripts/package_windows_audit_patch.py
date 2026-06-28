#!/usr/bin/env python3
"""Package a Windows-only audit patch ZIP without game files."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "dist/dswf-rus-patcher/payload"
BUILD = ROOT / "build"
STAGING = BUILD / "dswf-rus-audit-patch-v1.1.3-windows"
OUT_ZIP = BUILD / "dswf-rus-audit-patch-v1.1.3-windows.zip"
GAME_FILE_NAMES = {
    "DontSleepWithTheFishes.exe",
    "UnityPlayer.dll",
    "GameAssembly.dll",
}
GAME_DIR_NAMES = {
    "DontSleepWithTheFishes_Data",
}


RUN_BAT = r"""@echo off
cd /d "%~dp0"
if not exist "DontSleepWithTheFishes.exe" (
  echo Этот архив нужно распаковать в папку с DontSleepWithTheFishes.exe
  echo Игра в этот архив не входит. Используйте вашу собственную копию игры v1.1.3.
  pause
  exit /b 1
)
echo Запуск тестовой русификации с аудитом текста...
start "" "DontSleepWithTheFishes.exe"
"""

COLLECT_BAT = r"""@echo off
cd /d "%~dp0"
if not exist "tester_notes.txt" (
  > tester_notes.txt echo Напишите здесь, что вы заметили: обрезанный текст, английский текст, странный русский, наложение текста.
)
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
set ZIP=dswf_audit_logs_%COMPUTERNAME%_%TS%.zip
powershell -NoProfile -Command "$items=@(); if(Test-Path 'BepInEx\dswf_audit'){$items+='BepInEx\dswf_audit'}; if(Test-Path 'BepInEx\LogOutput.log'){$items+='BepInEx\LogOutput.log'}; if(Test-Path 'BepInEx\ErrorLog.log'){$items+='BepInEx\ErrorLog.log'}; if(Test-Path 'BepInEx\config\ru.dswf.runtimefix.cfg'){$items+='BepInEx\config\ru.dswf.runtimefix.cfg'}; if(Test-Path 'tester_notes.txt'){$items+='tester_notes.txt'}; if($items.Count -eq 0){Write-Error 'Нет файлов аудита для упаковки'; exit 1}; Compress-Archive -Path $items -DestinationPath '%ZIP%' -Force"
echo.
echo Готово. Отправьте файл:
echo %CD%\%ZIP%
pause
"""

RUN_SH = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f DontSleepWithTheFishes.exe ]]; then
  echo "Extract this audit patch into the folder containing DontSleepWithTheFishes.exe." >&2
  exit 1
fi
export WINEDLLOVERRIDES="winhttp=n,b"
wine DontSleepWithTheFishes.exe
"""

COLLECT_SH = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[[ -f tester_notes.txt ]] || printf '%s\n' 'Notes: clipped text, English text, awkward Russian, overlap.' > tester_notes.txt
ts="$(date +%Y%m%d_%H%M%S)"
zip_name="dswf_audit_logs_${HOSTNAME:-linux}_${ts}.zip"
items=()
[[ -d BepInEx/dswf_audit ]] && items+=(BepInEx/dswf_audit)
[[ -f BepInEx/LogOutput.log ]] && items+=(BepInEx/LogOutput.log)
[[ -f BepInEx/ErrorLog.log ]] && items+=(BepInEx/ErrorLog.log)
[[ -f BepInEx/config/ru.dswf.runtimefix.cfg ]] && items+=(BepInEx/config/ru.dswf.runtimefix.cfg)
items+=(tester_notes.txt)
zip -r "$zip_name" "${items[@]}"
echo "Created: $PWD/$zip_name"
"""


def copy_tree(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def write_text(path: Path, text: str, newline: str = "\r\n") -> None:
    path.write_text(text.replace("\n", newline), encoding="utf-8", newline="")


def configure_audit(staging: Path) -> None:
    cfg = staging / "BepInEx/config/ru.dswf.runtimefix.cfg"
    text = cfg.read_text(encoding="utf-8")
    replacements = {
        "EnableVisibleTextAudit = false": "EnableVisibleTextAudit = true",
        "VisibleTextAuditMode = EnglishOnly": "VisibleTextAuditMode = AllText",
        "VisibleTextAuditIntervalSeconds = 1": "VisibleTextAuditIntervalSeconds = 0.25",
        "VisibleTextAuditMaxScansPerScene = 30": "VisibleTextAuditMaxScansPerScene = 200",
        "VisibleTextAuditOutputRoot = BepInEx/dswf_audit": "VisibleTextAuditOutputRoot = BepInEx/dswf_audit",
        "VisibleTextAuditWriteRawSession = true": "VisibleTextAuditWriteRawSession = true",
        "VisibleTextAuditWriteUniqueSession = true": "VisibleTextAuditWriteUniqueSession = true",
        "VisibleTextAuditWriteGlobalUnique = true": "VisibleTextAuditWriteGlobalUnique = true",
        "VisibleTextAuditIncludeLayoutRisk = true": "VisibleTextAuditIncludeLayoutRisk = true",
    }
    for old, new in replacements.items():
        if old not in text and new not in text:
            raise SystemExit(f"missing config key while building audit patch: {old}")
        text = text.replace(old, new)
    cfg.write_text(text, encoding="utf-8")


def ensure_no_game_files(path: Path) -> None:
    for item in path.rglob("*"):
        if item.name in GAME_FILE_NAMES:
            raise SystemExit(f"refusing to package game file: {item}")
        if item.is_dir() and item.name in GAME_DIR_NAMES:
            raise SystemExit(f"refusing to package game directory: {item}")


def package_zip(out_zip: Path) -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    copy_tree(PAYLOAD / "bepinex", STAGING)
    copy_tree(PAYLOAD / "text", STAGING)
    copy_tree(PAYLOAD / "runtime", STAGING)
    write_text(STAGING / "run_dswf_rus_audit.bat", RUN_BAT)
    write_text(STAGING / "collect_audit_logs.bat", COLLECT_BAT)
    (STAGING / "run_dswf_rus_audit.sh").write_text(RUN_SH, encoding="utf-8")
    (STAGING / "collect_audit_logs.sh").write_text(COLLECT_SH, encoding="utf-8")
    shutil.copy2(ROOT / "docs/README_AUDIT_TESTERS_RU.txt", STAGING / "README_AUDIT_TESTERS_RU.txt")
    configure_audit(STAGING)
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


def ensure_no_game_files_in_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            parts = Path(name).parts
            if Path(name).name in GAME_FILE_NAMES or any(part in GAME_DIR_NAMES for part in parts):
                raise SystemExit(f"zip contains forbidden game file/path: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_ZIP))
    args = parser.parse_args()
    package_zip(Path(args.out))


if __name__ == "__main__":
    main()
