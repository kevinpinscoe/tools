# Tools

This repository collects small tools and automation scripts I have created for Linux, macOS, and Raspberry Pi systems.

Some of these scripts are also referenced from my playbook, so I keep them here in one place for versioning, reuse, and maintenance.

Most of the top-level files are standalone utilities. The main structured subproject is [`rss-feed-generators/`](./rss-feed-generators), which contains self-contained RSS feed generator scripts and related notes.

## Top-level scripts

- `gitcf` is a Python TUI that lists every untracked or modified file in the current git repo, lets you multi-select via an urwid checkbox picker, optionally prompts for a commit memo override, commits each selection, then pushes `HEAD` to `origin`.
- `ddir` / `ddir.py` compares two directories recursively, reporting missing files and running side-by-side diffs on files that differ.
- `decode-tldr-tracking-links.sh` decodes TLDR newsletter tracking links so the underlying destination URL is easier to inspect.
- `find-in-ai.sh` searches Markdown notes in the current tree with `rg`.
- `find-obsidian-vaults` finds Obsidian vaults under `$HOME` by locating `.obsidian` directories.
- `jsonfmt` safely formats JSON and JSONC files in place.
- `obsidian-backup-this-vault.sh` creates timestamped backups of the current Obsidian vault and prunes older archives.
- `ticket` is a Python TUI workspace manager for ticket-based development; clones selected repos into `~/Projects/workspaces/<TICKET>/` on a `kevini/<TICKET>` branch and opens a tmux + VS Code session.
- `walk_thru_readme_and_find_missing_files.py` checks `README.md` files for local Markdown links that point to missing files.
- `walk_thru_repo_looking_for_files_missing_from_README.py` finds Markdown files in the repo that are not linked from a sibling `README.md`.
- `create-ticket-in-youtrack` / `create-ticket-in-youtrack.py` interactively creates a YouTrack issue in either `Work - Inbox` or `Kevin - Inbox`; reads the server URL from `$YOUTRACK_SERVER` and the API token from `~/.config/YouTrack/self-host-api.txt`. Prints the human-readable issue ID and a clickable issue URL on success.

## Subprojects

- [`file-tools/`](./file-tools) contains tools for locating, searching, or manipulating files.
- [`rss-feed-generators/`](./rss-feed-generators) contains self-contained RSS feed generator scripts and related notes.
