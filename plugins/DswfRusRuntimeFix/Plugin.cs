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
using UnityEngine.SceneManagement;
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
    internal static ConfigEntry<bool> PatchMainMenuTitle;
    internal static ConfigEntry<bool> PatchTitleSplash;
    internal static ConfigEntry<bool> PatchSettingsLogo;
    internal static ConfigEntry<bool> PatchJournalIcon;
    internal static ConfigEntry<bool> PatchHowToPlay;
    internal static ConfigEntry<bool> PatchGameplay3DTextures;

    public override void Load()
    {
        LogSource = Log;
        EnableFontFix = Config.Bind("Font", "EnableFontFix", false, "Register a local TTF and create a runtime TMP fallback font asset.");
        OverrideTmpFonts = Config.Bind("Font", "OverrideTmpFonts", false, "Assign the runtime TMP font directly to TMP_Text objects. Fallback mode is safer and is tried first.");
        FontFileName = Config.Bind("Font", "FontFileName", "nyashasans.ttf", "TTF file under BepInEx/plugins/DswfRusRuntimeFix/Fonts.");
        EnableTextureFix = Config.Bind("Textures", "EnableTextureFix", true, "Replace visible runtime textures/sprites from the Textures folder.");
        PatchMainMenuTitle = Config.Bind("Textures", "PatchMainMenuTitle", true, "Patch only the main menu title UI Image.");
        PatchTitleSplash = Config.Bind("Textures", "PatchTitleSplash", false, "Patch the startup title splash logo images. Disabled until visual QA confirms it is safe.");
        PatchSettingsLogo = Config.Bind("Textures", "PatchSettingsLogo", false, "Patch the settings menu logo. Disabled for isolation testing.");
        PatchJournalIcon = Config.Bind("Textures", "PatchJournalIcon", false, "Patch the gameplay journal icon. Disabled for isolation testing.");
        PatchHowToPlay = Config.Bind("Textures", "PatchHowToPlay", false, "Patch how-to-play/menu icon textures. Disabled for isolation testing.");
        PatchGameplay3DTextures = Config.Bind("Textures", "PatchGameplay3DTextures", false, "Patch RawImage, SpriteRenderer, and Renderer material textures.");
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
    private readonly HashSet<string> replacementNames = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<int> patchedImages = new();
    private readonly HashSet<int> failedImages = new();
    private readonly HashSet<int> patchedRawImages = new();
    private readonly HashSet<int> patchedSpriteRenderers = new();
    private readonly HashSet<int> failedSpriteRenderers = new();
    private readonly HashSet<int> patchedRenderers = new();
    private readonly HashSet<int> patchedTmpTexts = new();
    private readonly Dictionary<int, RawImage> imageOverlays = new();
    private float scanUntil;
    private float nextScan;
    private int scanCount;
    private TMP_FontAsset runtimeTmpFont;
    private Font runtimeUnityFont;
    private bool fontAttempted;
    private string reportPath;
    private string componentReportPath;
    private string lastSceneName;
    private readonly List<Sprite> createdReplacementSprites = new();

    public RuntimeFixBehaviour(IntPtr ptr) : base(ptr) { }

    private void Start()
    {
        scanUntil = Time.realtimeSinceStartup + Math.Max(3f, Plugin.StartupScanSeconds.Value);
        nextScan = 0f;
        lastSceneName = SafeSceneName();
        reportPath = BuildDebugReportPath("runtime_visible_texture_targets.tsv");
        componentReportPath = BuildDebugReportPath("runtime_problem_texture_components.tsv");
        Plugin.LogSource.LogInfo("RuntimeFixBehaviour started. scene=" + lastSceneName);
        LoadReplacements();
        TrySetupFont();
        ScanAndPatch("startup");
    }

    private void Update()
    {
        var now = Time.realtimeSinceStartup;
        var sceneName = SafeSceneName();
        if (!string.Equals(lastSceneName, sceneName, StringComparison.Ordinal))
        {
            lastSceneName = sceneName;
            scanUntil = now + Math.Max(3f, Plugin.StartupScanSeconds.Value);
            nextScan = 0f;
            patchedImages.Clear();
            failedImages.Clear();
            imageOverlays.Clear();
            patchedRawImages.Clear();
            patchedSpriteRenderers.Clear();
            failedSpriteRenderers.Clear();
            patchedRenderers.Clear();
            patchedTmpTexts.Clear();
            Plugin.LogSource.LogInfo("Scene changed; texture/font scan window reset. scene=" + sceneName);
        }
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
                repl.AlphaMin = decoded.AlphaMin;
                repl.AlphaMax = decoded.AlphaMax;
                var tex = new Texture2D(decoded.Width, decoded.Height, TextureFormat.RGBA32, false);
                tex.name = repl.Stem;
                tex.wrapMode = TextureWrapMode.Clamp;
                tex.filterMode = FilterMode.Bilinear;
                var colors = new Il2CppStructArray<Color32>(decoded.Pixels.Length);
                for (var i = 0; i < decoded.Pixels.Length; i++) colors[i] = decoded.Pixels[i];
                tex.SetPixels32(colors);
                tex.Apply(false, false);
                repl.Texture = tex;
                repl.Width = tex.width;
                repl.Height = tex.height;
                byStem[repl.Stem] = repl;
                byName[repl.Stem] = repl;
                byName[repl.ExportedName] = repl;
                byName[$"{repl.ObjectType}:{repl.PathId}"] = repl;
                replacementNames.Add(repl.Stem);
                replacementNames.Add(repl.ExportedName);
                replacementNames.Add(repl.Texture.name);
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
        if (Plugin.DumpVisibleTextureNames.Value) DumpProblemComponents(reason);
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
                if (failedImages.Contains(id)) continue;
                if (imageOverlays.ContainsKey(id)) continue;
                var path = SafeObjectPath(image.gameObject);
                var spriteTextureName = image.sprite.texture != null ? image.sprite.texture.name : null;
                if (patchedImages.Contains(id) && IsReplacementName(image.sprite.name, spriteTextureName)) continue;
                var oldSpriteName = image.sprite.name;
                var decision = GetImageDecision(path, image.sprite.name, spriteTextureName);
                var repl = decision.Replacement;
                if (repl == null) continue;
                if (!string.Equals(decision.SkipReason, "apply", StringComparison.Ordinal)) continue;
                Sprite sprite;
                try
                {
                    sprite = CreateSpriteLike(repl, image.sprite);
                }
                catch (Exception ex) when (IsMainMenuTitlePath(path))
                {
                    if (ApplyMainMenuTitleRawImageOverlay(image, repl, path, ex.Message))
                    {
                        patchedImages.Add(id);
                        changed++;
                        continue;
                    }
                    throw;
                }
                if (IsMainMenuTitlePath(path)) LogMainMenuTitleDetails(path, image, repl, sprite, "before-apply");
                image.sprite = sprite;
                patchedImages.Add(id);
                changed++;
                Plugin.LogSource.LogInfo($"Texture replacement applied: UI.Image path='{path}' oldSprite='{oldSpriteName}' replacement='{repl.FileName}' group='{decision.Group}'");
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
                if (patchedRawImages.Contains(id) && IsReplacementName(rawImage.texture.name, null)) continue;
                if (!Plugin.PatchGameplay3DTextures.Value) continue;
                var repl = FindReplacement("Texture2D", rawImage.texture.name, null);
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
                var spriteTextureName = sr.sprite.texture != null ? sr.sprite.texture.name : null;
                if (failedSpriteRenderers.Contains(id)) continue;
                if (patchedSpriteRenderers.Contains(id) && IsReplacementName(sr.sprite.name, spriteTextureName)) continue;
                if (!Plugin.PatchGameplay3DTextures.Value) continue;
                var repl = FindReplacement("Sprite", sr.sprite.name, spriteTextureName);
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
                var mat = renderer.material;
                if (mat == null) continue;
                foreach (var prop in new[] { "_MainTex", "_BaseMap", "_EmissionMap" })
                {
                    if (!mat.HasProperty(prop)) continue;
                    var tex = mat.GetTexture(prop);
                    if (tex == null) continue;
                    if (patchedRenderers.Contains(id) && IsReplacementName(tex.name, null)) continue;
                    if (!Plugin.PatchGameplay3DTextures.Value) continue;
                    var repl = FindReplacement("Texture2D", tex.name, null);
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
    private Replacement FindReplacement(string objectType, string primary, string secondary)
    {
        foreach (var key in new[] { primary, secondary })
        {
            if (string.IsNullOrWhiteSpace(key)) continue;
            if (byName.TryGetValue(key, out var replacement) && ReplacementTypeMatches(replacement, objectType)) return replacement;
            var normalized = key.Trim();
            if (byName.TryGetValue(normalized, out replacement) && ReplacementTypeMatches(replacement, objectType)) return replacement;
        }
        return null;
    }

    private static bool ReplacementTypeMatches(Replacement replacement, string objectType) =>
        replacement != null && (string.IsNullOrEmpty(objectType) || string.Equals(replacement.ObjectType, objectType, StringComparison.OrdinalIgnoreCase));

    private bool IsReplacementName(string primary, string secondary)
    {
        foreach (var key in new[] { primary, secondary })
        {
            if (!string.IsNullOrWhiteSpace(key) && replacementNames.Contains(key.Trim())) return true;
        }
        return false;
    }

    [HideFromIl2Cpp]
    private ImageDecision GetImageDecision(string path, string spriteName, string textureName)
    {
        var replacement = FindReplacement("Sprite", spriteName, textureName);
        var group = ClassifyImageTarget(path);
        if (replacement == null) return new ImageDecision(null, group, "no_sprite_replacement_candidate");
        if (!IsImageGroupEnabled(group)) return new ImageDecision(replacement, group, $"disabled_{group}");
        return new ImageDecision(replacement, group, "apply");
    }

    private static string ClassifyImageTarget(string path)
    {
        if (IsMainMenuTitlePath(path)) return "main_menu_title";
        if (path == "TITLE/UI/Canvas/text" || path == "TITLE/UI/Canvas/textred" || path == "TITLE/UI/Canvas/textblue") return "title_splash";
        if (path == "GameController/SETTINGS_CANVAS/SETTINGS_MENU/logo") return "settings_logo";
        if (path.Contains("HowToPlayExc", StringComparison.Ordinal)) return "how_to_play";
        if (path.Contains("JournalHolder/JournalButton", StringComparison.Ordinal) || path.Contains("JournalButtonOff", StringComparison.Ordinal)) return "journal_icon";
        return "unknown_image";
    }

    private static bool IsImageGroupEnabled(string group) => group switch
    {
        "main_menu_title" => Plugin.PatchMainMenuTitle.Value,
        "title_splash" => Plugin.PatchTitleSplash.Value,
        "settings_logo" => Plugin.PatchSettingsLogo.Value,
        "journal_icon" => Plugin.PatchJournalIcon.Value,
        "how_to_play" => Plugin.PatchHowToPlay.Value,
        _ => false,
    };

    private static bool IsMainMenuTitlePath(string path) => path == "MENU/UI/Canvas/title_main_image";

    private static bool IsProblemPath(string path)
    {
        if (string.IsNullOrEmpty(path)) return false;
        return path == "MENU/UI/Canvas/title_main_image"
            || path.StartsWith("MENU/UI/Canvas/title_main_image/", StringComparison.Ordinal)
            || path.StartsWith("TITLE/UI/Canvas", StringComparison.Ordinal)
            || path.Contains("JournalHolder/JournalButton", StringComparison.Ordinal)
            || path.Contains("JournalButtonOff", StringComparison.Ordinal)
            || path.Contains("HowToPlayExc", StringComparison.Ordinal);
    }

    [HideFromIl2Cpp]
    private void LogMainMenuTitleDetails(string path, Image image, Replacement repl, Sprite created, string phase)
    {
        try
        {
            var original = image.sprite;
            var originalRect = original != null ? original.rect : Rect.zero;
            var originalPivot = original != null ? original.pivot : Vector2.zero;
            var originalTexture = original != null ? original.texture : null;
            var createdRect = created != null ? created.rect : Rect.zero;
            var createdPivot = created != null ? created.pivot : Vector2.zero;
            var size = SafeRectSize(image.rectTransform);
            Plugin.LogSource.LogInfo(
                "MainMenuTitle diagnostic " +
                $"phase='{phase}', path='{path}', active={image.gameObject.activeInHierarchy}, rectTransform={size.x.ToString(CultureInfo.InvariantCulture)}x{size.y.ToString(CultureInfo.InvariantCulture)}, " +
                $"sprite='{(original != null ? original.name : "")}', spriteTexture='{(originalTexture != null ? originalTexture.name : "")}', " +
                $"spriteRect={originalRect.width.ToString(CultureInfo.InvariantCulture)}x{originalRect.height.ToString(CultureInfo.InvariantCulture)}, " +
                $"spritePivot={originalPivot.x.ToString(CultureInfo.InvariantCulture)},{originalPivot.y.ToString(CultureInfo.InvariantCulture)}, " +
                $"spriteTextureSize={(originalTexture != null ? originalTexture.width : 0)}x{(originalTexture != null ? originalTexture.height : 0)}, " +
                $"replacement='{repl.FileName}', replacementType='{repl.ObjectType}', replacementPng={repl.Width}x{repl.Height}, replacementAlpha={repl.AlphaMin}-{repl.AlphaMax}, " +
                $"createdSpriteRect={createdRect.width.ToString(CultureInfo.InvariantCulture)}x{createdRect.height.ToString(CultureInfo.InvariantCulture)}, " +
                $"createdSpritePivot={createdPivot.x.ToString(CultureInfo.InvariantCulture)},{createdPivot.y.ToString(CultureInfo.InvariantCulture)}");
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("MainMenuTitle diagnostic failed: " + ex.Message);
        }
    }

    [HideFromIl2Cpp]
    private bool ApplyMainMenuTitleRawImageOverlay(Image image, Replacement repl, string path, string spriteFailure)
    {
        try
        {
            var id = image.GetInstanceID();
            if (imageOverlays.ContainsKey(id)) return true;

            var overlayObject = new GameObject("DswfRusRuntimeFix_MainTitleOverlay");
            overlayObject.transform.SetParent(image.transform, false);
            overlayObject.layer = image.gameObject.layer;

            var rect = overlayObject.AddComponent<RectTransform>();
            rect.anchorMin = Vector2.zero;
            rect.anchorMax = Vector2.one;
            rect.offsetMin = Vector2.zero;
            rect.offsetMax = Vector2.zero;
            rect.pivot = new Vector2(0.5f, 0.5f);
            rect.localScale = Vector3.one;

            var raw = overlayObject.AddComponent<RawImage>();
            raw.texture = repl.Texture;
            raw.color = Color.white;
            raw.raycastTarget = false;
            try
            {
                var fitter = overlayObject.AddComponent<AspectRatioFitter>();
                fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
                fitter.aspectRatio = repl.Width > 0 && repl.Height > 0 ? (float)repl.Width / repl.Height : 1f;
            }
            catch (Exception ex)
            {
                Plugin.LogSource.LogWarning("Main menu title overlay AspectRatioFitter failed: " + ex.Message);
            }

            image.enabled = false;
            imageOverlays[id] = raw;
            Plugin.LogSource.LogWarning($"Sprite replacement unavailable for main menu title ({spriteFailure}); using RawImage overlay fallback.");
            Plugin.LogSource.LogInfo($"Texture replacement applied: UI.Image overlay path='{path}' overlayPath='{SafeObjectPath(overlayObject)}' oldSprite='{image.sprite.name}' replacement='{repl.FileName}' group='main_menu_title_overlay' texture='{(raw.texture != null ? raw.texture.name : "")}' textureSize={repl.Width}x{repl.Height}");
            return true;
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning($"Main menu title RawImage overlay failed on '{path}': {ex}");
            return false;
        }
    }

    [HideFromIl2Cpp]
    private Sprite CreateSpriteLike(Replacement repl, Sprite original)
    {
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

        var sprite = TryCreateSprite(repl, rect, normalizedPivot, pixelsPerUnit);
        if (sprite == null)
        {
            throw new InvalidOperationException($"Sprite.Create returned null for {repl.FileName} ({repl.Width}x{repl.Height}).");
        }
        sprite.name = repl.Stem;
        createdReplacementSprites.Add(sprite);
        return sprite;
    }

    [HideFromIl2Cpp]
    private static Sprite TryCreateSprite(Replacement repl, Rect rect, Vector2 normalizedPivot, float pixelsPerUnit)
    {
        try
        {
            var sprite = Sprite.Create(repl.Texture, rect, normalizedPivot, pixelsPerUnit, 0, SpriteMeshType.FullRect, Vector4.zero, false);
            if (sprite != null) return sprite;
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning($"Sprite.Create full overload failed for {repl.FileName}: {ex.Message}");
        }

        try
        {
            var sprite = Sprite.Create(repl.Texture, rect, normalizedPivot, pixelsPerUnit, 0, SpriteMeshType.FullRect);
            if (sprite != null) return sprite;
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning($"Sprite.Create mesh overload failed for {repl.FileName}: {ex.Message}");
        }

        try
        {
            var sprite = Sprite.Create(repl.Texture, rect, normalizedPivot, pixelsPerUnit);
            if (sprite != null) return sprite;
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning($"Sprite.Create ppu overload failed for {repl.FileName}: {ex.Message}");
        }

        try
        {
            var sprite = Sprite.Create(repl.Texture, rect, normalizedPivot);
            if (sprite != null) return sprite;
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning($"Sprite.Create minimal overload failed for {repl.FileName}: {ex.Message}");
        }

        return null;
    }

    private void DumpVisibleTextureNames(string reason)
    {
        try
        {
            if (string.IsNullOrEmpty(reportPath)) return;
            var first = !File.Exists(reportPath);
            using var writer = new StreamWriter(reportPath, append: true);
            if (first) writer.WriteLine("scan\treason\tscene\tobject_path\tcomponent_type\tactive_in_hierarchy\tenabled\trect_width\trect_height\tsprite_name\tsprite_texture_name\traw_image_texture_name\trenderer_material_texture_name\tmaterial_property\treplacement_candidate\treplacement_applied\tskip_reason");
            foreach (var image in Resources.FindObjectsOfTypeAll<Image>())
            {
                if (image == null || image.sprite == null) continue;
                var path = SafeObjectPath(image.gameObject);
                var tex = image.sprite.texture;
                var decision = GetImageDecision(path, image.sprite.name, tex != null ? tex.name : null);
                var size = SafeRectSize(image.rectTransform);
                var overlayApplied = imageOverlays.ContainsKey(image.GetInstanceID());
                var applied = overlayApplied || IsReplacementName(image.sprite.name, tex != null ? tex.name : null);
                var skipReason = overlayApplied ? "overlay_applied_raw_image" : (applied ? "already_replaced" : decision.SkipReason);
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(path)}\tImage\t{image.gameObject.activeInHierarchy}\t{image.enabled}\t{size.x.ToString(CultureInfo.InvariantCulture)}\t{size.y.ToString(CultureInfo.InvariantCulture)}\t{Tsv(image.sprite.name)}\t{Tsv(tex != null ? tex.name : "")}\t\t\t\t{Tsv(decision.Replacement != null ? decision.Replacement.FileName : "")}\t{applied}\t{Tsv(skipReason)}");
            }
            foreach (var sr in Resources.FindObjectsOfTypeAll<SpriteRenderer>())
            {
                if (sr == null || sr.sprite == null) continue;
                var tex = sr.sprite.texture;
                var repl = FindReplacement("Sprite", sr.sprite.name, tex != null ? tex.name : null);
                var applied = IsReplacementName(sr.sprite.name, tex != null ? tex.name : null);
                var skip = Plugin.PatchGameplay3DTextures.Value ? (repl != null ? "apply_if_seen" : "no_sprite_replacement_candidate") : "disabled_gameplay_3d_textures";
                var skipReason = applied ? "already_replaced" : skip;
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(SafeObjectPath(sr.gameObject))}\tSpriteRenderer\t{sr.gameObject.activeInHierarchy}\t{sr.enabled}\t0\t0\t{Tsv(sr.sprite.name)}\t{Tsv(tex != null ? tex.name : "")}\t\t\t\t{Tsv(repl != null ? repl.FileName : "")}\t{applied}\t{Tsv(skipReason)}");
            }
            foreach (var raw in Resources.FindObjectsOfTypeAll<RawImage>())
            {
                if (raw == null || raw.texture == null) continue;
                var repl = FindReplacement("Texture2D", raw.texture.name, null);
                var size = SafeRectSize(raw.rectTransform);
                var applied = IsReplacementName(raw.texture.name, null);
                var skip = Plugin.PatchGameplay3DTextures.Value ? (repl != null ? "apply_if_seen" : "no_texture2d_replacement_candidate") : "disabled_gameplay_3d_textures";
                var skipReason = applied ? "already_replaced" : skip;
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(SafeObjectPath(raw.gameObject))}\tRawImage\t{raw.gameObject.activeInHierarchy}\t{raw.enabled}\t{size.x.ToString(CultureInfo.InvariantCulture)}\t{size.y.ToString(CultureInfo.InvariantCulture)}\t\t\t{Tsv(raw.texture.name)}\t\t\t{Tsv(repl != null ? repl.FileName : "")}\t{applied}\t{Tsv(skipReason)}");
            }
            foreach (var renderer in Resources.FindObjectsOfTypeAll<Renderer>())
            {
                if (renderer == null) continue;
                Material mat = null;
                try { mat = renderer.material; } catch { }
                if (mat == null) continue;
                foreach (var prop in new[] { "_MainTex", "_BaseMap", "_EmissionMap" })
                {
                    if (!mat.HasProperty(prop)) continue;
                    var tex = mat.GetTexture(prop);
                    if (tex == null) continue;
                    var repl = FindReplacement("Texture2D", tex.name, null);
                    var applied = IsReplacementName(tex.name, null);
                    var skip = Plugin.PatchGameplay3DTextures.Value ? (repl != null ? "apply_if_seen" : "no_texture2d_replacement_candidate") : "disabled_gameplay_3d_textures";
                    var skipReason = applied ? "already_replaced" : skip;
                    writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(SafeObjectPath(renderer.gameObject))}\tRenderer\t{renderer.gameObject.activeInHierarchy}\t{renderer.enabled}\t0\t0\t\t\t\t{Tsv(tex.name)}\t{prop}\t{Tsv(repl != null ? repl.FileName : "")}\t{applied}\t{Tsv(skipReason)}");
                }
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Visible texture dump failed: " + ex.Message);
        }
    }

    private void DumpProblemComponents(string reason)
    {
        try
        {
            if (string.IsNullOrEmpty(componentReportPath)) return;
            var first = !File.Exists(componentReportPath);
            using var writer = new StreamWriter(componentReportPath, append: true);
            if (first) writer.WriteLine("scan\treason\tscene\tobject_path\tactive_in_hierarchy\tcomponent_type\tenabled\tdetails");

            foreach (var image in Resources.FindObjectsOfTypeAll<Image>())
            {
                if (image == null) continue;
                var path = SafeObjectPath(image.gameObject);
                if (!IsProblemPath(path)) continue;
                var tex = image.sprite != null ? image.sprite.texture : null;
                var size = SafeRectSize(image.rectTransform);
                var details = $"rect={size.x.ToString(CultureInfo.InvariantCulture)}x{size.y.ToString(CultureInfo.InvariantCulture)}; sprite={(image.sprite != null ? image.sprite.name : "")}; texture={(tex != null ? tex.name : "")}; group={ClassifyImageTarget(path)}";
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(path)}\t{image.gameObject.activeInHierarchy}\t{Tsv(image.GetIl2CppType().FullName)}\t{image.enabled}\t{Tsv(details)}");
            }
            foreach (var raw in Resources.FindObjectsOfTypeAll<RawImage>())
            {
                if (raw == null) continue;
                var path = SafeObjectPath(raw.gameObject);
                if (!IsProblemPath(path)) continue;
                var size = SafeRectSize(raw.rectTransform);
                var details = $"rect={size.x.ToString(CultureInfo.InvariantCulture)}x{size.y.ToString(CultureInfo.InvariantCulture)}; texture={(raw.texture != null ? raw.texture.name : "")}";
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(path)}\t{raw.gameObject.activeInHierarchy}\t{Tsv(raw.GetIl2CppType().FullName)}\t{raw.enabled}\t{Tsv(details)}");
            }
            foreach (var sr in Resources.FindObjectsOfTypeAll<SpriteRenderer>())
            {
                if (sr == null) continue;
                var path = SafeObjectPath(sr.gameObject);
                if (!IsProblemPath(path)) continue;
                var tex = sr.sprite != null ? sr.sprite.texture : null;
                var details = $"sprite={(sr.sprite != null ? sr.sprite.name : "")}; texture={(tex != null ? tex.name : "")}";
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(path)}\t{sr.gameObject.activeInHierarchy}\t{Tsv(sr.GetIl2CppType().FullName)}\t{sr.enabled}\t{Tsv(details)}");
            }
            foreach (var renderer in Resources.FindObjectsOfTypeAll<Renderer>())
            {
                if (renderer == null) continue;
                var path = SafeObjectPath(renderer.gameObject);
                if (!IsProblemPath(path)) continue;
                var tex = "";
                try
                {
                    var mat = renderer.material;
                    if (mat != null && mat.HasProperty("_MainTex"))
                    {
                        var t = mat.GetTexture("_MainTex");
                        tex = t != null ? t.name : "";
                    }
                }
                catch { }
                var details = "mainTexture=" + tex;
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(path)}\t{renderer.gameObject.activeInHierarchy}\t{Tsv(renderer.GetIl2CppType().FullName)}\t{renderer.enabled}\t{Tsv(details)}");
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Problem component dump failed: " + ex.Message);
        }
    }

    private static string BuildDebugReportPath(string fileName)
    {
        try
        {
            var projectRoot = Directory.GetParent(Paths.GameRootPath)?.FullName;
            if (string.IsNullOrEmpty(projectRoot)) return null;
            var dir = Path.Combine(projectRoot, "debug_reports");
            Directory.CreateDirectory(dir);
            return Path.Combine(dir, fileName);
        }
        catch { return null; }
    }

    private static string SafeSceneName()
    {
        try { return SceneManager.GetActiveScene().name ?? ""; }
        catch { return ""; }
    }

    private static Vector2 SafeRectSize(RectTransform rectTransform)
    {
        try
        {
            if (rectTransform != null) return rectTransform.rect.size;
        }
        catch { }
        return Vector2.zero;
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
        public int Width;
        public int Height;
        public byte AlphaMin;
        public byte AlphaMax;
    }

    private sealed class ImageDecision
    {
        public readonly Replacement Replacement;
        public readonly string Group;
        public readonly string SkipReason;

        public ImageDecision(Replacement replacement, string group, string skipReason)
        {
            Replacement = replacement;
            Group = group;
            SkipReason = skipReason;
        }
    }

    private sealed class DecodedPng
    {
        public int Width;
        public int Height;
        public Color32[] Pixels;
        public byte AlphaMin;
        public byte AlphaMax;
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
            byte alphaMin = 255;
            byte alphaMax = 0;
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
                    if (c.a < alphaMin) alphaMin = c.a;
                    if (c.a > alphaMax) alphaMax = c.a;
                    pixels[(height - 1 - y) * width + x] = c;
                }
            }
            return new DecodedPng { Width = width, Height = height, Pixels = pixels, AlphaMin = alphaMin, AlphaMax = alphaMax };
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
