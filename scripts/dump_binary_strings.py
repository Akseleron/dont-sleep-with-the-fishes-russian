#!/usr/bin/env python3
"""Dump discoverable strings from IL2CPP/native binaries and Unity data files.

This does not restore C# source. It only extracts byte-level string and
metadata candidates with neighbouring context.
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSIONS = {
    "v1_1_2": Path("/mnt/shared/Games/DontSleepWithTheFishes_v1_1_2"),
    "v1_1_3": Path(
        "/mnt/shared/Games/DontSleepWithTheFishes_v1_1_3/"
        "DontSleepWithTheFishes_v1_1_3_ItchRelease"
    ),
}
UNITY_DATA_FILES = [
    "globalgamemanagers.assets",
    "resources.assets",
    "sharedassets0.assets",
    "sharedassets1.assets",
    "sharedassets2.assets",
    "sharedassets3.assets",
    "sharedassets4.assets",
    "sharedassets5.assets",
    "level0",
    "level1",
    "level2",
    "level3",
    "level4",
    "level5",
]
SOURCE_FILES = [
    "GameAssembly.dll",
    "DontSleepWithTheFishes_Data/il2cpp_data/Metadata/global-metadata.dat",
    "UnityPlayer.dll",
    "baselib.dll",
    *[f"DontSleepWithTheFishes_Data/{name}" for name in UNITY_DATA_FILES],
]
ASCII_RE = re.compile(rb"[ -~]{4,500}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,500}")
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
PATH_OR_EXT_RE = re.compile(r"[\\/]|(?:\.(?:dll|exe|png|jpg|assets|resource|json|ini|cfg|pdb|xml)\b)", re.I)
GUID_RE = re.compile(r"^[a-f0-9]{16,}$", re.I)

OUTPUT_COLUMNS = [
    "version",
    "source_file",
    "encoding",
    "offset",
    "string",
    "normalized_string",
    "context_before",
    "context_after",
    "category_guess",
    "notes",
]
TOOL_NAMES = ["Cpp2IL", "Il2CppDumper", "Il2CppInspector", "AssetRipper"]


@dataclass
class StringHit:
    version: str
    source_file: str
    encoding: str
    offset: int
    string: str
    category_guess: str = ""
    notes: str = ""


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("…", "...")
    text = TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def has_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]", text))


def obvious_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped or not has_letters(stripped):
        return True
    if len(set(stripped)) <= 2 and len(stripped) > 8:
        return True
    if GUID_RE.fullmatch(stripped):
        return True
    if re.fullmatch(r"[A-Za-z0-9_./\\:-]{4,160}", stripped) and PATH_OR_EXT_RE.search(stripped):
        return True
    if stripped.startswith(("Microsoft.", "System.", "UnityEngine.", "Unity.", "BepInEx.", "Il2Cpp")):
        return True
    if re.fullmatch(r"[A-Z0-9_]{6,}", stripped):
        return True
    words = WORD_RE.findall(stripped)
    if not words and len(stripped) > 20:
        return True
    return False


def category_guess(text: str, source_file: str) -> str:
    lowered = text.casefold()
    if "weight" in lowered or re.search(r"\bkg\b", lowered):
        return "weight/fishing"
    if any(term in lowered for term in ["fish", "bait", "food", "rod", "hook", "harpoon"]):
        return "fishing"
    if any(term in lowered for term in ["item", "broken", "found", "search", "damaged"]):
        return "item/ui"
    if any(term in lowered for term in ["talk", "sleep", "friend", "send ", "instead", "sure"]):
        return "dialogue/event"
    if any(mark in text for mark in ["?", "!", "...", "…"]) or len(WORD_RE.findall(text)) >= 4:
        return "player-facing-candidate"
    if "metadata" in source_file.casefold() or source_file.endswith(".dll"):
        return "binary-metadata"
    return "unknown"


def iter_strings(data: bytes, regex: re.Pattern[bytes], decoder: Callable[[bytes], str]) -> Iterable[tuple[int, str]]:
    for match in regex.finditer(data):
        try:
            text = decoder(match.group(0)).strip()
        except Exception:
            continue
        if obvious_noise(text):
            continue
        yield match.start(), text


def scan_file(version: str, root: Path, rel_path: str) -> list[StringHit]:
    path = root / rel_path
    if not path.exists() or not path.is_file():
        return []
    data = path.read_bytes()
    rows: list[StringHit] = []
    for encoding, regex, decoder in [
        ("ascii", ASCII_RE, lambda raw: raw.decode("utf-8", errors="replace")),
        ("utf-16le", UTF16_RE, lambda raw: raw.decode("utf-16le", errors="replace")),
    ]:
        for offset, text in iter_strings(data, regex, decoder):
            rows.append(
                StringHit(
                    version=version,
                    source_file=rel_path,
                    encoding=encoding,
                    offset=offset,
                    string=text,
                    category_guess=category_guess(text, rel_path),
                    notes="binary string dump only; does not reconstruct source",
                )
            )
    rows.sort(key=lambda item: (item.source_file, item.offset, item.encoding))
    return rows


def preview(text: str, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def write_version(version: str, root: Path, out_root: Path) -> None:
    out_dir = out_root / version
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[StringHit] = []
    for rel_path in SOURCE_FILES:
        rows.extend(scan_file(version, root, rel_path))

    by_file: dict[str, list[StringHit]] = {}
    for row in rows:
        by_file.setdefault(row.source_file, []).append(row)

    out_path = out_dir / "binary_strings.tsv"
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, delimiter="\t")
        writer.writeheader()
        for source_file, file_rows in sorted(by_file.items()):
            file_rows.sort(key=lambda item: item.offset)
            for index, row in enumerate(file_rows):
                before = " | ".join(preview(item.string) for item in file_rows[max(0, index - 3) : index])
                after = " | ".join(preview(item.string) for item in file_rows[index + 1 : index + 4])
                writer.writerow(
                    {
                        "version": row.version,
                        "source_file": row.source_file,
                        "encoding": row.encoding,
                        "offset": row.offset,
                        "string": row.string,
                        "normalized_string": normalize(row.string),
                        "context_before": before,
                        "context_after": after,
                        "category_guess": row.category_guess,
                        "notes": row.notes,
                    }
                )
    print(f"{version}: wrote {len(rows)} binary/raw string rows -> {out_path}")


def detect_tools(out_root: Path) -> None:
    search_roots = [ROOT, ROOT / ".tools", ROOT / ".tools-gui", Path("/home/akseleron/projects/dswf-rus")]
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tool_name in TOOL_NAMES:
        patterns = [f"*{tool_name}*", f"*{tool_name.lower()}*"]
        for base in search_roots:
            if not base.exists():
                continue
            for pattern in patterns:
                for path in base.rglob(pattern):
                    if ".git" in path.parts or ".local_dumps" in path.parts:
                        continue
                    key = (tool_name, str(path))
                    if key in seen:
                        continue
                    seen.add(key)
                    kind = "executable_or_dir"
                    if path.suffix.lower() == ".dll":
                        kind = "library_only"
                    rows.append({"tool": tool_name, "path": str(path), "kind": kind})
    out_root.mkdir(parents=True, exist_ok=True)
    with (out_root / "tool_availability.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tool", "path", "kind"], delimiter="\t")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (row["tool"], row["path"])))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(ROOT / ".local_dumps/binary_strings"))
    parser.add_argument("--v1-1-2", default=str(DEFAULT_VERSIONS["v1_1_2"]))
    parser.add_argument("--v1-1-3", default=str(DEFAULT_VERSIONS["v1_1_3"]))
    args = parser.parse_args()

    out_root = Path(args.out_root)
    detect_tools(out_root)
    for version, root in {
        "v1_1_2": Path(args.v1_1_2),
        "v1_1_3": Path(args.v1_1_3),
    }.items():
        write_version(version, root, out_root)


if __name__ == "__main__":
    main()
