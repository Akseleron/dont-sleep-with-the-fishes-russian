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
    internal static ConfigEntry<bool> DumpVisibleTextFit;
    internal static ConfigEntry<bool> EnableVisibleTextAudit;
    internal static ConfigEntry<float> VisibleTextAuditIntervalSeconds;
    internal static ConfigEntry<int> VisibleTextAuditMaxScansPerScene;
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
        EnableTextureFix = Config.Bind("Textures", "EnableTextureFix", false, "Replace visible runtime textures/sprites from the Textures folder. Disabled by default because offline Unity asset patching is now used for localized textures.");
        PatchMainMenuTitle = Config.Bind("Textures", "PatchMainMenuTitle", true, "Patch only the main menu title UI Image.");
        PatchTitleSplash = Config.Bind("Textures", "PatchTitleSplash", false, "Patch the startup title splash logo images. Disabled until visual QA confirms it is safe.");
        PatchSettingsLogo = Config.Bind("Textures", "PatchSettingsLogo", false, "Patch the settings menu logo. Disabled for isolation testing.");
        PatchJournalIcon = Config.Bind("Textures", "PatchJournalIcon", false, "Patch the gameplay journal icon. Disabled for isolation testing.");
        PatchHowToPlay = Config.Bind("Textures", "PatchHowToPlay", false, "Patch how-to-play/menu icon textures. Disabled for isolation testing.");
        PatchGameplay3DTextures = Config.Bind("Textures", "PatchGameplay3DTextures", false, "Patch RawImage, SpriteRenderer, and Renderer material textures.");
        DumpVisibleTextureNames = Config.Bind("Diagnostics", "DumpVisibleTextureNames", true, "Write visible texture/component names to ../debug_reports/runtime_visible_texture_names.tsv during scans.");
        DumpVisibleTextFit = Config.Bind("Diagnostics", "DumpVisibleTextFit", true, "Write visible TMP/UI text fit data to ../debug_reports/ui_text_fit_inventory.tsv during scans.");
        EnableVisibleTextAudit = Config.Bind("Diagnostics", "EnableVisibleTextAudit", false, "Development only: write likely English visible UI text to BepInEx/visible_english_audit.tsv. Does not modify text.");
        VisibleTextAuditIntervalSeconds = Config.Bind("Diagnostics", "VisibleTextAuditIntervalSeconds", 1.0f, "Seconds between visible-English audit scans while the scene startup scan window is active.");
        VisibleTextAuditMaxScansPerScene = Config.Bind("Diagnostics", "VisibleTextAuditMaxScansPerScene", 30, "Maximum visible-English audit scans per scene.");
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
    private static readonly Regex EnglishWord = new(@"[A-Za-z][A-Za-z']{1,}", RegexOptions.Compiled);
    private static readonly Regex TechnicalVisibleText = new(@"^(?:[A-Za-z0-9_./\\-]+\.(?:dll|exe|png|assets?)|[A-Fa-f0-9]{16,}|[A-Za-z_][A-Za-z0-9_]*(?:Controller|Manager|Renderer|Animator|Canvas|Holder|Pivot|Model|Prefab))$", RegexOptions.Compiled);
    private const string MainTitleTextureReplacementStem = "sharedassets1__Texture2D__50__unnamed_50";
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
    private float scanUntil;
    private float nextScan;
    private int scanCount;
    private TMP_FontAsset runtimeTmpFont;
    private Font runtimeUnityFont;
    private bool fontAttempted;
    private string reportPath;
    private string componentReportPath;
    private string textFitReportPath;
    private string visibleEnglishAuditPath;
    private string lastSceneName;
    private float nextVisibleTextAuditScan;
    private int visibleTextAuditScanCountForScene;
    private readonly List<Sprite> createdReplacementSprites = new();

    public RuntimeFixBehaviour(IntPtr ptr) : base(ptr) { }

    private void Start()
    {
        scanUntil = Time.realtimeSinceStartup + Math.Max(3f, Plugin.StartupScanSeconds.Value);
        nextScan = 0f;
        lastSceneName = SafeSceneName();
        reportPath = BuildDebugReportPath("runtime_visible_texture_targets.tsv");
        componentReportPath = BuildDebugReportPath("runtime_problem_texture_components.tsv");
        textFitReportPath = BuildDebugReportPath("ui_text_fit_inventory.tsv");
        visibleEnglishAuditPath = BuildGameBepInExPath("visible_english_audit.tsv");
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
            patchedRawImages.Clear();
            patchedSpriteRenderers.Clear();
            failedSpriteRenderers.Clear();
            patchedRenderers.Clear();
            patchedTmpTexts.Clear();
            visibleTextAuditScanCountForScene = 0;
            nextVisibleTextAuditScan = 0f;
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
                repl.PngBytes = File.ReadAllBytes(path);
                var decoded = SimplePng.Decode(repl.PngBytes);
                repl.Pixels = decoded.Pixels;
                repl.AlphaMin = decoded.AlphaMin;
                repl.AlphaMax = decoded.AlphaMax;
                repl.Width = decoded.Width;
                repl.Height = decoded.Height;
                var tex = CreateTextureFromReplacementPixels(repl, repl.Stem, out var textureCreateDetail);
                repl.Texture = tex;
                byStem[repl.Stem] = repl;
                byName[repl.Stem] = repl;
                byName[repl.ExportedName] = repl;
                byName[$"{repl.ObjectType}:{repl.PathId}"] = repl;
                replacementNames.Add(repl.Stem);
                replacementNames.Add(repl.ExportedName);
                if (repl.Texture != null) replacementNames.Add(repl.Texture.name);
                Plugin.LogSource.LogInfo($"Loaded replacement {repl.FileName}: type={repl.ObjectType}, pathId={repl.PathId}, name={repl.ExportedName}, size={repl.Width}x{repl.Height}, sourceTextureCreated={repl.Texture != null}, loader='{textureCreateDetail}'");
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
        if (Plugin.DumpVisibleTextFit.Value) DumpVisibleTextFit(reason);
        if (Plugin.EnableVisibleTextAudit.Value) DumpVisibleEnglishAudit(reason);
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
                var path = SafeObjectPath(image.gameObject);
                var spriteTextureName = image.sprite.texture != null ? image.sprite.texture.name : null;
                if (IsMainMenuTitlePath(path))
                {
                    if (patchedImages.Contains(id)) continue;
                    if (!Plugin.PatchMainMenuTitle.Value) continue;
                    if (TryOverwriteMainMenuTitleTexture(image, path))
                    {
                        patchedImages.Add(id);
                        changed++;
                    }
                    else
                    {
                        failedImages.Add(id);
                    }
                    continue;
                }
                if (patchedImages.Contains(id) && IsReplacementName(image.sprite.name, spriteTextureName)) continue;
                var oldSpriteName = image.sprite.name;
                var decision = GetImageDecision(path, image.sprite.name, spriteTextureName);
                var repl = decision.Replacement;
                if (repl == null) continue;
                if (!string.Equals(decision.SkipReason, "apply", StringComparison.Ordinal)) continue;
                var sprite = CreateSpriteLike(repl, image.sprite);
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
    private bool TryOverwriteMainMenuTitleTexture(Image image, string path)
    {
        var sprite = image.sprite;
        var tex = sprite != null ? sprite.texture as Texture2D : null;
        if (sprite == null || tex == null)
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='missing sprite or Texture2D'.");
            return false;
        }

        if (!byStem.TryGetValue(MainTitleTextureReplacementStem, out var repl) || repl == null)
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='replacement not loaded', replacementStem='{MainTitleTextureReplacementStem}'.");
            return false;
        }

        LogMainMenuTitleTextureOverwriteDiagnostic(path, image, repl, "before");

        if (repl.ObjectType != "Texture2D")
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='replacement is not Texture2D', replacement='{repl.FileName}', replacementType='{repl.ObjectType}'.");
            return false;
        }

        if (tex.width != repl.Width || tex.height != repl.Height)
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='dimension mismatch', originalTexture='{tex.name}', originalSize={tex.width}x{tex.height}, replacement='{repl.FileName}', replacementSize={repl.Width}x{repl.Height}.");
            return false;
        }

        var loadImageError = "";
        try
        {
            var bytes = new Il2CppStructArray<byte>(repl.PngBytes.Length);
            for (var i = 0; i < repl.PngBytes.Length; i++) bytes[i] = repl.PngBytes[i];
            var ok = ImageConversion.LoadImage(tex, bytes, false);
            Plugin.LogSource.LogInfo($"Main title texture overwrite result: path='{path}', component='UnityEngine.UI.Image', sprite='{sprite.name}', originalTexture='{tex.name}', originalSize={tex.width}x{tex.height}, targetFormat='{TextureFormatText(tex)}', targetGraphicsFormat='{GraphicsFormatText(tex)}', replacement='{repl.FileName}', replacementSize={repl.Width}x{repl.Height}, method='LoadImage', success={ok}.");
            if (ok)
            {
                LogMainMenuTitleTextureOverwriteDiagnostic(path, image, repl, "after-loadimage");
                return true;
            }
            loadImageError = "LoadImage returned false";
        }
        catch (Exception ex)
        {
            loadImageError = ex.GetType().Name + ": " + ex.Message;
            Plugin.LogSource.LogWarning($"Main title texture overwrite failed: path='{path}', method='LoadImage', replacement='{repl.FileName}', error='{loadImageError}'.");
        }

        var source = CreateTextureFromReplacementPixels(repl, MainTitleTextureReplacementStem + "__copy_source", out var sourceCreateDetail);
        var sourceCreated = source != null;
        Plugin.LogSource.LogInfo($"Main title source texture creation: path='{path}', replacement='{repl.FileName}', sourceTextureCreated={sourceCreated}, loader='{sourceCreateDetail}', sourceSize={(source != null ? source.width : 0)}x{(source != null ? source.height : 0)}, sourceFormat='{TextureFormatText(source)}', sourceGraphicsFormat='{GraphicsFormatText(source)}', sourceNativePtr='{NativeTexturePtrText(source)}', targetTexture='{tex.name}', targetSize={tex.width}x{tex.height}, targetFormat='{TextureFormatText(tex)}', targetGraphicsFormat='{GraphicsFormatText(tex)}', targetNativePtr='{NativeTexturePtrText(tex)}'.");
        if (source == null)
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='source texture creation failed', replacement='{repl.FileName}', loader='{sourceCreateDetail}', previousLoadImageError='{loadImageError}'. Vanilla title left untouched.");
            return false;
        }
        if (source.width != tex.width || source.height != tex.height)
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='source/target dimension mismatch', sourceSize={source.width}x{source.height}, targetSize={tex.width}x{tex.height}, previousLoadImageError='{loadImageError}'. Vanilla title left untouched.");
            return false;
        }

        var copyTextureError = "";
        try
        {
            Graphics.CopyTexture(source, tex);
            Plugin.LogSource.LogInfo($"Main title texture overwrite result: path='{path}', component='UnityEngine.UI.Image', sprite='{sprite.name}', originalTexture='{tex.name}', originalSize={tex.width}x{tex.height}, replacement='{repl.FileName}', replacementSize={repl.Width}x{repl.Height}, sourceTextureCreated=True, sourceTextureNull=False, method='Graphics.CopyTexture', success=True, previousLoadImageError='{loadImageError}', sourceFormat='{TextureFormatText(source)}', targetFormat='{TextureFormatText(tex)}', sourceGraphicsFormat='{GraphicsFormatText(source)}', targetGraphicsFormat='{GraphicsFormatText(tex)}'.");
            LogMainMenuTitleTextureOverwriteDiagnostic(path, image, repl, "after-copytexture");
            return true;
        }
        catch (Exception ex)
        {
            copyTextureError = ex.GetType().Name + ": " + ex.Message;
            Plugin.LogSource.LogWarning($"Main title texture overwrite failed: path='{path}', method='Graphics.CopyTexture', replacement='{repl.FileName}', error='{copyTextureError}', previousLoadImageError='{loadImageError}'.");
        }

        try
        {
            var ok = Graphics.ConvertTexture(source, tex);
            Plugin.LogSource.LogInfo($"Main title texture overwrite result: path='{path}', component='UnityEngine.UI.Image', sprite='{sprite.name}', originalTexture='{tex.name}', originalSize={tex.width}x{tex.height}, replacement='{repl.FileName}', replacementSize={repl.Width}x{repl.Height}, sourceTextureCreated=True, sourceTextureNull=False, method='Graphics.ConvertTexture', success={ok}, previousLoadImageError='{loadImageError}', previousCopyTextureError='{copyTextureError}', sourceFormat='{TextureFormatText(source)}', targetFormat='{TextureFormatText(tex)}', sourceGraphicsFormat='{GraphicsFormatText(source)}', targetGraphicsFormat='{GraphicsFormatText(tex)}'.");
            if (ok)
            {
                LogMainMenuTitleTextureOverwriteDiagnostic(path, image, repl, "after-converttexture");
                return true;
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning($"Main title texture overwrite failed: path='{path}', method='Graphics.ConvertTexture', replacement='{repl.FileName}', error='{ex.GetType().Name}: {ex.Message}', previousLoadImageError='{loadImageError}', previousCopyTextureError='{copyTextureError}'.");
        }

        Plugin.LogSource.LogWarning($"Main title texture overwrite skipped: path='{path}', reason='all overwrite methods failed', loadImage='{loadImageError}', copyTexture='{copyTextureError}'. Vanilla title left untouched.");
        return false;
    }

    [HideFromIl2Cpp]
    private static Texture2D CreateTextureFromReplacementPixels(Replacement repl, string textureName, out string detail)
    {
        try
        {
            if (repl.Pixels == null || repl.Pixels.Length != repl.Width * repl.Height)
            {
                var decoded = SimplePng.Decode(repl.PngBytes);
                repl.Pixels = decoded.Pixels;
                repl.Width = decoded.Width;
                repl.Height = decoded.Height;
                repl.AlphaMin = decoded.AlphaMin;
                repl.AlphaMax = decoded.AlphaMax;
            }
            var tex = new Texture2D(repl.Width, repl.Height, TextureFormat.RGBA32, false);
            tex.name = textureName;
            tex.wrapMode = TextureWrapMode.Clamp;
            tex.filterMode = FilterMode.Bilinear;
            var colors = new Il2CppStructArray<Color32>(repl.Pixels.Length);
            for (var i = 0; i < repl.Pixels.Length; i++) colors[i] = repl.Pixels[i];
            tex.SetPixels32(colors);
            tex.Apply(false, false);
            if (tex == null)
            {
                detail = "managed_png_decode:SetPixels32+Apply produced Unity-null Texture2D";
                return null;
            }
            detail = $"managed_png_decode:SetPixels32+Apply format='{TextureFormatText(tex)}' graphicsFormat='{GraphicsFormatText(tex)}' nativePtr='{NativeTexturePtrText(tex)}'";
            return tex;
        }
        catch (Exception ex)
        {
            detail = "managed_png_decode:SetPixels32+Apply failed: " + ex.GetType().Name + ": " + ex.Message;
            return null;
        }
    }

    [HideFromIl2Cpp]
    private void LogMainMenuTitleTextureOverwriteDiagnostic(string path, Image image, Replacement repl, string phase)
    {
        try
        {
            var sprite = image.sprite;
            var tex = sprite != null ? sprite.texture : null;
            var spriteRect = sprite != null ? sprite.rect : Rect.zero;
            var spritePivot = sprite != null ? sprite.pivot : Vector2.zero;
            var size = SafeRectSize(image.rectTransform);
            Plugin.LogSource.LogInfo(
                "MainTitle texture overwrite diagnostic " +
                $"phase='{phase}', path='{path}', component='UnityEngine.UI.Image', active={image.gameObject.activeInHierarchy}, imageEnabled={image.enabled}, " +
                $"sprite='{(sprite != null ? sprite.name : "")}', texture='{(tex != null ? tex.name : "")}', textureSize={(tex != null ? tex.width : 0)}x{(tex != null ? tex.height : 0)}, targetFormat='{TextureFormatText(tex)}', targetGraphicsFormat='{GraphicsFormatText(tex)}', " +
                $"spriteRect={RectText(spriteRect)}, spritePivot={VectorText(spritePivot)}, pixelsPerUnit={(sprite != null ? sprite.pixelsPerUnit.ToString(CultureInfo.InvariantCulture) : "")}, " +
                $"imageType='{image.type}', preserveAspect={image.preserveAspect}, rectTransformSize={VectorText(size)}, anchoredPosition={VectorText(image.rectTransform.anchoredPosition)}, " +
                $"replacement='{repl.FileName}', replacementType='{repl.ObjectType}', replacementPng={repl.Width}x{repl.Height}, replacementAlpha={repl.AlphaMin}-{repl.AlphaMax}");
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Main title texture overwrite diagnostic failed: " + ex.Message);
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
                var candidate = decision.Replacement;
                if (IsMainMenuTitlePath(path))
                {
                    byStem.TryGetValue(MainTitleTextureReplacementStem, out candidate);
                }
                var size = SafeRectSize(image.rectTransform);
                var applied = patchedImages.Contains(image.GetInstanceID()) || IsReplacementName(image.sprite.name, tex != null ? tex.name : null);
                var skipReason = patchedImages.Contains(image.GetInstanceID()) ? "texture_overwritten" : (applied ? "already_replaced" : decision.SkipReason);
                writer.WriteLine($"{scanCount}\t{reason}\t{Tsv(SafeSceneName())}\t{Tsv(path)}\tImage\t{image.gameObject.activeInHierarchy}\t{image.enabled}\t{size.x.ToString(CultureInfo.InvariantCulture)}\t{size.y.ToString(CultureInfo.InvariantCulture)}\t{Tsv(image.sprite.name)}\t{Tsv(tex != null ? tex.name : "")}\t\t\t\t{Tsv(candidate != null ? candidate.FileName : "")}\t{applied}\t{Tsv(skipReason)}");
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
            if (first) writer.WriteLine("scan\treason\tscene\tobject_path\tactive_self\tactive_in_hierarchy\tlayer\ttag\tcomponents\trect_anchor_min\trect_anchor_max\trect_pivot\trect_size_delta\trect_anchored_position\tlocal_scale\tcanvas_renderer\timage_enabled\timage_color\timage_material\timage_type\timage_preserve_aspect\timage_sprite_name\timage_sprite_texture_name\timage_sprite_rect\timage_sprite_pivot\timage_pixels_per_unit\traw_image_enabled\traw_image_color\traw_image_texture_name\traw_image_uv_rect\trenderer_enabled\trenderer_material_name\trenderer_main_texture_name");

            var objects = new Dictionary<int, GameObject>();
            foreach (var transform in Resources.FindObjectsOfTypeAll<Transform>())
            {
                if (transform == null || transform.gameObject == null) continue;
                var path = SafeObjectPath(transform.gameObject);
                if (IsProblemPath(path)) AddNeighborhood(transform.gameObject, objects);
            }

            foreach (var go in objects.Values.OrderBy(SafeObjectPath))
            {
                writer.WriteLine(BuildProblemObjectRow(reason, go));
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Problem component dump failed: " + ex.Message);
        }
    }

    private void DumpVisibleTextFit(string reason)
    {
        try
        {
            if (string.IsNullOrEmpty(textFitReportPath)) return;
            var first = !File.Exists(textFitReportPath);
            using var writer = new StreamWriter(textFitReportPath, append: true);
            if (first)
            {
                writer.WriteLine("scan\treason\tscene\tobject_path\tcomponent_type\tactive_in_hierarchy\tenabled\tcurrent_text\tfont_asset_name\tfont_material_name\tfont_fallback_assets\tfont_size\tenable_auto_sizing\tword_wrapping\toverflow_mode\talignment\trect_width\trect_height\tpreferred_width\tpreferred_height\trendered_width\trendered_height\tcontains_cyrillic\tlikely_issue");
            }

            foreach (var text in Resources.FindObjectsOfTypeAll<TMP_Text>())
            {
                if (text == null || text.gameObject == null) continue;
                if (!text.gameObject.activeInHierarchy || !text.enabled) continue;

                var rect = SafeRectSize(text.rectTransform);
                var preferredWidth = SafeFloat(() => text.preferredWidth);
                var preferredHeight = SafeFloat(() => text.preferredHeight);
                var renderedWidth = SafeFloat(() => text.renderedWidth);
                var renderedHeight = SafeFloat(() => text.renderedHeight);
                var currentText = SafeText(() => text.text);
                var issue = FitIssue(rect, preferredWidth, preferredHeight, renderedWidth, renderedHeight, currentText, text.enableWordWrapping);

                writer.WriteLine(string.Join("\t", new[]
                {
                    scanCount.ToString(CultureInfo.InvariantCulture),
                    Tsv(reason),
                    Tsv(SafeSceneName()),
                    Tsv(SafeObjectPath(text.gameObject)),
                    Tsv(ComponentTypeName(text)),
                    text.gameObject.activeInHierarchy.ToString(),
                    text.enabled.ToString(),
                    Tsv(currentText),
                    Tsv(text.font != null ? text.font.name : ""),
                    Tsv(text.fontSharedMaterial != null ? text.fontSharedMaterial.name : ""),
                    Tsv(TmpFallbackListText(text.font)),
                    text.fontSize.ToString(CultureInfo.InvariantCulture),
                    text.enableAutoSizing.ToString(),
                    text.enableWordWrapping.ToString(),
                    Tsv(text.overflowMode.ToString()),
                    Tsv(text.alignment.ToString()),
                    rect.x.ToString(CultureInfo.InvariantCulture),
                    rect.y.ToString(CultureInfo.InvariantCulture),
                    preferredWidth.ToString(CultureInfo.InvariantCulture),
                    preferredHeight.ToString(CultureInfo.InvariantCulture),
                    renderedWidth.ToString(CultureInfo.InvariantCulture),
                    renderedHeight.ToString(CultureInfo.InvariantCulture),
                    ContainsCyrillic(currentText).ToString(),
                    Tsv(issue),
                }));
            }

            foreach (var text in Resources.FindObjectsOfTypeAll<UnityEngine.UI.Text>())
            {
                if (text == null || text.gameObject == null) continue;
                if (!text.gameObject.activeInHierarchy || !text.enabled) continue;

                var rectTransform = text.GetComponent<RectTransform>();
                var rect = SafeRectSize(rectTransform);
                var currentText = SafeText(() => text.text);
                var wraps = text.horizontalOverflow == HorizontalWrapMode.Wrap;
                var preferredWidth = SafeFloat(() => text.preferredWidth);
                var preferredHeight = SafeFloat(() => text.preferredHeight);
                var issue = FitIssue(rect, preferredWidth, preferredHeight, 0f, 0f, currentText, wraps);

                writer.WriteLine(string.Join("\t", new[]
                {
                    scanCount.ToString(CultureInfo.InvariantCulture),
                    Tsv(reason),
                    Tsv(SafeSceneName()),
                    Tsv(SafeObjectPath(text.gameObject)),
                    Tsv(ComponentTypeName(text)),
                    text.gameObject.activeInHierarchy.ToString(),
                    text.enabled.ToString(),
                    Tsv(currentText),
                    Tsv(text.font != null ? text.font.name : ""),
                    Tsv(text.material != null ? text.material.name : ""),
                    "",
                    text.fontSize.ToString(CultureInfo.InvariantCulture),
                    "False",
                    wraps.ToString(),
                    Tsv(text.verticalOverflow.ToString()),
                    Tsv(text.alignment.ToString()),
                    rect.x.ToString(CultureInfo.InvariantCulture),
                    rect.y.ToString(CultureInfo.InvariantCulture),
                    preferredWidth.ToString(CultureInfo.InvariantCulture),
                    preferredHeight.ToString(CultureInfo.InvariantCulture),
                    "",
                    "",
                    ContainsCyrillic(currentText).ToString(),
                    Tsv(issue),
                }));
            }
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Visible text fit dump failed: " + ex.Message);
        }
    }

    private void DumpVisibleEnglishAudit(string reason)
    {
        try
        {
            if (string.IsNullOrEmpty(visibleEnglishAuditPath)) return;
            if (visibleTextAuditScanCountForScene >= Math.Max(0, Plugin.VisibleTextAuditMaxScansPerScene.Value)) return;

            var now = Time.realtimeSinceStartup;
            if (now < nextVisibleTextAuditScan) return;
            nextVisibleTextAuditScan = now + Math.Max(0.1f, Plugin.VisibleTextAuditIntervalSeconds.Value);
            visibleTextAuditScanCountForScene++;

            var first = !File.Exists(visibleEnglishAuditPath);
            var scanned = 0;
            var found = 0;
            using var writer = new StreamWriter(visibleEnglishAuditPath, append: true);
            if (first)
            {
                writer.WriteLine("scene\tscan_number\tcomponent_type\tgameobject_name\tfull_transform_path\tcurrent_text\tnormalized_text\tparent_path_block_guess\trect_width\trect_height\tfont_size\tactive_in_hierarchy\tnotes");
            }

            foreach (var text in Resources.FindObjectsOfTypeAll<TMP_Text>())
            {
                if (text == null || text.gameObject == null) continue;
                if (!text.gameObject.activeInHierarchy || !text.enabled) continue;
                scanned++;
                var currentText = SafeText(() => text.text);
                if (!IsLikelyVisibleEnglish(currentText)) continue;
                found++;
                var rect = SafeRectSize(text.rectTransform);
                WriteVisibleEnglishAuditRow(writer, text, text.gameObject, currentText, rect, text.fontSize, "TMP_Text");
            }

            foreach (var text in Resources.FindObjectsOfTypeAll<UnityEngine.UI.Text>())
            {
                if (text == null || text.gameObject == null) continue;
                if (!text.gameObject.activeInHierarchy || !text.enabled) continue;
                scanned++;
                var currentText = SafeText(() => text.text);
                if (!IsLikelyVisibleEnglish(currentText)) continue;
                found++;
                var rect = SafeRectSize(text.GetComponent<RectTransform>());
                WriteVisibleEnglishAuditRow(writer, text, text.gameObject, currentText, rect, text.fontSize, "UnityEngine.UI.Text");
            }

            Plugin.LogSource.LogInfo($"Visible English audit scan {visibleTextAuditScanCountForScene}: scanned={scanned}, likelyEnglish={found}, path='{visibleEnglishAuditPath}'");
        }
        catch (Exception ex)
        {
            Plugin.LogSource.LogWarning("Visible English audit failed: " + ex.Message);
        }
    }

    private void WriteVisibleEnglishAuditRow(StreamWriter writer, Component component, GameObject go, string currentText, Vector2 rect, float fontSize, string fallbackType)
    {
        var path = SafeObjectPath(go);
        var normalized = NormalizeVisibleText(currentText);
        writer.WriteLine(string.Join("\t", new[]
        {
            Tsv(SafeSceneName()),
            visibleTextAuditScanCountForScene.ToString(CultureInfo.InvariantCulture),
            Tsv(ComponentTypeName(component) ?? fallbackType),
            Tsv(go != null ? go.name : ""),
            Tsv(path),
            Tsv(currentText),
            Tsv(normalized),
            Tsv(GuessVisibleTextBlock(path, normalized)),
            rect.x.ToString(CultureInfo.InvariantCulture),
            rect.y.ToString(CultureInfo.InvariantCulture),
            fontSize.ToString(CultureInfo.InvariantCulture),
            (go != null && go.activeInHierarchy).ToString(),
            Tsv(VisibleEnglishNotes(currentText, rect)),
        }));
    }

    private static bool IsLikelyVisibleEnglish(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return false;
        var normalized = NormalizeVisibleText(text);
        if (normalized.Length < 2) return false;
        if (ContainsCyrillic(normalized)) return false;
        if (!EnglishWord.IsMatch(normalized)) return false;
        if (TechnicalVisibleText.IsMatch(normalized)) return false;
        return true;
    }

    private static string NormalizeVisibleText(string text)
    {
        if (string.IsNullOrEmpty(text)) return "";
        var noTags = Regex.Replace(text, "<[^>]+>", "");
        noTags = noTags.Replace("\\n", " ").Replace("\\r", " ");
        return Regex.Replace(noTags, @"\s+", " ").Trim();
    }

    private static string GuessVisibleTextBlock(string path, string normalizedText)
    {
        var p = path ?? "";
        var t = normalizedText ?? "";
        if (p.Contains("SETTINGS", StringComparison.OrdinalIgnoreCase) || t.Contains("Restore Defaults", StringComparison.Ordinal)) return "OptionsMenu";
        if (p.StartsWith("MENU/", StringComparison.Ordinal)) return "MainMenu";
        if (p.Contains("FriendManageUI", StringComparison.Ordinal) || p.Contains("FriendHud", StringComparison.Ordinal)) return "FriendSupportPanel";
        if (t.Contains("feel good", StringComparison.OrdinalIgnoreCase) || t.Contains("dying", StringComparison.OrdinalIgnoreCase) || t.Contains("pain", StringComparison.OrdinalIgnoreCase)) return "HealthStatusHUD";
        if (t.Contains("hungry", StringComparison.OrdinalIgnoreCase) || t.Contains("starving", StringComparison.OrdinalIgnoreCase)) return "HungerStatusHUD";
        if (p.Contains("FishedVisuals", StringComparison.Ordinal) || t.Contains("Weight:", StringComparison.Ordinal)) return "FishingResultCard";
        if (p.Contains("Search", StringComparison.OrdinalIgnoreCase)) return "SearchResultPaper";
        if (p.Contains("Notice", StringComparison.OrdinalIgnoreCase) || p.Contains("ItemsUpdate", StringComparison.OrdinalIgnoreCase)) return "LeftNotification";
        if (p.Contains("Task_", StringComparison.Ordinal) || p.Contains("Action", StringComparison.OrdinalIgnoreCase)) return "NightEventChoice";
        if (p.Contains("Journal", StringComparison.OrdinalIgnoreCase)) return "Journal";
        if (p.Contains("Dialog", StringComparison.OrdinalIgnoreCase)) return "Dialogue";
        if (p.Contains("Ending", StringComparison.OrdinalIgnoreCase) || t.Contains("Cause of Death", StringComparison.Ordinal) || t.Contains("Company", StringComparison.Ordinal)) return "EndingStatsScreen";
        return "UnknownNeedsContext";
    }

    private static string VisibleEnglishNotes(string text, Vector2 rect)
    {
        var notes = new List<string>();
        if (text.Contains("\n", StringComparison.Ordinal) || text.Contains("\r", StringComparison.Ordinal)) notes.Add("multiline");
        if (rect.x > 0f && rect.x < 160f) notes.Add("narrow_rect");
        if (text.Length > 40) notes.Add("long_text");
        return string.Join("|", notes);
    }

    private static void AddNeighborhood(GameObject go, Dictionary<int, GameObject> objects)
    {
        AddObject(go, objects);

        var parent = go.transform.parent;
        for (var i = 0; i < 3 && parent != null; i++)
        {
            AddObject(parent.gameObject, objects);
            parent = parent.parent;
        }

        AddChildren(go.transform, objects, 0, 3);
    }

    private static void AddChildren(Transform transform, Dictionary<int, GameObject> objects, int depth, int maxDepth)
    {
        if (transform == null || depth >= maxDepth) return;
        var childCount = transform.childCount;
        for (var i = 0; i < childCount; i++)
        {
            var child = transform.GetChild(i);
            if (child == null) continue;
            AddObject(child.gameObject, objects);
            AddChildren(child, objects, depth + 1, maxDepth);
        }
    }

    private static void AddObject(GameObject go, Dictionary<int, GameObject> objects)
    {
        if (go == null) return;
        objects[go.GetInstanceID()] = go;
    }

    private string BuildProblemObjectRow(string reason, GameObject go)
    {
        var rect = go.GetComponent<RectTransform>();
        var canvas = go.GetComponent<CanvasRenderer>();
        var image = go.GetComponent<Image>();
        var raw = go.GetComponent<RawImage>();
        var renderer = go.GetComponent<Renderer>();

        var imageSprite = image != null ? image.sprite : null;
        var imageTexture = imageSprite != null ? imageSprite.texture : null;
        var rawTexture = raw != null ? raw.texture : null;

        Material rendererMaterial = null;
        Texture rendererTexture = null;
        try
        {
            if (renderer != null) rendererMaterial = renderer.material;
            if (rendererMaterial != null && rendererMaterial.HasProperty("_MainTex")) rendererTexture = rendererMaterial.GetTexture("_MainTex");
        }
        catch { }

        return string.Join("\t", new[]
        {
            scanCount.ToString(CultureInfo.InvariantCulture),
            Tsv(reason),
            Tsv(SafeSceneName()),
            Tsv(SafeObjectPath(go)),
            go.activeSelf.ToString(),
            go.activeInHierarchy.ToString(),
            go.layer.ToString(CultureInfo.InvariantCulture),
            Tsv(SafeTag(go)),
            Tsv(ComponentList(go)),
            Tsv(rect != null ? VectorText(rect.anchorMin) : ""),
            Tsv(rect != null ? VectorText(rect.anchorMax) : ""),
            Tsv(rect != null ? VectorText(rect.pivot) : ""),
            Tsv(rect != null ? VectorText(rect.sizeDelta) : ""),
            Tsv(rect != null ? VectorText(rect.anchoredPosition) : ""),
            Tsv(rect != null ? VectorText(rect.localScale) : ""),
            Tsv(CanvasRendererText(canvas)),
            Tsv(image != null ? image.enabled.ToString() : ""),
            Tsv(image != null ? ColorText(image.color) : ""),
            Tsv(image != null && image.material != null ? image.material.name : ""),
            Tsv(image != null ? image.type.ToString() : ""),
            Tsv(image != null ? image.preserveAspect.ToString() : ""),
            Tsv(imageSprite != null ? imageSprite.name : ""),
            Tsv(imageTexture != null ? imageTexture.name : ""),
            Tsv(imageSprite != null ? RectText(imageSprite.rect) : ""),
            Tsv(imageSprite != null ? VectorText(imageSprite.pivot) : ""),
            Tsv(imageSprite != null ? imageSprite.pixelsPerUnit.ToString(CultureInfo.InvariantCulture) : ""),
            Tsv(raw != null ? raw.enabled.ToString() : ""),
            Tsv(raw != null ? ColorText(raw.color) : ""),
            Tsv(rawTexture != null ? rawTexture.name : ""),
            Tsv(raw != null ? RectText(raw.uvRect) : ""),
            Tsv(renderer != null ? renderer.enabled.ToString() : ""),
            Tsv(rendererMaterial != null ? rendererMaterial.name : ""),
            Tsv(rendererTexture != null ? rendererTexture.name : ""),
        });
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

    private static string BuildGameBepInExPath(string fileName)
    {
        try
        {
            var dir = Path.Combine(Paths.GameRootPath, "BepInEx");
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

    private static float SafeFloat(Func<float> getter)
    {
        try { return getter(); }
        catch { return 0f; }
    }

    private static string SafeText(Func<string> getter)
    {
        try { return getter() ?? ""; }
        catch (Exception ex) { return "text_unavailable:" + ex.GetType().Name + ":" + ex.Message; }
    }

    private static bool ContainsCyrillic(string text)
    {
        if (string.IsNullOrEmpty(text)) return false;
        foreach (var c in text)
        {
            if (c >= '\u0400' && c <= '\u04FF') return true;
        }
        return false;
    }

    private static string FitIssue(Vector2 rect, float preferredWidth, float preferredHeight, float renderedWidth, float renderedHeight, string text, bool wraps)
    {
        if (string.IsNullOrWhiteSpace(text)) return "ok";
        if (rect.x <= 0f || rect.y <= 0f) return "unknown_rect";

        var width = Math.Max(preferredWidth, renderedWidth);
        var height = Math.Max(preferredHeight, renderedHeight);
        if (height > rect.y + 2f) return "clipped_or_height_risk";
        if (!wraps && width > rect.x + 2f) return "clipped_or_width_risk";
        if (wraps && width > rect.x + 2f) return "wrapped_or_width_risk";
        if (text.Contains("\n", StringComparison.Ordinal) || text.Contains("\r", StringComparison.Ordinal)) return "explicit_multiline";
        return "ok";
    }

    private static string ComponentTypeName(Component component)
    {
        if (component == null) return "";
        try { return component.GetIl2CppType().FullName; }
        catch { return component.GetType().FullName; }
    }

    private static string TmpFallbackListText(TMP_FontAsset font)
    {
        if (font == null) return "";
        try
        {
            var table = font.fallbackFontAssetTable;
            if (table == null) return "";
            var names = new List<string>();
            for (var i = 0; i < table.Count; i++)
            {
                var fallback = table[i];
                if (fallback != null) names.Add(fallback.name);
            }
            return string.Join("|", names);
        }
        catch (Exception ex)
        {
            return "fallback_list_error:" + ex.GetType().Name + ":" + ex.Message;
        }
    }

    private static string VectorText(Vector2 value) =>
        value.x.ToString(CultureInfo.InvariantCulture) + "," + value.y.ToString(CultureInfo.InvariantCulture);

    private static string VectorText(Vector3 value) =>
        value.x.ToString(CultureInfo.InvariantCulture) + "," + value.y.ToString(CultureInfo.InvariantCulture) + "," + value.z.ToString(CultureInfo.InvariantCulture);

    private static string RectText(Rect value) =>
        value.x.ToString(CultureInfo.InvariantCulture) + "," +
        value.y.ToString(CultureInfo.InvariantCulture) + "," +
        value.width.ToString(CultureInfo.InvariantCulture) + "," +
        value.height.ToString(CultureInfo.InvariantCulture);

    private static string ColorText(Color value) =>
        value.r.ToString(CultureInfo.InvariantCulture) + "," +
        value.g.ToString(CultureInfo.InvariantCulture) + "," +
        value.b.ToString(CultureInfo.InvariantCulture) + "," +
        value.a.ToString(CultureInfo.InvariantCulture);

    private static string TextureFormatText(Texture2D tex)
    {
        if (tex == null) return "null";
        try { return tex.format.ToString(); }
        catch (Exception ex) { return "unavailable:" + ex.GetType().Name + ":" + ex.Message; }
    }

    private static string GraphicsFormatText(Texture tex)
    {
        if (tex == null) return "null";
        try { return tex.graphicsFormat.ToString(); }
        catch (Exception ex) { return "unavailable:" + ex.GetType().Name + ":" + ex.Message; }
    }

    private static string NativeTexturePtrText(Texture tex)
    {
        if (tex == null) return "null";
        try { return tex.GetNativeTexturePtr().ToString("x"); }
        catch (Exception ex) { return "unavailable:" + ex.GetType().Name + ":" + ex.Message; }
    }

    private static string SafeTag(GameObject go)
    {
        try { return go.tag ?? ""; }
        catch { return ""; }
    }

    private static string ComponentList(GameObject go)
    {
        try
        {
            var components = go.GetComponents<Component>();
            var names = new List<string>();
            foreach (var component in components)
            {
                if (component == null) continue;
                try { names.Add(component.GetIl2CppType().FullName); }
                catch { names.Add(component.GetType().FullName); }
            }
            return string.Join("|", names);
        }
        catch (Exception ex)
        {
            return "component_list_error:" + ex.GetType().Name + ":" + ex.Message;
        }
    }

    private static string CanvasRendererText(CanvasRenderer canvas)
    {
        if (canvas == null) return "";
        try { return "present=True,cull=" + canvas.cull; }
        catch { return "present=True"; }
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
        public byte[] PngBytes;
        public Color32[] Pixels;
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
