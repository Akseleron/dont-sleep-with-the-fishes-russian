# DSWF Russian Runtime Fix Plugin

`DswfRusRuntimeFix` is a dedicated BepInEx IL2CPP plugin for the Russian localization runtime layer.

It intentionally keeps XUnity.AutoTranslator responsible only for text translation. Font and texture runtime fixes are handled outside XUnity because:

- XUnity text replacement works in this game.
- XUnity TMP font fallback/override failed for every tested `arialuni_sdf_*` AssetBundle with `UnityEngine.AssetBundle::LoadFromFile_Internal(System.String,System.UInt32,System.UInt64) was not resolved`.
- XUnity texture replacement did not visibly apply the translated title texture, and XUnity texture dumping failed with `No way to encode the texture to PNG`.
- Direct UnityPy `.assets` texture patching previously broke runtime visuals and must not be repeated blindly.

## Runtime Files

Packaged plugin files live under:

- `patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix/DswfRusRuntimeFix.dll`
- `patches/dswf_runtime_plugin/BepInEx/plugins/DswfRusRuntimeFix/Textures/*.png`
- `patches/dswf_runtime_plugin/BepInEx/config/DswfRusRuntimeFix.cfg`

The plugin loads replacement PNGs from `BepInEx/plugins/DswfRusRuntimeFix/Textures/` and scans runtime UI objects, sprite renderers, raw images, and renderer material texture slots. It assigns replacement runtime textures/sprites to components and does not modify Unity asset files.

## Font Status

The plugin can test a local font named `nyashasans.ttf` under `BepInEx/plugins/DswfRusRuntimeFix/Fonts/`. The current repository does not include that TTF because no redistribution license was present next to `_manual/nyashasans/nyashasans.ttf`.

When a redistributable Cyrillic font is selected, place it in the plugin `Fonts` directory and update `FontFileName` in config if needed. The plugin attempts private process font registration, creates a Unity dynamic font, then creates a TMP font asset and adds it to TMP fallback lists.

Runtime smoke testing with the local Nyasha Sans file confirmed that private process font registration succeeds under Wine, but TMP font creation is still blocked:

- `TMP_FontAsset.CreateFontAsset(string)` returns null.
- `Font.CreateDynamicFontFromOSFont("Nyasha Sans", 32)` fails with `System.NotSupportedException: Method unstripping failed`.

Because no TMP font asset is created, this plugin does not yet fix Cyrillic font style. It keeps the diagnostic font path in place for future work with a verified redistributable font or a different TMP asset creation strategy.

## Texture Status

Runtime smoke testing confirmed that the plugin loads all 12 translated PNG replacements and applies runtime UI sprite replacements without modifying Unity asset files.

Confirmed replacements in logs:

- title scene logo images: `TITLE/UI/Canvas/text`, `textred`, `textblue`
- main menu title marker: `MENU/UI/Canvas/title_main_image`
- journal icon marker: `MENU/UI/Canvas_GameModes/Difficulties/HowToPlay/HowToPlayExc`
- settings menu logo marker: `GameController/SETTINGS_CANVAS/SETTINGS_MENU/logo`

The replacement mapping uses `Textures/TextureAliases.tsv` for runtime names such as `main_title`, `logo_text`, and `newjournalicon`. Smoke logs showed no magenta visuals and no repeated `NullReferenceException` from the plugin after switching to pre-created runtime sprites.

Manual visual QA is still required to confirm that scale, placement, and alpha look correct in-game.

## Build

Use:

```bash
scripts/build_dswf_runtime_plugin.sh
```

The script expects the local SDK under `.tools/dotnet/`. That SDK was installed with Microsoft `dotnet-install.sh` for local development only and is not committed.

## Runtime Test Install

Use:

```bash
scripts/install_runtime_plugin_to_test.sh
rsync -a patches/dswf_runtime_plugin/ game_runtime_test/
```

For local font testing only, the install helper copies `_manual/nyashasans/nyashasans.ttf` into `game_runtime_test/BepInEx/plugins/DswfRusRuntimeFix/Fonts/` when it exists. This local copy is not committed.

## Diagnostics

The plugin logs:

- plugin load and config values
- font file discovery/registration
- Unity font and TMP font creation results
- Cyrillic glyph checks
- texture replacement PNG load count
- component replacement counts per scan
- visible texture names when `DumpVisibleTextureNames=true`

Visible texture names are written to `debug_reports/runtime_visible_texture_names.tsv` during runtime tests.
