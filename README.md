# Tools

This repository collects small tools and automation scripts I have created for Linux, macOS, and Raspberry Pi systems.

Some of these scripts are also referenced from my playbook, so I keep them here in one place for versioning, reuse, and maintenance.

Most of the top-level files are standalone utilities. The main structured subproject is [`rss-feed-generators/`](./rss-feed-generators), which contains self-contained RSS feed generator scripts and related notes.

## Top-level scripts

- `gitcf` is a Python TUI that lists every untracked or modified file in the current git repo, lets you multi-select via an urwid checkbox picker, then commits (one batch commit if a memo is given, one per file otherwise) and pushes `HEAD` to `origin`.
- `ddir` / `ddir.py` compares two directories recursively, reporting missing files and running side-by-side diffs on files that differ.
- `decode-tldr-tracking-links.sh` decodes TLDR newsletter tracking links so the underlying destination URL is easier to inspect.
- `find-in-ai.sh` searches Markdown notes in the current tree with `rg`.
- `find-obsidian-vaults` finds Obsidian vaults under `$HOME` by locating `.obsidian` directories.
- `jsonfmt` safely formats JSON and JSONC files in place.
- `pause` is a compiled Go binary that sleeps for a specified number of seconds, displaying a live countdown status line on stderr; drop it into scripts wherever `sleep N` would leave the user wondering how long remains.
- `myclaude` launches `claude` inside a named `screen` session with disk logging, and writes a cleaned `.txt` sibling next to the raw `.log` when the session exits (or via `myclaude --clean <log-file>` after a detach). Logs land at `<LOG_ROOT>/CLAUDE/_<REL>/<timestamp>.log`, where `_<REL>` encodes the cwd `myclaude` was launched from (e.g. `_.environment`, `_tools`, `_Projects-foo`, `_home`). Exports `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` so Claude Code renders into the terminal's native scrollback instead of the fullscreen alt-screen — yields significantly cleaner captured logs. Generates a per-session screenrc that disables screen's `smcup/rmcup` (alt-screen) sequences so host-terminal scrollback works: mouse-wheel scrolls Ghostty's native scrollback directly, or tmux's pane scrollback when nested under a tmux with `mouse on`. Requires Claude Code >= 2.1.132 ([release notes](https://code.claude.com/docs/en/changelog#2-1-132)); auto-runs `claude update` and re-checks if the installed version is older.
- `claude-log-view` is a curses TUI for browsing `myclaude` logs; navigates `_<REL>` cwd-directories under `<LOG_ROOT>/CLAUDE/` and views logs through an ANSI-stripping pipeline.
- `obsidian-backup-this-vault.sh` creates timestamped backups of the current Obsidian vault and prunes older archives.
- `ticket` is a Python TUI workspace manager for ticket-based development; clones selected repos into `~/Projects/workspaces/<TICKET>/` on a `kevini/<TICKET>` branch and opens a tmux + VS Code session.
- `pull-requests` scans all git repos under a root directory (default: `~/Projects`) for open GitHub PRs authored by `$GITHUB_USER`; supports whitelist/blacklist filtering via `~/.config/pull-request/`.
- `check-git-branch` is a compiled Go binary that scans git repos under `$HOME` (or `$CHECK_GIT_BRANCH`) and reports any that are not on their default branch or have non-default local branches left over from previous work; silent when everything is clean.
- `eks` is a Python urwid TUI that reads `~/.environment/eks-clusters.dat`, logs in via AWS SSO, writes the selected profile to `~/.environment/.env_set.sh`, and runs `aws eks update-kubeconfig` to set the default kubectl context.
- `k3s` is a Python urwid TUI that reads `~/.environment/k3s-clusters.dat` and sets the default kubectl context to the selected k3s cluster via `kubectl config use-context`.
- `what-did-i` / `what-did-i-accomplish-today.py` queries today's git commits from GitHub (via `gh`) and Gitea (via REST API) and writes a dated Markdown summary to `$JOURNAL_PATH/ACCOMPLISHMENTS/YYYY-MM/git-work-for-YYYY-MM-DD.md` (Linux: `~/Journal/Personal Journal`; macOS: `~/Journal/Professional`); also prints to stdout.
- `walk_thru_readme_and_find_missing_files.py` checks `README.md` files for local Markdown links that point to missing files.
- `walk_thru_repo_looking_for_files_missing_from_README.py` finds Markdown files in the repo that are not linked from a sibling `README.md`.
- `create-ticket-in-youtrack` / `create-ticket-in-youtrack.py` interactively creates a YouTrack issue in either `Work - Inbox` or `Kevin - Inbox`; reads the server URL from `$YOUTRACK_SERVER` and the API token from `~/.config/YouTrack/self-host-api.txt`. Prints the human-readable issue ID and a clickable issue URL on success.
- `trufflehog.sh` scans credential-relevant paths for secrets using TruffleHog; detects the current platform (Fedora, macOS, Raspberry Pi) and adjusts paths accordingly. Prints a summary grouped by detector. Compare output against `~/.environment/.credentials-map.md` to identify undocumented credentials.
- `wd` prints the current working directory, replacing the `$HOME` prefix with `~` when inside the home directory.

## Subprojects

- [`file-tools/`](./file-tools) contains tools for locating, searching, or manipulating files.
- [`rss-feed-generators/`](./rss-feed-generators) contains self-contained RSS feed generator scripts and related notes.
