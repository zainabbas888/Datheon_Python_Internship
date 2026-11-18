#!/usr/bin/env python3
"""
organizer.py - Automated File Organizer & Cleanup Utility

Sorts files in a directory (e.g. Downloads) into category subfolders
based on file extension, safely handling name collisions and
permission errors.

Usage:
    python organizer.py                      # organize ~/Downloads
    python organizer.py "C:/Users/me/Downloads"
    python organizer.py ./folder --dry-run   # preview only, no changes
    python organizer.py ./folder --recursive # also sort files in subfolders
"""

import argparse
import logging
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# Extension -> category mapping
# --------------------------------------------------------------------------
CATEGORIES = {
    "Documents": {
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx",
        ".ppt", ".pptx", ".csv", ".md", ".epub",
    },
    "Images": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff",
        ".ico", ".heic",
    },
    "Videos": {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    },
    "Archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
    },
    "Code": {
        ".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h",
        ".cs", ".go", ".rs", ".php", ".rb", ".sh", ".json", ".xml", ".sql",
        ".ipynb",
    },
}
DEFAULT_CATEGORY = "Others"

# Build a fast reverse lookup: ".pdf" -> "Documents"
EXT_TO_CATEGORY = {
    ext: category for category, exts in CATEGORIES.items() for ext in exts
}
CATEGORY_FOLDERS = set(CATEGORIES) | {DEFAULT_CATEGORY}

# Files we should never touch
SKIP_NAMES = {Path(__file__).name, "organizer.log", "desktop.ini", "thumbs.db"}
# Partial/in-progress downloads
SKIP_EXTENSIONS = {".crdownload", ".part", ".tmp", ".download"}

logger = logging.getLogger("organizer")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def setup_logging(log_file: Path | None) -> None:
    """Log to console and (optionally) to a file."""
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s",
                            datefmt="%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError as exc:
            logger.warning("Could not create log file %s: %s", log_file, exc)


def get_category(path: Path) -> str:
    return EXT_TO_CATEGORY.get(path.suffix.lower(), DEFAULT_CATEGORY)


def unique_destination(dest: Path) -> Path:
    """Return a non-colliding path: file.txt -> file (1).txt -> file (2).txt"""
    if not dest.exists():
        return dest
    counter = 1
    while True:
        candidate = dest.with_name(f"{dest.stem} ({counter}){dest.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def iter_files(directory: Path, recursive: bool, root: Path):
    """Yield file paths using os.scandir, skipping category folders."""
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        # Never descend into our own category folders
                        if recursive and not (
                            directory == root and entry.name in CATEGORY_FOLDERS
                        ):
                            yield from iter_files(Path(entry.path), recursive, root)
                    elif entry.is_file(follow_symlinks=False):
                        yield Path(entry.path)
                except PermissionError:
                    logger.warning("Permission denied (skipped): %s", entry.path)
                except OSError as exc:
                    logger.warning("Cannot inspect %s: %s", entry.path, exc)
    except PermissionError:
        logger.warning("Permission denied reading directory: %s", directory)
    except FileNotFoundError:
        logger.error("Directory not found: %s", directory)


# --------------------------------------------------------------------------
# Core logic
# --------------------------------------------------------------------------
def organize(root: Path, recursive: bool = False, dry_run: bool = False) -> dict:
    stats = {"moved": 0, "skipped": 0, "errors": 0, "renamed": 0}
    per_category = Counter()

    # Materialize the list first so moving files doesn't affect scanning
    files = list(iter_files(root, recursive, root))
    logger.info("Found %d file(s) to inspect in %s", len(files), root)

    for src in files:
        name_lower = src.name.lower()

        if (name_lower in SKIP_NAMES
                or src.name.startswith(".")
                or src.suffix.lower() in SKIP_EXTENSIONS):
            stats["skipped"] += 1
            logger.info("SKIP    %s", src.name)
            continue

        category = get_category(src)
        target_dir = root / category

        # Already sitting in the right place (e.g. root/Images/x.png)
        if src.parent == target_dir:
            stats["skipped"] += 1
            continue

        try:
            if not dry_run:
                target_dir.mkdir(exist_ok=True)

            dest = unique_destination(target_dir / src.name)
            renamed = dest.name != src.name

            if dry_run:
                logger.info("DRY-RUN %s -> %s/%s", src.name, category, dest.name)
            else:
                shutil.move(str(src), str(dest))
                logger.info("MOVED   %s -> %s/%s", src.name, category, dest.name)

            stats["moved"] += 1
            per_category[category] += 1
            if renamed:
                stats["renamed"] += 1

        except PermissionError:
            stats["errors"] += 1
            logger.error("Permission denied (file may be open/locked): %s", src)
        except FileExistsError:
            stats["errors"] += 1
            logger.error("Destination already exists: %s", src)
        except shutil.Error as exc:
            stats["errors"] += 1
            logger.error("Move failed for %s: %s", src, exc)
        except OSError as exc:
            stats["errors"] += 1
            logger.error("OS error on %s: %s", src, exc)

    stats["per_category"] = per_category
    return stats


def print_summary(stats: dict, dry_run: bool) -> None:
    line = "=" * 46
    print(f"\n{line}")
    print(" EXECUTION SUMMARY" + (" (DRY RUN)" if dry_run else ""))
    print(line)
    for category, count in sorted(stats["per_category"].items()):
        print(f" {category:<14} {count:>5} file(s)")
    print("-" * 46)
    print(f" {'Total moved':<14} {stats['moved']:>5}")
    print(f" {'Renamed':<14} {stats['renamed']:>5}  (name collisions)")
    print(f" {'Skipped':<14} {stats['skipped']:>5}")
    print(f" {'Errors':<14} {stats['errors']:>5}")
    print(line)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Organize files into category folders by extension.")
    parser.add_argument("directory", nargs="?",
                        default=str(Path.home() / "Downloads"),
                        help="Directory to organize (default: ~/Downloads)")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Also organize files inside subfolders")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Show what would happen without moving anything")
    parser.add_argument("--no-log-file", action="store_true",
                        help="Do not write organizer.log")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        return 1

    log_file = None if (args.no_log_file or args.dry_run) else root / "organizer.log"
    setup_logging(log_file)

    logger.info("Starting organizer on %s%s", root,
                " [dry run]" if args.dry_run else "")
    stats = organize(root, recursive=args.recursive, dry_run=args.dry_run)
    print_summary(stats, args.dry_run)
    return 0 if stats["errors"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())