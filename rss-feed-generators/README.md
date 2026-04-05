# rss-feed-generators

RSS feed generators for websites that don't offer one natively. Each generator is a single self-contained Python script that fetches data from a site's public API or page, converts it to a valid RSS 2.0 feed, and writes it to `/var/www/html/feed/{{SITE-NAME}}/index.xml`.

See [RUNBOOK.md](RUNBOOK.md) for scheduling, systemd unit details, and operational commands.

## Generators

| Script | Source | Feed output |
|--------|--------|-------------|
| `pinboard-recent/pinboard-recent-generator.py` | [pinboard.in/recent/](https://pinboard.in/recent/) (scraped) | `/var/www/html/feed/pinboard-recent/index.xml` |

## Layout

Each generator lives in its own subdirectory named after the site:

```
rss-feed-generators/
  {{SITE-NAME}}/
    {{SITE-NAME}}-generator.py   ← the script
    CLAUDE.md                    ← site-specific notes
```

## Dependencies

Python 3.7+ standard library only — no `pip install` required.
