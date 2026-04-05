# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A single-file Python script (`./pinboard-recent-generator.py`) that scrapes `https://pinboard.in/recent/` and writes an RSS 2.0 feed to `/var/www/html/feed/pinboard-recent/index.xml`. No external dependencies — Python 3.7+ stdlib only.

Pinboard does not expose a public RSS feed for `/recent/`, so the script parses the inline JavaScript `bmarks` object embedded in the page HTML.

## Running and testing

```bash
# Smoke-test: write to a temp file to avoid needing sudo
python3 pinboard-recent-generator.py /tmp/pinboard-test.xml

# Validate well-formed XML
python3 -c "import xml.etree.ElementTree as ET; ET.parse('/tmp/pinboard-test.xml'); print('OK')"

# Production run (requires root write access)
sudo -A python3 pinboard-recent-generator.py
```

## Systemd deployment

Managed by `rss-feed-pinboard-recent.timer` / `rss-feed-pinboard-recent.service` in `/etc/systemd/system/`. Runs every 6 hours starting at 01:30 local time.

```bash
systemctl list-timers rss-feed-pinboard-recent.timer
journalctl -u rss-feed-pinboard-recent.service
```

## How the scrape works

The page embeds bookmark data as inline JS in this pattern:

```javascript
bmarks[1234567890] = { "title": "...", "url": "...", "tags": [...], ... };
```

The script uses a regex (`bmarks\[\d+\]\s*=\s*(\{.*?\});` with DOTALL) to extract each JSON object. If zero entries are found, the script exits with an error — this is the early-warning signal that Pinboard changed its page structure.

## bmarks field reference

| Field | Type | Notes |
|-------|------|-------|
| `title` | str | Bookmark title |
| `url` | str | Target URL |
| `description` | str | Optional extended text |
| `tags` | list[str] | May be empty |
| `created` | str | ISO 8601 UTC (`Z` suffix) |
| `author` | str | Pinboard username |
| `bookmark_url` | str | `https://pinboard.in/u:user/b:id` — used as `<guid>` |
| `private` | int | 0 or 1; private bookmarks won't appear on `/recent/` |
