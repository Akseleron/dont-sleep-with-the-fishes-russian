using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using Il2CppInterop.Runtime.Attributes;
using Il2CppInterop.Runtime.InteropTypes.Arrays;
using Il2CppInterop.Runtime.Injection;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace DswfRusRuntimeFix;

[BepInPlugin(PluginGuid, PluginName, PluginVersion)]
public sealed class Plugin : BasePlugin
{
    public const string PluginGuid = "ru.dswf.runtimefix";
    public const string PluginName = "DSWF Russian Runtime Fix";
    public const string PluginVersion = "0.1.0";

    internal static ManualLogSource LogSource;
    internal static ConfigEntry<bool> EnableFontFix;
    internal static ConfigEntry<bool> EnableTextureFix;
    internal static ConfigEntry<bool> OverrideTmpFonts;
    internal static ConfigEntry<bool> DumpVisibleTextureNames;
    internal static ConfigEntry<string> FontFileName;
    internal static ConfigEntry<float> StartupScanSeconds;

    public override void Load()
    {
        LogSource = Log;
        EnableFontFix = Config.Bind("Font", "EnableFontFix", true, "Register a local TTF and create a runtime TMP fallback font asset.");
        OverrideTmpFonts = Config.Bind("Font", "OverrideTmpFonts", false, "Assign the runtime TMP font directly to TMP_Text objects. Fallback mode is safer and is tried first.");
        FontFileName = Config.Bind("Font", "FontFileName", "nyashasans.ttf", "TTF file under BepInEx/plugins/DswfRusRuntimeFix/Fonts.");
        EnableTextureFix = Config.Bind("Textures", "EnableTextureFix", true, "Replace visible runtime textures/sprites from the Textures folder.");
        DumpVisibleTextureNames = Config.Bind("Diagnostics", "DumpVisibleTextureNames", true, "Write visible texture/component names to ../debug_reports/runtime_visible_texture_names.tsv during scans.");
        StartupScanSeconds = Config.Bind("Diagnostics", "StartupScanSeconds", 15f, "Scan repeatedly for this many seconds after startup/scene load.");

        try
        {
            ClassInjector.RegisterTypeInIl2Cpp<RuntimeFixBehaviour>();
        }
        catch (Exception ex)
        {
            Log.LogWarning("Behaviour type registration reported an exception. Continuing: " + ex);
        }

        var go = new GameObject("DswfRusRuntimeFix");
        UnityEngine.Object.DontDestroyOnLoad(go);
        go.hideFlags = HideFlags.HideAndDontSave;
        go.AddComponent<RuntimeFixBehaviour>();
        Log.LogInfo($"{PluginName} {PluginVersion} loaded. FontFix={EnableFontFix.Value}, TextureFix={EnableTextureFix.Value}");
    }
}

public sealed class RuntimeFixBehaviour : MonoBehaviour
{
    private static readonly Regex ReplacementName = new(@"^(?<asset>sharedassets\d+)__(?<type>Texture2D|Sprite)__(?<pathId>\d+)__(?<name>.+)$", RegexOptions.Compiled);
    private readonly Dictionary<string, Replacement> byName = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, Replacement> byStem = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<int> patchedImages = new();
    private readonly HashSet<int> failedImages = new();
    private readonly HashSet<int> patchedRawImages = new();
    private readonly HashSet<int> patchedSpriteRenderers = new();
    private readonly HashSet<int> failedSpriteRenderers = new();
    private readonly HashSet<int> patchedRenderers = new();
    private readonly HashSet<int> patchedTmpTexts = new();
    private float scanUntil;
    private float nextScan;
    private int scanCount;
    private TMP_FontAsset runtimeTmpFont;
    private Font runtimeUnityFont;
    private bool fontAttempted;
    private string reportPath;

    public RuntimeFixBehaviour(IntPtr ptr) : base(ptr) { }

