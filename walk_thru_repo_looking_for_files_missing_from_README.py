#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HTML_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def extract_link_targets(readme_path: Path) -> set[Path]:
    """
    Return a set of resolved local file paths linked from the README.
    Only local links are considered. Anchors, mailto, and URLs are ignored.
    """
    try:
        content = readme_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = readme_path.read_text(encoding="utf-8", errors="replace")

    targets: set[Path] = set()
    readme_dir = readme_path.parent

    raw_targets = []
    raw_targets.extend(MARKDOWN_LINK_RE.findall(content))
    raw_targets.extend(HTML_HREF_RE.findall(content))

    for raw in raw_targets:
        target = raw.strip()

        if not target:
            continue

        # Ignore URLs and anchors
        lowered = target.lower()
        if lowered.startswith(("http://", "https://", "mailto:", "#")):
            continue

        # Strip optional title in markdown links: (file.md "title")
        if " " in target and not target.startswith("<"):
            first_part = target.split(" ", 1)[0]
            if first_part:
                target = first_part

        # Remove wrapping angle brackets: (<file.md>)
        target = target.strip("<>")

        # Drop anchor/query
        target = target.split("#", 1)[0]
        target = target.split("?", 1)[0]

        if not target:
            continue

        target = unquote(target)

        resolved = (readme_dir / target).resolve()
        targets.add(resolved)

    return targets


def main() -> int:
    root = Path.cwd().resolve()
    missing_found = False

    for md_file in sorted(root.rglob("*.md")):
        if not md_file.is_file():
            continue

        # Skip the README itself
        if md_file.name == "README.md":
            continue

        readme_path = md_file.parent / "README.md"

        # Per your requirement: if README.md does not exist, skip and do not report
        if not readme_path.is_file():
            continue

        linked_targets = extract_link_targets(readme_path)

        if md_file.resolve() not in linked_targets:
            missing_found = True
            print(f"MISSING {md_file.name} from {readme_path}")

    return 1 if missing_found else 0


if __name__ == "__main__":
    sys.exit(main())