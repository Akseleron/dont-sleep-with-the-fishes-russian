# Russian Runtime Localization Test Checklist

Use a clean game copy with BepInEx IL2CPP and XUnity.AutoTranslator installed. Do not use the binary smoke-test `level3` file when validating the runtime package unless the test explicitly needs to compare both methods.

- [ ] Main menu: New Game, Load Game, Play, Back, difficulty labels, locked difficulty text.
- [ ] Settings: volume sliders, resolution prompt, brightness, mouse sensitivity, instant clicking, reset defaults, accept/cancel.
- [ ] Difficulty select: Adventure, selected state, unavailable/locked state, how-to panels.
- [ ] Gameplay HUD: food label, day/end-day label, journal label, status labels, distance/food/item feedback.
- [ ] Inventory/item prompts: Food, Fish Can, Fishnet, broken item names, repair/eat/search prompts.
- [ ] Journal: open/close journal, new/no entry states, handwritten prompt.
- [ ] Sleep prompt: Go To Sleep?, choices, night event text, item selection.
- [ ] Fishing prompt: Try Fishing, Needs Bait, Prepare Bait, Bait Consumed, fish names and weights.
- [ ] Font rendering: verify Russian Cyrillic glyphs render normally, not boxes/blanks.
- [ ] Hotkeys: ALT+T toggles translation, ALT+R reloads updated translation files, ALT+U attempts manual hook refresh if IL2CPP misses text.
