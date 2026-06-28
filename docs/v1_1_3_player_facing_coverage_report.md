# v1.1.3 Player-Facing English Coverage Report

Date: 2026-06-28

## Scope

This pass broadened v1.1.3 player-facing coverage using the existing inventory, dump, and workset outputs. It did not patch Unity assets, run the game, build release archives, enable runtime texture replacement, or implement TMP/font replacement.

## Outputs

- Added `scripts/audit_player_facing_coverage.py`.
- Generated `docs/v1_1_3_player_facing_english_coverage.tsv`.
- Regenerated `docs/translation_workset_v1_1_3.tsv`.
- Updated source translations and regenerated XUnity dictionaries/payload text files.
- Updated `docs/v1_1_3_runtime_test_checklist.md`.

## Coverage Summary

- Total reviewed candidate rows: 3,089
- Already translated rows: 1,345
- New source translation rows added in this phase: 52
- Existing active source rows updated or confirmed with safer text: 7
- Remaining `needs-context` rows: 1,472
- High-priority `needs-context` rows: 395
- Ignored technical/noise rows: 272

Status counts in `docs/v1_1_3_player_facing_english_coverage.tsv`:

- `done`: 1,345
- `needs-context`: 1,472
- `ignore-technical`: 265
- `raw-fragment-do-not-translate`: 7

## Screenshot-Confirmed Strings Added or Changed

The following screenshot/runtime-confirmed source strings were added or updated through `translations/source_queue.tsv` and regenerated into both active and payload XUnity dictionaries:

- `Visit the small island?` -> `Посетить островок?`
- `Get the Barrel!` -> `Достать бочку!`
- `Support?` -> `Помочь?`
- `Bait guarantees catches today.` -> `С наживкой улов гарантирован.`
- `Cause of Death:` -> `Причина смерти:`
- `Your boat fell apart.` -> `Шлюпка развалилась.`
- `Days Survived:` -> `Дней выжито:`
- `Food Eaten:` -> `Еды съедено:`
- `Fish Caught:` -> `Рыбы поймано:`
- `Items Used:` -> `Предметов использовано:`
- `Company's Note:` -> `Заметка компании:`
- `Calculated risk.` -> `Рассчитанный риск.`
- `Dragged to the seafloor.` -> `Утащило на дно.`
- `Everything under control.` -> `Всё под контролем.`
- `The End` -> `Конец`
- `Click to Cancel!` -> `Нажмите, чтобы отменить!`
- `Empty...` -> `Пусто...`
- `Nails Left:` -> `Гвоздей осталось:`
- `You are unprepared.` -> `Вы не готовы.`
- `Item Lost` -> `Потеряно`
- `Items Lost` -> `Потеряно`
- `You lost an item to the sea.` -> `Предмет унесло в море.`
- `Item Broken` -> `Предмет сломан`
- `Items Broken` -> `Сломано`

Narrow regexes were added for dynamic labels that keep numeric or rich-text suffixes, including `Nails Left: N` and end/stat labels with TMP tags. No exact numeric weight rows and no bare `kg=кг` row were added.

An older active exact row, `Nails Left: 4`, was removed from `translations/source_queue.tsv` so the dynamic nail-count label is handled by the stable prefix and regex instead of a single observed number.

## Additional High-Confidence Strings Added

This phase also added compact translations for complete high-confidence event, prompt, and ending strings, including:

