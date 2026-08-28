#!/usr/bin/env python3
"""Organize downloaded academic paper PDFs: rename by Author_Year_Title and
sort into folders either by keyword category or by author.

Usage:
    python organize_papers.py --keywords keywords.json [--path PATH] [--dry-run]
                               [--no-rename] [--recursive]
                               [--uncategorized-folder NAME]

    python organize_papers.py --by-author [--path PATH] [--dry-run]
                               [--no-rename] [--recursive]

    python organize_papers.py --title-only [--path PATH] [--dry-run]
                               [--recursive] [--papers-folder NAME]

Requires the 'pypdf' package:
    pip install pypdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
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
# Reserved device names that Windows refuses to use as a file/folder name.
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
    f"LPT{i}" for i in range(1, 10)
}
# Unicode categories that are control/formatting/unassigned characters -
# these can turn up in text extracted from PDFs with broken font encodings
# (e.g. CID fonts without a ToUnicode map) and are invalid in Windows paths.
_UNSAFE_UNICODE_CATEGORIES = {"Cc", "Cf", "Co", "Cs", "Cn"}


def sanitize(text: str, max_len: int | None = None) -> str:
    text = "".join(ch for ch in text if unicodedata.category(ch) not in _UNSAFE_UNICODE_CATEGORIES)
    text = INVALID_CHARS.sub("", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = text.strip("_. ")
    if max_len:
        text = text[:max_len].rstrip("_")
    if not text or text.upper() in WINDOWS_RESERVED_NAMES:
        return "unknown"
    return text


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
        if not (10 <= len(line) <= 200) or line.isdigit():
            continue
        # Skip lines that are mostly garbled/control characters, which can
        # happen with PDFs that use broken font encodings.
        letters = sum(ch.isalpha() for ch in line)
        if letters / len(line) < 0.5:
            continue
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
    def __init__(self, title: str, author: str, year: str, text_sample: str,
                 title_guessed: bool, author_guessed: bool, year_guessed: bool):
        self.title = title
        self.author = author
        self.year = year
        self.text_sample = text_sample
        self.title_guessed = title_guessed
        self.author_guessed = author_guessed
        self.year_guessed = year_guessed
        self.guessed = title_guessed or author_guessed or year_guessed


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

    title_guessed = False
    title = meta_title if meta_title.lower() not in PLACEHOLDER_TITLES else ""
    if not title or len(title) < 5:
        guessed_title = guess_title_from_text(text_sample)
        if guessed_title:
            title = guessed_title
            title_guessed = True
        else:
            title = pdf_path.stem
            title_guessed = True

    if meta_author.lower() in PLACEHOLDER_AUTHORS:
        meta_author = ""
    author = guess_author_surname(meta_author)
    author_guessed = not author
    if author_guessed:
        author = "UnknownAuthor"

    year = guess_year(meta_date_str, text_sample)
    year_guessed = not year
    if year_guessed:
        year = "UnknownYear"

    return PaperInfo(title=title, author=author, year=year, text_sample=text_sample,
                      title_guessed=title_guessed, author_guessed=author_guessed, year_guessed=year_guessed)


def build_filename(info: PaperInfo, original_suffix: str) -> str:
    author = sanitize(info.author, 40)
    year = sanitize(info.year, 10)
    title = sanitize(info.title, MAX_TITLE_LEN)
    return f"{author}_{year}_{title}{original_suffix}"


def build_title_only_filename(info: PaperInfo, original_suffix: str) -> str:
    return f"{sanitize(info.title, MAX_TITLE_LEN)}{original_suffix}"


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
    group.add_argument("--title-only", action="store_true",
                        help="Don't sort into categories - gather every paper into one folder "
                             "and rename it to just its title")
    parser.add_argument("--dry-run", action="store_true",
                         help="Show what would happen without moving/renaming anything")
    parser.add_argument("--no-rename", action="store_true",
                         help="Only sort into folders; keep original filenames")
    parser.add_argument("--recursive", action="store_true",
                         help="Also look inside subfolders (e.g. if papers already sit in a "
                              "Documents folder from organize_downloads.py)")
    parser.add_argument("--uncategorized-folder", default=UNCATEGORIZED_DEFAULT,
                         help=f"Folder name for papers matching no keyword (default: {UNCATEGORIZED_DEFAULT})")
    parser.add_argument("--papers-folder", default="Papers",
                         help="Folder name to gather papers into when using --title-only (default: Papers)")
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser().resolve()
    if not target.is_dir():
        print(f"Error: '{target}' is not a directory.", file=sys.stderr)
        return 1

    keywords = load_keywords(args.keywords) if args.keywords else None

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

        if args.title_only:
            category = args.papers_folder
        elif args.by_author:
            category = sanitize(info.author, 40)
        else:
            category = classify(info, keywords, args.uncategorized_folder)

        if args.recursive and pdf_path.parent.name == category:
            # Already sitting in its correct category folder from a previous run.
            skipped += 1
            continue

        if args.no_rename:
            new_name = pdf_path.name
        elif args.title_only:
            new_name = build_title_only_filename(info, pdf_path.suffix)
        else:
            new_name = build_filename(info, pdf_path.suffix)
        dest_dir = target / category
        dest_path = unique_destination(dest_dir / new_name)
        relevant_guess = info.title_guessed if args.title_only else info.guessed
        note = "  [!] guessed - please double-check" if relevant_guess and not args.no_rename else ""

        if args.dry_run:
            print(f"[dry-run] {pdf_path.name} -> {dest_path.relative_to(target)}{note}")
            processed += 1
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                pdf_path.rename(dest_path)
            except OSError as exc:
                print(f"[skip] {pdf_path.name}: could not move it ({exc})")
                failed += 1
                continue
            print(f"{pdf_path.name} -> {dest_path.relative_to(target)}{note}")
            processed += 1

    print(f"\nDone. {processed} paper(s) {'would be ' if args.dry_run else ''}processed, "
          f"{skipped} already organized, {failed} failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
