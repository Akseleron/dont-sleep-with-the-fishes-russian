# v1.1.3 Runtime Screenshot Regression Report

Date: 2026-06-28

## Scope

Manual runtime testing after `765d577` showed that flat dictionary coverage is not enough. This phase adds a runtime-visible English audit mode and a block-based UI coverage report, then applies only high-confidence source-text fixes from visible screenshots and nearby dump context.

The game was not run in this phase. Release archives were not built. Runtime texture replacement remains disabled, and TMP/font replacement is still not implemented.

## Runtime Visible-English Audit

`DSWF Russian Runtime Fix` now has a disabled-by-default development audit:

- `EnableVisibleTextAudit = false`
- `VisibleTextAuditIntervalSeconds = 1`
- `VisibleTextAuditMaxScansPerScene = 30`

When enabled, it writes:

```text
BepInEx/visible_english_audit.tsv
```

The TSV records scene, scan number, component type, GameObject name, full transform path, current text, normalized text, block guess, rect size, font size, active state, and notes. It does not modify text.

## Block Coverage

Generated:

```text
docs/v1_1_3_ui_block_coverage.tsv
```

Rows: 2,875

Block counts:

- `OptionsMenu`: 35
- `MainMenu`: 1
- `HealthStatusHUD`: 3
- `HungerStatusHUD`: 3
- `FriendSupportPanel`: 12
- `ItemCard`: 7
- `BrokenItemActionPrompt`: 3
- `SearchResultPaper`: 23
- `LeftNotification`: 7
- `NightEventChoice`: 4
- `NightEventResult`: 1
- `FishingResultCard`: 8
- `EndingStatsScreen`: 33
- `Journal`: 518
- `Dialogue`: 424
- `UnknownNeedsContext`: 1,793

The high `UnknownNeedsContext`, `Journal`, and `Dialogue` counts are expected; narrative text needs a separate translation pass with context, not automatic one-line fixes.

## Screenshot-Confirmed English Fixed

Options/menu:

- `Restore Defaults` -> `Сбросить`
- `Fast-Forwarding` -> `Ускорение`
- `(While ON: Press 'F' to Fast-Forward time during the beginning of night events.)` -> `Если включено: нажмите F, чтобы ускорить начало ночных событий.`

Fishing result:

- `Weight:` -> `Вес:`
- Added multiline regexes that preserve fish/result text and translate embedded `Weight: Xkg` or `<b>Weight:</b> Xkg` lines.

Health/status HUD:

- `I don't feel good` -> `Мне нехорошо`
- `I'm dying...` -> `Я умираю...`
- `I have some pain` -> `Мне больно`
- `I'm starving` -> `Я умираю от голода`
- `Hungry` -> `Голод`
- `Starving` -> `Голод`

Friend/support panel:

- `Depressed` -> `Подавлен`
- `Miserable` -> `В отчаянии`
- `Bored` -> `Скучает`
- `Happy` -> `Счастлив`
- `Row does not feel well...` -> `Роу нездоровится...`
- `Makes repairing less demanding today.` -> `Ремонт сегодня проще.`
- `Support?` -> `Помочь?`

Action/night prompts:

- `Fix by hand` -> `Починить вручную`
- `Click to Cancel!` -> `Нажмите, чтобы отменить!`
- `Try skipping the night?` -> `Попробовать пропустить ночь?`
- `You sleep guarded tonight...` -> `Сегодня вы спите под охраной...`
- `Send Row Instead?` -> `Отправить Роу?`
- `... Just wait here.` -> `... Просто жди здесь.`
- `Check the back?` -> `Посмотреть назад?`

Ending/death screen:

- `Starved to death.` -> `Умер от голода.`
- `Calculated risk.` -> `Рассчитанный риск.`
- `Row could not make it.` -> `Роу не выжил.`
- `Captain Whiskers may wander the sea alone.` -> `Капитан Усатик может скитаться по морю в одиночестве.`

Left notification compact fixes:

- `Item Found` -> `Найдено`
- `Items Found` -> `Найдено:`
- `Item Broken` -> `Сломано`
- `Items Broken` -> `Сломано`
- `Item Lost` -> `Потеряно`
- `Items Lost` -> `Потеряно`
- `Boat Damaged` -> `Шлюпка`

Item card/action text:

- `Broken Compass` -> `Компас сломан`
- `Broken Scuba Set` -> `Акваланг сломан`
- `Torn Umbrella` -> `Рваный зонт`
- `Fix with tape!` -> `Починить скотчем!`
- `Looks reparable!` -> `Можно починить.`
- `Looks tasty!` -> `Выглядит вкусно.`
- `Soaked but readable.` -> `Намокло, но читаемо.`
- `Details are smudged.` -> `Детали размазаны.`

## Issue Classification

- Options/menu English: dictionary-fixable; fixed, needs runtime verification.
- Health/status HUD English: dictionary-fixable; fixed, needs runtime verification.
- Friend/support panel English: dictionary-fixable; fixed, needs runtime verification.
- Night prompts/results: dictionary-fixable for exact source strings; fixed where screenshot-confirmed.
- Fishing result `Weight: 0.9kg`: regex-fixable if the visible TMP text contains a multiline block with a Weight line; regex added, needs runtime verification.
- Left notification clipping: dictionary-fixable only up to compact title wording; if clipping persists with `Найдено`, `Сломано`, `Потеряно`, or `Шлюпка`, it is likely runtime/layout-fix-needed.
- Item card clipping: compact dictionary fixes applied for confirmed strings; remaining clipping may need context-specific runtime/layout handling.
- Result/search paper overlap: likely runtime/layout or texture/layer issue; dictionary-only fixes have not removed `ПОИСКА` overlap.
- Textures: not validated because the last dev install used `--skip-textures`; texture validation requires `--apply-textures` or full patcher texture application.

## Strings Intentionally Not Changed

- Large journal/event paragraphs remain `needs-context`; they need a narrative pass with neighbouring lines and route context.
- Dialogue blocks remain mostly `needs-context`; they should be translated in conversation clusters.
- No exact numeric `Weight: 0.9kg` row was added.
- No bare `kg=кг` row was added.
- Runtime texture replacement remains disabled.

## Runtime Follow-Up

After reinstalling the dev payload, enable `EnableVisibleTextAudit=true`, run the game, and inspect `BepInEx/visible_english_audit.tsv`. Use that TSV as the source of truth for the next coverage pass.
