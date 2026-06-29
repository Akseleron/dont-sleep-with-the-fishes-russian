# v1.1.3 Full Localization Audit

Date: 2026-06-29
Branch: `update-v1.1.3`
Baseline: `62e60eb add Windows v1.1.3 audit patch pipeline`

This pass used runtime tester audit merges, manual screenshot feedback, static Unity string inventories, readable Unity dumps, TextAsset resources, the translation workset, generated XUnity dictionaries, regex files, and the exported image manifest. It does not claim official v1.1.3 support.

## Inputs Reviewed

- Runtime tester logs from `tester_audits/`: 3 returned audit ZIPs, 66 TSV files read by `scripts/merge_tester_audits.py`.
- Merged runtime outputs:
  - `docs/v1_1_3_merged_runtime_visible_text_by_location.tsv`: 711 rows after whitespace cleanup.
  - `docs/v1_1_3_merged_runtime_visible_text_by_text.tsv`: 612 rows after whitespace cleanup.
  - `docs/v1_1_3_merged_runtime_english_review.tsv`: 15 rows including blank separator rows.
  - `docs/v1_1_3_merged_runtime_layout_risk.tsv`: 115 rows.
- Static reports:
  - `docs/string_inventory_v1_1_3.tsv`
  - `docs/untranslated_inventory_v1_1_3.tsv`
  - `docs/translation_workset_v1_1_3.tsv`: 1389 candidate rows.
  - `docs/v1_1_3_player_facing_english_coverage.tsv`: 3143 candidate rows.
  - `docs/v1_1_3_ui_block_coverage.tsv`: 2929 block rows.
- Readable dumps under `.local_dumps/unity_readable/v1_1_3/`.
- Binary/string dumps under `.local_dumps/binary_strings/v1_1_3/`.
- Exported texture manifest under `build/dswf_v1_1_3_images_for_review/manifest.tsv`; exported PNGs remain uncommitted.

## Classification Summary

| classification | status |
|---|---|
| fixed_text_translation | 57 source queue rows were added or updated in this pass. This includes runtime-visible strings, company note variants, tutorial variants, journal cells, dialogue cleanups, and compact UI labels. |
| fixed_regex_dynamic | Existing narrow regexes for `Weight: Xkg`, multiline fish-result weight lines, `Nails Left: N`, and `Runs: X Record: Y Days` were preserved. No exact numeric weight rows and no bare `kg=кг` entry were added. |
| fixed_layout_shortening | Shorter dictionary translations were applied for cramped global/context strings such as `Continue`, `Lore`, `Torn Fishing Net`, `Looks reparable!`, `Seems useable!`, friend fate lines, and several dialogue bubbles. |
| needs_context | Runtime audit rows `[E]`, `1920 x 1080`, credits with `DopplerGhost`, and route-locked/rare UI strings are not translated blindly. |
| texture_text | Main menu logo/title texture still shows `Don't Sleep With The Fishes`. It is classified as texture text and needs safe offline texture identification/replacement validation. |
| audit_miss | The how-to-play screenshot showed English text that did not appear in merged English rows. Exact tagged and no-tag variants were added, but the audit timing/component coverage still needs re-test. |
| technical_ignore | Developer/branding/version/seed/resolution/key-only rows are ignored unless later screenshot evidence shows they need localization. |
| remaining_risk | Clean v1.1.3 runtime testing is still required for route coverage, texture validation, clipping, and late runtime assignment. |

## Fixed Text Areas

- Runtime-visible tester audit rows:
  - `Be a bad fisherman...`
  - `Click to Shoo!`
  - `Frederik`
  - `Make an offer.`
  - `Needs fixing`
  - `Row's fate is unknown.`
  - `Frederik's fate is unknown.`
  - `Send Frederik Instead?`
  - `What do you think? Should we do this?`
- Company note regression:
  - Added exact full-line dictionary rows for all observed/suspected company note variants.
  - Added adjacent `EndingController` note values: `High-impact failure.`, `Extensive layoffs executed.`, and `Recovery efforts failed.`
  - No runtime hook was added in this pass; exact dictionary coverage is safer until a clean runtime test proves XUnity cannot catch a late assignment.
- How-to-play/tutorial:
  - Existing tagged source was shortened.
  - Added straight-apostrophe tagged and plain no-tag variants for the screenshot-confirmed story paragraph.
  - Shortened the first daytime/survival slides for fit.
- Journals/dialogues:
  - `resources.assets` journals: 159 rows, 314 text/title cells, 232 unique strings, 0 missing exact source-queue keys after this pass.
  - `resources.assets` dialogues: 180 rows, 415 dialogue cells, 412 unique strings, 0 missing exact source-queue keys after this pass.
  - Fixed six island journal variants, repeated moon journal text, bad journal titles, and several bad/long dialogue translations.

## Texture Status

The logo/title `Don't Sleep With The Fishes` remains a texture/image issue. Runtime texture replacement remains disabled. This pass only classified the texture work and created a candidate/plan document; it did not patch Unity assets.

## Support Status

Do not claim v1.1.3 support yet. A clean v1.1.3 runtime pass must verify:

- dictionary fixes in live UI;
- company note late assignment behavior;
- how-to-play screen text and slide layout;
- journal and ending route coverage;
- left notification, item card, and ending screen clipping;
- texture replacement through `--apply-textures` or the full patcher path.
