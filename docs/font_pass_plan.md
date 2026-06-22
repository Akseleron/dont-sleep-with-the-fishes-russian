# Font Pass Plan

## Current Observation

- Cyrillic renders in the current XUnity runtime test build, so the installed fallback path is usable for QA.
- The Russian glyphs do not match the original hand-drawn English UI/dialogue style.
- This is likely because the original TextMeshPro font asset does not contain Cyrillic glyphs, so TextMeshPro falls back to another font asset or font override for Russian text.

## Evidence To Inspect

- `extracted/font_report.tsv` currently lists the extracted font assets and glyph ranges.
- `extracted/visible_strings.tsv` for UI/dialogue object names, TMP field hits, and likely font-bearing objects.
- `docs/findings.md` for earlier notes about font rendering and XUnity/TMP behavior.
- Runtime logs from `game_runtime_test/BepInEx/LogOutput.log` after a full restart with Cyrillic text visible.

## Current Extracted Font Assets

From `extracted/font_report.tsv`:

- `resources.assets`:
  - `Font` `PerfectDOSVGA437`, embedded font bytes present, Cyrillic support unknown.
  - `Font` `LiberationSans`, embedded font bytes present, Cyrillic support unknown.
  - `TMP_FontAsset` `LiberationSans SDF - Fallback`, source font `Liberation Sans`, ranges `32 - 126, 160 - 255, 8192 - 8303, 8364, 8482, 9633`, likely no Cyrillic.
  - `TMP_FontAsset` `LiberationSans SDF`, same ranges, likely no Cyrillic.
- `sharedassets1.assets`:
  - `Font` `Stimcard`, embedded font bytes present, Cyrillic support unknown.
  - `TMP_FontAsset` `Stimcard SDF OutLine Lowres`, `Stimcard SDF OutLine`, and `Stimcard SDF`, source font `Stimcard`, ranges `32 - 126, 160, 8203, 8230, 9633`, likely no Cyrillic.
- `sharedassets3.assets`:
  - `TMP_FontAsset` `Stimcard_LowRes`, source font `Stimcard`, ranges `32 - 126, 160, 8203, 8230, 9633`, likely no Cyrillic.
- `sharedassets5.assets`:
  - `Font` `Essays1743`, embedded font bytes present, Cyrillic support unknown.
  - `TMP_FontAsset` `Essays1743 SDF`, source font `Essays1743`, likely no Cyrillic.
- `unity default resources`:
  - `Font` `LegacyRuntime`, no embedded font data.

The TMP font assets currently visible in the extraction do not include Cyrillic codepoint ranges. This supports the current hypothesis that Cyrillic renders through a runtime fallback/override rather than the original hand-drawn TMP assets.

## Current XUnity Font Options

`game_runtime_test/BepInEx/config/AutoTranslatorConfig.ini` exposes:

- `FallbackFontTextMeshPro=`
- `OverrideFontTextMeshPro=`

Both are currently empty in the config. A later font pass can use these options if a compatible TMP font AssetBundle is prepared and tested.

## Font Selection Requirements

- Cyrillic glyph support.
- License permits redistribution with the localization package.
- Visual style close to the original hand-drawn/rough UI font.
- Can be packed into a TMP SDF AssetBundle compatible with Unity `6000.2.7f2`.
- The user must provide or approve the exact font name, download/source URL, and license before any font is bundled.

No proposed chat font name/link/license is currently recorded in this repo.

## Later Font Pass

1. Identify the exact TMP font assets used by dialogue bubbles, HUD labels, journal text, and menu/button text.
2. Confirm whether those original TMP font assets lack Cyrillic glyphs.
3. Choose a Cyrillic-compatible font with a license suitable for redistribution.
4. Generate replacement or fallback TMP SDF font assets, or configure TMP fallback cleanly through the runtime pipeline.
5. Retest dialogue, journal, HUD, fishing results, and cramped buttons after the font change because different Cyrillic metrics can alter layout.

No fonts were downloaded, bundled, or replaced in the current QA cleanup pass.

## 2026-06-22 Runtime Inventory

- Runtime text inventory was written to `debug_reports/tmp_font_usage_inventory.tsv`.
- Static font inventory was written to `debug_reports/font_inventory.tsv`.
- Active TMP text objects still report original `Stimcard SDF*` font assets:
  - `Stimcard SDF OutLine`
  - `Stimcard SDF`
  - `Stimcard_LowRes`
  - `Stimcard SDF OutLine Lowres`
- Runtime fallback font tables were empty in the captured TMP objects.
- Static extraction still shows no Cyrillic ranges in the original TMP font assets.
- `nyashasans.ttf` exists locally at `_manual/nyashasans/nyashasans.ttf` and has Latin/Cyrillic coverage by `fc-scan`, but no license/readme was found next to it, so it must not be bundled yet.
- XUnity's real TMP keys are `FallbackFontTextMeshPro` and `OverrideFontTextMeshPro`. A runtime-only test with `FallbackFontTextMeshPro=nyashasans.ttf` failed because XUnity attempted the AssetBundle loader path and hit `AssetBundle::LoadFromFile_Internal(System.String,System.UInt32,System.UInt64) was not resolved`.
- Current recommendation: do not use XUnity TMP font override with raw TTF in this game. Keep the existing font behavior and continue targeted UI-fit fixes unless a licensed TMP font AssetBundle or offline TMP font patch workflow is proven safe.
