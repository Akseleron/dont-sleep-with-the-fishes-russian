# v1.1.3 Texture Replacement Workflow

Texture localization is now wired into the static offline patch path for the approved v4 `Texture2D` replacements. Visual validation is still required before release.

## Inputs

- Full review export: `build/dswf_v1_1_3_all_textures_for_manual_review/manifest.tsv`
- Template: `docs/v1_1_3_texture_replacement_manifest_template.tsv`
- Active replacement manifest: `docs/v1_1_3_texture_replacement_manifest.tsv`
- Active static payload: `dist/dswf-rus-patcher/payload/textures/`
- Current tooling:
  - `scripts/export_unity_textures.py`
  - `scripts/patch_unity_textures.py`
  - `scripts/inventory_unity_textures.py`
  - `scripts/select_texture_candidates.py`

## Mapping Rules

- Map replacements by `source_asset_file`, `source_type`, and `source_path_id`.
- Keep `source_name`, dimensions, and notes for human review, but do not use names alone as identity.
- Replacement dimensions must match the source dimensions unless a later patcher change explicitly supports resizing.
- Commit replacement PNGs only after they are approved and copied into the active payload location.
- Do not commit exported review folders or review ZIPs under `build/`.

## Future Replacement Manifest

Use the template columns:

- `source_asset_file`
- `source_type`
- `source_path_id`
- `source_name`
- `source_width`
- `source_height`
- `replacement_file`
- `replacement_width`
- `replacement_height`
- `status`
- `notes`

Recommended statuses:

- `candidate`
- `approved`
- `rejected`
- `needs-redraw`
- `needs-runtime-check`

The v4 archive uses these statuses:

- `approved`: dimensions match original metadata and the row is a `Texture2D` supported by the offline patcher.
- `unsupported_type`: the row is a `Sprite`; the current offline patcher does not apply Sprite replacements.

## Safety

- Runtime texture replacement remains disabled: `EnableTextureFix = false`.
- Texture validation uses the safe offline patcher path through `scripts/dev_install_to_game.py --apply-textures` or the GUI patcher texture application.
- Extraction-only Windows/Linux ZIPs do not patch Unity asset files. If built with `--include-textures`, they include `_dswf_rus_texture_payload/` for inspection/manual installer testing only.

## Current v4 Result

- Incoming archive: `TEXTURES_REWORKED_v4.rar`
- Extracted files: 16 PNGs.
- Approved static payload rows: 9 `Texture2D` PNGs.
- Unsupported rows: 7 `Sprite` PNGs.
- Clean dev install with `--apply-textures` applied all 9 approved rows.
- Manual visual validation is still required with `docs/v1_1_3_texture_runtime_checklist.md`.

The active static payload was replaced with the approved v4 `Texture2D` set. These legacy payload rows were removed from `dist/dswf-rus-patcher/payload/textures/` because they are not present in the v4 approved manifest; `sharedassets3__Texture2D__106__unnamed_106.png` and `sharedassets3__Texture2D__120__unnamed_120.png` also mismatched v1.1.3 original dimensions:

- `sharedassets1__Texture2D__107__unnamed_107.png`
- `sharedassets3__Texture2D__106__unnamed_106.png`
- `sharedassets3__Texture2D__120__unnamed_120.png`
- `sharedassets3__Texture2D__129__unnamed_129.png`
