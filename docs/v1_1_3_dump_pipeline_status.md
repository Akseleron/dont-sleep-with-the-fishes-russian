# v1.1.3 Dump Pipeline Status

Generated during the dump-pipeline phase. No translation fixes were applied.

## Files Changed

- `.gitignore`
- `scripts/dump_unity_readable_assets.py`
- `scripts/dump_binary_strings.py`
- `scripts/build_translation_workset.py`
- `docs/translation_workset_v1_1_3.tsv`
- `docs/weight_runtime_diagnostic_v1_1_3.md`
- `docs/v1_1_3_dump_pipeline_status.md`

## Dump Outputs

- Unity readable dumps:
  - `.local_dumps/unity_readable/v1_1_2/`
  - `.local_dumps/unity_readable/v1_1_3/`
- Binary/string dumps:
  - `.local_dumps/binary_strings/v1_1_2/binary_strings.tsv`
  - `.local_dumps/binary_strings/v1_1_3/binary_strings.tsv`
- Tool availability:
  - `.local_dumps/binary_strings/tool_availability.tsv`

`.local_dumps/` is ignored and must not be committed.

## Unity Readable Dump

Scanned `globalgamemanagers.assets`, `resources.assets`, `sharedassets0.assets` through `sharedassets5.assets`, and `level0` through `level5` when present.

| Version | Objects indexed | TextAssets dumped | MonoBehaviour/ScriptableObject/GameObject typetrees dumped | Raw MonoBehaviour string objects | Texture/Sprite metadata dumps |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1.1.2 | 35,344 | 8 | 12,996 | 2,380 | 1,167 |
| v1.1.3 | 35,371 | 8 | 13,210 | 2,165 | 884 |

Texture and sprite output is metadata only. No bulk PNG export was performed.

## Binary/String Dump

Scanned `GameAssembly.dll`, `DontSleepWithTheFishes_Data/il2cpp_data/Metadata/global-metadata.dat`, `UnityPlayer.dll`, `baselib.dll`, and selected Unity data files.

| Version | Raw/binary string rows |
| --- | ---: |
| v1.1.2 | 1,103,188 |
| v1.1.3 | 1,081,153 |

This is a byte/string/metadata dump only. It does not restore original C# source.

Detected local tool libraries:

- Cpp2IL libraries found inside BepInEx payloads (`Cpp2IL.Core.dll`, `LibCpp2IL.dll`).
- AssetRipper libraries found inside BepInEx payloads (`AssetRipper.CIL.dll`, `AssetRipper.Primitives.dll`).
- No standalone Cpp2IL, Il2CppDumper, Il2CppInspector, or AssetRipper executable was used or downloaded.

## Translation Workset

Output: `docs/translation_workset_v1_1_3.tsv`

Rows produced: 1,393.

Priority meanings:

- `1`: known visual/UI bugs.
- `2`: item names and mapping issues.
- `3`: event/dialogue strings.
- `4`: new v1.1.3 strings.
- `5`: remaining high-confidence player-facing strings.
- `6`: dynamic/runtime strings needing strategy.

## Top 30 Workset Rows

