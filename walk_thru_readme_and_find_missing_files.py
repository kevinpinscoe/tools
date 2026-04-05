#!/usr/bin/env python3
"""
check_readme_links.py

Walk from the current directory downward, find every README.md,
extract local markdown links that point to .md files, and report any
missing targets.

Usage:
    python3 check_readme_links.py

Optional:
    python3 check_readme_links.py /some/start/path
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r'(?<!\!)\[[^\]]+\]\(([^)]+)\)')


def normalize_target(raw_target: str) -> str:
    target = raw_target.strip()

    if " " in target and not target.startswith("<"):
        first_part = target.split(" ", 1)[0]
        if first_part.endswith(".md") or ".md#" in first_part:
            target = first_part

    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()

    target = unquote(target)
    target = target.split("#", 1)[0]

    return target


def is_local_markdown_link(target: str) -> bool:
    lowered = target.lower()

    if not target:
        return False
    if lowered.startswith(("http://", "https://", "mailto:", "ftp://")):
        return False
    if lowered.startswith("#"):
        return False

    return lowered.endswith(".md")


def find_missing_links(readme_path: Path) -> list[tuple[str, str, Path]]:
    """
    Return a list of:
      (readme_relative_path, raw_target, resolved_missing_path)
    """
    missing: list[tuple[str, str, Path]] = []

    try:
        content = readme_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = readme_path.read_text(encoding="utf-8", errors="replace")

    for match in LINK_RE.finditer(content):
        raw_target = match.group(1)
        target = normalize_target(raw_target)

        if not is_local_markdown_link(target):
            continue

        resolved = (readme_path.parent / target).resolve()

        if not resolved.exists():
            missing.append((str(readme_path), raw_target, resolved))

    return missing


def main() -> int:
    start_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()

    if not start_path.exists():
        print(f"ERROR: start path does not exist: {start_path}", file=sys.stderr)
        return 2

    readmes = sorted(start_path.rglob("README.md"))

    total_readmes = 0
    total_missing = 0

    for readme in readmes:
        total_readmes += 1
        missing = find_missing_links(readme)

        for readme_name, raw_target, resolved in missing:
            total_missing += 1
            try:
                readme_display = str(Path(readme_name).resolve().relative_to(start_path))
            except ValueError:
                readme_display = readme_name

            print(f"MISSING: {readme_display} -> {raw_target}")
            print(f"         Resolved to: {resolved}")

    print("\nSummary")
    print(f"  README.md files checked: {total_readmes}")
    print(f"  Missing markdown links: {total_missing}")

    return 1 if total_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())