# v1.1.3 Texture Replacement Workflow

Texture localization is not done in this pass. The current work only prepares a manifest-based path for later approved replacement files.

## Inputs

- Full review export: `build/dswf_v1_1_3_all_textures_for_manual_review/manifest.tsv`
- Template: `docs/v1_1_3_texture_replacement_manifest_template.tsv`
- Current tooling:
  - `scripts/export_unity_textures.py`
  - `scripts/patch_unity_textures.py`
  - `scripts/inventory_unity_textures.py`
  - `scripts/select_texture_candidates.py`

## Mapping Rules

- Map replacements by `source_asset_file`, `source_type`, and `source_path_id`.
- Keep `source_name`, dimensions, and notes for human review, but do not use names alone as identity.
- Replacement dimensions must match the source dimensions unless a later patcher change explicitly supports resizing.
- Keep replacement PNGs out of git until they are final approved assets.
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

## Safety

- Runtime texture replacement remains disabled: `EnableTextureFix = false`.
- Texture validation must use either the safe offline patcher path or the GUI patcher texture application.
- Do not package texture replacements in Windows/Linux patch ZIPs until the replacement manifest and runtime screenshots are approved.