| Priority | Category | Source | Recommendation/current | Location |
| ---: | --- | --- | --- | --- |
| 1 | notification | `Item Broken` |  | `known_visual_ui_bugs:` |
| 1 | notification | `Item Found / Items Found clipped left notification` |  | `known_visual_ui_bugs:` |
| 1 | result/search | `RESULT/SEARCH paper title / ПОИСКА overlap` |  | `known_visual_ui_bugs:` |
| 1 | notification | `Scuba set was damaged in the process.` | `Акваланг повреждён.` | `known_visual_ui_bugs:` |
| 1 | notification | `You found` | `Найдено:` | `known_visual_ui_bugs:` |
| 1 | result/search | `Your search did not yield results.` | `Ничего не найдено.` | `known_visual_ui_bugs:` |
| 2 | ui | `Sleeping With The Fishes` | `Сон с рыбами` | `level1:path_id=1517:raw_length_prefixed@171228` |
| 2 | unknown | `Light Items` | `Легкие предметы` | `level1:path_id=1518:raw_length_prefixed@171772` |
| 2 | unknown | `Heavy Items` | `Тяжелые предметы` | `level1:path_id=1528:raw_length_prefixed@177084` |
| 2 | notification | `Time is running out! Gather whatever you can and toss it into your lifeboat, before the ship sinks...` | existing translation present | `level1:path_id=1529:raw_length_prefixed@177612` |
| 2 | notification | `If your night does get interrupted, use an item you brought to handle the situation...` | existing translation present | `level1:path_id=1548:raw_length_prefixed@187996` |
| 2 | unknown | `Super Energy` | `Суперэнергия` | `level1:path_id=1557:raw_length_prefixed@192924` |
| 2 | ui | `Use the daytime to spend your energy on fishing, eating, doing small tasks...` | existing translation present | `level1:path_id=1558:raw_length_prefixed@193452` |
| 2 | ui | `Don't Sleep With the Fishes` | `Не спи с рыбами` | `level1:path_id=1567:raw_length_prefixed@198476` |
| 2 | unknown | `Eat for Energy` | `Ешьте ради энергии` | `level1:path_id=1591:raw_length_prefixed@211564` |
| 2 | unknown | `kill/getfish/superhelp` |  | `level1:path_id=1616:raw_length_prefixed@225020` |
| 2 | unknown | `Be a bad fisherman...` |  | `level1:path_id=1834:raw_length_prefixed@274684` |
| 2 | unknown | `Bring exploration tools...` |  | `level1:path_id=1934:raw_length_prefixed@292240` |
| 2 | notification | `You lost an item to the sea.` |  | `level1:path_id=2074:raw_length_prefixed@334932` |
| 2 | ui | `Your friend is sleeping with the fishes.` |  | `level1:path_id=2074:raw_length_prefixed@334888` |
| 2 | notification | `Item Background` |  | `level1:path_id=436:m_Name` |
| 2 | notification | `Item Label` |  | `level1:path_id=443:m_Name` |
| 2 | item | `Item` |  | `level1:path_id=475:m_Name` |
| 2 | notification | `Item Checkmark` |  | `level1:path_id=479:m_Name` |
| 2 | notification | `If your night does get interrupted, use an item brought...` |  | `level1:raw_ascii@187996` |
| 2 | unknown | `Use the daytime to spend your energy on fishing, eating, doing small tasks...` |  | `level1:raw_ascii@193452` |
| 2 | ui | `When you run out of energy, end the day and try to sleep hoping nothing disrupts your rest.` |  | `level1:raw_ascii@193579` |
| 2 | notification | `You lost an item to the sea.!` |  | `level1:raw_ascii@334932` |
| 2 | item | `food_fish (1)` |  | `level2:path_id=1104:m_Name` |
| 2 | item | `bait` | `Наживка` | `level2:path_id=171:m_Name` |

## Weight Diagnostic

Output: `docs/weight_runtime_diagnostic_v1_1_3.md`

The diagnostic confirms a static rich TMP sample at `level3` path `4342`, GameObject `bottom`, and treats arbitrary numeric weight values as runtime-generated unless clean v1.1.3 logging proves XUnity sees them as full strings.

No exact numeric `Weight: Xkg` rows were added. No bare `kg=кг` row was added.

## Limitations

- The binary dump intentionally keeps broad discovery rows, so it contains substantial engine and metadata noise.
- UnityPy readable typetrees do not reconstruct stripped IL2CPP field names for every custom behaviour.
- Raw length-prefixed MonoBehaviour strings provide context, not stable patch addresses.
- The translation workset is an audit/work queue, not a patch.
- v1.1.3 support is still not claimed; clean runtime testing is required after future fixes.
