# Weight Runtime Diagnostic v1.1.3

Generated during the v1.1.3 dump-pipeline phase. This is diagnostic only.
No translation rows, regexes, plugin code, or config values were changed.

## Evidence

- `docs/string_inventory_v1_1_3.tsv` contains 30 weight/fishing-related rows.
- `docs/untranslated_inventory_v1_1_3.tsv` only adds noisy font-weight rows: `Weight Bold` and `Weight Normal`.
- `.local_dumps/unity_readable/v1_1_3/object_index.tsv` resolves the static rich weight sample to `level3`, `MonoBehaviour` path `4342`, script `Unity.TextMeshPro:TMPro.TextMeshProUGUI`, GameObject `bottom`.
- `.local_dumps/unity_readable/v1_1_3/level3/MonoBehaviour/4342__bottom.json` contains raw length-prefixed string `<b>Weight:</b> 0.5kg`.
- `docs/string_inventory_v1_1_3.tsv` also shows fish result/name context in `level3`, `MonoBehaviour` path `4764`, object `Task_Fishing`, including `Red Snapper`, `Clownfish`, and `Swordfish` near fishing result item strings.
- `.local_dumps/binary_strings/v1_1_3/binary_strings.tsv` contains 434 `weight/fishing` rows, but most are Unity engine/rendering metadata noise. The useful game-facing exact hit is `DontSleepWithTheFishes_Data/level3` offset `814492`: `<b>Weight:</b> 0.5kg`.
- Existing XUnity dictionary entries include `Weight:=Вес:`, `<b>Weight:</b>=<b>Вес:</b>`, fish names, and food suffixes.
- `patches/xunity_autotranslator/BepInEx/Translation/ru/Text/FishingRegex.txt` already contains regex hypotheses for plain and rich weight:
  - `Weight: Xkg` -> `Вес: X кг`
  - `<b>Weight:</b> Xkg` -> `<b>Вес:</b> X кг`
- Packaged XUnity config keeps `GeneratePartialTranslations=False`.
- Runtime plugin config keeps `EnableTextureFix = false`; this diagnostic does not change that.

## Likely Origin

The static template/sample appears as a TMP text object in `level3` path `4342`, GameObject `bottom`. The arbitrary numeric values seen in runtime QA, such as `Weight: 0.28kg`, `Weight: 1.21kg`, `Weight: 2.77kg`, and `Weight: 25.97kg`, are likely generated at runtime by fishing result code rather than stored as complete serialized Unity strings.

The fish names and fishing result neighbours live near `Task_Fishing` (`level3` path `4764` in v1.1.3). That object has the item/fish context needed for a targeted runtime formatter if regex translation does not fire.

## XUnity Regex Safety

XUnity regex is the safest first implementation path if runtime testing proves `FishingRegex.txt` is applied to the actual TMP text updates. The existing regexes are anchored and specific:

- They require `Weight:` or `<b>Weight:</b>`.
- They require a numeric value followed immediately by `kg`.
- They do not add a bare `kg=кг`.

This avoids the main false-positive risk from partial translation or broad unit replacement. Keep `GeneratePartialTranslations=False`.

## Runtime Plugin Option

If clean v1.1.3 runtime logs/screenshots show that XUnity never sees the dynamic weight string, the runtime plugin should handle it later with a narrow fishing-result formatter. The target should be the fishing result TMP context, not global TMP replacement:

- Match only text values shaped like `Weight: <number>kg` or `<b>Weight:</b> <number>kg`.
- Prefer limiting by scene/object context around `Task_Fishing`, `FishedInfoHolder`, or the `bottom` TMP object if runtime paths confirm them.
- Preserve rich text tags.

Do not use runtime texture replacement for this. TMP/font replacement remains unimplemented and unrelated.

## Do Not Do

- Do not add exact numeric rows such as `Weight: 0.52kg`.
- Do not restore generated ranges of exact numeric weight values.
- Do not add bare `kg=кг`.
- Do not enable partial translations in the packaged config.
- Do not claim v1.1.3 weight support until tested on a clean v1.1.3 install.

## Recommended Path

1. Keep the existing `FishingRegex.txt` hypothesis.
2. Runtime-test clean v1.1.3 with XUnity logging enabled enough to verify whether the live weight TMP text is observed and matched.
3. If regex works, keep the regex-only solution and do not add exact numeric rows.
4. If regex does not work, implement a minimal runtime fishing-result formatter in `DswfRusRuntimeFix` later, scoped to the fishing result text context.
5. Re-test with several numeric values, including values above earlier generated ranges.
