# v1.1.3 Packaging Plan

This branch is not release-ready yet. These scripts prepare the package base only; do not publish or tag a release until fresh runtime audit and texture validation pass.

## Package Scripts

- Windows: `.venv-tools/bin/python scripts/package_windows_patch.py`
- Linux/Wine: `.venv-tools/bin/python scripts/package_linux_patch.py`

Both scripts write local ZIPs under `build/`. Build ZIPs are local artifacts and must not be committed.

## Included Payload

The scripts stage the tracked payload from `dist/dswf-rus-patcher/payload/`:

- `payload/bepinex`
- `payload/text`
- `payload/runtime`

This includes:

- BepInEx / XUnity AutoTranslator base files
- generated Russian XUnity dictionary
- `FishingRegex.txt`
- DSWF Russian Runtime Fix plugin
- runtime config with safe defaults

Safe defaults required by the scripts:

- `EnableVisibleTextAudit = false`
- `EnableTextureFix = false`
- `EnableRuntimeTextReapply = true`

## Not Included

The scripts reject these game files and paths:

- `DontSleepWithTheFishes.exe`
- `DontSleepWithTheFishes_Data/`
- `UnityPlayer.dll`
- `GameAssembly.dll`

Textures are not included by default because v1.1.3 texture replacements are still under manual review. A future pass may use `--include-textures` only after final approved texture payloads exist.

## Windows Notes

The Windows package reuses the existing BepInEx/Doorstop layout, including `winhttp.dll` and `doorstop_config.ini` from the tracked payload. Users extract the ZIP into the folder containing `DontSleepWithTheFishes.exe` and launch the game normally.

## Linux Notes

The Linux/Wine package includes `run_dswf_rus.sh`, which sets:

```bash
WINEDLLOVERRIDES=winhttp=n,b
```

Users extract the ZIP into the folder containing `DontSleepWithTheFishes.exe` and run `./run_dswf_rus.sh`.

## Audit And Logs

Normal packages keep full visible text audit disabled. If a tester reports missed English, collect:

- `BepInEx/LogOutput.log`
- `BepInEx/ErrorLog.log`, if present

The runtime plugin logs each unique suspicious visible English candidate once in known sensitive contexts, without writing full audit TSVs unless `EnableVisibleTextAudit = true`.

## Release Blockers

- Fresh clean v1.1.3 runtime audit must pass with `unapproved_visible_english=0`.
- Ending death causes, company notes, friend fate, fishing weight, and FriendManageUI must be retested.
- Texture replacements must be finalized and validated separately.
- Linux and Windows package ZIPs must be built and inspected for forbidden game files.
