# v1.1.3 Texture Localization Plan

## Current Finding

Manual screenshot evidence confirms that the main menu title/logo texture still contains English text: `Don't Sleep With The Fishes`.

This is not a dictionary or XUnity text issue. It is classified as `texture_text`.

## Available Inputs

- Exported image manifest: `build/dswf_v1_1_3_images_for_review/manifest.tsv`
- Exported review images: `build/dswf_v1_1_3_images_for_review/`
- Existing texture tooling:
  - `scripts/inventory_unity_textures.py`
  - `scripts/select_texture_candidates.py`
  - `scripts/export_unity_textures.py`
  - `scripts/patch_unity_textures.py`

The exported image folder and any review ZIPs must remain uncommitted.

## Safe Process

1. Review exported PNGs/contact sheets and identify exact source asset, path_id, kind, dimensions, and exported PNG for the title/logo.
2. Check whether a Russian replacement already exists in project texture replacement folders.
3. If no replacement exists, create a replacement separately and verify it matches dimensions/alpha/format expectations.
4. Apply only through existing offline texture patch tooling or the full patcher path.
5. Test on a clean v1.1.3 copy with `--apply-textures` or the full patcher texture application.
6. Keep runtime texture replacement disabled.

## Explicit Non-Goals For This Pass

- Do not enable runtime texture replacement.
- Do not patch Unity assets directly without existing safe tooling.
- Do not commit exported images, screenshots, game files, or build ZIPs.
- Do not claim texture localization is fixed until the logo replacement is applied and tested.

## Remaining Questions

- Exact logo texture asset/path_id is still unknown from screenshot alone.
- Other texture-only English may exist in atlases or button images and needs visual review.
- Texture validation has not been performed because the recent dev installs used `--skip-textures`.
