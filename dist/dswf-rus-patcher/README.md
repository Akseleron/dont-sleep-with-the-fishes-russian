# DSWF Russian Patcher Plan

This is a planning scaffold only, not a release package.

The eventual patcher should:

- accept the path to an installed `DontSleepWithTheFishes.exe`;
- verify `DontSleepWithTheFishes_Data/` exists;
- check supported game asset SHA/version before patching;
- create backups before touching Unity assets;
- apply offline Texture2D replacements through `scripts/patch_unity_textures.py` or equivalent packaged logic;
- install/update BepInEx + XUnity translation files if the user opts into the runtime text patch;
- install runtime plugin/config with `EnableTextureFix=false`;
- apply a font fix only after one is visually and legally confirmed;
- provide restore/uninstall command;
- write a readable log;
- refuse unknown game versions unless `--force` is explicitly passed.

Current blockers before release packaging:

- Font replacement is not solved. XUnity TMP fallback with `nyashasans.ttf` fails through the AssetBundle loader path.
- `nyashasans.ttf` has no verified redistribution license in this workspace.
- Dynamic fish weight text remains a separate runtime blocker.
- Manual QA is still required after each fit/layout change.
