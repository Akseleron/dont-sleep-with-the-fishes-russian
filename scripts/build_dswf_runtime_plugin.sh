#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOTNET="$ROOT/.tools/dotnet/dotnet"
if [[ ! -x "$DOTNET" ]]; then
  echo "Missing local dotnet SDK at $DOTNET" >&2
  exit 1
fi
"$DOTNET" build "$ROOT/plugins/DswfRusRuntimeFix/DswfRusRuntimeFix.csproj" -c Release --nologo
mkdir -p "$ROOT/patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix"
cp "$ROOT/plugins/DswfRusRuntimeFix/bin/Release/DswfRusRuntimeFix.dll" "$ROOT/patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix/DswfRusRuntimeFix.dll"
