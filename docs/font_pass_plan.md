# Font Pass Plan

## Current Observation

- Cyrillic renders in the current XUnity runtime test build, so the installed fallback path is usable for QA.
- The Russian glyphs do not match the original hand-drawn English UI/dialogue style.
- This is likely because the original TextMeshPro font asset does not contain Cyrillic glyphs, so TextMeshPro falls back to another font asset or font override for Russian text.

## Evidence To Inspect

- `extracted/font_report.tsv` if present or regenerated in a later font-specific pass.
- `extracted/visible_strings.tsv` for UI/dialogue object names, TMP field hits, and likely font-bearing objects.
- `docs/findings.md` for earlier notes about font rendering and XUnity/TMP behavior.
- Runtime logs from `game_runtime_test/BepInEx/LogOutput.log` after a full restart with Cyrillic text visible.

## Later Font Pass

1. Identify the exact TMP font assets used by dialogue bubbles, HUD labels, journal text, and menu/button text.
2. Confirm whether those original TMP font assets lack Cyrillic glyphs.
3. Choose a Cyrillic-compatible font with a license suitable for redistribution.
4. Generate replacement or fallback TMP SDF font assets, or configure TMP fallback cleanly through the runtime pipeline.
5. Retest dialogue, journal, HUD, fishing results, and cramped buttons after the font change because different Cyrillic metrics can alter layout.

No fonts were downloaded, bundled, or replaced in the current QA cleanup pass.
