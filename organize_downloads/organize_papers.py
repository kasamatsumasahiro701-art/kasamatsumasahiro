#!/usr/bin/env python3
"""Organize downloaded academic paper PDFs: rename by Author_Year_Title and
sort into folders either by keyword category or by author.

Usage:
    python organize_papers.py --keywords keywords.json [--path PATH] [--dry-run]
                               [--no-rename] [--recursive]
                               [--uncategorized-folder NAME]

    python organize_papers.py --by-author [--path PATH] [--dry-run]
                               [--no-rename] [--recursive]

Requires the 'pypdf' package:
    pip install pypdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print(
        "Error: the 'pypdf' package is required.\n"
        "Install it with:  pip install pypdf   (or: pip3 install pypdf)",
        file=sys.stderr,
    )
    raise SystemExit(1)

UNCATEGORIZED_DEFAULT = "Uncategorized"
MAX_TITLE_LEN = 80
INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def sanitize(text: str, max_len: int | None = None) -> str:
    text = INVALID_CHARS.sub("", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = text.strip("_.")
    if max_len:
        text = text[:max_len].rstrip("_")
    return text or "unknown"


def guess_author_surname(raw_author: str | None) -> str | None:
    if not raw_author:
        return None
    first = re.split(r"[;,]|\band\b", raw_author, maxsplit=1)[0].strip()
    if not first:
        return None
    parts = first.split()
    return parts[-1] if parts else None


def guess_title_from_text(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if 10 <= len(line) <= 200 and not line.isdigit():
            return line
    return None


PLACEHOLDER_TITLES = {"untitled", "unknown", "document", "no title", ""}
PLACEHOLDER_AUTHORS = {"anonymous", "unknown", ""}


def guess_year(metadata_date: str | None, text: str) -> str | None:
    # Prefer a year mentioned in the paper's own text over the PDF's
    # "creation date" metadata, which usually just reflects when the file
    # was generated/downloaded rather than when the paper was published.
    m = YEAR_RE.search(text)
    if m:
        return m.group(0)
    if metadata_date:
        m = YEAR_RE.search(metadata_date)
        if m:
            return m.group(0)
    return None


class PaperInfo:
    def __init__(self, title: str, author: str, year: str, text_sample: str, guessed: bool):
        self.title = title
        self.author = author
        self.year = year
        self.text_sample = text_sample
        self.guessed = guessed


def extract_paper_info(pdf_path: Path) -> PaperInfo:
    reader = PdfReader(str(pdf_path))
    meta = reader.metadata or {}
    meta_title = (getattr(meta, "title", None) or "").strip()
    meta_author = (getattr(meta, "author", None) or "").strip()
    meta_date = getattr(meta, "creation_date", None)
    meta_date_str = str(meta_date) if meta_date else None

    text_sample = ""
    for page in reader.pages[:3]:
        try:
            text_sample += page.extract_text() or ""
        except Exception:
            continue

    guessed = False
    title = meta_title if meta_title.lower() not in PLACEHOLDER_TITLES else ""
    if not title or len(title) < 5:
        guessed_title = guess_title_from_text(text_sample)
        if guessed_title:
            title = guessed_title
            guessed = True
        else:
            title = pdf_path.stem
            guessed = True

    if meta_author.lower() in PLACEHOLDER_AUTHORS:
        meta_author = ""
    author = guess_author_surname(meta_author)
    if not author:
        guessed = True
        author = "UnknownAuthor"

    year = guess_year(meta_date_str, text_sample)
    if not year:
        guessed = True
        year = "UnknownYear"

    return PaperInfo(title=title, author=author, year=year, text_sample=text_sample, guessed=guessed)


def build_filename(info: PaperInfo, original_suffix: str) -> str:
    author = sanitize(info.author, 40)
    year = sanitize(info.year, 10)
    title = sanitize(info.title, MAX_TITLE_LEN)
    return f"{author}_{year}_{title}{original_suffix}"


def load_keywords(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("keywords file must be a JSON object of {category: [keywords]}")
    return data


def classify(info: PaperInfo, keywords: dict[str, list[str]], uncategorized: str) -> str:
    haystack = f"{info.title}\n{info.text_sample}".lower()
    for category, terms in keywords.items():
        for term in terms:
            if term.lower() in haystack:
                return category
    return uncategorized


def unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def iter_pdfs(target: Path, recursive: bool):
    pattern = "**/*.pdf" if recursive else "*.pdf"
    for entry in sorted(target.glob(pattern)):
        if entry.is_file():
            yield entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(Path.home() / "Downloads"),
                         help="Folder containing the PDF papers (default: ~/Downloads)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--keywords",
                        help="Path to a JSON file mapping category -> list of keywords "
                             "(see keywords.example.json)")
    group.add_argument("--by-author", action="store_true",
                        help="Sort into one folder per author's surname instead of by keyword")
    parser.add_argument("--dry-run", action="store_true",
                         help="Show what would happen without moving/renaming anything")
    parser.add_argument("--no-rename", action="store_true",
                         help="Only sort into folders; keep original filenames")
    parser.add_argument("--recursive", action="store_true",
                         help="Also look inside subfolders (e.g. if papers already sit in a "
                              "Documents folder from organize_downloads.py)")
    parser.add_argument("--uncategorized-folder", default=UNCATEGORIZED_DEFAULT,
                         help=f"Folder name for papers matching no keyword (default: {UNCATEGORIZED_DEFAULT})")
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser().resolve()
    if not target.is_dir():
        print(f"Error: '{target}' is not a directory.", file=sys.stderr)
        return 1

    keywords = None if args.by_author else load_keywords(args.keywords)

    print(f"Scanning: {target}{' (dry run)' if args.dry_run else ''}")
    processed = 0
    skipped = 0
    failed = 0

    for pdf_path in iter_pdfs(target, args.recursive):
        try:
            info = extract_paper_info(pdf_path)
        except Exception as exc:
            print(f"[skip] {pdf_path.name}: could not read PDF ({exc})")
            failed += 1
            continue

        if args.by_author:
            category = sanitize(info.author, 40)
        else:
            category = classify(info, keywords, args.uncategorized_folder)

        if args.recursive and pdf_path.parent.name == category:
            # Already sitting in its correct category folder from a previous run.
            skipped += 1
            continue

        new_name = pdf_path.name if args.no_rename else build_filename(info, pdf_path.suffix)
        dest_dir = target / category
        dest_path = unique_destination(dest_dir / new_name)
        note = "  [!] title/author/year guessed - please double-check" if info.guessed and not args.no_rename else ""

        if args.dry_run:
            print(f"[dry-run] {pdf_path.name} -> {dest_path.relative_to(target)}{note}")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            pdf_path.rename(dest_path)
            print(f"{pdf_path.name} -> {dest_path.relative_to(target)}{note}")
        processed += 1

    print(f"\nDone. {processed} paper(s) {'would be ' if args.dry_run else ''}processed, "
          f"{skipped} already organized, {failed} failed to read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
