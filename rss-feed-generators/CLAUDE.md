# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

RSS feed generators for websites that don't offer one natively. Each generator is a single-file Python script that fetches data from a site's public API or page, converts it to a valid RSS 2.0 feed, and writes it to `/var/www/html/feed/<source>/index.xml`. No external dependencies — Python 3.7+ stdlib only.

## Output location

Feed XML files go to `/var/www/html/feed/{{SITE-NAME}}/index.xml`, which is root-owned. Scripts must run with `sudo -A` (or as root via cron) to write there. Use a custom path (e.g. `/tmp/`) for testing without elevated privileges.

## Running and testing

```bash
# Smoke-test: write to a temp file to avoid needing sudo
python3 {{SITE-NAME}}/{{SITE-NAME}}-generator.py /tmp/test-feed.xml

# Validate well-formed XML output
python3 -c "import xml.etree.ElementTree as ET; ET.parse('/tmp/test-feed.xml'); print('OK')"

# Production run (requires root write access to /var/www/html/feed/)
sudo -A python3 {{SITE-NAME}}/{{SITE-NAME}}-generator.py
```

## Conventions

- Scripts use `#!/usr/bin/env python3` with stdlib only — no `pip install` required.
- Each script accepts an optional positional argument for the output path; default is `/var/www/html/feed/<source>/index.xml`.
- Auth tokens/credentials are read from `$HOME/.config/`; never hardcoded.
- `os.makedirs(..., exist_ok=True)` is called before writing to ensure the output directory exists.

## Architecture pattern

Each generator follows the same four-function shape:

```
fetch_*(url) → raw data
build_description(item) → str
build_rss(items) → xml.etree.ElementTree.Element
write_feed(element, path) → None  # minidom pretty-print → UTF-8 file
main() → parses argv[1] for output path, calls the above in sequence
```

## Adding a new generator

1. Create a `{{SITE-NAME}}/` subdirectory here and a matching one under `/var/www/html/feed/`.
2. Place the script at `{{SITE-NAME}}/{{SITE-NAME}}-generator.py`.
3. Duplicate an existing script and change:
   - `SOURCE_URL` — the JSON/API endpoint to fetch
   - Channel metadata in `build_rss()` — `<title>`, `<link>`, `<description>`
   - Item field mapping in `build_rss()` to match the new source's schema
   - `DEFAULT_OUTPUT` — the output path under `/var/www/html/feed/`
4. Add a `{{SITE-NAME}}/CLAUDE.md` documenting any site-specific scraping details.

## Systemd deployment (Fedora Linux 42)

This system uses systemd timers, not cron. Each generator has a `.service` + `.timer` pair installed in `/etc/systemd/system/`. Timers run every 6 hours starting at 01:30 local time (01:30, 07:30, 13:30, 19:30).

Unit file naming convention: `rss-feed-{{SITE-NAME}}.service` / `rss-feed-{{SITE-NAME}}.timer`

```ini
# /etc/systemd/system/rss-feed-{{SITE-NAME}}.service
[Unit]
Description=RSS feed generator: {{SITE-NAME}}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /home/kinscoe/tools/rss-feed-generators/{{SITE-NAME}}/{{SITE-NAME}}-generator.py
StandardOutput=journal
StandardError=journal
```

```ini
# /etc/systemd/system/rss-feed-{{SITE-NAME}}.timer
[Unit]
Description=Run RSS feed generator: {{SITE-NAME}} every 6 hours

[Timer]
OnCalendar=*-*-* 01/6:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

After installing new unit files:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rss-feed-{{SITE-NAME}}.timer
```

Check scheduled runs:

```bash
systemctl list-timers 'rss-feed-*'
```

View logs:

```bash
journalctl -u rss-feed-{{SITE-NAME}}.service
```
