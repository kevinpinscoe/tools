#!/usr/bin/env python3
"""Fetch pinboard.in/recent/ and write an RSS 2.0 feed to disk.

Pinboard does not expose a public RSS feed for /recent/. This script
scrapes the inline JavaScript `bmarks` object that the page embeds and
converts it to a standard RSS 2.0 feed.
"""

import json
import os
import re
import sys
import urllib.request
import xml.dom.minidom
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

SOURCE_URL = "https://pinboard.in/recent/"
DEFAULT_OUTPUT = "/var/www/html/feed/pinboard-recent/index.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; rss-feed-generator/1.0)"
}

# Matches lines like: bmarks[1234567890] = { ... };
BMARKS_RE = re.compile(r"bmarks\[\d+\]\s*=\s*(\{.*?\});", re.DOTALL)


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_bmarks(html: str) -> list:
    items = []
    for match in BMARKS_RE.finditer(html):
        try:
            items.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    # Sort newest-first by created timestamp
    items.sort(key=lambda b: b.get("created", ""), reverse=True)
    return items


def rfc2822(iso: str) -> str:
    """Convert an ISO 8601 UTC timestamp to RFC 2822 for RSS."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return format_datetime(dt)


def build_description(bmark: dict) -> str:
    parts = []
    if bmark.get("description"):
        parts.append(bmark["description"])
    tags = bmark.get("tags", [])
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if bmark.get("bookmark_url"):
        parts.append(bmark["bookmark_url"])
    return "\n".join(parts)


def build_rss(bmarks: list) -> Element:
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "Pinboard – Recent"
    SubElement(channel, "link").text = SOURCE_URL
    SubElement(channel, "description").text = "Recent public bookmarks from pinboard.in"
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(timezone.utc)
    )

    for bmark in bmarks:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = bmark.get("title") or bmark.get("url", "")
        SubElement(item, "link").text = bmark.get("url", "")
        if bmark.get("bookmark_url"):
            SubElement(item, "guid", isPermaLink="true").text = bmark["bookmark_url"]
        if bmark.get("created"):
            SubElement(item, "pubDate").text = rfc2822(bmark["created"])
        if bmark.get("author"):
            SubElement(item, "author").text = bmark["author"]
        SubElement(item, "description").text = build_description(bmark)

    return rss


def write_feed(rss_element: Element, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = tostring(rss_element, encoding="unicode")
    pretty = xml.dom.minidom.parseString(raw).toprettyxml(
        indent="  ", encoding="utf-8"
    )
    with open(path, "wb") as fh:
        fh.write(pretty)


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT
    html = fetch_page(SOURCE_URL)
    bmarks = parse_bmarks(html)
    if not bmarks:
        print("ERROR: no bmarks entries found — page structure may have changed", file=sys.stderr)
        sys.exit(1)
    rss = build_rss(bmarks)
    write_feed(rss, output)
    print(f"Wrote {len(bmarks)} items → {output}")


if __name__ == "__main__":
    main()
