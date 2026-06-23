#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk,
    BooleanVar,
    StringVar,
    Text,
    END,
    DISABLED,
    NORMAL,
    filedialog,
    messagebox,
)
from tkinter import ttk


PATCHER_VERSION = "0.1.2"
GAME_EXE = "DontSleepWithTheFishes.exe"
DATA_DIR_NAME = "DontSleepWithTheFishes_Data"
PATCH_DIR_NAME = "_dswf_rus_patch"
MANIFEST_NAME = "manifest.json"

# These files may be rewritten by BepInEx/XUnity after the first game launch.
# For install detection we check that they exist, but we do not require the
# original patched sha256 to stay unchanged forever. Humanity survives another
# config file mutating itself in public.
MUTABLE_INSTALLED_REL_PATHS = {
    "BepInEx/config/AutoTranslatorConfig.ini",
    "BepInEx/config/ru.dswf.runtimefix.cfg",
}

PNG_RE = re.compile(
    r"^(?P<asset>sharedassets\d+)__(?P<type>Texture2D|Sprite)__(?P<path_id>\d+)__(?P<name>.+)\.png$"
)


def app_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
PAYLOAD_DIR = APP_DIR / "payload"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def rel_to_game(game_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(game_dir.resolve()).as_posix()


def validate_game_dir(game_dir: Path) -> tuple[Path, Path]:
    game_dir = game_dir.expanduser().resolve()
    exe = game_dir / GAME_EXE
    data_dir = game_dir / DATA_DIR_NAME

    if not game_dir.exists():
        raise RuntimeError(f"Папка не существует: {game_dir}")
    if not exe.is_file():
        raise RuntimeError(f"Не найден {GAME_EXE} в выбранной папке.")
    if not data_dir.is_dir():
        raise RuntimeError(f"Не найдена папка {DATA_DIR_NAME} рядом с exe.")

    return game_dir, data_dir


def patch_root(data_dir: Path) -> Path:
    return data_dir / PATCH_DIR_NAME


def manifest_path(data_dir: Path) -> Path:
    return patch_root(data_dir) / MANIFEST_NAME


def load_manifest(data_dir: Path) -> dict | None:
    path = manifest_path(data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_manifest(data_dir: Path, manifest: dict) -> None:
    root = patch_root(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = manifest_path(data_dir)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_installed(game_dir: Path, data_dir: Path) -> tuple[bool, list[str]]:
    manifest = load_manifest(data_dir)
    if not manifest:
        return False, ["manifest.json не найден"]

    files = manifest.get("files", {})
    if not isinstance(files, dict) or not files:
        return False, ["manifest.json есть, но список файлов пустой"]

    problems: list[str] = []
    for rel, info in files.items():
        dst = game_dir / rel
        patched_sha = info.get("patched_sha256")
        existed_after = info.get("exists_after", True)

        if existed_after and not dst.exists():
            problems.append(f"файл отсутствует: {rel}")
            continue

        if existed_after and patched_sha:
            if rel in MUTABLE_INSTALLED_REL_PATHS:
                continue
            current_sha = sha256_file(dst)
            if current_sha != patched_sha:
                problems.append(f"sha256 не совпадает: {rel}")

    return len(problems) == 0, problems


def iter_payload_files(payload_subdir: str) -> list[tuple[Path, Path]]:
    root = PAYLOAD_DIR / payload_subdir
    if not root.exists():
        raise RuntimeError(f"Payload folder missing: {root}")

    result: list[tuple[Path, Path]] = []
    for src in sorted(root.rglob("*")):
        if src.is_file():
            rel = src.relative_to(root)
            result.append((src, rel))
    return result


class InstallSession:
    def __init__(self, game_dir: Path, data_dir: Path, log):
        self.game_dir = game_dir
        self.data_dir = data_dir
        self.log = log
        self.patch_root = patch_root(data_dir)
        self.backup_dir = self.patch_root / "backups" / now_stamp()
        self.files: dict[str, dict] = {}

    def ensure_backup_dir(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_before_write(self, dst: Path) -> dict:
        self.ensure_backup_dir()
        rel = rel_to_game(self.game_dir, dst)

        if rel in self.files:
            return self.files[rel]

        existed_before = dst.exists()
        original_sha = sha256_file(dst) if existed_before else None
        backup_rel = None

        if existed_before:
            backup_path = self.backup_dir / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup_path)
            backup_rel = backup_path.relative_to(self.patch_root).as_posix()
            self.log(f"Backup: {rel}")

        info = {
            "existed_before": existed_before,
            "exists_after": True,
            "original_sha256": original_sha,
            "patched_sha256": None,
            "backup_rel": backup_rel,
        }
        self.files[rel] = info
        return info

    def record_after_write(self, dst: Path) -> None:
        rel = rel_to_game(self.game_dir, dst)
        info = self.files.setdefault(rel, {})
        info["exists_after"] = dst.exists()
        info["patched_sha256"] = sha256_file(dst) if dst.exists() else None

    def copy_payload_tree(self, payload_subdir: str, title: str) -> None:
        self.log(f"Installing: {title}")
        for src, rel in iter_payload_files(payload_subdir):
            dst = self.game_dir / rel
            self.backup_before_write(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            self.record_after_write(dst)
            self.log(f"  copied {rel.as_posix()}")

    def backup_game_data_file(self, rel: str) -> Path:
        dst = self.data_dir / rel
        self.backup_before_write(dst)
        return dst

    def write_manifest(self, components: list[str]) -> None:
        manifest = {
            "patcher": "DSWF Russian Patcher",
            "patcher_version": PATCHER_VERSION,
            "installed_at": datetime.now().isoformat(timespec="seconds"),
            "detected_os": platform.system(),
            "game_dir": str(self.game_dir),
            "data_dir": str(self.data_dir),
            "components": components,
            "backup_dir": self.backup_dir.relative_to(self.patch_root).as_posix(),
            "files": self.files,
            "font_replacement": {
                "status": "not implemented",
                "message": "TMP font replacement is not implemented yet.",
            },
        }
        save_manifest(self.data_dir, manifest)
        self.log(f"Manifest written: {manifest_path(self.data_dir)}")


def parse_texture_pngs(texture_dir: Path) -> dict[tuple[str, int], Path]:
    textures: dict[tuple[str, int], Path] = {}
    for path in sorted(texture_dir.glob("*.png")):
        match = PNG_RE.match(path.name)
        if not match:
            continue
        if match.group("type") != "Texture2D":
            continue
        key = (match.group("asset"), int(match.group("path_id")))
        textures[key] = path
    return textures

def create_linux_launcher(session: InstallSession) -> None:
    if platform.system() != "Linux":
        return

    launcher = session.game_dir / "run_dswf_rus.sh"

    content = """#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export WINEDLLOVERRIDES="winhttp=n,b"
exec wine DontSleepWithTheFishes.exe
"""

    session.log("Installing: Linux Wine launcher")
    session.backup_before_write(launcher)
    launcher.write_text(content, encoding="utf-8")
    launcher.chmod(0o755)
    session.record_after_write(launcher)
    session.log("  created run_dswf_rus.sh")

def apply_texture_patches(session: InstallSession) -> None:
    try:
        import UnityPy  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Не найден UnityPy. Для запуска из исходников используй окружение, где установлен UnityPy. "
            "В собранном релизе он должен быть упакован внутрь."
        ) from exc

    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Не найден Pillow. Для запуска из исходников нужен пакет Pillow."
        ) from exc

    texture_dir = PAYLOAD_DIR / "textures"
    textures = parse_texture_pngs(texture_dir)
    if not textures:
        raise RuntimeError(f"Texture2D PNG не найдены в payload: {texture_dir}")

    session.log(f"Installing: offline textures ({len(textures)} PNG)")

    groups: dict[str, dict[int, Path]] = {}
    for (asset_stem, path_id), png in textures.items():
        groups.setdefault(asset_stem + ".assets", {})[path_id] = png

    report_rows: list[dict[str, str]] = []

    for asset_file, targets in sorted(groups.items()):
        asset_path = session.data_dir / asset_file
        if not asset_path.exists():
            raise RuntimeError(f"Не найден Unity asset файл: {asset_path}")

        session.backup_game_data_file(asset_file)
        resS = session.data_dir / (asset_file + ".resS")
        if resS.exists():
            session.backup_game_data_file(asset_file + ".resS")

        before_sha = sha256_file(asset_path)
        session.log(f"Patching {asset_file}")

        env = UnityPy.load(str(asset_path))
        changed = False
        found: set[int] = set()

        for obj in env.objects:
            if obj.type.name != "Texture2D":
                continue

            path_id = int(obj.path_id)
            if path_id not in targets:
                continue

            found.add(path_id)
            png = targets[path_id]

            row = {
                "asset_file": asset_file,
                "path_id": str(path_id),
                "png": png.name,
                "status": "",
                "notes": "",
            }

            try:
                data = obj.read()
                width = int(getattr(data, "m_Width", 0) or 0)
                height = int(getattr(data, "m_Height", 0) or 0)
                unity_name = str(getattr(data, "m_Name", "") or "")

                with Image.open(png) as img:
                    img = img.convert("RGBA")
                    if (img.width, img.height) != (width, height):
                        row["status"] = "skipped_size_mismatch"
                        row["notes"] = f"{img.width}x{img.height} != {width}x{height}"
                        report_rows.append(row)
                        session.log(f"  skipped size mismatch: {png.name}")
                        continue

                    original_format = getattr(data, "m_TextureFormat", None)
                    mip_count = int(getattr(data, "m_MipCount", 1) or 1)
                    data.set_image(img, target_format=original_format, mipmap_count=mip_count)
                    data.save()

                changed = True
                row["status"] = "applied"
                row["notes"] = unity_name
                report_rows.append(row)
                session.log(f"  applied Texture2D {path_id}: {png.name}")

            except Exception as exc:
                row["status"] = "failed"
                row["notes"] = f"{type(exc).__name__}: {exc}"
                report_rows.append(row)
                session.log(f"  failed Texture2D {path_id}: {exc}")

        for path_id, png in sorted(targets.items()):
            if path_id not in found:
                report_rows.append({
                    "asset_file": asset_file,
                    "path_id": str(path_id),
                    "png": png.name,
                    "status": "missing_target",
                    "notes": "",
                })
                session.log(f"  missing Texture2D {path_id}: {png.name}")

        if changed:
            with tempfile.TemporaryDirectory() as td:
                out_dir = Path(td)
                env.save(out_path=str(out_dir))
                patched = out_dir / asset_file
                if not patched.exists():
                    raise RuntimeError(f"UnityPy did not write patched asset: {asset_file}")
                shutil.copy2(patched, asset_path)

            after_sha = sha256_file(asset_path)
            session.record_after_write(asset_path)
            if resS.exists():
                session.record_after_write(resS)
            session.log(f"  sha256 {before_sha[:10]} -> {after_sha[:10]}")
        else:
            session.record_after_write(asset_path)
            if resS.exists():
                session.record_after_write(resS)

    report_path = session.patch_root / "texture_patch_report.tsv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=["asset_file", "path_id", "png", "status", "notes"],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    session.log(f"Texture report written: {report_path}")



def raise_if_texture_patch_failed(session: InstallSession) -> None:
    report = patch_root(session.data_dir) / "texture_patch_report.tsv"
    if not report.exists():
        raise RuntimeError(f"Texture patch report not found: {report}")

    failed: list[str] = []

    with report.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row.get("status") == "failed":
                asset_file = row.get("asset_file", "?")
                path_id = row.get("path_id", "?")
                notes = row.get("notes", "")
                failed.append(f"{asset_file}:{path_id} {notes}".strip())

    if failed:
        preview = "\n".join(failed[:12])
        raise RuntimeError(
            "Texture patch failed. Installation was stopped because the localization "
            "would be incomplete.\n" + preview
        )

def install_patch(game_dir: Path, use_text: bool, use_textures: bool, use_fonts: bool, log) -> None:
    game_dir, data_dir = validate_game_dir(game_dir)

    if use_fonts:
        log("Font replacement is not implemented yet. No files were changed for fonts.")

    components: list[str] = []

    session = InstallSession(game_dir, data_dir, log)

    if use_text:
        components.append("text")
        session.copy_payload_tree("bepinex", "BepInEx + XUnity base")
        session.copy_payload_tree("text", "Russian text translations")
        session.copy_payload_tree("runtime", "DSWF runtime text/layout helper")
        create_linux_launcher(session)

    if use_textures:
        components.append("textures")
        apply_texture_patches(session)
        raise_if_texture_patch_failed(session)

    if use_fonts:
        components.append("fonts_not_implemented")

    if not components:
        raise RuntimeError("Не выбран ни один компонент для установки.")

    session.write_manifest(components)
    log("Install complete.")



def manifest_prefix_owned_by_patcher(manifest: dict, prefix: str) -> bool:
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        return False

    related = [
        info
        for rel, info in files.items()
        if rel == prefix or rel.startswith(prefix + "/")
    ]

    if not related:
        return False

    return all(not bool(info.get("existed_before")) for info in related)


def remove_tree_if_exists(path: Path, game_dir: Path, log, label: str) -> None:
    if not path.exists():
        return

    shutil.rmtree(path)
    try:
        rel = rel_to_game(game_dir, path)
    except Exception:
        rel = str(path)

    log(f"Removed generated folder: {rel} ({label})")


def remove_empty_dirs(root: Path) -> None:
    if not root.exists() or not root.is_dir():
        return

    dirs = [p for p in root.rglob("*") if p.is_dir()]
    dirs.sort(key=lambda p: len(p.parts), reverse=True)

    for directory in dirs:
        try:
            directory.rmdir()
        except OSError:
            pass

    try:
        root.rmdir()
    except OSError:
        pass


def cleanup_after_uninstall(game_dir: Path, data_dir: Path, manifest: dict, log) -> None:
    # dotnet is a self-contained BepInEx runtime payload. If it did not exist
    # before the patch, remove the whole generated tree after uninstall.
    if manifest_prefix_owned_by_patcher(manifest, "dotnet"):
        remove_tree_if_exists(game_dir / "dotnet", game_dir, log, "BepInEx .NET runtime")
    else:
        remove_empty_dirs(game_dir / "dotnet")

    # BepInEx generates logs, interop assemblies and unity-libs on first run.
    # Remove the whole tree only when the patcher installed BepInEx into a clean
    # game folder. Do not nuke a user's pre-existing mod setup.
    if manifest_prefix_owned_by_patcher(manifest, "BepInEx"):
        remove_tree_if_exists(game_dir / "BepInEx", game_dir, log, "BepInEx generated files")
    else:
        remove_empty_dirs(game_dir / "BepInEx")

    root = patch_root(data_dir)
    if root.exists():
        shutil.rmtree(root)
        log("Removed patch data folder.")


def uninstall_patch(game_dir: Path, log, allow_mismatch: bool = False) -> None:
    game_dir, data_dir = validate_game_dir(game_dir)
    manifest = load_manifest(data_dir)

    if not manifest:
        raise RuntimeError("Русификация не найдена: manifest.json отсутствует.")

    files = manifest.get("files", {})
    if not isinstance(files, dict) or not files:
        raise RuntimeError("manifest.json повреждён или не содержит список файлов.")

    root = patch_root(data_dir)

    for rel, info in sorted(files.items(), reverse=True):
        dst = game_dir / rel
        existed_before = bool(info.get("existed_before"))
        backup_rel = info.get("backup_rel")
        patched_sha = info.get("patched_sha256")

        if dst.exists() and patched_sha and rel not in MUTABLE_INSTALLED_REL_PATHS:
            current_sha = sha256_file(dst)
            if current_sha != patched_sha and not allow_mismatch:
                raise RuntimeError(
                    "Файл был изменён после установки русификатора, откат остановлен: "
                    f"{rel}"
                )

        if existed_before:
            if not backup_rel:
                raise RuntimeError(f"Нет backup_rel для файла: {rel}")
            backup = root / backup_rel
            if not backup.exists():
                raise RuntimeError(f"Backup-файл отсутствует: {backup}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, dst)
            log(f"Restored: {rel}")
        else:
            if dst.exists():
                dst.unlink()
                log(f"Removed: {rel}")

    manifest_file = manifest_path(data_dir)
    if manifest_file.exists():
        manifest_file.unlink()
        log("Removed manifest.json")

    cleanup_after_uninstall(game_dir, data_dir, manifest, log)

    log("Uninstall complete.")


class PatcherApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("DSWF Russian Patcher")
        self.root.geometry("820x620")
        self.apply_dark_theme()

        self.game_path = StringVar()
        self.detected_os = StringVar(value=f"Detected OS: {platform.system()}")

        self.use_text = BooleanVar(value=True)
        self.use_textures = BooleanVar(value=True)
        self.use_fonts = BooleanVar(value=False)

        self.status = StringVar(value="Выбери папку игры.")

        self.build_ui()
        self.log(f"DSWF Russian Patcher {PATCHER_VERSION}")
        self.log(f"Detected OS: {platform.system()} {platform.release()}")
        self.log(f"Payload dir: {PAYLOAD_DIR}")

    def apply_dark_theme(self) -> None:
        self.colors = {
            "bg": "#1e1f22",
            "panel": "#25262b",
            "field": "#111317",
            "text": "#e6e6e6",
            "muted": "#a8abb3",
            "accent": "#7aa2f7",
            "button": "#2f3138",
            "button_active": "#3a3d46",
            "border": "#4b4f5c",
            "select": "#3d59a1",
            "disabled": "#6b6f7a",
        }

        self.root.configure(bg=self.colors["bg"])

        style = ttk.Style(self.root)

        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            ".",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["field"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            troughcolor=self.colors["field"],
            selectbackground=self.colors["select"],
            selectforeground=self.colors["text"],
            font=("DejaVu Sans", 10),
        )

        style.configure("TFrame", background=self.colors["bg"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])

        style.configure(
            "TLabelframe",
            background=self.colors["panel"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
        )
        style.configure(
            "TLabelframe.Label",
            background=self.colors["bg"],
            foreground=self.colors["text"],
        )

        style.configure(
            "TButton",
            background=self.colors["button"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            focusthickness=1,
            focuscolor=self.colors["accent"],
            padding=(8, 5),
        )
        style.map(
            "TButton",
            background=[
                ("active", self.colors["button_active"]),
                ("pressed", self.colors["field"]),
                ("disabled", self.colors["panel"]),
            ],
            foreground=[
                ("disabled", self.colors["disabled"]),
            ],
        )

        style.configure(
            "TCheckbutton",
            background=self.colors["panel"],
            foreground=self.colors["text"],
            indicatorcolor=self.colors["field"],
            focuscolor=self.colors["accent"],
        )
        style.map(
            "TCheckbutton",
            background=[
                ("active", self.colors["panel"]),
                ("disabled", self.colors["panel"]),
            ],
            foreground=[
                ("disabled", self.colors["disabled"]),
            ],
            indicatorcolor=[
                ("selected", self.colors["accent"]),
                ("disabled", self.colors["field"]),
            ],
        )

        style.configure(
            "TEntry",
            fieldbackground=self.colors["field"],
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor=self.colors["border"],
        )

    def build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, textvariable=self.detected_os).pack(anchor="w", **pad)

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill="x", **pad)

        ttk.Entry(path_frame, textvariable=self.game_path).pack(side="left", fill="x", expand=True)
        ttk.Button(path_frame, text="Выбрать папку игры", command=self.choose_game_dir).pack(side="left", padx=6)

        comp = ttk.LabelFrame(frame, text="Компоненты")
        comp.pack(fill="x", **pad)

        ttk.Checkbutton(comp, text="Русский текст / BepInEx / XUnity", variable=self.use_text).pack(anchor="w", padx=10, pady=4)
        ttk.Checkbutton(comp, text="Русские текстуры offline", variable=self.use_textures).pack(anchor="w", padx=10, pady=4)

        fonts_cb = ttk.Checkbutton(
            comp,
            text="Русский TMP-шрифт, пока не реализовано",
            variable=self.use_fonts,
            state=DISABLED,
        )
        fonts_cb.pack(anchor="w", padx=10, pady=4)

        ttk.Label(frame, textvariable=self.status).pack(anchor="w", **pad)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", **pad)

        ttk.Button(buttons, text="Установить", command=self.install).pack(side="left", padx=4)
        ttk.Button(buttons, text="Переустановить", command=self.reinstall).pack(side="left", padx=4)
        ttk.Button(buttons, text="Удалить русификацию", command=self.uninstall).pack(side="left", padx=4)
        ttk.Button(buttons, text="Проверить", command=self.refresh_status).pack(side="left", padx=4)

        log_frame = ttk.LabelFrame(frame, text="Лог")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = Text(
            log_frame,
            height=22,
            wrap="word",
            bg=self.colors["field"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["select"],
            selectforeground=self.colors["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            font=("DejaVu Sans Mono", 10),
        )
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def log(self, text: str) -> None:
        self.log_text.insert(END, text + "\n")
        self.log_text.see(END)
        self.root.update_idletasks()

    def selected_game_dir(self) -> Path:
        raw = self.game_path.get().strip()
        if not raw:
            raise RuntimeError("Папка игры не выбрана.")
        return Path(raw)

    def choose_game_dir(self) -> None:
        selected = filedialog.askdirectory(title="Выбери папку с DontSleepWithTheFishes.exe")
        if not selected:
            return
        self.game_path.set(selected)
        self.refresh_status()

    def refresh_status(self) -> None:
        try:
            game_dir, data_dir = validate_game_dir(self.selected_game_dir())
            installed, problems = check_installed(game_dir, data_dir)
            if installed:
                self.status.set("Русификация уже установлена и проверена по manifest + sha256.")
                self.log("Status: installed and verified.")
            else:
                manifest = load_manifest(data_dir)
                if manifest:
                    self.status.set("Manifest найден, но проверка установки не прошла.")
                    self.log("Status: manifest found, but verification failed:")
                    for p in problems:
                        self.log(f"  - {p}")
                else:
                    self.status.set("Игра найдена. Русификация не установлена.")
                    self.log("Status: game found, patch not installed.")
        except Exception as exc:
            self.status.set(str(exc))
            self.log(f"Status error: {exc}")

    def install(self) -> None:
        try:
            game_dir, data_dir = validate_game_dir(self.selected_game_dir())
            installed, _ = check_installed(game_dir, data_dir)

            if installed:
                ok = messagebox.askyesno(
                    "Русификация уже установлена",
                    "Русификация уже установлена и проверена.\n\nПереустановить?",
                )
                if not ok:
                    return
                uninstall_patch(game_dir, self.log, allow_mismatch=True)

            install_patch(
                game_dir,
                use_text=self.use_text.get(),
                use_textures=self.use_textures.get(),
                use_fonts=self.use_fonts.get(),
                log=self.log,
            )
            self.refresh_status()
            messagebox.showinfo("Готово", "Русификация установлена.")
        except Exception as exc:
            self.log("ERROR:")
            self.log(str(exc))
            self.log(traceback.format_exc())
            messagebox.showerror("Ошибка", str(exc))

    def reinstall(self) -> None:
        try:
            game_dir, _ = validate_game_dir(self.selected_game_dir())
            ok = messagebox.askyesno(
                "Переустановка",
                "Переустановить русификацию?\n\nСначала будет выполнен откат из backup, потом новая установка.",
            )
            if not ok:
                return

            if load_manifest(game_dir / DATA_DIR_NAME):
                uninstall_patch(game_dir, self.log, allow_mismatch=True)

            install_patch(
                game_dir,
                use_text=self.use_text.get(),
                use_textures=self.use_textures.get(),
                use_fonts=self.use_fonts.get(),
                log=self.log,
            )
            self.refresh_status()
            messagebox.showinfo("Готово", "Русификация переустановлена.")
        except Exception as exc:
            self.log("ERROR:")
            self.log(str(exc))
            self.log(traceback.format_exc())
            messagebox.showerror("Ошибка", str(exc))

    def uninstall(self) -> None:
        try:
            game_dir, _ = validate_game_dir(self.selected_game_dir())
            ok = messagebox.askyesno(
                "Удаление русификации",
                "Удалить русификацию и восстановить оригинальные файлы из backup?",
            )
            if not ok:
                return

            try:
                uninstall_patch(game_dir, self.log, allow_mismatch=False)
            except RuntimeError as exc:
                if "Файл был изменён после установки" not in str(exc):
                    raise
                force = messagebox.askyesno(
                    "Файлы изменены",
                    str(exc) + "\n\nВсё равно восстановить из backup?",
                )
                if not force:
                    return
                uninstall_patch(game_dir, self.log, allow_mismatch=True)

            self.refresh_status()
            messagebox.showinfo("Готово", "Русификация удалена.")
        except Exception as exc:
            self.log("ERROR:")
            self.log(str(exc))
            self.log(traceback.format_exc())
            messagebox.showerror("Ошибка", str(exc))

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = PatcherApp()
    app.run()


if __name__ == "__main__":
    main()
