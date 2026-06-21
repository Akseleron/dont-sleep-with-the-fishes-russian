# Russian test patch install notes

This workspace currently contains a minimal Russian smoke-test patch, not a full localization.

## What it changes

- Target file: `game_work/DontSleepWithTheFishes_Data/level3`
- Offset: `838332`
- Source: `Eat Fish!`
- Replacement: `Рыбу!`
- Method: equal-byte-length UTF-8 replacement inside a `TMPro.TextMeshProUGUI` serialized string.

## Rebuild from a clean working copy

1. Restore `game_work/` from `game_original/` or from a clean copy of the game.
2. From the workspace root, install the parser dependency in a local venv if needed:

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install UnityPy
   ```

3. Apply only rows marked `test`:

   ```sh
   .venv/bin/python scripts/apply_minimal_patch.py
   ```

4. The script creates a backup in `patches/backups/game_work/` and appends to `patches/changelog.tsv`.

## Manual install over a clean game

For this test patch only, replace the clean game's `DontSleepWithTheFishes_Data/level3` with the patched `game_work/DontSleepWithTheFishes_Data/level3`.

The safer reproducible method is to run `scripts/apply_minimal_patch.py` against a working copy, because it verifies the source bytes and length field before writing.

## Revert

Copy `patches/backups/game_work/DontSleepWithTheFishes_Data/level3` back to `game_work/DontSleepWithTheFishes_Data/level3`, or restore the file from `game_original/DontSleepWithTheFishes_Data/level3`.