    private void Start()
    {
        scanUntil = Time.realtimeSinceStartup + Math.Max(3f, Plugin.StartupScanSeconds.Value);
        nextScan = 0f;
        reportPath = BuildDebugReportPath();
        Plugin.LogSource.LogInfo("RuntimeFixBehaviour started.");
        LoadReplacements();
        TrySetupFont();
        ScanAndPatch("startup");
    }

    private void Update()
    {
        var now = Time.realtimeSinceStartup;
        if (now <= scanUntil && now >= nextScan)
        {
            nextScan = now + 1.0f;
            ScanAndPatch("startup-repeat");
        }
    }

    private void LoadReplacements()
    {
        if (!Plugin.EnableTextureFix.Value)
        {
            Plugin.LogSource.LogInfo("Texture replacement disabled by config.");
            return;
        }

        var dir = Path.Combine(Paths.PluginPath, "DswfRusRuntimeFix", "Textures");
        if (!Directory.Exists(dir))
        {
            Plugin.LogSource.LogWarning("Texture replacement directory not found: " + dir);
            return;
        }

        foreach (var path in Directory.GetFiles(dir, "*.png", SearchOption.TopDirectoryOnly).OrderBy(p => p))
        {
            try
            {
                var file = Path.GetFileNameWithoutExtension(path);
                var m = ReplacementName.Match(file);
                if (!m.Success)
                {
                    Plugin.LogSource.LogWarning("Skipping texture with unexpected file name: " + Path.GetFileName(path));
                    continue;
                }

                var repl = new Replacement
                {
                    FileName = Path.GetFileName(path),
                    Stem = file,
                    Asset = m.Groups["asset"].Value,
                    ObjectType = m.Groups["type"].Value,
                    PathId = m.Groups["pathId"].Value,
                    ExportedName = m.Groups["name"].Value,
                };
                var decoded = SimplePng.Decode(File.ReadAllBytes(path));
                var tex = new Texture2D(decoded.Width, decoded.Height, TextureFormat.RGBA32, false);
                tex.name = repl.ExportedName;
                tex.wrapMode = TextureWrapMode.Clamp;
                tex.filterMode = FilterMode.Bilinear;
                var colors = new Il2CppStructArray<Color32>(decoded.Pixels.Length);
                for (var i = 0; i < decoded.Pixels.Length; i++) colors[i] = decoded.Pixels[i];
                tex.SetPixels32(colors);
                tex.Apply(false, false);
                repl.Texture = tex;
                repl.Width = tex.width;
                repl.Height = tex.height;
                try
                {
                    repl.Sprite = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0.5f), 100f);
                    repl.Sprite.name = repl.ExportedName;
                }
                catch (Exception ex)
                {
                    Plugin.LogSource.LogWarning($"Could not pre-create sprite for {repl.FileName}: {ex.Message}");
                }
                byStem[repl.Stem] = repl;
                byName[repl.ExportedName] = repl;
                byName[$"{repl.ObjectType}:{repl.PathId}"] = repl;
                Plugin.LogSource.LogInfo($"Loaded replacement {repl.FileName}: type={repl.ObjectType}, pathId={repl.PathId}, name={repl.ExportedName}, size={tex.width}x{tex.height}");
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogError("Failed loading replacement PNG " + path + ": " + ex);
            }
        }

        LoadAliases(dir);
        Plugin.LogSource.LogInfo($"Texture replacements loaded: {byStem.Count}");
    }

    private void LoadAliases(string textureDir)
    {
        var aliasPath = Path.Combine(textureDir, "TextureAliases.tsv");
        if (!File.Exists(aliasPath))
        {
            Plugin.LogSource.LogInfo("Texture alias manifest not found: " + aliasPath);
            return;
        }

        var count = 0;
        foreach (var rawLine in File.ReadAllLines(aliasPath))
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith("#", StringComparison.Ordinal)) continue;
            var parts = line.Split('\t');
            if (parts.Length < 2 || parts[0] == "runtime_name") continue;
            var runtimeName = parts[0].Trim();
            var replacementStem = Path.GetFileNameWithoutExtension(parts[1].Trim());
            if (runtimeName.Length == 0 || replacementStem.Length == 0) continue;
            if (!byStem.TryGetValue(replacementStem, out var replacement))
            {
                Plugin.LogSource.LogWarning($"Texture alias skipped; replacement not loaded: runtime='{runtimeName}', replacement='{replacementStem}'");
                continue;
            }
            byName[runtimeName] = replacement;
            count++;
            Plugin.LogSource.LogInfo($"Texture alias registered: runtime='{runtimeName}' => replacement='{replacement.FileName}'");
        }
        Plugin.LogSource.LogInfo("Texture aliases registered: " + count);
    }

    private void TrySetupFont()
    {
        if (!Plugin.EnableFontFix.Value || fontAttempted) return;
        fontAttempted = true;
        var fontPath = Path.Combine(Paths.PluginPath, "DswfRusRuntimeFix", "Fonts", Plugin.FontFileName.Value);
        if (!File.Exists(fontPath))
        {
            Plugin.LogSource.LogWarning("Font file not found; font fix skipped: " + fontPath);
            return;
        }

        try
        {
            var registered = TryRegisterPrivateFont(fontPath);
            Plugin.LogSource.LogInfo($"Private font registration result for {fontPath}: {registered}");

            try
            {
                runtimeTmpFont = TMP_FontAsset.CreateFontAsset(fontPath, "Nyasha Sans", 90);
                if (runtimeTmpFont != null)
                {
                    runtimeTmpFont.name = "Nyasha Sans Runtime TMP";
                    var addedFromFile = runtimeTmpFont.TryAddCharacters("ЖёЯф", false);
                    var tmpGlyphsFromFile = runtimeTmpFont.HasCharacters("ЖёЯф");
                    Plugin.LogSource.LogInfo($"TMP font asset created directly from TTF. TryAddCharacters={addedFromFile}, HasCharacters ЖёЯф={tmpGlyphsFromFile}");
                    AddTmpFallback(runtimeTmpFont);
                    return;
                }
                Plugin.LogSource.LogWarning("TMP_FontAsset.CreateFontAsset(string) returned null.");
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogWarning("TMP_FontAsset.CreateFontAsset(string) failed: " + ex);
            }

            try
            {
                runtimeUnityFont = Font.CreateDynamicFontFromOSFont("Nyasha Sans", 32);
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogWarning("Font.CreateDynamicFontFromOSFont failed: " + ex);
            }

            if (runtimeUnityFont == null)
            {
                Plugin.LogSource.LogWarning("Unity dynamic font creation returned null for 'Nyasha Sans'.");
                return;
            }
            runtimeUnityFont.name = "Nyasha Sans Runtime";
            var unityGlyphs = "ЖёЯф".All(c => runtimeUnityFont.HasCharacter(c));
            Plugin.LogSource.LogInfo("Unity dynamic font created. Cyrillic glyph check ЖёЯф=" + unityGlyphs);

            runtimeTmpFont = TMP_FontAsset.CreateFontAsset(runtimeUnityFont);
            if (runtimeTmpFont == null)
            {
                Plugin.LogSource.LogWarning("TMP_FontAsset.CreateFontAsset returned null.");
                return;
            }
            runtimeTmpFont.name = "Nyasha Sans Runtime TMP";
            var added = runtimeTmpFont.TryAddCharacters("ЖёЯф", false);
            var tmpGlyphs = runtimeTmpFont.HasCharacters("ЖёЯф");
            Plugin.LogSource.LogInfo($"TMP font asset created. TryAddCharacters={added}, HasCharacters ЖёЯф={tmpGlyphs}");

            AddTmpFallback(runtimeTmpFont);
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogError("Font setup failed: " + ex);
        }
    }

    private static void AddTmpFallback(TMP_FontAsset fontAsset)
    {
        var settings = TMP_Settings.instance;
        if (settings == null)
        {
            Plugin.LogSource.LogWarning("TMP_Settings.instance is null; cannot update global fallback list.");
            return;
        }
        var list = TMP_Settings.fallbackFontAssets;
        if (list == null)
        {
            list = new Il2CppSystem.Collections.Generic.List<TMP_FontAsset>();
            TMP_Settings.fallbackFontAssets = list;
        }
        if (!list.Contains(fontAsset)) list.Add(fontAsset);
        Plugin.LogSource.LogInfo("Added runtime TMP font to TMP_Settings.fallbackFontAssets. Count=" + list.Count);
    }

    private static bool TryRegisterPrivateFont(string path)
    {
        try
        {
            if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                Plugin.LogSource.LogInfo("Process is not reported as Windows; skipping AddFontResourceExW.");
                return false;
            }
            return AddFontResourceExW(path, 0x10, IntPtr.Zero) > 0;
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("AddFontResourceExW failed: " + ex.Message);
            return false;
        }
    }

    [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern int AddFontResourceExW(string lpszFilename, uint fl, IntPtr pdv);

    private void ScanAndPatch(string reason)
    {
        scanCount++;
        int tmp = 0, images = 0, raw = 0, sprites = 0, renderers = 0;
        if (runtimeTmpFont != null) tmp = PatchTmpTexts();
        if (Plugin.EnableTextureFix.Value)
        {
            images = PatchImages();
            raw = PatchRawImages();
            sprites = PatchSpriteRenderers();
            renderers = PatchRenderers();
        }
        if (Plugin.DumpVisibleTextureNames.Value) DumpVisibleTextureNames(reason);
        Plugin.LogSource.LogInfo($"Scan {scanCount} ({reason}) complete. TMP patched={tmp}, Images={images}, RawImages={raw}, SpriteRenderers={sprites}, Renderers={renderers}");
    }

    private int PatchTmpTexts()
    {
        int changed = 0;
        var texts = Resources.FindObjectsOfTypeAll<TMP_Text>();
        foreach (var text in texts)
        {
            if (text == null) continue;
            try
            {
                var id = text.GetInstanceID();
                if (!patchedTmpTexts.Add(id) && !Plugin.OverrideTmpFonts.Value) continue;
                if (text.font != null && text.font.fallbackFontAssetTable != null && !text.font.fallbackFontAssetTable.Contains(runtimeTmpFont))
                {
                    text.font.fallbackFontAssetTable.Add(runtimeTmpFont);
                    changed++;
                }
                if (Plugin.OverrideTmpFonts.Value)
                {
                    text.font = runtimeTmpFont;
                    changed++;
                }
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogWarning("TMP patch failed on " + SafeObjectPath(text.gameObject) + ": " + ex.Message);
            }
        }
        return changed;
    }

    private int PatchImages()
    {
        int changed = 0;
        foreach (var image in Resources.FindObjectsOfTypeAll<Image>())
        {
            if (image == null || image.sprite == null) continue;
            try
            {
                var id = image.GetInstanceID();
                if (patchedImages.Contains(id) || failedImages.Contains(id)) continue;
                var oldSpriteName = image.sprite.name;
                var repl = FindReplacement(image.sprite.name, image.sprite.texture != null ? image.sprite.texture.name : null);
                if (repl == null) continue;
                var sprite = CreateSpriteLike(repl, image.sprite);
                image.sprite = sprite;
                patchedImages.Add(id);
                changed++;
                Plugin.LogSource.LogInfo($"Texture replacement applied: UI.Image path='{SafeObjectPath(image.gameObject)}' oldSprite='{oldSpriteName}' replacement='{repl.FileName}'");
            }
            catch (Exception ex)
            {
                try { failedImages.Add(image.GetInstanceID()); } catch { }
                Plugin.LogSource.LogWarning($"UI.Image replacement failed on '{SafeObjectPath(image.gameObject)}': {ex}");
            }
        }
        return changed;
    }

    private int PatchRawImages()
    {
        int changed = 0;
        foreach (var rawImage in Resources.FindObjectsOfTypeAll<RawImage>())
        {
            if (rawImage == null || rawImage.texture == null) continue;
            try
            {
                var id = rawImage.GetInstanceID();
                if (patchedRawImages.Contains(id)) continue;
                var repl = FindReplacement(rawImage.texture.name, null);
                if (repl == null) continue;
                rawImage.texture = repl.Texture;
                patchedRawImages.Add(id);
                changed++;
                Plugin.LogSource.LogInfo($"Texture replacement applied: RawImage path='{SafeObjectPath(rawImage.gameObject)}' texture='{rawImage.texture.name}' replacement='{repl.FileName}'");
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogWarning("RawImage replacement failed: " + ex);
            }
        }
        return changed;
    }

    private int PatchSpriteRenderers()
    {
        int changed = 0;
        foreach (var sr in Resources.FindObjectsOfTypeAll<SpriteRenderer>())
        {
            if (sr == null || sr.sprite == null) continue;
            try
            {
                var id = sr.GetInstanceID();
                if (patchedSpriteRenderers.Contains(id) || failedSpriteRenderers.Contains(id)) continue;
                var repl = FindReplacement(sr.sprite.name, sr.sprite.texture != null ? sr.sprite.texture.name : null);
                if (repl == null) continue;
                sr.sprite = CreateSpriteLike(repl, sr.sprite);
                patchedSpriteRenderers.Add(id);
                changed++;
                Plugin.LogSource.LogInfo($"Texture replacement applied: SpriteRenderer path='{SafeObjectPath(sr.gameObject)}' replacement='{repl.FileName}'");
            }
            catch (Exception ex)
            {
                try { failedSpriteRenderers.Add(sr.GetInstanceID()); } catch { }
                Plugin.LogSource.LogWarning($"SpriteRenderer replacement failed on '{SafeObjectPath(sr.gameObject)}': {ex}");
            }
        }
        return changed;
    }

    private int PatchRenderers()
    {
        int changed = 0;
        foreach (var renderer in Resources.FindObjectsOfTypeAll<Renderer>())
        {
            if (renderer == null) continue;
            try
            {
                var id = renderer.GetInstanceID();
                if (patchedRenderers.Contains(id)) continue;
                var mat = renderer.material;
                if (mat == null) continue;
                foreach (var prop in new[] { "_MainTex", "_BaseMap", "_EmissionMap" })
                {
                    if (!mat.HasProperty(prop)) continue;
                    var tex = mat.GetTexture(prop);
                    if (tex == null) continue;
                    var repl = FindReplacement(tex.name, null);
                    if (repl == null) continue;
                    mat.SetTexture(prop, repl.Texture);
                    patchedRenderers.Add(id);
                    changed++;
                    Plugin.LogSource.LogInfo($"Texture replacement applied: Renderer path='{SafeObjectPath(renderer.gameObject)}' property='{prop}' texture='{tex.name}' replacement='{repl.FileName}'");
                    break;
                }
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogWarning("Renderer replacement failed: " + ex);
            }
        }
        return changed;
    }

    [HideFromIl2Cpp]
    private Replacement FindReplacement(string primary, string secondary)
    {
        foreach (var key in new[] { primary, secondary })
        {
            if (string.IsNullOrWhiteSpace(key)) continue;
            if (byName.TryGetValue(key, out var replacement)) return replacement;
            var normalized = key.Trim();
            if (byName.TryGetValue(normalized, out replacement)) return replacement;
        }
        return null;
    }

    private static Sprite CreateSpriteLike(Replacement repl, Sprite original)
    {
        if (!ReferenceEquals(repl.Sprite, null)) return repl.Sprite;

        var rect = new Rect(0, 0, repl.Width, repl.Height);
        var normalizedPivot = new Vector2(0.5f, 0.5f);
        var pixelsPerUnit = 100f;

        try
        {
            if (original != null)
            {
                var originalRect = original.rect;
                var pivot = original.pivot;
                if (originalRect.width > 0 && originalRect.height > 0)
                {
                    normalizedPivot = new Vector2(pivot.x / originalRect.width, pivot.y / originalRect.height);
                }
                pixelsPerUnit = original.pixelsPerUnit > 0 ? original.pixelsPerUnit : pixelsPerUnit;
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Could not read original sprite layout; using centered fallback sprite layout: " + ex.Message);
        }

        var sprite = Sprite.Create(repl.Texture, rect, normalizedPivot, pixelsPerUnit);
        sprite.name = repl.ExportedName;
        return sprite;
    }

    private void DumpVisibleTextureNames(string reason)
    {
        try
        {
            if (string.IsNullOrEmpty(reportPath)) return;
            var first = !File.Exists(reportPath);
            using var writer = new StreamWriter(reportPath, append: true);
            if (first) writer.WriteLine("scan\treason\tkind\tpath\tsprite\ttexture\twidth\theight");
            foreach (var image in Resources.FindObjectsOfTypeAll<Image>())
            {
                if (image == null || image.sprite == null) continue;
                var tex = image.sprite.texture;
                writer.WriteLine($"{scanCount}\t{reason}\tImage\t{Tsv(SafeObjectPath(image.gameObject))}\t{Tsv(image.sprite.name)}\t{Tsv(tex != null ? tex.name : "")}\t{(tex != null ? tex.width : 0)}\t{(tex != null ? tex.height : 0)}");
            }
            foreach (var sr in Resources.FindObjectsOfTypeAll<SpriteRenderer>())
            {
                if (sr == null || sr.sprite == null) continue;
                var tex = sr.sprite.texture;
                writer.WriteLine($"{scanCount}\t{reason}\tSpriteRenderer\t{Tsv(SafeObjectPath(sr.gameObject))}\t{Tsv(sr.sprite.name)}\t{Tsv(tex != null ? tex.name : "")}\t{(tex != null ? tex.width : 0)}\t{(tex != null ? tex.height : 0)}");
            }
            foreach (var raw in Resources.FindObjectsOfTypeAll<RawImage>())
            {
                if (raw == null || raw.texture == null) continue;
                writer.WriteLine($"{scanCount}\t{reason}\tRawImage\t{Tsv(SafeObjectPath(raw.gameObject))}\t\t{Tsv(raw.texture.name)}\t{raw.texture.width}\t{raw.texture.height}");
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Visible texture dump failed: " + ex.Message);
        }
    }

    private static string BuildDebugReportPath()
    {
        try
        {
            var projectRoot = Directory.GetParent(Paths.GameRootPath)?.FullName;
            if (string.IsNullOrEmpty(projectRoot)) return null;
            var dir = Path.Combine(projectRoot, "debug_reports");
            Directory.CreateDirectory(dir);
            return Path.Combine(dir, "runtime_visible_texture_names.tsv");
        }
        catch { return null; }
    }

    private static string SafeObjectPath(GameObject go)
    {
        if (go == null) return "";
        try
        {
            var parts = new List<string>();
            var t = go.transform;
            while (t != null)
            {
                parts.Add(t.gameObject.name);
                t = t.parent;
            }
            parts.Reverse();
            return string.Join("/", parts);
        }
        catch { return go.name; }
    }

    private static string Tsv(string value) => (value ?? "").Replace("\t", " ").Replace("\r", " ").Replace("\n", " ");

    private sealed class Replacement
    {
        public string FileName;
        public string Stem;
        public string Asset;
        public string ObjectType;
        public string PathId;
        public string ExportedName;
        public Texture2D Texture;
        public Sprite Sprite;
        public int Width;
        public int Height;
    }

    private sealed class DecodedPng
    {
        public int Width;
        public int Height;
        public Color32[] Pixels;
    }

    private static class SimplePng
    {
        private static readonly byte[] Signature = { 137, 80, 78, 71, 13, 10, 26, 10 };

        public static DecodedPng Decode(byte[] png)
        {
            for (var i = 0; i < Signature.Length; i++)
                if (png[i] != Signature[i]) throw new InvalidDataException("Invalid PNG signature.");

            int pos = 8, width = 0, height = 0, bitDepth = 0, colorType = 0;
            var idat = new MemoryStream();
            while (pos + 8 <= png.Length)
            {
                var length = ReadInt32(png, pos); pos += 4;
                var type = System.Text.Encoding.ASCII.GetString(png, pos, 4); pos += 4;
                if (type == "IHDR")
                {
                    width = ReadInt32(png, pos);
                    height = ReadInt32(png, pos + 4);
                    bitDepth = png[pos + 8];
                    colorType = png[pos + 9];
                }
                else if (type == "IDAT")
                {
                    idat.Write(png, pos, length);
                }
                else if (type == "IEND")
                {
                    break;
                }
                pos += length + 4; // data + CRC
            }

            if (width <= 0 || height <= 0) throw new InvalidDataException("PNG missing IHDR.");
            if (bitDepth != 8) throw new NotSupportedException("Only 8-bit PNGs are supported.");
            var bpp = colorType switch
            {
                0 => 1,
                2 => 3,
                4 => 2,
                6 => 4,
                _ => throw new NotSupportedException("Unsupported PNG color type: " + colorType),
            };

            idat.Position = 0;
            idat.ReadByte(); // zlib CMF
            idat.ReadByte(); // zlib FLG
            byte[] inflated;
            using (var deflate = new DeflateStream(idat, CompressionMode.Decompress))
            using (var raw = new MemoryStream())
            {
                deflate.CopyTo(raw);
                inflated = raw.ToArray();
            }

            var stride = width * bpp;
            var recon = new byte[height * stride];
            var src = 0;
            for (var y = 0; y < height; y++)
            {
                var filter = inflated[src++];
                var row = y * stride;
                var prev = row - stride;
                for (var x = 0; x < stride; x++)
                {
                    var value = inflated[src++];
                    var left = x >= bpp ? recon[row + x - bpp] : 0;
                    var up = y > 0 ? recon[prev + x] : 0;
                    var upLeft = y > 0 && x >= bpp ? recon[prev + x - bpp] : 0;
                    recon[row + x] = filter switch
                    {
                        0 => value,
                        1 => unchecked((byte)(value + left)),
                        2 => unchecked((byte)(value + up)),
                        3 => unchecked((byte)(value + ((left + up) >> 1))),
                        4 => unchecked((byte)(value + Paeth(left, up, upLeft))),
                        _ => throw new InvalidDataException("Unsupported PNG filter: " + filter),
                    };
                }
            }

            var pixels = new Color32[width * height];
            for (var y = 0; y < height; y++)
            {
                var row = y * stride;
                for (var x = 0; x < width; x++)
                {
                    var p = row + x * bpp;
                    Color32 c = colorType switch
                    {
                        0 => new Color32(recon[p], recon[p], recon[p], 255),
                        2 => new Color32(recon[p], recon[p + 1], recon[p + 2], 255),
                        4 => new Color32(recon[p], recon[p], recon[p], recon[p + 1]),
                        6 => new Color32(recon[p], recon[p + 1], recon[p + 2], recon[p + 3]),
                        _ => new Color32(255, 0, 255, 255),
                    };
                    pixels[(height - 1 - y) * width + x] = c;
                }
            }
            return new DecodedPng { Width = width, Height = height, Pixels = pixels };
        }

        private static int ReadInt32(byte[] data, int offset) =>
            (data[offset] << 24) | (data[offset + 1] << 16) | (data[offset + 2] << 8) | data[offset + 3];

        private static int Paeth(int a, int b, int c)
        {
            var p = a + b - c;
            var pa = Math.Abs(p - a);
            var pb = Math.Abs(p - b);
            var pc = Math.Abs(p - c);
            if (pa <= pb && pa <= pc) return a;
            return pb <= pc ? b : c;
        }
    }
}
