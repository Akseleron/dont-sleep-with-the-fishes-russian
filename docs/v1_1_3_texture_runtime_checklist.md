# v1.1.3 Texture Runtime Checklist

Use this after installing a clean v1.1.3 test copy with texture patching enabled:

```bash
.venv-tools/bin/python scripts/dev_prepare_v1_1_3_test_copy.py
.venv-tools/bin/python scripts/dev_install_to_game.py game_runtime_test_v1_1_3 --clean-bepinex --apply-textures
```

The dev install report must contain:

- `textures_applied=True`
- `texture_payload_files=9`
- `runtime_texture_replacement=disabled`

The texture patch report must contain nine `applied` rows and no skipped/failed rows:

- `sharedassets1.assets:25` `newspaper`
- `sharedassets1.assets:28` `page`
- `sharedassets1.assets:50` `main_title`
- `sharedassets1.assets:106` `first_aid_kit`
- `sharedassets1.assets:109` `energybartest`
- `sharedassets3.assets:114` `endday_button`
- `sharedassets3.assets:130` `junk`
- `sharedassets3.assets:140` `journalicon`
- `sharedassets4.assets:204` `welcomesign`

## Visual Checks

- Main menu title/logo texture is localized and has no white rectangle, wrong scale, or wrong placement.
- Newspaper/page result textures show Russian text and do not overlap runtime text.
- First aid kit and energy bar textures still match the item identity; no flare gun/energy bar swap.
- End day button texture is localized and not cropped.
- Junk texture is localized and not swapped with another item.
- Journal icon texture is localized and has no white square artifact.
- Welcome sign/table texture displays `Добро пожаловать в Холтаг` if that replacement is visible in the route.
- No old English texture text remains on the replaced assets.
- Alpha/transparency is intact; no black, white, or pink missing-texture artifacts.
- No texture replacement warnings/errors appear in `BepInEx/LogOutput.log`.

## Unsupported Archive Rows

The v4 archive also contains seven `Sprite` PNGs. They are documented in `docs/v1_1_3_texture_replacement_manifest.tsv`, but the current offline patcher applies `Texture2D` objects only. Do not treat those Sprite rows as applied until the patcher explicitly supports safe Sprite metadata/cropping replacement.

## Runtime Text Gate

After manual gameplay creates a fresh audit folder, run:

```bash
.venv-tools/bin/python scripts/validate_runtime_visible_english.py game_runtime_test_v1_1_3/BepInEx/dswf_audit
```

Expected after a fresh texture-enabled run: `unapproved_visible_english=0`.
