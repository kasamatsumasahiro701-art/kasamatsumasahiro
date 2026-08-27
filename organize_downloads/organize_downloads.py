#!/usr/bin/env python3
"""Organize files in a Downloads folder into category subfolders.

Usage:
    python organize_downloads.py [--path PATH] [--dry-run] [--by-date]
                                  [--config CONFIG.json] [--include-incomplete]

By default, targets ~/Downloads. Files are sorted into subfolders such as
Images, Documents, Videos, Audio, Archives, Installers, Spreadsheets,
Presentations, Code and Others, based on their extension.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".tiff", ".ico"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".pages"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods", ".numbers"],
    "Presentations": [".ppt", ".pptx", ".odp", ".key"],
    "Videos": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk"],
    "Code": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".html", ".css",
             ".json", ".xml", ".yaml", ".yml", ".sh", ".ipynb"],
}

# Extensions that indicate an in-progress/incomplete download; skipped unless
# --include-incomplete is passed.
INCOMPLETE_SUFFIXES = {".crdownload", ".part", ".download", ".tmp"}

OTHERS = "Others"


def load_categories(config_path: str | None) -> dict[str, list[str]]:
    if not config_path:
        return DEFAULT_CATEGORIES
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    categories = dict(DEFAULT_CATEGORIES)
    categories.update(data)
    return categories


def build_extension_map(categories: dict[str, list[str]]) -> dict[str, str]:
    ext_map: dict[str, str] = {}
    for category, extensions in categories.items():
        for ext in extensions:
            ext_map[ext.lower()] = category
    return ext_map


def unique_destination(dest: Path) -> Path:
    """Avoid overwriting an existing file by appending a counter."""
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def organize(
    target: Path,
    ext_map: dict[str, str],
    known_folders: set[str],
    dry_run: bool,
    by_date: bool,
    include_incomplete: bool,
) -> tuple[int, int]:
    moved = 0
    skipped = 0

    for entry in sorted(target.iterdir()):
        if entry.is_dir():
            continue
        if entry.name.startswith("."):
            skipped += 1
            continue
        if entry.suffix.lower() in INCOMPLETE_SUFFIXES and not include_incomplete:
            skipped += 1
            continue
        if entry.parent.name in known_folders:
            skipped += 1
            continue

        category = ext_map.get(entry.suffix.lower(), OTHERS)
        dest_dir = target / category
        if by_date:
            month = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m")
            dest_dir = dest_dir / month

        dest_path = unique_destination(dest_dir / entry.name)

        if dry_run:
            print(f"[dry-run] {entry.name} -> {dest_path.relative_to(target)}")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(dest_path))
            print(f"{entry.name} -> {dest_path.relative_to(target)}")
        moved += 1

    return moved, skipped


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default=str(Path.home() / "Downloads"),
        help="Folder to organize (default: ~/Downloads)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be moved without moving anything",
    )
    parser.add_argument(
        "--by-date",
        action="store_true",
        help="Further group each category into YYYY-MM subfolders by modified date",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON file overriding/extending the default category->extensions map",
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Also move in-progress download files (.crdownload, .part, etc.)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = Path(args.path).expanduser().resolve()

    if not target.is_dir():
        print(f"Error: '{target}' is not a directory.", file=sys.stderr)
        return 1

    categories = load_categories(args.config)
    ext_map = build_extension_map(categories)
    known_folders = set(categories.keys()) | {OTHERS}

    print(f"Organizing: {target}{' (dry run)' if args.dry_run else ''}")
    moved, skipped = organize(
        target,
        ext_map,
        known_folders,
        args.dry_run,
        args.by_date,
        args.include_incomplete,
    )
    print(f"\nDone. {moved} file(s) {'would be ' if args.dry_run else ''}moved, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
