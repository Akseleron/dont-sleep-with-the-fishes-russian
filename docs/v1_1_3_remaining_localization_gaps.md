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

## Still Needs Runtime Route Coverage

- Rare endings and friend fate combinations.
- Night events with Row, Frederik, Laurel, and Captain Whiskers variants.
- Journal entries reached through less common event outcomes.
- How-to-play slides after the runtime TMP correction, especially pages beyond `TUT_0`.
- Company notes assigned late on ending screen after the narrow runtime correction.
- Health status hover tooltips after the narrow runtime correction.
- Search/result panels after multiple result types.

## Texture-Only

- Main menu logo/title still shows `Don't Sleep With The Fishes`.
- Exact texture asset/path_id has not been identified from screenshot alone.
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
- Dictionary exact matching cannot guarantee late runtime text will be translated if the game rewrites text after XUnity refresh; company note variants need runtime verification.

## Support Claim

Do not claim v1.1.3 support yet. The next phase should reinstall the dev payload into a clean v1.1.3 copy, run the game with visible audit enabled, collect logs/screenshots, and verify the fixes listed in the runtime checklist.
