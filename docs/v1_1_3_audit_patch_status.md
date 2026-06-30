# v1.1.3 Windows Audit Patch Status

Date: 2026-06-28

## What Changed

The runtime audit is now a Windows-first tester pipeline instead of a single local English-only TSV.

Runtime plugin changes:

- Normal tracked config keeps `EnableVisibleTextAudit = false`.
- Audit mode supports `EnglishOnly`, `MixedRuEn`, and `AllText`.
- Audit can capture English-only, mixed RU/EN, all visible text, and layout-risk Russian text.
- Audit output goes under `BepInEx/dswf_audit`.
- Runtime texture replacement remains disabled.
- TMP/font replacement is not implemented.

## Runtime Audit Layout

Per-session folder:

```text
BepInEx/dswf_audit/sessions/session_<timestamp>_<tester_id>/
```

Session files:

- `visible_text_raw.tsv`
- `visible_text_unique_by_location.tsv`
- `visible_text_unique_by_text.tsv`
- `visible_english_unique.tsv`
- `visible_mixed_ru_en_unique.tsv`
- `layout_risk.tsv`
- `session_summary.txt`

Global cumulative files:

- `BepInEx/dswf_audit/all_unique_visible_text_by_location.tsv`
- `BepInEx/dswf_audit/all_unique_visible_text_by_text.tsv`
- `BepInEx/dswf_audit/all_unique_english_text.tsv`
- `BepInEx/dswf_audit/all_unique_mixed_ru_en_text.tsv`
- `BepInEx/dswf_audit/all_layout_risk.tsv`
- `BepInEx/dswf_audit/audit_summary.txt`

Unique-by-location key:

```text
scene + full_transform_path + normalized_text
```

Unique-by-text key:

```text
normalized_text
```

## Windows Tester ZIP

Generated ZIP:

```text
build/dswf-rus-audit-patch-v1.1.3-windows.zip
```

This is an audit patch only. It does not include:

- `DontSleepWithTheFishes.exe`
- `DontSleepWithTheFishes_Data/`
- `UnityPlayer.dll`
- `GameAssembly.dll`

The ZIP audit config enables:

- `EnableVisibleTextAudit = true`
- `VisibleTextAuditMode = AllText`
- `VisibleTextAuditIntervalSeconds = 0.25`
- `VisibleTextAuditMaxScansPerScene = 200`
- `VisibleTextAuditOutputRoot = BepInEx/dswf_audit`

Normal tracked payload config remains release-safe:

- `EnableVisibleTextAudit = false`
- `VisibleTextAuditMode = EnglishOnly`

## Tester Workflow

1. Tester extracts `dswf-rus-audit-patch-v1.1.3-windows.zip` into their own v1.1.3 game folder.
2. Tester runs `run_dswf_rus_audit.bat`.
3. Tester plays normally and tries menu, options, fishing, search, inventory, support, night events, journal, deaths, and endings.
4. Tester closes the game.
5. Tester runs `collect_audit_logs.bat`.
6. Tester sends back `dswf_audit_logs_<COMPUTERNAME>_<YYYYMMDD_HHMMSS>.zip`.

The collector includes only audit/log/config files and `tester_notes.txt`, not game files.

## Merge Workflow

Put returned tester ZIPs into a local ignored folder, for example:

```text
tester_audits/
```

Then run:

```bash
.venv-tools/bin/python scripts/merge_tester_audits.py tester_audits
```

The merge script writes:

- `docs/v1_1_3_merged_runtime_visible_text_by_location.tsv`
- `docs/v1_1_3_merged_runtime_visible_text_by_text.tsv`
- `docs/v1_1_3_merged_runtime_english_review.tsv`
- `docs/v1_1_3_merged_runtime_layout_risk.tsv`
- `docs/v1_1_3_tester_audit_merge_report.md`

Do not commit tester ZIPs, extracted tester logs, or raw runtime audit files.

## Current Local Audit Import

The existing local `game_runtime_test_v1_1_3/BepInEx/visible_english_audit.tsv` was consumed into:

- `docs/v1_1_3_runtime_visible_english_review.tsv`
- `docs/v1_1_3_runtime_visible_english_audit_report.md`

That local raw TSV remains untracked and ignored.

## New Runtime Fixes

Added source-text translations for:

- `Shipmates sunk with the ship.`
- `Everything under control.`
- `Company's Note: "Everything under control."`
- main menu medal descriptions

Added regex:

```text
Runs: X Record: Y Days -> Забегов: X Рекорд: Y дн.
```

## What Not To Commit

- `build/dswf-rus-audit-patch-v1.1.3-windows.zip`
- `tester_audits/`
- tester ZIPs
- `game_runtime_test_v1_1_3/`
- `BepInEx` runtime logs
- runtime `visible_*.tsv` output
- screenshots
- `.local_dumps/`
- game files
- normal release archives

## Remaining Risks

- The audit mode has not yet been tested on a clean Windows machine.
- Layout-risk heuristics can flag intentional ellipses and should be reviewed with screenshots.
- Mixed RU/EN detection is now implemented, but real coverage depends on testers reaching the relevant screens.
- Texture validation still requires a separate `--apply-textures` or full patcher pass.
