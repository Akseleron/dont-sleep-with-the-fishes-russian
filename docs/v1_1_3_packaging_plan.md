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

Textures are not included by default because the extraction ZIPs cannot patch Unity `.assets` files by themselves. The approved v4 static texture payload lives under `dist/dswf-rus-patcher/payload/textures/` and is applied by the dev/GUI installer path.

For local inspection packages only, pass `--include-textures`. This adds `_dswf_rus_texture_payload/` with approved PNGs and `v1_1_3_texture_replacement_manifest.tsv`; extracting that ZIP alone still does not modify Unity assets.

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

## Texture-Enabled Test Install

Texture validation currently uses:

```bash
.venv-tools/bin/python scripts/dev_prepare_v1_1_3_test_copy.py
.venv-tools/bin/python scripts/dev_install_to_game.py game_runtime_test_v1_1_3 --clean-bepinex --apply-textures
```

The current v4 payload has nine approved `Texture2D` rows. See `docs/v1_1_3_texture_replacement_manifest.tsv` and `docs/v1_1_3_texture_runtime_checklist.md`.

Latest local texture-enabled dev install:

- command: `.venv-tools/bin/python scripts/dev_install_to_game.py game_runtime_test_v1_1_3 --clean-bepinex --apply-textures`
- report: `game_runtime_test_v1_1_3/dswf_rus_dev_install_report.txt`
- result: `textures_applied=True`
- texture patch report: `game_runtime_test_v1_1_3/DontSleepWithTheFishes_Data/_dswf_rus_patch/texture_patch_report.tsv`
- applied rows: 9

## Latest Local Package Artifacts

Built for inspection only; do not commit these ZIPs:

- `build/dswf-rus-v1.1.3-windows-patch.zip`
- `build/dswf-rus-v1.1.3-linux-patch.zip`

Both were built with `--include-textures`, include `_dswf_rus_texture_payload/`, and were inspected for forbidden game files.

## Release Blockers

- Fresh clean v1.1.3 runtime audit must pass with `unapproved_visible_english=0`.
- Ending death causes, company notes, friend fate, fishing weight, and FriendManageUI must be retested.
- Texture replacements must pass manual visual validation after the texture-enabled install.
- Linux and Windows package ZIPs must be built and inspected for forbidden game files.
