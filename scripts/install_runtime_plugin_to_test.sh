#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/game_runtime_test/BepInEx/plugins/DswfRusRuntimeFix"
mkdir -p "$DEST/Textures" "$DEST/Fonts"
cp "$ROOT/patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix/DswfRusRuntimeFix.dll" "$DEST/DswfRusRuntimeFix.dll"
if [[ -d "$ROOT/patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix/Textures" ]]; then
  rsync -a "$ROOT/patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix/Textures/" "$DEST/Textures/"
fi
if [[ -f "$ROOT/_manual/nyashasans/nyashasans.ttf" ]]; then
  cp "$ROOT/_manual/nyashasans/nyashasans.ttf" "$DEST/Fonts/nyashasans.ttf"
fi