- `Dead by the Sea.` -> `Погиб в море.`
- `Your friend is sleeping with the fishes.` -> `Ваш спутник спит с рыбами.`
- `Something broke during the night.` -> `Ночью что-то сломалось.`
- `You did not sleep very well.` -> `Вы плохо поспали.`
- `You feel weak.` -> `Вы ослабли.`
- `Help may be on the way...` -> `Возможно, помощь уже близко...`
- `Hand over diving gear?` -> `Отдать снаряжение?`
- `Give fishnet?` -> `Отдать сеть?`
- `Pick up chest?` -> `Подобрать сундук?`
- `Set foot on land?` -> `Ступить на сушу?`
- `Reached land.` -> `Добрался до суши.`
- `Eaten alive.` -> `Съеден заживо.`
- `Became chest loot.` -> `Стал добычей сундука.`
- `Mauled to death.` -> `Растерзан.`
- `The fog came.` -> `Пришёл туман.`
- `Sharing blood with the sea.` -> `Кровь смешалась с морем.`
- `Found by cargo ship.` -> `Найден грузовым судном.`
- `Found by the company.` -> `Найден компанией.`
- `Grabbed into stomatch.` -> `Затащен в желудок.`
- `Were being watched.` -> `За вами наблюдали.`
- `Torn into pieces.` -> `Разорван на части.`
- `Delusions became too strong.` -> `Бред стал слишком сильным.`
- `Trafficed to ghosts.` -> `Продан призракам.`
- `Debt Overdue.` -> `Долг просрочен.`
- `SLEEP` -> `СПАТЬ`
- `Stared at the moon for too long.` -> `Слишком долго смотрел на луну.`

## Focused Stale Translation Cleanup

Active source/generator/payload files were updated where stale or long translations were still preferred:

- `Boat Damaged`: `Шлюпка повреждена` -> `Шлюпка сломана`
- `Items Broken`: `Сломано предметов` -> `Сломано`
- `Items Lost`: `Потеряно предметов` -> `Потеряно`
- `Pick up chest?`: `Поднять сундук?` -> `Подобрать сундук?`
- Exact company note TMP row: `Записка компании`/`Просчитанный риск` -> `Заметка компании`/`Рассчитанный риск`
- Removed old exact dynamic row `Nails Left: 4` in favor of `Nails Left:` plus a narrow regex.

Old strings such as `Энергетический батончик`, `Поиск ничего не дал.`, `В процессе был поврежден акваланг.`, `Найдено предметов`, and `Сломано предметов` still appear in historical audit/workset evidence where they document previous state. They are not preferred active source translations after regeneration.

## Result/Search Overlap Finding

The active source queue and generated dictionaries now use:

- `Search Results` -> `Результаты`
- `Your search did not yield results.` -> `Ничего не найдено.`

No active source queue or generated dictionary entry currently maps a live source string to `ПОИСКА`. The `ПОИСКА` evidence remains in historical docs/workset notes and likely comes from a separate visible label, baked/offline texture, or another object layer that remains visible under the translated title.

Conclusion: a dictionary-only change cannot confidently solve the remaining `Результаты` + `ПОИСКА` overlap. This should be marked as a runtime layout/texture validation issue. Do not change global UI layout blindly; if clean runtime testing confirms two visible layers, use a narrow runtime/plugin or texture-specific strategy later.

## Remaining High-Priority Needs-Context Rows

The highest-priority unresolved rows are not safe for broad automatic translation in this phase:

- Ending/company note fragments: `Extensive layoffs executed.`, `High-impact failure.`, `Recovery efforts failed.`
- Large journal/event TextAsset bodies in `resources.assets/TextAsset/158__journals.txt`
- Dialogue TextAsset sections in `resources.assets/TextAsset/160__dialogues.txt`
- Some UI/action/status strings that need runtime screenshots or neighbouring object review before adding concise translations

These should be handled in a dedicated narrative/dialogue pass because many entries are long, contextual, or contain character/route variants.

## Runtime Checks Still Needed

- Clean v1.1.3 install with the updated payload.
- Search/result paper overlap and no-result text overlap.
- Left notification clipping for found/lost/broken/boat-damaged notifications.
- Item card clipping for compact item names and descriptions.
- End/death screen stat labels and company note regex behavior.
- Dynamic `Nails Left: N` behavior.
- Existing `Weight: Xkg` and `<b>Weight:</b> Xkg` regex behavior.
- Texture validation with `--apply-textures` or the full patcher; previous `--skip-textures` installs do not validate texture patches.
