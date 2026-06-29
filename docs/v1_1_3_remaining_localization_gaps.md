# v1.1.3 Remaining Localization Gaps

This report is deliberately conservative. The current pass improves broad text coverage, but it does not prove full v1.1.3 localization.

## Fixed In This Pass

- Runtime-visible English from tester audits:
  - `Be a bad fisherman...`
  - `Click to Shoo!`
  - `Frederik`
  - `Make an offer.`
  - `Needs fixing`
  - `Row's fate is unknown.`
  - `Frederik's fate is unknown.`
  - `Send Frederik Instead?`
  - `What do you think? Should we do this?`
- Ending company note exact variants, including all observed/suspected note values from `EndingController`.
- How-to-play/tutorial paragraph variants for tagged and plain runtime forms.
- `resources.assets` journal/dialogue exact-key coverage.
- Several layout-risk Russian strings shortened.
- Merged tester audit reports are now stored as processed docs.

## Fixed In Narrow Runtime Pass

- `MENU/UI/Canvas_Tutorial/MENU/CONTENT/TUT_0/howtoplay_txt` is corrected directly by the runtime plugin when the TMP text still contains the English opening tutorial paragraph. XUnity dictionary rows existed, but the live TMP component did not apply them reliably.
- `MENU/UI/Canvas/MedalsButton/runs_text` is corrected directly by the runtime plugin for one-line, newline, and whitespace-normalized `Runs: X Record: Y Days` forms. The result keeps two Russian lines so it fits the main menu stats block.
- Ending company note lines are corrected directly by the runtime plugin for known exact `Company's Note: "..."` variants when they are late-assigned on the ending canvas.
- Health hover tooltip late/runtime variants `Hurts a bit` and `Everything hurts` now have dictionary entries and a narrow runtime correction for `UI/HUD/Health/HoverBox_health/mood_info`.
- Fishing/item card text `A tape record...?` is shortened to `Аудиозапись...?`.
- The observed bad item tooltip text `Два работает.` is corrected at runtime to `2 применения.` only in item/tooltip-like contexts. The original English source for this bad Russian runtime text was not found in the current static inventory.
- These fixes still need clean v1.1.3 screenshot/audit verification before they are treated as fully validated.

## Runtime Text Safety Net

- The runtime plugin now loads the installed XUnity exact dictionary and narrow regex file, then reapplies translations to active visible TMP/UI text after scene load and at a low recurring interval.
- This is intended for player-facing UI text assigned after XUnity's initial pass, including ending friend fate lines, company notes, ending death causes, and fishing result weight lines.
- The pass still filters obvious technical values such as seeds, versions, resolutions, paths, developer branding, and isolated key labels.
- Runtime-composed ending/fishing families now have focused parsers:
  - `Cause of Death: <TMP tags><reason>` translates the label and known reason atoms while preserving TMP tags.
  - `friend_fate` text is translated by known sentence atoms, so `Frederik could not make it. Captain Whiskers may wander the sea alone.` and newline variants do not require every exact combined row.
  - `Company's Note: "<value>"` translates all known values and keeps `???` as a valid unknown placeholder with the Russian prefix.
  - Fishing result `Weight:` lines support dot and comma decimals in plain, bold, and multiline forms.
- `scripts/validate_runtime_visible_english.py` now treats unapproved visible English as a validation failure.
- The dynamic ending/fishing blockers from the previous audit are covered after `e10aa5d`; a fresh runtime audit after this pass is still required for confirmation.
- The latest stale audit now fails only on `Improves eating efficiency today.` and standalone `Laurel`; both were added in this FriendManageUI pass.
- The validator intentionally allows Russian text with isolated keybind tokens such as `F`, and translated credits lines that preserve developer/tester names.

## Fixed In FriendManageUI Pass

- `Improves eating efficiency today.` -> `Сегодня еда сытнее.`
- `Laurel` -> `Лорел` as a standalone visible FriendManageUI shipmate name.
- Verified existing FriendManageUI coverage for `Prepare Bait`, `Boost eating?`, `Bait guarantees catches today.`, `Makes repairing less demanding today.`, `Feed?`, `Heal?`, and `Talk?`.
- Verified standalone visible `Row`, `Frederik`, and `Captain Whiskers` are already covered. `Dorothy` is covered in player-facing prose/exact lines; no standalone visible name-row failure was found.
- Shortened the FastForward setting text to `Если включено: F ускоряет ночные события.`
- Runtime diagnostics now ignore TMP tag Latin when deciding whether text still contains English.

## Still Needs Runtime Route Coverage

- Rare endings and friend fate combinations.
- Death-cause variants not yet reached in runtime screenshots, especially rare route endings.
- Night events with Row, Frederik, Laurel, and Captain Whiskers variants.
- Journal entries reached through less common event outcomes.
- How-to-play slides after the runtime TMP correction, especially pages beyond `TUT_0`.
- Company notes assigned late on ending screen after the narrow runtime correction.
- Fishing result cards with several fish names and both comma/dot decimal weights after the regex/runtime parser update.
- Health status hover tooltips after the narrow runtime correction.
- Search/result panels after multiple result types.

## Texture-Only

- Main menu logo/title still shows `Don't Sleep With The Fishes`.
- Exact texture asset/path_id has not been identified from screenshot alone.
- A full local texture export for manual review was prepared at `build/dswf_v1_1_3_all_textures_for_manual_review/`, with manifest `build/dswf_v1_1_3_all_textures_for_manual_review/manifest.tsv` and optional review ZIP `build/dswf-v1.1.3-all-textures-for-manual-review.zip`.
- Texture validation requires `--apply-textures` or full patcher texture application.

## Layout And Clipping

- Main menu `Архив` button needs runtime check.
- Ending `Далее` button needs runtime check.
- Torn fishing net item card/tooltip needs runtime check.
- Journal `Взгляд смерти` title needs runtime check.
- How-to-play slide text needs runtime check.
- Left notifications and item cards still need screenshot verification after the shortened strings.

## Human Wording Review

- Some older TextAsset translations are still machine-draft quality even though they now have exact coverage.
- This pass fixed obvious bad grammar and runtime/layout-risk rows, not every stylistic issue.
- Further review should prioritize rows surfaced by `docs/v1_1_3_merged_runtime_layout_risk.tsv` and route screenshots.

## Known Audit Limitations

- Runtime visible audit can miss screens if they appear outside the scan window or use non-scanned render paths.
- Texture text is invisible to text-component auditing.
- AllText audit captures useful layout data, but it also captures technical/branding/key/resolution rows that should not be translated blindly.
- Dictionary exact matching alone cannot guarantee late runtime text will be translated if the game rewrites text after XUnity refresh. The runtime reapply pass is designed to cover that failure mode, but it still needs a fresh clean runtime audit.

## Support Claim

Do not claim v1.1.3 support yet. Release-candidate status is blocked until the dev payload is reinstalled into a clean v1.1.3 copy, visible audit is rerun, `scripts/validate_runtime_visible_english.py` passes, and screenshots verify the fixes listed in the runtime checklist.
