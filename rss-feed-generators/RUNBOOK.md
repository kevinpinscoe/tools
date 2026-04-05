# RUNBOOK — rss-feed-generators

How and when the RSS feed generators run on this system (Fedora Linux 42).

## Schedule

Each generator runs every 6 hours starting at 01:30 local time:
**01:30 — 07:30 — 13:30 — 19:30**

## Systemd units

Each generator has a `.service` + `.timer` pair installed in `/etc/systemd/system/`.

| Generator | Timer | Service |
|-----------|-------|---------|
| pinboard-recent | `rss-feed-pinboard-recent.timer` | `rss-feed-pinboard-recent.service` |

## Checking status

```bash
# Next scheduled runs for all feed generators
systemctl list-timers 'rss-feed-*'

# Status of a specific timer
systemctl status rss-feed-pinboard-recent.timer

# Logs for a specific generator (most recent run)
journalctl -u rss-feed-pinboard-recent.service -e

# Follow logs in real time
journalctl -u rss-feed-pinboard-recent.service -f
```

## Running manually

```bash
# Trigger a generator immediately (without waiting for the timer)
sudo systemctl start rss-feed-pinboard-recent.service

# Or run the script directly for testing (writes to /tmp to avoid needing sudo)
python3 pinboard-recent/pinboard-recent-generator.py /tmp/test-feed.xml
```

## Adding a new generator

1. Create the script at `{{SITE-NAME}}/{{SITE-NAME}}-generator.py`.
2. Create `/etc/systemd/system/rss-feed-{{SITE-NAME}}.service`:

```ini
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

3. Create `/etc/systemd/system/rss-feed-{{SITE-NAME}}.timer`:

```ini
[Unit]
Description=Run RSS feed generator: {{SITE-NAME}} every 6 hours

[Timer]
OnCalendar=*-*-* 01/6:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

4. Enable and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rss-feed-{{SITE-NAME}}.timer
```

## Output files

Feed XML is written to `/var/www/html/feed/{{SITE-NAME}}/index.xml` (root-owned). The service runs as root so no `sudo` is needed in the unit file.
