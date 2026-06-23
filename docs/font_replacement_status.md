# Font replacement status

Status: **not implemented**

## Summary

Russian text and offline Texture2D replacements are currently the supported parts of the DSWF Russian patch.

TMP font replacement is intentionally not enabled in release builds yet.

The game uses TextMeshPro TMP font assets based on the original `Stimcard` font. These assets do not contain Cyrillic glyph coverage, so Russian text is rendered through the current available fallback/visual behavior rather than through a clean bundled Cyrillic TMP font replacement.

## Known TMP font assets

The relevant TMP font assets are:

| Asset file             | Path ID | TMP font asset                |
| ---------------------- | ------: | ----------------------------- |
| `sharedassets1.assets` |   `321` | `Stimcard SDF OutLine Lowres` |
| `sharedassets1.assets` |   `322` | `Stimcard SDF OutLine`        |
| `sharedassets1.assets` |   `323` | `Stimcard SDF`                |
| `sharedassets3.assets` |   `391` | `Stimcard_LowRes`             |

Known character ranges:

`32 - 126, 160, 8203, 8230, 9633`

These ranges do not include Cyrillic.

## Investigation results

### UnityPy

UnityPy can see the TMP font assets as `MonoBehaviour` objects and can read basic shell fields:

* `m_GameObject`
* `m_Enabled`
* `m_Script`
* `m_Name`

However, it does not currently deserialize the full TMP font asset data for this game version. The needed fields are not available through the current UnityPy path:

* `m_CharacterTable`
* `m_GlyphTable`
* `m_AtlasTextures`
* `m_FaceInfo`
* `m_SourceFontFile`
* `m_Material`
* `m_FallbackFontAssetTable`

Observed failure examples:

* `Expected to read 9924 bytes, but only read 60 bytes`
* `Expected to read 9916 bytes, but only read 52 bytes`
* `Expected to read 48784 bytes, but only read 44 bytes`
* `Expected to read 9912 bytes, but only read 48 bytes`

### UABEA

UABEA can locate the TMP font assets by name and Path ID, but `View Data` fails to deserialize the TMP font asset data.

Observed message:

`Asset failed to deserialize. The file version may be too new for this tpk or the file format is custom.`

### Runtime AssetBundle / BepInEx font path

Runtime font replacement through AssetBundle / TMP fallback was investigated but is not considered reliable enough for release.

Observed blockers included IL2CPP/.NET interop issues around AssetBundle loading and runtime font creation.

Runtime font replacement should remain disabled for release builds.

## Release decision

Do not expose font replacement as a working release feature yet.

Allowed release behavior:

* Russian text: supported
* Offline texture replacement: supported
* TMP font replacement: not implemented

If a patcher UI or CLI exposes a font option, it must clearly report:

`Font replacement is not implemented yet. No files were changed for fonts.`

## Future options

Possible future research paths:

1. AssetRipper-based investigation of TMP font asset structure.
2. Custom serialized TMP_FontAsset patcher for Unity 6000.2.7f2.
3. Generating replacement TMP font assets in a matching Unity version and finding a safe offline import path.
4. Glyph atlas remap hack as a last-resort workaround:

   * keep original TMP character tables;
   * replace glyph images in existing atlas slots;
   * remap Russian text into those slots;
   * avoid breaking TMP tags and remaining Latin text.

The glyph atlas remap hack is not preferred and should only be considered if proper TMP asset replacement remains blocked.
