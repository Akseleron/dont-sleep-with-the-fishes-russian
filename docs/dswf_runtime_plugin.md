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
- `patches/dswf_runtime_plugin/BepInEx/config/ru.dswf.runtimefix.cfg`

The plugin loads replacement PNGs from `BepInEx/plugins/DswfRusRuntimeFix/Textures/` and scans runtime UI objects, sprite renderers, raw images, and renderer material texture slots. It assigns replacement runtime textures/sprites to components and does not modify Unity asset files.

## Font Status

The plugin can test a local font named `nyashasans.ttf` under `BepInEx/plugins/DswfRusRuntimeFix/Fonts/`. The current repository does not include that TTF because no redistribution license was present next to `_manual/nyashasans/nyashasans.ttf`.

When a redistributable Cyrillic font is selected, place it in the plugin `Fonts` directory and update `FontFileName` in config if needed. The plugin attempts private process font registration, creates a Unity dynamic font, then creates a TMP font asset and adds it to TMP fallback lists.

Runtime smoke testing with the local Nyasha Sans file confirmed that private process font registration succeeds under Wine, but TMP font creation is still blocked:

- `TMP_FontAsset.CreateFontAsset(string)` returns null.
- `Font.CreateDynamicFontFromOSFont("Nyasha Sans", 32)` fails with `System.NotSupportedException: Method unstripping failed`.

Because no TMP font asset is created, this plugin does not yet fix Cyrillic font style. It keeps the diagnostic font path in place for future work with a verified redistributable font or a different TMP asset creation strategy.

## Texture Status

Runtime smoke testing confirms only that the plugin loads the translated PNG replacements, does not modify Unity asset files, and can run without crash/NRE in the current isolation mode. It does not prove visual correctness. Manual QA after `6ed0532` showed that log-only "Texture replacement applied" was not enough:

- the main menu title became a large white rectangle;
- title splash objects briefly showed the Russian title in the wrong place;
- a white square appeared near the gameplay journal UI while the journal label stayed English.

Those findings mean texture replacement must be advanced one target group at a time and verified visually.

The texture pack was later replaced with the complete `fish3` set after runtime QA showed the previous pack was missing some paired `Texture2D` objects. The current packaged set contains 13 PNG files:

- 7 `Texture2D` replacements
- 6 `Sprite` replacements
- paired `Texture2D + Sprite` entries for the known title/journal/button assets
- one standalone `sharedassets3__Texture2D__120__unnamed_120.png` entry for the `ХЛАМ` texture

The replacement mapping uses `Textures/TextureAliases.tsv` for runtime names such as `main_title`, `logo_text`, and `newjournalicon`.

Important mappings:

- `MENU/UI/Canvas/title_main_image` -> `sharedassets1__Texture2D__50__unnamed_50.png` through the dedicated `OverwriteExistingSpriteTexture` path
- `main_title` -> `sharedassets1__Sprite__260__unnamed_260.png` for sprite matching/diagnostics; the main title object bypasses normal sprite replacement
- `logo_text` -> `sharedassets1__Sprite__260__unnamed_260.png`
- `newjournalicon` -> `sharedassets3__Sprite__376__unnamed_376.png`

The main menu title no longer uses a child `RawImage` overlay and no longer assigns a newly created `Sprite`. Manual QA showed that the overlay approach produced a large white rectangle. The current implementation leaves the original `Image.sprite`, sprite rect, pivot, pixels-per-unit, `Image.type`, `preserveAspect`, and `RectTransform` in place, then overwrites the original `main_title` texture contents with the full 1024x1024 replacement texture.

Runtime smoke testing for the overwrite path showed:

- `ImageConversion.LoadImage` fails in this IL2CPP runtime with a `ReadOnlySpan` missing-method error.
- the plugin decodes PNGs with its managed `SimplePng` decoder and creates a fresh RGBA32 `Texture2D` through `SetPixels32`/`Apply`.
- source texture creation is now logged separately with `sourceTextureCreated`, size, format, graphics format, and native pointer.
- `Graphics.CopyTexture` is attempted only after the source texture is non-null and dimensions match the target.
- the latest smoke test reported `sourceTextureCreated=True`, `sourceTextureNull=False`, source `RGBA32`/`R8G8B8A8_SRGB`, target `BC7`/`RGBA_BC7_SRGB`, then `Graphics.CopyTexture success=True`.
- no `RawImage` overlay object is created.
- no Unity `.assets` files are modified.

This still requires manual visual QA. The smoke test confirms the non-null source texture path, method call path, and absence of crash/NRE only.

Current default config is isolation mode:

- `PatchMainMenuTitle=true`
- `PatchTitleSplash=false`
- `PatchSettingsLogo=false`
- `PatchJournalIcon=false`
- `PatchHowToPlay=false`
- `PatchGameplay3DTextures=false`

Disabled groups are intentionally skipped:

- `TITLE/UI/Canvas/text`
- `TITLE/UI/Canvas/textred`
- `TITLE/UI/Canvas/textblue`
- `MENU/UI/Canvas_GameModes/Difficulties/HowToPlay/HowToPlayExc`
- `GameController/SETTINGS_CANVAS/SETTINGS_MENU/logo`

Runtime smoke testing also showed that `Sprite.Create` returns null for `sharedassets1__Sprite__260__unnamed_260.png` in this IL2CPP runtime. For that reason, sprite replacement remains disabled for the main title path and the plugin uses texture-content overwrite instead.

Manual QA protocol for the current build:

1. Launch the game and watch the startup/title splash. The huge Russian `НЕ СПИТЕ С РЫБАМИ` should not appear over the splash in this isolation mode.
2. On the first main menu, check whether the title is Russian and whether the large white rectangle is gone.
3. Open settings. The settings logo should remain unpatched in this pass.
4. Enter or continue gameplay. The journal icon/label should remain unpatched in this pass, and the previous white square near the journal UI should not appear.
5. Return to the main menu. The title should not turn into a persistent white rectangle or revert unexpectedly.

If the title is still visually wrong, the next texture iteration should keep all other groups disabled and refine only the main title texture overwrite path before enabling any other replacement group.

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

Visible texture names are written to `debug_reports/runtime_visible_texture_targets.tsv` during runtime tests. Problem-object component dumps are written to `debug_reports/runtime_problem_texture_components.tsv`.

The current dump includes scene name, object path, component type, hierarchy active state, sprite/texture names, material texture property, UI rect size, texture size, matched replacement filename, and whether the current texture is already a plugin replacement. This is intended to diagnose scene changes and cases where a Unity UI object restores the original sprite/texture after the plugin has patched it.
